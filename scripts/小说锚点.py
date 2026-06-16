import argparse
from pathlib import Path

from 公共工具 import emit, failure, read_text, success, write_text


def anchor_lines(chapter, kind):
    chapter = int(chapter)
    return (
        f"<!-- chapter:{chapter} {kind}:start -->",
        f"<!-- chapter:{chapter} {kind}:end -->",
    )


def locate_anchor_block(text, chapter, kind):
    start_anchor, end_anchor = anchor_lines(chapter, kind)
    lines = text.splitlines(keepends=True)
    starts = []
    ends = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == start_anchor:
            starts.append(index)
        elif stripped == end_anchor:
            ends.append(index)

    result = {
        "exists": len(starts) == 1 and len(ends) == 1,
        "missing": not starts and not ends,
        "duplicate": len(starts) > 1 or len(ends) > 1,
        "start_count": len(starts),
        "end_count": len(ends),
        "line_range": None,
        "start_index": None,
        "end_index": None,
        "start_anchor": start_anchor,
        "end_anchor": end_anchor,
    }
    if result["exists"] and starts[0] < ends[0]:
        result["line_range"] = {"start": starts[0] + 1, "end": ends[0] + 1}
        result["start_index"] = starts[0]
        result["end_index"] = ends[0]
    elif starts or ends:
        result["exists"] = False
    return result


def public_check_data(command, file_path, chapter, kind, block):
    return success(
        command,
        file=str(file_path),
        chapter=int(chapter),
        kind=kind,
        exists=block["exists"],
        missing=block["missing"],
        duplicate=block["duplicate"],
        start_count=block["start_count"],
        end_count=block["end_count"],
        line_range=block["line_range"],
    )


def check(args):
    file_path = Path(args.file)
    block = locate_anchor_block(read_text(file_path), args.chapter, args.kind)
    return public_check_data("check", file_path, args.chapter, args.kind, block)


def replace(args):
    file_path = Path(args.file)
    text = read_text(file_path)
    block = locate_anchor_block(text, args.chapter, args.kind)
    base = public_check_data("replace", file_path, args.chapter, args.kind, block)
    base["dry_run"] = bool(args.dry_run)
    base["changed"] = False

    if not block["exists"]:
        base["ok"] = False
        base["error"] = {
            "code": "ANCHOR_NOT_UNIQUE",
            "message": "目标锚点不存在或不唯一，未写入文件",
        }
        return base

    lines = text.splitlines(keepends=True)
    content = read_text(args.content_file).rstrip("\r\n") + "\n"
    new_lines = (
        lines[: block["start_index"] + 1]
        + [content]
        + lines[block["end_index"] :]
    )
    new_text = "".join(new_lines)
    base["changed"] = new_text != text
    if base["changed"] and not args.dry_run:
        write_text(file_path, new_text)
    return base


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 小说锚点工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--file", required=True)
    check_parser.add_argument("--chapter", required=True)
    check_parser.add_argument("--kind", choices=["summary", "review", "outline", "repair"], required=True)
    check_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    check_parser.set_defaults(handler=check)

    replace_parser = subparsers.add_parser("replace")
    replace_parser.add_argument("--file", required=True)
    replace_parser.add_argument("--chapter", required=True)
    replace_parser.add_argument("--kind", choices=["summary", "review", "outline", "repair"], required=True)
    replace_parser.add_argument("--content-file", required=True)
    replace_parser.add_argument("--dry-run", action="store_true")
    replace_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    replace_parser.set_defaults(handler=replace)

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
