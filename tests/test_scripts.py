import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


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
            cwd=str(ROOT), text=True, encoding="utf-8",
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
            cwd=str(ROOT), text=True, encoding="utf-8",
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
            cwd=str(ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(cc_data.returncode, 0)
        cc_count = int(cc_data.stdout.strip().split(":")[-1].strip().split()[0])
        self.assertEqual(lint_data["word_count"]["count"], cc_count)


class TestRankScan(unittest.TestCase):
    def make_records(self, count, platform="番茄", days_ago=5):
        from datetime import date, timedelta
        snapshot = (date.today() - timedelta(days=days_ago)).isoformat()
        return {
            "schema_version": 1,
            "records": [
                {
                    "source_platform": platform,
                    "list_name": "测试榜",
                    "snapshot_date": snapshot,
                    "rank": i + 1,
                    "title": f"测试作品{i}",
                    "author": f"作者{i}",
                    "work_id": f"w{i}",
                    "url": f"https://example.test/book/{i}",
                    "genre_tags": ["末世", "经营"],
                    "evidence_dimensions": ["management_loop", "system_loop"],
                    "captured_at": snapshot,
                }
                for i in range(count)
            ],
        }

    def run_scan(self, records, archive_dir):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        input_path = Path(temp_dir.name) / "rank.json"
        input_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "扫榜.py"),
             "--input", str(input_path), "--archive-dir", str(archive_dir)],
            cwd=str(ROOT), text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return completed

    def test_ready_with_fresh_market_samples(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data = self.run_scan(self.make_records(5), Path(temp_dir))
            self.assertEqual(data.returncode, 0, data.stderr)
            payload = json.loads(data.stdout)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["market_validation_count"], 5)
            self.assertEqual(payload["fresh_market_validation_count"], 5)
            self.assertTrue(payload["archive_path"])

    def test_insufficient_samples_returns_code_3(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data = self.run_scan(self.make_records(3), Path(temp_dir))
            self.assertEqual(data.returncode, 3)
            payload = json.loads(data.stdout)
            self.assertEqual(payload["status"], "insufficient_samples")
            self.assertEqual(payload["market_validation_count"], 3)

    def test_stale_evidence_returns_code_4(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data = self.run_scan(self.make_records(5, days_ago=45), Path(temp_dir))
            self.assertEqual(data.returncode, 4)
            payload = json.loads(data.stdout)
            self.assertEqual(payload["status"], "stale_evidence")
            self.assertEqual(payload["fresh_market_validation_count"], 0)

    def test_missing_url_is_schema_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            records = self.make_records(5)
            for r in records["records"]:
                r["url"] = ""
            data = self.run_scan(records, Path(temp_dir))
            self.assertEqual(data.returncode, 2)
            payload = json.loads(data.stdout)
            self.assertEqual(payload["status"], "schema_invalid")
            self.assertEqual(payload["valid_count"], 0)

    def test_dedup_conflict_returns_code_5(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            records = self.make_records(2)
            records["records"].append(dict(records["records"][0], title="改名"))
            data = self.run_scan(records, Path(temp_dir))
            self.assertEqual(data.returncode, 5)
            payload = json.loads(data.stdout)
            self.assertEqual(payload["status"], "dedup_conflict")
            self.assertTrue(payload["conflicts"])

    def test_reused_archive_does_not_rewrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "arch"
            data1 = self.run_scan(self.make_records(5), archive)
            path = json.loads(data1.stdout)["archive_path"]
            mtime = Path(path).stat().st_mtime
            data2 = self.run_scan(self.make_records(5), archive)
            payload2 = json.loads(data2.stdout)
            self.assertTrue(payload2["reused"])
            self.assertEqual(Path(path).stat().st_mtime, mtime)

    def test_market_count_requires_management_or_system_loop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            records = self.make_records(6)
            for r in records["records"]:
                r["evidence_dimensions"] = ["opening"]
            data = self.run_scan(records, Path(temp_dir))
            payload = json.loads(data.stdout)
            # 无经营证据：market_validation_count 为 0 → insufficient
            self.assertEqual(payload["market_validation_count"], 0)
            self.assertEqual(data.returncode, 3)


STYLE_TEXT = """第1章 永夜

夜色沉沉，远处有狗在叫。他听见了，但是没有动。

“你来了。”那人说。
他点点头，默默抽出一根烟。

第二日清晨，他去镇上换了一袋米。
“这米不错。”老板说道。
“能吃饱就行。”他答。

第2章 火泉

天亮了。风从山谷里灌进来。
他站在火堆边，把冻僵的手指烤暖。

“再等一天。”他对自己说。
山道上的雪还没有化，走不得。
"""

STYLE_INDEX = """# 《测试》章节索引

| 序号 | 标题 | 章节ID | 正文来源 | 访问日期 | 字数 |
|---:|---|---|---|---|---:|
| 1 | 第1章 永夜 | 1 | test | 2026-08-09 | 200 |
| 2 | 第2章 火泉 | 2 | test | 2026-08-09 | 200 |
"""


class TestStyleStats(unittest.TestCase):
    def write_text(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name) / "测试正文.txt"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return path

    def make_fixture(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "测试正文.txt"
        index_path = Path(temp_dir.name) / "测试索引.md"
        text_path.write_text(STYLE_TEXT, encoding="utf-8")
        index_path.write_text(STYLE_INDEX, encoding="utf-8")
        return text_path, index_path

    def test_profile_outputs_core_stats(self):
        text_path, index_path = self.make_fixture()
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        self.assertTrue(data["ok"])
        self.assertEqual(data["total"]["chapters"], 2)
        self.assertGreater(data["total"]["chars"], 0)
        self.assertGreater(data["total"]["sentences"], 0)
        self.assertGreater(data["total"]["paragraphs"], 0)

    def test_chinese_quote_dialogue_ratio(self):
        text_path, index_path = self.make_fixture()
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        self.assertGreater(data["total"]["dialogue_ratio"], 0)

    def test_ellipsis_and_dash_counts(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "测试正文.txt"
        index_path = Path(temp_dir.name) / "测试索引.md"
        text_path.write_text("第1章 始\n\n他想了想……再想想……\n\n他走了——头也不回——\n", encoding="utf-8")
        index_path.write_text("| 序号 | 标题 | 章节ID | 正文来源 | 访问日期 | 字数 |\n|---:|---|---|---|---|---:|\n| 1 | 第1章 始 | 1 | test | 2026-08-09 | 100 |\n", encoding="utf-8")
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        punct = data["punctuation"]
        self.assertGreater(punct["……"], 0)
        self.assertGreater(punct["——"], 0)

    def test_empty_paragraphs_and_headings_excluded_from_paragraph_count(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "测试正文.txt"
        index_path = Path(temp_dir.name) / "测试索引.md"
        text_path.write_text("第1章 始\n\n\n第一段。\n\n\n第二段。\n\n", encoding="utf-8")
        index_path.write_text("| 序号 | 标题 | 章节ID | 正文来源 | 访问日期 | 字数 |\n|---:|---|---|---|---|---:|\n| 1 | 第1章 始 | 1 | test | 2026-08-09 | 50 |\n", encoding="utf-8")
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        self.assertEqual(data["total"]["paragraphs"], 2)

    def test_multi_chapter_selection(self):
        text_path, index_path = self.make_fixture()
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path), "--chapters", "1")
        self.assertEqual(data["total"]["chapters"], 1)
        self.assertEqual(data["chapters"][0]["number"], 1)

    def test_sentence_and_paragraph_quantiles(self):
        text_path, index_path = self.make_fixture()
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        for bucket in [data["sentence_lengths"], data["paragraph_lengths"]]:
            for key in ["mean", "p25", "median", "p75", "p90"]:
                self.assertIn(key, bucket)
                self.assertGreaterEqual(bucket[key], 0)

    def test_utf8_chinese_path(self):
        text_path, index_path = self.make_fixture()
        data = run_script("文风统计.py", "profile", "--text", str(text_path), "--index", str(index_path))
        self.assertTrue(data["ok"])

    def test_empty_text_fails(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        text_path = Path(temp_dir.name) / "测试正文.txt"
        index_path = Path(temp_dir.name) / "测试索引.md"
        text_path.write_text("", encoding="utf-8")
        index_path.write_text(STYLE_INDEX, encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "文风统计.py"), "profile", "--text", str(text_path), "--index", str(index_path)],
            cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(completed.returncode, 0)
        data = json.loads(completed.stdout)
        self.assertFalse(data["ok"])

    def test_missing_index_fails(self):
        text_path, _ = self.make_fixture()
        missing = Path(text_path.parent) / "不存在.md"
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "文风统计.py"), "profile", "--text", str(text_path), "--index", str(missing)],
            cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_nonexistent_chapter_fails(self):
        text_path, index_path = self.make_fixture()
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "文风统计.py"), "profile", "--text", str(text_path), "--index", str(index_path), "--chapters", "99"],
            cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertNotEqual(completed.returncode, 0)


class TestOverlapCheck(unittest.TestCase):
    def write_files(self, draft, source):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        draft_path = Path(temp_dir.name) / "测试草稿.txt"
        source_path = Path(temp_dir.name) / "测试来源.txt"
        draft_path.write_text(draft, encoding="utf-8")
        source_path.write_text(source, encoding="utf-8")
        return draft_path, source_path

    def run_check(self, draft, source, extra=None):
        draft_path, source_path = self.write_files(draft, source)
        cmd = [sys.executable, str(SCRIPTS / "原文重合检查.py"), "check", "--draft", str(draft_path), "--source", str(source_path)]
        if extra:
            cmd.extend(extra)
        completed = subprocess.run(cmd, cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_reports_both_punctuation_scopes(self):
        source = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。你来了。那人说。"
        draft = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。你来了。那人说。"
        data = self.run_check(draft, source)
        scopes = {item["scope"] for item in data["findings"]}
        self.assertEqual(scopes, {"with_punct", "without_punct"})

    def test_threshold_boundaries(self):
        base = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
        for length, expected in [(16, "需复核"), (23, "需复核"), (24, "阻断")]:
            source = "开场" + base[:length] + "收尾"
            draft = base[:length]
            data = self.run_check(draft, source)
            wp = [item for item in data["findings"] if item["scope"] == "with_punct"]
            self.assertTrue(wp, f"no with_punct finding for length {length}")
            self.assertEqual(wp[0]["length"], length)
            self.assertEqual(wp[0]["severity"], expected)

    def test_multi_source(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        draft_path = Path(temp_dir.name) / "测试草稿.txt"
        source_a = Path(temp_dir.name) / "测试来源A.txt"
        source_b = Path(temp_dir.name) / "测试来源B.txt"
        base = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
        draft_path.write_text(base[:20], encoding="utf-8")
        source_a.write_text("A开头" + base[:16], encoding="utf-8")
        source_b.write_text("B开头" + base[2:22], encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "原文重合检查.py"), "check", "--draft", str(draft_path), "--source", str(source_a), "--source", str(source_b)],
            cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertEqual(data["summary"]["sources"], 2)
        self.assertEqual({item["source_index"] for item in data["findings"]}, {0, 1})

    def test_whitelist_exempts(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        draft_path = Path(temp_dir.name) / "测试草稿.txt"
        source_path = Path(temp_dir.name) / "测试来源.txt"
        whitelist_path = Path(temp_dir.name) / "白名单.txt"
        base = "一二三四五六七八九十甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
        draft_path.write_text(base[:20], encoding="utf-8")
        source_path.write_text("前缀" + base[:20], encoding="utf-8")
        whitelist_path.write_text("# 白名单\n一二三四五六七八九十甲乙丙丁戊己庚辛壬癸\n", encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "原文重合检查.py"), "check", "--draft", str(draft_path), "--source", str(source_path), "--whitelist", str(whitelist_path)],
            cwd=str(ROOT), text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertGreaterEqual(len(data["exempted"]), 1)
        self.assertLessEqual(len(data["findings"]), 2)

    def test_short_overlap_reports_only_when_repeated(self):
        base13 = "一二三四五六七八九十一二三"
        source_single = "前缀" + base13
        draft = "前缀" + base13
        data_single = self.run_check(draft, source_single)
        short_wp = [item for item in data_single["findings"] if item["scope"] == "with_punct" and item["length"] <= 15]
        self.assertEqual(short_wp, [], "unique short overlap should not be reported")

        source_repeat = "AAA" + base13 + "BBB" + base13
        data_repeat = self.run_check(draft, source_repeat)
        short_wp_repeat = [item for item in data_repeat["findings"] if item["scope"] == "with_punct" and item["length"] <= 15]
        self.assertTrue(short_wp_repeat, "repeated short overlap should be reported")

    def test_positions_are_locatable(self):
        source = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。你来了。那人说。"
        draft = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。你来了。那人说。"
        data = self.run_check(draft, source)
        for item in data["findings"]:
            self.assertIn("draft_position", item)
            self.assertIn("source_position", item)
            self.assertIn("original_start", item["draft_position"])
            self.assertIn("original_end", item["draft_position"])
            self.assertIn("original_start", item["source_position"])
            self.assertIn("original_end", item["source_position"])

    def test_utf8_chinese_path(self):
        source = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。"
        draft = "夜色沉沉，远处有狗在叫。他听见了，但是没有动。"
        data = self.run_check(draft, source)
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
