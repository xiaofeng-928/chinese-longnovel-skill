import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class TestLongFormEntryBoundary(unittest.TestCase):
    def test_entry_stays_a_router_instead_of_a_domain_rule_dump(self):
        skill = read_doc("SKILL.md")

        self.assertLessEqual(len(skill.splitlines()), 120)
        for phrase in [
            "入口只定义路由、全局不变量和执行边界",
            "不得把单一题材、金手指、文风、角色、状态仓库或某一生产阶段的细则追加到入口",
            "`references/` 是流程、状态权威关系和领域硬约束的唯一说明层",
        ]:
            self.assertIn(phrase, skill)

        for detail in [
            "2200-3000",
            "第51-100章细纲审查通过后",
            "总结/主角状态仓库.md",
            "正文状态：待导入",
            "待重蒸馏",
            "只有设计档案明确存在任务引擎",
        ]:
            self.assertNotIn(detail, skill)

    def test_every_routed_resource_exists(self):
        skill = read_doc("SKILL.md")
        paths = set(re.findall(r"`((?:references|prompts)/[^`]+\.md)`", skill))

        self.assertGreater(len(paths), 0)
        for relative_path in paths:
            self.assertTrue(
                (ROOT / Path(relative_path)).is_file(),
                f"Missing routed resource: {relative_path}",
            )


class TestDraftWordCountDocs(unittest.TestCase):
    def test_generation_targets_2200_to_3000_and_review_keeps_2000_floor(self):
        skill = read_doc("SKILL.md")
        outline = read_doc("prompts/大纲生成提示词.md")
        stage_outline = read_doc("prompts/分阶段大纲细化提示词.md")
        generation = read_doc("prompts/草稿生成提示词.md")
        workflow = read_doc("references/草稿生成流程.md")
        review = read_doc("prompts/草稿审查提示词.md")

        for doc in [outline, stage_outline, generation, workflow]:
            self.assertIn("2200-3000字", doc.replace(" ", ""))

        self.assertNotIn("2200-3000", skill)
        self.assertIn("scripts/count_chars.py", workflow)
        self.assertIn("实际字数进入2200-3000字前，不得更新总结或进入下一章", workflow)
        self.assertIn("低于2000字则报为B2问题", review)
        self.assertNotIn("低于2200字则报为B2问题", review)


class TestStageOutlineMemorySyncDocs(unittest.TestCase):
    def test_project_reference_defines_single_character_authority(self):
        skill = read_doc("SKILL.md")
        project = read_doc("references/项目定位.md")

        for phrase in [
            "细纲审查通过后",
            "角色卡、反派画像、称谓辈分和禁写清单写入 `novel-config.md`",
            "总大纲只在阶段目标、主线/反派线、伏笔追踪或下阶段铺垫发生变化时更新",
            "写回",
        ]:
            self.assertIn(phrase, project)

        self.assertIn("分阶段大纲细化", skill)
        self.assertNotIn("第51-100章细纲审查通过后", skill)
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
        project = read_doc("references/项目定位.md")
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")

        for phrase in [
            "第51-100章细纲",
            "前48章大纲",
            "第49-50章",
            "边界未写章节细纲",
        ]:
            self.assertIn(phrase, project)
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

    def test_qidian_defaults_to_all_free_chapters_before_paid_boundary(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")
        prompt = read_doc("prompts/拆书与仿写提示词.md")

        for phrase in [
            "起点官方公开章节默认连续获取到第一章完整收费正文之前",
            "不设 50 章下载上限",
            "第一章完整收费正文",
            "最后一章完整免费正文",
            "第39章开始收费",
            "第1-38章",
            "不得绕过登录、风控、订阅或付费限制",
        ]:
            self.assertIn(phrase, workflow + prompt)

        self.assertNotIn("默认最多保存第1-50章", workflow)

    def test_other_partial_sources_keep_a_bounded_default_range(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        self.assertIn("其他局部正文来源未约定范围时，默认规范化连续第1-50章", workflow)
        self.assertIn("默认分析范围仍为连续第1-50章", workflow)

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
            "直到首个收费边界或全书目录结束",
            "上架感言、请假条、公告、成绩汇报",
            "不写入 `正文.txt` 或 `章节索引.md`",
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

    def test_large_import_is_preserved_while_default_analysis_stays_at_50(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "完整入库不等于全文分析",
            "不得因默认分析范围而截断或删除第51章以后的内容",
            "默认分析范围仍为连续第1-50章",
            "已入库范围",
            "实际分析范围",
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
            (skill, ["细纲整理", "references/细纲整理流程.md"]),
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

        for doc in [project, prompt]:
            self.assertIn("第1-50章", doc)
            self.assertIn("黄金三章微操细纲", doc)
            self.assertIn("先生成", doc)

        self.assertIn("黄金三章微操细纲", skill)
        self.assertNotIn("第1-50章常规分阶段细纲", skill)
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


class TestStyleDistillationContracts(unittest.TestCase):
    def test_skill_routes_three_style_workflows(self):
        skill = read_doc("SKILL.md")

        for phrase in [
            "文风蒸馏",
            "项目文风确定",
            "文风校准",
            "references/文风蒸馏与执行流程.md",
            "prompts/文风蒸馏提示词.md",
            "prompts/项目文风编译提示词.md",
        ]:
            self.assertIn(phrase, skill)

    def test_source_dir_defines_all_style_assets(self):
        workflow = read_doc("references/范文拆书与仿写流程.md")

        for phrase in [
            "文风统计报告.md",
            "文风分析报告.md",
            "文风基因.md",
            "拆书与文风蒸馏分离",
            "文风状态",
            "待重蒸馏",
        ]:
            self.assertIn(phrase, workflow)

    def test_project_style_spec_is_unique_execution_authority(self):
        structure = read_doc("references/文件结构与锚点.md")
        reference = read_doc("references/文风蒸馏与执行流程.md")

        for phrase in [
            "文风/项目文风规范.md",
            "唯一执行权威",
            "文风校准记录.md",
            "文风配置",
            "文风变更规则",
        ]:
            self.assertIn(phrase, structure + reference)

    def test_context_assembly_reads_project_style_and_blocks_source(self):
        context = read_doc("references/上下文组装.md")

        for phrase in [
            "文风/项目文风规范.md",
            "文风执行表",
            "禁止把范文 `正文.txt`",
            "文风分析报告",
        ]:
            self.assertIn(phrase, context)

    def test_draft_prompts_include_style_version_and_character_priority(self):
        docs = [
            read_doc("prompts/草稿生成提示词.md"),
            read_doc("prompts/草稿审查提示词.md"),
            read_doc("prompts/草稿自动修复提示词.md"),
        ]
        for doc in docs:
            self.assertIn("项目文风规范", doc)
            self.assertIn("性格规格卡", doc)
        self.assertIn("本章文风执行表", read_doc("prompts/草稿生成提示词.md"))
        self.assertIn("文风执行核对", read_doc("prompts/草稿审查提示词.md"))

    def test_review_reports_style_check_block(self):
        prompt = read_doc("prompts/草稿审查提示词.md")
        for phrase in [
            "## 文风执行核对",
            "项目文风版本",
            "场景模式匹配",
            "硬规则",
            "软倾向整体一致性",
            "角色声音优先级",
            "原文重合检查",
        ]:
            self.assertIn(phrase, prompt)

    def test_outline_and_golden_three_consume_project_style(self):
        outline = read_doc("prompts/大纲生成提示词.md")
        stage = read_doc("prompts/分阶段大纲细化提示词.md")
        golden = read_doc("prompts/黄金三章微操细纲提示词.md")

        for phrase in ["项目文风规范"]:
            self.assertIn(phrase, outline)
            self.assertIn(phrase, stage)
            self.assertIn(phrase, golden)
        self.assertIn("场景文风模式", stage)

    def test_teardown_prompt_does_not_generate_style_gene_inline(self):
        prompt = read_doc("prompts/拆书与仿写提示词.md")
        for phrase in ["不顺带生成文风基因", "文风蒸馏", "文风蒸馏提示词.md"]:
            self.assertIn(phrase, prompt)

    def test_all_style_docs_forbid_identity_imitation_and_source_reuse(self):
        reference = read_doc("references/文风蒸馏与执行流程.md")
        distill = read_doc("prompts/文风蒸馏提示词.md")
        compile_prompt = read_doc("prompts/项目文风编译提示词.md")

        for doc in [reference, distill, compile_prompt]:
            self.assertIn("化身作者", doc)
            self.assertIn("原句", doc)
        self.assertIn("不包含来源原句", compile_prompt)

    def test_script_contract_documents_new_scripts(self):
        contract = read_doc("references/自动化脚本契约.md")
        for phrase in ["文风统计.py", "原文重合检查.py", "阻断", "需复核", "白名单"]:
            self.assertIn(phrase, contract)


class TestAIPolishContracts(unittest.TestCase):
    def test_long_form_generates_without_independent_ai_polish_stage(self):
        skill = read_doc("SKILL.md")
        flow = read_doc("references/草稿生成流程.md")
        prompt = read_doc("prompts/草稿生成提示词.md")

        for phrase in [
            "去 AI 味是正文生成的固有约束",
            "不另设生成后二次润稿阶段",
            "修复 AI 味或文风偏移",
        ]:
            self.assertIn(phrase, skill)
        for phrase in [
            "去AI味约束",
            "不是事后二次加工的补救项",
            "从下笔那一刻起",
            "字数守恒红线",
        ]:
            self.assertIn(phrase, prompt)
        self.assertIn("正式草稿审查", flow)
        self.assertFalse((ROOT / "references" / "去AI润稿流程.md").exists())
        self.assertFalse((ROOT / "prompts" / "去AI润稿提示词.md").exists())

    def test_root_does_not_advertise_ai_polish_as_independent_stage(self):
        root = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("去 AI 润稿", root)
        self.assertNotIn("short-form", root)
        self.assertNotIn("短篇", root)


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
        ]
        for doc in docs:
            self.assertIn("金手指设计档案", doc)
            self.assertIn("金手指闭环", doc)


class TestGoldfingerDesignCapabilityContracts(unittest.TestCase):
    def test_skill_routes_design_and_stage_planning(self):
        skill = read_doc("SKILL.md")
        reference = read_doc("references/金手指设计与运营.md")
        prompt = read_doc("prompts/金手指阶段规划提示词.md")
        for phrase in [
            "金手指设计/重构",
            "金手指阶段规划",
            "references/金手指设计与运营.md",
            "prompts/金手指设计提示词.md",
            "prompts/金手指阶段规划提示词.md",
        ]:
            self.assertIn(phrase, skill)
        self.assertIn("plan/金手指发展_第X-Y章.md", reference + prompt)

    def test_design_prompt_makes_ai_propose_and_stress_test(self):
        prompt = read_doc("prompts/金手指设计提示词.md")
        for phrase in [
            "2-3套",
            "推荐方案",
            "压力测试",
            "用户校准",
            "机制画像",
            "成长拓扑",
            "经济健康",
            "任务合理性闸门",
            "写回 `novel-config.md`",
        ]:
            self.assertIn(phrase, prompt)

    def test_reference_defines_task_engine_and_store_boundaries(self):
        reference = read_doc("references/金手指设计与运营.md")
        for phrase in [
            "小说类型与金手指机制正交",
            "系统商店",
            "主角经营商店",
            "任务生成链",
            "任务合理性闸门",
            "主角能动性",
            "全知任务",
            "救场任务",
            "追溯奖励",
        ]:
            self.assertIn(phrase, reference)

    def test_stage_plan_owns_store_task_and_five_chapter_cycle(self):
        prompt = read_doc("prompts/金手指阶段规划提示词.md")
        for phrase in [
            "资源预算",
            "系统商店快照",
            "经营商店快照",
            "阶段任务池",
            "感知来源",
            "奖励预算",
            "五章玩法循环",
            "战略跃升",
            "plan/金手指发展_第X-Y章.md",
        ]:
            self.assertIn(phrase, prompt)

    def test_stage_outline_consumes_goldfinger_stage_plan(self):
        prompt = read_doc("prompts/分阶段大纲细化提示词.md")
        for phrase in [
            "同范围金手指阶段规划",
            "系统任务交互",
            "金手指决策",
            "商店状态变化",
            "任务状态",
            "下一轮期待",
        ]:
            self.assertIn(phrase, prompt)

    def test_context_and_summary_support_optional_separate_repository(self):
        context = read_doc("references/上下文组装.md")
        repository = read_doc("references/主角状态仓库.md")
        summary = read_doc("references/总结流程.md")
        structure = read_doc("references/文件结构与锚点.md")
        for doc in [context, repository, summary, structure]:
            self.assertIn("总结/金手指状态仓库.md", doc)
        self.assertIn("任意两项", repository)
        self.assertIn("禁止双重权威", repository)

    def test_draft_review_detects_task_and_choice_failures(self):
        generation = read_doc("prompts/草稿生成提示词.md")
        review = read_doc("prompts/草稿审查提示词.md")
        repair = read_doc("prompts/草稿自动修复提示词.md")
        for phrase in ["任务感知来源", "主角选择", "场景化结算"]:
            self.assertIn(phrase, generation)
        for phrase in [
            "虚假选择",
            "全知任务",
            "救场任务",
            "追溯奖励",
            "判定漂移",
            "木偶驱动",
        ]:
            self.assertIn(phrase, review)
        self.assertIn("structural", repair)
        self.assertIn("退回金手指阶段规划", repair)


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
