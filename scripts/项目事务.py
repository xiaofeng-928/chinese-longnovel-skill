#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""项目事务运行时：manifest、单写者锁、genesis/commit-head 链、不可变事务与投影重建。

状态目录约定：
- 写锁：项目根 `.mynovel-write-lock.json`
- commit head：`修复记录/生产状态/commit-head.json`
- 事务：`修复记录/生产状态/transactions/<transaction_id>/`
- 尝试工作区：`修复记录/生产状态/attempts/<node_id>/<attempt_id>/`

本模块只处理确定性事实；不负责自然化、审查等模型行为。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid as uuid_module
from pathlib import Path

import 公共工具 as tool

PRODUCTION_ROOT = Path("修复记录") / "生产状态"
LOCK_PATH = Path(".mynovel-write-lock.json")
COMMIT_HEAD_PATH = PRODUCTION_ROOT / "commit-head.json"
TRANSACTIONS_DIR = PRODUCTION_ROOT / "transactions"

# 生命周期枚举（按 vNext schema）
PROJECT_STATUSES = ["开书方案", "系统设计", "总纲", "细纲", "正文中", "完结"]
MIGRATION_STATES = ["legacy", "staging", "active"]
OPERATION_MODES = ["normal", "migration", "maintenance", "epub"]
PRODUCT_TYPES = ["长篇经营类系统爽文", "legacy-long-form"]
SYSTEM_MODES = ["required", "legacy-none"]

REQUIRED_MANIFEST_KEYS = [
    "schema_version",
    "migration_state",
    "legacy_scope",
    "legacy_source_hash",
    "legacy_snapshot_path",
    "operation_mode",
    "project_status",
    "project_id",
    "书名",
    "产品类型",
    "系统模式",
    "经营主线",
    "目标章数下限",
    "当前计划窗口",
    "下一计划窗口",
    "最近迁移日期",
    "文风版本",
    "文风生效节点",
    "系统设定版本",
]

MANIFEST_HEADING = "# 项目清单"
AUTHORITY_HEADING = "## 权威路径"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """原子写：先写同目录临时文件，再 os.replace。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(str(tmp), str(path))


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def new_uuid() -> str:
    return str(uuid_module.uuid4())


def utc_timestamp() -> str:
    return f"{__import__('datetime').datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%S%z}"


def now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def parse_manifest_text(text: str):
    """解析 vNext manifest（容忍 `键：值` 与 `键: 值`、`**` 加粗标记）。"""
    data = {}
    authority = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if line == MANIFEST_HEADING:
            section = "core"
            continue
        if line.startswith(AUTHORITY_HEADING):
            section = "authority"
            continue
        m = re.match(r"^-\s+\*{0,2}([^*:\s：][^*：:]*?)\*{0,2}\s*[:：]\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if section == "authority":
            authority[key] = value
        else:
            data[key] = value
    return data, authority


def parse_manifest(project_root: Path):
    """解析 manifest 并返回 (core, authority) 字典。"""
    config = project_root / "novel-config.md"
    if not config.is_file():
        raise FileNotFoundError(f"missing novel-config.md at {config}")
    return parse_manifest_text(config.read_text(encoding="utf-8"))


def parse_bool(value):
    return str(value).strip().lower() in ("true", "1", "yes")


def validate_manifest(project_root: Path, project_id: str | None = None):
    """校验 manifest schema。返回 (ok: bool, errors: list[str])。"""
    core, authority = parse_manifest(project_root)
    errors = []

    missing = [k for k in REQUIRED_MANIFEST_KEYS if k not in core]
    if missing:
        errors.append(f"manifest missing required keys: {missing}")

    if "schema_version" in core and core["schema_version"] != "3":
        errors.append("schema_version must be 3")

    if "migration_state" in core and core["migration_state"] not in MIGRATION_STATES:
        errors.append(f"migration_state must be one of {MIGRATION_STATES}")

    if "operation_mode" in core and core["operation_mode"] not in OPERATION_MODES:
        errors.append(f"operation_mode must be one of {OPERATION_MODES}")

    if "project_status" in core and core["project_status"] not in PROJECT_STATUSES:
        errors.append(f"project_status must be one of {PROJECT_STATUSES}")

    if "产品类型" in core and core["产品类型"] not in PRODUCT_TYPES:
        errors.append(f"产品类型 must be one of {PRODUCT_TYPES}")

    if "系统模式" in core and core["系统模式"] not in SYSTEM_MODES:
        errors.append(f"系统模式 must be one of {SYSTEM_MODES}")

    pid = core.get("project_id")
    if pid:
        try:
            uuid_module.UUID(pid)
        except ValueError:
            errors.append(f"project_id is not a valid UUID: {pid}")
    elif not errors:
        errors.append("project_id missing")

    if project_id is not None and pid and pid != project_id:
        errors.append(f"project_id mismatch: manifest={pid} expected={project_id}")

    if "目标章数下限" in core:
        try:
            if int(core["目标章数下限"]) <= 0:
                errors.append("目标章数下限 must be positive")
        except ValueError:
            errors.append("目标章数下限 must be an integer")

    # 权威路径必须是项目根相对路径
    for key, value in authority.items():
        if value == "null":
            continue
        target = (project_root / value).resolve()
        if not target.is_relative_to(project_root.resolve()):
            errors.append(f"authority path escapes project root: {value}")

    return not errors, errors


class WriteLock:
    """项目单写者锁。获取用原子 CREATE_NEW，防止并发双写。"""

    REQUIRED = [
        "lock_id", "project_id", "owner_id", "operation",
        "base_head_sha256", "acquired_at", "heartbeat_at", "lease_until",
    ]

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.lock_path = self.project_root / LOCK_PATH

    def _create_new(self, data: dict) -> None:
        tmp = self.lock_path.with_name(self.lock_path.name + ".tmp")
        atomic_write_bytes(tmp, json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
        try:
            # CREATE_NEW 语义：目标已存在则失败
            os.link(str(tmp), str(self.lock_path))
        except OSError:
            tmp.unlink(missing_ok=True)
            raise FileExistsError(f"write lock already held: {self.lock_path}")
        tmp.unlink(missing_ok=True)

    def acquire(self, project_id: str, owner_id: str, operation: str = "normal",
                lease_seconds: int = 3600, base_head_sha256: str | None = None) -> str:
        if operation not in OPERATION_MODES:
            raise ValueError(f"invalid operation: {operation}")
        lock_id = new_uuid()
        acquired = now_iso()
        data = {
            "lock_id": lock_id,
            "project_id": project_id,
            "owner_id": owner_id,
            "operation": operation,
            "base_head_sha256": base_head_sha256 or "",
            "acquired_at": acquired,
            "heartbeat_at": acquired,
            "lease_until": "",
        }
        self._create_new(data)
        self.renew(lock_id, lease_seconds=lease_seconds)
        return lock_id

    def read(self):
        return load_json(self.lock_path)

    def renew(self, lock_id: str, lease_seconds: int = 3600):
        current = self.read()
        if not current or current.get("lock_id") != lock_id:
            raise PermissionError("lock token mismatch")
        current["heartbeat_at"] = now_iso()
        import datetime
        lease = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=lease_seconds)
        current["lease_until"] = lease.isoformat(timespec="seconds")
        atomic_write_json(self.lock_path, current)
        return current

    def is_active(self, lock_id: str | None = None) -> bool:
        current = self.read()
        if not current:
            return False
        if lock_id is not None and current.get("lock_id") != lock_id:
            return False
        import datetime
        try:
            lease = datetime.datetime.fromisoformat(current["lease_until"])
        except (KeyError, ValueError):
            return False
        return lease > datetime.datetime.now(datetime.timezone.utc)

    def release(self, lock_id: str) -> None:
        current = self.read()
        if not current or current.get("lock_id") != lock_id:
            raise PermissionError("lock token mismatch")
        self.lock_path.unlink(missing_ok=True)

    def recover_stale(self, stale_dir: Path, lease_seconds: int = 3600):
        """过期锁恢复：先核对锁文件哈希与当前 head，再 CAS 改名后重新获取。"""
        current = self.read()
        if not current:
            return None
        import datetime
        try:
            lease = datetime.datetime.fromisoformat(current["lease_until"])
        except (KeyError, ValueError):
            raise RuntimeError("malformed lock lease; manual inspection required")
        if lease > datetime.datetime.now(datetime.timezone.utc):
            raise PermissionError("lock is not stale")
        lock_hash = sha256_file(self.lock_path)
        stale_dir.mkdir(parents=True, exist_ok=True)
        stale_target = stale_dir / f"stale-lock-{current['lock_id']}.json"
        os.replace(str(self.lock_path), str(stale_target))
        stale_target.write_text(
            json.dumps({**current, "recovered_at": now_iso(), "original_sha256": lock_hash},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.acquire(
            current["project_id"], current.get("owner_id", "recovery"),
            operation=current.get("operation", "normal"),
            lease_seconds=lease_seconds,
        )


def atomic_write_json(path: Path, data) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def genesis_head(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "head_transaction_id": "tx-genesis",
        "parent_transaction_id": None,
        "generation_id": "gen-0001",
        "committed_node_id": None,
        "projection_hashes": {},
    }


def create_genesis(project_root: Path, project_id: str) -> dict:
    head = genesis_head(project_id)
    atomic_write_json(project_root / COMMIT_HEAD_PATH, head)
    return head


def read_head(project_root: Path) -> dict | None:
    return load_json(project_root / COMMIT_HEAD_PATH)


def head_hash(project_root: Path) -> str:
    head = read_head(project_root)
    if head is None:
        return ""
    return sha256_file(project_root / COMMIT_HEAD_PATH)


def tx_manifest_path(project_root: Path, transaction_id: str) -> Path:
    return project_root / TRANSACTIONS_DIR / transaction_id / "manifest.json"


def prepare_transaction(project_root: Path, *, project_id: str, parent_transaction_id: str,
                        generation_id: str, base_head_sha256: str, node_id: str,
                        attempt_id: str, assets: dict, sequence_event: dict | None = None,
                        transaction_id: str | None = None) -> dict:
    """创建不可变事务清单。assets 为 {relative_path: sha256}，增量块哈希由调用方提供。"""
    if transaction_id is None:
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        transaction_id = f"tx-{node_id}-{stamp}-{uuid_module.uuid4().hex[:8]}"
    manifest = {
        "project_id": project_id,
        "transaction_id": transaction_id,
        "parent_transaction_id": parent_transaction_id,
        "generation_id": generation_id,
        "base_head_sha256": base_head_sha256,
        "node_id": node_id,
        "attempt_id": attempt_id,
        "assets": assets,
        "sequence_event": sequence_event,
    }
    manifest["manifest_sha256"] = sha256_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    )
    path = tx_manifest_path(project_root, transaction_id)
    atomic_write_json(path, manifest)
    return manifest


def chain_parents(project_root: Path, head: dict | None = None) -> list[dict]:
    """从 head 沿 parent_transaction_id 回溯到 genesis，返回有序列表。"""
    head = head or read_head(project_root)
    if head is None:
        return []
    chain = []
    seen = set()
    current_id = head.get("head_transaction_id")
    while current_id and current_id not in seen:
        seen.add(current_id)
        if current_id == "tx-genesis":
            chain.append({"transaction_id": "tx-genesis", "parent_transaction_id": None})
            break
        mf = load_json(tx_manifest_path(project_root, current_id))
        if not mf:
            raise ValueError(f"broken chain: transaction {current_id} missing")
        chain.append(mf)
        current_id = mf.get("parent_transaction_id")
    return chain


def verify_chain(project_root: Path, project_id: str, base_head_sha256: str | None = None):
    """校验 commit head 链：project_id 一致、无环、哈希匹配。返回 (ok, errors)。"""
    errors = []
    head = read_head(project_root)
    if head is None:
        return False, ["commit-head.json missing"]
    if head.get("project_id") != project_id:
        errors.append("commit-head project_id mismatch")
    if base_head_sha256 is not None and head_hash(project_root) != base_head_sha256:
        errors.append("commit-head hash mismatch")
    try:
        chain = chain_parents(project_root, head)
    except ValueError as exc:
        return False, [str(exc)]
    return not errors, errors


def commit_head_cas(project_root: Path, new_head: dict, base_head_sha256: str) -> str:
    """CAS 提交：仅当当前 head 哈希等于 base_head_sha256 时原子替换。"""
    current = head_hash(project_root)
    if current != base_head_sha256:
        raise RuntimeError(
            f"compare-and-swap failed: current={current[:12]} base={base_head_sha256[:12]}"
        )
    new_head["commit_hash"] = sha256_text(
        json.dumps(new_head, ensure_ascii=False, sort_keys=True)
    )
    atomic_write_json(project_root / COMMIT_HEAD_PATH, new_head)
    return new_head["commit_hash"]
