import json
import re
from pathlib import Path


DIRECTORY_ALIASES = {
    "body": ["正文"],
    "outline": ["plan", "大纲"],
    "summary": ["章节总结", "总结"],
    "stage_summary": ["阶段总结"],
    "review": ["审查报告"],
    "repair": ["修复记录"],
}


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def write_text(path, text):
    Path(path).write_text(text, encoding="utf-8")


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def json_dump(data):
    print(json_text(data))


def success(command, **kwargs):
    data = {"ok": True, "command": command}
    data.update(kwargs)
    return data


def failure(command, code, message):
    return {
        "ok": False,
        "command": command,
        "error": {"code": code, "message": message},
    }


def parse_chapter_number(text):
    value = str(text)
    patterns = [
        r"第\s*0*(\d+)\s*章",
        r"chapter\s*:\s*0*(\d+)",
        r"^\s*0*(\d+)\s*$",
    ]
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def parse_chapter_range(text):
    value = str(text).strip()
    range_match = re.search(r"(?:第)?\s*0*(\d+)\s*(?:-|到|至|—|－)\s*(?:第)?\s*0*(\d+)\s*(?:章)?", value)
    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2))
    else:
        chapter = parse_chapter_number(value)
        if chapter is None:
            raise ValueError("无法解析章节范围")
        start = chapter
        end = chapter
    if start > end:
        start, end = end, start
    return {"start": start, "end": end, "count": end - start + 1}


def archive_span(chapter):
    number = int(chapter)
    start = ((number - 1) // 50) * 50 + 1
    return start, start + 49


def find_first_existing_dir(project, aliases):
    root = Path(project)
    for name in aliases:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    return root / aliases[0]


def directory_for(project, kind):
    aliases = DIRECTORY_ALIASES.get(kind, [kind])
    return find_first_existing_dir(project, aliases)


def parse_chapter_file(path):
    file_path = Path(path)
    chapter = parse_chapter_number(file_path.name)
    if chapter is None:
        return None
    name = file_path.stem
    if "草稿" in name:
        status = "草稿"
    elif "已审查" in name:
        status = "已审查"
    else:
        status = "正式稿"
    return {"chapter": chapter, "status": status, "path": str(file_path)}


def list_chapter_files(project):
    body_dir = directory_for(project, "body")
    if not body_dir.is_dir():
        return []
    entries = []
    for path in sorted(body_dir.glob("*.md")):
        parsed = parse_chapter_file(path)
        if parsed:
            entries.append(parsed)
    return entries


def archive_file(project, kind, chapter):
    start, end = archive_span(chapter)
    directory = directory_for(project, kind)
    if kind == "summary":
        name = f"章节总结_第{start}-{end}章.md"
    elif kind == "outline":
        name = f"大纲_第{start}-{end}章.md"
    elif kind == "review":
        name = f"审查_第{start}-{end}章.md"
    elif kind == "repair":
        name = f"修复_第{start}-{end}章.md"
    else:
        name = f"{kind}_第{start}-{end}章.md"
    return directory / name


def markdown_response(data):
    lines = [f"# {data.get('command', 'result')}", ""]
    lines.append("```json")
    lines.append(json_text(data))
    lines.append("```")
    return "\n".join(lines)


def emit(data, output_format):
    if output_format == "markdown":
        print(markdown_response(data))
    else:
        json_dump(data)

