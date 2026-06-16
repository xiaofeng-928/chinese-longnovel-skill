import argparse
from pathlib import Path

from 公共工具 import (
    archive_file,
    directory_for,
    emit,
    failure,
    list_chapter_files,
    success,
)


def file_exists_item(path):
    path = Path(path)
    return {"path": str(path), "exists": path.is_file()}


def recent_chapter_items(project, chapter):
    chapter = int(chapter)
    files = list_chapter_files(project)
    by_chapter = {}
    for item in files:
        number = item["chapter"]
        by_chapter.setdefault(number, []).append(item)

    start = max(1, chapter - 3)
    items = []
    for number in range(start, chapter):
        chapter_files = by_chapter.get(number, [])
        if chapter_files:
            items.append(
                {
                    "chapter": number,
                    "files": chapter_files,
                    "duplicate": len(chapter_files) > 1,
                }
            )
    return items


def chapter_summary_items(project, chapter):
    chapter = int(chapter)
    if chapter <= 1:
        return []
    return [
        {
            "path": str(archive_file(project, "summary", chapter - 1)),
            "range": {"start": max(1, chapter - 20), "end": chapter - 1},
        }
    ]


def outline_item(project, chapter):
    chapter = int(chapter)
    return {
        "current": file_exists_item(archive_file(project, "outline", chapter)),
        "next_boundary_chapters": [chapter + 1, chapter + 2],
    }


def stage_summary_items(project):
    directory = directory_for(project, "stage_summary")
    if not directory.is_dir():
        return []
    return [
        {"path": str(path), "exists": True}
        for path in sorted(directory.glob("*.md"))
    ]


def build(args):
    project = Path(args.project)
    chapter = int(args.chapter)
    config = project / "novel-config.md"
    return success(
        "build",
        project=str(project),
        chapter=chapter,
        mode=args.mode,
        novel_config=str(config),
        recent_chapters=recent_chapter_items(project, chapter),
        chapter_summaries=chapter_summary_items(project, chapter),
        outline=outline_item(project, chapter),
        stage_summaries=stage_summary_items(project),
        foreshadowing_hints=[],
    )


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 小说上下文工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--project", required=True)
    build_parser.add_argument("--chapter", required=True)
    build_parser.add_argument("--mode", choices=["draft", "review", "repair"], required=True)
    build_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    build_parser.set_defaults(handler=build)

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
