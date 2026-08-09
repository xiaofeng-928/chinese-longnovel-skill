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
            "拆书记录.md",
            "总结.md",
            "审查报告.md",
            "正文/第001章_标题.md",
            "一到两万字",
            "不使用 50 章归档",
        ]:
            self.assertIn(phrase, short_skill)

    def test_short_form_keeps_type_rules_separate_from_common_ai_polish_prompt(self):
        short_root = ROOT / "short-form"

        self.assertTrue((short_root / "prompts" / "去AI润稿提示词.md").is_file())
        self.assertTrue((short_root / "references" / "去AI润稿流程.md").is_file())
        self.assertTrue((short_root / "references" / "上下文装配.md").is_file())
        short_skill = (short_root / "SKILL.md").read_text(encoding="utf-8")
        common_prompt = (short_root / "prompts" / "去AI润稿提示词.md").read_text(encoding="utf-8")
        self.assertIn("<作品类型>/提示词/创作提示词.md", short_skill)
        self.assertIn("类型提示词", common_prompt)
        self.assertIn("不把所有短篇统一改成一种", common_prompt)

    def test_short_form_routes_reference_disassembly_before_outline(self):
        short_skill = (ROOT / "short-form" / "SKILL.md").read_text(encoding="utf-8")
        disassembly = (ROOT / "short-form" / "references" / "拆书与重组.md").read_text(encoding="utf-8")

        for phrase in ["拆书与重组.md", "拆书记录.md", "原创性闸门", "10-15 个核心事件", "可复用套路模板"]:
            self.assertIn(phrase, short_skill + disassembly)

        self.assertIn("台词润色", short_skill)
        self.assertIn("不能把外部范文改名改词", short_skill)

    def test_short_form_persists_intro_before_summary_and_publication(self):
        short_skill = (ROOT / "short-form" / "SKILL.md").read_text(encoding="utf-8")
        structure = (ROOT / "short-form" / "references" / "项目定位与文件结构.md").read_text(encoding="utf-8")

        summary_ref = (ROOT / "short-form" / "references" / "总结与导语.md").read_text(encoding="utf-8")

        for phrase in ["总结.md", "导语", "第001章", "发布"]:
            self.assertIn(phrase, short_skill + structure)

        self.assertIn("先写导语，再写内部总结", short_skill)
        self.assertIn("先写导语，再写内部总结", summary_ref)
        self.assertIn("放在 `正文/第001章_<标题>.md` 之前", summary_ref)

    def test_imported_reference_text_requires_reusable_close_reading_notes(self):
        library = (ROOT / "short-form" / "references" / "类型范文库.md").read_text(encoding="utf-8")
        disassembly = (ROOT / "short-form" / "references" / "拆书与重组.md").read_text(encoding="utf-8")
        context = (ROOT / "short-form" / "references" / "上下文装配.md").read_text(encoding="utf-8")

        for phrase in ["正文补齐后", "精读笔记", "主线压缩", "关键事件链", "人设标签"]:
            self.assertIn(phrase, library + disassembly)

        self.assertIn("范文库长期资产", disassembly)
        self.assertIn("正文与精读笔记", context)

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
