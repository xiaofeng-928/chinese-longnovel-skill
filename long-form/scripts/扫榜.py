import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("books", data.get("records", []))
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array or an object containing books/records")
    return [item for item in data if isinstance(item, dict)]


def age_label(records):
    dates = []
    for item in records:
        value = item.get("captured_at") or item.get("date")
        if not value:
            continue
        try:
            dates.append(datetime.fromisoformat(str(value)[:10]).date())
        except ValueError:
            continue
    if not dates:
        return "不足"
    age = (date.today() - max(dates)).days
    return "新鲜" if age <= 30 else "偏旧"


def genres_for(item):
    genres = item.get("genres") or item.get("tags") or []
    return [genres] if isinstance(genres, str) else genres


def analyze(records):
    genre_counts = Counter()
    for item in records:
        for genre in genres_for(item):
            if genre:
                genre_counts[str(genre)] += 1
    candidates = []
    for genre, count in genre_counts.most_common():
        samples = [item for item in records if genre in genres_for(item)]
        candidates.append({
            "genre": genre,
            "sample_count": count,
            "platforms": sorted({str(item.get("platform", "未注明")) for item in samples}),
            "heat_evidence": "；".join(str(item.get("heat")) for item in samples[:3] if item.get("heat")),
            "competition_risk": "高" if count >= 8 else "中" if count >= 4 else "低",
            "source_urls": [item.get("source_url") for item in samples if item.get("source_url")][:5],
        })
    return candidates


def markdown(records, candidates):
    platforms = sorted({str(item.get("platform", "未注明")) for item in records})
    lines = [
        "# 选题决策", "",
        "## 扫榜元数据",
        f"- 扫榜日期：{date.today().isoformat()}",
        f"- 平台：{'、'.join(platforms) or '未注明'}",
        f"- 样本数量：{len(records)}",
        f"- 数据新鲜度：{age_label(records)}",
        "- 数据来源：见下方来源表", "",
        "## 题材候选",
        "| 优先级 | 题材 | 样本数 | 热度证据 | 竞争风险 | 来源 |",
        "|---:|---|---:|---|---|---|",
    ]
    for index, item in enumerate(candidates[:3], 1):
        source = "、".join(url for url in item["source_urls"] if url) or "未提供"
        lines.append(f"| {index} | {item['genre']} | {item['sample_count']} | {item['heat_evidence'] or '未提供'} | {item['competition_risk']} | {source} |")
    lines.extend([
        "", "## 推荐结论",
        "- 首选题材：由用户结合候选证据确认，不由脚本自动替用户拍板。",
        "- 推荐理由：综合样本数量、热度证据、竞争风险和用户优势。",
        "- 不建议直接模仿的部分：具体书名、角色、情节、独特设定和文案。",
        "- 开篇可验证的承诺：待用户确认后填写。",
        "- 前 10 章验证指标：待用户确认后填写。", "",
        "## 来源与证据",
        "| 来源 | 平台 | 日期 | 支持的结论 | 可信度 |",
        "|---|---|---|---|---|",
    ])
    for item in records:
        source = item.get("source_url", "未提供")
        captured = item.get("captured_at", item.get("date", "未注明"))
        confidence = "高" if item.get("source_url") and captured != "未注明" else "低"
        lines.append(f"| {source} | {item.get('platform', '未注明')} | {captured} | {item.get('evidence', '未填写')} | {confidence} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="MyNovel 扫榜数据标准化工具")
    parser.add_argument("--input", required=True, help="JSON 榜单记录")
    parser.add_argument("--output", help="输出选题决策.md")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()
    records = load_records(args.input)
    candidates = analyze(records)
    rendered = markdown(records, candidates)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    payload = {"ok": True, "records": len(records), "freshness": age_label(records), "candidates": candidates[:3]}
    print(rendered if args.format == "markdown" else json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
