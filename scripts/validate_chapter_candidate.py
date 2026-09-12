#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate a versioned chapter attempt before review or commit."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from collections import Counter
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
PROTECTED_PREFIX_PATTERN = re.compile(
    r"(生存点|积分|余额|点数|库存|任务|模块|等级|时间)"
    r"\s*[:：]?\s*(-?\d+(?:\.\d+)?%?)"
)
PROTECTED_SUFFIX_PATTERN = re.compile(
    r"((?:零下|-)?\d+(?:\.\d+)?)\s*"
    r"(公里/小时|千米/小时|摄氏度|小时|分钟|秒|公里|千米|厘米|毫米|米|"
    r"毫升|升|千克|公斤|克|吨|万元|元|级|生存点|点|千瓦|kW|瓦|W|伏|V|安|A|天|度|%|％)"
)
NEGATION_MARKERS = ["不是", "没有", "未", "无", "禁止", "不得", "绝不", "从不", "无法", "不可能"]
REPAIR_IMPACTS = {"metadata_only", "summary_rebuild", "state_rebuild", "rebase"}


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


def protected_values(text: str) -> list[str]:
    text = strip_markdown(text)
    values = [f"{label}={value}" for label, value in PROTECTED_PREFIX_PATTERN.findall(text)]
    values.extend(f"{unit}={value}" for value, unit in PROTECTED_SUFFIX_PATTERN.findall(text))
    return sorted(values)


def protected_value_differences(source_text: str, candidate_text: str):
    source_values = Counter(protected_values(source_text))
    candidate_values = Counter(protected_values(candidate_text))
    return source_values - candidate_values, candidate_values - source_values


def negation_count(text: str) -> int:
    text = strip_markdown(text)
    return sum(text.count(marker) for marker in NEGATION_MARKERS)


def compare_sequences(source_text: str, candidate_text: str):
    errors = []
    source = strip_markdown(source_text)
    candidate = strip_markdown(candidate_text)

    src_vals = protected_values(source_text)
    cand_vals = protected_values(candidate_text)
    if src_vals != cand_vals:
        errors.append(f"protected value changed: source={src_vals} candidate={cand_vals}")
    src_negs = negation_count(source)
    cand_negs = negation_count(candidate)
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


def validate_repair_changes(path: Path, basis_path: Path, *, source_text: str,
                            candidate_text: str):
    errors = []
    changes = read_json(path)
    if not isinstance(changes, list) or not changes:
        return {
            "errors": ["approved-changes.json must be a non-empty list"],
            "changed_lock_ids": set(),
            "lock_new_values": {},
            "downstream_impacts": set(),
            "impact_changes": [],
        }
    basis_text = basis_path.read_text(encoding="utf-8")
    source_removed, candidate_added = protected_value_differences(source_text, candidate_text)
    approved_removed = Counter()
    approved_added = Counter()
    changed_lock_ids = set()
    lock_new_values: dict[str, set[str]] = {}
    approved_negation_delta = 0
    change_ids = set()
    downstream_impacts = set()
    impact_changes = []
    source_spans = []
    candidate_spans = []
    required = {
        "change_id", "dimensions", "fact_lock_ids", "old_value", "new_value",
        "source_anchor", "source_anchor_sha256", "candidate_anchor",
        "candidate_anchor_sha256", "issue_anchor", "issue_anchor_sha256",
        "protected_values_before", "protected_values_after", "downstream_impact",
    }
    for change in changes:
        if not isinstance(change, dict) or not required.issubset(change):
            errors.append("approved change missing required fields")
            continue
        change_id = str(change["change_id"])
        if not NODE_ID_RE.fullmatch(change_id):
            errors.append(f"approved change_id invalid: {change_id}")
        elif change_id in change_ids:
            errors.append(f"duplicate approved change_id: {change_id}")
        change_ids.add(change_id)

        dimensions = change["dimensions"]
        if (not isinstance(dimensions, list) or not dimensions
                or any(item not in REVIEW_DIMENSIONS for item in dimensions)):
            errors.append(f"approved change dimensions invalid: {change_id}")
            dimensions = []
        lock_ids = change["fact_lock_ids"]
        if not isinstance(lock_ids, list) or any(not isinstance(item, str) for item in lock_ids):
            errors.append(f"approved change fact_lock_ids invalid: {change_id}")
            lock_ids = []
        elif dimensions and any(item in {
            "event_order", "facts", "numbers", "polarity", "character_knowledge",
            "dialogue_intent", "timeline", "system_boundary", "chapter_hook",
        } for item in dimensions) and not lock_ids:
            errors.append(f"factual approved change requires fact_lock_ids: {change_id}")

        old_value = str(change["old_value"]).strip()
        new_value = str(change["new_value"]).strip()
        source_anchor = str(change["source_anchor"])
        candidate_anchor = str(change["candidate_anchor"])
        issue_anchor = str(change["issue_anchor"])
        if not old_value or not new_value or old_value == new_value:
            errors.append(f"approved change old/new values invalid: {change_id}")
        if old_value and old_value not in source_anchor:
            errors.append(f"approved change old_value missing from source anchor: {change_id}")
        if new_value and new_value not in candidate_anchor:
            errors.append(f"approved change new_value missing from candidate anchor: {change_id}")
        if old_value and source_anchor.count(old_value) != 1:
            errors.append(
                f"approved change old_value must occur exactly once in source anchor: {change_id}"
            )
        elif old_value and new_value and source_anchor.replace(old_value, new_value, 1) != candidate_anchor:
            errors.append(
                f"approved change anchor contains edits beyond declared old/new replacement: {change_id}"
            )
        for label, anchor, text, declared_hash in (
            ("source", source_anchor, source_text, str(change["source_anchor_sha256"])),
            ("candidate", candidate_anchor, candidate_text,
             str(change["candidate_anchor_sha256"])),
            ("issue", issue_anchor, basis_text, str(change["issue_anchor_sha256"])),
        ):
            if not anchor or anchor not in text:
                errors.append(f"approved change {label} anchor missing: {change_id}")
            elif not SHA256_RE.fullmatch(declared_hash):
                errors.append(f"approved change {label} anchor hash invalid: {change_id}")
            elif sha256_text(anchor) != declared_hash:
                errors.append(f"approved change {label} anchor hash mismatch: {change_id}")
        marker = f"\0MYNOVEL_APPROVED_CHANGE:{change_id}\0"
        for label, anchor, text, spans in (
            ("source", source_anchor, source_text, source_spans),
            ("candidate", candidate_anchor, candidate_text, candidate_spans),
        ):
            count = text.count(anchor) if anchor else 0
            if count != 1:
                errors.append(
                    f"approved change {label} anchor must occur exactly once: {change_id}"
                )
            else:
                start = text.index(anchor)
                spans.append((start, start + len(anchor), marker, change_id))

        before = change["protected_values_before"]
        after = change["protected_values_after"]
        if not isinstance(before, list) or not all(isinstance(item, str) for item in before):
            errors.append(f"approved change protected_values_before invalid: {change_id}")
            before = []
        if not isinstance(after, list) or not all(isinstance(item, str) for item in after):
            errors.append(f"approved change protected_values_after invalid: {change_id}")
            after = []
        anchor_before = Counter(protected_values(source_anchor))
        anchor_after = Counter(protected_values(candidate_anchor))
        if Counter(before) - anchor_before:
            errors.append(f"approved change protected before token not in source anchor: {change_id}")
        if Counter(after) - anchor_after:
            errors.append(f"approved change protected after token not in candidate anchor: {change_id}")
        approved_removed.update(before)
        approved_added.update(after)

        impact = str(change["downstream_impact"])
        if impact not in REPAIR_IMPACTS:
            errors.append(f"approved change downstream_impact invalid: {change_id}")
        else:
            downstream_impacts.add(impact)
            impact_changes.append({
                "change_id": change_id,
                "impact": impact,
                "old_value": old_value,
                "new_value": new_value,
                "fact_lock_ids": set(lock_ids),
            })
        if dimensions and any(item in {
            "event_order", "facts", "numbers", "polarity", "character_knowledge",
            "dialogue_intent", "timeline", "system_boundary", "chapter_hook",
        } for item in dimensions) and impact == "metadata_only":
            errors.append(f"factual approved change cannot be metadata_only: {change_id}")

        if "polarity" in dimensions:
            approved_negation_delta += negation_count(candidate_anchor) - negation_count(source_anchor)
        for lock_id in lock_ids:
            changed_lock_ids.add(lock_id)
            lock_new_values.setdefault(lock_id, set()).add(new_value)

    if approved_removed != source_removed:
        errors.append(
            f"approved protected source changes mismatch: approved={sorted(approved_removed.elements())} "
            f"actual={sorted(source_removed.elements())}"
        )
    if approved_added != candidate_added:
        errors.append(
            f"approved protected candidate changes mismatch: approved={sorted(approved_added.elements())} "
            f"actual={sorted(candidate_added.elements())}"
        )
    actual_negation_delta = negation_count(candidate_text) - negation_count(source_text)
    if approved_negation_delta != actual_negation_delta:
        errors.append(
            f"approved polarity delta mismatch: approved={approved_negation_delta} "
            f"actual={actual_negation_delta}"
        )

    def mask_approved_anchors(text: str, spans: list[tuple[int, int, str, str]], label: str):
        masked = []
        cursor = 0
        for start, end, marker, change_id in sorted(spans):
            if start < cursor:
                errors.append(f"approved change {label} anchors overlap: {change_id}")
                continue
            masked.extend((text[cursor:start], marker))
            cursor = end
        masked.append(text[cursor:])
        return "".join(masked)

    masked_source = mask_approved_anchors(source_text, source_spans, "source")
    masked_candidate = mask_approved_anchors(candidate_text, candidate_spans, "candidate")
    if masked_source != masked_candidate:
        errors.append("candidate contains changes outside approved source/candidate anchors")
    return {
        "errors": errors,
        "changed_lock_ids": changed_lock_ids,
        "lock_new_values": lock_new_values,
        "downstream_impacts": downstream_impacts,
        "impact_changes": impact_changes,
    }


def validate_review_report(path: Path, *, kind: str, node_id: str, attempt_id: str,
                           source_hash: str, candidate_hash: str,
                           fact_lock_hash: str,
                           review_subject: str | None = None,
                           approved_changes_hash: str | None = None) -> list[str]:
    if not path.is_file():
        return [f"missing {kind} review report: {path.name}"]
    front = parse_frontmatter(path)
    required = [
        "review_id", "reviewer_id", "node_id", "attempt_id", "review_kind", "source_sha256", "reviewed_sha256",
        "fact_lock_sha256", "review_prompt_version", "reviewed_at", "total_result",
    ]
    if review_subject == "working_copy":
        required.extend([
            "review_subject", "base_committed_sha256", "working_copy_sha256",
        ])
    elif review_subject == "repair":
        required.extend([
            "review_subject", "base_committed_sha256", "repair_candidate_sha256",
            "approved_changes_sha256",
        ])
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
    if review_subject == "working_copy":
        expected.update({
            "review_subject": "working_copy",
            "base_committed_sha256": source_hash,
            "working_copy_sha256": candidate_hash,
        })
    elif review_subject == "repair":
        expected.update({
            "review_subject": "repair",
            "base_committed_sha256": source_hash,
            "repair_candidate_sha256": candidate_hash,
            "approved_changes_sha256": approved_changes_hash or "",
        })
    for key, value in expected.items():
        if front.get(key) and front[key] != value:
            errors.append(f"{kind} review {key} mismatch")
    hash_keys = ["source_sha256", "reviewed_sha256", "fact_lock_sha256"]
    if review_subject == "repair":
        hash_keys.append("approved_changes_sha256")
    for key in hash_keys:
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
        match.group(1): (match.group(2), match.group(3).strip())
        for match in re.finditer(
            r"^\|\s*(event_order|facts|numbers|causality|polarity|coreference|"
            r"character_knowledge|dialogue_intent|motivation|pov|timeline|"
            r"system_boundary|chapter_hook)\s*\|\s*(pass|fail)\s*\|\s*([^|\r\n]*)\|\s*$",
            text,
            re.MULTILINE,
        )
    }
    for dimension in REVIEW_DIMENSIONS:
        result, evidence = found.get(dimension, (None, ""))
        if result != "pass":
            errors.append(f"{kind} review dimension is not pass: {dimension}")
        elif not evidence or evidence.lower() in {"...", "…", "-", "none", "n/a"}:
            errors.append(f"{kind} review dimension evidence is empty: {dimension}")
    return errors


def validate_state_evidence(attempt_dir: Path, *, node_id: str, attempt_id: str,
                            candidate_hash: str, fact_lock_ids: set[str],
                            downstream_impacts: set[str] | None = None,
                            impact_changes: list[dict] | None = None) -> list[str]:
    errors = []
    downstream_impacts = downstream_impacts or set()
    impact_changes = impact_changes or []
    require_summary_delta = bool(
        downstream_impacts & {"summary_rebuild", "state_rebuild", "rebase"}
    )
    require_state_delta = bool(downstream_impacts & {"state_rebuild", "rebase"})
    final_body = attempt_dir / "workspace" / "final_body.md"
    delta_path = attempt_dir / "deltas" / "state.json"
    summary_delta_path = attempt_dir / "deltas" / "summary.md"
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
    if require_state_delta and not deltas:
        errors.append("state_rebuild/rebase requires a non-empty deltas/state.json")
    if require_summary_delta:
        if not summary_delta_path.is_file():
            errors.append("summary/state rebuild requires deltas/summary.md")
        elif not summary_delta_path.read_text(encoding="utf-8").strip():
            errors.append("deltas/summary.md must be non-empty")
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
    summary_text = (
        summary_delta_path.read_text(encoding="utf-8")
        if summary_delta_path.is_file() else ""
    )
    for change in impact_changes:
        if change["impact"] in {"summary_rebuild", "state_rebuild", "rebase"}:
            if change["change_id"] not in summary_text:
                errors.append(
                    f"summary delta does not cover approved change: {change['change_id']}"
                )
        if change["impact"] in {"state_rebuild", "rebase"}:
            matched = False
            for delta in deltas:
                if not isinstance(delta, dict):
                    continue
                refs = delta.get("fact_lock_ids", [])
                if (str(delta.get("old_value", "")) == change["old_value"]
                        and str(delta.get("new_value", "")) == change["new_value"]
                        and isinstance(refs, list)
                        and change["fact_lock_ids"].issubset(set(refs))):
                    matched = True
                    break
            if not matched:
                errors.append(
                    f"state delta does not cover approved change: {change['change_id']}"
                )
    front = parse_frontmatter(review_path)
    required_front = [
        "node_id", "attempt_id", "reviewed_sha256", "state_delta_sha256",
        "review_prompt_version", "reviewed_at", "total_result",
    ]
    if require_summary_delta:
        required_front.append("summary_delta_sha256")
    errors.extend(validate_required_frontmatter(front, required_front, "state review"))
    expected = {
        "node_id": node_id,
        "attempt_id": attempt_id,
        "reviewed_sha256": candidate_hash,
        "state_delta_sha256": sha256_file(delta_path),
        "total_result": "pass",
    }
    if require_summary_delta and summary_delta_path.is_file():
        expected["summary_delta_sha256"] = sha256_file(summary_delta_path)
    for key, value in expected.items():
        if front.get(key) and front[key] != value:
            errors.append(f"state review {key} mismatch")
    return errors


def check_attempt(attempt_dir: Path, *, project_root: Path | None = None,
                   require_reviews: bool = False,
                   require_state_validation: bool = False,
                   allow_working_copy: bool = False,
                   allow_repair: bool = False):
    attempt_dir = Path(attempt_dir)
    project_root = Path(project_root) if project_root else infer_project_root(attempt_dir)
    report = {
        "ok": True,
        "attempt_dir": str(attempt_dir),
        "validation_mode": (
            "repair" if allow_repair else "working_copy" if allow_working_copy else "strict"
        ),
        "eligible_for_review_passed": False,
        "checks": {},
    }
    workspace = attempt_dir / "workspace"
    paths = {
        "source": workspace / "source.md",
        "candidate": attempt_dir / "candidate.md",
        "record": attempt_dir / "naturalization.md",
        "state": attempt_dir / "state.json",
        "fact_lock": attempt_dir / "fact-lock.json",
    }
    if allow_repair:
        paths.update({
            "approved_changes": attempt_dir / "approved-changes.json",
            "repair_basis": workspace / "repair-basis.md",
        })
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
    mode_errors = []
    if allow_working_copy and allow_repair:
        mode_errors.append("--allow-working-copy and --allow-repair are mutually exclusive")
    report["checks"]["mode"] = {"ok": not mode_errors, "errors": mode_errors}
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

    subject_errors = []
    subject_warnings = []
    review_subject = front.get("review_subject", "")
    approved_changes_hash = (
        sha256_file(paths["approved_changes"]) if allow_repair else None
    )
    repair_validation = {
        "errors": [], "changed_lock_ids": set(), "lock_new_values": {},
        "downstream_impacts": set(), "impact_changes": [],
    }
    if allow_working_copy:
        if not require_reviews:
            subject_errors.append("working copy validation requires --require-reviews")
        subject_errors.extend(validate_required_frontmatter(
            front,
            ["review_subject", "base_committed_sha256", "working_copy_sha256", "working_copy_path"],
            "working copy",
        ))
        if review_subject and review_subject != "working_copy":
            subject_errors.append("working copy review_subject must be working_copy")
        for key, actual in (
            ("base_committed_sha256", source_hash),
            ("working_copy_sha256", candidate_hash),
        ):
            value = front.get(key)
            if value and not SHA256_RE.fullmatch(value):
                subject_errors.append(f"working copy {key} invalid")
            elif value and value != actual:
                subject_errors.append(f"working copy {key} mismatch")
        raw_working_path = front.get("working_copy_path")
        if raw_working_path:
            try:
                working_path = resolve_source_path(raw_working_path, attempt_dir, project_root)
            except ValueError as exc:
                subject_errors.append(str(exc))
            else:
                if not working_path.is_file():
                    subject_errors.append(f"working copy file missing: {raw_working_path}")
                elif sha256_file(working_path) != candidate_hash:
                    subject_errors.append("working copy file does not match candidate.md")
        if state.get("status") == "review_passed":
            subject_errors.append("working copy evidence cannot use review_passed status")
        if require_state_validation:
            subject_errors.append("working copy evidence cannot enter state-validation/commit preparation")
        subject_warnings.append(
            "working copy validation is provisional and cannot create review_passed, rename正文, or attest the current commit chain"
        )
    elif allow_repair:
        if not require_reviews:
            subject_errors.append("repair validation requires --require-reviews")
        if not require_state_validation:
            subject_errors.append("repair validation requires --require-state-validation")
        subject_errors.extend(validate_required_frontmatter(
            front,
            ["review_subject", "base_committed_sha256", "repair_candidate_sha256",
             "repair_target_path", "approved_changes_sha256", "repair_basis_sha256"],
            "repair",
        ))
        if review_subject and review_subject != "repair":
            subject_errors.append("repair review_subject must be repair")
        for key, actual in (
            ("base_committed_sha256", source_hash),
            ("repair_candidate_sha256", candidate_hash),
            ("approved_changes_sha256", approved_changes_hash),
            ("repair_basis_sha256", sha256_file(paths["repair_basis"])),
        ):
            value = front.get(key)
            if value and not SHA256_RE.fullmatch(value):
                subject_errors.append(f"repair {key} invalid")
            elif value and value != actual:
                subject_errors.append(f"repair {key} mismatch")
        raw_target_path = front.get("repair_target_path")
        if raw_target_path:
            try:
                target_path = resolve_source_path(raw_target_path, attempt_dir, project_root)
            except ValueError as exc:
                subject_errors.append(str(exc))
            else:
                if not target_path.is_file():
                    subject_errors.append(f"repair target file missing: {raw_target_path}")
                elif sha256_file(target_path) != candidate_hash:
                    subject_errors.append("repair target file does not match candidate.md")
        repair_validation = validate_repair_changes(
            paths["approved_changes"],
            paths["repair_basis"],
            source_text=paths["source"].read_text(encoding="utf-8"),
            candidate_text=paths["candidate"].read_text(encoding="utf-8"),
        )
        report["checks"]["approved_changes"] = {
            "ok": not repair_validation["errors"],
            "errors": repair_validation["errors"],
        }
    elif review_subject in {"working_copy", "repair"}:
        subject_errors.append(
            f"{review_subject} attempt requires its matching --allow-{review_subject.replace('_', '-')} mode"
        )
    report["checks"]["review_subject"] = {
        "ok": not subject_errors,
        "errors": subject_errors,
        "warnings": subject_warnings,
    }

    lock_errors = []
    lock_warnings = []
    fact_locks = read_json(paths["fact_lock"])
    lock_ids = set()
    immutable_source_text = paths["source"].read_text(encoding="utf-8")
    candidate_text = paths["candidate"].read_text(encoding="utf-8")
    if not isinstance(fact_locks, list) or not fact_locks:
        lock_errors.append("fact-lock.json must be a non-empty list")
        fact_locks = []
    for lock in fact_locks:
        required = {"lock_id", "category", "expected_value", "source_path", "source_anchor", "source_sha256"}
        if allow_working_copy:
            required.update({"working_copy_anchor", "working_copy_anchor_sha256"})
        elif allow_repair:
            required.update({"repair_anchor", "repair_anchor_sha256"})
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
        declared_hash = str(lock["source_sha256"])
        if not SHA256_RE.fullmatch(declared_hash):
            lock_errors.append(f"fact lock source hash invalid: {lock_id}")
        anchor = str(lock["source_anchor"])
        expected_value = str(lock["expected_value"]).strip()
        if not expected_value:
            lock_errors.append(f"fact lock expected_value empty: {lock_id}")
        elif expected_value not in anchor:
            lock_errors.append(f"fact lock expected_value missing from source anchor: {lock_id}")
        if allow_working_copy or allow_repair:
            immutable_ok = (
                SHA256_RE.fullmatch(declared_hash)
                and source_hash == declared_hash
                and bool(anchor)
                and anchor in immutable_source_text
            )
            if not immutable_ok:
                lock_errors.append(f"fact lock immutable base evidence invalid: {lock_id}")
            else:
                live_ok = (
                    source_path.is_file()
                    and sha256_file(source_path) == declared_hash
                    and anchor in source_path.read_text(encoding="utf-8")
                )
                if not live_ok:
                    lock_warnings.append(
                        f"fact lock live source drifted; immutable workspace/source.md remains valid: {lock_id}"
                    )
            anchor_label = "repair" if allow_repair else "working-copy"
            candidate_anchor = str(lock.get(
                "repair_anchor" if allow_repair else "working_copy_anchor", ""
            ))
            candidate_anchor_hash = str(lock.get(
                "repair_anchor_sha256" if allow_repair else "working_copy_anchor_sha256", ""
            ))
            if not candidate_anchor or candidate_anchor not in candidate_text:
                lock_errors.append(f"fact lock {anchor_label} anchor missing: {lock_id}")
            elif not SHA256_RE.fullmatch(candidate_anchor_hash):
                lock_errors.append(f"fact lock {anchor_label} anchor hash invalid: {lock_id}")
            elif sha256_text(candidate_anchor) != candidate_anchor_hash:
                lock_errors.append(f"fact lock {anchor_label} anchor hash mismatch: {lock_id}")
            if allow_repair and lock_id in repair_validation["changed_lock_ids"]:
                new_values = repair_validation["lock_new_values"].get(lock_id, set())
                if not any(value in candidate_anchor for value in new_values):
                    lock_errors.append(f"approved repair value missing from repair anchor: {lock_id}")
            elif expected_value and expected_value not in candidate_anchor:
                lock_errors.append(
                    f"fact lock expected_value missing from {anchor_label} anchor: {lock_id}"
                )
        else:
            if not source_path.is_file():
                lock_errors.append(f"fact lock source missing: {lock['source_path']}")
                continue
            if SHA256_RE.fullmatch(declared_hash) and sha256_file(source_path) != declared_hash:
                lock_errors.append(f"fact lock source hash changed: {lock_id}")
            if not anchor or anchor not in source_path.read_text(encoding="utf-8"):
                lock_errors.append(f"fact lock source anchor missing: {lock_id}")
            if expected_value and expected_value not in candidate_text:
                lock_errors.append(f"fact lock expected_value missing from candidate: {lock_id}")
    if allow_repair:
        unknown_changed_locks = repair_validation["changed_lock_ids"] - lock_ids
        if unknown_changed_locks:
            lock_errors.append(
                f"approved changes reference unknown fact locks: {sorted(unknown_changed_locks)}"
            )
    report["checks"]["fact_lock"] = {
        "ok": not lock_errors,
        "errors": lock_errors,
        "warnings": lock_warnings,
    }

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
    diff_warnings = []
    if allow_working_copy:
        polarity_errors = [error for error in diff_errors if error.startswith("negation marker count changed:")]
        diff_errors = [error for error in diff_errors if error not in polarity_errors]
        diff_warnings.extend(
            f"{error}; semantic polarity must still pass both formal reviews"
            for error in polarity_errors
        )
        diff_ok = not diff_errors
    elif allow_repair:
        diff_errors = list(repair_validation["errors"])
        diff_ok = not diff_errors
        if diff_ok:
            diff_warnings.append(
                "source/candidate factual differences are fully covered by approved-changes.json"
            )
    report["checks"]["differences"] = {
        "ok": diff_ok,
        "errors": diff_errors,
        "warnings": diff_warnings,
    }

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
                review_subject=(
                    "repair" if allow_repair else "working_copy" if allow_working_copy else None
                ),
                approved_changes_hash=approved_changes_hash,
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
            downstream_impacts=(
                repair_validation["downstream_impacts"] if allow_repair else set()
            ),
            impact_changes=(repair_validation["impact_changes"] if allow_repair else []),
        )
        report["checks"]["state_evidence"] = {
            "ok": not state_evidence_errors,
            "errors": state_evidence_errors,
        }

    report["ok"] = all(detail["ok"] for detail in report["checks"].values())
    report["eligible_for_review_passed"] = report["ok"] and not allow_working_copy
    return report


def main():
    parser = argparse.ArgumentParser(description="MyNovel chapter attempt validator")
    parser.add_argument("--attempt-dir", required=True, type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--require-reviews", action="store_true")
    parser.add_argument("--require-state-validation", action="store_true")
    subject_group = parser.add_mutually_exclusive_group()
    subject_group.add_argument(
        "--allow-working-copy",
        action="store_true",
        help="validate a provisional current 正文/ working-copy attempt without making it commit-eligible",
    )
    subject_group.add_argument(
        "--allow-repair",
        action="store_true",
        help="validate an approved repair attempt for formal revision/rebase submission",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_attempt(
        args.attempt_dir,
        project_root=args.project_root,
        require_reviews=args.require_reviews,
        require_state_validation=args.require_state_validation,
        allow_working_copy=args.allow_working_copy,
        allow_repair=args.allow_repair,
    )
    if args.json:
        tool.json_dump(report)
    else:
        lines = []
        for name, detail in report["checks"].items():
            lines.append(f"[{'OK' if detail['ok'] else 'FAIL'}] {name}")
            lines.extend(f"        {error}" for error in detail["errors"])
            lines.extend(f"        warning: {warning}" for warning in detail.get("warnings", []))
        if not report["eligible_for_review_passed"]:
            reason = "working-copy evidence only" if args.allow_working_copy else "validation failed"
            lines.append(f"eligible_for_review_passed: false ({reason})")
        lines.append(f"result: {'pass' if report['ok'] else 'fail'}")
        tool.write_stdout("\n".join(lines) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
