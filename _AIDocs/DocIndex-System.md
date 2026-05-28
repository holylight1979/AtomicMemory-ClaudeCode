# 原子記憶系統 — 全檔案索引

> 最近同步：2026-05-27（V5 GA 簽收，Wave 5 Session 4 收尾）
> 目標：讓 Claude Code AI 能了解自己，以利後續升級、迭代、進化
> V5 概覽：[`SPEC_ATOM_V5.md`](SPEC_ATOM_V5.md)

---

## 1. 啟動鏈（Session Lifecycle）

```
Claude Code 啟動
  ↓
settings.json（hook 配置 + 權限白名單）
  ↓
[SessionStart hooks]
  ├─ user-init.sh → USER.template.md → USER-{username}.md → USER.md
  ├─ workflow-guardian.py（shim → dispatcher.main()）
  │   └─ handlers/session_start.py
  │       ├─ 解析 _atom_index.json（JSON SoT）
  │       ├─ 掃描 _AIDocs/_INDEX.md
  │       ├─ register_project(cwd) → project-registry.json
  │       ├─ Wisdom Engine blind spots
  │       ├─ Long DIE check（Dual-Backend）
  │       ├─ 啟動 Vector Service（port 3849，bg subprocess）
  │       └─ _call_project_hook("session_start") → delegate
  ├─ ensure-mcp.py（MCP server 可用性確認）
  └─ codex_companion.py（subprocess 模型 in-process state）
  ↓
CLAUDE.md @import
  ├─ IDENTITY.md（AI 人格 — 收尾檢核 4 項硬契約）
  ├─ USER.md（使用者偏好）
  ├─ MEMORY.md（atom 索引人類可讀版）
  └─ rules/core.md
  ↓
Session Ready
  ↓
[UserPromptSubmit] ×N → trigger → BM25 全域層 → Vector fallback → atom 注入 + Evasion
[PreToolUse] → Write/Edit/Bash matcher → atom format gate + memory path block + SVN test block
[PostToolUse] → file tracking + 增量索引 + read tracking + test-fail 偵測 + _CHANGELOG auto-roll
[Stop] → sync 閘門 + TestFailGate + Evasion Detection
[Stop async] → quick-extract.py (qwen3:1.7b 5s → hot_cache.json)
[PreCompact] → state snapshot
[SessionEnd] → episodic 生成 + LLM 萃取 + 跨 session 鞏固 + Wisdom 反思 + audit-reconcile
```

## 2. 設定檔層

| 檔案 | 用途 | 載入方式 | 多人 |
|------|------|---------|------|
| CLAUDE.md | 全域入口，@import 3 檔 | 自動 | 共用 |
| IDENTITY.template.md / USER.template.md | 個人實例 template | 拷貝 | 共用 |
| IDENTITY.md / USER.md | AI 人格 / 使用者偏好（個人實例） | @import | gitignored, per-user |
| IDENTITY-{user}.md / USER-{user}.md | 個人擴充 | @import | per-user |
| BOOTSTRAP.md | 首次設定引導（IDENTITY/USER 為空時觸發） | 條件觸發 | 共用 |
| settings.json | 8 hook events + 權限白名單 | Claude Code 讀取 | per-user |
| version.json | atom_memory + guardian 版本標識 | 文件用 | 共用 |
| workflow/config.json | Guardian / Vector / Decay / Capture 全參數 | hook 每次讀取 | 共用 |
| memory/_meta/forbidden-phrases.json | 禁語 single source | IDENTITY + wg_evasion 共用 | 共用 |
| mcp-servers.template.json | MCP server 清單（Install-forAI 用） | 安裝時讀 | 共用 |

## 3. 規則模組（rules/）

| 模組 | 職責 |
|------|------|
| core.md | 知識庫維護 + 原子記憶分類 + 同步工作流 + 對話續航（合併單檔） |

## 4. Hook 系統（dispatcher + handlers + 7 wg_*）

| 檔案 | 行數 | 職責 |
|------|------|------|
| workflow-guardian.py | 20 | 薄 shim（5 行可執行 code）轉發 `dispatcher.main()` |
| dispatcher.py | ~75 | 純路由：讀 stdin event → 找 handler → 呼叫 |
| handlers/_shared.py | — | 跨 handler 共用 helper |
| handlers/session_start.py | — | init state + 去重 + bootstrap + Vector bg subprocess |
| handlers/user_prompt_submit.py | — | RECALL（trigger → BM25 → Vector）+ intent + evasion |
| handlers/pre_tool_use.py | — | Write/Edit atom format gate + memory path block + Bash SVN test block |
| handlers/post_tool_use.py | — | file tracking + 增量索引 + read tracking + test-fail + changelog auto-roll |
| handlers/stop.py | — | sync 閘門 + Fix Escalation + TestFailGate + Evasion |
| handlers/session_end.py | — | Episodic + 萃取 + 衝突偵測 + Wisdom 反思 |
| handlers/pre_compact.py | — | state snapshot |
| handlers/notification.py | — | 通知處理 |
| wg_core.py | — | 路徑唯一真相 + state IO + log rotation + PreToolUse guards |
| wg_atoms.py | — | trigger + BM25 + ACT-R + vector search + atom 晉升 |
| wg_extraction.py | — | per-turn 萃取 + worker + hot cache + user-extract + content classify |
| wg_episodic.py | — | episodic 生成 + 衝突 + 品質回饋 |
| wg_evasion.py | — | Evasion Guard + Test-Fail + ScanReport + 自評整合 |
| wg_docdrift.py | — | src → _AIDocs 映射 drift 偵測 |
| wg_roles.py | — | V4 sub-layer 探勘 shim |
| codex_companion.py | — | Codex Companion hook：in-process state + spawn audit.py subprocess |
| extract-worker.py | — | SessionEnd 萃取子程序 |
| user-extract-worker.py | — | L1/L2 使用者決策萃取 |
| quick-extract.py | — | Stop async 快篩 |
| wisdom_engine.py | — | 2 硬規則 + 3 反思指標 + Bayesian arch sensitivity |
| ensure-mcp.py | — | MCP server 可用性確認 |
| user-init.sh | — | 多人 USER.md 初始化 |
| webfetch-guard.sh | — | WebFetch 安全護欄 |

## 5. Skills（19 個全域）

V5 把 commands/*.md 遷到 skills/{name}/SKILL.md 結構（對齊 Anthropic 官方「commands merged into skills」）。Legacy `commands/` 全刪除。

| 指令 | 檔案 | 用途 | 依賴 |
|------|------|------|------|
| /atom-debug | skills/atom-debug/SKILL.md | Debug log 開關 | 無 |
| /codex-companion | skills/codex-companion/SKILL.md | Codex Companion 開關（subprocess 模型，只 toggle config flag） | codex CLI |
| /changelog-debug | skills/changelog-debug/SKILL.md | 手動滾動 _CHANGELOG.md（PostToolUse 已自動，僅 debug） | 無 |
| /conflict | skills/conflict/SKILL.md | 記憶衝突偵測 | Vector Service + Ollama |
| /conflict-review | skills/conflict-review/SKILL.md | 管理職裁決 Pending Queue（雙向認證） | wg_roles + Vector Service |
| /consciousness-stream | skills/consciousness-stream/SKILL.md | 高風險跨系統識流處理 | 無 |
| /continue | skills/continue/SKILL.md | 讀 _staging/next-phase.md 續接 | 無 |
| /extract | skills/extract/SKILL.md | 手動知識萃取 | Ollama |
| /fix-escalation | skills/fix-escalation/SKILL.md | 精確修正升級（6 Agent 會議） | 無 |
| /generate-episodic | skills/generate-episodic/SKILL.md | 手動生成 episodic atom | 無 |
| /handoff | skills/handoff/SKILL.md | 跨 Session Handoff Prompt Builder | 無 |
| /harvest | skills/harvest/SKILL.md | Playwright 網頁收割→Markdown | Playwright |
| /init-roles | skills/init-roles/SKILL.md | 多職務模式啟用引導 | wg_roles + git |
| /memory | skills/memory/SKILL.md | 5 合 1：health / peek / undo / review / session-score（subcmd 分派） | 無 |
| /read-project | skills/read-project/SKILL.md | 系統性閱讀→doc-index atom | 無 |
| /upgrade | skills/upgrade/SKILL.md | 環境升級（diff + merge + rebuild） | 無 |
| /vector | skills/vector/SKILL.md | 向量服務管理 | Vector Service |
| /journal | skills/journal/SKILL.md | 工作日誌產出 | 無 |
| /browse-sprites | skills/browse-sprites/SKILL.md | 批次圖片預覽 | 無 |

> 已刪除（與內建衝突）：`/resume`（內建 --resume）/ `/init-project`（內建 /init）/ `/svn-update` / `/unity-yaml`（下沉專案層）/ `/changelog-roll`（改名 changelog-debug）

## 6. 工具鏈（tools/）

### MCP Server（3 tool）
- `workflow-guardian-mcp/server.js` — stdio MCP + dashboard port 3848
  - `atom_write` / `atom_move` / `atom_promote`（3 個業務 tool）
  - 內部 IPC 4 個（`workflow_signal` / `workflow_status` / `memory_queue_add` / `memory_queue_flush`）已內化為 Stop gate hook 自動偵測

### Vector Service（port 3849；專案層 + episodic + cross-session dedup 用）
- service.py — HTTP daemon
- config.py — config.json 讀寫
- indexer.py — atom→chunk→embed→LanceDB（含 `cleanup_stale_chunks` 機制）
- searcher.py — semantic + ranked + section-level（5-factor 排名）
- reranker.py — LLM query rewrite + re-rank
- 全域層改 BM25 in-memory（in `wg_atoms.py`），手刻 ~80 行（k1=1.2, b=0.75，ASCII word + 中文 char-bigram tokenization）

### Ollama 雙 Backend
- ollama_client.py — singleton，generate() / chat() / embed()
  - rdchat-direct: gemma4:e4b + qwen3-embedding:latest（GPU 直連，pri=1）
  - local: qwen3:1.7b + qwen3-embedding（CPU/GPU，pri=3）
  - 三階段退避：normal → short_die(60s) → long_die(6h boundary: 0/6/12/18)

### lib/ — atom funnel 核心
- atom_spec.py — atom 格式規則純函式（slugify / build_atom_content / validate / SKIP_DIRS / VALID_SCOPES），audit/health/atom_io 共用 import
- atom_io.py — 知識內容寫入 funnel（`write_atom` / `write_raw` / `write_index_full`），對拍 server.js byte-identical
- atom_access.py — 遙測 funnel（`<atom>.access.json` 旁路檔，schema atom-access-v2）；`init_access` / `increment_read_hits` / `increment_confirmation` / `record_promotion` / `bulk_read`
- atom_io_cli.py — thin CLI bridge（stdin JSON → write_* → stdout WriteResult）給 MCP server.js spawn
- atom_index_json.py — `_atom_index.json` JSON SoT API（load / save / upsert / delete / regenerate_md / migrate / validate）
- ollama_extract_core.py — 萃取共用核心 + SessionBudgetTracker（240 tok/session, CJK-aware）

### 記憶品質
- memory-audit.py — 格式驗證 + staleness + 雙軌晉升建議（Conf≥4/10 or RH≥20/50）
- atom-health-check.py — 參照完整性（含 `_` 前綴豁免 / project→global up-ref / `--shadow-check` 與 _AIDocs 子段相似度偵測）
- atom-health-audit.py — atom 體質審視（七類分類：歸檔 / 晉升 / 冷凍 / 缺欄 / trigger 補強 / 保留）
- check-bypass.py — 靜態掃描 funnel 繞過（WHITELIST 外 `write_text` / `open(w)` / `fs.writeFileSync` 命中 memory 路徑 → CI exit 1）
- audit-reconcile.py — 動態對拍（mtime × audit log entries），三分類（counter_only / knowledge / unknown）
- memory-write-gate.py — 寫入閘門（6 規則 + 0.80 dedup）
- memory-conflict-detector.py — 向量衝突 + LLM 分類（mode ∈ {full-scan / write-check / pull-audit}）
- conflict-review.py — Pending Queue 後端（list / approve / reject，is_management 雙向認證 guard）
- atom-move.py — 跨層原子搬遷工具（mv + 更新 Scope + 同步索引 + 處理 inbound refs）
- sync-atom-index.py / sync-memory-index.py — atom frontmatter Trigger ↔ `_atom_index.json` 一致性同步
- cleanup-projects-residue.py — projects/{slug}/memory/ 殘骸清理工具

### 遷移 / 維護
- init-roles.py — `/init-roles` 後端
- memory-peek.py / memory-undo.py / memory-session-score.py — `/memory` 子命令後端
- changelog-roll.py — _CHANGELOG.md 自動滾動（PostToolUse hook 偵測寫入 → detached subprocess 觸發）
- cleanup-old-files.py — 環境清理
- audit-reconcile.py — 已列於記憶品質節
- journal-aggregate.py — `/journal` 後端

### Codex Companion（V5 subprocess）
- audit.py — one-shot subprocess（stdin JSON → assessor.run_assessment → state.write_assessment 落盤）
- assessor.py — 組 prompt → `codex exec` → parse JSON；retry 1 次；`_classify_failure` 識別 R2-5 級錯誤
- prompts.py — plan review / turn audit / architecture review 模板，含 SANDBOX_CONSTRAINT 紅線
- state.py — per-session 狀態 + per-turn assessment cache（含 metric API + 白名單）
- heuristics.py — 規則式軟閘（< 10ms 無 LLM）；Silent Advisory Mode 預設啟用
- scorer.py — turn-level risk scoring（五因子加權 0-10），< score_threshold 跳過 codex

> Codex Companion 設計原則：軟閘屬「背景品質觀測」，不干擾使用者對話流。`silent_advisory: true` + `max_inject_severity: high` 預設，多數 advisory 走「靜默落盤 + metric 計數」路徑。

### 其他
- read-excel.py（openpyxl + xlrd）
- unity-yaml-tool.py
- rag-engine.py（CLI wrapper）
- sprite_contact_sheet.py
- gdoc-harvester/（Playwright 網頁收割 + dashboard）

## 7. 記憶層

- **MEMORY.md**（always loaded）— 16 atoms 一覽（人類可讀）
- **_atom_index.json**（JSON SoT）— 機器源真相，16 atoms 完整索引
- **_ATOM_INDEX.md**（自動生成 mirror）— 人類可讀備援 parser
- **全域 Atoms**（16 個 .md）— core 8（decisions / decisions-architecture / preferences / workflow-rules / workflow-icld / workflow-svn / toolchain / toolchain-ollama）+ feedback 5（V5 整併 24→5）+ 特定領域 3（electron-uia-automation / gdoc-harvester / 記憶機制靜默失效confirmations-零增-episodic-停擺）
- **failures/**（atom 子族） — 跨專案踩坑記錄
- **templates/** — icld-sprint-template 等
- **_reference/**（手動讀取）— SPEC 等深度規格
- **wisdom/**（live state）— DESIGN.md + reflection_metrics.json + causal_graph.json
- **_meta/forbidden-phrases.json**（V5 single source）— 禁語清單
- **_meta/atom_io_audit.jsonl** — 寫入稽核日誌
- **Runtime（gitignored）**：episodic/ / _vectordb/ / _staging/ / _distant/ / state-*.json / *.access.json

## 8. 專案自治層

每個已註冊專案的 `{project_root}/.claude/` 結構：

| 路徑 | 用途 |
|------|------|
| `.claude/memory/MEMORY.md` | 專案 atom 索引 |
| `.claude/memory/*.md` | 專案 atoms（V4 三層 scope：shared / role / personal） |
| `.claude/memory/shared/_roles.md` | V4 管理職白名單（雙向認證） |
| `.claude/memory/shared/_pending_review/` | 敏感 atom 等管理職裁決 |
| `.claude/memory/episodic/` | 自動生成（gitignored） |
| `.claude/memory/failures/` | 踩坑記錄（版控） |
| `.claude/memory/_staging/` | 暫存（gitignored） |
| `.claude/hooks/project_hooks.py` | 專案 delegate（inject / extract / session_start） |
| `.claude/.gitignore` | 排除 ephemeral 檔案 |

管理：`memory/project-registry.json` 索引所有已註冊專案根路徑。

## 9. 對外文件

- README.md — GitHub 入口（設計理念 + 架構 + Token 影響 + 安裝）
- Install-forAI.md — AI 代跑安裝指南（V5 GA 對齊）
- TECH.md — 技術深度文件（架構 / 流程圖 / 子系統，以代碼為真源）
- _AIDocs/ — 知識庫（Architecture / SPEC_ATOM_V5 / SPEC_ATOM_V4 / DevHistory / Failures / ClaudeCodeInternals / Tools）
- _AIDocs/DevHistory/v5-overhaul-2026-05/ — V5 升版完整紀錄
- LICENSE — GPLv3

---

## 速查

| 問題 | 去看 |
|------|------|
| 啟動時載入了什麼？ | settings.json → handlers/session_start.py |
| Atom 怎麼被注入的？ | wg_atoms.py（trigger → BM25 全域 / Vector 專案）+ ACT-R rank |
| 記憶怎麼寫入？ | lib/atom_io.py funnel（PreToolUse 強制門禁 + audit_io_audit.jsonl 留證） |
| 向量搜尋怎麼運作？ | tools/memory-vector-service/{indexer,searcher,reranker}.py |
| Ollama 雙 Backend？ | ollama_client.py + workflow/config.json `ollama_backends` |
| 專案自治層？ | wg_core.py（registry + 路徑切換）+ project_hooks.py delegate |
| 怎麼升級環境？ | /upgrade skill |
| Codex Companion 怎麼運作？ | hooks/codex_companion.py（spawn audit.py subprocess） |
