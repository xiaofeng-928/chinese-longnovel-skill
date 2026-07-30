import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHORT_SCRIPTS = ROOT / "short-form" / "scripts"


class TestShortRankScan(unittest.TestCase):
    def test_scan_writes_type_report_and_opt_in_feature_profile(self):
        records = [
            {
                "platform": "短篇平台",
                "title": f"样本{i}",
                "captured_at": "2026-07-30",
                "source_url": f"https://example.test/{i}",
                "tags": ["世俗言情文", "先婚后爱"],
                "hook": "开局被迫闪婚",
                "relationship": "先婚后爱",
                "conflict": "契约关系失衡",
                "ending": "关系确认",
            }
            for i in range(1, 6)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "rank.json"
            type_dir = temp_path / "世俗言情文"
            input_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SHORT_SCRIPTS / "扫榜.py"),
                    "--input", str(input_path),
                    "--type-dir", str(type_dir),
                    "--update-features",
                    "--format", "json",
                ],
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["records"], 5)
            self.assertEqual(payload["sample_status"], "足够")

            library_dir = type_dir / "范文参照"
            report_path = library_dir / "扫榜记录" / "2026-07-30_扫榜.md"
            profile_path = library_dir / "类型创作特征.md"
            self.assertTrue(report_path.is_file())
            self.assertTrue(profile_path.is_file())
            self.assertFalse((library_dir / "范文合集.txt").exists())

            report = report_path.read_text(encoding="utf-8")
            profile = profile_path.read_text(encoding="utf-8")
            self.assertIn("样本数量：5", report)
            self.assertIn("先婚后爱", profile)
            self.assertIn("开局被迫闪婚", profile)


if __name__ == "__main__":
    unittest.main()
