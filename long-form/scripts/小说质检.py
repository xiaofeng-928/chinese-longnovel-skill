import argparse
import re
from pathlib import Path

from 公共工具 import count_review_chars, emit, failure, read_text, success
from 质检规则 import (
    ABILITY_TERMS,
    AI_THRESHOLDS,
    AI_TIER1,
    AI_TIER2,
    AI_TIER3,
    DEFAULT_FORBIDDEN_WORDS,
    TIME_ANCHOR_TERMS,
)



def count_terms(text, terms):
    return {
        term: {"count": text.count(term)}
        for term in terms
        if text.count(term) > 0
    }


def scan_ai_flavor(text):
    tier1_terms = count_terms(text, AI_TIER1)
    tier2_terms = count_terms(text, AI_TIER2)
    tier3_terms = count_terms(text, AI_TIER3)
    tier2_total = sum(item["count"] for item in tier2_terms.values())
    tier3_total = sum(item["count"] for item in tier3_terms.values())
    return {
        "tier1": {
            "triggered": any(
                item["count"] >= AI_THRESHOLDS["tier1_per_term"]
                for item in tier1_terms.values()
            ),
            "terms": tier1_terms,
        },
        "tier2": {
            "triggered": tier2_total > AI_THRESHOLDS["tier2_total"],
            "total": tier2_total,
            "terms": tier2_terms,
        },
        "tier3": {
            "triggered": tier3_total > AI_THRESHOLDS["tier3_total"],
            "total": tier3_total,
            "terms": tier3_terms,
        },
    }


def split_sentences(text):
    parts = re.split(r"(?<=[。！？!?；;])|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def scan_candidates(text, terms):
    candidates = []
    for sentence in split_sentences(text):
        matched = [term for term in terms if term in sentence]
        if matched:
            candidates.append({"text": sentence, "matched_terms": matched})
    return candidates


def find_project_root(file_path):
    for parent in [file_path.parent, *file_path.parents]:
        if (parent / "novel-config.md").is_file():
            return parent
    return None


def load_word_file(path):
    if not path or not Path(path).is_file():
        return []
    words = []
    for line in read_text(path).splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            words.append(word)
    return words


def load_forbidden_words(path, project_root=None):
    words = list(DEFAULT_FORBIDDEN_WORDS)
    if path:
        words.extend(load_word_file(path))
    whitelist_path = project_root / ".deslop-whitelist" if project_root else None
    return words, whitelist_path, load_word_file(whitelist_path)


def scan_forbidden_words(text, words):
    matches = []
    for word in words:
        count = text.count(word)
        if count > 0:
            matches.append({"word": word, "count": count})
    return {"matches": matches, "total": sum(item["count"] for item in matches)}


def lint(args):
    file_path = Path(args.file)
    text = read_text(file_path)
    project_root = find_project_root(file_path)
    forbidden_words, whitelist_path, whitelist = load_forbidden_words(
        args.forbidden_words, project_root
    )
    if whitelist:
        forbidden_words = [word for word in forbidden_words if word not in whitelist]
    warnings = []
    if not args.forbidden_words:
        warnings.append({
            "code": "FORBIDDEN_WORDS_NOT_CONFIGURED",
            "message": "未提供禁用词文件；禁用词扫描结果为空，不代表正文通过禁用词检查。",
        })
    return success(
        "lint",
        inputs={
            "file": str(file_path),
            "forbidden_words": str(args.forbidden_words) if args.forbidden_words else None,
            "project_root": str(project_root) if project_root else None,
            "whitelist": str(whitelist_path) if whitelist_path and whitelist_path.is_file() else None,
        },
        word_count={"count": count_review_chars(text), "unit": "review_char"},
        ai_flavor=scan_ai_flavor(text),
        forbidden_words=scan_forbidden_words(text, forbidden_words),
        time_anchor_candidates=scan_candidates(text, TIME_ANCHOR_TERMS),
        ability_candidates=scan_candidates(text, ABILITY_TERMS),
        warnings=warnings,
    )


def build_parser():
    parser = argparse.ArgumentParser(description="MyNovel 小说质检工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser("lint")
    lint_parser.add_argument("--file", required=True)
    lint_parser.add_argument("--forbidden-words")
    lint_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    lint_parser.set_defaults(handler=lint)

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
