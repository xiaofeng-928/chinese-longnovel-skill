#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""原文重合检查：检测草稿与来源范文之间的连续文本重合，支持多来源和白名单。

只做确定性的连续字符重合，不把语义近似伪装成确定性抄袭判断。
"""

from __future__ import annotations

import argparse
import unicodedata
from collections import defaultdict
from pathlib import Path

from 公共工具 import emit, failure, read_text, success

# 阈值集中定义，避免散落在提示词中。
MIN_REPORT = 12        # 低于此长度一律不报告（极短公共表达过滤）
SHORT_MAX = 15         # 12-15 字：只在同一表达命中多次时才报告
REVIEW_MIN = 16        # 16-23 字：需复核
BLOCK_MIN = 24         # 24 字及以上：阻断
SHORT_REQUIRED_HITS = 2  # 12-15 字重合需要同一表达在来源中重复出现的次数下限
KGRAM = 12             # 最小 k-gram 检索长度

PUNCTUATION = set(
    "，。、；：？！…—·“”‘’（）《》〈〉【】「」『』～￥"
    ".,;:!?()[]{}<>-‐‑–—'\"“”‘’…·"
)

FULLWIDTH_BASE = 0xFEE0  # ord(Ａ) - ord(A)


def halfwidth(ch: str) -> str:
    code = ord(ch)
    if 0xFF01 <= code <= 0xFF5E:
        return chr(code - FULLWIDTH_BASE)
    if code == 0x3000:  # 全角空格
        return " "
    return ch


def normalize(text: str, strip_punct: bool = False):
    """归一化：全半角统一、去空白；可选去标点。返回 (归一化文本, 映射到原字符下标)。"""
    normalized = []
    mapping = []
    for idx, raw_ch in enumerate(text):
        ch = halfwidth(raw_ch)
        if ch.isspace():
            continue
        if strip_punct and ch in PUNCTUATION:
            continue
        normalized.append(ch)
        mapping.append(idx)
    return "".join(normalized), mapping


def load_whitelist(path):
    if not path:
        return []
    words = []
    for line in read_text(path).splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            words.append(word)
    return words


def find_matches(draft, source, kgram=KGRAM, min_len=MIN_REPORT, max_positions=2000):
    """在 source 中查找与 draft 的连续重合，返回 (d_start,d_end,s_start,s_end,length,text)。"""
    positions = defaultdict(list)
    for i in range(len(source) - kgram + 1):
        gram = source[i:i + kgram]
        if len(positions[gram]) < max_positions:
            positions[gram].append(i)

    matches = []
    i = 0
    n = len(draft)
    while i <= n - kgram:
        gram = draft[i:i + kgram]
        cand = positions.get(gram)
        if not cand:
            i += 1
            continue
        best = None
        for p in cand:
            # 向后扩展
            bd, bs = i, p
            while bd > 0 and bs > 0 and draft[bd - 1] == source[bs - 1]:
                bd -= 1
                bs -= 1
            # 向前扩展
            ed, es = i + kgram, p + kgram
            while ed < n and es < len(source) and draft[ed] == source[es]:
                ed += 1
                es += 1
            length = ed - bd
            if best is None or length > best[0]:
                best = (length, bd, ed, bs, es)
        length, bd, ed, bs, es = best
        if length >= min_len:
            matches.append((bd, ed, bs, es, length, draft[bd:ed]))
            i = max(i + 1, ed)  # 跳过已覆盖区域，避免同一位置重复报告
        else:
            i += 1
    return matches


def dedupe_matches(matches):
    """按草稿位置做非重叠贪心去重。"""
    matches.sort(key=lambda m: (m[0], -m[4]))
    result = []
    last_end = -1
    for match in matches:
        d_start, d_end = match[0], match[1]
        if d_start >= last_end:
            result.append(match)
            last_end = d_end
    return result


def whitelist_exempt(expression, whitelist):
    for term in whitelist:
        if term in expression or expression in term:
            return True, term
    return False, None


def classify(length, hits_in_source):
    if length >= BLOCK_MIN:
        return "阻断"
    if length >= REVIEW_MIN:
        return "需复核"
    if length <= SHORT_MAX:
        if hits_in_source >= SHORT_REQUIRED_HITS:
            return "需复核"
        return "跳过"
    return "需复核"


def run_scope(scope_name, draft_text, source_text, sources_maps, whitelist):
    draft_norm, draft_map = normalize(draft_text, strip_punct=(scope_name == "without_punct"))
    findings = []
    exempted = []
    for source_index, source_text_item in enumerate(source_text):
        source_norm, source_map = normalize(source_text_item, strip_punct=(scope_name == "without_punct"))
        matches = dedupe_matches(find_matches(draft_norm, source_norm))
        for d_start, d_end, s_start, s_end, length, expression in matches:
            hits_in_source = source_norm.count(expression)
            exempted_flag, term = whitelist_exempt(expression, whitelist)
            severity = classify(length, hits_in_source)
            if exempted_flag:
                exempted.append({
                    "scope": scope_name,
                    "source_index": source_index,
                    "expression": expression,
                    "whitelist_term": term,
                    "length": length,
                })
                continue
            if severity == "跳过":
                continue
            # 原文本位置（通过映射回退到原文件下标）
            draft_orig_start = draft_map[d_start]
            draft_orig_end = draft_map[d_end - 1] + 1
            source_orig_start = source_map[s_start]
            source_orig_end = source_map[s_end - 1] + 1
            findings.append({
                "scope": scope_name,
                "source_index": source_index,
                "severity": severity,
                "length": length,
                "expression": expression,
                "hits_in_source": hits_in_source,
                "draft_position": {
                    "normalized_start": d_start,
                    "normalized_end": d_end,
                    "original_start": draft_orig_start,
                    "original_end": draft_orig_end,
                },
                "source_position": {
                    "normalized_start": s_start,
                    "normalized_end": s_end,
                    "original_start": source_orig_start,
                    "original_end": source_orig_end,
                },
            })
    return findings, exempted


def check(args):
    draft_path = Path(args.draft)
    if not draft_path.is_file():
        raise FileNotFoundError(draft_path)
    draft_text = read_text(draft_path).lstrip("\ufeff")

    sources = []
    for source_arg in args.source:
        source_path = Path(source_arg)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        sources.append((str(source_path), read_text(source_path).lstrip("\ufeff")))

    whitelist = load_whitelist(args.whitelist)
    all_findings = []
    all_exempted = []
    for scope_name in ("with_punct", "without_punct"):
        findings, exempted = run_scope(
            scope_name, draft_text, [item[1] for item in sources], None, whitelist
        )
        all_findings.extend(findings)
        all_exempted.extend(exempted)

    summary = {
        "blocked": sum(1 for item in all_findings if item["severity"] == "阻断"),
        "review": sum(1 for item in all_findings if item["severity"] == "需复核"),
        "exempted": len(all_exempted),
        "sources": len(sources),
    }

    payload = success(
        "check",
        input={
            "draft": str(draft_path),
            "sources": [item[0] for item in sources],
            "whitelist": str(args.whitelist) if args.whitelist else None,
            "output": str(args.output) if args.output else None,
        },
        thresholds={
            "min_report": MIN_REPORT,
            "short_max": SHORT_MAX,
            "review_min": REVIEW_MIN,
            "block_min": BLOCK_MIN,
            "short_required_hits": SHORT_REQUIRED_HITS,
        },
        scopes=["with_punct", "without_punct"],
        findings=all_findings,
        exempted=all_exempted,
        summary=summary,
        note="只检测规范化后的连续字符重合，不判定语义近似抄袭。",
    )

    if args.output:
        _write_markdown_report(payload, sources, args.output)
    return payload


def _write_markdown_report(payload, sources, output_path):
    lines = ["# 原文重合检查报告", ""]
    lines.append(f"- 草稿：{payload['input']['draft']}")
    for idx, source in enumerate(sources):
        lines.append(f"- 来源{idx + 1}：{source[0]}")
    lines.append(f"- 白名单：{payload['input']['whitelist'] or '无'}")
    lines.append("")
    lines.append("## 阈值")
    lines.append(f"- 12-15 字：同一表达命中 {SHORT_REQUIRED_HITS} 次以上才报告（需复核）")
    lines.append(f"- 16-23 字：需复核")
    lines.append(f"- 24 字及以上：阻断")
    lines.append("")
    lines.append("## 结论")
    lines.append(f"- 阻断：{payload['summary']['blocked']} 处")
    lines.append(f"- 需复核：{payload['summary']['review']} 处")
    lines.append(f"- 白名单豁免：{payload['summary']['exempted']} 处")
    lines.append("")
    if payload["findings"]:
        lines.append("## 明细")
        for item in payload["findings"]:
            lines.append(f"- [{item['severity']}][{item['scope']}] 来源{item['source_index'] + 1} 长度{item['length']}：{item['expression']}")
            lines.append(f"  - 草稿位置：normalized {item['draft_position']['normalized_start']}-{item['draft_position']['normalized_end']}；原文件 {item['draft_position']['original_start']}-{item['draft_position']['original_end']}")
            lines.append(f"  - 来源位置：normalized {item['source_position']['normalized_start']}-{item['source_position']['normalized_end']}；原文件 {item['source_position']['original_start']}-{item['source_position']['original_end']}")
    else:
        lines.append("未发现达到报告阈值的连续重合。")
    lines.append("")
    lines.append("> 本报告只检测规范化后的连续字符重合，不判定语义近似抄袭。")
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 原文重合检查工具（连续字符重合检测）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--draft", required=True, help="草稿文件路径")
    check_parser.add_argument("--source", action="append", required=True, help="范文正文.txt 路径，可重复")
    check_parser.add_argument("--whitelist", default=None, help="白名单文件，一行一个豁免项，# 开头和空行忽略")
    check_parser.add_argument("--output", default=None, help="可读 Markdown 检查报告输出路径")
    check_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    check_parser.set_defaults(handler=check)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        data = args.handler(args)
    except Exception as exc:
        data = failure(args.command, "COMMAND_FAILED", str(exc))
    emit(data, args.format)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
