import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LONG_ROOT = ROOT / "long-form"


def read_doc(relative_path):
    return (LONG_ROOT / relative_path).read_text(encoding="utf-8")


class TestStageOutlineMemorySyncDocs(unittest.TestCase):
    def test_skill_defines_single_character_authority(self):
        skill = read_doc("SKILL.md")

        for phrase in [
            "细纲审查通过后",
            "角色画像默认只写回 `novel-config.md`",
            "总大纲只在阶段目标、主线/反派线、伏笔追踪或下阶段铺垫发生变化时更新",
            "写回",
        ]:
            self.assertIn(phrase, skill)

        self.assertNotIn("总大纲对应角色规划卡", skill)

    def test_stage_outline_prompt_routes_character_and_plot_sync_separately(self):
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")

        for phrase in [
            "细纲记忆同步清单",
            "新增/强化角色卡",
            "角色卡/反派画像默认写回 `novel-config.md`",
            "总大纲只记录影响阶段目标、主线/反派线、伏笔追踪或下阶段铺垫的变化",
        ]:
            self.assertIn(phrase, prompt)

        self.assertNotIn("| 写回 `novel-config.md` | 写回总大纲 |", prompt)

    def test_file_structure_defines_authoritative_sync_targets_without_duplication(self):
        structure = read_doc("references/文件结构与锚点.md")

        for phrase in [
            "细纲记忆同步",
            "`novel-config.md` 是角色设定唯一权威源",
            "总大纲不是角色卡副本",
            "只在宏观剧情结构变化时更新",
            "只增补缺失画像",
        ]:
            self.assertIn(phrase, structure)

    def test_stage_outline_review_requires_prior_48_outline_cleanup(self):
        skill = read_doc("SKILL.md")
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")

        for phrase in [
            "第51-100章细纲",
            "前48章大纲",
            "第49-50章",
            "边界未写章节细纲",
        ]:
            self.assertIn(phrase, skill)
            self.assertIn(phrase, prompt)

    def test_config_compresses_only_dead_or_offline_characters(self):
        structure = read_doc("references/文件结构与锚点.md")

        for phrase in [
            "仅处理已死亡/已下线角色",
            "保留未死亡角色",
            "已死亡、已下线",
            "核心三项性格",
            "移除“绝对不能写什么”",
        ]:
            self.assertIn(phrase, structure)


class TestWorkflowContractDocs(unittest.TestCase):
    def test_rank_scan_has_a_formal_route_row(self):
        skill = read_doc("SKILL.md")

        route_rows = [line for line in skill.splitlines() if "rank-scan" in line]
        self.assertEqual(len(route_rows), 1)
        self.assertIn("references/扫榜流程.md", route_rows[0])
        self.assertIn("prompts/扫榜提示词.md", route_rows[0])

    def test_p0_review_modes_and_rank_scan_are_documented(self):
        skill = read_doc("SKILL.md")
        summary = read_doc("references/总结流程.md")
        review = read_doc("references/草稿审查流程.md")
        scan = read_doc("references/扫榜流程.md")
        prompt = read_doc("prompts/扫榜提示词.md")

        for phrase in ["扫榜与选题", "扫榜流程.md", "扫榜提示词.md"]:
            self.assertIn(phrase, skill)
        for phrase in ["细纲计划", "正文实际", "structural"]:
            self.assertIn(phrase, summary)
        for phrase in ["Requested Mode:", "Effective Mode:", "Fallback:", ".deslop-whitelist"]:
            self.assertIn(phrase, review)
        for phrase in ["样本少于 5 个", "选题决策.md", "不编造榜单数据"]:
            self.assertIn(phrase, scan + prompt)

    def test_skill_metadata_and_archive_contract_are_normalized(self):
        skill = read_doc("SKILL.md")
        structure = read_doc("references/文件结构与锚点.md")
        contract = read_doc("references/自动化脚本契约.md")

        self.assertIn("name: my-novel", skill)
        self.assertIn("总结/` 是总结的唯一标准根目录", structure)
        self.assertIn("FORBIDDEN_WORDS_NOT_CONFIGURED", contract)

    def test_outline_normalization_and_effective_sequence_are_documented(self):
        skill = read_doc("SKILL.md")
        prompt = read_doc("prompts/细纲整理提示词.md")
        process = read_doc("references/细纲整理流程.md")
        sequence = read_doc("references/章节序列.md")
        context = read_doc("references/上下文组装.md")

        for doc, phrases in [
            (skill, ["细纲整理", "正式细纲", "即使尚未审查，也必须作为有效历史正文参与上下文"]),
            (prompt, ["不使用“草稿”", "不得擅自新增主要事件", "事件展开"]),
            (process, ["不重新规划主线", "正文和上下文组装直接读取"]),
            (sequence, ["第49(1)章", "最近 3 个有效节点", "最近 1 个“主线锚点”"]),
            (context, ["有效节点组装", "已写出未审查", "第49(1)、第49(2)、第49(3)、第48章"]),
        ]:
            for phrase in phrases:
                self.assertIn(phrase, doc)

    def test_first_50_outline_requires_golden_three_micro_outline(self):
        skill = read_doc("SKILL.md")
        project = read_doc("references/项目定位.md")
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")
        readme = read_doc("README.md")

        for doc in [skill, project, prompt]:
            self.assertIn("第1-50章", doc)
            self.assertIn("黄金三章微操细纲", doc)
            self.assertIn("先生成", doc)

        self.assertNotIn("黄金三章微操细纲（可选）", readme)

    def test_readme_uses_five_chapter_execution_limit(self):
        readme = read_doc("README.md")

        self.assertIn("每批最多 5 章", readme)
        self.assertNotIn("每批约 10 章", readme)

    def test_windows_script_examples_include_py_launcher_fallback(self):
        contract = read_doc("references/自动化脚本契约.md")

        self.assertIn("py -3", contract)
        self.assertIn("Windows", contract)
        self.assertIn("python 不可用", contract)

    def test_epub_sync_contract_in_skill_docs(self):
        project = read_doc("references/项目定位.md")

        for phrase in [
            "$env:OneDrive\\小说",
            "书名子文件夹",
            "plan",
            "检查",
            "EPUB 和 plan 文件夹",
        ]:
            self.assertIn(phrase, project)


if __name__ == "__main__":
    unittest.main()
