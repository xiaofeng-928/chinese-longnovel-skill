#!/usr/bin/env python
"""Deterministically grade the four workflow eval outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CHECKS: dict[int, list[tuple[str, list[tuple[str, ...]]]]] = {
    1: [
        ("naturalization_before_review", [
            ("正式审查前必须先自然化", "自然化在正式审查前", "正文自然化先于正式审查"),
        ]),
        ("hashes_and_fact_lock", [
            ("source_sha256", "源稿哈希"),
            ("candidate_sha256", "候选哈希"),
            ("fact-lock", "事实锁"),
        ]),
        ("two_reviews", [
            ("reviews/naturalization.md", "自然化前后差异审查"),
            ("reviews/context.md", "候选对项目上下文审查", "候选正文对项目上下文审查"),
            ("独立", "不同 reviewer"),
        ]),
        ("state_and_cas", [("状态回证",), ("CAS",)]),
    ],
    2: [
        ("skipped_state", [("skipped",)]),
        ("byte_identity", [("字节",), ("一致", "相同")]),
        ("fact_lock_retained", [("事实锁", "fact-lock")]),
        ("review_retained", [("审查",)]),
    ],
    3: [
        ("numbers_failure", [("numbers", "数值"), ("fail", "失败", "阻断")]),
        ("polarity_failure", [("polarity", "否定极性"), ("fail", "失败", "阻断")]),
        ("new_attempt", [("新", "下一"), ("attempt",)]),
        ("commit_blocked", [("不得", "不更新", "阻止"), ("commit", "提交")]),
    ],
    4: [
        ("fresh_scan_reused", [("7 天", "7天", "30 天", "30天"), ("扫榜",), ("复用",)]),
        ("personal_assembly", [("经营",), ("开书方案", "方案")]),
        ("no_length_question", [("不询问", "不再询问", "无需询问", "不问"), ("短中长篇", "短篇")]),
        ("thousand_chapters", [("1000",)]),
    ],
}


def grade(eval_id: int, output: str) -> dict:
    results = []
    normalized = output.lower()
    for name, groups in CHECKS[eval_id]:
        passed = all(any(token.lower() in normalized for token in alternatives) for alternatives in groups)
        results.append({
            "text": name,
            "passed": passed,
            "evidence": f"required concept groups: {groups}",
        })
    passed_count = sum(item["passed"] for item in results)
    return {
        "expectations": results,
        "summary": {
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "total": len(results),
            "pass_rate": passed_count / len(results),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-id", required=True, type=int, choices=sorted(CHECKS))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--grading", required=True, type=Path)
    args = parser.parse_args()
    result = grade(args.eval_id, args.output.read_text(encoding="utf-8"))
    args.grading.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
