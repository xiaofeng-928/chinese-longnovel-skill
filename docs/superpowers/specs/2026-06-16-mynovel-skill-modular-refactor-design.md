# MyNovel Skill Modular Refactor Design

## Goal

Refactor `MyNovel` from a large single-file workflow into a modular skill that keeps `SKILL.md` concise, moves detailed procedures into first-level `references/`, and reserves stable script interfaces for deterministic checks such as file locating, anchor replacement, word counts, AI-flavor scans, forbidden terms, and timeline anchors.

## Current State

- Authoritative skill directory: `C:\Users\Lenovo\.claude\skills\MyNovel`
- Baseline commit/tag: `v1.0`
- Current `SKILL.md` size: about 819 lines and about 23k characters.
- Existing supporting files: `prompts/` contains generation, review, repair, outline, and golden-three-chapter prompts.
- Current weakness: `SKILL.md` contains routing, project discovery, context assembly, drafting, review, repair, summary formats, consistency checks, file naming, anchor rules, and config templates in one body. This makes the workflow usable but attention-heavy.

## Design Principles

1. Keep `SKILL.md` as the router and hard-gate layer.
2. Move detailed workflows into first-level `references/` files, each linked directly from `SKILL.md`.
3. Keep existing `prompts/` stable in the first refactor pass.
4. Add script contracts before implementing scripts so both Claude Code and Codex know when script output is authoritative evidence.
5. Preserve current behavior: no route, window limit, archive rule, anchor rule, or context layer may be dropped during the split.
6. Avoid deep reference chains: `SKILL.md` must point directly to every reference file an agent may need.
7. Keep deterministic work scriptable over time; keep creative judgment with the AI.

## Target Structure

```text
MyNovel/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── prompts/
│   ├── 大纲生成提示词.md
│   ├── 分阶段大纲细化提示词.md
│   ├── 黄金三章微操细纲提示词.md
│   ├── 草稿生成提示词.md
│   ├── 草稿审查提示词.md
│   └── 草稿自动修复提示词.md
└── references/
    ├── project-discovery.md
    ├── file-layout-and-anchors.md
    ├── context-assembly.md
    ├── drafting-workflow.md
    ├── review-workflow.md
    ├── repair-workflow.md
    ├── summary-workflow.md
    ├── consistency-workflow.md
    └── automation-scripts-contract.md
```

## `SKILL.md` Responsibilities

`SKILL.md` should keep only the instructions that must always be visible after the skill triggers:

- Project selection and authoritative directories.
- Route table from user intent to workflow.
- Window limits: direct writing, review, and repair are limited to five chapters; outline refinement is limited to fifty chapters.
- Required reference file for each route.
- Required prompt file for each route.
- Global invariants:
  - Use PowerShell-native search in this workspace.
  - Do not skip context assembly for drafting, review, repair, or continuation.
  - Do not overwrite unrelated 50-chapter archive blocks.
  - Do not duplicate or break HTML anchors.
  - Stop on duplicate chapter files.
  - Treat stage summaries as the long-term memory layer, especially key time anchors.
- Script policy:
  - General workflow scripts live under `D:\ai小说\提示词和脚本`.
  - Project-specific export scripts such as `convert_to_epub.py` stay inside each novel project.
  - Script output is evidence for review reports and verification.

The target size for `SKILL.md` is 300-450 lines.

## Reference Files

### `project-discovery.md`

Own project detection and selection:

- Scan `D:\ai小说` to depth two for `novel-config.md`.
- Treat each containing folder as a novel project.
- If multiple projects match and the user did not name one, ask which book.
- If one project matches and the user intent is not new-project initialization, select it.
- EPUB generation rule: find and run the project-local `convert_to_epub.py`; if absent, adapt from another novel project.

### `file-layout-and-anchors.md`

Own file layout, naming, and archive mechanics:

- Standard novel project folders.
- Chapter file naming and status tags.
- Duplicate chapter file detection.
- 50-chapter archive calculation.
- Stage summary file calculation.
- Stable HTML anchors for outline, summary, review, and repair blocks.
- Replacement rules for re-generation, re-review, and re-repair.

### `context-assembly.md`

Own all context-building rules:

- Stage summaries as long-term memory.
- Recent three chapters as full text.
- Recent twenty chapter summaries, including summaries for the recent three chapters.
- Current full outline and next two chapter boundaries.
- Conditional伏笔補读: original chapter text plus corresponding summary.
- Logic dependency table: hard facts, key time anchors, character cognition, ability/resource state, relationship state, information flow, causal debts, and forbidden future mistakes.
- Pre-writing alignment gate.

### `drafting-workflow.md`

Own draft generation:

- Chapter range parsing.
- Five-chapter direct writing limit.
- Read `context-assembly.md`.
- Read `prompts/草稿生成提示词.md`.
- Write one chapter at a time.
- After each chapter, generate/update the chapter summary.
- Stop if outline and context conflict.

### `review-workflow.md`

Own review:

- Five-chapter direct review limit.
- Required inputs.
- Review dependency table, including key time anchors.
- A/B issue classes.
- Quantitative checks delegated to scripts when available.
- Review report archive rules.
- Default stop after review; do not auto-repair unless explicitly requested.

### `repair-workflow.md`

Own automatic repair:

- Explicit trigger only.
- Requires review report or user-specified issue.
- Five-chapter direct repair limit.
- Read target chapter, outline, writing rules, character profiles, and relevant report entries.
- Apply A-class fixes first.
- Run local recheck for modified paragraphs.
- Update review report, chapter summary, and file status.
- Verify all writes.

### `summary-workflow.md`

Own chapter and stage summaries:

- Chapter summary format.
- Stage summary format.
- `关键时间锚` rules:
  - Only record time anchors that affect future logic, relationships,伏笔, deadlines, or stage transitions.
  - Do not record daily time流水.
- Save/update rules using anchors.
- Session-end summary update workflow.

### `consistency-workflow.md`

Own cross-chapter and cross-stage checks:

- Read all stage summaries, recent three chapter texts, recent twenty chapter summaries, `novel-config.md`, and伏笔 tracking table.
- Check dead characters, ability overuse, relationship rollback, overdue伏笔, timeline conflict, repeated settings, evidence conflict, cognition overreach, information leak, causal break, and伏笔 meaning drift.
- Emit actionable report only.

### `automation-scripts-contract.md`

Own planned script interfaces:

- `novel_files.py`: locate project files, calculate archive paths, detect duplicate chapter files.
- `novel_anchor.py`: inspect and replace stable anchor blocks.
- `novel_lint.py`: word count, AI-flavor terms, forbidden terms, key time anchors, ability unlock scans.
- `novel_context.py`: assemble deterministic file lists for context layers.
- Scripts are optional at first, but when a script exists and matches the task, agents should prefer it over manual counting or ad hoc text scanning.

## Script Compatibility

The scripts should be ordinary local CLI scripts, not platform-specific hooks.

- Claude Code can run them through shell commands.
- Codex can run them through shell commands.
- Subagents can run them if the prompt gives the stable path and required arguments.
- The skill should not rely on hidden platform hooks.

Use stable workspace paths for shared workflow scripts:

```text
D:\ai小说\提示词和脚本\
```

Use project-local scripts only for project-specific exports and packaging:

```text
D:\ai小说\小说\<book>\convert_to_epub.py
```

## Migration Phases

### Phase 1: Structural Split

- Create `references/`.
- Move detailed prose from `SKILL.md` into reference files.
- Rewrite `SKILL.md` into a router and hard-gate document.
- Do not change prompts.
- Do not implement scripts yet.
- Validate that every current route points to a reference file and prompt file.

### Phase 2: Script Contract and First Script

- Add `automation-scripts-contract.md`.
- Implement the first script outside the skill package under `D:\ai小说\提示词和脚本`.
- Recommended first script: `novel_lint.py` for word count and AI-flavor scans because the thresholds are already quantified.
- Make review workflow cite script output as evidence.

### Phase 3: File Operations Scripts

- Implement `novel_files.py` for locating chapters and calculating archive targets.
- Implement `novel_anchor.py` for anchor inspection and safe replacement.
- Update references to prefer scripts when available.

### Phase 4: Forward Testing

- Test with realistic tasks:
  - Review a chapter with an injected time-anchor error.
  - Repair a chapter with duplicate chapter file conflict.
  - Generate/update a stage summary with only important time anchors.
  - Run AI-flavor scan and cite numerical output.
- Compare outcomes against `v1.0`.

## Validation Checklist

- `SKILL.md` frontmatter remains valid.
- `SKILL.md` stays under 500 lines.
- Every route from the original routing table still exists.
- Every direct workflow has a reference file.
- Every prompt referenced from `SKILL.md` exists.
- Five-chapter and fifty-chapter limits remain visible in `SKILL.md`.
- Key time anchors remain required in stage summaries.
- Review workflow still checks key time anchors.
- Anchor replacement rules remain available.
- Duplicate chapter file conflicts still stop the workflow.
- No script is required unless it exists and is applicable.
- Git tag `v1.0` remains as rollback baseline.

## Risks

- Over-splitting can make agents miss the right reference. Mitigation: keep all references one level deep and list exact route-to-reference mapping in `SKILL.md`.
- Keeping process docs inside the skill repository can clutter the package. Mitigation: remove or archive `docs/superpowers/` after the refactor if the final distributable should contain only skill assets.
- Script contracts can drift from real scripts. Mitigation: once scripts exist, each script must have a tested command example in `automation-scripts-contract.md`.
- The first refactor can accidentally change behavior. Mitigation: treat Phase 1 as a split-only change and compare routes against `v1.0`.

## Approval Gate

After this design is reviewed, create a detailed implementation plan before modifying `SKILL.md` or adding references.
