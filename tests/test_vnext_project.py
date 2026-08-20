import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sys as _sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import 项目事务 as tx
import validate_project as project_validator


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
            node_id="chapter-0001", attempt_id="attempt-0001", asset=True,
            review_status="review_passed"):
    assets = {}
    if asset:
        relative, digest = create_asset(root, f"workspace/{node_id}.md", node_id)
        assets[relative] = digest
    review_evidence = {}
    evidence_files = [("state_validation_report_sha256", "state.md")]
    if review_status == "review_passed":
        evidence_files[:0] = [
            ("naturalization_review_sha256", "naturalization.md"),
            ("context_review_sha256", "context.md"),
        ]
    for key, name in evidence_files:
        relative, digest = create_asset(
            root, f"attempts/{node_id}/reviews/{name}", f"{node_id}:{name}"
        )
        assets[relative] = digest
        review_evidence[key] = digest
    return tx.prepare_transaction(
        root, project_id=project_id, parent_transaction_id=parent,
        generation_id="gen-0001", base_head_sha256=tx.head_hash(root),
        node_id=node_id, attempt_id=attempt_id, assets=assets,
        review_evidence=review_evidence, review_status=review_status,
        transaction_id=transaction_id,
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

    def test_pending_review_transaction_only_requires_state_evidence(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        manifest = prepare(root, review_status="review_pending")
        self.assertEqual(manifest["review_status"], "review_pending")
        self.assertEqual(set(manifest["review_evidence"]), {"state_validation_report_sha256"})
        head = tx.read_head(root)
        head.update({
            "head_transaction_id": manifest["transaction_id"],
            "parent_transaction_id": "tx-genesis",
        })
        tx.commit_head_cas(root, head, tx.head_hash(root))
        ok, errors = tx.verify_chain(root, PROJECT_ID)
        self.assertTrue(ok, errors)

    def test_body_filename_must_match_review_status(self):
        root = self.make_project()
        tx.create_genesis(root, PROJECT_ID)
        relative, digest = create_asset(root, "正文/第001章_测试.md", "正文")
        state_path, state_hash = create_asset(
            root, "attempts/chapter-0001/reviews/state.md", "state pass"
        )
        with self.assertRaisesRegex(ValueError, "must keep the （草稿） suffix"):
            tx.prepare_transaction(
                root,
                project_id=PROJECT_ID,
                parent_transaction_id="tx-genesis",
                generation_id="gen-0001",
                base_head_sha256=tx.head_hash(root),
                node_id="chapter-0001",
                attempt_id="attempt-0001",
                assets={relative: digest, state_path: state_hash},
                review_status="review_pending",
                review_evidence={"state_validation_report_sha256": state_hash},
            )

        draft_relative, draft_digest = create_asset(
            root, "正文/第001章_测试（草稿）.md", "正文"
        )
        natural_path, natural_hash = create_asset(
            root, "attempts/chapter-0001/reviews/naturalization.md", "natural pass"
        )
        context_path, context_hash = create_asset(
            root, "attempts/chapter-0001/reviews/context.md", "context pass"
        )
        with self.assertRaisesRegex(ValueError, "must not keep the （草稿） suffix"):
            tx.prepare_transaction(
                root,
                project_id=PROJECT_ID,
                parent_transaction_id="tx-genesis",
                generation_id="gen-0001",
                base_head_sha256=tx.head_hash(root),
                node_id="chapter-0001",
                attempt_id="attempt-0002",
                assets={
                    draft_relative: draft_digest,
                    state_path: state_hash,
                    natural_path: natural_hash,
                    context_path: context_hash,
                },
                review_status="review_passed",
                review_evidence={
                    "state_validation_report_sha256": state_hash,
                    "naturalization_review_sha256": natural_hash,
                    "context_review_sha256": context_hash,
                },
            )

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

    def make_window_contract_project(self, *, early_exit=False, empty_reserve=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "plan").mkdir(parents=True)
        (root / "plan" / "系统发展_第1-50章.md").write_text("# 系统发展\n", encoding="utf-8")
        reserve = "[]" if empty_reserve else "第51-100章完成阶段收束"
        first_exit = "true" if early_exit else "false"
        budget_rows = "\n".join(
            f"| 第{start}-{start + 4}章 | 推进第{start}章经营矛盾 | "
            f"结算本组资源投入 | 不完成阶段退出条件 | 保留后续对手压力 |"
            for start in range(1, 51, 5)
        )
        outline = f"""# 总大纲

<!-- MYNOVEL:STAGE:stage-0001:START -->
- stage_id: stage-0001
- chapter_start: 1
- chapter_end: 100
- stage_status: active
- exit_condition: 第100章完成阶段退出
<!-- MYNOVEL:STAGE:stage-0001:END -->

## 规划窗口合同

<!-- MYNOVEL:WINDOW:window-0001-0050:START -->
- window_id: window-0001-0050
- stage_id: stage-0001
- chapter_start: 1
- chapter_end: 50
- window_status: prepared
- stage_exit_allowed: {first_exit}
- system_plan: plan/系统发展_第1-50章.md
- must_complete: 建立初步经营闭环
- advance_only: 推进阶段主矛盾但不完成
- protagonist_progress_cap: 完成初步经营者身份但不成为区域领袖
- system_progress_cap: 开放基础经营权限但不解锁阶段终极模块
- forbidden_early_completion: 禁止完成阶段退出条件
- reserved_for_later: {reserve}
- end_unresolved: 核心对手仍在且资源债未结
- next_stage_forbidden: 禁止进入下一地图
- next_window_id: window-0051-0100
- five_chapter_budget_status: locked

## 五章剧情预算
| 五章组 | 本组职责 | 允许结算 | 禁止越过 | 必须留给后组 |
|---|---|---|---|---|
{budget_rows}
<!-- MYNOVEL:WINDOW:window-0001-0050:END -->

<!-- MYNOVEL:WINDOW:window-0051-0100:START -->
- window_id: window-0051-0100
- stage_id: stage-0001
- chapter_start: 51
- chapter_end: 100
- window_status: reserved
- stage_exit_allowed: true
- system_plan: null
- must_complete: 完成阶段退出条件
- advance_only: []
- protagonist_progress_cap: 完成阶段身份跃迁
- system_progress_cap: 完成本阶段系统结算
- forbidden_early_completion: 禁止进入下一宏观阶段核心事件
- reserved_for_later: []
- end_unresolved: 保留下一阶段入口压力
- next_stage_forbidden: 禁止提前解决下一阶段对手
- next_window_id: null
- five_chapter_budget_status: pending
<!-- MYNOVEL:WINDOW:window-0051-0100:END -->
"""
        (root / "plan" / "总大纲.md").write_text(outline, encoding="utf-8")
        core = {
            "规划窗口协议版本": "1",
            "当前计划窗口": "第1-50章",
            "当前窗口合同": "window-0001-0050",
            "当前剧情预算锁": "locked",
            "下一计划窗口": "null",
            "下一窗口合同": "null",
            "下一剧情预算锁": "null",
        }
        authority = {
            "总大纲": "plan/总大纲.md",
            "当前系统计划": "plan/系统发展_第1-50章.md",
            "下一系统计划": "null",
        }
        return root, core, authority

    def test_window_contract_protocol_accepts_full_stage_budget(self):
        root, core, authority = self.make_window_contract_project()
        ok, errors = project_validator.check_window_contracts(root, core, authority)
        self.assertTrue(ok, errors)

    def test_window_contract_protocol_rejects_early_stage_exit(self):
        root, core, authority = self.make_window_contract_project(early_exit=True)
        ok, errors = project_validator.check_window_contracts(root, core, authority)
        self.assertFalse(ok)
        self.assertTrue(any("stage_exit_allowed" in error for error in errors), errors)

    def test_window_contract_protocol_rejects_empty_future_reserve(self):
        root, core, authority = self.make_window_contract_project(empty_reserve=True)
        ok, errors = project_validator.check_window_contracts(root, core, authority)
        self.assertFalse(ok)
        self.assertTrue(any("reserved_for_later" in error for error in errors), errors)

    def test_window_contract_protocol_rejects_incomplete_five_chapter_budget(self):
        root, core, authority = self.make_window_contract_project()
        outline = root / "plan" / "总大纲.md"
        text = outline.read_text(encoding="utf-8")
        outline.write_text(
            text.replace(
                "| 第46-50章 | 推进第46章经营矛盾 | 结算本组资源投入 | "
                "不完成阶段退出条件 | 保留后续对手压力 |\n",
                "",
                1,
            ),
            encoding="utf-8",
        )
        ok, errors = project_validator.check_window_contracts(root, core, authority)
        self.assertFalse(ok)
        self.assertTrue(any("budget coverage mismatch" in error for error in errors), errors)

    def test_window_contract_protocol_rejects_empty_or_placeholder_budget_cells(self):
        for replacement in ("", "...", "本组职责"):
            with self.subTest(replacement=replacement):
                root, core, authority = self.make_window_contract_project()
                outline = root / "plan" / "总大纲.md"
                text = outline.read_text(encoding="utf-8")
                outline.write_text(
                    text.replace("推进第1章经营矛盾", replacement, 1),
                    encoding="utf-8",
                )
                ok, errors = project_validator.check_window_contracts(root, core, authority)
                self.assertFalse(ok)
                self.assertTrue(any("budget cell" in error for error in errors), errors)

    def test_window_contract_protocol_rejects_manifest_system_plan_mismatch(self):
        root, core, authority = self.make_window_contract_project()
        authority["当前系统计划"] = "plan/系统发展_第51-100章.md"
        ok, errors = project_validator.check_window_contracts(root, core, authority)
        self.assertFalse(ok)
        self.assertTrue(any("系统计划路径与窗口合同不一致" in error for error in errors), errors)

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
