#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate a versioned chapter attempt before review or commit."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path

import 公共工具 as tool


REVIEW_DIMENSIONS = [
    "event_order", "facts", "numbers", "causality", "polarity", "coreference",
    "character_knowledge", "dialogue_intent", "motivation", "pov", "timeline",
    "system_boundary", "chapter_hook",
]
REVIEW_KINDS = {"naturalization", "context"}
NATURALIZATION_RESULTS = {
    "candidate", "repaired", "reverted", "skipped", "accepted", "not_requested",
}
PRE_REVIEW_STATES = {"draft_generated", "naturalization_candidate", "review_pending"}
POST_REVIEW_STATES = {"review_pending", "review_passed", "summary_staged", "commit_prepared"}
STATE_VALIDATION_STATES = {"summary_staged", "commit_prepared"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
ATTEMPT_ID_RE = re.compile(r"^attempt-[0-9]{4,}$")
PROTECTED_VALUE_PATTERN = re.compile(
    r"(生存点|积分|余额|点数|库存|任务|模块|等级|时间|小时|天|公里|度|分|元|%)"
    r"\s*[:：]?\s*(-?\d+(?:\.\d+)?)"
)
NEGATION_MARKERS = ["不是", "没有", "未", "无", "禁止", "不得", "绝不", "从不", "无法", "不可能"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        match = re.match(r"^([a-z0-9_]+):\s*(.+)$", line)
        if match:
            result[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    return {}


def strip_markdown(text: str) -> str:
    lines = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def compare_sequences(source_text: str, candidate_text: str):
    errors = []
    source = strip_markdown(source_text)
    candidate = strip_markdown(candidate_text)
    src_vals = sorted(PROTECTED_VALUE_PATTERN.findall(source))
    cand_vals = sorted(PROTECTED_VALUE_PATTERN.findall(candidate))
    if src_vals != cand_vals:
        errors.append(f"protected value changed: source={src_vals} candidate={cand_vals}")
    src_negs = sum(source.count(marker) for marker in NEGATION_MARKERS)
    cand_negs = sum(candidate.count(marker) for marker in NEGATION_MARKERS)
    if src_negs != cand_negs:
        errors.append(f"negation marker count changed: source={src_negs} candidate={cand_negs}")
    return not errors, errors


def infer_project_root(attempt_dir: Path) -> Path | None:
    resolved = attempt_dir.resolve()
    for parent in [resolved, *resolved.parents]:
        if parent.name == "attempts" and len(parent.parents) >= 3:
            return parent.parents[2]
    return None


def resolve_source_path(raw_path: str, attempt_dir: Path, project_root: Path | None) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        if project_root is None:
            raise ValueError("relative fact-lock source_path requires --project-root")
        path = project_root / path
    resolved = path.resolve()
    if project_root is not None and not resolved.is_relative_to(project_root.resolve()):
        raise ValueError(f"fact-lock source_path escapes project root: {raw_path}")
    return resolved


def validate_required_frontmatter(front: dict, required: list[str], label: str) -> list[str]:
    errors = []
    for key in required:
        if not front.get(key):
            errors.append(f"{label} missing required frontmatter: {key}")
    return errors


def validate_iso_timestamp(value: str, label: str) -> list[str]:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return [f"{label} must be an ISO-8601 timestamp"]
    if parsed.tzinfo is None:
        return [f"{label} must include a timezone"]
    return []


def validate_review_report(path: Path, *, kind: str, node_id: str, attempt_id: str,
                           source_hash: str, candidate_hash: str,
                           fact_lock_hash: str) -> list[str]:
    if not path.is_file():
        return [f"missing {kind} review report: {path.name}"]
    front = parse_frontmatter(path)
    required = [
        "review_id", "reviewer_id", "node_id", "attempt_id", "review_kind", "source_sha256", "reviewed_sha256",
        "fact_lock_sha256", "review_prompt_version", "reviewed_at", "total_result",
    ]
    errors = validate_required_frontmatter(front, required, kind)
    expected = {
        "node_id": node_id,
        "attempt_id": attempt_id,
        "review_kind": kind,
        "source_sha256": source_hash,
        "reviewed_sha256": candidate_hash,
        "fact_lock_sha256": fact_lock_hash,
        "total_result": "pass",
    }
    for key, value in expected.items():
        if front.get(key) and front[key] != value:
            errors.append(f"{kind} review {key} mismatch")
    for key in ("source_sha256", "reviewed_sha256", "fact_lock_sha256"):
        if front.get(key) and not SHA256_RE.fullmatch(front[key]):
            errors.append(f"{kind} review {key} invalid")
    if front.get("review_id") and not NODE_ID_RE.fullmatch(front["review_id"]):
        errors.append(f"{kind} review_id invalid")
    if front.get("reviewer_id") and not NODE_ID_RE.fullmatch(front["reviewer_id"]):
        errors.append(f"{kind} reviewer_id invalid")
    if front.get("reviewed_at"):
        errors.extend(validate_iso_timestamp(front["reviewed_at"], f"{kind} reviewed_at"))
    text = path.read_text(encoding="utf-8")
    found = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"^\|\s*(event_order|facts|numbers|causality|polarity|coreference|"
            r"character_knowledge|dialogue_intent|motivation|pov|timeline|"
            r"system_boundary|chapter_hook)\s*\|\s*(pass|fail)\s*\|",
            text,
            re.MULTILINE,
        )
    }
    for dimension in REVIEW_DIMENSIONS:
        if found.get(dimension) != "pass":
            errors.append(f"{kind} review dimension is not pass: {dimension}")
    return errors


def validate_state_evidence(attempt_dir: Path, *, node_id: str, attempt_id: str,
                            candidate_hash: str, fact_lock_ids: set[str]) -> list[str]:
    errors = []
    final_body = attempt_dir / "workspace" / "final_body.md"
    delta_path = attempt_dir / "deltas" / "state.json"
    review_path = attempt_dir / "reviews" / "state.md"
    for path in (final_body, delta_path, review_path):
        if not path.is_file():
            errors.append(f"missing state validation file: {path.relative_to(attempt_dir)}")
    if errors:
        return errors
    final_hash = sha256_file(final_body)
    if final_hash != candidate_hash:
        errors.append("final_body.md does not match reviewed candidate")
    deltas = read_json(delta_path)
    if not isinstance(deltas, list):
        return errors + ["deltas/state.json must be a list"]
    body_text = final_body.read_text(encoding="utf-8")
    seen = set()
    required = {
        "delta_id", "field", "old_value", "new_value", "source_anchor",
        "source_excerpt_sha256", "fact_lock_ids",
    }
    for delta in deltas:
        if not isinstance(delta, dict) or not required.issubset(delta):
            errors.append("state delta missing required fields")
            continue
        delta_id = str(delta["delta_id"])
        if delta_id in seen:
            errors.append(f"duplicate state delta: {delta_id}")
        seen.add(delta_id)
        anchor = str(delta["source_anchor"])
        if not anchor or anchor not in body_text:
            errors.append(f"state delta source anchor missing: {delta_id}")
        elif sha256_text(anchor) != delta["source_excerpt_sha256"]:
            errors.append(f"state delta excerpt hash mismatch: {delta_id}")
        refs = delta["fact_lock_ids"]
        if not isinstance(refs, list) or not set(refs).issubset(fact_lock_ids):
            errors.append(f"state delta fact lock reference invalid: {delta_id}")
    front = parse_frontmatter(review_path)
    required_front = [
        "node_id", "attempt_id", "reviewed_sha256", "state_delta_sha256",
        "review_prompt_version", "reviewed_at", "total_result",
    ]
    errors.extend(validate_required_frontmatter(front, required_front, "state review"))
    expected = {
        "node_id": node_id,
        "attempt_id": attempt_id,
        "reviewed_sha256": candidate_hash,
        "state_delta_sha256": sha256_file(delta_path),
        "total_result": "pass",
    }
    for key, value in expected.items():
        if front.get(key) and front[key] != value:
            errors.append(f"state review {key} mismatch")
    return errors


def check_attempt(attempt_dir: Path, *, project_root: Path | None = None,
                  require_reviews: bool = False,
                  require_state_validation: bool = False):
    attempt_dir = Path(attempt_dir)
    project_root = Path(project_root) if project_root else infer_project_root(attempt_dir)
    report = {"ok": True, "attempt_dir": str(attempt_dir), "checks": {}}
    workspace = attempt_dir / "workspace"
    paths = {
        "source": workspace / "source.md",
        "candidate": attempt_dir / "candidate.md",
        "record": attempt_dir / "naturalization.md",
        "state": attempt_dir / "state.json",
        "fact_lock": attempt_dir / "fact-lock.json",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    report["checks"]["files"] = {"ok": not missing, "errors": [f"missing files: {missing}"] if missing else []}
    if missing:
        report["ok"] = False
        return report

    source_hash = sha256_file(paths["source"])
    candidate_hash = sha256_file(paths["candidate"])
    fact_lock_hash = sha256_file(paths["fact_lock"])
    front = parse_frontmatter(paths["record"])
    state = read_json(paths["state"], {})
    hash_errors = []
    for key, actual in (("source_sha256", source_hash), ("candidate_sha256", candidate_hash)):
        value = front.get(key)
        if not value:
            hash_errors.append(f"naturalization missing required frontmatter: {key}")
        elif not SHA256_RE.fullmatch(value):
            hash_errors.append(f"invalid {key}")
        elif value != actual:
            hash_errors.append(f"{key} mismatch")
    report["checks"]["hashes"] = {"ok": not hash_errors, "errors": hash_errors}
    metadata_errors = validate_required_frontmatter(
        front,
        ["node_id", "attempt_id", "source_sha256", "candidate_sha256",
         "prompt_version", "processed_at", "naturalization_result"],
        "naturalization",
    )
    node_id = front.get("node_id", "")
    attempt_id = front.get("attempt_id", "")
    if node_id and not NODE_ID_RE.fullmatch(node_id):
        metadata_errors.append("invalid node_id")
    if attempt_id and not ATTEMPT_ID_RE.fullmatch(attempt_id):
        metadata_errors.append("invalid attempt_id")
    if front.get("source_sha256") and front["source_sha256"] != source_hash:
        metadata_errors.append("source_sha256 mismatch")
    if front.get("candidate_sha256") and front["candidate_sha256"] != candidate_hash:
        metadata_errors.append("candidate_sha256 mismatch")
    for key in ("source_sha256", "candidate_sha256"):
        if front.get(key) and not SHA256_RE.fullmatch(front[key]):
            metadata_errors.append(f"invalid {key}")
    if front.get("naturalization_result") not in NATURALIZATION_RESULTS:
        metadata_errors.append("invalid naturalization_result")
    if front.get("processed_at"):
        metadata_errors.extend(validate_iso_timestamp(front["processed_at"], "processed_at"))
    if front.get("naturalization_result") in {"skipped", "not_requested"} and source_hash != candidate_hash:
        metadata_errors.append(
            f"{front['naturalization_result']} must use the source bytes as candidate"
        )
    if state.get("node_id") != node_id or state.get("attempt_id") != attempt_id:
        metadata_errors.append("state node_id/attempt_id mismatch")
    report["checks"]["metadata"] = {"ok": not metadata_errors, "errors": metadata_errors}

    lock_errors = []
    fact_locks = read_json(paths["fact_lock"])
    lock_ids = set()
    if not isinstance(fact_locks, list) or not fact_locks:
        lock_errors.append("fact-lock.json must be a non-empty list")
        fact_locks = []
    for lock in fact_locks:
        required = {"lock_id", "category", "expected_value", "source_path", "source_anchor", "source_sha256"}
        if not isinstance(lock, dict) or not required.issubset(lock):
            lock_errors.append("fact lock missing required fields")
            continue
        lock_id = str(lock["lock_id"])
        if lock_id in lock_ids:
            lock_errors.append(f"duplicate fact lock ID: {lock_id}")
        lock_ids.add(lock_id)
        try:
            source_path = resolve_source_path(str(lock["source_path"]), attempt_dir, project_root)
        except ValueError as exc:
            lock_errors.append(str(exc))
            continue
        if not source_path.is_file():
            lock_errors.append(f"fact lock source missing: {lock['source_path']}")
            continue
        if not SHA256_RE.fullmatch(str(lock["source_sha256"])):
            lock_errors.append(f"fact lock source hash invalid: {lock_id}")
        elif sha256_file(source_path) != lock["source_sha256"]:
            lock_errors.append(f"fact lock source hash changed: {lock_id}")
        anchor = str(lock["source_anchor"])
        if not anchor or anchor not in source_path.read_text(encoding="utf-8"):
            lock_errors.append(f"fact lock source anchor missing: {lock_id}")
    report["checks"]["fact_lock"] = {"ok": not lock_errors, "errors": lock_errors}

    status_errors = []
    status = state.get("status")
    allowed_states = POST_REVIEW_STATES if require_reviews else PRE_REVIEW_STATES
    if require_state_validation:
        allowed_states = STATE_VALIDATION_STATES
    if status not in allowed_states:
        status_errors.append(f"status {status!r} is not allowed for this validation phase")
    report["checks"]["state"] = {"ok": not status_errors, "errors": status_errors}

    diff_ok, diff_errors = compare_sequences(
        paths["source"].read_text(encoding="utf-8"),
        paths["candidate"].read_text(encoding="utf-8"),
    )
    report["checks"]["differences"] = {"ok": diff_ok, "errors": diff_errors}

    if require_reviews:
        review_errors = []
        review_fronts = []
        for kind in sorted(REVIEW_KINDS):
            review_path = attempt_dir / "reviews" / f"{kind}.md"
            review_errors.extend(validate_review_report(
                review_path,
                kind=kind,
                node_id=node_id,
                attempt_id=attempt_id,
                source_hash=source_hash,
                candidate_hash=candidate_hash,
                fact_lock_hash=fact_lock_hash,
            ))
            if review_path.is_file():
                review_fronts.append(parse_frontmatter(review_path))
        if len(review_fronts) == 2:
            if len({front.get("review_id") for front in review_fronts}) != 2:
                review_errors.append("review_id must be unique across independent reviews")
            if len({front.get("reviewer_id") for front in review_fronts}) != 2:
                review_errors.append("reviewer_id must be unique across independent reviews")
        report["checks"]["reviews"] = {"ok": not review_errors, "errors": review_errors}

    if require_state_validation:
        state_evidence_errors = validate_state_evidence(
            attempt_dir,
            node_id=node_id,
            attempt_id=attempt_id,
            candidate_hash=candidate_hash,
            fact_lock_ids=lock_ids,
        )
        report["checks"]["state_evidence"] = {
            "ok": not state_evidence_errors,
            "errors": state_evidence_errors,
        }

    report["ok"] = all(detail["ok"] for detail in report["checks"].values())
    return report


def main():
    parser = argparse.ArgumentParser(description="MyNovel chapter attempt validator")
    parser.add_argument("--attempt-dir", required=True, type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--require-reviews", action="store_true")
    parser.add_argument("--require-state-validation", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_attempt(
        args.attempt_dir,
        project_root=args.project_root,
        require_reviews=args.require_reviews,
        require_state_validation=args.require_state_validation,
    )
    if args.json:
        tool.json_dump(report)
    else:
        lines = []
        for name, detail in report["checks"].items():
            lines.append(f"[{'OK' if detail['ok'] else 'FAIL'}] {name}")
            lines.extend(f"        {error}" for error in detail["errors"])
        lines.append(f"result: {'pass' if report['ok'] else 'fail'}")
        tool.write_stdout("\n".join(lines) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
