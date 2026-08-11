# EPUB导出与同步

## 定位

EPUB 脚本不提升为 MyNovel 根目录的通用写入脚本。`convert_to_epub.py` 继续放在各小说项目根目录。目录压缩或项目迁移不得删除已有 EPUB 脚本。

## 脚本契约

项目脚本必须通过 `--contract-version` 输出 `mynovel-epub/2`，并支持 `--project-root`、`--onedrive-root`、`--dry-run`。

运行真实项目之前先在临时夹具执行 dry run，确认它从 commit head 链及 head 匹配的章节序列投影选章、校验正文哈希、缺章阻断，不会枚举未提交草稿。

## 脚本发现

- 当前项目脚本存在但能力探测失败时不得直接运行；保留旧脚本并生成适配差异。
- 当前项目缺脚本时搜索其他小说项目：只有一个通过临时夹具的候选，或多个候选内容哈希完全相同时才可作为参考；候选实现分叉时输出差异并停止，不自动选最新文件。

## 导出流程

1. 导出获取项目级写锁，锁的 `operation` 为 `epub`；记录 `project_id`、`source_head_transaction_id` 和 `source_head_commit_hash`，在同一锁保护下冻结正文清单与完整 plan 快照。
2. 构建先写项目内临时目录，生成 EPUB 和 `export-manifest.json`。清单包含不可变 `project_id`、确定性 `build_id = epub-<headSHA前12位>-<plan清单SHA前12位>`、`source_head_transaction_id`、`source_head_commit_hash`、原始书名、安全目录名、所有导出 node ID、正文 SHA-256、`epub_path`、`epub_sha256`、`plan_snapshot_sha256`、plan 相对路径与 SHA-256，以及脚本契约版本。同一源重试复用 build ID 和 staging，不重复创建不同结果。
3. `$env:OneDrive` 缺失或目标不可写时整体失败，不声称同步成功，也不改已有目标。
4. 选择目标目录前，在 OneDrive 小说根的 `.mynovel-locks/` 中按"安全书名规范化结果的 SHA-256"原子创建排他目标锁；同一安全书名族在锁释放前只能有一个发布者。过期锁复核锁文件哈希与未完成发布状态后 CAS 改名再获取恢复锁，不得直接删除。
5. 默认目标仍为 `$env:OneDrive\小说\《安全书名》\`：
   - 已有目标的 `export-manifest.json` 若 `project_id` 相同可原位更新；
   - 若 ID 不同，绝不移动、备份或覆盖该目录，当前项目改用 `$env:OneDrive\小说\《安全书名》_<project_id前8位>\`，并对该候选目录重复 ID 校验；
   - 已有目标缺少清单或 `project_id` 时停止，让用户明确将旧目标绑定到哪个本地项目，不能根据书名、路径或最近修改时间猜测。
6. 在最终目标书目录同级创建仅属于本次 `project_id + build_id` 的 staging，放入 EPUB、完整 plan 镜像和同一导出清单；逐项哈希通过后，只允许把"清单中 project ID 与当前项目相同"的既有精确目标改名为带 `backup-<build_id>` 的备份，再把 staging 原子改名为正式书目录。切换失败立即恢复备份，不做"EPUB 新、plan 旧"的混合复制。
7. 发布前在仍持项目锁和目标锁状态下再次确认 commit head 等于 source head、目标目录绑定的 project ID 未变化；任一变化即丢弃 staging。
8. 验收读取正式目录内本次 `project_id + build_id` 清单并重新计算 EPUB 与 plan 全部哈希；仅检查文件存在不算成功。正式目录切换后的最终验收若失败，必须把新目录移回 staging 并恢复 backup。
9. 成功或完整恢复后才释放目标锁和项目锁。旧备份不在本次流程永久删除，清理由用户另行授权。

## 目标目录安全命名

目录名先把控制字符和 Windows 非法字符 `<>:"/\|?*` 替换为 `_`，去掉末尾空格/点，禁止空值、`.`、`..` 和保留设备名；超过 80 字符时截断并追加原书名 SHA-256 前 8 位。清洗碰撞时同样追加哈希。

所有 target/staging/backup 路径都必须经路径 API 解析，并验证其父目录严格等于规范化后的 `$env:OneDrive\小说`，不能靠字符串前缀判断。
