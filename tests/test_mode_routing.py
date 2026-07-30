import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestModeRouting(unittest.TestCase):
    def test_root_skill_routes_to_separate_long_and_short_form_skills(self):
        root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "long-form" / "SKILL.md").is_file())
        self.assertTrue((ROOT / "short-form" / "SKILL.md").is_file())
        self.assertIn("long-form/SKILL.md", root_skill)
        self.assertIn("short-form/SKILL.md", root_skill)

    def test_short_form_defines_the_confirmed_project_layout(self):
        short_skill = (ROOT / "short-form" / "SKILL.md").read_text(encoding="utf-8")

        for phrase in [
            "D:\\ai小说\\短篇",
            "范文参照",
            "config-novel.md",
            "参考素材.txt",
            "审查报告.md",
            "正文/第001章_标题.md",
            "一到两万字",
            "不使用 50 章归档",
        ]:
            self.assertIn(phrase, short_skill)

    def test_short_form_keeps_type_rules_out_of_generic_prompt_shims(self):
        short_root = ROOT / "short-form"

        self.assertFalse((short_root / "prompts").exists())
        self.assertTrue((short_root / "references" / "上下文装配.md").is_file())
        self.assertIn("<作品类型>/提示词/创作提示词.md", (short_root / "SKILL.md").read_text(encoding="utf-8"))

    def test_short_form_requires_structural_review_before_type_prompt_changes(self):
        short_skill = (ROOT / "short-form" / "SKILL.md").read_text(encoding="utf-8")

        for phrase in [
            "类型提示词审查",
            "功能与结构相似度",
            "可生成",
            "提示词审查记录.md",
        ]:
            self.assertIn(phrase, short_skill)


if __name__ == "__main__":
    unittest.main()
