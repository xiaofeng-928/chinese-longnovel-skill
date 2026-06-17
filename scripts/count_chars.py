#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""审查字数统计 CLI，口径与小说质检.py 一致。"""

from __future__ import annotations

import argparse
from pathlib import Path

from 公共工具 import count_review_chars


def iter_markdown(paths):
    files = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    return files


def main():
    parser = argparse.ArgumentParser(
        description="审查字数统计（省略号加权口径）。"
    )
    parser.add_argument("paths", nargs="+", type=Path, help="Markdown 文件或目录")
    args = parser.parse_args()

    for file_path in iter_markdown(args.paths):
        text = file_path.read_text(encoding="utf-8")
        print(f"{file_path}: {count_review_chars(text)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
