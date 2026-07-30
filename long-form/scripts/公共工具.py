import json
import re
import sys
from pathlib import Path


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


def json_text(data):
    return json.dumps(data, ensure_ascii=False, indent=2)


def json_dump(data):
    write_stdout(json_text(data) + "\n")


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


def count_review_chars(text):
    """审查字数口径：非空白字符 + 省略号加权（……=6，…=3）。"""
    compact = re.sub(r"\s", "", text)
    n = len(compact)
    n += compact.count("……") * 4
    n += compact.replace("……", "").count("…") * 2
    return n


def markdown_response(data):
    lines = [f"# {data.get('command', 'result')}", ""]
    lines.append("```json")
    lines.append(json_text(data))
    lines.append("```")
    return "\n".join(lines)


def emit(data, output_format):
    if output_format == "markdown":
        write_stdout(markdown_response(data) + "\n")
    else:
        json_dump(data)


def write_stdout(text):
    data = text.encode("utf-8")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(data)
    else:
        sys.stdout.write(text)
