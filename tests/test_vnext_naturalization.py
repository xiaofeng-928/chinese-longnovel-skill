import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import validate_chapter_candidate as vcc


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
ATTEMPT_OK = FIXTURES / "attempt_ok"
ATTEMPT_BROKEN = FIXTURES / "attempt_broken"


def write_reviews(attempt: Path, *, working_copy: bool = False):
    source_hash = vcc.sha256_file(attempt / "workspace" / "source.md")
    candidate_hash = vcc.sha256_file(attempt / "candidate.md")
    lock_hash = vcc.sha256_file(attempt / "fact-lock.json")
    dimensions = "\n".join(f"| {name} | pass | evidence |" for name in vcc.REVIEW_DIMENSIONS)
    subject_frontmatter = ""
    if working_copy:
        subject_frontmatter = (
            "review_subject: working_copy\n"
            f"base_committed_sha256: {source_hash}\n"
            f"working_copy_sha256: {candidate_hash}\n"
        )
    for kind, reviewer in (("naturalization", "reviewer-naturalization"),
                           ("context", "reviewer-context")):
        path = attempt / "reviews" / f"{kind}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"review_id: review-{kind}\nreviewer_id: {reviewer}\n"
            "node_id: chapter-0001\nattempt_id: attempt-0001\n"
            f"review_kind: {kind}\nsource_sha256: {source_hash}\n"
            f"reviewed_sha256: {candidate_hash}\nfact_lock_sha256: {lock_hash}\n"
            f"{subject_frontmatter}"
            "review_prompt_version: review-v3.0\n"
            "reviewed_at: 2026-08-11T10:00:00+00:00\ntotal_result: pass\n---\n"
            "| dimension | result | evidence |\n|---|---|---|\n" + dimensions + "\n",
            encoding="utf-8",
        )


def write_state_evidence(attempt: Path):
    candidate = attempt / "candidate.md"
    final_body = attempt / "workspace" / "final_body.md"
    final_body.write_bytes(candidate.read_bytes())
    anchor = "生存点余额：1000"
    deltas = [{
        "delta_id": "delta-0001", "field": "生存点余额", "old_value": "900",
        "new_value": "1000", "source_anchor": anchor,
        "source_excerpt_sha256": vcc.sha256_text(anchor), "fact_lock_ids": ["fl-0001"],
    }]
    delta_path = attempt / "deltas" / "state.json"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(json.dumps(deltas, ensure_ascii=False), encoding="utf-8")
    review = attempt / "reviews" / "state.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review.write_text(
        "---\nnode_id: chapter-0001\nattempt_id: attempt-0001\n"
        f"reviewed_sha256: {vcc.sha256_file(candidate)}\n"
        f"state_delta_sha256: {vcc.sha256_file(delta_path)}\n"
        "review_prompt_version: state-v3.0\nreviewed_at: 2026-08-11T10:01:00+00:00\n"
        "total_result: pass\n---\n# 状态回证\n",
        encoding="utf-8",
    )


def make_working_copy_attempt(root: Path, *, balance: int = 1000) -> Path:
    attempt = root / "attempt"
    shutil.copytree(ATTEMPT_OK, attempt)
    base_hash = vcc.sha256_file(attempt / "workspace" / "source.md")
    candidate_text = (
        "# 第1章 风起\n\n"
        "雪压在车窗上，他仍旧坐着。"
        f"生存点余额：{balance}。\n"
    )
    working_path = root / "正文" / "第001章_风起（草稿）.md"
    working_path.parent.mkdir(parents=True)
    working_path.write_text(candidate_text, encoding="utf-8")
    (attempt / "candidate.md").write_text(candidate_text, encoding="utf-8")
    candidate_hash = vcc.sha256_file(attempt / "candidate.md")
    (attempt / "naturalization.md").write_text(
        "---\n"
        "node_id: chapter-0001\n"
        "attempt_id: attempt-0001\n"
        f"source_sha256: {base_hash}\n"
        f"candidate_sha256: {candidate_hash}\n"
        "prompt_version: repair-v1.0\n"
        "processed_at: 2026-08-16T10:00:00+00:00\n"
        "naturalization_result: repaired\n"
        "review_subject: working_copy\n"
        f"base_committed_sha256: {base_hash}\n"
        f"working_copy_sha256: {candidate_hash}\n"
        f"working_copy_path: {working_path.as_posix()}\n"
        "---\n# 工作副本记录\n",
        encoding="utf-8",
    )
    current_anchor = f"生存点余额：{balance}"
    locks = json.loads((attempt / "fact-lock.json").read_text(encoding="utf-8"))
    locks[0]["source_path"] = working_path.as_posix()
    locks[0]["working_copy_anchor"] = current_anchor
    locks[0]["working_copy_anchor_sha256"] = vcc.sha256_text(current_anchor)
    (attempt / "fact-lock.json").write_text(
        json.dumps(locks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (attempt / "state.json").write_text(
        json.dumps({
            "status": "review_pending",
            "node_id": "chapter-0001",
            "attempt_id": "attempt-0001",
        }),
        encoding="utf-8",
    )
    return attempt


class TestValidateChapterCandidate(unittest.TestCase):
    def test_working_copy_expression_rewrite_allows_hash_drift_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = make_working_copy_attempt(Path(tmp))
            strict_report = vcc.check_attempt(attempt)
            self.assertFalse(strict_report["checks"]["review_subject"]["ok"])

            report = vcc.check_attempt(attempt, allow_working_copy=True)
            self.assertFalse(report["ok"], report)
            self.assertFalse(report["eligible_for_review_passed"])
            self.assertTrue(report["checks"]["fact_lock"]["warnings"])
            self.assertTrue(report["checks"]["differences"]["warnings"])
            self.assertTrue(any(
                "requires --require-reviews" in error
                for error in report["checks"]["review_subject"]["errors"]
            ))

    def test_number_before_unit_changes_are_blocked(self):
        for source, candidate in [
            ("他走了20公里。", "他走了200公里。"),
            ("花了100元。", "花了1000元。"),
            ("成功率50%。", "成功率5%。"),
            ("温度降到零下20度。", "温度降到零下2度。"),
            ("温度降到零下20度。", "温度升到20度。"),
        ]:
            with self.subTest(source=source, candidate=candidate):
                ok, errors = vcc.compare_sequences(source, candidate)
                self.assertFalse(ok)
                self.assertTrue(any("protected value changed" in error for error in errors))

    def test_fact_lock_expected_value_must_match_source_and_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            locks = json.loads((root / "fact-lock.json").read_text(encoding="utf-8"))
            locks[0]["expected_value"] = "900"
            (root / "fact-lock.json").write_text(
                json.dumps(locks, ensure_ascii=False), encoding="utf-8"
            )
            report = vcc.check_attempt(root)
            self.assertFalse(report["checks"]["fact_lock"]["ok"])
            self.assertTrue(any(
                "expected_value" in error
                for error in report["checks"]["fact_lock"]["errors"]
            ))

    def test_review_dimensions_require_nonempty_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            state_path = root / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "review_pending"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            write_reviews(root)
            for path in (root / "reviews").glob("*.md"):
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "| pass | evidence |", "| pass | |"
                    ),
                    encoding="utf-8",
                )
            report = vcc.check_attempt(root, require_reviews=True)
            self.assertFalse(report["checks"]["reviews"]["ok"])
            self.assertTrue(any(
                "evidence is empty" in error
                for error in report["checks"]["reviews"]["errors"]
            ))

    def test_working_copy_protected_value_change_still_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = make_working_copy_attempt(Path(tmp), balance=900)
            report = vcc.check_attempt(attempt, allow_working_copy=True)
            self.assertFalse(report["ok"])
            self.assertFalse(report["checks"]["differences"]["ok"])
            self.assertTrue(any(
                "protected value changed" in error
                for error in report["checks"]["differences"]["errors"]
            ))

    def test_working_copy_reviews_are_provisional_and_reject_review_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt = make_working_copy_attempt(Path(tmp))
            write_reviews(attempt, working_copy=True)
            report = vcc.check_attempt(
                attempt,
                allow_working_copy=True,
                require_reviews=True,
            )
            self.assertTrue(report["ok"], report)
            self.assertFalse(report["eligible_for_review_passed"])

            state_path = attempt / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "review_passed"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            report = vcc.check_attempt(
                attempt,
                allow_working_copy=True,
                require_reviews=True,
            )
            self.assertFalse(report["checks"]["review_subject"]["ok"])

    def test_not_requested_requires_byte_identical_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            record = root / "naturalization.md"
            record.write_text(
                record.read_text(encoding="utf-8").replace(
                    "naturalization_result: candidate",
                    "naturalization_result: not_requested",
                ),
                encoding="utf-8",
            )
            (root / "candidate.md").write_bytes((root / "workspace" / "source.md").read_bytes())
            record.write_text(
                record.read_text(encoding="utf-8").replace(
                    next(line.split(": ", 1)[1] for line in record.read_text(encoding="utf-8").splitlines()
                         if line.startswith("candidate_sha256:")),
                    vcc.sha256_file(root / "candidate.md"),
                ),
                encoding="utf-8",
            )
            report = vcc.check_attempt(root)
            self.assertTrue(report["ok"], report)

            (root / "candidate.md").write_text("已被改写", encoding="utf-8")
            changed_hash = vcc.sha256_file(root / "candidate.md")
            lines = record.read_text(encoding="utf-8").splitlines()
            record.write_text(
                "\n".join(
                    f"candidate_sha256: {changed_hash}" if line.startswith("candidate_sha256:") else line
                    for line in lines
                ) + "\n",
                encoding="utf-8",
            )
            report = vcc.check_attempt(root)
            self.assertFalse(report["checks"]["metadata"]["ok"])
            self.assertTrue(any("not_requested" in error for error in report["checks"]["metadata"]["errors"]))

    def test_ok_attempt_passes(self):
        report = vcc.check_attempt(ATTEMPT_OK)
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["checks"]["hashes"]["ok"])
        self.assertTrue(report["checks"]["fact_lock"]["ok"])
        self.assertTrue(report["checks"]["differences"]["ok"])

    def test_value_change_fails(self):
        report = vcc.check_attempt(ATTEMPT_BROKEN)
        self.assertFalse(report["ok"])
        self.assertFalse(report["checks"]["differences"]["ok"])
        self.assertTrue(any("protected value" in e for e in report["checks"]["differences"]["errors"]))

    def test_passed_state_rejects_new_candidate(self):
        # 已进入 review_passed 的 attempt 不应接受新候选
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workspace").mkdir()
            (root / "workspace" / "source.md").write_text("正文", encoding="utf-8")
            (root / "candidate.md").write_text("正文", encoding="utf-8")
            (root / "naturalization.md").write_text(
                "source_sha256: " + vcc.sha256_text("正文") + "\n"
                "candidate_sha256: " + vcc.sha256_text("正文") + "\n",
                encoding="utf-8",
            )
            (root / "state.json").write_text(
                json.dumps({"status": "review_passed"}), encoding="utf-8"
            )
            (root / "fact-lock.json").write_text("[]", encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["ok"])
            self.assertFalse(report["checks"]["state"]["ok"])

    def test_missing_files_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = vcc.check_attempt(root)
            self.assertFalse(report["ok"])
            self.assertFalse(report["checks"]["files"]["ok"])

    def test_fact_lock_source_hash_change_fails(self):
        with __import__("tempfile").TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workspace").mkdir()
            (root / "workspace" / "source.md").write_text("正文", encoding="utf-8")
            (root / "candidate.md").write_text("正文", encoding="utf-8")
            (root / "naturalization.md").write_text(
                "source_sha256: " + vcc.sha256_text("正文") + "\n"
                "candidate_sha256: " + vcc.sha256_text("正文") + "\n",
                encoding="utf-8",
            )
            (root / "state.json").write_text(
                json.dumps({"status": "naturalization_candidate"}), encoding="utf-8"
            )
            lock = [{
                "lock_id": "fl-1", "category": "n", "expected_value": "x",
                "source_path": str(root / "workspace" / "source.md"),
                "source_anchor": "正文", "source_sha256": "0" * 64,
            }]
            (root / "fact-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("fact lock source hash changed" in e for e in report["checks"]["fact_lock"]["errors"]))

    def test_missing_hashes_and_empty_fact_lock_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            record = root / "naturalization.md"
            record.write_text(
                "\n".join(line for line in record.read_text(encoding="utf-8").splitlines()
                          if not line.startswith(("source_sha256:", "candidate_sha256:"))) + "\n",
                encoding="utf-8",
            )
            (root / "fact-lock.json").write_text("[]", encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["checks"]["hashes"]["ok"])
            self.assertFalse(report["checks"]["fact_lock"]["ok"])

    def test_fact_lock_missing_anchor_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            locks = json.loads((root / "fact-lock.json").read_text(encoding="utf-8"))
            locks[0]["source_path"] = str(root / "workspace" / "source.md")
            locks[0]["source_anchor"] = "不存在的事实锚点"
            (root / "fact-lock.json").write_text(json.dumps(locks, ensure_ascii=False), encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["checks"]["fact_lock"]["ok"])

    def test_two_independent_reviews_and_hashes_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            (root / "state.json").write_text(
                json.dumps({"status": "review_pending", "node_id": "chapter-0001",
                            "attempt_id": "attempt-0001"}), encoding="utf-8")
            write_reviews(root)
            report = vcc.check_attempt(root, require_reviews=True)
            self.assertTrue(report["ok"], report)
            (root / "reviews" / "context.md").unlink()
            report = vcc.check_attempt(root, require_reviews=True)
            self.assertFalse(report["checks"]["reviews"]["ok"])

    def test_state_validation_is_independent_from_formal_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            state_path = root / "state.json"
            state_path.write_text(
                json.dumps({"status": "summary_staged", "node_id": "chapter-0001",
                            "attempt_id": "attempt-0001"}), encoding="utf-8")
            write_state_evidence(root)
            report = vcc.check_attempt(root, require_state_validation=True)
            self.assertTrue(report["ok"], report)
            self.assertNotIn("reviews", report["checks"])

            cli = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_chapter_candidate.py"),
                 "--attempt-dir", str(root), "--require-state-validation"],
                cwd=str(ROOT), text=True, encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)

    def test_review_dimension_and_state_evidence_failures_block_their_own_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            state_path = root / "state.json"
            state_path.write_text(
                json.dumps({"status": "summary_staged", "node_id": "chapter-0001",
                            "attempt_id": "attempt-0001"}), encoding="utf-8")
            write_reviews(root)
            write_state_evidence(root)
            context = root / "reviews" / "context.md"
            context.write_text(context.read_text(encoding="utf-8").replace(
                "| causality | pass |", "| causality | fail |"), encoding="utf-8")
            report = vcc.check_attempt(root, require_reviews=True)
            self.assertFalse(report["checks"]["reviews"]["ok"])
            write_reviews(root)
            deltas = json.loads((root / "deltas" / "state.json").read_text(encoding="utf-8"))
            deltas[0]["source_excerpt_sha256"] = "f" * 64
            (root / "deltas" / "state.json").write_text(json.dumps(deltas), encoding="utf-8")
            report = vcc.check_attempt(root, require_state_validation=True)
            self.assertFalse(report["checks"]["state_evidence"]["ok"])

    def test_cli_exit_codes(self):
        ok_run = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_chapter_candidate.py"),
             "--attempt-dir", str(ATTEMPT_OK)],
            cwd=str(ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(ok_run.returncode, 0)
        bad_run = subprocess.run(
            [sys.executable, str(SCRIPTS / "validate_chapter_candidate.py"),
             "--attempt-dir", str(ATTEMPT_BROKEN)],
            cwd=str(ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(bad_run.returncode, 1)


if __name__ == "__main__":
    unittest.main()
