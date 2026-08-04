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
            "`novel-config.md` 是角色、能力与金手指设计的唯一权威源",
            "金手指设计档案",
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
    def test_long_form_examples_have_formal_routes_and_resources(self):
        skill = read_doc("SKILL.md")

        for phrase in [
            "范文入库",
            "范文拆书",
            "原创仿写",
            "references/范文拆书与仿写流程.md",
            "prompts/拆书与仿写提示词.md",
        ]:
            self.assertIn(phrase, skill)

    def test_long_form_example_library_contract_is_platform_then_genre(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            r"D:\ai小说\小说\范文",
            "<平台>范文",
            "<大类题材>",
            "番茄范文",
            "起点范文",
            "细分题材不建目录",
        ]:
            self.assertIn(phrase, workflow)

    def test_rank_scan_promotes_selected_candidates_without_implying_full_text(self):
        scan = read_doc("references/扫榜流程.md")
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in ["范文候选", "建立元数据范文", "正文状态：待导入"]:
            self.assertIn(phrase, scan)
        for phrase in ["合法全文", "不可拆书", "元数据"]:
            self.assertIn(phrase, workflow)

    def test_imitation_requires_project_level_migration_and_originality_gate(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        prompt = read_doc("prompts/拆书与仿写提示词.md")

        for phrase in [
            "参考素材.md",
            "plan/范文迁移方案.md",
            "原创性闸门",
            "人物与关系",
            "核心冲突",
            "事件因果链",
            "反转机制",
            "结局选择",
        ]:
            self.assertIn(phrase, workflow + prompt)

    def test_reference_driven_new_project_has_no_initialization_cycle(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        project = read_doc("references/项目定位.md")

        for phrase in ["范文驱动预初始化", "待生成总大纲", "最小项目壳"]:
            self.assertIn(phrase, workflow + project)

    def test_example_metadata_uses_fixed_states_and_outline_rechecks_originality(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        outline = read_doc("prompts/大纲生成提示词.md")

        for phrase in [
            "正文状态：待导入 / 局部已导入 / 全文已导入",
            "拆书状态：不可拆书 / 可用于开篇观察 / 可用于前期拆书 / 可用于深度拆书",
            "正文版本",
            "二次原创性复查",
            "plan/总大纲_待原创性复查.md",
            "复查通过前不得写回 `novel-config.md`",
        ]:
            self.assertIn(phrase, workflow + outline)

    def test_partial_example_defaults_to_50_and_stops_before_first_paid_chapter(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "默认获取第1-50章",
            "第一章完整收费正文",
            "最后一章完整免费正文",
            "第39章开始收费",
            "第1-38章",
            "不得绕过登录、风控、订阅或付费限制",
        ]:
            self.assertIn(phrase, workflow)

    def test_qidian_chapter_acquisition_uses_official_mobile_pages_and_access_markers(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "https://m.qidian.com/book/<bookId>/",
            "https://m.qidian.com/chapter/<bookId>/<chapterId>/",
            "firstChapterId",
            "nextChapterId",
            "vipStatus",
            "price",
            "isBuy",
            "正文完整性",
        ]:
            self.assertIn(phrase, workflow)

    def test_partial_teardown_has_chapter_thresholds_and_evidence_boundary(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        prompt = read_doc("prompts/拆书与仿写提示词.md")

        for phrase in [
            "少于30章",
            "30-49章",
            "达到50章",
            "只分析实际读到的章节",
            "不得推断未读章节",
            "局部正文",
        ]:
            self.assertIn(phrase, workflow + prompt)

    def test_rank_scan_is_limited_to_qidian_and_fanqie(self):
        scan = read_doc("references/扫榜流程.md")
        prompt = read_doc("prompts/扫榜提示词.md")

        for phrase in ["只支持番茄小说和起点中文网", "不得扩展到其他平台"]:
            self.assertIn(phrase, scan + prompt)

    def test_fanqie_scan_promotes_samples_as_metadata_for_manual_body_import(self):
        scan = read_doc("references/扫榜流程.md")
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "番茄范文候选",
            "建立元数据范文",
            "正文状态：待导入",
            "用户手动补充正文",
            "不得自动获取番茄正文",
        ]:
            self.assertIn(phrase, scan + workflow)

    def test_example_body_import_is_source_neutral_and_normalized(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "EPUB、TXT、Markdown",
            "直接粘贴",
            "未加密 EPUB",
            "正文.txt",
            "章节索引.md",
            "不按平台区分",
        ]:
            self.assertIn(phrase, workflow)

    def test_large_example_body_is_indexed_and_read_in_chapter_chunks(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        prompt = read_doc("prompts/拆书与仿写提示词.md")

        for phrase in [
            "写入本地文件不等于载入模型上下文",
            "不得一次性载入全部正文",
            "按章节连续分块读取",
            "第1-3章",
            "第4-10章",
            "第11-30章",
            "第31-50章",
        ]:
            self.assertIn(phrase, workflow + prompt)

    def test_full_source_is_preserved_while_default_analysis_stays_at_50(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "完整导入不等于全文分析",
            "不得截断或删除第51章以后的原始内容",
            "默认分析范围仍为连续第1-50章",
        ]:
            self.assertIn(phrase, workflow)

    def test_metadata_only_sample_does_not_require_a_teardown_report(self):
        skill = read_doc("SKILL.md")
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "元数据范文只复读 `元数据.md`",
            "有正文并执行拆书后",
            "不得创建空白 `拆书报告.md`",
        ]:
            self.assertIn(phrase, skill + workflow)

    def test_unspecified_scan_platform_requires_one_explicit_choice(self):
        scan = read_doc("references/扫榜流程.md")

        self.assertIn("先确认扫描番茄、起点或两者", scan)

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

    def test_readme_declares_release_version_1_5_0(self):
        readme = read_doc("README.md")

        self.assertIn("当前版本：**v1.5.0**", readme)
        self.assertNotIn("当前版本：**v1.5**", readme)

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


class TestGoldfingerDesignContracts(unittest.TestCase):
    def test_total_outline_requires_operating_dossier(self):
        prompt = read_doc("prompts/大纲生成提示词.md")
        for phrase in [
            "金手指设计档案",
            "运行闭环",
            "货物/资源池",
            "进货方式",
            "交易/变现方式",
            "成本与收益",
            "限制与代价",
            "升级树",
            "阶段演化表",
            "写回 `novel-config.md`",
        ]:
            self.assertIn(phrase, prompt)

    def test_stage_outline_tracks_goldfinger_payoff(self):
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")
        for phrase in [
            "金手指设计档案",
            "金手指发展台账",
            "进货/获取",
            "使用/消耗",
            "售卖/兑现",
            "结算/反馈",
            "本阶段新增解锁",
            "金手指存在感",
        ]:
            self.assertIn(phrase, prompt)

    def test_golden_three_requires_first_use_loop(self):
        prompt = read_doc("prompts/黄金三章微操细纲提示词.md")
        for phrase in [
            "金手指设计档案",
            "首次发现",
            "首次操作",
            "首次交易/验证",
            "下一次解锁",
        ]:
            self.assertIn(phrase, prompt)

    def test_draft_workflows_audit_goldfinger_contract(self):
        docs = [
            read_doc("prompts/草稿生成提示词.md"),
            read_doc("prompts/草稿审查提示词.md"),
            read_doc("prompts/草稿自动修复提示词.md"),
            read_doc("SKILL.md"),
        ]
        for doc in docs:
            self.assertIn("金手指设计档案", doc)
            self.assertIn("金手指闭环", doc)


class TestProtagonistStateRepositoryContracts(unittest.TestCase):
    def test_file_structure_defines_repository_as_current_state_authority(self):
        structure = read_doc("references/文件结构与锚点.md")
        for phrase in [
            "总结/主角状态仓库.md",
            "当前真实状态",
            "唯一当前状态权威源",
            "总大纲只维护计划状态",
            "章节总结只维护状态增量",
        ]:
            self.assertIn(phrase, structure)

    def test_summary_flow_records_deltas_without_copying_repository(self):
        summary = read_doc("references/总结流程.md")
        for phrase in [
            "主角状态增量",
            "主角状态仓库同步",
            "不复制完整仓库",
            "仓库是当前状态权威源",
        ]:
            self.assertIn(phrase, summary)

    def test_context_assembly_reads_repository_before_recent_deltas(self):
        context = read_doc("references/上下文组装.md")
        for phrase in [
            "主角状态仓库",
            "当前真实状态",
            "先读取仓库",
            "章节总结中的状态增量",
        ]:
            self.assertIn(phrase, context)

    def test_outline_prompts_separate_planned_state_from_actual_state(self):
        outline = read_doc("prompts/大纲生成提示词.md")
        stage = read_doc("prompts/分阶段大纲细化提示词.md")
        for phrase in ["主角状态仓库初始基线", "计划状态", "不写当前实际状态"]:
            self.assertIn(phrase, outline)
        for phrase in ["主角状态仓库", "状态增量", "仓库同步"]:
            self.assertIn(phrase, stage)

    def test_draft_workflows_require_repository_context(self):
        docs = [
            read_doc("prompts/草稿生成提示词.md"),
            read_doc("prompts/草稿审查提示词.md"),
            read_doc("prompts/草稿自动修复提示词.md"),
        ]
        for doc in docs:
            self.assertIn("主角状态仓库", doc)

    def test_consistency_check_uses_repository_as_dynamic_state_source(self):
        consistency = read_doc("references/一致性检查.md")
        for phrase in [
            "总结/主角状态仓库.md",
            "当前真实状态",
            "能力成长",
            "资源资产",
            "关系承诺",
            "信息认知",
            "后文禁止误写",
            "章节总结只核对状态增量",
        ]:
            self.assertIn(phrase, consistency)


if __name__ == "__main__":
    unittest.main()
