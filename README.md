# MyNovel：面向中文长篇网文的 Codex / Claude Code Skill

当前版本：**v2.2.0**。

本版精简技能入口，按任务加载流程与参考；完善事实修复的差异授权、正文哈希与状态回证校验，并增强 shadow rebase 的恢复与切换检查。保留逐章提交、双审查和草稿状态约束。

让 AI 写长篇，真正困难的不是生成下一章，而是写到几十、几百章以后仍然记得：谁知道什么、资源还剩多少、系统开放到哪一级、哪条因果债没有偿还、哪个伏笔应该在什么阶段回收。

MyNovel 是一套面向中文长篇网络小说的完整写作工作流。它通过**分层上下文组装、可回证状态仓库、每 50 章分阶段规划、伏笔与因果债追踪、章节事务链和独立审查**，降低长篇创作中常见的剧情抢跑、设定漂移、数值失真、角色失忆和草率完结。

它不是一段“万能写作提示词”，而是一套让 Codex 或 Claude Code 按项目事实持续工作的工程化协议。

## 为什么长篇不容易写崩

### 1. 每章重新组装有边界的上下文

写新章节前，MyNovel 不会把整本书粗暴塞进上下文，也不会只看上一章。它按固定证据层级读取：

1. 项目配置、当前提交链、当前细纲节点和后续两个主线节点边界。
2. 主角状态仓库；复杂系统文再读取独立系统状态仓库。
3. 当前 50 章的系统发展计划，区分“计划目标”和“已经发生的事实”。
4. 最近 3 个有效章节正文；主线锚点不足时补最近一个主线节点。
5. 最近 20 个有效章节总结，并自动跨 50 章归档块拼接。
6. 每 50 章阶段总结、每 200 章长期摘要。
7. 角色档案、世界观、伏笔追踪和项目文风规范；涉及早期伏笔时回读埋设原章。

这样既保留近场叙事连续性，又不会随着章节增加无限膨胀上下文。

### 2. 用事实锁阻止“看起来合理”的胡写

组装完成后，工作流会提炼事实锁，覆盖：

- 时间、地点、角色认知与信息传播；
- 能力、装备、余额、库存、订单和资源消耗；
- 系统权限、任务触发、奖励预算和判定边界；
- 关系承诺、未偿因果债、伏笔和后文禁止误写。

事实锁绑定来源路径、正文锚点和 SHA-256。细纲若与已经发生的事实冲突，流程会停止，而不是为了把这一章写出来就偷偷改写历史。

### 3. 每 50 章分阶段规划，避免一次写完整本书

很多模型会把 200 章的阶段目标压缩到前 20 章，随后只能重复升级或提前完结。MyNovel 把细纲限制在每批最多 50 章，并在展开前读取系统阶段计划、总大纲边界和已经发生的状态，明确：

- 当前阶段应该推进什么；
- 哪些系统能力和剧情结算尚未解锁；
- 主角成长、任务和经营循环如何分布；
- 哪些矛盾、角色转变和伏笔必须留给后续阶段。

细纲不能擅自新增总纲之外的主线事件、角色、能力或伏笔，从规划层减少为了眼前高潮而透支后续剧情的情况。

### 4. 伏笔不是备注，而是上下文中的待偿债务

伏笔会同时进入细纲计划、章节总结、阶段摘要和伏笔追踪。写作时检查它是否被提前消费，审查时检查是否超期、变义或缺少因果桥；计划回收时还会回读埋设原章及其总结。

这让“埋下了但忘了”“回收时意思变了”“为了当前高潮提前用掉后期伏笔”都变成可检查的问题。

### 5. 正文、总结和状态保持同一条证据链

每章通过候选验证后才会生成章节总结和状态增量，再以事务方式推进 current head。未提交草稿、孤儿事务和哈希失效候选不会进入下一章上下文。

正式审查绑定正文哈希；正文被修改后，旧审查自动失效。事实性修复会重建受影响章节之后的状态投影，避免出现“正文改了，摘要和角色状态还停在旧版本”的分叉。

## 覆盖的工作流

- 扫榜、题材选择与新书初始化
- 长篇范文入库、拆书、原创仿写与文风蒸馏
- 系统／金手指设计、总大纲、黄金三章与分阶段细纲
- 系统阶段规划与每 50 章分阶段细纲
- 连续正文生成、逐章总结和状态提交
- 手动自然化、双独立审查、自动修复与一致性检查
- EPUB 导出与大纲同步

## 一键安装

需要先安装 Git。正文工作流中的确定性校验脚本还需要 Python 3。

### Windows PowerShell

安装到 Codex：

```powershell
$u='https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.ps1'; $p=Join-Path $env:TEMP 'install-mynovel.ps1'; irm $u -OutFile $p; & $p -Platform codex
```

安装到 Claude Code：

```powershell
$u='https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.ps1'; $p=Join-Path $env:TEMP 'install-mynovel.ps1'; irm $u -OutFile $p; & $p -Platform claude
```

同时安装到两个平台：

```powershell
$u='https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.ps1'; $p=Join-Path $env:TEMP 'install-mynovel.ps1'; irm $u -OutFile $p; & $p -Platform both
```

### macOS / Linux

安装到 Codex：

```bash
curl -fsSL https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.sh | bash -s -- --platform codex
```

安装到 Claude Code：

```bash
curl -fsSL https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.sh | bash -s -- --platform claude
```

同时安装到两个平台：

```bash
curl -fsSL https://raw.githubusercontent.com/xiaofeng-928/chinese-longnovel-skill/master/install.sh | bash -s -- --platform both
```

安装脚本默认使用以下目录：

| 平台 | 默认目录 | 可覆盖变量 |
|---|---|---|
| Codex | `~/.codex/skills/my-novel` | `CODEX_HOME` |
| Claude Code | `~/.claude/skills/my-novel` | `CLAUDE_CONFIG_DIR` |

重复执行同一命令会以 fast-forward 方式更新现有安装，不会删除本地改动。安装完成后重启对应平台。

## 开始使用

在准备存放小说项目的工作区中启动 Codex 或 Claude Code，然后直接描述任务，例如：

```text
帮我根据最近的榜单趋势设计一本经营流长篇网文。
```

```text
为这本书准备第51-100章规划窗口和分阶段细纲。
```

```text
继续写下一章，严格沿用已有事实、状态和伏笔计划。
```

```text
审查最近5章的一致性、伏笔状态和系统数值，并修复发现的问题。
```

默认以当前工作区作为小说工作区。也可以设置 `MYNOVEL_WORKSPACE` 指向统一的小说工作区；每个包含 `novel-config.md` 的目录会被识别为一本小说项目。

## 项目结构

典型项目会逐步形成以下结构：

```text
题材-书名/
|-- novel-config.md
|-- 创作依据/
|-- 设定/
|-- plan/
|-- 正文/
|-- 总结/
|-- 审查报告/
`-- 修复记录/
```

计划态、正文事实、状态投影和审查证据分开保存，避免总大纲、当前状态和未来目标互相污染。

## 适合与不适合

MyNovel 适合预计数百章以上、需要系统成长、经营循环、多角色关系、跨阶段伏笔或严格数值连续性的中文长篇项目。

如果只需要一次性生成短篇、单章润色或随手续写，它的状态与验证流程可能显得过重。

## 反馈

真正有价值的反馈不是点一个 Star，而是实际写完若干章后告诉我们：

- 安装和第一次建书卡在哪里；
- 连续写到第几章开始出现上下文或状态问题；
- 哪条审查阻断是误报；
- 哪个伏笔、数值或角色认知仍然发生漂移。

请通过 [Issues](https://github.com/xiaofeng-928/chinese-longnovel-skill/issues) 提交可复现问题。涉及正文隐私时，只提供最小化、匿名化片段。

## 第三方许可

第三方来源及许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
