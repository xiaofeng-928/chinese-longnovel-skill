#!/usr/bin/env python
"""Deterministically grade the workflow eval outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CHECKS: dict[int, list[tuple[str, list[tuple[str, ...]]]]] = {
    1: [
        ("manual_trigger", [("手动", "明确要求", "用户要求"), ("自然化", "去ai")]),
        ("hashes_and_fact_lock", [
            ("source_sha256", "源稿哈希"),
            ("candidate_sha256", "候选哈希"),
            ("fact-lock", "事实锁"),
        ]),
        ("new_attempt_invalidates_review", [("新", "新的"), ("attempt",), ("旧审查",), ("失效",)]),
        ("facts_unchanged", [("不得", "不能", "不允许"), ("剧情", "事实"), ("状态", "仓库")]),
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
        ("new_attempt", [("新", "下一"), ("attempt",), ("验证",)]),
        ("commit_blocked", [("不得", "不更新", "阻止"), ("commit", "提交")]),
    ],
    4: [
        ("fresh_scan_reused", [("7 天", "7天", "30 天", "30天"), ("扫榜",), ("复用",)]),
        ("personal_assembly", [("经营",), ("开书方案", "方案")]),
        ("no_length_question", [("不询问", "不再询问", "无需询问", "不问"), ("短中长篇", "短篇")]),
        ("thousand_chapters", [("1000",)]),
    ],
    5: [
        ("pending_does_not_block", [("review_pending", "待审"), ("不阻断", "直接续写")]),
        ("old_batch_not_reviewed", [("第1-3章", "1-3章"), ("不先审", "无需先审", "不审查")]),
        ("requested_chapters_committed", [("第4-6章", "4-6章"), ("不自然化", "不自动自然化", "跳过自然化"), ("总结",), ("状态", "仓库"), ("提交",), ("review_pending",)]),
        ("no_automatic_review", [("不自动", "不会自动"), ("审查",)]),
    ],
    6: [
        ("five_chapter_review_batch", [("第11-15章", "11-15章"), ("5章", "五章", "连续5章", "连续五章")]),
        ("style_only_keeps_semantic_state", [("第12章",), ("句式", "表达"), ("不重", "无需重", "不重新"), ("总结",), ("仓库", "状态")]),
        ("fact_change_refreshes_deltas", [("第14章",), ("交易",), ("余额",), ("summary/state", "总结", "状态增量")]),
        ("downstream_rebuilt_from_impact", [("影响点", "第14章"), ("重建",), ("后续", "投影"), ("主角",), ("系统",)]),
    ],
    7: [
        ("no_automatic_naturalization", [("不自动", "不调用", "不会"), ("自然化", "去ai")]),
        ("raw_candidate_identity", [("not_requested",), ("字节",), ("一致", "相同")]),
        ("summary_and_repositories", [("章节总结", "总结"), ("主角",), ("系统",), ("仓库", "状态")]),
        ("per_chapter_commit", [("状态回证",), ("逐章", "每章"), ("review_pending",), ("下一章", "继续")]),
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
