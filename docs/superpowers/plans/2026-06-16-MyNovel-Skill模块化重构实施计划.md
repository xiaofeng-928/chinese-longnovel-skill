# MyNovel Skill 模块化重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md` 从单文件长工作流重构为“短入口 + 中文 `references/` + 中文 `scripts/` 预留”的模块化 Skill。

**Architecture:** `SKILL.md` 保留 frontmatter、项目定位入口、路由表、硬性闸门和参考文档导航；详细流程移入一级 `references/` 中文文档。第一轮不改 `prompts/` 语义，不实现真实脚本，只创建 `scripts/` 目录并在 `自动化脚本契约.md` 中规定未来中文脚本接口。

**Tech Stack:** Markdown Skill 文档、PowerShell 原生命令、Git、未来 Python 脚本接口。

---

## 文件结构

- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md`
  - 只保留入口、路由、硬规则、章节窗口限制、参考文档导航、提示词导航、脚本策略。
  - 目标少于 500 行，理想范围 300-450 行。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\项目定位.md`
  - 负责项目扫描、项目选择、新小说初始化入口、大纲类短流程归属说明。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\文件结构与锚点.md`
  - 负责目录结构、章节命名、50章归档、阶段总结定位、HTML 锚点与替换规则。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\上下文组装.md`
  - 负责写作、审查、修复、续写前的上下文读取层级和逻辑依赖表。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿生成流程.md`
  - 负责正文生成、五章直写限制、写前校准、写后总结。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿审查流程.md`
  - 负责审查输入、五章直审限制、A/B 类问题、关键时间锚检查、报告归档。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿修复流程.md`
  - 负责显式修复触发、A 类优先修复、局部复查、状态更新。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\总结流程.md`
  - 负责章节总结、阶段总结、关键时间锚、会话结束流程。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\一致性检查.md`
  - 负责跨章节、跨阶段一致性检查清单和报告格式。
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\自动化脚本契约.md`
  - 负责未来中文脚本接口：`小说质检.py`、`小说文件.py`、`小说锚点.py`、`小说上下文.py`。
- Create directory: `C:\Users\Lenovo\.claude\skills\MyNovel\scripts\`
  - 第一轮只创建目录，不创建脚本文件。

## 迁移映射

| 当前 `SKILL.md` 区段 | 迁移目标 |
|---|---|
| `启动：定位小说项目` | `references\项目定位.md`，`SKILL.md` 保留简短入口 |
| `资源目录：提示词与通用脚本` | `SKILL.md` 改为 Skill 内置 `scripts/` 策略，细节进 `自动化脚本契约.md` |
| `智能路由` | `SKILL.md` 保留完整路由表 |
| `任务范围闸门` | `SKILL.md` 保留硬规则，细节同步到对应流程文档 |
| `阶段0：新小说初始化` | `references\项目定位.md` 和 `references\文件结构与锚点.md` |
| `阶段1：大纲生成` | `SKILL.md` 保留短路由，并指向 `prompts\大纲生成提示词.md` |
| `阶段2：分阶段大纲细化`、`黄金三章微操细纲生成` | `SKILL.md` 保留范围闸门和提示词导航 |
| `阶段3：草稿生成`、`上下文组装`、`写前校准` | `references\上下文组装.md`、`references\草稿生成流程.md` |
| `阶段4：草稿审查`、`审查进度表格式` | `references\草稿审查流程.md` |
| `阶段4.3 修复确认`、`阶段4.4 自动修复` | `references\草稿修复流程.md` |
| `阶段5：章节总结生成`、`阶段6：阶段总结更新`、`会话结束流程` | `references\总结流程.md` |
| `阶段7：一致性检查` | `references\一致性检查.md` |
| `文件夹结构约定`、`章节文件命名约定`、`50章分块文件定位`、`novel-config.md 必须包含的字段` | `references\文件结构与锚点.md` |

### Task 1: 预检并确认基线

**Files:**
- Read: `C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md`
- Read: `C:\Users\Lenovo\.claude\skills\MyNovel\docs\superpowers\specs\2026-06-16-mynovel-skill-modular-refactor-design.md`
- Read directory: `C:\Users\Lenovo\.claude\skills\MyNovel\prompts`

- [ ] **Step 1: 确认工作区干净**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' status --short
```

Expected: no output. If there is output, inspect it and do not overwrite unrelated user changes.

- [ ] **Step 2: 确认当前基线 tag**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' tag --list 'v1.0'
```

Expected:

```text
v1.0
```

- [ ] **Step 3: 记录当前入口规模**

Run:

```powershell
(Get-Content -LiteralPath 'C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md' -Encoding UTF8).Count
```

Expected: current count is greater than `500`; use this as the before value.

### Task 2: 创建资源目录

**Files:**
- Create directory: `C:\Users\Lenovo\.claude\skills\MyNovel\references`
- Create directory: `C:\Users\Lenovo\.claude\skills\MyNovel\scripts`

- [ ] **Step 1: 创建目录**

Run:

```powershell
New-Item -ItemType Directory -Force -Path 'C:\Users\Lenovo\.claude\skills\MyNovel\references'
New-Item -ItemType Directory -Force -Path 'C:\Users\Lenovo\.claude\skills\MyNovel\scripts'
```

Expected: both directories exist.

- [ ] **Step 2: 验证目录**

Run:

```powershell
Get-ChildItem -LiteralPath 'C:\Users\Lenovo\.claude\skills\MyNovel' -Directory |
  Where-Object { $_.Name -in @('references','scripts') } |
  Select-Object Name
```

Expected:

```text
references
scripts
```

- [ ] **Step 3: Commit**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- references scripts
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'chore: add MyNovel resource directories'
```

Expected: commit succeeds with only the two new directories if Git tracks them through added files later; if empty directories are not tracked, skip this commit and commit after Task 3 creates reference files.

### Task 3: 写入项目、结构、上下文三份基础参考文档

**Files:**
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\项目定位.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\文件结构与锚点.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\上下文组装.md`

- [ ] **Step 1: 创建 `项目定位.md`**

Content requirements:

```markdown
# 项目定位

## 职责

负责小说项目检测、选择、新小说初始化入口，以及大纲类任务的项目归属判断。

## 项目扫描

- 工作区根目录是 `D:\ai小说`。
- 扫描根目录下最多两层子目录，查找 `novel-config.md`。
- 每个包含 `novel-config.md` 的目录视为一本小说项目。
- 如果用户意图是“开新小说”“新建小说”或提供了与已有项目不匹配的新总大纲，进入新小说初始化。
- 如果只有一个小说项目且不是开新坑，自动选中。
- 如果有多个小说项目且用户没有指定，停止并询问要操作哪一本。

## 新小说初始化

- 从用户提供的总大纲提取书名、类型、核心卖点、主角、主线目标、阶段划分、写作铁律、角色档案、伏笔追踪表和世界观设定。
- 生成安全的文件夹名：`题材-书名`。
- 创建标准项目结构；具体目录结构以 `文件结构与锚点.md` 为准。
- 生成 `novel-config.md`；字段格式以 `文件结构与锚点.md` 为准。
- 初始化完成后只报告创建了哪些文件和下一步建议，不直接开始写正文。

## 大纲类任务

- 总大纲生成读取 `prompts/大纲生成提示词.md`。
- 分阶段大纲细化读取 `prompts/分阶段大纲细化提示词.md`。
- 黄金三章微操细纲读取 `prompts/黄金三章微操细纲提示词.md`。
- 分阶段大纲细化一次最多处理 50 章；超过 50 章必须要求拆分。

## EPUB 生成

- 生成 EPUB 时，优先查找当前小说项目目录下的 `convert_to_epub.py`。
- 如果当前项目没有该脚本，再参考其他小说项目中的已有脚本改造。
- EPUB 脚本属于单本小说项目专属脚本，不放入 MyNovel Skill 的 `scripts/`。
```

- [ ] **Step 2: 创建 `文件结构与锚点.md`**

Content requirements:

````markdown
# 文件结构与锚点

## 职责

负责小说项目目录结构、文件命名、50章归档、阶段总结定位、HTML 锚点和安全替换规则。

## 标准项目结构

```text
小说项目/
├── novel-config.md
├── 大纲/
├── 正文/
├── 总结/
├── 审查报告/
└── 修复记录/
```

## 章节文件命名

- 正文章节文件使用第几章和状态标签命名。
- 同一章出现多个正文文件时必须停止，并让用户确认哪个是权威版本。
- 不得擅自删除、覆盖或合并同章冲突文件。

## 50章归档

- 大纲、章节总结、审查报告、修复记录按 50 章一个归档文件管理。
- 第 1-50 章归入第一个分块，第 51-100 章归入第二个分块，以此类推。
- 一次只处理 5 章正文，不改变 50 章归档规则。

## 阶段总结定位

- 阶段总结是长期记忆层。
- 阶段总结文件按 `novel-config.md` 中的阶段划分定位。
- 阶段总结必须包含 `关键时间锚`。

## HTML 锚点

- 章节大纲、章节总结、审查报告、修复记录都使用稳定 HTML 注释锚点包裹。
- 重生成、重审、重修时，只替换目标锚点块。
- 不得重复追加同一锚点块。
- 不得覆盖同一 50 章归档文件里的无关章节块。

## `novel-config.md` 字段

- 基本信息：书名、类型、题材、卖点、主角、主线目标。
- 阶段划分：阶段名、章节范围、阶段目标。
- 写作铁律：节奏、视角、禁用写法、爽点规则。
- 角色档案：身份、关系、目标、认知边界、能力边界、性格规格卡。
- 伏笔追踪表：伏笔、埋设章、预计回收章、当前状态。
- 世界观设定：规则、限制、资源、势力。
````

- [ ] **Step 3: 创建 `上下文组装.md`**

Content requirements:

```markdown
# 上下文组装

## 职责

负责正文生成、续写、草稿审查、自动修复前必须读取的上下文层级。

## 必读上下文

- `novel-config.md`
- 当前阶段总结和所有必要的前置阶段总结
- 最近 3 章正文全文
- 最近 20 章章节总结，且必须包含最近 3 章正文对应总结
- 本章完整大纲
- 后续 2 章边界大纲
- 角色档案、写作铁律、伏笔追踪表

## 伏笔补读

- 如果本章涉及早期伏笔，必须补读伏笔埋设原章正文。
- 同时补读该章章节总结。
- 只补读与本章逻辑相关的伏笔，不扩大到无关章节。

## 逻辑依赖表

组装上下文后，先提炼逻辑依赖表，再进入正文、审查或修复。

逻辑依赖表必须包含：

- 硬事实
- 关键时间锚
- 角色认知
- 能力/资源状态
- 关系状态
- 信息流边界
- 因果债
- 后文禁止误写

## 写前校准闸门

- 对照本章大纲和上下文硬事实。
- 如果大纲与已发生正文冲突，停止并报告冲突点。
- 不得为了顺着大纲而改写既有事实。
- 不得擅自新增主线事件、角色、能力、设定或伏笔。
```

- [ ] **Step 4: Commit**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- references
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'docs: add MyNovel core reference docs'
```

Expected: commit includes the three reference files.

### Task 4: 写入草稿、审查、修复三份流程文档

**Files:**
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿生成流程.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿审查流程.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\草稿修复流程.md`

- [ ] **Step 1: 创建 `草稿生成流程.md`**

Include these required sections:

```markdown
# 草稿生成流程

## 职责

负责单章或五章以内正文草稿生成。

## 范围限制

- 正文创作一次最多 5 章。
- 超过 5 章必须停止并要求拆分，或等待后续批处理脚本。
- “继续写”但未指定范围时，默认处理下一章或下一组最多 5 章。

## 执行步骤

1. 解析章节范围。
2. 按 `上下文组装.md` 组装每一章上下文。
3. 执行写前大纲-上下文校准闸门。
4. 读取 `prompts/草稿生成提示词.md`。
5. 按章节顺序逐章生成正文。
6. 每写完一章，立即按 `总结流程.md` 更新章节总结。
7. 复读落盘文件，确认章节号、标题、状态和锚点正确。

## 阻断条件

- 大纲和上下文冲突。
- 同一章存在多个正文文件。
- 本章所需大纲缺失。
- 伏笔原章或关键总结缺失，且该伏笔影响本章逻辑。
```

- [ ] **Step 2: 创建 `草稿审查流程.md`**

Include these required sections:

```markdown
# 草稿审查流程

## 职责

负责草稿审查，只输出审查报告，不默认修改正文。

## 范围限制

- 草稿审查一次最多 5 章。
- 超过 5 章必须要求拆分。

## 审查输入

- 目标正文
- 本章大纲
- 最近 20 章章节总结
- 最近 3 章正文
- 当前阶段总结
- `novel-config.md`
- 角色档案、伏笔追踪表、写作铁律
- 可用脚本输出

## 逻辑依赖表

审查前必须派生审查逻辑依赖表，且必须包含关键时间锚。

## 问题分类

- A 类：硬伤，必须修。包括时间线矛盾、角色认知越界、硬事实冲突、能力越级、信息流泄露、伏笔含义变形。
- B 类：风险或体验问题。包括节奏拖沓、AI味偏重、爽点弱、表达重复、情绪铺垫不足。

## 脚本证据

- 如果 `scripts/小说质检.py` 存在且适用，优先运行脚本。
- 审查报告引用脚本输出作为字数、AI味、禁用词等量化证据。
- 如果脚本不存在，报告中注明未使用脚本，不临时创建替代脚本。

## 审查后动作

- 默认停止，不自动修复。
- 用户明确说“修复”“审查并修复”时，进入 `草稿修复流程.md`。
```

- [ ] **Step 3: 创建 `草稿修复流程.md`**

Include these required sections:

```markdown
# 草稿修复流程

## 职责

负责用户显式要求后的自动修复。

## 触发条件

- 用户明确要求“修复”“审查并修复”“fix”。
- 有审查报告，或用户明确指出需要修复的问题。

## 范围限制

- 自动修复一次最多 5 章。
- 超过 5 章必须要求拆分。

## 修复输入

- 目标正文
- 本章大纲
- 审查报告或用户指出的问题
- 写作铁律
- 角色档案
- 相关章节总结和阶段总结

## 修复顺序

1. 先修 A 类硬伤。
2. 再处理 B 类体验问题。
3. 每次只改与问题相关的段落。
4. 修改后做局部复查。
5. 更新审查报告进度、章节总结和章节文件状态。
6. 复读落盘文件确认修改生效。

## 禁止行为

- 不得为修复一个问题擅自新增主线事件。
- 不得扩大修改范围到无关段落。
- 不得跳过审查报告中的 A 类问题。
```

- [ ] **Step 4: Commit**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- references
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'docs: add MyNovel draft review repair references'
```

Expected: commit includes the three workflow reference files.

### Task 5: 写入总结、一致性、脚本契约文档

**Files:**
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\总结流程.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\一致性检查.md`
- Create: `C:\Users\Lenovo\.claude\skills\MyNovel\references\自动化脚本契约.md`

- [ ] **Step 1: 创建 `总结流程.md`**

Include these required sections:

```markdown
# 总结流程

## 职责

负责章节总结、阶段总结和会话结束补齐。

## 章节总结

章节总结记录本章对后文有用的信息：

- 关键事件
- 角色状态变化
- 本章确立的硬事实
- 角色认知变化
- 能力/资源变化
- 信息流边界
- 因果债与未解决冲突
- 伏笔操作
- 后文禁止误写
- 章末状态

时间只在影响行动逻辑、期限、伏笔、关系或后文因果时记录。

## 阶段总结

阶段总结是长期记忆层，必须包含：

- 关键事件
- 关键时间锚
- 角色状态快照
- 角色死亡/退出
- 关系变化
- 主角能力/资源
- 关键硬事实
- 信息流边界
- 因果债与未解决冲突
- 后文禁止误写
- 未回收伏笔

## 关键时间锚

- 只记录影响后文逻辑、角色关系、伏笔、倒计时、阶段衔接的重要时间。
- 不记录每章日常时间流水。
- 如果时间锚会影响交通、等待、治疗、约定、死亡、失踪、追杀、考试、比赛、营业时间或倒计时，必须记录。

## 会话结束流程

- 检查本轮新增或修改章节是否已有章节总结。
- 补齐缺失的章节总结。
- 更新当前阶段总结。
- 只替换目标锚点块，不覆盖无关章节。
```

- [ ] **Step 2: 创建 `一致性检查.md`**

Include these required sections:

```markdown
# 一致性检查

## 职责

负责跨章节、跨阶段检查角色、时间线、伏笔、能力、信息流和因果一致性。

## 检查输入

- 全部阶段总结
- 最近 3 章正文
- 最近 20 章章节总结
- `novel-config.md`
- 伏笔追踪表
- 相关伏笔原章正文

## 检查项

- 死人复活或退出角色无故回归
- 能力越级或资源凭空出现
- 关系状态回退
- 伏笔超期或含义变形
- 时间线矛盾
- 重复设定或设定冲突
- 前文证据冲突
- 角色认知越界
- 信息流泄露
- 因果断裂

## 输出格式

- 硬伤：必须修。
- 风险：需要确认。
- 伏笔状态：列出未回收和异常伏笔。
- 通过项：简短列出已核对无问题的关键项。
```

- [ ] **Step 3: 创建 `自动化脚本契约.md`**

Include these required sections:

````markdown
# 自动化脚本契约

## 职责

规定未来 MyNovel Skill 内置脚本的文件名、用途、调用方式和输出用途。

## 脚本目录

通用脚本放在：

```text
C:\Users\Lenovo\.claude\skills\MyNovel\scripts\
```

单本小说专属导出脚本仍放在小说项目目录，例如 `convert_to_epub.py`。

## 计划脚本

- `小说质检.py`：字数统计、AI味词、禁用词、关键时间锚、能力解锁扫描。
- `小说文件.py`：定位项目文件、计算 50 章归档路径、检测同章多文件。
- `小说锚点.py`：检查稳定锚点、替换目标锚点块。
- `小说上下文.py`：确定性组装上下文文件列表。

## 调用原则

- 脚本是普通本地命令行工具，不依赖隐藏 hook。
- Claude Code、Codex 和子 agent 都通过 shell 调用脚本。
- 脚本存在且适用时，优先使用脚本输出作为证据。
- 脚本不存在时，不临时创建替代脚本；在报告中注明未使用脚本。
- 脚本输出可写入审查报告、验证结论和修复记录。

## 第一轮状态

第一轮结构拆分只创建 `scripts/` 目录，不实现脚本文件。
````

- [ ] **Step 4: Commit**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- references scripts
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'docs: add MyNovel summary consistency script references'
```

Expected: commit includes the three reference files and the `scripts` directory if it contains a tracked marker file. If Git does not track the empty `scripts` directory, add `scripts\.gitkeep` as an empty file and commit it.

### Task 6: 重写 `SKILL.md` 为入口路由文档

**Files:**
- Modify: `C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md`

- [ ] **Step 1: 保留 frontmatter**

Keep the existing frontmatter exactly unless the description no longer matches the routing behavior:

```markdown
---
name: MyNovel
description: 网络小说写作工作流。覆盖新小说初始化、大纲生成、分阶段细纲、草稿生成、草稿审查、显式修复、章节总结、一致性检查、续写上下文组装。仅当用户请求明确处于小说写作上下文时触发，例如提到小说、章节、第X章、正文、草稿、大纲、角色、伏笔、续写、新小说、开新坑等；不要因单独的"审查""总结""结束"等通用词触发，也不要用于审查 skill/代码/文档/配置/服务器任务。
---
```

- [ ] **Step 2: 写入入口职责**

`SKILL.md` body must include:

```markdown
# MyNovel——网络小说写作工作流

你是网络小说写作助手。每次执行小说正文创作、续写、审查、修复、总结、一致性检查前，先选择小说项目，再按路由读取对应参考文档和提示词。

## 权威目录

- Skill 根目录：`C:\Users\Lenovo\.claude\skills\MyNovel`
- 提示词目录：`C:\Users\Lenovo\.claude\skills\MyNovel\prompts`
- 参考文档目录：`C:\Users\Lenovo\.claude\skills\MyNovel\references`
- 通用脚本目录：`C:\Users\Lenovo\.claude\skills\MyNovel\scripts`
- 小说工作区：`D:\ai小说`
```

- [ ] **Step 3: 写入硬规则**

`SKILL.md` must include these rules visibly:

```markdown
## 全局硬规则

- 在 `D:\ai小说` 工作区搜索文件和文本时，使用 PowerShell 原生命令，例如 `Get-ChildItem`、`Select-String`、`Where-Object`。
- 不使用 `rg`、`ripgrep` 或 `grep`。
- 正文生成、续写、审查、修复不得跳过上下文组装。
- 正文直写、草稿审查、自动修复一次最多 5 章。
- 分阶段大纲细化一次最多 50 章。
- 不得覆盖同一 50 章归档文件里的无关章节块。
- 不得重复追加或破坏 HTML 锚点。
- 同一章出现多个正文文件时，停止并让用户确认权威文件。
- 阶段总结是长期记忆层，必须维护关键时间锚。
- 脚本存在且适用时，优先使用脚本结果作为证据；脚本不存在时注明未使用脚本。
```

- [ ] **Step 4: 写入路由表**

Keep all original route intents and add required references/prompts columns:

```markdown
## 智能路由

| 用户意图 | 工作流 | 必读参考文档 | 必读提示词 |
|---|---|---|---|
| 新小说、开新坑、新建小说、粘贴新总大纲 | 新小说初始化 | `项目定位.md`、`文件结构与锚点.md` | 无 |
| 大纲、总大纲、规划剧情 | 大纲生成 | `项目定位.md` | `大纲生成提示词.md` |
| 细化大纲、分阶段大纲、第X-X章大纲 | 分阶段大纲细化 | `项目定位.md`、`文件结构与锚点.md` | `分阶段大纲细化提示词.md` |
| 黄金三章、前三章微操 | 黄金三章微操细纲 | `项目定位.md`、`文件结构与锚点.md` | `黄金三章微操细纲提示词.md` |
| 写第X章、草稿、写下一章 | 草稿生成 | `上下文组装.md`、`草稿生成流程.md`、`总结流程.md` | `草稿生成提示词.md` |
| 审查第X章、审查草稿、检查草稿 | 草稿审查 | `上下文组装.md`、`草稿审查流程.md`、`文件结构与锚点.md`、`自动化脚本契约.md` | `草稿审查提示词.md` |
| 审查并修复、review and fix | 草稿审查后自动修复 | `上下文组装.md`、`草稿审查流程.md`、`草稿修复流程.md` | `草稿审查提示词.md`、`草稿自动修复提示词.md` |
| 修复第X章、fix | 自动修复 | `上下文组装.md`、`草稿修复流程.md` | `草稿自动修复提示词.md` |
| 修好了、已修复、修改完毕 | 修复确认 | `草稿修复流程.md`、`文件结构与锚点.md` | 无 |
| 总结第X章、章节总结 | 章节总结 | `总结流程.md`、`文件结构与锚点.md` | 无 |
| 一致性、矛盾、对不上 | 一致性检查 | `一致性检查.md`、`上下文组装.md` | 无 |
| 续写、继续写、接着写 | 续写并生成草稿 | `上下文组装.md`、`草稿生成流程.md`、`总结流程.md` | `草稿生成提示词.md` |
| 今天小说就到这、本轮章节结束 | 会话结束流程 | `总结流程.md`、`文件结构与锚点.md` | 无 |
```

- [ ] **Step 5: 写入参考文档导航**

`SKILL.md` must link every reference directly:

```markdown
## 参考文档

- `references/项目定位.md`
- `references/文件结构与锚点.md`
- `references/上下文组装.md`
- `references/草稿生成流程.md`
- `references/草稿审查流程.md`
- `references/草稿修复流程.md`
- `references/总结流程.md`
- `references/一致性检查.md`
- `references/自动化脚本契约.md`
```

- [ ] **Step 6: Commit**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- SKILL.md
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'refactor: split MyNovel skill into routed references'
```

Expected: commit modifies only `SKILL.md`.

### Task 7: 验证引用、规模和关键规则

**Files:**
- Verify: `C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md`
- Verify: `C:\Users\Lenovo\.claude\skills\MyNovel\references\*.md`
- Verify: `C:\Users\Lenovo\.claude\skills\MyNovel\prompts\*.md`

- [ ] **Step 1: 验证 `SKILL.md` 行数**

Run:

```powershell
(Get-Content -LiteralPath 'C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md' -Encoding UTF8).Count
```

Expected: less than `500`.

- [ ] **Step 2: 验证参考文档存在**

Run:

```powershell
$refs = @(
  '项目定位.md',
  '文件结构与锚点.md',
  '上下文组装.md',
  '草稿生成流程.md',
  '草稿审查流程.md',
  '草稿修复流程.md',
  '总结流程.md',
  '一致性检查.md',
  '自动化脚本契约.md'
)
$missing = $refs | Where-Object {
  -not (Test-Path -LiteralPath (Join-Path 'C:\Users\Lenovo\.claude\skills\MyNovel\references' $_))
}
$missing
```

Expected: no output.

- [ ] **Step 3: 验证提示词文件存在**

Run:

```powershell
$prompts = @(
  '大纲生成提示词.md',
  '分阶段大纲细化提示词.md',
  '黄金三章微操细纲提示词.md',
  '草稿生成提示词.md',
  '草稿审查提示词.md',
  '草稿自动修复提示词.md'
)
$missing = $prompts | Where-Object {
  -not (Test-Path -LiteralPath (Join-Path 'C:\Users\Lenovo\.claude\skills\MyNovel\prompts' $_))
}
$missing
```

Expected: no output.

- [ ] **Step 4: 验证关键规则可搜索**

Run:

```powershell
Select-String -LiteralPath 'C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md' -Pattern '最多 5 章','最多 50 章','关键时间锚','PowerShell','HTML 锚点','同一章出现多个正文文件' -SimpleMatch
```

Expected: each pattern appears at least once.

- [ ] **Step 5: 验证脚本旧路径不存在**

Run:

```powershell
$oldWorkspaceScriptPath = 'D:' + '\ai小说\提示词和脚本'
$oldEnglishPrefix = 'novel' + '_'
Select-String -Path 'C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md','C:\Users\Lenovo\.claude\skills\MyNovel\references\*.md' -Pattern $oldWorkspaceScriptPath,$oldEnglishPrefix -SimpleMatch
```

Expected: no output.

- [ ] **Step 6: 验证没有占位符**

Run:

```powershell
$redFlags = @(
  ('TO' + 'DO'),
  ('TB' + 'D'),
  ('place' + 'holder'),
  ('待' + '定'),
  ('以后' + '补')
)
Select-String -Path 'C:\Users\Lenovo\.claude\skills\MyNovel\SKILL.md','C:\Users\Lenovo\.claude\skills\MyNovel\references\*.md' -Pattern $redFlags -SimpleMatch
```

Expected: no output.

- [ ] **Step 7: Commit validation fixes if needed**

If any validation step required edits, run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' add -- SKILL.md references scripts
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' commit -m 'fix: validate MyNovel modular references'
```

Expected: commit includes only validation corrections.

### Task 8: 最终对比和交付

**Files:**
- Read: Git history and final status.

- [ ] **Step 1: 查看最终状态**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' status --short
```

Expected: no output.

- [ ] **Step 2: 查看提交链**

Run:

```powershell
git -C 'C:\Users\Lenovo\.claude\skills\MyNovel' log --oneline --decorate -8
```

Expected: shows `v1.0` baseline plus modular refactor commits.

- [ ] **Step 3: 汇报结果**

Final report must include:

```text
- `SKILL.md` 最终行数。
- 新增的 `references/` 文件清单。
- `scripts/` 目录已预留，第一轮未实现脚本。
- 已验证旧脚本路径和英文脚本名无残留。
- 已验证关键时间锚、5章限制、50章限制、锚点规则、同章多文件冲突规则仍可找到。
- Git 当前干净。
```

## 自检

- Spec coverage: 本计划覆盖设计文档中的第一阶段结构拆分、中文 `references/`、Skill 内置 `scripts/`、中文脚本名、`SKILL.md` 少于 500 行、关键时间锚、5章/50章限制、锚点规则、同章多文件冲突、脚本契约。
- Scope decision: 本计划不实现 `小说质检.py`，只预留脚本目录并写入契约；真实脚本属于第二轮可独立验证任务。
- 占位项扫描：本计划没有留下需要执行者自行补全的空白步骤。
- Risk note: 如果执行后 `SKILL.md` 仍超过 500 行，把大纲类短流程进一步移入 `references/项目定位.md`，但不新增设计清单外的 reference 文件。
