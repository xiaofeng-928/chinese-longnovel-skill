import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import validate_chapter_candidate as vcc


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
ATTEMPT_OK = FIXTURES / "attempt_ok"
ATTEMPT_BROKEN = FIXTURES / "attempt_broken"


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
                json.dumps({"status": "review_passed"}), encoding="utf-8"
            )
            (root / "fact-lock.json").write_text("[]", encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["ok"])
            self.assertFalse(report["checks"]["state"]["ok"])

    def test_missing_files_fail(self):
        with __import__("tempfile").TemporaryDirectory() as tmp:
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
                "source_anchor": "a", "source_sha256": "deadbeef",
            }]
            (root / "fact-lock.json").write_text(json.dumps(lock), encoding="utf-8")
            report = vcc.check_attempt(root)
            self.assertFalse(report["ok"])
            self.assertTrue(any("fact lock source hash changed" in e for e in report["checks"]["fact_lock"]["errors"]))

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
