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
import datetime
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


def canonical_json_hash(data: dict, excluded: tuple[str, ...] = ()) -> str:
    payload = {key: value for key, value in data.items() if key not in excluded}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(encoded)


def project_relative_path(project_root: Path, raw_path: str) -> tuple[str, Path]:
    """Return a normalized project-relative path and reject traversal/absolute paths."""
    if not raw_path or "\\" in raw_path or Path(raw_path).is_absolute():
        raise ValueError(f"asset path must be a forward-slash project-relative path: {raw_path}")
    resolved_root = project_root.resolve()
    resolved = (project_root / raw_path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"asset path escapes project root: {raw_path}")
    return resolved.relative_to(resolved_root).as_posix(), resolved


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """原子写：先写同目录临时文件，再 os.replace。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    try:
        os.replace(str(tmp), str(path))
    except PermissionError:
        path.write_bytes(data)
        tmp.unlink(missing_ok=True)



def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def new_uuid() -> str:
    return str(uuid_module.uuid4())


def utc_timestamp() -> str:
    return f"{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%S%z}"


def now_iso() -> str:
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
            parsed_pid = uuid_module.UUID(pid)
            if parsed_pid.version != 4 or str(parsed_pid) != pid:
                errors.append("project_id must be canonical lowercase UUID v4")
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

    for key in ("legacy_scope", "经营主线"):
        if key in core and core[key] not in ("true", "false"):
            errors.append(f"{key} must be true or false")

    if core.get("migration_state") == "staging" and core.get("operation_mode") != "migration":
        errors.append("staging migration_state requires operation_mode migration")
    if core.get("migration_state") == "active" and core.get("operation_mode") not in (
        "normal", "maintenance", "epub"
    ):
        errors.append("active migration_state requires normal, maintenance, or epub operation_mode")
    if core.get("legacy_scope") == "true":
        for key in ("legacy_source_hash", "legacy_snapshot_path"):
            if core.get(key) in (None, "", "null"):
                errors.append(f"legacy project requires {key}")
        if core.get("产品类型") != "legacy-long-form":
            errors.append("legacy_scope true requires 产品类型 legacy-long-form")
    elif core.get("产品类型") == "legacy-long-form":
        errors.append("产品类型 legacy-long-form requires legacy_scope true")
    if core.get("legacy_scope") == "false" and core.get("系统模式") != "required":
        errors.append("vNext new project requires 系统模式 required")
    if core.get("legacy_scope") == "false" and core.get("经营主线") != "true":
        errors.append("vNext new project requires 经营主线 true")
    if core.get("legacy_scope") == "false" and core.get("目标章数下限"):
        try:
            if int(core["目标章数下限"]) < 1000:
                errors.append("vNext new project target must be at least 1000 chapters")
        except ValueError:
            pass

    for key in ("当前计划窗口", "下一计划窗口"):
        value = core.get(key)
        if value not in (None, "null") and not re.fullmatch(r"第[1-9][0-9]*-[1-9][0-9]*章", value):
            errors.append(f"{key} must be 第X-Y章 or null")
    for key in ("文风版本", "系统设定版本"):
        value = core.get(key)
        if value not in (None, "null") and not re.fullmatch(r"v[0-9]+\.[0-9]+", value):
            errors.append(f"{key} must be vN.N or null")
    value = core.get("文风生效节点")
    if value not in (None, "null") and not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", value):
        errors.append("文风生效节点 must be a node_id or null")
    value = core.get("最近迁移日期")
    if value not in (None, "null"):
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            errors.append("最近迁移日期 must be YYYY-MM-DD or null")

    # 权威路径必须是项目根相对路径
    for key, value in authority.items():
        if value == "null":
            continue
        if not value or Path(value).is_absolute() or "\\" in value:
            errors.append(f"authority path must be a non-empty forward-slash relative path: {value}")
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
        expected_head = current.get("base_head_sha256", "")
        if expected_head and expected_head != head_hash(self.project_root):
            raise RuntimeError("stale lock base head changed; manual recovery required")
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


def genesis_head(project_id: str, projection_hashes: dict | None = None) -> dict:
    head = {
        "project_id": project_id,
        "head_transaction_id": "tx-genesis",
        "parent_transaction_id": None,
        "generation_id": "gen-0001",
        "committed_node_id": None,
        "projection_hashes": dict(projection_hashes or {}),
        "chain_hash": sha256_text(f"{project_id}:tx-genesis"),
    }
    head["commit_hash"] = canonical_json_hash(head, ("commit_hash",))
    return head


def create_genesis(project_root: Path, project_id: str,
                   projection_hashes: dict | None = None) -> dict:
    path = project_root / COMMIT_HEAD_PATH
    if path.exists():
        raise FileExistsError(f"genesis already exists: {path}")
    head = genesis_head(project_id, projection_hashes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(head, stream, ensure_ascii=False, indent=2)
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


def validate_body_asset_names(assets: dict, review_status: str) -> None:
    """Keep the user-visible draft suffix aligned with the formal review state."""
    for relative in assets:
        normalized = str(relative).replace("\\", "/")
        if not normalized.startswith("正文/") or not normalized.endswith(".md"):
            continue
        is_draft = normalized.endswith("（草稿）.md")
        if review_status == "review_pending" and not is_draft:
            raise ValueError("review_pending body asset must keep the （草稿） suffix")
        if review_status == "review_passed" and is_draft:
            raise ValueError("review_passed body asset must not keep the （草稿） suffix")


def prepare_transaction(project_root: Path, *, project_id: str, parent_transaction_id: str,
                        generation_id: str, base_head_sha256: str, node_id: str,
                        attempt_id: str, assets: dict, sequence_event: dict | None = None,
                        review_evidence: dict | None = None,
                        review_status: str | None = None,
                        transaction_id: str | None = None) -> dict:
    """创建不可变事务清单。assets 为 {relative_path: sha256}，增量块哈希由调用方提供。"""
    if transaction_id is None:
        import datetime
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        transaction_id = f"tx-{node_id}-{stamp}-{uuid_module.uuid4().hex[:8]}"
    if not isinstance(assets, dict):
        raise ValueError("assets must be a mapping of project-relative path to sha256")
    all_review_evidence = {
        "naturalization_review_sha256", "context_review_sha256",
        "state_validation_report_sha256",
    }
    if review_status is None:
        review_status = (
            "review_passed" if isinstance(review_evidence, dict)
            and all_review_evidence.issubset(review_evidence)
            else "review_pending"
        )
    if review_status not in {"review_pending", "review_passed"}:
        raise ValueError("review_status must be review_pending or review_passed")
    validate_body_asset_names(assets, review_status)
    required_review_evidence = {"state_validation_report_sha256"}
    if review_status == "review_passed":
        required_review_evidence = all_review_evidence
    if not isinstance(review_evidence, dict) or not required_review_evidence.issubset(review_evidence):
        raise ValueError("review_evidence is incomplete for review_status")
    formal_keys = {"naturalization_review_sha256", "context_review_sha256"}
    if len(formal_keys.intersection(review_evidence)) == 1:
        raise ValueError("formal review evidence must contain both review hashes")
    for key in all_review_evidence.intersection(review_evidence):
        if not re.fullmatch(r"[0-9a-f]{64}", str(review_evidence[key])):
            raise ValueError(f"invalid review evidence hash: {key}")
    transaction_dir = tx_manifest_path(project_root, transaction_id).parent
    transaction_dir.mkdir(parents=True, exist_ok=False)
    immutable_assets = {}
    try:
        for raw_path, expected_hash in sorted(assets.items()):
            relative, source = project_relative_path(project_root, str(raw_path))
            if not source.is_file():
                raise FileNotFoundError(f"transaction asset missing: {relative}")
            actual_hash = sha256_file(source)
            if actual_hash != expected_hash:
                raise ValueError(f"transaction asset hash mismatch: {relative}")
            snapshot_relative = (Path("assets") / Path(relative)).as_posix()
            snapshot = transaction_dir / snapshot_relative
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            with snapshot.open("xb") as stream:
                stream.write(source.read_bytes())
            immutable_assets[relative] = {
                "sha256": actual_hash,
                "snapshot_path": snapshot_relative,
            }

        evidence_paths = {
            "naturalization_review_sha256": "reviews/naturalization.md",
            "context_review_sha256": "reviews/context.md",
            "state_validation_report_sha256": "reviews/state.md",
        }
        for evidence_key, suffix in evidence_paths.items():
            if evidence_key not in review_evidence:
                continue
            matches = [
                item for relative, item in immutable_assets.items()
                if relative.endswith(suffix)
            ]
            if len(matches) != 1 or matches[0]["sha256"] != review_evidence[evidence_key]:
                raise ValueError(f"review evidence is not backed by one immutable asset: {evidence_key}")

        manifest = {
        "project_id": project_id,
        "transaction_id": transaction_id,
        "parent_transaction_id": parent_transaction_id,
        "generation_id": generation_id,
        "base_head_sha256": base_head_sha256,
        "node_id": node_id,
        "attempt_id": attempt_id,
        "assets": immutable_assets,
        "sequence_event": sequence_event,
        "review_status": review_status,
        "review_evidence": review_evidence,
        "created_at": now_iso(),
        }
        manifest["manifest_sha256"] = canonical_json_hash(manifest, ("manifest_sha256",))
        path = tx_manifest_path(project_root, transaction_id)
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
    except Exception:
        # Only the newly-created transaction directory is eligible for rollback.
        for child in sorted(transaction_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        transaction_dir.rmdir()
        raise
    return manifest


def chain_parents(project_root: Path, head: dict | None = None) -> list[dict]:
    """从 head 沿 parent_transaction_id 回溯到 genesis，返回有序列表。"""
    head = head or read_head(project_root)
    if head is None:
        return []
    chain = []
    seen = set()
    current_id = head.get("head_transaction_id")
    if not current_id:
        raise ValueError("broken chain: head transaction ID missing")
    while True:
        if current_id in seen:
            raise ValueError(f"cycle detected at transaction {current_id}")
        seen.add(current_id)
        if current_id == "tx-genesis":
            chain.append({"transaction_id": "tx-genesis", "parent_transaction_id": None})
            break
        mf = load_json(tx_manifest_path(project_root, current_id))
        if not mf:
            raise ValueError(f"broken chain: transaction {current_id} missing")
        chain.append(mf)
        current_id = mf.get("parent_transaction_id")
        if not current_id:
            raise ValueError("broken chain: reached null before tx-genesis")
    return chain


def verify_chain(project_root: Path, project_id: str, base_head_sha256: str | None = None):
    """校验 commit head 链：project_id 一致、无环、哈希匹配。返回 (ok, errors)。"""
    errors = []
    head = read_head(project_root)
    if head is None:
        return False, ["commit-head.json missing"]
    if head.get("project_id") != project_id:
        errors.append("commit-head project_id mismatch")
    stored_commit_hash = head.get("commit_hash")
    if not stored_commit_hash:
        errors.append("commit-head commit_hash missing")
    elif stored_commit_hash != canonical_json_hash(head, ("commit_hash",)):
        errors.append("commit-head commit_hash mismatch")
    if not head.get("chain_hash"):
        errors.append("commit-head chain_hash missing")
    if base_head_sha256 is not None and head_hash(project_root) != base_head_sha256:
        errors.append("commit-head hash mismatch")
    try:
        chain = chain_parents(project_root, head)
    except ValueError as exc:
        return False, [str(exc)]
    for index, manifest in enumerate(chain[:-1]):
        transaction_id = manifest.get("transaction_id")
        if manifest.get("project_id") != project_id:
            errors.append(f"transaction project_id mismatch: {transaction_id}")
        if not transaction_id or tx_manifest_path(project_root, transaction_id).parent.name != transaction_id:
            errors.append(f"transaction ID/path mismatch: {transaction_id}")
        expected_hash = canonical_json_hash(manifest, ("manifest_sha256",))
        if manifest.get("manifest_sha256") != expected_hash:
            errors.append(f"transaction manifest hash mismatch: {transaction_id}")
        if not manifest.get("generation_id"):
            errors.append(f"transaction generation missing: {transaction_id}")
        review_evidence = manifest.get("review_evidence")
        all_evidence = {
            "naturalization_review_sha256", "context_review_sha256",
            "state_validation_report_sha256",
        }
        review_status = manifest.get("review_status")
        if review_status is None and isinstance(review_evidence, dict) and all_evidence.issubset(review_evidence):
            review_status = "review_passed"
        if review_status not in {"review_pending", "review_passed"}:
            errors.append(f"transaction review status invalid: {transaction_id}")
        else:
            try:
                validate_body_asset_names(manifest.get("assets") or {}, review_status)
            except ValueError as exc:
                errors.append(f"transaction body filename/status mismatch: {transaction_id}: {exc}")
        required_evidence = {"state_validation_report_sha256"}
        if review_status == "review_passed":
            required_evidence = all_evidence
        if not isinstance(review_evidence, dict) or not required_evidence.issubset(review_evidence):
            errors.append(f"transaction review evidence missing: {transaction_id}")
        elif any(not re.fullmatch(r"[0-9a-f]{64}", str(review_evidence[key]))
                 for key in all_evidence.intersection(review_evidence)):
            errors.append(f"transaction review evidence invalid: {transaction_id}")
        if isinstance(review_evidence, dict):
            formal_keys = {"naturalization_review_sha256", "context_review_sha256"}
            if len(formal_keys.intersection(review_evidence)) == 1:
                errors.append(f"transaction formal review evidence incomplete: {transaction_id}")
        next_parent = chain[index + 1].get("transaction_id")
        if manifest.get("parent_transaction_id") != next_parent:
            errors.append(f"transaction parent mismatch: {transaction_id}")
        assets = manifest.get("assets")
        if not isinstance(assets, dict):
            errors.append(f"transaction assets invalid: {transaction_id}")
            continue
        transaction_dir = tx_manifest_path(project_root, transaction_id).parent
        for relative, asset_evidence in assets.items():
            if not isinstance(asset_evidence, dict):
                errors.append(f"transaction asset evidence invalid: {transaction_id}:{relative}")
                continue
            snapshot_raw = asset_evidence.get("snapshot_path", "")
            try:
                snapshot_relative, snapshot = project_relative_path(transaction_dir, snapshot_raw)
            except ValueError:
                errors.append(f"transaction asset snapshot path invalid: {transaction_id}:{relative}")
                continue
            if not snapshot_relative.startswith("assets/") or not snapshot.is_file():
                errors.append(f"transaction asset snapshot missing: {transaction_id}:{relative}")
            elif sha256_file(snapshot) != asset_evidence.get("sha256"):
                errors.append(f"transaction asset hash mismatch: {transaction_id}:{relative}")
        if isinstance(review_evidence, dict) and isinstance(assets, dict):
            expected_suffixes = {
                "naturalization_review_sha256": "reviews/naturalization.md",
                "context_review_sha256": "reviews/context.md",
                "state_validation_report_sha256": "reviews/state.md",
            }
            for evidence_key, suffix in expected_suffixes.items():
                if evidence_key not in review_evidence:
                    continue
                matches = [item for relative, item in assets.items() if relative.endswith(suffix)]
                if (len(matches) != 1 or not isinstance(matches[0], dict)
                        or matches[0].get("sha256") != review_evidence.get(evidence_key)):
                    errors.append(
                        f"transaction review evidence asset mismatch: {transaction_id}:{evidence_key}"
                    )
    if chain[-1].get("transaction_id") != "tx-genesis":
        errors.append("chain does not reach tx-genesis")
    if head.get("head_transaction_id") != "tx-genesis":
        first = chain[0]
        if head.get("parent_transaction_id") != first.get("parent_transaction_id"):
            errors.append("commit-head parent does not match head transaction")
        if head.get("generation_id") != first.get("generation_id"):
            errors.append("commit-head generation does not match head transaction")
    expected_chain_hash = sha256_text(
        ":".join(
            [project_id]
            + [item.get("manifest_sha256", "tx-genesis") for item in reversed(chain)]
        )
    )
    if head.get("chain_hash") and head.get("chain_hash") != expected_chain_hash:
        errors.append("commit-head chain_hash mismatch")
    return not errors, errors


def commit_head_cas(project_root: Path, new_head: dict, base_head_sha256: str) -> str:
    """CAS 提交：仅当当前 head 哈希等于 base_head_sha256 时原子替换。"""
    current = head_hash(project_root)
    if current != base_head_sha256:
        raise RuntimeError(
            f"compare-and-swap failed: current={current[:12]} base={base_head_sha256[:12]}"
        )
    old_head = read_head(project_root)
    if old_head is None:
        raise RuntimeError("commit head missing")
    if new_head.get("project_id") != old_head.get("project_id"):
        raise ValueError("new head project_id mismatch")
    new_transaction_id = new_head.get("head_transaction_id")
    old_transaction_id = old_head.get("head_transaction_id")
    if new_transaction_id != old_transaction_id:
        manifest = load_json(tx_manifest_path(project_root, new_transaction_id))
        if not manifest:
            raise ValueError(f"new head transaction missing: {new_transaction_id}")
        if manifest.get("project_id") != new_head.get("project_id"):
            raise ValueError("new head transaction project_id mismatch")
        if manifest.get("parent_transaction_id") != old_transaction_id:
            raise ValueError("new head transaction parent is not current head")
        if new_head.get("parent_transaction_id") != old_transaction_id:
            raise ValueError("new head parent_transaction_id is not current head")
        if new_head.get("generation_id") != manifest.get("generation_id"):
            raise ValueError("new head generation does not match transaction")
        chain = chain_parents(project_root, new_head)
        new_head["chain_hash"] = sha256_text(
            ":".join(
                [new_head["project_id"]]
                + [item.get("manifest_sha256", "tx-genesis") for item in reversed(chain)]
            )
        )
    else:
        new_head["chain_hash"] = old_head.get("chain_hash", new_head.get("chain_hash"))
    new_head["commit_hash"] = canonical_json_hash(new_head, ("commit_hash",))
    atomic_write_json(project_root / COMMIT_HEAD_PATH, new_head)
    return new_head["commit_hash"]


def materialize_transaction_assets(project_root: Path, transaction_id: str,
                                   relative_paths: list[str]) -> dict[str, str]:
    """Materialize selected immutable snapshots after their transaction becomes current head."""
    head = read_head(project_root)
    if not head or head.get("head_transaction_id") != transaction_id:
        raise ValueError("only the current head transaction may materialize projections")
    manifest = load_json(tx_manifest_path(project_root, transaction_id))
    if not manifest:
        raise FileNotFoundError(f"transaction missing: {transaction_id}")
    ok, errors = verify_chain(project_root, head.get("project_id", ""))
    if not ok:
        raise ValueError(f"cannot materialize invalid chain: {errors}")
    assets = manifest.get("assets", {})
    result = {}
    transaction_dir = tx_manifest_path(project_root, transaction_id).parent
    for raw in relative_paths:
        relative, target = project_relative_path(project_root, raw)
        evidence = assets.get(relative)
        if not evidence:
            raise ValueError(f"transaction does not own projection asset: {relative}")
        _, snapshot = project_relative_path(transaction_dir, evidence["snapshot_path"])
        if not snapshot.is_file() or sha256_file(snapshot) != evidence["sha256"]:
            raise ValueError(f"immutable projection asset invalid: {relative}")
        if not target.is_file() or sha256_file(target) != evidence["sha256"]:
            atomic_write_bytes(target, snapshot.read_bytes())
        result[relative] = evidence["sha256"]
    return result


def rebase_start(project_root: Path, *, project_id: str, base_head_transaction_id: str,
                 old_generation_id: str, new_generation_id: str,
                 base_head_sha256: str, rebase_id: str | None = None) -> dict:
    """提交 rebase_start 控制事务，把 operation_mode 设为 maintenance。

    同一次 head CAS 中保存 rebase_id、base_head_transaction_id、新旧代际和
    operation_mode: maintenance。commit head 中的 operation mode 是运行时权威，
    manifest 只是其物化镜像。
    """
    if rebase_id is None:
        rebase_id = f"rebase-{uuid_module.uuid4().hex[:12]}"
    current_head = read_head(project_root)
    if current_head is None:
        raise ValueError("rebase requires an existing commit head")
    if head_hash(project_root) != base_head_sha256:
        raise ValueError("commit head compare-and-swap failed")
    if current_head.get("operation_mode", "normal") != "normal":
        raise ValueError("rebase can only start from normal operation mode")
    if current_head.get("project_id") != project_id:
        raise ValueError("rebase project_id does not match current head")
    if current_head.get("head_transaction_id") != base_head_transaction_id:
        raise ValueError("rebase base transaction does not match current head")
    if current_head.get("generation_id") != old_generation_id:
        raise ValueError("rebase old generation does not match current head")
    if new_generation_id == old_generation_id:
        raise ValueError("rebase new generation must differ from old generation")
    rebase_parent = project_root / "修复记录" / "生产状态" / "rebases"
    rebase_parent.mkdir(parents=True, exist_ok=True)
    rebase_dir = rebase_parent / rebase_id
    rebase_dir.mkdir()
    manifest = {
        "rebase_id": rebase_id,
        "project_id": project_id,
        "base_head_transaction_id": base_head_transaction_id,
        "base_head_sha256": base_head_sha256,
        "old_generation_id": old_generation_id,
        "new_generation_id": new_generation_id,
        "operation_mode": "maintenance",
        "created_at": now_iso(),
    }
    # Prepare durable recovery evidence before the head enters maintenance.
    atomic_write_json(rebase_dir / "manifest.json", manifest)
    new_head = dict(current_head)
    new_head.update({
        "project_id": project_id,
        "rebase_id": rebase_id,
        "base_head_transaction_id": base_head_transaction_id,
        "old_generation_id": old_generation_id,
        "new_generation_id": new_generation_id,
        "generation_id": new_generation_id,
        "operation_mode": "maintenance",
    })
    commit_head_cas(project_root, new_head, base_head_sha256)
    return manifest


def rebase_abort(project_root: Path, *, project_id: str, base_head_sha256: str,
                 head_transaction_id: str, generation_id: str) -> dict:
    """提交 rebase_abort 控制事务，把 head 切回旧 generation 并恢复 normal。"""
    new_head = dict(read_head(project_root) or genesis_head(project_id))
    new_head.update({
        "project_id": project_id,
        "head_transaction_id": head_transaction_id,
        "generation_id": generation_id,
        "operation_mode": "normal",
        "rebase_id": None,
    })
    commit_head_cas(project_root, new_head, base_head_sha256)
    return new_head


def rebase_complete(project_root: Path, *, project_id: str, base_head_sha256: str,
                    head_transaction_id: str, generation_id: str,
                    projection_hashes: dict | None = None,
                    committed_node_id: str | None = None) -> dict:
    """rebase 全部后继节点验证通过后，原子切回 normal。"""
    current_head = read_head(project_root)
    if current_head is None or head_hash(project_root) != base_head_sha256:
        raise RuntimeError("rebase completion compare-and-swap failed")
    if current_head.get("project_id") != project_id:
        raise ValueError("rebase completion project_id mismatch")
    if current_head.get("operation_mode") != "maintenance":
        raise ValueError("rebase completion requires maintenance mode")
    if current_head.get("new_generation_id") != generation_id:
        raise ValueError("rebase completion generation mismatch")
    target = load_json(tx_manifest_path(project_root, head_transaction_id))
    if not target or target.get("generation_id") != generation_id:
        raise ValueError("rebase target transaction missing or generation mismatch")
    new_head = dict(current_head)
    new_head.update({
        "project_id": project_id,
        "head_transaction_id": head_transaction_id,
        "parent_transaction_id": target.get("parent_transaction_id"),
        "generation_id": generation_id,
        "operation_mode": "normal",
        "rebase_id": None,
    })
    if projection_hashes is not None:
        new_head["projection_hashes"] = dict(projection_hashes)
    if committed_node_id is not None:
        new_head["committed_node_id"] = committed_node_id
    chain = chain_parents(project_root, new_head)
    base_transaction_id = current_head.get("base_head_transaction_id")
    if base_transaction_id not in {item.get("transaction_id") for item in chain}:
        raise ValueError("shadow chain does not descend from rebase base transaction")
    new_head["chain_hash"] = sha256_text(
        ":".join(
            [project_id]
            + [item.get("manifest_sha256", "tx-genesis") for item in reversed(chain)]
        )
    )
    new_head.pop("base_head_transaction_id", None)
    new_head.pop("old_generation_id", None)
    new_head.pop("new_generation_id", None)
    new_head["commit_hash"] = canonical_json_hash(new_head, ("commit_hash",))
    if head_hash(project_root) != base_head_sha256:
        raise RuntimeError("rebase completion compare-and-swap failed")
    atomic_write_json(project_root / COMMIT_HEAD_PATH, new_head)
    return new_head


def plan_activation(project_root: Path, *, project_id: str, base_head_sha256: str,
                    head_transaction_id: str, generation_id: str,
                    current_window: str, next_window: str,
                    current_plot_path: str | None, next_plot_path: str | None,
                    current_system_path: str | None, next_system_path: str | None) -> dict:
    """双窗口协议：当前窗口最后一个 main 节点 committed 后切换窗口。"""
    new_head = dict(read_head(project_root) or genesis_head(project_id))
    new_head.update({
        "project_id": project_id,
        "head_transaction_id": head_transaction_id,
        "generation_id": generation_id,
        "operation_mode": "normal",
        "current_window": current_window,
        "next_window": next_window,
        "current_plot_path": current_plot_path,
        "next_plot_path": next_plot_path,
        "current_system_path": current_system_path,
        "next_system_path": next_system_path,
    })
    commit_head_cas(project_root, new_head, base_head_sha256)
    return new_head
