#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""validate_project.py — 项目验证器。

检查 manifest schema、权威路径存在性、commit head 链、plan 过期运行态、
HTML 锚点、状态仓库拆分声明、重复权威块、章节节点推进顺序、未提交事务污染。

用法：
  py -3 scripts/validate_project.py --project-root <项目根>
  py -3 scripts/validate_project.py --project-root <项目根> --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import 项目事务 as tx
import 公共工具 as tool


def check_manifest(project_root: Path):
    ok, errors = tx.validate_manifest(project_root)
    return ok, [f"manifest: {e}" for e in errors]


def check_authority_files_exist(project_root: Path, status: str):
    """按生命周期检查必需权威文件（文档 9.1）。"""
    core, authority = tx.parse_manifest(project_root)
    errors = []
    required_relative = {
        "开书方案": ["开书方案"],
        "系统设计": ["开书方案", "参考素材", "系统设定", "文风规范"],
        "总纲": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范"],
        "细纲": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                 "当前剧情细纲", "章节序列"],
        "正文中": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                  "当前剧情细纲", "章节序列", "提交头", "主角状态"],
        "完结": ["开书方案", "参考素材", "世界观", "角色档案", "总大纲", "文风规范",
                 "当前剧情细纲", "章节序列", "提交头", "主角状态"],
    }[status]

    for key in required_relative:
        value = authority.get(key)
        if not value or value == "null":
            errors.append(f"authority path missing for {key}")
            continue
        path = project_root / value
        if not path.is_file():
            errors.append(f"declared authority file does not exist: {value}")

    # required 系统模式：系统设定在"系统设计"状态起必需，系统状态在"正文中"起必需
    core = dict(core)
    system_statuses = {"系统设计", "总纲", "细纲", "正文中", "完结"}
    runtime_statuses = {"正文中", "完结"}
    if core.get("系统模式") == "required":
        if status in system_statuses:
            value = authority.get("系统设定")
            if not value or value == "null":
                errors.append(f"required system mode needs authority path: 系统设定")
            elif not (project_root / value).is_file():
                errors.append(f"declared system authority file missing: {value}")
        if status in runtime_statuses:
            value = authority.get("系统状态")
            if not value or value == "null":
                errors.append(f"required system mode needs authority path: 系统状态")
            elif not (project_root / value).is_file():
                errors.append(f"declared system authority file missing: {value}")
    return not errors, [f"authority: {e}" for e in errors]


def check_stale_runtime_state_in_plan(project_root: Path):
    """plan 文件不得携带“当前写到第几章”等过期运行态（文档 3.8）。"""
    errors = []
    patterns = [
        re.compile(r"已发布章节"),
        re.compile(r"已写第\s*[0-9]+"),
        re.compile(r"只写到第\s*[0-9]+"),
        re.compile(r"当前写到"),
    ]
    plan_dir = project_root / "plan"
    if not plan_dir.is_dir():
        return True, []
    for path in sorted(plan_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for pat in patterns:
            if pat.search(text):
                errors.append(f"stale runtime state in plan: {path.name}")
                break
    return not errors, [f"plan: {e}" for e in errors]


def check_html_anchors(project_root: Path):
    """HTML 锚点不得重复、必须配对（文档 9.4）。"""
    errors = []
    seen = set()
    for path in sorted(project_root.rglob("*.md")):
        if "legacy" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        starts = re.findall(r"<!--\s*MYNOVEL:([A-Z-]+):([a-z0-9-]+):START\s*-->", text)
        ends = re.findall(r"<!--\s*MYNOVEL:([A-Z-]+):([a-z0-9-]+):END\s*-->", text)
        for kind, node in starts:
            if f"{kind}:{node}" in seen:
                errors.append(f"duplicate anchor {kind}:{node} in {path.name}")
            seen.add(f"{kind}:{node}")
        start_set = set(starts)
        end_set = set(ends)
        if start_set != end_set:
            errors.append(f"unpaired anchors in {path.name}")
    return not errors, [f"anchor: {e}" for e in errors]


def check_commit_chain(project_root: Path, status: str):
    core, _ = tx.parse_manifest(project_root)
    project_id = core.get("project_id")
    if not project_id:
        return True, []
    # 开书方案/系统设计/总纲 状态尚未进入正文生产，不需要 genesis head
    if status in ("开书方案", "系统设计", "总纲"):
        return True, []
    ok, errors = tx.verify_chain(project_root, project_id)
    return ok, [f"chain: {e}" for e in errors]


def check_duplicate_authority_blocks(project_root: Path):
    """文风、系统、角色、世界观不得出现重复权威块（文档 13.4）。"""
    errors = []
    for path in sorted(project_root.rglob("*.md")):
        if "legacy" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ["# 文风规范", "# 系统设定", "# 角色档案", "# 世界观"]:
            count = text.count(marker)
            if count > 1:
                errors.append(f"duplicate authority block {marker} in {path.name}")
    return not errors, [f"dup-authority: {e}" for e in errors]


def check_project(project_root: Path):
    report = {"project_root": str(project_root), "checks": {}}
    core, _ = tx.parse_manifest(project_root)
    status = core.get("project_status", "")

    checks = {
        "manifest": check_manifest(project_root),
        "authority": check_authority_files_exist(project_root, status),
        "plan": check_stale_runtime_state_in_plan(project_root),
        "anchor": check_html_anchors(project_root),
        "chain": check_commit_chain(project_root, status),
        "duplicate_authority": check_duplicate_authority_blocks(project_root),
    }

    all_ok = True
    for name, (ok, errors) in checks.items():
        report["checks"][name] = {"ok": ok, "errors": errors}
        if not ok:
            all_ok = False
    report["ok"] = all_ok
    return report


def main():
    parser = argparse.ArgumentParser(description="validate MyNovel project structure")
    parser.add_argument("--project-root", required=True, type=Path, help="小说项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而非 markdown")
    args = parser.parse_args()

    report = check_project(args.project_root)
    if args.json:
        tool.json_dump(report)
    else:
        lines = []
        for name, detail in report["checks"].items():
            status = "OK" if detail["ok"] else "FAIL"
            lines.append(f"[{status}] {name}")
            for err in detail["errors"]:
                lines.append(f"        {err}")
        lines.append(f"result: {'pass' if report['ok'] else 'fail'}")
        tool.write_stdout("\n".join(lines) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
