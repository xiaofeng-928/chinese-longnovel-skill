import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LONG_ROOT = ROOT / "long-form"
SCRIPTS = LONG_ROOT / "scripts"


def run_script(script_name, *args):
    cmd = [sys.executable, str(SCRIPTS / script_name)] + list(args)
    completed = subprocess.run(
        cmd,
        cwd=str(LONG_ROOT),
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


class TestNovelLint(unittest.TestCase):
    def write_temp_text(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "sample.md"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    # --- 字数口径（审查口径，含省略号加权） ---

    def test_word_count_ignores_whitespace(self):
        text_file = self.write_temp_text("他 A1，\n\t好。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["word_count"]["count"], 6)
        self.assertEqual(data["word_count"]["unit"], "review_char")

    def test_word_count_counts_letters_digits_and_punctuation(self):
        text_file = self.write_temp_text("A计划3分钟。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        self.assertEqual(data["word_count"]["count"], 7)

    def test_word_count_chinese_ellipsis_counts_as_six(self):
        text_file = self.write_temp_text("他……走了。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        # 他=1 ……=6 走=1 了=1 。=1 → 10
        self.assertEqual(data["word_count"]["count"], 10)

    def test_word_count_single_ellipsis_and_dash(self):
        text_file = self.write_temp_text("天啊…真的吗——不可能！")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        # 天=1 啊=1 …=3 真=1 的=1 吗=1 ——=2 不=1 可=1 能=1 ！=1 → 14
        self.assertEqual(data["word_count"]["count"], 14)

    # --- AI 味三梯队 ---

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

    # --- 时间锚 / 能力候选 ---

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

    # --- 禁用词 ---

    def test_scans_forbidden_words_from_file(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "chapter.md"
        text_path.write_text("这段话包含绝对不能写的词。", encoding="utf-8")
        words_path = Path(temp_dir.name) / "forbidden.txt"
        words_path.write_text("# 注释\n绝对不能写的\n", encoding="utf-8")
        data = run_script(
            "小说质检.py", "lint",
            "--file", str(text_path),
            "--forbidden-words", str(words_path),
        )
        matches = {item["word"]: item["count"] for item in data["forbidden_words"]["matches"]}
        self.assertEqual(matches["绝对不能写的"], 1)

    def test_warns_when_forbidden_words_are_not_configured(self):
        text_file = self.write_temp_text("普通正文。")
        data = run_script("小说质检.py", "lint", "--file", str(text_file))
        warning_codes = {item["code"] for item in data["warnings"]}
        self.assertIn("FORBIDDEN_WORDS_NOT_CONFIGURED", warning_codes)

    def test_whitelist_does_not_replace_forbidden_word_configuration(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_dir = Path(temp_dir.name)
        (project_dir / "novel-config.md").write_text("# project\n", encoding="utf-8")
        (project_dir / ".deslop-whitelist").write_text("exempt-term\n", encoding="utf-8")
        text_path = project_dir / "chapter.md"
        text_path.write_text("plain text", encoding="utf-8")
        lint_script = next(
            path for path in SCRIPTS.glob("*.py")
            if "def lint(args)" in path.read_text(encoding="utf-8")
        )
        completed = subprocess.run(
            [sys.executable, str(lint_script), "lint", "--file", str(text_path)],
            cwd=str(LONG_ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        warning_codes = {item["code"] for item in data["warnings"]}
        self.assertIn("FORBIDDEN_WORDS_NOT_CONFIGURED", warning_codes)

    def test_project_whitelist_exempts_only_listed_forbidden_words(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_dir = Path(temp_dir.name)
        (project_dir / "novel-config.md").write_text("# project\n", encoding="utf-8")
        (project_dir / ".deslop-whitelist").write_text("exempt-term\n", encoding="utf-8")
        text_path = project_dir / "chapter.md"
        text_path.write_text("exempt-term blocked-term", encoding="utf-8")
        forbidden_path = project_dir / "forbidden.txt"
        forbidden_path.write_text("exempt-term\nblocked-term\n", encoding="utf-8")
        lint_script = next(
            path for path in SCRIPTS.glob("*.py")
            if "def lint(args)" in path.read_text(encoding="utf-8")
        )
        completed = subprocess.run(
            [
                sys.executable, str(lint_script), "lint", "--file", str(text_path),
                "--forbidden-words", str(forbidden_path),
            ],
            cwd=str(LONG_ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        matches = {item["word"] for item in data["forbidden_words"]["matches"]}
        self.assertEqual(matches, {"blocked-term"})


class TestCountChars(unittest.TestCase):
    """验证 count_chars.py CLI 与小说质检.py 口径一致。"""

    def test_count_chars_cli_matches_lint(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "sample.md"
        text_path.write_text("他……走了。\n天啊…真的吗——不可能！", encoding="utf-8")
        lint_data = run_script("小说质检.py", "lint", "--file", str(text_path))
        cc_data = subprocess.run(
            [sys.executable, str(SCRIPTS / "count_chars.py"), str(text_path)],
            cwd=str(LONG_ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(cc_data.returncode, 0)
        cc_count = int(cc_data.stdout.strip().split(":")[-1].strip().split()[0])
        self.assertEqual(lint_data["word_count"]["count"], cc_count)


class TestRankScan(unittest.TestCase):
    def test_rank_scan_groups_genres_and_writes_decision(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        input_path = Path(temp_dir.name) / "rank.json"
        output_path = Path(temp_dir.name) / "选题决策.md"
        input_path.write_text(json.dumps([
            {"platform": "番茄", "genres": ["末世", "经营"], "heat": "1.2亿", "captured_at": "2026-07-26", "source_url": "https://example.test/a"},
            {"platform": "番茄", "genres": ["末世"], "heat": "9000万", "captured_at": "2026-07-26", "source_url": "https://example.test/b"},
            {"platform": "番茄", "genres": ["末世"], "heat": "8000万", "captured_at": "2026-07-26", "source_url": "https://example.test/c"},
            {"platform": "番茄", "genres": ["经营"], "heat": "7000万", "captured_at": "2026-07-26", "source_url": "https://example.test/d"},
            {"platform": "番茄", "genres": ["末世"], "heat": "6000万", "captured_at": "2026-07-26", "source_url": "https://example.test/e"},
        ], ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "扫榜.py"), "--input", str(input_path), "--output", str(output_path), "--format", "json"],
            cwd=str(LONG_ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertEqual(data["records"], 5)
        self.assertEqual(data["candidates"][0]["genre"], "末世")
        self.assertIn("选题决策", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
