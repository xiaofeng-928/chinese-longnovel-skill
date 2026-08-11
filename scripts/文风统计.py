#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文风统计：对范文正文做确定性文体统计，只输出可计算事实，不输出文学判断。"""

from __future__ import annotations

import argparse
import math
import re
import unicodedata
from pathlib import Path

from 公共工具 import emit, failure, read_text, success


CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
TERMINATORS = "。！？…；;.!?～"
FULLWIDTH_QUOTE_PAIRS = [
    ("“", "”"),
    ("「", "」"),
    ("『", "』"),
    ("（", "）"),
]

CHINESE_NUM = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "零": 0,
}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000}


def chinese_num_to_int(chars: str) -> int | None:
    if not chars:
        return None
    if chars.isdigit():
        return int(chars)
    total = 0
    section = 0
    for ch in chars:
        if ch in CHINESE_NUM:
            section = section * 10 + CHINESE_NUM[ch]
        elif ch in CHINESE_UNITS:
            unit = CHINESE_UNITS[ch]
            if section == 0:
                section = 1
            total += section * unit
            section = 0
        else:
            return None
    return total + section


CHAPTER_HEADING = re.compile(r"^\s*第\s*([0-9]+|[一二三四五六七八九十百千万两零]+)\s*[章节回]\s*(.*)$")


def parse_chapter_heading(line: str) -> int | None:
    match = CHAPTER_HEADING.match(line)
    if not match:
        return None
    number = chinese_num_to_int(match.group(1))
    if number is None or len(line) > 60:
        return None
    return number


def is_blank(line: str) -> bool:
    return not line.strip()


def content_chars(text: str) -> int:
    return len(re.sub(r"\s", "", text))


def split_sentences(text: str) -> list[str]:
    sentences = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in TERMINATORS:
            sentences.append("".join(buf).strip())
            buf = []
    if buf:
        sentences.append("".join(buf).strip())
    return [s for s in sentences if s]


def split_paragraphs(text: str, skip_heading_numbers: set[int]) -> list[str]:
    paragraphs = []
    for line in text.splitlines():
        if is_blank(line):
            continue
        if parse_chapter_heading(line) is not None:
            continue
        paragraphs.append(line.strip())
    return paragraphs


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * p / 100.0
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    return sorted_values[lower] * (upper - rank) + sorted_values[upper] * (rank - lower)


def length_stats(values: list[int]) -> dict:
    if not values:
        return {
            "count": 0, "mean": 0.0, "p25": 0.0,
            "median": 0.0, "p75": 0.0, "p90": 0.0,
        }
    sorted_values = sorted(float(v) for v in values)
    return {
        "count": len(values),
        "mean": round(sum(sorted_values) / len(sorted_values), 2),
        "p25": round(percentile(sorted_values, 25), 2),
        "median": round(percentile(sorted_values, 50), 2),
        "p75": round(percentile(sorted_values, 75), 2),
        "p90": round(percentile(sorted_values, 90), 2),
    }


def quote_chars(text: str) -> int:
    """统计中文引号对白内的字符数（不含空白）。"""
    total = 0
    opens = {o for o, _ in FULLWIDTH_QUOTE_PAIRS}
    closes = {c for _, c in FULLWIDTH_QUOTE_PAIRS}
    inside = False
    for ch in text:
        if ch in opens:
            inside = True
            continue
        if ch in closes:
            inside = False
            continue
        if inside and not ch.isspace():
            total += 1
    return total


def is_pure_dialogue_paragraph(paragraph: str) -> bool:
    chars = content_chars(paragraph)
    if chars == 0:
        return False
    return quote_chars(paragraph) / chars >= 0.9


def punctuation_freq(text: str) -> dict:
    terms = [
        "，", "。", "？", "！", "；", "、", "：", "…", "……", "——",
        "“", "”", "『", "』", "「", "」",
    ]
    return {term: text.count(term) for term in terms}


CONNECTORS = ["然后", "接着", "随后", "紧接着", "与此同时", "不过", "但是", "可是", "因此", "于是", "所以"]
REACTION_WORDS = ["不由得", "情不自禁", "下意识", "本能地", "震惊", "不可思议", "倒吸一口凉气", "瞳孔骤缩", "面色大变"]
DEGREE_ADVERBS = ["微微", "淡淡", "缓缓", "默默", "轻轻", "深深", "猛地", "极其", "精准", "瞬间", "彻底", "终于", "几乎", "特别"]
TRANSITION_WORDS = ["就在这时", "下一刻", "下一秒", "不一会儿", "很快", "随即", "转而", "与此同时"]


def word_class_freq(text: str) -> dict:
    return {
        "连接词": {t: text.count(t) for t in CONNECTORS if text.count(t) > 0},
        "反应词": {t: text.count(t) for t in REACTION_WORDS if text.count(t) > 0},
        "程度副词": {t: text.count(t) for t in DEGREE_ADVERBS if text.count(t) > 0},
        "转场词": {t: text.count(t) for t in TRANSITION_WORDS if text.count(t) > 0},
    }


def head_of_sentence(sentence: str) -> str:
    head = "".join(ch for ch in sentence if CJK.match(ch))
    return head[:2]


def same_structure_runs(sentences: list[str], min_run: int = 3) -> list[dict]:
    runs = []
    current = []
    for sentence in sentences:
        head = head_of_sentence(sentence)
        if not head:
            continue
        if current and current[-1][0] == head:
            current.append((head, sentence))
        else:
            if len(current) >= min_run:
                runs.append(_run_payload(current))
            current = [(head, sentence)]
    if len(current) >= min_run:
        runs.append(_run_payload(current))
    return runs[:20]


def _run_payload(current) -> dict:
    return {
        "共头词": current[0][0],
        "句数": len(current),
        "示例": [item[1][:40] for item in current[:3]],
    }


def repeated_phrase_candidates(text: str, ngram_size: int = 4, min_count: int = 3) -> list[dict]:
    cjk = "".join(CJK.findall(text))
    counts = {}
    for i in range(len(cjk) - ngram_size + 1):
        gram = cjk[i:i + ngram_size]
        counts[gram] = counts.get(gram, 0) + 1
    candidates = [
        {"短语": gram, "次数": count}
        for gram, count in counts.items()
        if count >= min_count
    ]
    candidates.sort(key=lambda item: (-item["次数"], item["短语"]))
    return candidates[:20]


def parse_chapter_selection(expression: str | None) -> set[int] | None:
    """返回选中章节集合；None 表示全部。"""
    if not expression:
        return None
    selected = set()
    for part in expression.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, _, end_s = part.partition("-")
            try:
                start, end = int(start_s), int(end_s)
            except ValueError:
                raise ValueError(f"无法解析章节选择表达式：{expression!r}")
            if start > end:
                raise ValueError(f"章节区间起点大于终点：{part!r}")
            selected.update(range(start, end + 1))
        else:
            try:
                selected.add(int(part))
            except ValueError:
                raise ValueError(f"无法解析章节选择表达式：{expression!r}")
    return selected


def load_chapters(text: str) -> list[dict]:
    """从正文文本中按章节标题切分章节。"""
    chapters = []
    current = None
    for line in text.splitlines():
        number = parse_chapter_heading(line)
        if number is not None:
            if current is not None:
                chapters.append(current)
            title = line.strip()
            current = {"number": number, "title": title, "lines": []}
        else:
            if current is not None:
                current["lines"].append(line)
    if current is not None:
        chapters.append(current)
    chapters.sort(key=lambda item: item["number"])
    return chapters


def select_chapters(chapters: list[dict], selection: set[int] | None) -> list[dict]:
    if selection is None:
        return chapters
    available = {item["number"] for item in chapters}
    missing = selection - available
    if missing:
        ordered = ",".join(str(n) for n in sorted(missing))
        raise ValueError(f"章节不存在：{ordered}")
    return [item for item in chapters if item["number"] in selection]


def parse_index_numbers(index_path: str) -> set[int]:
    """从章节索引.md 提取章节序号集合（保留供索引校验使用）。"""
    text = read_text(index_path)
    numbers = set()
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 3:
            continue
        for cell in cells[:3]:
            match = re.fullmatch(r"\s*(\d+)\s*", cell)
            if match:
                numbers.add(int(match.group(1)))
                break
    return numbers


def chapter_stats(chapter: dict, text_body: str) -> dict:
    paragraphs = split_paragraphs(text_body, {chapter["number"]})
    sentences = split_sentences(text_body)
    sentence_lens = [content_chars(s) for s in sentences]
    paragraph_lens = [content_chars(p) for p in paragraphs]
    chars = content_chars(text_body)
    quote_chars_total = quote_chars(text_body)
    pure_dialogue = sum(1 for p in paragraphs if is_pure_dialogue_paragraph(p))
    return {
        "number": chapter["number"],
        "title": chapter["title"],
        "chars": chars,
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
        "sentence_lengths": length_stats(sentence_lens),
        "paragraph_lengths": length_stats(paragraph_lens),
        "dialogue_chars": quote_chars_total,
        "dialogue_ratio": round(quote_chars_total / chars, 4) if chars else 0.0,
        "pure_dialogue_paragraphs": pure_dialogue,
        "pure_dialogue_ratio": round(pure_dialogue / len(paragraphs), 4) if paragraphs else 0.0,
        "punctuation": punctuation_freq(text_body),
    }


def profile(args):
    text_path = Path(args.text)
    index_path = Path(args.index)
    if not text_path.is_file():
        raise FileNotFoundError(text_path)
    text = read_text(text_path).lstrip("\ufeff")
    body = "\n".join(line for line in text.splitlines() if not is_blank(line))
    if not content_chars(body):
        raise ValueError("正文为空，无法进行文风统计")
    if not index_path.is_file():
        raise FileNotFoundError(index_path)

    chapters = load_chapters(text)
    if not chapters:
        raise ValueError("未能从正文中定位章节标题，无法按章节统计")
    selection = parse_chapter_selection(args.chapters)
    selected = select_chapters(chapters, selection)
    if selection is not None:
        index_numbers = parse_index_numbers(index_path)
        if not index_numbers:
            raise ValueError("章节索引中未找到可识别的章节序号")
        missing_in_index = selection - index_numbers
        if missing_in_index:
            ordered = ",".join(str(n) for n in sorted(missing_in_index))
            raise ValueError(f"章节在索引中不存在：{ordered}")

    per_chapter = []
    for chapter in selected:
        body_text = "\n".join(chapter["lines"])
        per_chapter.append(chapter_stats(chapter, body_text))

    all_text = "\n".join("\n".join(item["lines"]) for item in selected)
    # 统一段落切分：把选中章节行拼接后按行切段
    all_paragraphs = []
    for item in selected:
        all_paragraphs.extend(split_paragraphs("\n".join(item["lines"]), set()))
    sentences = split_sentences(all_text)
    sentence_lens = [content_chars(s) for s in sentences]
    paragraph_lens = [content_chars(p) for p in all_paragraphs]
    chars = content_chars(all_text)
    quote_chars_total = quote_chars(all_text)
    pure_dialogue = sum(1 for p in all_paragraphs if is_pure_dialogue_paragraph(p))

    payload = success(
        "profile",
        input={
            "text": str(text_path),
            "index": str(index_path),
            "chapters": args.chapters or "all",
            "output": str(args.output) if args.output else None,
        },
        total={
            "chars": chars,
            "chapters": len(selected),
            "sentences": len(sentences),
            "paragraphs": len(all_paragraphs),
            "dialogue_ratio": round(quote_chars_total / chars, 4) if chars else 0.0,
            "pure_dialogue_ratio": round(pure_dialogue / len(all_paragraphs), 4) if all_paragraphs else 0.0,
        },
        sentence_lengths=length_stats(sentence_lens),
        paragraph_lengths=length_stats(paragraph_lens),
        punctuation=punctuation_freq(all_text),
        word_classes=word_class_freq(all_text),
        candidates={
            "same_structure_runs": same_structure_runs(sentences),
            "repeated_phrases": repeated_phrase_candidates(all_text),
        },
        chapters=per_chapter,
        note="只输出可计算统计事实，不包含文学判断；样本中的缺失不能解读为绝对规律。",
    )

    if args.output:
        _write_markdown_report(payload, args.output)
    return payload


def _write_markdown_report(payload: dict, output_path: str) -> None:
    lines = ["# 文风统计报告", ""]
    total = payload["total"]
    lines.append("## 总体")
    lines.append(f"- 字符数：{total['chars']}")
    lines.append(f"- 章节数：{total['chapters']}")
    lines.append(f"- 句子数：{total['sentences']}")
    lines.append(f"- 段落数：{total['paragraphs']}")
    lines.append(f"- 对话字符占比：{total['dialogue_ratio']}")
    lines.append(f"- 纯对白段占比：{total['pure_dialogue_ratio']}")
    lines.append("")
    lines.append("## 句长与段长")
    lines.append("| 指标 | 均值 | P25 | 中位数 | P75 | P90 |")
    lines.append("|---|---|---|---|---|---|")
    sl = payload["sentence_lengths"]
    pl = payload["paragraph_lengths"]
    lines.append(
        f"| 句长 | {sl['mean']} | {sl['p25']} | {sl['median']} | {sl['p75']} | {sl['p90']} |"
    )
    lines.append(
        f"| 段长 | {pl['mean']} | {pl['p25']} | {pl['median']} | {pl['p75']} | {pl['p90']} |"
    )
    lines.append("")
    lines.append("## 标点频率")
    lines.append("```json")
    lines.append("".join(str(payload["punctuation"])))
    lines.append("```")
    lines.append("")
    lines.append("## 词类频率")
    lines.append("```json")
    lines.append("".join(str(payload["word_classes"])))
    lines.append("```")
    lines.append("")
    lines.append("## 候选提示（需人工复核，不是结论）")
    lines.append("```json")
    lines.append("".join(str(payload["candidates"])))
    lines.append("```")
    lines.append("")
    lines.append("## 按章节")
    for chapter in payload["chapters"]:
        lines.append(f"### {chapter['title']}")
        lines.append(f"- 字符数：{chapter['chars']}；句子数：{chapter['sentences']}；段落数：{chapter['paragraphs']}")
        lines.append(f"- 对话占比：{chapter['dialogue_ratio']}；纯对白段：{chapter['pure_dialogue_ratio']}")
        lines.append(f"- 句长均值：{chapter['sentence_lengths']['mean']}；段长均值：{chapter['paragraph_lengths']['mean']}")
    lines.append("")
    lines.append("> 本报告只描述可计算事实，不得直接推断文学效果。")
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 文风统计工具（只输出可计算事实）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("--text", required=True, help="范文正文.txt 路径")
    profile_parser.add_argument("--index", required=True, help="章节索引.md 路径")
    profile_parser.add_argument("--chapters", default=None, help="章节选择表达式，如 1-10,12,15-18；默认全部")
    profile_parser.add_argument("--output", default=None, help="可读 Markdown 统计报告输出路径")
    profile_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    profile_parser.set_defaults(handler=profile)

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
