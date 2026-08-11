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


def write_reviews(attempt: Path):
    source_hash = vcc.sha256_file(attempt / "workspace" / "source.md")
    candidate_hash = vcc.sha256_file(attempt / "candidate.md")
    lock_hash = vcc.sha256_file(attempt / "fact-lock.json")
    dimensions = "\n".join(f"| {name} | pass | evidence |" for name in vcc.REVIEW_DIMENSIONS)
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
    review.write_text(
        "---\nnode_id: chapter-0001\nattempt_id: attempt-0001\n"
        f"reviewed_sha256: {vcc.sha256_file(candidate)}\n"
        f"state_delta_sha256: {vcc.sha256_file(delta_path)}\n"
        "review_prompt_version: state-v3.0\nreviewed_at: 2026-08-11T10:01:00+00:00\n"
        "total_result: pass\n---\n# 状态回证\n",
        encoding="utf-8",
    )


class TestValidateChapterCandidate(unittest.TestCase):
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

    def test_review_dimension_failure_and_state_evidence_failure_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "attempt"
            shutil.copytree(ATTEMPT_OK, root)
            state_path = root / "state.json"
            state_path.write_text(
                json.dumps({"status": "summary_staged", "node_id": "chapter-0001",
                            "attempt_id": "attempt-0001"}), encoding="utf-8")
            write_reviews(root)
            write_state_evidence(root)
            report = vcc.check_attempt(root, require_state_validation=True)
            self.assertTrue(report["ok"], report)
            context = root / "reviews" / "context.md"
            context.write_text(context.read_text(encoding="utf-8").replace(
                "| causality | pass |", "| causality | fail |"), encoding="utf-8")
            report = vcc.check_attempt(root, require_state_validation=True)
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
