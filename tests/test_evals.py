import unittest

from evals.grade_outputs import grade


class TestEvalGrader(unittest.TestCase):
    def test_accepts_field_names_and_equivalent_chinese(self):
        output = """
        正式审查前必须先自然化，记录 source_sha256、candidate_sha256 和 fact-lock.json。
        reviews/naturalization.md 与 reviews/context.md 由不同 reviewer 独立完成。
        状态回证通过后才执行 CAS。
        """
        self.assertEqual(grade(1, output)["summary"]["pass_rate"], 1.0)

    def test_accepts_chinese_failure_terms_without_weakening_requirements(self):
        output = """
        numbers 检查失败，polarity 检查失败。修复后创建新的 attempt；
        通过前不得推进 commit-head，也不得提交。
        """
        self.assertEqual(grade(3, output)["summary"]["pass_rate"], 1.0)

    def test_missing_fact_lock_still_fails(self):
        output = """
        正式审查前必须先自然化，记录 source_sha256 和 candidate_sha256。
        reviews/naturalization.md 与 reviews/context.md 由不同 reviewer 独立完成。
        状态回证通过后才执行 CAS。
        """
        result = grade(1, output)
        fact_lock = next(item for item in result["expectations"] if item["text"] == "hashes_and_fact_lock")
        self.assertFalse(fact_lock["passed"])


if __name__ == "__main__":
    unittest.main()
