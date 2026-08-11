#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add deterministic PLAN-NODE wrappers to an existing chapter-outline file."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


HEADING_RE = re.compile(r"(?m)^(#{1,6}\s*第([1-9][0-9]*)章[^\r\n]*)$")


def migrate(path: Path, start: int, end: int, mainline_anchor: str) -> None:
    text = path.read_text(encoding="utf-8")
    if "MYNOVEL:PLAN-NODE" in text:
        raise ValueError(f"PLAN-NODE markers already exist: {path}")
    matches = list(HEADING_RE.finditer(text))
    found = [int(match.group(2)) for match in matches]
    expected = list(range(start, end + 1))
    if found != expected:
        raise ValueError(f"chapter headings must exactly cover {start}-{end}; found {found}")
    pieces = [text[:matches[0].start()]]
    for index, match in enumerate(matches):
        chapter = int(match.group(2))
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        original = text[match.start():body_end].rstrip()
        node_id = f"chapter-{chapter:04d}"
        pieces.append(
            f"<!-- MYNOVEL:PLAN-NODE:{node_id}:START -->\n"
            f"- node_id: {node_id}\n"
            f"- planned_main_chapter: {chapter}\n"
            f"- node_type: main\n"
            f"- mainline_anchor: {mainline_anchor}\n"
            f"- plan_status: planned\n"
            f"- task_refs: []\n\n"
            f"{original}\n"
            f"<!-- MYNOVEL:PLAN-NODE:{node_id}:END -->\n\n"
        )
    path.write_text("".join(pieces).rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--start", required=True, type=int)
    parser.add_argument("--end", required=True, type=int)
    parser.add_argument("--mainline-anchor", required=True)
    args = parser.parse_args()
    migrate(args.path, args.start, args.end, args.mainline_anchor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
