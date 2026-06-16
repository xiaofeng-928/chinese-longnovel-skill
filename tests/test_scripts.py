import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
PROJECT = FIXTURES / "迷你小说项目"


def run_script(script_name, *args):
    cmd = [sys.executable, str(SCRIPTS / script_name)] + list(args)
    completed = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return json.loads(completed.stdout)


class TestNovelFiles(unittest.TestCase):
    def test_scan_projects_finds_fixture_project(self):
        data = run_script("小说文件.py", "scan-projects", "--root", str(FIXTURES))
        self.assertTrue(data["ok"])
        names = [item["name"] for item in data["projects"]]
        self.assertIn("迷你小说项目", names)

    def test_scan_projects_returns_fuzzy_match_score(self):
        data = run_script("小说文件.py", "scan-projects", "--root", str(FIXTURES), "--query", "迷你")
        self.assertTrue(data["ok"])
        self.assertGreater(data["projects"][0]["match_score"], 0)
        self.assertTrue(data["projects"][0]["reason"])

    def test_chapter_status_parses_range_1_to_30(self):
        data = run_script("小说文件.py", "chapter-status", "--project", str(PROJECT), "--range", "1-30")
        self.assertEqual(data["range"], {"start": 1, "end": 30, "count": 30})

    def test_chapter_status_detects_duplicate_chapter_files(self):
        data = run_script("小说文件.py", "chapter-status", "--project", str(PROJECT), "--range", "1-30")
        duplicates = {item["chapter"]: item for item in data["duplicate_chapters"]}
        self.assertIn(2, duplicates)
        self.assertEqual(len(duplicates[2]["files"]), 2)

    def test_archive_path_calculates_51_to_100_for_chapter_61(self):
        data = run_script("小说文件.py", "archive-path", "--project", str(PROJECT), "--chapter", "61", "--type", "summary")
        self.assertEqual(data["archive"]["start"], 51)
        self.assertEqual(data["archive"]["end"], 100)
        self.assertIn("第51-100章", data["archive"]["path"])


class TestNovelLint(unittest.TestCase):
    def write_temp_text(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "sample.md"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def test_word_count_ignores_whitespace(self):
        text_file = self.write_temp_text("他 A1，\n\t好。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["word_count"]["count"], 6)

    def test_word_count_counts_letters_digits_and_punctuation(self):
        text_file = self.write_temp_text("A计划3分钟。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["word_count"]["count"], 7)

    def test_tier1_ai_flavor_triggers_per_term_at_two(self):
        text_file = self.write_temp_text("他不由得停下，又不由得回头。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertTrue(data["ai_flavor"]["tier1"]["triggered"])
        self.assertEqual(data["ai_flavor"]["tier1"]["terms"]["不由得"]["count"], 2)

    def test_tier2_ai_flavor_triggers_by_total_above_three(self):
        text_file = self.write_temp_text("震惊。不可思议。面色大变。空气凝固。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["ai_flavor"]["tier2"]["total"], 4)
        self.assertTrue(data["ai_flavor"]["tier2"]["triggered"])

    def test_tier3_ai_flavor_triggers_by_total_above_five(self):
        text_file = self.write_temp_text("微微淡淡缓缓默默轻轻深深")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["ai_flavor"]["tier3"]["total"], 6)
        self.assertTrue(data["ai_flavor"]["tier3"]["triggered"])

    def test_extracts_time_anchor_candidates(self):
        text_file = self.write_temp_text("二十分钟后，他在晚上赶到。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        first = data["time_anchor_candidates"][0]
        self.assertIn("二十分钟", first["matched_terms"])
        self.assertIn("晚上", first["matched_terms"])

    def test_extracts_ability_candidates(self):
        text_file = self.write_temp_text("系统解锁新能力，消耗10点积分。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        first = data["ability_candidates"][0]
        for term in ["解锁", "能力", "消耗", "积分"]:
            self.assertIn(term, first["matched_terms"])

    def test_scans_forbidden_words_file(self):
        data = run_script(
            "小说质检.py",
            "lint",
            "--file",
            str(PROJECT / "正文" / "第001章_开局.md"),
            "--forbidden-words",
            str(FIXTURES / "禁用词.txt"),
        )
        matches = {item["word"]: item["count"] for item in data["forbidden_words"]["matches"]}
        self.assertEqual(matches["绝对不能写"], 1)


class TestNovelAnchor(unittest.TestCase):
    def test_check_existing_anchor_block(self):
        target = PROJECT / "章节总结" / "章节总结_第1-50章.md"
        data = run_script("小说锚点.py", "check", "--file", str(target), "--chapter", "1", "--kind", "summary")
        self.assertTrue(data["exists"])
        self.assertFalse(data["duplicate"])

    def test_check_duplicate_anchor_block(self):
        target = PROJECT / "章节总结" / "章节总结_第1-50章.md"
        data = run_script("小说锚点.py", "check", "--file", str(target), "--chapter", "2", "--kind", "summary")
        self.assertTrue(data["duplicate"])
        self.assertGreater(data["start_count"], 1)

    def test_check_missing_anchor_block(self):
        target = PROJECT / "章节总结" / "章节总结_第1-50章.md"
        data = run_script("小说锚点.py", "check", "--file", str(target), "--chapter", "9", "--kind", "summary")
        self.assertFalse(data["exists"])
        self.assertTrue(data["missing"])

    def test_replace_dry_run_does_not_modify_file(self):
        target = PROJECT / "章节总结" / "章节总结_第1-50章.md"
        before = target.read_text(encoding="utf-8")
        data = run_script(
            "小说锚点.py",
            "replace",
            "--file",
            str(target),
            "--chapter",
            "1",
            "--kind",
            "summary",
            "--content-file",
            str(FIXTURES / "新内容.md"),
            "--dry-run",
        )
        after = target.read_text(encoding="utf-8")
        self.assertTrue(data["dry_run"])
        self.assertEqual(before, after)

    def test_replace_changes_only_target_block(self):
        target = PROJECT / "章节总结" / "章节总结_第1-50章.md"
        original = target.read_text(encoding="utf-8")
        try:
            data = run_script(
                "小说锚点.py",
                "replace",
                "--file",
                str(target),
                "--chapter",
                "1",
                "--kind",
                "summary",
                "--content-file",
                str(FIXTURES / "新内容.md"),
            )
            changed = target.read_text(encoding="utf-8")
            self.assertTrue(data["changed"])
            self.assertIn("替换后的总结", changed)
            self.assertIn("重复锚点 A", changed)
            self.assertIn("重复锚点 B", changed)
        finally:
            target.write_text(original, encoding="utf-8")


class TestNovelContext(unittest.TestCase):
    def test_build_review_context_lists_required_files(self):
        data = run_script("小说上下文.py", "build", "--project", str(PROJECT), "--chapter", "3", "--mode", "review")
        self.assertTrue(data["ok"])
        self.assertTrue(data["novel_config"].endswith("novel-config.md"))
        self.assertTrue(data["chapter_summaries"])
        self.assertTrue(data["outline"]["current"])
        self.assertTrue(data["stage_summaries"])

    def test_recent_three_chapters_excludes_current_chapter(self):
        data = run_script("小说上下文.py", "build", "--project", str(PROJECT), "--chapter", "3", "--mode", "review")
        chapters = [item["chapter"] for item in data["recent_chapters"]]
        self.assertEqual(chapters, [1, 2])

    def test_recent_twenty_summary_points_to_archive_for_chapter_23(self):
        data = run_script("小说上下文.py", "build", "--project", str(PROJECT), "--chapter", "23", "--mode", "review")
        self.assertIn("章节总结_第1-50章.md", data["chapter_summaries"][0]["path"])
        self.assertEqual(data["chapter_summaries"][0]["range"]["start"], 3)
        self.assertEqual(data["chapter_summaries"][0]["range"]["end"], 22)

    def test_next_two_outline_boundary_chapters(self):
        data = run_script("小说上下文.py", "build", "--project", str(PROJECT), "--chapter", "3", "--mode", "review")
        self.assertEqual(data["outline"]["next_boundary_chapters"], [4, 5])


if __name__ == "__main__":
    unittest.main()

