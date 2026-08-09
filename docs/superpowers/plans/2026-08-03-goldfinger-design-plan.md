# 金手指设计全链路 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make long-form outline workflows design, track, and audit a goldfinger's operating loop, growth, and chapter-level payoff.

**Architecture:** The total-outline prompt owns a reusable goldfinger design dossier and whole-book evolution map. Stage-outline and golden-three prompts turn that dossier into chapter obligations; draft generation, review, and repair consume the same dossier and detect drift, missing validation, and low presence. `novel-config.md` remains the persistent authority for the dossier.

**Tech Stack:** Markdown skill prompts, Python `unittest` documentation contracts, PowerShell validation.

---

### Task 1: Lock the contract with failing tests

**Files:**
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\tests\test_skill_docs.py`

- [ ] Add assertions requiring the dossier, stage ledger, golden-three first-use loop, and draft audit fields.
- [ ] Run the focused tests and confirm they fail against the current prompts.

### Task 2: Add the reusable dossier to total outline generation

**Files:**
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\大纲生成提示词.md`

- [ ] Expand the goldfinger interview and confirmation summary.
- [ ] Require an operating dossier, item/resource pool, acquisition and transaction loops, constraints/costs, upgrade tree, and stage evolution table.
- [ ] Require the dossier to be written to the persistent config sync target.

### Task 3: Bind stage and golden-three planning to the dossier

**Files:**
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\分阶段大纲细化提示词.md`
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\黄金三章微操细纲提示词.md`

- [ ] Add dossier input and a per-stage ledger for use, acquisition, sale, settlement, unlocks, costs, and external feedback.
- [ ] Require the first three chapters to show discovery, first operation, first transaction/validation, and a concrete next unlock hook.

### Task 4: Extend generation, review, repair, and routing contracts

**Files:**
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\草稿生成提示词.md`
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\草稿审查提示词.md`
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\prompts\草稿自动修复提示词.md`
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\long-form\SKILL.md`

- [ ] Require the dossier in context and logical dependency checks.
- [ ] Add hard/quality checks for rule drift, missing operating loops, missing validation, and low goldfinger presence.
- [ ] Route the dossier as a first-class persistent memory layer.

### Task 5: Verify

- [ ] Run focused and full MyNovel tests.
- [ ] Run the skill quick validator if available.
- [ ] Re-read all changed files and confirm the dossier fields are consistent.
