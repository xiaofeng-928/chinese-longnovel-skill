import argparse
from pathlib import Path

from 公共工具 import (
    archive_file,
    archive_span,
    emit,
    failure,
    list_chapter_files,
    parse_chapter_range,
    read_text,
    success,
)


def read_book_title(config_path):
    text = read_text(config_path)
    for line in text.splitlines():
        cleaned = line.strip().lstrip("-").strip()
        if cleaned.startswith("书名"):
            parts = cleaned.split("：", 1)
            if len(parts) == 2:
                return parts[1].strip()
            parts = cleaned.split(":", 1)
            if len(parts) == 2:
                return parts[1].strip()
    return Path(config_path).parent.name


def match_project(project_dir, title, query):
    if not query:
        return 0, "未提供查询词"
    haystacks = [
        ("book_title", title),
        ("directory", project_dir.name),
        ("path", str(project_dir)),
    ]
    best_score = 0
    best_reason = "未匹配"
    for field, value in haystacks:
        if query == value:
            score = 100
            reason = f"{field} 精确匹配"
        elif query in value:
            score = 80
            reason = f"{field} 包含查询词"
        else:
            common = len(set(query) & set(value))
            score = int(common / max(len(set(query)), 1) * 50)
            reason = f"{field} 字符相似"
        if score > best_score:
            best_score = score
            best_reason = reason
    return best_score, best_reason


def scan_projects(args):
    root = Path(args.root)
    projects = []
    for config in sorted(root.rglob("novel-config.md")):
        project_dir = config.parent
        title = read_book_title(config)
        score, reason = match_project(project_dir, title, args.query)
        if args.query and score <= 0:
            continue
        projects.append(
            {
                "name": project_dir.name,
                "book_title": title,
                "path": str(project_dir),
                "config": str(config),
                "match_score": score,
                "reason": reason,
            }
        )
    projects.sort(key=lambda item: item["match_score"], reverse=True)
    return success("scan-projects", root=str(root), query=args.query, projects=projects)


def chapter_status(args):
    project = Path(args.project)
    parsed_range = parse_chapter_range(args.range)
    files = list_chapter_files(project)
    by_chapter = {}
    for item in files:
        by_chapter.setdefault(item["chapter"], []).append(item)
    start = parsed_range["start"]
    end = parsed_range["end"]
    existing = []
    missing = []
    duplicates = []
    statuses = []
    for chapter in range(start, end + 1):
        chapter_files = by_chapter.get(chapter, [])
        if chapter_files:
            existing.append(chapter)
            statuses.append(
                {
                    "chapter": chapter,
                    "files": chapter_files,
                    "statuses": sorted({item["status"] for item in chapter_files}),
                }
            )
            if len(chapter_files) > 1:
                duplicates.append({"chapter": chapter, "files": [item["path"] for item in chapter_files]})
        else:
            missing.append(chapter)
    highest = max(by_chapter.keys()) if by_chapter else None
    return success(
        "chapter-status",
        project=str(project),
        range=parsed_range,
        existing_chapters=existing,
        missing_chapters=missing,
        duplicate_chapters=duplicates,
        chapter_statuses=statuses,
        highest_chapter=highest,
    )


def archive_path(args):
    project = Path(args.project)
    chapter = int(args.chapter)
    start, end = archive_span(chapter)
    path = archive_file(project, args.type, chapter)
    return success(
        "archive-path",
        project=str(project),
        chapter=chapter,
        archive={"start": start, "end": end, "path": str(path), "type": args.type},
    )


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 小说文件工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan-projects")
    scan.add_argument("--root", required=True)
    scan.add_argument("--query", default="")
    scan.add_argument("--format", choices=["json", "markdown"], default="json")
    scan.set_defaults(handler=scan_projects)

    status = subparsers.add_parser("chapter-status")
    status.add_argument("--project", required=True)
    status.add_argument("--range", required=True)
    status.add_argument("--format", choices=["json", "markdown"], default="json")
    status.set_defaults(handler=chapter_status)

    archive = subparsers.add_parser("archive-path")
    archive.add_argument("--project", required=True)
    archive.add_argument("--chapter", required=True)
    archive.add_argument("--type", choices=["summary", "outline", "review", "repair"], required=True)
    archive.add_argument("--format", choices=["json", "markdown"], default="json")
    archive.set_defaults(handler=archive_path)

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

