import unittest

from evals.grade_outputs import grade


class TestEvalGrader(unittest.TestCase):
    def test_accepts_field_names_and_equivalent_chinese(self):
        output = """
        只有用户明确要求去AI时才手动自然化。以已提交正文创建新的 attempt，
        记录 source_sha256、candidate_sha256 和 fact-lock.json；正文变化使旧审查失效。
        不得改变剧情事实和状态仓库语义。
        """
        self.assertEqual(grade(1, output)["summary"]["pass_rate"], 1.0)

    def test_accepts_chinese_failure_terms_without_weakening_requirements(self):
        output = """
        numbers 检查失败，polarity 检查失败。修复后创建新的 attempt 并重新验证；
        通过前不得推进 commit-head，也不得提交。
        """
        self.assertEqual(grade(3, output)["summary"]["pass_rate"], 1.0)

    def test_missing_fact_lock_still_fails(self):
        output = """
        用户手动要求自然化，创建新的 attempt，记录 source_sha256 和 candidate_sha256。
        正文变化使旧审查失效，不得改变剧情事实和状态仓库语义。
        """
        result = grade(1, output)
        fact_lock = next(item for item in result["expectations"] if item["text"] == "hashes_and_fact_lock")
        self.assertFalse(fact_lock["passed"])

    def test_continuation_eval_forbids_review_before_writing(self):
        output = """
        第1-3章的 review_pending 待审状态不阻断，直接续写，不先审第1-3章。
        第4-6章逐章生成，不自动自然化，写总结、更新状态仓库并提交为 review_pending。
        写完后不自动进入审查。
        """
        self.assertEqual(grade(5, output)["summary"]["pass_rate"], 1.0)

    def test_review_repair_eval_distinguishes_style_and_fact_changes(self):
        output = """
        第11-15章按连续5章审查。第12章只是句式表达调整，不重新生成语义总结和状态仓库。
        第14章交易结果与余额变化，重算章节总结和 summary/state 状态增量；
        从第14章这个影响点重建主角、系统仓库及后续投影。
        """
        self.assertEqual(grade(6, output)["summary"]["pass_rate"], 1.0)

    def test_ordinary_writing_eval_requires_raw_candidate_and_state_commit(self):
        output = """
        普通创作不自动调用自然化或去AI。每章源稿与候选字节一致，
        记录 naturalization_result: not_requested。随后生成章节总结，
        更新主角和系统状态仓库，状态回证后逐章提交为 review_pending，再写下一章。
        """
        self.assertEqual(grade(7, output)["summary"]["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
