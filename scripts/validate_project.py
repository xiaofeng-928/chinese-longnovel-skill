#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate a MyNovel v3 project as a closed, committed state."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import 公共工具 as tool
import 项目事务 as tx


FIELD_RE = re.compile(r"^-\s+([a-z0-9_]+)\s*[:：]\s*(.*?)\s*$", re.MULTILINE)
STAGE_RE = re.compile(
    r"<!--\s*MYNOVEL:STAGE:([a-z0-9-]+):START\s*-->(.*?)"
    r"<!--\s*MYNOVEL:STAGE:\1:END\s*-->",
    re.DOTALL,
)
PLAN_NODE_RE = re.compile(
    r"<!--\s*MYNOVEL:PLAN-NODE:([a-z0-9-]+):START\s*-->(.*?)"
    r"<!--\s*MYNOVEL:PLAN-NODE:\1:END\s*-->",
    re.DOTALL,
)
WINDOW_RE = re.compile(
    r"<!--\s*MYNOVEL:WINDOW:([a-z0-9-]+):START\s*-->(.*?)"
    r"<!--\s*MYNOVEL:WINDOW:\1:END\s*-->",
    re.DOTALL,
)
BUDGET_ROW_RE = re.compile(
    r"^\|\s*第([1-9][0-9]*)-([1-9][0-9]*)章\s*\|"
    r"\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*$",
    re.MULTILINE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BUILD_ID_RE = re.compile(r"^epub-[0-9a-f]{12}-[0-9a-f]{12}$")


def fields_from_block(block: str) -> dict[str, str]:
    return {match.group(1): match.group(2).strip() for match in FIELD_RE.finditer(block)}


def prefixed(label: str, errors: list[str]) -> tuple[bool, list[str]]:
    return not errors, [f"{label}: {error}" for error in errors]


def check_manifest(project_root: Path):
    try:
        ok, errors = tx.validate_manifest(project_root)
    except (FileNotFoundError, UnicodeError, ValueError) as exc:
        return False, [f"manifest: {exc}"]
    return ok, [f"manifest: {error}" for error in errors]


def check_authority_files_exist(project_root: Path, core: dict, authority: dict):
    errors = []
    status = core.get("project_status")
    required_by_status = {
        "开书方案": ["开书方案"],
        "系统设计": ["开书方案", "参考素材", "文风规范"],
        "总纲": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范"],
        "细纲": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                 "当前剧情细纲", "章节序列", "提交头"],
        "正文中": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                  "当前剧情细纲", "章节序列", "提交头", "主角状态"],
        "完结": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                 "当前剧情细纲", "章节序列", "提交头", "主角状态"],
    }
    required = required_by_status.get(status)
    if required is None:
        return prefixed("authority", [f"unknown project_status: {status}"])
    if core.get("系统模式") == "required" and status in {"系统设计", "总纲", "细纲", "正文中", "完结"}:
        required.append("系统设定")
    if core.get("系统模式") == "required" and status in {"正文中", "完结"}:
        required.append("系统状态")
    for key in required:
        raw = authority.get(key)
        if not raw or raw == "null":
            errors.append(f"authority path missing for {key}")
            continue
        path = project_root / raw
        if not path.is_file():
            errors.append(f"declared authority file does not exist: {raw}")
    return prefixed("authority", errors)


def check_stale_runtime_state_in_plan(project_root: Path):
    errors = []
    patterns = [
        re.compile(r"已发布章节"), re.compile(r"已写第\s*[0-9]+"),
        re.compile(r"只写到第\s*[0-9]+"), re.compile(r"当前写到"),
    ]
    plan_dir = project_root / "plan"
    if not plan_dir.is_dir():
        return True, []
    for path in sorted(plan_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if any(pattern.search(text) for pattern in patterns):
            errors.append(f"stale runtime state in plan: {path.name}")
    return prefixed("plan", errors)


def check_html_anchors(project_root: Path):
    errors = []
    seen = set()
    anchor_re = re.compile(r"<!--\s*MYNOVEL:([A-Z-]+):([a-z0-9-]+):(START|END)\s*-->")
    for path in sorted(project_root.rglob("*.md")):
        if "legacy" in path.parts or "修复记录" in path.parts or path.name.startswith("~$") or path.name.startswith("."):
            continue
        counts = {}
        for kind, node, edge in anchor_re.findall(path.read_text(encoding="utf-8")):
            key = (kind, node)
            counts.setdefault(key, {"START": 0, "END": 0})[edge] += 1
            global_key = f"{kind}:{node}"
            if edge == "START" and global_key in seen:
                errors.append(f"duplicate anchor {global_key} in {path.name}")
            if edge == "START":
                seen.add(global_key)
        for key, edges in counts.items():
            if edges != {"START": 1, "END": 1}:
                errors.append(f"unpaired anchor {key[0]}:{key[1]} in {path.name}")
    return prefixed("anchor", errors)


def check_stage_schema(project_root: Path, core: dict, authority: dict):
    errors = []
    raw_path = authority.get("总大纲")
    if not raw_path or raw_path == "null" or not (project_root / raw_path).is_file():
        return prefixed("stage", ["total outline unavailable"])
    text = (project_root / raw_path).read_text(encoding="utf-8")
    stages = []
    seen = set()
    for anchor_id, block in STAGE_RE.findall(text):
        fields = fields_from_block(block)
        required = {"stage_id", "chapter_start", "chapter_end", "stage_status"}
        missing = sorted(required - fields.keys())
        if missing:
            errors.append(f"stage {anchor_id} missing fields: {missing}")
            continue
        if fields["stage_id"] != anchor_id:
            errors.append(f"stage anchor/field mismatch: {anchor_id}")
        if anchor_id in seen:
            errors.append(f"duplicate stage_id: {anchor_id}")
        seen.add(anchor_id)
        if fields["stage_status"] not in {"planned", "active", "completed", "superseded"}:
            errors.append(f"invalid stage_status: {anchor_id}")
        try:
            start, end = int(fields["chapter_start"]), int(fields["chapter_end"])
        except ValueError:
            errors.append(f"non-integer chapter range: {anchor_id}")
            continue
        if start <= 0 or end < start:
            errors.append(f"invalid chapter range: {anchor_id}")
        stages.append((start, end, anchor_id))
    if not stages:
        return prefixed("stage", errors + ["no MYNOVEL:STAGE blocks"])
    stages.sort()
    expected_start = 1
    for start, end, stage_id in stages:
        if start != expected_start:
            errors.append(f"stage coverage gap/overlap before {stage_id}: expected {expected_start}, got {start}")
        expected_start = end + 1
    try:
        target = int(core.get("目标章数下限", "0"))
    except ValueError:
        target = 0
    if stages[-1][1] < target:
        errors.append(f"stage coverage ends at {stages[-1][1]}, below target {target}")
    return prefixed("stage", errors)


def parse_window(raw: str | None) -> tuple[int, int] | None:
    match = re.fullmatch(r"第([1-9][0-9]*)-([1-9][0-9]*)章", raw or "")
    return (int(match.group(1)), int(match.group(2))) if match else None


def contract_value_present(raw: str | None) -> bool:
    return raw not in (None, "", "null", "[]")


def expected_window_id(start: int, end: int) -> str:
    return f"window-{start:04d}-{end:04d}"


def meaningful_budget_cell(value: str) -> bool:
    compact = re.sub(r"\s+", "", value).lower()
    placeholders = {
        "本组职责", "本组结算", "阶段退出", "后续负载",
        "允许结算", "禁止越过", "必须留给后组",
        "待定", "待补", "待填写", "占位", "todo", "tbd",
    }
    return bool(compact) and compact not in placeholders and not re.fullmatch(r"[.…·_\-/—]+", compact)


def check_window_contracts(project_root: Path, core: dict, authority: dict):
    protocol = core.get("规划窗口协议版本")
    if protocol in (None, "", "null"):
        return True, []
    errors = []
    if protocol != "1":
        return prefixed("window_contract", [f"unsupported protocol version: {protocol}"])

    raw_path = authority.get("总大纲")
    if not raw_path or raw_path == "null" or not (project_root / raw_path).is_file():
        return prefixed("window_contract", ["total outline unavailable"])
    text = (project_root / raw_path).read_text(encoding="utf-8")

    stages = {}
    for anchor_id, block in STAGE_RE.findall(text):
        fields = fields_from_block(block)
        try:
            start = int(fields.get("chapter_start", ""))
            end = int(fields.get("chapter_end", ""))
        except ValueError:
            continue
        stages[anchor_id] = {
            "start": start,
            "end": end,
            "exit_condition": fields.get("exit_condition"),
        }

    required = {
        "window_id", "stage_id", "chapter_start", "chapter_end", "window_status",
        "stage_exit_allowed", "system_plan", "must_complete", "advance_only",
        "protagonist_progress_cap", "system_progress_cap", "forbidden_early_completion",
        "reserved_for_later", "end_unresolved",
        "next_stage_forbidden", "next_window_id", "five_chapter_budget_status",
    }
    windows = {}
    for anchor_id, block in WINDOW_RE.findall(text):
        fields = fields_from_block(block)
        missing = sorted(required - fields.keys())
        if missing:
            errors.append(f"window {anchor_id} missing fields: {missing}")
            continue
        window_id = fields["window_id"]
        if window_id != anchor_id:
            errors.append(f"window anchor/field mismatch: {anchor_id}")
        if window_id in windows:
            errors.append(f"duplicate window_id: {window_id}")
            continue
        try:
            start = int(fields["chapter_start"])
            end = int(fields["chapter_end"])
        except ValueError:
            errors.append(f"window range must be integer: {window_id}")
            continue
        if start <= 0 or end < start or end - start + 1 > 50:
            errors.append(f"invalid window range: {window_id}")
        if window_id != expected_window_id(start, end):
            errors.append(f"window_id/range mismatch: {window_id}")
        status = fields["window_status"]
        if status not in {"reserved", "prepared", "active", "consumed", "superseded"}:
            errors.append(f"invalid window_status: {window_id}")
        if fields["stage_exit_allowed"] not in {"true", "false"}:
            errors.append(f"stage_exit_allowed must be true/false: {window_id}")
        budget_status = fields["five_chapter_budget_status"]
        if budget_status not in {"pending", "locked"}:
            errors.append(f"invalid five_chapter_budget_status: {window_id}")
        if budget_status == "locked":
            if not re.search(r"^##\s+五章剧情预算\s*$", block, re.MULTILINE):
                errors.append(f"locked window missing five-chapter budget table: {window_id}")
            budget_rows = BUDGET_ROW_RE.findall(block)
            budget_ranges = [(int(row[0]), int(row[1])) for row in budget_rows]
            expected_ranges = []
            cursor = start
            while cursor <= end:
                group_end = min(cursor + 4, end)
                expected_ranges.append((cursor, group_end))
                cursor = group_end + 1
            if budget_ranges != expected_ranges:
                errors.append(
                    f"five-chapter budget coverage mismatch: {window_id}: "
                    f"got={budget_ranges} expected={expected_ranges}"
                )
            cell_names = ("responsibility", "settlement", "boundary", "reserve")
            for row in budget_rows:
                row_label = f"第{row[0]}-{row[1]}章"
                for name, value in zip(cell_names, row[2:]):
                    if not meaningful_budget_cell(value):
                        errors.append(
                            f"five-chapter budget cell empty/placeholder: "
                            f"{window_id}:{row_label}:{name}"
                        )
        for key in (
            "must_complete", "protagonist_progress_cap", "system_progress_cap",
            "forbidden_early_completion", "end_unresolved", "next_stage_forbidden",
        ):
            if not contract_value_present(fields.get(key)):
                errors.append(f"{key} empty: {window_id}")
        stage = stages.get(fields["stage_id"])
        if stage is None:
            errors.append(f"unknown stage_id for window {window_id}: {fields['stage_id']}")
        elif start < stage["start"] or end > stage["end"]:
            errors.append(f"window outside stage range: {window_id}")
        system_plan = fields["system_plan"]
        if system_plan != "null":
            try:
                _, system_path = tx.project_relative_path(project_root, system_plan)
            except ValueError as exc:
                errors.append(f"{window_id}: {exc}")
            else:
                if status in {"prepared", "active"} and not system_path.is_file():
                    errors.append(f"prepared window system plan missing: {window_id}: {system_plan}")
        elif status in {"prepared", "active"}:
            errors.append(f"prepared window requires system_plan: {window_id}")
        windows[window_id] = {
            "fields": fields,
            "block": block,
            "start": start,
            "end": end,
        }

    if not windows:
        return prefixed("window_contract", errors + ["protocol enabled but no MYNOVEL:WINDOW blocks"])

    by_stage = {}
    for window_id, item in windows.items():
        if item["fields"]["window_status"] == "superseded":
            continue
        by_stage.setdefault(item["fields"]["stage_id"], []).append((window_id, item))
    for stage_id, stage_windows in by_stage.items():
        stage = stages.get(stage_id)
        if stage is None:
            continue
        if not contract_value_present(stage.get("exit_condition")):
            errors.append(f"stage exit_condition empty: {stage_id}")
        ordered = sorted(stage_windows, key=lambda pair: (pair[1]["start"], pair[1]["end"]))
        expected_start = stage["start"]
        for index, (window_id, item) in enumerate(ordered):
            fields = item["fields"]
            if item["start"] != expected_start:
                errors.append(
                    f"window coverage gap/overlap in {stage_id}: expected {expected_start}, got {item['start']}"
                )
            expected_start = item["end"] + 1
            is_last = item["end"] == stage["end"]
            allowed = fields["stage_exit_allowed"] == "true"
            if allowed != is_last:
                errors.append(f"stage_exit_allowed inconsistent with stage end: {window_id}")
            if is_last:
                if fields["next_window_id"] != "null":
                    errors.append(f"final stage window next_window_id must be null: {window_id}")
            else:
                if not contract_value_present(fields.get("reserved_for_later")):
                    errors.append(f"reserved_for_later empty before stage end: {window_id}")
                next_id = fields["next_window_id"]
                next_item = windows.get(next_id)
                if next_item is None:
                    errors.append(f"next_window_id missing target: {window_id}: {next_id}")
                elif next_item["fields"]["stage_id"] != stage_id or next_item["start"] != item["end"] + 1:
                    errors.append(f"next_window_id is not the next continuous window: {window_id}: {next_id}")
            if index < len(ordered) - 1 and fields["next_window_id"] != ordered[index + 1][0]:
                errors.append(f"next_window_id order mismatch: {window_id}")
        if expected_start != stage["end"] + 1:
            errors.append(
                f"window contracts do not cover full stage {stage_id}: end at {expected_start - 1}, expected {stage['end']}"
            )

    configured = [
        (
            "当前", core.get("当前计划窗口"), core.get("当前窗口合同"),
            core.get("当前剧情预算锁"), authority.get("当前系统计划"),
        ),
        (
            "下一", core.get("下一计划窗口"), core.get("下一窗口合同"),
            core.get("下一剧情预算锁"), authority.get("下一系统计划"),
        ),
    ]
    for label, raw_window, contract_id, lock, authority_system_plan in configured:
        parsed = parse_window(raw_window)
        if parsed is None:
            if (
                contract_id not in (None, "", "null")
                or lock not in (None, "", "null")
                or authority_system_plan not in (None, "", "null")
            ):
                errors.append(f"{label}计划窗口为 null 时合同、预算锁和系统计划也必须为 null")
            continue
        if not contract_value_present(contract_id):
            errors.append(f"{label}计划窗口缺少窗口合同")
            continue
        if lock != "locked":
            errors.append(f"{label}剧情预算锁必须为 locked")
        item = windows.get(contract_id)
        if item is None:
            errors.append(f"{label}窗口合同不存在: {contract_id}")
            continue
        if (item["start"], item["end"]) != parsed:
            errors.append(f"{label}窗口合同范围与计划窗口不一致: {contract_id}")
        if item["fields"]["window_status"] not in {"prepared", "active", "consumed"}:
            errors.append(f"{label}窗口合同状态不可用于细纲: {contract_id}")
        if item["fields"]["five_chapter_budget_status"] != "locked":
            errors.append(f"{label}窗口合同五章剧情预算未锁定: {contract_id}")
        if authority_system_plan in (None, "", "null"):
            errors.append(f"{label}窗口缺少 manifest 系统计划路径")
        elif item["fields"]["system_plan"] != authority_system_plan:
            errors.append(f"{label}系统计划路径与窗口合同不一致: {contract_id}")

    return prefixed("window_contract", errors)


def parse_task_refs(raw: str) -> bool:
    if raw == "[]":
        return True
    return bool(re.fullmatch(r"\[[a-z0-9-]+(?:,\s*[a-z0-9-]+)*\]", raw))


def check_plan_nodes(project_root: Path, core: dict, authority: dict):
    if core.get("project_status") in {"开书方案", "系统设计", "总纲"}:
        return True, []
    errors = []
    raw_path = authority.get("当前剧情细纲")
    window = parse_window(core.get("当前计划窗口"))
    if not raw_path or raw_path == "null" or not (project_root / raw_path).is_file():
        return prefixed("plan_schema", ["current plot outline unavailable"])
    if window is None:
        return prefixed("plan_schema", ["current plan window invalid"])
    text = (project_root / raw_path).read_text(encoding="utf-8")
    nodes = []
    seen_ids = set()
    main_chapters = set()
    for anchor_id, block in PLAN_NODE_RE.findall(text):
        fields = fields_from_block(block)
        required = {
            "node_id", "planned_main_chapter", "node_type", "mainline_anchor",
            "plan_status", "task_refs",
        }
        missing = sorted(required - fields.keys())
        if missing:
            errors.append(f"plan node {anchor_id} missing fields: {missing}")
            continue
        node_id = fields["node_id"]
        if anchor_id != node_id:
            errors.append(f"plan node anchor/field mismatch: {anchor_id}")
        if node_id in seen_ids:
            errors.append(f"duplicate plan node_id: {node_id}")
        seen_ids.add(node_id)
        node_type = fields["node_type"]
        if node_type not in {"main", "insert", "side"}:
            errors.append(f"invalid node_type: {node_id}")
        if fields["plan_status"] not in {"planned", "consumed", "superseded"}:
            errors.append(f"invalid plan_status: {node_id}")
        if not fields["mainline_anchor"]:
            errors.append(f"mainline_anchor empty: {node_id}")
        if not parse_task_refs(fields["task_refs"]):
            errors.append(f"task_refs invalid: {node_id}")
        try:
            chapter = int(fields["planned_main_chapter"])
        except ValueError:
            errors.append(f"planned_main_chapter invalid: {node_id}")
            continue
        if not window[0] <= chapter <= window[1]:
            errors.append(f"planned_main_chapter outside current window: {node_id}")
        if node_type == "main":
            if chapter in main_chapters:
                errors.append(f"duplicate main chapter: {chapter}")
            main_chapters.add(chapter)
        nodes.append((node_id, node_type, chapter))
    if not nodes:
        return prefixed("plan_schema", errors + ["no MYNOVEL:PLAN-NODE blocks"])
    expected = set(range(window[0], window[1] + 1))
    if main_chapters != expected:
        missing = sorted(expected - main_chapters)
        extra = sorted(main_chapters - expected)
        errors.append(f"main plan coverage mismatch: missing={missing} extra={extra}")
    return prefixed("plan_schema", errors)


def check_commit_chain(project_root: Path, core: dict):
    status = core.get("project_status")
    if status in {"开书方案", "系统设计", "总纲"}:
        return True, []
    project_id = core.get("project_id")
    if not project_id:
        return prefixed("chain", ["project_id missing"])
    ok, errors = tx.verify_chain(project_root, project_id)
    return ok, [f"chain: {error}" for error in errors]


def check_projection_and_pollution(project_root: Path, core: dict, authority: dict):
    errors = []
    head = tx.read_head(project_root)
    if head is None:
        return prefixed("projection", ["commit head missing"])
    if head.get("project_id") != core.get("project_id"):
        errors.append("project_id does not close between manifest and head")
    sequence_raw = authority.get("章节序列")
    if sequence_raw and sequence_raw != "null" and (project_root / sequence_raw).is_file():
        fields = fields_from_block((project_root / sequence_raw).read_text(encoding="utf-8"))
        if fields.get("materialized_head_transaction_id") != head.get("head_transaction_id"):
            errors.append("chapter sequence materialized head transaction mismatch")
        if fields.get("materialized_head_sha256") != head.get("commit_hash"):
            errors.append("chapter sequence materialized head hash mismatch")
    projections = head.get("projection_hashes")
    if not isinstance(projections, dict):
        errors.append("projection_hashes must be an object")
        projections = {}
    for raw, expected_hash in projections.items():
        try:
            relative, path = tx.project_relative_path(project_root, raw)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not SHA256_RE.fullmatch(str(expected_hash)):
            errors.append(f"projection hash invalid: {relative}")
        elif not path.is_file():
            errors.append(f"projection file missing: {relative}")
        elif tx.sha256_file(path) != expected_hash:
            errors.append(f"projection hash mismatch: {relative}")
    try:
        chain = tx.chain_parents(project_root, head)
    except ValueError as exc:
        return prefixed("projection", errors + [str(exc)])
    reachable_ids = {item["transaction_id"] for item in chain if item["transaction_id"] != "tx-genesis"}
    transactions_dir = project_root / tx.TRANSACTIONS_DIR
    if transactions_dir.is_dir():
        actual_ids = {path.name for path in transactions_dir.iterdir() if path.is_dir()}
        for transaction_id in sorted(actual_ids - reachable_ids):
            errors.append(f"uncommitted transaction present: {transaction_id}")
    committed_body_paths = set()
    for manifest in chain[:-1]:
        for relative in (manifest.get("assets") or {}):
            if relative.startswith("正文/"):
                committed_body_paths.add(relative)
    body_dir = project_root / "正文"
    if body_dir.is_dir():
        for path in body_dir.rglob("*.md"):
            relative = path.relative_to(project_root).as_posix()
            if relative not in committed_body_paths:
                errors.append(f"uncommitted body pollution: {relative}")
    return prefixed("projection", errors)


def check_runtime_mode(project_root: Path, core: dict):
    errors = []
    head = tx.read_head(project_root)
    if head is None:
        return prefixed("runtime", ["commit head missing"])
    manifest_mode = core.get("operation_mode")
    head_mode = head.get("operation_mode", "normal")
    if manifest_mode != head_mode:
        errors.append(f"operation mode mismatch: manifest={manifest_mode} head={head_mode}")
    rebase_id = head.get("rebase_id")
    if head_mode == "maintenance":
        if not rebase_id:
            errors.append("maintenance head requires rebase_id")
        elif not (project_root / tx.PRODUCTION_ROOT / "rebases" / rebase_id / "manifest.json").is_file():
            errors.append("maintenance rebase manifest missing")
    elif rebase_id:
        errors.append("normal/epub head cannot retain rebase_id")
    return prefixed("runtime", errors)


def check_epub_exports(project_root: Path, core: dict):
    errors = []
    head = tx.read_head(project_root) or {}
    export_root = project_root / tx.PRODUCTION_ROOT / "exports"
    if not export_root.is_dir():
        return True, []
    for path in export_root.rglob("export-manifest.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeError) as exc:
            errors.append(f"invalid export manifest {path.name}: {exc}")
            continue
        required = {
            "project_id", "build_id", "source_head_transaction_id", "source_head_commit_hash",
            "epub_path", "epub_sha256", "plan_snapshot_sha256",
        }
        missing = sorted(required - data.keys())
        if missing:
            errors.append(f"export manifest missing fields: {missing}")
            continue
        if data["project_id"] != core.get("project_id"):
            errors.append("export project_id mismatch")
        if not BUILD_ID_RE.fullmatch(str(data["build_id"])):
            errors.append("export build_id invalid")
        if data["source_head_transaction_id"] != head.get("head_transaction_id"):
            errors.append("export source head transaction is stale")
        if data["source_head_commit_hash"] != head.get("commit_hash"):
            errors.append("export source head hash is stale")
        epub = Path(data["epub_path"])
        if not epub.is_absolute():
            epub = project_root / epub
        if not epub.is_file() or tx.sha256_file(epub) != data["epub_sha256"]:
            errors.append("export EPUB hash mismatch or file missing")
        if not SHA256_RE.fullmatch(str(data["plan_snapshot_sha256"])):
            errors.append("export plan snapshot hash invalid")
    return prefixed("epub", errors)


def check_duplicate_authority_blocks(project_root: Path):
    errors = []
    for path in sorted(project_root.rglob("*.md")):
        if "legacy" in path.parts or "修复记录" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ["# 文风规范", "# 系统设定", "# 角色档案", "# 世界观"]:
            if text.count(marker) > 1:
                errors.append(f"duplicate authority block {marker} in {path.name}")
    return prefixed("dup-authority", errors)


def check_project(project_root: Path):
    report = {"project_root": str(project_root), "checks": {}}
    manifest_check = check_manifest(project_root)
    try:
        core, authority = tx.parse_manifest(project_root)
    except (FileNotFoundError, UnicodeError, ValueError) as exc:
        core, authority = {}, {}
        if manifest_check[0]:
            manifest_check = False, [f"manifest: {exc}"]
    checks = {
        "manifest": manifest_check,
        "authority": check_authority_files_exist(project_root, core, authority),
        "plan": check_stale_runtime_state_in_plan(project_root),
        "anchor": check_html_anchors(project_root),
        "stage": check_stage_schema(project_root, core, authority),
        "window_contract": check_window_contracts(project_root, core, authority),
        "plan_schema": check_plan_nodes(project_root, core, authority),
        "chain": check_commit_chain(project_root, core),
        "projection": check_projection_and_pollution(project_root, core, authority),
        "runtime": check_runtime_mode(project_root, core),
        "epub": check_epub_exports(project_root, core),
        "duplicate_authority": check_duplicate_authority_blocks(project_root),
    }
    for name, (ok, errors) in checks.items():
        report["checks"][name] = {"ok": ok, "errors": errors}
    report["ok"] = all(detail["ok"] for detail in report["checks"].values())
    return report


def main():
    parser = argparse.ArgumentParser(description="validate MyNovel project structure")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_project(args.project_root)
    if args.json:
        tool.json_dump(report)
    else:
        lines = []
        for name, detail in report["checks"].items():
            lines.append(f"[{'OK' if detail['ok'] else 'FAIL'}] {name}")
            lines.extend(f"        {error}" for error in detail["errors"])
        lines.append(f"result: {'pass' if report['ok'] else 'fail'}")
        tool.write_stdout("\n".join(lines) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
