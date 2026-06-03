# Atom Index — Global

> Hook 自動匹配 trigger 注入相關 atom（完整觸發表見 `_atom_index.json` / `_ATOM_INDEX.md` mirror）。

| Atom | 說明 |
|------|------|
| decisions-architecture | 架構決策 |
| decisions | 全域決策 |
| preferences | 使用者偏好（補充） |
| toolchain-ollama | Ollama Dual-Backend 實戰記憶 |
| toolchain | 工具鏈實戰記憶 |
| workflow-icld | 增量式閉環開發（ICLD） |
| workflow-rules | 工作流規則（全域） |
| workflow-svn | SVN 工作流規則 |
| workflow-parallel-agents | 多 agent 並行：拆 ≥2 sub-agent 同 message dispatch 的評估準則 |
| atom-table-support | atom_write 知識區表格/程式碼 fence block 渲染用法（dogfood） |
| memory-index-caption-regen | MEMORY.md 描述欄 regen 機制 + 保留人工策展（atom_write 沖描述覆轍根治） |
| atom-usefulness-loop | 注入→使用→結果 閉環效用 (α,β)：use 偵測 + Wilson 晉升 + 慢衰減（Phase 2，#2） |
| atom-元資料編輯與晉升閘真相 | atom 元資料編輯與晉升閘真相 |
| realm-範疇分區機制-v5 | Realm 範疇分區機制 (V5+) |
| feedback-* | 行為校正（7 atoms） → [`_AIDocs/Failures/`](../_AIDocs/Failures/) |
| memory-pipeline-silent-failure-2026-05 | 記憶機制靜默失效（confirmations 零增 + episodic 停擺） → [`_AIDocs/Failures/memory-pipeline-silent-failure-2026-05.md`](../_AIDocs/Failures/memory-pipeline-silent-failure-2026-05.md) |
| cognitive-patterns | 認知模式偏差（Cognitive Patterns） → [`_AIDocs/Failures/cognitive-patterns.md`](../_AIDocs/Failures/cognitive-patterns.md) |

## 本地範疇（~/.claude，僅核心環境注入）

> 物理居 `_AIDocs/_atoms/<domain>/`，索引仍在 `_atom_index.json`（scope=global）；**只在 cwd∈~/.claude 時注入**，外部專案零負擔。機制見 [[realm-範疇分區機制-v5]]。

### MemDev

| Atom | 說明 |
|------|------|
| guardian-dashboard-孤兒佔埠與新碼重啟 | Guardian Dashboard 孤兒佔埠與新碼重啟 |

### Tools

| Atom | 說明 |
|------|------|
| electron-uia-automation | Electron app UI 自動化三層障礙 |
| gdoc-harvester | gdoc-harvester — Web Harvester 收割工具經驗 |
| cc-能力查證反編譯實跑-binary | CC 能力查證：反編譯實跑 binary |
| codex-log-bloat-analytics | codex-log-bloat-analytics |

### World

| Atom | 說明 |
|------|------|
| 腦內世界-v3-自癒與-command-bus-架構 | 腦內世界 v3 自癒與 Command Bus 架構 |
| reconcile-render-動畫狀態歸屬陷阱 | reconcile-render 動畫狀態歸屬陷阱 |
| 腦內世界-環境演化-放置式架構 | 腦內世界-環境演化-放置式架構 |
