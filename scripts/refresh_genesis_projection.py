#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bind a migrated, body-empty project genesis head to its current plan projections."""

from __future__ import annotations

import argparse
from pathlib import Path

import 项目事务 as tx


def refresh(project_root: Path) -> None:
    core, authority = tx.parse_manifest(project_root)
    head = tx.read_head(project_root)
    if not head or head.get("head_transaction_id") != "tx-genesis":
        raise ValueError("refresh_genesis_projection only accepts a genesis project")
    body_dir = project_root / "正文"
    if body_dir.is_dir() and any(body_dir.rglob("*.md")):
        raise ValueError("refusing to refresh genesis while body files exist")
    projection_keys = ["总大纲", "当前剧情细纲", "当前系统计划"]
    projections = {}
    for key in projection_keys:
        raw = authority.get(key)
        if not raw or raw == "null":
            continue
        relative, path = tx.project_relative_path(project_root, raw)
        if not path.is_file():
            raise FileNotFoundError(f"projection file missing: {relative}")
        projections[relative] = tx.sha256_file(path)
    head.update({
        "project_id": core["project_id"],
        "parent_transaction_id": None,
        "generation_id": "gen-0001",
        "committed_node_id": None,
        "projection_hashes": projections,
        "chain_hash": tx.sha256_text(f"{core['project_id']}:tx-genesis"),
        "operation_mode": core.get("operation_mode", "normal"),
    })
    head["commit_hash"] = tx.canonical_json_hash(head, ("commit_hash",))
    tx.atomic_write_json(project_root / tx.COMMIT_HEAD_PATH, head)
    sequence_raw = authority.get("章节序列")
    if sequence_raw and sequence_raw != "null":
        _, sequence = tx.project_relative_path(project_root, sequence_raw)
        sequence.parent.mkdir(parents=True, exist_ok=True)
        tx.atomic_write_text(
            sequence,
            "# 章节序列\n\n"
            f"- materialized_head_transaction_id: {head['head_transaction_id']}\n"
            f"- materialized_head_sha256: {head['commit_hash']}\n",
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    refresh(args.project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
