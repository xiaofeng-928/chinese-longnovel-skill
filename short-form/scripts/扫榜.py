import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROFILE_START = "<!-- AUTO-RANK-SCAN:START -->"
PROFILE_END = "<!-- AUTO-RANK-SCAN:END -->"
PATTERN_FIELDS = {
    "tags": "高频标签",
    "hook": "开篇钩子",
    "relationship": "人物关系",
    "conflict": "核心冲突",
    "ending": "结局模式",
}


def load_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("records", data.get("books", []))
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array or an object containing records/books")
    return [record for record in data if isinstance(record, dict)]


def values_for(record, field):
    value = record.get(field, []) if field == "tags" else record.get(field)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if value and str(value).strip() else []


def latest_capture_date(records):
    dates = []
    for record in records:
        value = record.get("captured_at") or record.get("date")
        if not value:
            continue
        try:
            dates.append(datetime.fromisoformat(str(value)[:10]).date())
        except ValueError:
            continue
    return max(dates) if dates else date.today()


def analyze(records):
    return {
        field: Counter(
            value
            for record in records
            for value in values_for(record, field)
        ).most_common(8)
        for field in PATTERN_FIELDS
    }


def report_markdown(type_name, records, patterns, captured_on):
    sample_status = "足够" if len(records) >= 5 else "样本不足"
    lines = [
        f"# {type_name} 短篇扫榜记录",
        "",
        "## 扫榜元数据",
        f"- 数据日期：{captured_on.isoformat()}",
        f"- 样本数量：{len(records)}",
        f"- 样本状态：{sample_status}",
        "- 使用范围：仅提炼类型模式，不复用具体书名、人物、情节或表达。",
        "",
        "## 样本与证据",
        "| 作品 | 平台 | 热度/排名 | 来源 | 日期 |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| {title} | {platform} | {heat} | {url} | {captured} |".format(
                title=record.get("title", "未提供"),
                platform=record.get("platform", "未提供"),
                heat=record.get("heat", record.get("rank", "未提供")),
                url=record.get("source_url", "未提供"),
                captured=record.get("captured_at", record.get("date", "未提供")),
            )
        )
    lines.extend(["", "## 模式观察"])
    for field, title in PATTERN_FIELDS.items():
        lines.extend(["", f"### {title}"])
        values = patterns[field]
        if values:
            lines.extend(f"- {value}：{count} 个样本" for value, count in values)
        else:
            lines.append("- 未提供足够结构化字段，不能下结论。")
    return "\n".join(lines) + "\n"


def profile_block(type_name, patterns, captured_on):
    lines = [
        PROFILE_START,
        f"## 自动扫榜提炼（{captured_on.isoformat()}）",
        "",
        f"以下内容来自 {type_name} 的结构化扫榜样本，供创作时参考，需与人工范文和判断共同使用。",
    ]
    for field, title in PATTERN_FIELDS.items():
        lines.extend(["", f"### {title}"])
        values = patterns[field]
        if values:
            lines.extend(f"- {value}（{count} 个样本）" for value, count in values)
        else:
            lines.append("- 暂无足够样本。")
    lines.extend(["", PROFILE_END, ""])
    return "\n".join(lines)


def update_profile(path, block):
    existing = path.read_text(encoding="utf-8") if path.exists() else "# 类型创作特征\n\n"
    start = existing.find(PROFILE_START)
    end = existing.find(PROFILE_END)
    if start != -1 and end != -1 and end > start:
        existing = existing[:start] + existing[end + len(PROFILE_END):].lstrip("\r\n")
    path.write_text(existing.rstrip() + "\n\n" + block, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="MyNovel 短篇类型扫榜工具")
    parser.add_argument("--input", required=True, help="JSON 榜单或样本记录")
    parser.add_argument("--type-dir", required=True, help="短篇类型目录，例如 D:\\ai小说\\短篇\\世俗言情文")
    parser.add_argument("--update-features", action="store_true", help="更新类型创作特征中的自动扫榜区块")
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args()

    records = load_records(args.input)
    type_dir = Path(args.type_dir)
    library_dir = type_dir / "范文参照"
    scan_dir = library_dir / "扫榜记录"
    scan_dir.mkdir(parents=True, exist_ok=True)

    captured_on = latest_capture_date(records)
    patterns = analyze(records)
    report_path = scan_dir / f"{captured_on.isoformat()}_扫榜.md"
    report = report_markdown(type_dir.name, records, patterns, captured_on)
    report_path.write_text(report, encoding="utf-8")

    profile_path = library_dir / "类型创作特征.md"
    if args.update_features:
        update_profile(profile_path, profile_block(type_dir.name, patterns, captured_on))

    payload = {
        "ok": True,
        "records": len(records),
        "sample_status": "足够" if len(records) >= 5 else "样本不足",
        "report": str(report_path),
        "features_updated": args.update_features,
    }
    print(report if args.format == "markdown" else json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
