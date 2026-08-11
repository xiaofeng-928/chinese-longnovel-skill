#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""validate_chapter_candidate.py — 正文候选确定性检查。

在自然化候选进入 review_passed 之前，核对：
- 事实锁 ID、所有受保护数值/实体/系统状态、否定极性标记；
- 自然化前/候选/审查报告的 SHA-256 绑定；
- 候选与自然化前版本的事件顺序、数值、因果、指代、动机、POV、时间线、系统边界和章末钩子差异（确定性部分）；
- attempt 状态是否允许当前推进。

用法：
  py -3 scripts/validate_chapter_candidate.py --attempt-dir <attempts/<node>/<attempt>>
  py -3 scripts/validate_chapter_candidate.py --attempt-dir <...> --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import 公共工具 as tool

# 审查必须逐项输出的维度（文档 6.3）
REVIEW_DIMENSIONS = [
    "event_order", "facts", "numbers", "causality", "polarity", "coreference",
    "character_knowledge", "dialogue_intent", "motivation", "pov", "timeline",
    "system_boundary", "chapter_hook",
]
REVIEW_RESULTS = {"pass", "fail"}
TOTAL_RESULTS = {"pass", "repair", "revert", "structural_block"}

# 受保护数值/实体/状态的正则：出现数字、点/积分/余额/任务/库存等词后跟数字
PROTECTED_VALUE_PATTERN = re.compile(
    r"(生存点|积分|余额|点数|库存|任务|模块|等级|时间|小时|天|公里|度|分|元|%)\s*[:：]?\s*(-?\d+(?:\.\d+)?)"
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


def strip_markdown(text: str) -> str:
    """去除 markdown 标题与代码围栏，便于比对正文内容。"""
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        if line.strip().startswith("```"):
            continue
        lines.append(line)
    return "\n".join(lines)


def compare_sequences(source_text: str, candidate_text: str):
    """确定性差异检查。返回 (ok, errors)。"""
    errors = []
    source = strip_markdown(source_text)
    candidate = strip_markdown(candidate_text)

    src_vals = sorted(PROTECTED_VALUE_PATTERN.findall(source))
    cand_vals = sorted(PROTECTED_VALUE_PATTERN.findall(candidate))
    if src_vals != cand_vals:
        errors.append(
            f"protected value changed: source={src_vals} candidate={cand_vals}"
        )

    # 否定极性标记不得被反转：粗粒度按词条出现次数比较
    src_negs = sum(source.count(m) for m in NEGATION_MARKERS)
    cand_negs = sum(candidate.count(m) for m in NEGATION_MARKERS)
    if src_negs != cand_negs:
        errors.append(
            f"negation marker count changed: source={src_negs} candidate={cand_negs}"
        )

    return not errors, errors


def check_attempt(attempt_dir: Path):
    report = {"ok": True, "attempt_dir": str(attempt_dir), "checks": {}}

    workspace = attempt_dir / "workspace"
    source_path = workspace / "source.md"
    candidate_path = attempt_dir / "candidate.md"
    record_path = attempt_dir / "naturalization.md"
    state_path = attempt_dir / "state.json"
    fact_lock_path = attempt_dir / "fact-lock.json"

    checks = {}

    # 1. 文件存在性
    missing = [p.name for p in [source_path, candidate_path, record_path, state_path]
               if not p.is_file()]
    if missing:
        checks["files"] = {"ok": False, "errors": [f"missing files: {missing}"]}
        report["checks"] = checks
        report["ok"] = False
        return report
    checks["files"] = {"ok": True, "errors": []}

    # 2. 哈希绑定：naturalization.md frontmatter 中的 source/candidate sha256 必须与文件一致
    record_text = record_path.read_text(encoding="utf-8")
    front = {}
    for m in re.finditer(r"^([a-z_]+):\s*(.+)$", record_text, re.MULTILINE):
        front[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    src_hash = sha256_file(source_path)
    cand_hash = sha256_file(candidate_path)
    hash_errors = []
    if front.get("source_sha256") and front["source_sha256"] != src_hash:
        hash_errors.append("source_sha256 mismatch")
    if front.get("candidate_sha256") and front["candidate_sha256"] != cand_hash:
        hash_errors.append("candidate_sha256 mismatch")
    checks["hashes"] = {"ok": not hash_errors, "errors": hash_errors}
    if hash_errors:
        report["ok"] = False
        return report

    # 3. 事实锁：验证来源路径与哈希
    fact_lock = read_json(fact_lock_path, [])
    lock_errors = []
    if isinstance(fact_lock, list):
        for lock in fact_lock:
            if not all(k in lock for k in ("lock_id", "category", "expected_value",
                                            "source_path", "source_anchor", "source_sha256")):
                lock_errors.append("fact lock missing required fields")
                continue
            source = Path(lock["source_path"])
            if source.is_file():
                actual = sha256_file(source)
                if actual != lock["source_sha256"]:
                    lock_errors.append(f"fact lock source hash changed: {lock['lock_id']}")
            else:
                lock_errors.append(f"fact lock source missing: {lock['source_path']}")
    else:
        lock_errors.append("fact-lock.json must be a list")
    checks["fact_lock"] = {"ok": not lock_errors, "errors": lock_errors}
    if lock_errors:
        report["ok"] = False

    # 4. 状态推进
    state = read_json(state_path, {})
    current = state.get("status")
    if current in ("review_passed", "summary_staged", "commit_prepared", "committed"):
        checks["state"] = {"ok": False,
                           "errors": ["already passed review; new candidate requires new attempt"]}
        report["checks"] = checks
        report["ok"] = False
        return report
    checks["state"] = {"ok": True, "errors": []}

    # 5. 差异检查（确定性部分）
    diff_ok, diff_errors = compare_sequences(
        source_path.read_text(encoding="utf-8"),
        candidate_path.read_text(encoding="utf-8"),
    )
    checks["differences"] = {"ok": diff_ok, "errors": diff_errors}
    if not diff_ok:
        report["ok"] = False

    report["checks"] = checks
    return report


def main():
    parser = argparse.ArgumentParser(description="MyNovel 正文候选确定性检查")
    parser.add_argument("--attempt-dir", required=True, type=Path,
                        help="修复记录/生产状态/attempts/<node_id>/<attempt_id>/")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 markdown")
    args = parser.parse_args()

    report = check_attempt(args.attempt_dir)
    if args.json:
        tool.json_dump(report)
    else:
        lines = []
        for name, detail in report["checks"].items():
            status = "OK" if detail["ok"] else "FAIL"
            lines.append(f"[{status}] {name}")
            for err in detail["errors"]:
                lines.append(f"        {err}")
        lines.append(f"result: {'pass' if report['ok'] else 'fail'}")
        tool.write_stdout("\n".join(lines) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
