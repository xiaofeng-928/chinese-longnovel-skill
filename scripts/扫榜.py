# -*- coding: utf-8 -*-
"""扫榜.py — 榜单数据规范化和聚合器（不是抓榜器）。

把已取得的公开榜单记录标准化、校验、去重、跨平台分组并写入不可变归档。
进程退出码：0=ready、2=schema_invalid、3=insufficient_samples、
4=stale_evidence、5=dedup_conflict、6=archive_io_error。
多种错误同时存在时按 2→5→6→3→4 的优先级返回。

人类可读说明写到标准错误；机器结果固定通过 JSON 标准输出。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.parse
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
EVIDENCE_DIMENSIONS = {"opening", "payoff", "management_loop", "system_loop",
                       "voice", "long_structure"}
VALID_FIELDS = {
    "source_platform", "list_name", "snapshot_date", "rank", "title", "author",
    "work_id", "canonical_work_id", "url", "genre_tags", "evidence_dimensions",
    "captured_at",
}
REQUIRED_FIELDS = {"source_platform", "list_name", "snapshot_date", "title", "url", "captured_at"}
MARKET_DIMENSIONS = {"management_loop", "system_loop"}
ARCHIVE_ROOT = Path(r"D:\ai小说\小说\范文\扫榜")

EXIT_READY = 0
EXIT_SCHEMA_INVALID = 2
EXIT_INSUFFICIENT = 3
EXIT_STALE = 4
EXIT_DEDUP_CONFLICT = 5
EXIT_ARCHIVE_IO = 6


def write_stdout_text(text: str) -> None:
    data = text.encode("utf-8")
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(data)
    else:
        sys.stdout.write(text)


def write_stderr(text: str) -> None:
    data = text.encode("utf-8")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr.buffer.write(data)
    else:
        sys.stderr.write(text)


def normalize_url(raw: str) -> str:
    """URI 解析器统一规范化 URL。只接受绝对 http/https。"""
    if not isinstance(raw, str) or not raw:
        return ""
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return ""
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    # 去掉默认端口
    if host.endswith(":80") and scheme == "http":
        host = host[:-3]
    elif host.endswith(":443") and scheme == "https":
        host = host[:-4]
    query_pairs = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().startswith("utm_") or key.lower() == "spm":
            continue
        query_pairs.append((key, value))
    query = urllib.parse.urlencode(sorted(query_pairs), doseq=True)
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"
    return urllib.parse.urlunsplit((scheme, host, path, query, ""))  # 去掉 fragment


def parse_rank(value):
    if value in (None, ""):
        return None
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return "invalid"
    return rank if rank > 0 else "invalid"


def parse_date(value, key="snapshot_date"):
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def validate_record(raw: dict) -> tuple[dict | None, list[str]]:
    """返回 (规范化记录, 错误列表)。schema 无效时记录被丢弃。"""
    errors = []
    record = {}
    for field in REQUIRED_FIELDS:
        value = raw.get(field)
        if value in (None, ""):
            errors.append(f"missing required field: {field}")
            return None, errors
        record[field] = str(value)

    url = normalize_url(raw.get("url", ""))
    if not url:
        errors.append("url is not an absolute http(s) URL")
        return None, errors
    record["url"] = url

    rank = parse_rank(raw.get("rank"))
    if rank == "invalid":
        errors.append("rank must be a positive integer or null")
        return None, errors
    record["rank"] = rank

    snapshot = parse_date(record["snapshot_date"], "snapshot_date")
    if snapshot is None:
        errors.append("snapshot_date must be YYYY-MM-DD")
        return None, errors
    # 未来日期属于 schema_invalid
    if snapshot > date.today():
        errors.append("snapshot_date is in the future")
        return None, errors
    record["snapshot_date"] = snapshot.isoformat()

    captured = parse_date(record["captured_at"], "captured_at")
    if captured is None:
        errors.append("captured_at must be an ISO 8601 date")
        return None, errors
    record["captured_at"] = record["captured_at"]

    for field in ("author", "work_id", "canonical_work_id"):
        value = raw.get(field)
        record[field] = None if value in (None, "") else str(value)

    tags = raw.get("genre_tags") or raw.get("genres") or raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    record["genre_tags"] = [str(t) for t in tags if str(t)]

    dims = raw.get("evidence_dimensions") or []
    if isinstance(dims, str):
        dims = [dims]
    bad_dims = [str(d) for d in dims if str(d) not in EVIDENCE_DIMENSIONS]
    if bad_dims:
        errors.append(f"invalid evidence_dimensions: {bad_dims}")
        return None, errors
    record["evidence_dimensions"] = [str(d) for d in dims]

    return record, errors


def load_json_input(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        records = data.get("records")
    else:
        raise ValueError("JSON root object must be {\"schema_version\": 1, \"records\": [...]}")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    return records


def load_csv_input(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV must have a header row with field names")
    records = []
    for row in reader:
        record = {}
        for field in VALID_FIELDS:
            record[field] = row.get(field)
        for key in ("genre_tags", "evidence_dimensions"):
            value = record.get(key)
            if value:
                try:
                    record[key] = json.loads(value)
                except ValueError:
                    record[key] = [value]
        records.append(record)
    return records


def load_records(path: Path):
    if path.suffix.lower() == ".csv":
        return load_csv_input(path)
    return load_json_input(path)


def dedupe(records: list[dict]):
    """平台内去重：键依次为 source_platform+work_id、规范化 URL。书名不能单独判重。"""
    kept: dict[tuple, dict] = {}
    conflicts: list[dict] = []
    for record in records:
        keys = []
        if record.get("work_id"):
            keys.append(("work", record["source_platform"], record["work_id"]))
        keys.append(("url", record["source_platform"], record["url"]))
        merged = False
        for key in keys:
            existing = kept.get(key)
            if existing is not None:
                # 相同键、核心字段一致 → 保留 captured_at 最新
                if (existing["title"] == record["title"]
                        and existing["author"] == record["author"]
                        and existing["url"] == record["url"]):
                    if record["captured_at"] >= existing["captured_at"]:
                        kept[key] = record
                else:
                    conflicts.append({
                        "key": list(key),
                        "existing": existing,
                        "incoming": record,
                        "reason": "same key but conflicting core fields",
                    })
                merged = True
                break
        if not merged:
            kept[keys[-1]] = record
    return list(kept.values()), conflicts


def cross_platform_groups(records: list[dict]):
    """按 canonical_work_id 分组；无 canonical 时暂按平台内键。"""
    groups: dict = {}
    for record in records:
        cid = record.get("canonical_work_id")
        if cid:
            group_key = ("canonical", cid)
        else:
            group_key = ("platform", record["source_platform"], record["url"])
        groups.setdefault(group_key, []).append(record)
    possible_dups = []
    # 规范化书名 + 规范化作者相同而平台键不同 → 进入疑似跨平台重复
    name_map: dict = {}
    for record in records:
        key = (record["title"], record.get("author"))
        if record.get("canonical_work_id"):
            continue
        if key in name_map and name_map[key] != record["source_platform"]:
            possible_dups.append({
                "title": record["title"],
                "author": record.get("author"),
                "records": [name_map[key], record],
            })
        else:
            name_map[key] = record["source_platform"]
    return groups, possible_dups


def is_fresh(record: dict) -> bool:
    snapshot = parse_date(record["snapshot_date"], "snapshot_date")
    if snapshot is None:
        return False
    delta = (date.today() - snapshot).days
    return 0 <= delta <= 30


def count_market_records(records: list[dict]) -> tuple[int, int]:
    """market_validation_count：去重+跨平台分组后含经营证据的不同作品；
    fresh_market_validation_count：再限制每条 snapshot_date 均在过去 0-30 日。"""
    market = [r for r in records if set(r["evidence_dimensions"]) & MARKET_DIMENSIONS]
    # 同一作品（canonical 或平台+url）只计一次
    seen = set()
    market_dedup = []
    for r in market:
        cid = r.get("canonical_work_id")
        key = ("canonical", cid) if cid else ("url", r["source_platform"], r["url"])
        if key not in seen:
            seen.add(key)
            market_dedup.append(r)
    fresh = [r for r in market_dedup if is_fresh(r)]
    return len(market_dedup), len(fresh)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def archive_name(records: list[dict]) -> str:
    latest = max(parse_date(r["snapshot_date"], "snapshot_date") or date.min for r in records)
    platforms = sorted({r["source_platform"] for r in records})
    scope = "+".join(platforms)
    import re
    scope = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", scope)
    if len(scope) > 48:
        scope = scope[:48] + hashlib.sha256(scope.encode("utf-8")).hexdigest()[:8]
    return f"{latest.isoformat()}_经营系统_{scope}_PLACEHOLDER.json"


def main():
    parser = argparse.ArgumentParser(description="MyNovel 扫榜数据规范化与聚合器")
    parser.add_argument("--input", required=True, help="JSON 或 CSV 榜单记录")
    parser.add_argument("--archive-dir", default=str(ARCHIVE_ROOT), help="扫榜归档目录")
    args = parser.parse_args()

    input_path = Path(args.input)
    archive_dir = Path(args.archive_dir)
    if not input_path.is_file():
        sys.exit(EXIT_SCHEMA_INVALID)
    try:
        raw_records = load_records(input_path)
    except Exception as exc:
        payload = {"status": "schema_invalid", "valid_count": 0,
                   "market_validation_count": 0, "fresh_market_validation_count": 0,
                   "latest_snapshot_date": None, "deduplicated_count": 0,
                   "possible_cross_platform_duplicates": [], "conflicts": [],
                   "archive_path": None, "sha256": None,
                   "error": {"code": "schema_invalid", "message": str(exc)}}
        write_stdout_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        sys.exit(EXIT_SCHEMA_INVALID)

    valid = []
    invalid = []
    for raw in raw_records:
        if not isinstance(raw, dict):
            invalid.append({"reason": "record is not an object"})
            continue
        record, errors = validate_record(raw)
        if record is None:
            invalid.append({"raw": raw, "errors": errors})
        else:
            valid.append(record)

    deduped, conflicts = dedupe(valid)
    groups, possible_dups = cross_platform_groups(deduped)
    market_count, fresh_count = count_market_records(deduped)

    dates = [parse_date(r["snapshot_date"], "snapshot_date") for r in deduped]
    latest = max((d for d in dates if d), default=None)
    latest_iso = latest.isoformat() if latest else None

    # 优先级 2→5→6→3→4，status 与 exit_code 必须一致
    archive_io_error = False
    if invalid:
        status = "schema_invalid"
        exit_code = EXIT_SCHEMA_INVALID
    elif conflicts:
        status = "dedup_conflict"
        exit_code = EXIT_DEDUP_CONFLICT
    elif market_count < 5:
        status = "insufficient_samples"
        exit_code = EXIT_INSUFFICIENT
    elif fresh_count < 5:
        status = "stale_evidence"
        exit_code = EXIT_STALE
    else:
        status = "ready"
        exit_code = EXIT_READY

    # 归档：不可变，同路径同哈希返回 ready + reused
    archive_path = None
    archive_sha = None
    reused = False
    archive_io_error = False
    if not invalid and not conflicts:
        try:
            serialized = json.dumps(
                {"schema_version": SCHEMA_VERSION, "records": deduped},
                ensure_ascii=False, sort_keys=True, indent=2)
            archive_sha = sha256_text(serialized)
            latest_d = latest or date.today()
            scope = "+".join(sorted({r["source_platform"] for r in deduped}))
            import re
            scope = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", scope)
            if len(scope) > 48:
                scope = scope[:48] + hashlib.sha256(scope.encode("utf-8")).hexdigest()[:8]
            filename = f"{latest_d.isoformat()}_经营系统_{scope}_{archive_sha}.json"
            target = archive_dir / filename
            if target.is_file():
                existing_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                if existing_hash == sha256_text(
                        target.read_text(encoding="utf-8")):
                    reused = True
                archive_path = str(target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(serialized, encoding="utf-8", newline="")
                archive_path = str(target)
        except OSError as exc:
            archive_io_error = True
            write_stderr(f"archive io error: {exc}\n")

    if archive_io_error:
        status = "archive_io_error"
        exit_code = EXIT_ARCHIVE_IO

    payload = {
        "status": status,
        "valid_count": len(valid),
        "market_validation_count": market_count,
        "fresh_market_validation_count": fresh_count,
        "latest_snapshot_date": latest_iso,
        "deduplicated_count": len(deduped),
        "possible_cross_platform_duplicates": possible_dups,
        "conflicts": conflicts,
        "archive_path": archive_path,
        "sha256": archive_sha,
        "reused": reused,
    }
    write_stdout_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
