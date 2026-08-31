# 原子記憶系統 — 全檔案索引（V5 GA + Session α/β）

- Scope: global
- Confidence: [固]
- Type: semantic
- Trigger: 記憶系統架構, 檔案結構, hook, skill, tool, lib, 記憶升級, 記憶迭代, 目錄結構
- Last-used: 2026-05-28
- Updated: 2026-05-28
- Created: 2026-03-13
- Confirmations: 67
- Tags: doc-index, system-overview
- Related: decisions, decisions-architecture, toolchain

> 本檔為原 V2.21 全檔索引（2026-03-27）的 V5 GA 完整重寫。對應 [TECH.md §10 架構目錄樹](../../TECH.md#2-系統架構目錄樹2026-05-28-v5-ga--session-αβ-現況) 與 [SPEC_ATOM_V5.md](../SPEC_ATOM_V5.md) 之現況，提供「按檔索引」視角（TECH.md 是「按子系統」視角）。

## 知識

### 啟動鏈（V5 GA）

| 步驟 | 觸發點 | 對應檔案 |
|------|--------|---------|
| 1 | Claude Code 啟動 session | `~/.claude/settings.json`（8 hook event 註冊） |
| 2 | SessionStart hook 觸發 | `~/.claude/hooks/workflow-guardian.py`（1 行 shim → `dispatcher.main()`） |
| 3 | dispatcher 從 stdin 讀 JSON | `hooks/dispatcher.py`（~75 行純路由）|
| 4 | 路由到 event handler | `hooks/handlers/session_start.py`（同理 8 event 各一檔） |
| 5 | `CLAUDE.md` @import 三件套 | `IDENTITY.md` + `USER.md` + `memory/MEMORY.md` |
| 6 | rules 由 `rules/core.md` 集中 | `rules/core.md`（合併單檔：知識庫+記憶+同步+對話） |
| 7 | atom index 載入 | `memory/_atom_index.json`（V5 JSON SoT，17 atoms） |

### 設定檔（依層級）

| 檔案 | 用途 | 維護方 |
|------|------|--------|
| `CLAUDE.md` | 全域入口（@import IDENTITY/USER/MEMORY + rules/core.md） | 系統 |
| `IDENTITY.md` | AI 角色定義（團隊共用） | 團隊 |
| `IDENTITY.template.md` | 多人模板（git tracked） | 系統 |
| `USER.md` | 操作者個人資料（per-user，gitignored）| 使用者本人 |
| `USER.template.md` | 多人模板 | 系統 |
| `BOOTSTRAP.md` | 首次啟動引導（IDENTITY/USER 為空時觸發）| 系統 |
| `settings.json` | Hook 綁定 + permissions + env（不入 git） | 使用者本人 |
| `.mcp.json` / `~/.claude.json` | MCP server 設定 | 安裝流程合併 |
| `mcp-servers.template.json` | MCP server 清單（Install-forAI 讀取） | 系統 |
| `workflow/config.json` | Guardian / Vector / WriteGate / Capture 參數 | 系統 + user 覆寫 |
| `memory/_meta/forbidden-phrases.json` | V5 禁語單一真相（IDENTITY + wg_evasion 共讀） | 系統 |
| `version.json` | V5 GA 版本標識（`atom_memory: 5.0` / `guardian: 5.0.0`） | 系統 |

### Hook 系統 — V5 P2 結構（hooks/）

| 類別 | 檔案 | 行數量級 | 用途 |
|------|------|---------|------|
| Shim | `workflow-guardian.py` | 1 行 | → `dispatcher.main()` |
| Dispatcher | `dispatcher.py` | ~75 | 純路由 + main entry，無業務邏輯 |
| Handlers | `handlers/session_start.py` | — | SessionStart：state dedup / atom index 載入 / Vector health |
| 同上 | `handlers/user_prompt_submit.py` | ~680 | 注入主入口（atom recall / hot cache / wisdom / evasion / handoff） |
| 同上 | `handlers/pre_tool_use.py` | — | feedback routing advisory + 路徑 whitelist 檢查 |
| 同上 | `handlers/post_tool_use.py` | — | modified/accessed tracking + Hot Cache check + docdrift |
| 同上 | `handlers/stop.py` | — | 逐輪萃取 + 同步 gate |
| 同上 | `handlers/session_end.py` | — | 全量萃取 + episodic + cross-session 鞏固 + wisdom reflect |
| 同上 | `handlers/pre_compact.py` / `notification.py` | — | 對應事件 |
| 同上 | `handlers/_shared.py` | — | 共用 helper |
| 主模組 | `wg_core.py` | — | 路徑唯一真相 + state IO + config + log rotation |
| 同上 | `wg_atoms.py` | — | trigger + BM25 + ACT-R + vector + 晉升 |
| 同上 | `wg_extraction.py` | — | per-turn 萃取 + worker + hot cache + user-extract L0 |
| 同上 | `wg_episodic.py` | — | episodic 生成 + 衝突 + 品質回饋 |
| 同上 | `wg_evasion.py` | — | Evasion Guard + Test-Fail Gate + 4 套自評整合 |
| 同上 | `wg_docdrift.py` | — | src → _AIDocs 映射 drift |
| Shim（V4 sub-layer） | `wg_roles.py` | — | V4 sub-layer 探勘 |
| Shim（觀察採樣） | `wg_atom_observation.py` | — | REG-005 觀察採樣（flag-gated） |
| 獨立保留 | `wisdom_engine.py` | — | 反思引擎 + Fix Escalation |
| 同上 | `codex_companion.py` | — | V5 P5b subprocess 模型（無 daemon） |
| 同上 | `extract-worker.py` / `quick-extract.py` / `user-extract-worker.py` | — | 萃取 worker（detached） |
| 同上 | `ensure-mcp.py` | — | SessionStart 自檢 MCP 套件 + npm |
| 同上 | `post-git-pull.sh` / `user-init.sh` / `webfetch-guard.sh` | — | 工具 shim |

### lib/（V5 GA + Session α/β 抽象層）

| 檔案 | 用途 | 備註 |
|------|------|------|
| `atom_index_json.py` | V5 JSON SoT API（load/save/upsert/delete/regenerate_md/migrate/validate） | V5 P3b 主交付 |
| `atom_io.py` | atom 讀寫統一入口（write funnel：寫入規則集中） | atom_write MCP 與 hook 共用 |
| `atom_spec.py` | atom 合法性規範（slugify / is_atom_file / REQUIRED_METADATA / SKIP_DIRS） | |
| `atom_access.py` | `.access.json` 計數 funnel（ReadHits / Confirmations / last_used） | 計數類欄位單一來源 |
| `atom_locations.py` | V5+ atom 物理位置 + 路由規則單一來源（FAILURES_DIR / iter_atom_files_multi / failures_write_target / atom_writable_dir_segments） | commit `89ccb2d`；JS mirror 在 server.js:applyFeedbackRouting |
| `ollama_extract_core.py` | 共享萃取核心 + SessionBudgetTracker（240 tok/session）| V4.1 L1+L2 共用 |

### Skills（V5 P1 — 19 個 `skills/{name}/SKILL.md`）

| Skill | 用途 | 外部依賴 |
|-------|------|---------|
| `/atom-debug` | 切換 atom 注入/萃取 debug log | 無 |
| `/browse-sprites` | 圖片批次預覽（拼貼縮圖 + 大圖） | tools/sprite_contact_sheet.py |
| `/changelog-debug` | 手動滾動 _CHANGELOG.md（debug） | tools/changelog-roll.py |
| `/codex-companion` | 切換 Codex Companion 開關 | codex CLI |
| `/conflict` | 記憶衝突偵測 | Vector Service + Ollama |
| ~~`/conflict-review`~~ | 管理職裁決 _pending_review/（**P8a archived·dormant** → `skills/_archived/`） | 無 |
| `/consciousness-stream` | 識流處理（連續對話流寫入記憶） | 無 |
| `/continue` | 讀 _staging/next-phase*.md 續接任務 | 無 |
| `/extract` | 手動知識萃取（不等 SessionEnd）| Ollama |
| `/fix-escalation` | 精確修正升級（6 Agent 會議） | 無 |
| `/generate-episodic` | 手動生成 episodic atom | 無 |
| `/handoff` | 跨 session handoff prompt（6 區塊強制模板） | 無 |
| `/harvest` | 網頁收割（Playwright + cookie） | Playwright |
| ~~`/init-roles`~~ | 專案多職務模式啟用（**P8a archived·dormant** → `skills/_archived/`） | 無 |
| `/journal` | 工作日誌產出（atoms + git log + transcript）| Ollama |
| `/memory` | 5-in-1 記憶工具（health/peek/undo/review/score） | 無 |
| `/read-project` | 系統性讀取專案 → atom + DocIndex | Ollama（可選）|
| `/upgrade` | V4/V5 schema migration 升級 | 無 |
| `/vector` | Vector Service 管理（啟動/停止/重建） | LanceDB + Ollama |

> V4 期間 22 個 `commands/*.md` 已全部刪除；遷移對應見 [SPEC_ATOM_V5 §4](../SPEC_ATOM_V5.md#4-commands--skills-遷移v5-p12026-05-27)。
> 已刪除（與內建衝突或合併）：`/init-project`、`/resume`、`/svn-update`、`/unity-yaml`、`memory-{health,peek,undo,review,session-score}` 五合一為 `/memory`。

### 工具（tools/）

| 檔案/目錄 | 用途 |
|-----------|------|
| `ollama_client.py` | Dual-Backend Ollama singleton（三階段退避 + auto failover） |
| `memory-audit.py` | atom 格式驗證 + staleness（含 V5+ 多根掃描）|
| `memory-write-gate.py` | 寫入品質閘門（規則 + dedup + CJK pattern） |
| `memory-conflict-detector.py` | 向量衝突偵測（三時段：write/pull/startup） |
| `memory-peek.py` / `memory-undo.py` / `memory-session-score.py` | 記憶 UX（被 /memory skill 合併呼叫） |
| `atom-health-check.py` | 參照完整性驗證（V5+ 多根） |
| `atom-move.py` | atom 跨 scope 搬移（含 access.json） |
| `sync-atom-index.py` | V5 P6c：frontmatter Trigger ↔ `_atom_index.json` 同步（V5+ 雙根掃描） |
| `sync-memory-index.py` | MEMORY.md 渲染（讀 `_atom_index.json` SoT） |
| `audit-reconcile.py` | audit log 對帳 |
| `cleanup-old-files.py` / `cleanup-projects-residue.py` | 舊檔清理 |
| `changelog-roll.py` | _CHANGELOG.md 自動滾動（PostToolUse 觸發） |
| `check-bypass.py` | 防止測試碼 / atom 內容 leak 進 SVN/GIT |
| `journal-aggregate.py` | 工作日誌聚合 |
| `generate-episodic-manual.py` | 手動 episodic 生成 |
| `rag-engine.py` | Vector Service CLI |
| `read-excel.py` / `sprite_contact_sheet.py` | 領域工具 |
| `init-roles.py` / `conflict-review.py` | 多職務管理工具 |
| `codex-companion/` | V5 P5b 子目錄（audit.py + assessor + heuristics + prompts + scorer + state） |
| `gdoc-harvester/` | 網頁收割工具集 |
| `memory-vector-service/` | HTTP Vector Service @ port 3849（service.py + indexer.py + requirements.txt） |
| `unity-desktop/` | Unity 桌面工具集 |
| `workflow-guardian-mcp/server.js` | MCP server @ stdio（3 tool：atom_write/move/promote）+ Dashboard @ port 3848 |

### 記憶層（memory/）

| 路徑 | 用途 | 入版控？ |
|------|------|---------|
| `MEMORY.md` | AI 一覽索引（人類可讀，always loaded via CLAUDE.md @import） | ✓ |
| `_atom_index.json` | V5 JSON SoT 機器源（17 atoms） | ✓ |
| `_ATOM_INDEX.md` | deprecated mirror（自動生成 by upsert_atom）| ✓ |
| `_meta/forbidden-phrases.json` | V5 禁語單一真相 | ✓ |
| `*.md`（一般 atoms） | 10 個全域 atom（decisions / decisions-architecture / preferences / toolchain / toolchain-ollama / workflow-rules / workflow-icld / workflow-svn / gdoc-harvester / electron-uia-automation） | ✓ |
| `personal/{user}/` | V4 個人層（gitignored） | ✗ |
| `shared/` / `roles/` | V4 分層（`/init-roles` 後啟用） | ✓ |
| `wisdom/` | 反思指標 + 自我迭代狀態 | 部分 |
| `episodic/` | 自動生成 episodic atom（TTL 24d） | ✗ |
| `_staging/` | 暫存區（next-phase / 草稿） | ✗ |
| `_distant/` | 封存區（V4 舊內容、過期 atom） | ✗ |
| `_reference/` | 參考文件（internal-pipeline.md 等） | ✓ |
| `_vectordb/` | LanceDB 索引 + audit.log（專案層用）| ✗ |
| `_promotion_audit.jsonl` | 晉升 audit | ✓ |

> **V5+ Session α 起**：title 以 `feedback-` 開頭的 atom（5 個）+ `cognitive-patterns` + `memory-pipeline-silent-failure-2026-05` 共 7 個 atom 物理居 `_AIDocs/Failures/`，索引仍在此 `_atom_index.json` 單一來源。
> 規則來源：[`lib/atom_locations.py`](../../lib/atom_locations.py) + [SPEC_ATOM_V5 §2.1](../SPEC_ATOM_V5.md#21-atom-存放擴展feedback--失敗模式類v5-session-αβ2026-05-28)。

### _AIDocs/（V5 GA + Session α/β）

| 路徑 | 用途 |
|------|------|
| `_INDEX.md` | 本目錄索引 + 一句話摘要 |
| `_CHANGELOG.md` | 變更記錄（最近 ~8 筆，hook 自動滾動）|
| `_CHANGELOG_ARCHIVE.md` | 變更記錄封存（>8 筆部分）|
| `Architecture.md` | 系統架構總覽 |
| `Project_File_Tree.md` | 頂層目錄角色說明 |
| `SPEC_ATOM_V5.md` | **V5 GA 規格主檔**（§2.1 含 feedback-* 路由）|
| `SPEC_ATOM_V4.md` | V4 規格（V5 依賴的對照證物：scope / 衝突 / pending review 詳述）|
| `DocIndex-System.md` | 系統索引（**本檔**）|
| `known-regressions.md` | 已知回歸列表 |
| `ClaudeCodeInternals/` | CC 原生架構研究筆記（**來源 2026-04 初**，部分參考價值，見子 _INDEX 註記）|
| `Tools/` | 工具與領域知識（Unity / Excel / BM25 / 本檔）|
| `Failures/` | 失敗模式 + V5+ 起為 feedback-* atoms 物理位置 |
| `DevHistory/` | 版本演進 + V5 升版完整紀錄（`v5-overhaul-2026-05/`）|

### 專案自治層（{project_root}/.claude/）

V2.21 引入、V5 沿用：

| 路徑 | 用途 |
|------|------|
| `.claude/memory/MEMORY.md` | 專案 atom 索引 |
| `.claude/memory/*.md` | 專案 atoms |
| `.claude/memory/shared/` / `roles/` / `personal/{user}/` | V4 多職務分層 |
| `.claude/memory/episodic/` | 自動生成（gitignore）|
| `.claude/memory/failures/` | 踩坑記錄（版控）|
| `.claude/memory/_staging/` | 暫存（gitignore）|
| `.claude/hooks/project_hooks.py` | 專案 delegate（如有自訂注入/萃取）|
| `.claude/.gitignore` | 排除 ephemeral 檔案 |

### 對外文件（根目錄）

| 檔案 | 用途 |
|------|------|
| `README.md` | GitHub 入口（V5 GA + 3 步上手）|
| `TECH.md` | 技術深度文件（架構 + 流程圖 + 子系統 + 實際運作範例）|
| `Install-forAI.md` | 由 AI 代跑的安裝 SOP |
| `BOOTSTRAP.md` | IDENTITY/USER 空時的引導 |
| `LICENSE` | GPLv3 |

### Verify 結構（H-test-prune 後，commit `c8dc52f`）

| 路徑 | 內容 |
|------|------|
| `run_verify.py` | 跨平台 entrypoint（動態掃 `{src}/verify/`）|
| `pytest.ini` | `python_files = test_*.py verify_*.py` |
| `hooks/verify/` / `tools/verify/` / `tools/codex-companion/verify/` / `lib/verify/` | 14 個 verify_*.py（283 passed baseline）|
| `skills/{name}/verify/` | 17 個空結構 + .gitkeep + README（候選見 `_staging/next-phase-skills-verify.md`）|

## 行動

- 需要了解某模組細節時，直接 Read 對應檔案
- 升級/迭代時，從此索引定位影響範圍
- 開發 hook → 改 `hooks/handlers/{event}.py` 或 `hooks/wg_*.py` 主模組
- 開發 skill → 建 `skills/{name}/SKILL.md` + 加 frontmatter（description/when_to_use/disable-model-invocation/user-invocable/allowed-tools）
- 寫入 atom → 必走 MCP `atom_write` tool（不手刻 .md + frontmatter）
- 查詢 atom 物理位置規則 → `lib/atom_locations.py` + [SPEC_ATOM_V5 §2.1](../SPEC_ATOM_V5.md#21-atom-存放擴展feedback--失敗模式類v5-session-αβ2026-05-28)
- 新增系統檔案 → 同步更新本索引 + `_AIDocs/_INDEX.md` + `Project_File_Tree.md`

## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-13 | 初始建立 | /read-project |
| 2026-03-19 | 純索引化 + 去重 decisions | 系統精修 |
| 2026-03-19 | 更新 extract-worker/guardian 行數（v2.13）| failures 自動化 |
| 2026-03-23 | Guardian 模組化：1 monolith → 7 模組 | 重構 Phase 1-6 |
| 2026-03-27 | V2.21 Phase 3-4：wg_paths.py + 專案自治層 | V2.21 遷移 |
| 2026-04-15 | V4 多職務分層上線 | V4 |
| 2026-04-16 | V4.1 使用者決策萃取 | V4.1 |
| **2026-05-28** | **V5 GA + Session α/β 完整重寫**（取代 V2.21 版）— 對齊 hook 6+2 模組 / dispatcher + handlers/ / lib/ 6 檔含 atom_locations / 19 skills / 17 atoms / `_atom_index.json` SoT / V5+ feedback-* 路由 / verify 結構 | Session β 收尾 |
