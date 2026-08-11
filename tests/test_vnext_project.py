import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sys as _sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import 项目事务 as tx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
MISSING_REPO = FIXTURES / "project_missing_system_repo"
HEALTHY = FIXTURES / "project_healthy"

PROJECT_ID = "a1b2c3d4-0000-4000-8000-000000000001"
def create_asset(root: Path, relative: str = "正文/x.md", text: str = "正文"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return relative, tx.sha256_file(path)


def prepare(root: Path, *, transaction_id=None, parent="tx-genesis", project_id=PROJECT_ID,
            node_id="chapter-0001", attempt_id="attempt-0001", asset=True):
    assets = {}
    if asset:
        relative, digest = create_asset(root, f"workspace/{node_id}.md", node_id)
        assets[relative] = digest
    review_evidence = {}
    for key, name in [
        ("naturalization_review_sha256", "naturalization.md"),
        ("context_review_sha256", "context.md"),
        ("state_validation_report_sha256", "state.md"),
    ]:
        relative, digest = create_asset(
            root, f"attempts/{node_id}/reviews/{name}", f"{node_id}:{name}"
        )
        assets[relative] = digest
        review_evidence[key] = digest
    return tx.prepare_transaction(
        root, project_id=project_id, parent_transaction_id=parent,
        generation_id="gen-0001", base_head_sha256=tx.head_hash(root),
        node_id=node_id, attempt_id=attempt_id, assets=assets,
        review_evidence=review_evidence, transaction_id=transaction_id,
    )


class TestManifestParsing(unittest.TestCase):
    def test_parses_v3_manifest(self):
        core, authority = tx.parse_manifest(MISSING_REPO)
        self.assertEqual(core["schema_version"], "3")
        self.assertEqual(core["project_status"], "正文中")
        self.assertEqual(core["目标章数下限"], "1000")
        self.assertEqual(authority["系统状态"], "总结/系统状态仓库.md")

    def test_validate_manifest_ok_for_fixture(self):
        ok, errors = tx.validate_manifest(MISSING_REPO)
        self.assertTrue(ok, errors)

    def test_validate_manifest_rejects_bad_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "novel-config.md").write_text(
                "# 项目清单\n- schema_version：99\n- project_status：完结\n",
                encoding="utf-8",
            )
            ok, errors = tx.validate_manifest(root)
            self.assertFalse(ok)
            self.assertTrue(any("schema_version" in e for e in errors))

    def test_validate_manifest_rejects_invalid_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "novel-config.md").write_text(
                "# 项目清单\n- schema_version：3\n- project_id：not-a-uuid\n",
                encoding="utf-8",
            )
            ok, errors = tx.validate_manifest(root)
            self.assertFalse(ok)
            self.assertTrue(any("project_id" in e for e in errors))

    def test_validate_manifest_rejects_non_v4_and_noncanonical_uuid(self):
        config = (HEALTHY / "novel-config.md").read_text(encoding="utf-8")
        for bad in ["A1B2C3D4-0000-4000-8000-000000000002",
                    "a1b2c3d4-0000-1000-8000-000000000002"]:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                root.joinpath("novel-config.md").write_text(
                    config.replace("a1b2c3d4-0000-4000-8000-000000000002", bad),
                    encoding="utf-8",
                )
                ok, errors = tx.validate_manifest(root)
                self.assertFalse(ok)
                self.assertTrue(any("UUID v4" in error for error in errors))

    def test_authority_path_cannot_escape_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "novel-config.md").write_text(
                "# 项目清单\n- schema_version：3\n"
                "## 权威路径\n- 开书方案：../../etc/passwd\n",
                encoding="utf-8",
            )
            ok, errors = tx.validate_manifest(root)
            self.assertFalse(ok)
            self.assertTrue(any("escapes" in e for e in errors))


class TestWriteLock(unittest.TestCase):
    def make_project(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)
        return root

    def test_acquire_and_release(self):
        root = self.make_project()
        lock = tx.WriteLock(root)
        lock_id = lock.acquire(PROJECT_ID, "owner-1")
        self.assertTrue(lock.is_active(lock_id))
        lock.release(lock_id)
        self.assertIsNone(lock.read())

    def test_second_acquire_blocks_while_locked(self):
        root = self.make_project()
        lock = tx.WriteLock(root)
        lock.acquire(PROJECT_ID, "owner-1", lease_seconds=600)
        with self.assertRaises(FileExistsError):
            tx.WriteLock(root).acquire(PROJECT_ID, "owner-2", lease_seconds=600)

    def test_token_mismatch_release_fails(self):
        root = self.make_project()
        lock = tx.WriteLock(root)
        lock_id = lock.acquire(PROJECT_ID, "owner-1", lease_seconds=600)
        with self.assertRaises(PermissionError):
            lock.release("wrong-token")

    def test_expired_lock_recovery(self):
        root = self.make_project()
        lock = tx.WriteLock(root)
        # 已过期：直接写一个过期锁文件
        stale = {
            "lock_id": "stale-1", "project_id": PROJECT_ID, "owner_id": "dead",
            "operation": "normal", "base_head_sha256": "",
            "acquired_at": "2020-01-01T00:00:00+00:00",
            "heartbeat_at": "2020-01-01T00:00:00+00:00",
            "lease_until": "2020-01-01T01:00:00+00:00",
        }
        tx.atomic_write_json(root / tx.LOCK_PATH, stale)
        stale_dir = root / "修复记录" / "生产状态" / "locks"
        new_id = lock.recover_stale(stale_dir, lease_seconds=600)
        self.assertIsNotNone(new_id)
        self.assertTrue((stale_dir / "stale-lock-stale-1.json").is_file())
        self.assertTrue(lock.is_active(new_id))

    def test_non_expired_lock_recovery_refuses(self):
        root = self.make_project()
        lock = tx.WriteLock(root)
        lock_id = lock.acquire(PROJECT_ID, "owner-1", lease_seconds=600)
        stale_dir = root / "locks"
        with self.assertRaises(PermissionError):
            lock.recover_stale(stale_dir, lease_seconds=600)


class TestGenesisAndChain(unittest.TestCase):
    def make_project(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        self.addCleanup(tmp.cleanup)
        return root

    def test_create_genesis_and_read_head(self):
        root = self.make_project()
        head = tx.create_genesis(root, PROJECT_ID)
        self.assertEqual(head["head_transaction_id"], "tx-genesis")
        self.assertEqual(tx.read_head(root)["project_id"], PROJECT_ID)

    def test_prepare_transaction_creates_immutable_manifest(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        manifest = prepare(root)
        txid = manifest["transaction_id"]
        path = tx.tx_manifest_path(root, txid)
        self.assertTrue(path.is_file())
        self.assertEqual(tx.load_json(path)["transaction_id"], txid)
        self.assertIn("manifest_sha256", manifest)
        evidence = next(iter(manifest["assets"].values()))
        self.assertTrue((path.parent / evidence["snapshot_path"]).is_file())

    def test_duplicate_transaction_id_is_rejected_without_overwrite(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        first = prepare(root, transaction_id="tx-fixed")
        before = tx.sha256_file(tx.tx_manifest_path(root, "tx-fixed"))
        with self.assertRaises(FileExistsError):
            prepare(root, transaction_id="tx-fixed", node_id="chapter-0002")
        self.assertEqual(before, tx.sha256_file(tx.tx_manifest_path(root, "tx-fixed")))
        self.assertEqual(first, tx.load_json(tx.tx_manifest_path(root, "tx-fixed")))

    def test_review_evidence_must_be_backed_by_frozen_assets(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        with self.assertRaises(ValueError):
            tx.prepare_transaction(
                root, project_id=PROJECT_ID, parent_transaction_id="tx-genesis",
                generation_id="gen-0001", base_head_sha256=tx.head_hash(root),
                node_id="chapter-0001", attempt_id="attempt-0001", assets={},
                review_evidence={
                    "naturalization_review_sha256": "1" * 64,
                    "context_review_sha256": "2" * 64,
                    "state_validation_report_sha256": "3" * 64,
                },
            )

    def test_current_transaction_asset_can_materialize_projection(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        manifest = prepare(root)
        head = tx.read_head(root)
        head.update({
            "head_transaction_id": manifest["transaction_id"],
            "parent_transaction_id": "tx-genesis",
        })
        tx.commit_head_cas(root, head, tx.head_hash(root))
        target = root / "workspace" / "chapter-0001.md"
        target.write_text("changed projection", encoding="utf-8")
        result = tx.materialize_transaction_assets(
            root, manifest["transaction_id"], ["workspace/chapter-0001.md"]
        )
        self.assertEqual(target.read_text(encoding="utf-8"), "chapter-0001")
        self.assertEqual(result["workspace/chapter-0001.md"], tx.sha256_file(target))

    def test_chain_walks_back_to_genesis(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        base = tx.head_hash(root)
        m1 = prepare(root, asset=False)
        head = tx.read_head(root)
        head["head_transaction_id"] = m1["transaction_id"]
        head["parent_transaction_id"] = "tx-genesis"
        tx.commit_head_cas(root, head, base)
        chain = tx.chain_parents(root)
        self.assertEqual([c["transaction_id"] for c in chain],
                         [m1["transaction_id"], "tx-genesis"])

    def test_verify_chain_detects_missing_transaction(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        head = tx.read_head(root)
        head["head_transaction_id"] = "tx-missing-1"
        head["parent_transaction_id"] = "tx-genesis"
        tx.atomic_write_json(root / tx.COMMIT_HEAD_PATH, head)
        ok, errors = tx.verify_chain(root, PROJECT_ID)
        self.assertFalse(ok)
        self.assertTrue(any("missing" in e for e in errors))

    def test_commit_head_cas(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        base = tx.head_hash(root)
        manifest = prepare(root, asset=False)
        new_head = dict(tx.read_head(root))
        new_head["committed_node_id"] = "chapter-0001"
        new_head["head_transaction_id"] = manifest["transaction_id"]
        new_head["parent_transaction_id"] = "tx-genesis"
        tx.commit_head_cas(root, new_head, base)
        self.assertEqual(tx.read_head(root)["committed_node_id"], "chapter-0001")

    def test_commit_head_cas_race_fails(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        # base 过期（已有其他提交改变了 head）
        base = "deadbeef" * 8
        with self.assertRaises(RuntimeError):
            tx.commit_head_cas(root, dict(tx.read_head(root)), base)

    def test_chain_cycle_and_early_null_fail(self):
        for mode in ("cycle", "null"):
            with self.subTest(mode=mode):
                root = self.make_project()
                tx.create_genesis(root, PROJECT_ID)
                manifest = prepare(root, transaction_id=f"tx-{mode}", asset=False)
                path = tx.tx_manifest_path(root, manifest["transaction_id"])
                broken = tx.load_json(path)
                broken["parent_transaction_id"] = manifest["transaction_id"] if mode == "cycle" else None
                broken["manifest_sha256"] = tx.canonical_json_hash(broken, ("manifest_sha256",))
                tx.atomic_write_json(path, broken)
                head = tx.read_head(root)
                head.update({
                    "head_transaction_id": manifest["transaction_id"],
                    "parent_transaction_id": broken["parent_transaction_id"],
                })
                head["commit_hash"] = tx.canonical_json_hash(head, ("commit_hash",))
                tx.atomic_write_json(root / tx.COMMIT_HEAD_PATH, head)
                ok, errors = tx.verify_chain(root, PROJECT_ID)
                self.assertFalse(ok)
                self.assertTrue(any("cycle" in error or "null" in error for error in errors))

    def test_chain_rejects_project_manifest_and_asset_tampering(self):
        for mode in ("project", "manifest", "asset"):
            with self.subTest(mode=mode):
                root = self.make_project()
                tx.create_genesis(root, PROJECT_ID)
                manifest = prepare(root)
                head = tx.read_head(root)
                head.update({
                    "head_transaction_id": manifest["transaction_id"],
                    "parent_transaction_id": "tx-genesis",
                })
                tx.commit_head_cas(root, head, tx.head_hash(root))
                path = tx.tx_manifest_path(root, manifest["transaction_id"])
                if mode == "asset":
                    evidence = next(iter(manifest["assets"].values()))
                    (path.parent / evidence["snapshot_path"]).write_text("tampered", encoding="utf-8")
                else:
                    broken = tx.load_json(path)
                    if mode == "project":
                        broken["project_id"] = "a1b2c3d4-0000-4000-8000-000000000099"
                        broken["manifest_sha256"] = tx.canonical_json_hash(broken, ("manifest_sha256",))
                    else:
                        broken["node_id"] = "chapter-9999"
                    tx.atomic_write_json(path, broken)
                ok, _ = tx.verify_chain(root, PROJECT_ID)
                self.assertFalse(ok)

    def test_rebase_start_sets_maintenance_mode(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        base = tx.head_hash(root)
        manifest = tx.rebase_start(
            root,
            project_id=PROJECT_ID,
            base_head_transaction_id="tx-genesis",
            old_generation_id="gen-0001",
            new_generation_id="gen-0002",
            base_head_sha256=base,
        )
        head = tx.read_head(root)
        self.assertEqual(head["operation_mode"], "maintenance")
        self.assertEqual(head["generation_id"], "gen-0002")
        self.assertEqual(head["rebase_id"], manifest["rebase_id"])
        self.assertTrue((root / "修复记录" / "生产状态" / "rebases" / manifest["rebase_id"] / "manifest.json").is_file())

    def test_rebase_abort_restores_normal_mode(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        base = tx.head_hash(root)
        tx.rebase_start(root, project_id=PROJECT_ID,
                        base_head_transaction_id="tx-genesis",
                        old_generation_id="gen-0001",
                        new_generation_id="gen-0002",
                        base_head_sha256=base)
        head = tx.read_head(root)
        tx.rebase_abort(root, project_id=PROJECT_ID,
                        base_head_sha256=tx.head_hash(root),
                        head_transaction_id="tx-genesis",
                        generation_id="gen-0001")
        head = tx.read_head(root)
        self.assertEqual(head["operation_mode"], "normal")
        self.assertEqual(head["generation_id"], "gen-0001")

    def test_plan_activation_switches_window(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        base = tx.head_hash(root)
        tx.plan_activation(
            root, project_id=PROJECT_ID, base_head_sha256=base,
            head_transaction_id="tx-genesis", generation_id="gen-0001",
            current_window="第51-100章", next_window=None,
            current_plot_path="plan/大纲_第51-100章.md", next_plot_path=None,
            current_system_path="plan/系统发展_第51-100章.md", next_system_path=None,
        )
        head = tx.read_head(root)
        self.assertEqual(head["current_window"], "第51-100章")
        self.assertIsNone(head["next_window"])


class TestValidateProjectScript(unittest.TestCase):
    def run_validator(self, project_root, expect_fail=False):
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_project.py"),
             "--project-root", str(project_root), "--json"],
            cwd=str(ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 1 if expect_fail else 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_missing_system_repo_fixture_fails_only_on_system_repo(self):
        report = self.run_validator(MISSING_REPO, expect_fail=True)
        self.assertFalse(report["ok"])
        authority = report["checks"]["authority"]
        self.assertFalse(authority["ok"])
        self.assertTrue(any("系统状态" in e for e in authority["errors"]))
        # 其他检查通过
        self.assertTrue(report["checks"]["manifest"]["ok"])
        self.assertTrue(report["checks"]["plan"]["ok"])
        self.assertTrue(report["checks"]["anchor"]["ok"])
        self.assertTrue(report["checks"]["chain"]["ok"])

    def test_healthy_fixture_passes(self):
        report = self.run_validator(HEALTHY)
        self.assertTrue(report["ok"], report)

    def test_plan_stage_and_node_schema_are_enforced(self):
        for relative, marker, check in [
            ("plan/总大纲.md", "MYNOVEL:STAGE:stage-0002:START", "stage"),
            ("plan/大纲_第1-50章.md", "MYNOVEL:PLAN-NODE:chapter-0002:START", "plan_schema"),
        ]:
            with self.subTest(check=check), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "project"
                __import__("shutil").copytree(HEALTHY, root)
                path = root / relative
                path.write_text(path.read_text(encoding="utf-8").replace(marker, marker + "-broken", 1),
                                encoding="utf-8")
                report = self.run_validator(root, expect_fail=True)
                self.assertFalse(report["checks"][check]["ok"])

    def test_uncommitted_body_and_transaction_pollution_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            __import__("shutil").copytree(HEALTHY, root)
            body = root / "正文" / "第1章.md"
            body.parent.mkdir()
            body.write_text("未提交正文", encoding="utf-8")
            orphan = root / tx.TRANSACTIONS_DIR / "tx-orphan"
            orphan.mkdir(parents=True)
            report = self.run_validator(root, expect_fail=True)
            errors = report["checks"]["projection"]["errors"]
            self.assertTrue(any("uncommitted body" in error for error in errors))
            self.assertTrue(any("uncommitted transaction" in error for error in errors))

    def test_invalid_manifest_returns_structured_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "novel-config.md").write_text(
                "# 项目清单\n- schema_version：99\n- project_status：unknown\n",
                encoding="utf-8",
            )
            report = self.run_validator(root, expect_fail=True)
            self.assertFalse(report["checks"]["manifest"]["ok"])
            self.assertFalse(report["checks"]["authority"]["ok"])

    def test_stale_runtime_state_in_plan_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plan").mkdir(parents=True)
            (root / "plan" / "大纲_第1-50章.md").write_text(
                "## 当前进度\n- 已发布章节：第1-3章\n", encoding="utf-8"
            )
            # 用健康项目补齐 manifest，但检测旧 plan
            config = (HEALTHY / "novel-config.md").read_text(encoding="utf-8")
            (root / "novel-config.md").write_text(config, encoding="utf-8")
            report = self.run_validator(root, expect_fail=True)
            self.assertFalse(report["checks"]["plan"]["ok"])

    def test_unpaired_anchor_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "plan").mkdir(parents=True)
            (root / "plan" / "大纲.md").write_text(
                "<!-- MYNOVEL:CHAPTER:chapter-0001:START -->\n- node_id: chapter-0001\n",
                encoding="utf-8",
            )
            config = (HEALTHY / "novel-config.md").read_text(encoding="utf-8")
            (root / "novel-config.md").write_text(config, encoding="utf-8")
            report = self.run_validator(root, expect_fail=True)
            self.assertFalse(report["checks"]["anchor"]["ok"])


if __name__ == "__main__":
    unittest.main()
