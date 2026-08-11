# 原子記憶系統 — 全檔案索引

> 最近同步：2026-07-25（V5.1 ultra-opt：RRF 融合 + memory-eval + recall-miss + Depends/Evidence）
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
  ├─ user-init.sh → templates/USER.template.md → USER-{username}.md → USER.md；IDENTITY.md 缺失時從 templates/IDENTITY.template.md 災復還原
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
  ├─ MEMORY.md（atom 索引人類可讀版 — **core-only**；本地範疇段抽到 _local_catalog.md）
  └─ rules/core.md
  ↓
SessionStart hook（cwd∈~/.claude 才注入 memory/_local_catalog.md 本地範疇 catalog）
  ↓
Session Ready
  ↓
[UserPromptSubmit] ×N → trigger → BM25 全域層 → Vector fallback → atom 注入 + Evasion
[PreToolUse] → Write/Edit/Bash matcher → atom format gate + memory path block + cross-realm write block + SVN test block
[PostToolUse] → file tracking + 增量索引 + test-fail 偵測 + _CHANGELOG auto-roll（matcher 無 Read）
[Stop] → sync 閘門 + TestFailGate + Evasion Detection + transcript 單次 tail-read（含 accessed_files 回收）
[Stop async] → quick-extract.py (qwen3:1.7b 5s → hot_cache.json)
[PreCompact] → state snapshot + injected_atoms 快照
[PostCompact] → stash 壓縮前 atom 緊湊內文 + pending_reinjection flag（不注入）
[PostToolBatch] → 見 flag 一次性重注入壓縮前 atom 內文（閉 mid-turn auto-compact 缺口；選配 #4）
[SessionEnd] → episodic 生成 + LLM 萃取 + 跨 session 鞏固 + Wisdom 反思 + audit-reconcile
```

## 2. 設定檔層

| 檔案 | 用途 | 載入方式 | 多人 |
|------|------|---------|------|
| CLAUDE.md | 全域入口，@import 3 檔 | 自動 | 共用 |
| templates/IDENTITY.template.md / templates/USER.template.md | 實例的 tracked 備份/還原源 | 災復拷貝 | 共用 |
| IDENTITY.md / USER.md | AI 行為契約（直接維護單一真相）/ 使用者偏好實例 | @import | gitignored, per-user |
| IDENTITY-{user}.md / USER-{user}.md | 個人擴充槽（IDENTITY 選配）/ USER 編輯點 | 啟用時 @import / 每啟動拷成 USER.md | per-user |
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
| handlers/user_prompt_submit.py | — | UPS orchestrator：串聯 ups_* 四段 + 收尾（2026-06-12 拆分）+ UPS 被 kill 哨兵（`workflow/ups-sentinel/`，殘留→告警）+ AEC (d) 刪除決策後驗（exists() 實查→重注入/告警） |
| handlers/ups_gates.py | — | UPS detect 段：evasion 追蹤 + V4.1 + long_die + hot cache + atom-write guard |
| handlers/ups_context.py | — | UPS context 段：session context + wisdom + parallel + AIDocs + JIT |
| handlers/ups_search.py | — | UPS search 段：RECALL（trigger → BM25 → Vector〔全空 fallback / 專案層 enrichment：trigger 命中 <3 才打〕）+ supersedes + RRF 三路融合 × ACT-R 個別化 decay（`fusion:"legacy"` 可回退；含分心懲罰 `compute_injection_rank`，Memory Governance A） |
| handlers/ups_inject.py | — | UPS inject 段：hot/cold + budget + related spread（含 `_filter_related_by_relevance` 最小集裁切，Memory Governance C）+ 效用晉升提示 |
| handlers/pre_tool_use.py | — | Write/Edit atom format gate + memory path block + cross-realm write block（外部專案 session 禁寫核心層子目錄+根層敏感檔）+ Bash 全域 MCP 變更閘 + SVN test block |
| handlers/post_tool_use.py | — | file tracking + 增量索引 + read tracking + test-fail + changelog auto-roll + AEC one-writer（emit 收訖 + (b) 欄 cross-check：hook 證據 vs 自評「無」→ 升 real-evasion） |
| handlers/stop.py | — | sync 閘門 + Fix Escalation + TestFailGate + Evasion（觸發落 `Logs/guard-evasion.jsonl` + `evasion_events` 證據暫存）+ outcome 三值計數 |
| handlers/session_end.py | — | Episodic + 萃取 + 衝突偵測 + Wisdom 反思 + selective forgetting（`apply_selective_forget` 隔離 `_distant/`，預設 dry-run，Memory Governance D）+ outcome unknown 比率遙測（`workflow/outcome_stats.jsonl` → 連續偏高 marker → SessionStart advisory）+ 失念偵測（`wg_recall_miss` → `Logs/recall-miss.jsonl`） |
| handlers/pre_compact.py | — | state snapshot + injected_atoms 快照 |
| handlers/post_compact.py | — | 壓縮後 stash 壓縮前 atom 緊湊內文 + pending flag（不注入；選配 #4） |
| handlers/post_tool_batch.py | — | idle early-exit；見 flag 一次性 additionalContext 重注入 + 清 flag（選配 #4） |
| handlers/notification.py | — | 通知處理 |
| wg_core.py | — | 路徑唯一真相 + state IO + token budget 單一來源（2026-06-12 集中） + log rotation + PreToolUse guards |
| wg_atoms.py | — | trigger（any/count_trigger_hits 原語）+ BM25 + ACT-R + vector search + atom 晉升 |
| wg_extraction.py | — | per-turn 萃取 + worker + hot cache + user-extract + content classify |
| wg_episodic.py | — | episodic 生成 + 衝突 + 品質回饋 |
| wg_evasion.py | — | Evasion Guard + Test-Fail + ScanReport + 自評整合 + `crosscheck_aec_severity`（(b) 欄 cross-check 純函式）+ `flush_outcome_stats`（unknown 比率遙測） |
| wg_docdrift.py | — | src → _AIDocs 映射 drift 偵測（觸發落 `Logs/guard-docdrift.jsonl`） |
| lang_guard.py | — | P8b 英文回應漂移攔截（standalone Stop hook；觸發落 `Logs/guard-lang.jsonl`） |
| wg_roles.py | — | V4 sub-layer 探勘 shim |
| wg_rescue.py | — | 救援日誌：注入 atom 高特異 token watch + 工具呼叫命中 → `Logs/rescue-log.jsonl`（純字串比對） |
| wg_recall_miss.py | — | 失念偵測（recall-miss）：SessionEnd 比對「失敗證據 × 庫中未注入 atom trigger」（≥2 非泛用詞）→ `Logs/recall-miss.jsonl`；浮出走效果報表 D 節 + 週健檢黃燈 |
| codex_companion.py | — | Codex Companion hook：in-process state + spawn audit.py subprocess |
| extract-worker.py | — | SessionEnd 萃取子程序 |
| user-extract-worker.py | — | L1/L2 使用者決策萃取 |
| quick-extract.py | — | Stop async 快篩 |
| wisdom_engine.py | — | 2 硬規則 + 3 反思指標 + Bayesian arch sensitivity |
| ensure-mcp.py | — | MCP server 可用性確認 |
| user-init.sh | — | 多人 USER.md 初始化 |
| webfetch-guard.sh | — | WebFetch 安全護欄 |

## 5. Skills（<!-- skill-count -->21<!-- /skill-count --> 個 active；記憶系統 skill + 1 個外部/通用 skill〔karpathy-guidelines〕；**init-roles / conflict-review 於 P8a 2026-07-01 單人環境降 dormant → `skills/_archived/`，不計入此數**）

V5 把 commands/*.md 遷到 skills/{name}/SKILL.md 結構（對齊 Anthropic 官方「commands merged into skills」）。Legacy `commands/` 全刪除。

| 指令 | 檔案 | 用途 | 依賴 |
|------|------|------|------|
| /atom-debug | skills/atom-debug/SKILL.md | Debug log 開關 | 無 |
| /codex-companion | skills/codex-companion/SKILL.md | Codex Companion 開關（subprocess 模型，只 toggle config flag） | codex CLI |
| /changelog-debug | skills/changelog-debug/SKILL.md | 手動滾動 _CHANGELOG.md（PostToolUse 已自動，僅 debug） | 無 |
| /conflict | skills/conflict/SKILL.md | 記憶衝突偵測 | Vector Service + Ollama |
| ~~/conflict-review~~ | skills/_archived/conflict-review/SKILL.md | 管理職裁決 Pending Queue（雙向認證）**P8a archived·dormant** | wg_roles + Vector Service |
| /consciousness-stream | skills/consciousness-stream/SKILL.md | 高風險跨系統識流處理 | 無 |
| /continue | skills/continue/SKILL.md | 讀 _staging/next-phase.md 續接 | 無 |
| /extract | skills/extract/SKILL.md | 手動知識萃取 | Ollama |
| /fix-escalation | skills/fix-escalation/SKILL.md | 精確修正升級（6 Agent 會議） | 無 |
| /generate-episodic | skills/generate-episodic/SKILL.md | 手動生成 episodic atom | 無 |
| /handoff | skills/handoff/SKILL.md | 跨 Session Handoff Prompt Builder | 無 |
| /harvest | skills/harvest/SKILL.md | Playwright 網頁收割→Markdown | Playwright |
| ~~/init-roles~~ | skills/_archived/init-roles/SKILL.md | 多職務模式啟用引導 **P8a archived·dormant** | wg_roles + git |
| /memory | skills/memory/SKILL.md | 5 合 1：health / peek / undo / review / session-score（subcmd 分派） | 無 |
| /read-project | skills/read-project/SKILL.md | 系統性閱讀→doc-index atom | 無 |
| /upgrade | skills/upgrade/SKILL.md | 環境升級（diff + merge + rebuild） | 無 |
| /vector | skills/vector/SKILL.md | 向量服務管理 | Vector Service |
| /journal | skills/journal/SKILL.md | 工作日誌產出 | 無 |
| /browse-sprites | skills/browse-sprites/SKILL.md | 批次圖片預覽 | 無 |
| /skill-creator | skills/skill-creator/SKILL.md | **新增 meta-skill**：寫/改/審 skill（三層架構 + 5 設計模式 + audit/new-skill/cost-measure） | 無 |
| /heal-review | skills/heal-review/SKILL.md | 管理職裁決記憶自癒失敗佇列（`_heal_review/` resolve/dismiss；腦內世界 P3） | wg_roles + atom-health-check |
| /refile | skills/refile/SKILL.md | **V6 手動歸檔**：拖入非 `_AIDocs/_atoms/` 的 `.md` → 核心檔辨識護欄 + realm 分類提議 + 互動移檔 + doc-ref 掃描（sweep 的手動鏡像） | Ollama（分類 fallback） |
| /karpathy-guidelines | skills/karpathy-guidelines/SKILL.md | **外部 skill（MIT，源 multica-ai）**：寫/審/重構碼的行為準則（Think Before / Simplicity / Surgical / Goal-Driven）。on-demand 被動觸發，非 always-on；唯一加值的 verify-loop 另萃成 atom `goal-driven-verify-loop` | 無 |

> 已刪除（與內建衝突）：`/resume`（內建 --resume）/ `/init-project`（內建 /init）/ `/svn-update` / `/unity-yaml`（下沉專案層）/ `/changelog-roll`（改名 changelog-debug）
> 已休眠（單人環境·非刪）：`/init-roles` / `/conflict-review`（多人團隊層）→ 見 `skills/_archived/README.md`

## 6. 工具鏈（tools/）

### MCP Server（5 tool）
- `workflow-guardian-mcp/server.js`（+ 11 lib 模組，原 4394 行單檔純機械拆分）— stdio MCP + dashboard port 3848
  - `atom_write` / `atom_move` / `atom_promote` / `atom_edit_meta`（4 個 atom 業務 tool；`atom_edit_meta`=元資料外科編輯 → [SPEC_ATOM_V5 §3.4](SPEC_ATOM_V5.md)）
  - `anti_evasion_report`（收尾檢核 (a)(b)(c)(d) emit → Anti-Evasion HUD；**one-writer**：MCP tool 只回 chip，Python `post_tool_use` 獨佔寫 state + 落 `workflow/aec-report/`；HUD 頁 `lib/{anti-evasion,aec-hud-html}.js` 服）
  - `atom_write` 的 `knowledge` 陣列 block-aware：單一元素以豎線（markdown 表格）或三反引號（程式碼 fence）開頭者整段原樣輸出、不加 bullet、前後補空行（規則 SoT → [SPEC_ATOM_V5 §11](SPEC_ATOM_V5.md)）
  - 內部 IPC 4 個（`workflow_signal` / `workflow_status` / `memory_queue_add` / `memory_queue_flush`）已內化為 Stop gate hook 自動偵測

### Vector Service（port 3849；專案層 + episodic + cross-session dedup 用）
- service.py — HTTP daemon（`ThreadingHTTPServer`：長請求不再 block `/health` 致 starter 誤殺；`POST /index/incremental` 為寫後重索引路由〔MCP funnel 呼叫，順跑 stale chunk 清理〕）
- config.py — config.json 讀寫
- indexer.py — atom→chunk→embed→LanceDB（含 `cleanup_stale_chunks`；ranking 計數欄改讀 `lib.atom_access` sidecar；掃描根走 `atom_locations.atom_search_roots()`——**local realm atoms（`_AIDocs/_atoms/`）一併入索引**；embed 前置「atom 標題+domain」脈絡 prefix）
- searcher.py — semantic + ranked + section-level（5-factor 排名）
- reranker.py — LLM query rewrite + re-rank
- starter.py — 啟動器自癒（kill 前驗 PID cmdline 身分，防 Windows PID 重用誤殺）
- 全域層改 BM25 in-memory（in `wg_atoms.py`），手刻 ~80 行（k1=1.2, b=0.75，ASCII word + 中文 char-bigram tokenization）

### 檢索回歸評估（tools/memory-eval/）
- genqueries.py — 每 atom 以本地 LLM 離線生成「應命中 prompt」＋負例 → queries.jsonl（223 條）
- run.py — 量測 Recall@1/@3、MRR、誤注入率，與 baseline.json 比對（秒級 A/B；RRF/BM25 調參的驗證前提）
- 守門：`tools/verify/verify_memory_eval.py`

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
- memory-audit.py — 格式驗證 + staleness + 晉升建議（對齊線上 usefulness Wilson 閘）；索引 parser 認 CC 原生清單格式 `- [題](檔.md)`（projects 層誤報歸零）
- atom-health-check.py — 參照完整性（含 `_` 前綴豁免 / project→global up-ref / `--shadow-check` 與 _AIDocs 子段相似度偵測 / `--atom <name>` 單顆健康過濾，供 atom-heal 重用）+ **`check_stale_deps` 壞滅緣檢查**（atom `Depends:` path 型指向消失 → 報 stale_deps）
- atom-health-audit.py — atom 體質審視（七類分類：歸檔 / 晉升 / 冷凍 / 缺欄 / trigger 補強 / 保留）
- atom-heal.py — 記憶自癒單一來源（腦內世界 P3）：L1 機械補反向連結(免 LLM) / L2 broken_refs 呼本地 Ollama 出結構化提案經 funnel 套用 / L3 stale 喚醒；後端可插拔（config `heal.backend`，預設 ollama 免費序列、cloud 選配並行）；修不好 → `_heal_review/<atom>.json` 退人工
- heal-review.py — `/heal-review` skill 後端：列 `_heal_review/` 失敗診斷卡，management resolve(重掃確認健康)/dismiss
- check-bypass.py — 靜態掃描 funnel 繞過（WHITELIST 外 `write_text` / `open(w)` / `fs.writeFileSync` 命中 memory 路徑 → CI exit 1）
- audit-reconcile.py — 動態對拍（mtime × audit log entries），三分類（counter_only / knowledge / unknown）
- memory-write-gate.py — 寫入閘門（6 規則 + 0.80 dedup；pitfall 捷徑僅豁免品質分、不豁免 dedup）
- memory-conflict-detector.py — 向量衝突 + LLM 分類（mode ∈ {full-scan / write-check / pull-audit}）；裁決優先序＝證據等級（實證>引述>推測>未標）→ recency + fast-refute 快速否證通道（新側實證 vs 舊側 [固]/[觀] 置頂）
- conflict-review.py — Pending Queue 後端（list / approve / reject，is_management 雙向認證 guard）
- atom-move.py — 跨層原子搬遷工具（mv + 更新 Scope + 同步索引 + 處理 inbound refs）
- sync-atom-index.py — atom frontmatter Trigger ↔ `_atom_index.json` 一致性同步
- sync-memory-index.py — 從 `_atom_index.json` 雙輸出渲染：`MEMORY.md`（core-only，@import）+ `_local_catalog.md`（本地範疇 Lv1 根，hook 注）+ **V6 各層按需 `_INDEX.md`**（有子層 ∨ atom≥2）；`--check` 兩檔 + `_INDEX.md` 深樹 round-trip、stale 清理、caption preserve 跨檔；sweep 搬後補觸發 `--write`
- cleanup-projects-residue.py — projects/{slug}/memory/ 殘骸清理工具

### 常駐可觀測
- statusline.py — settings.json `statusLine` 渲染器：CC status JSON（stdin）+ state/vector flag/aec-report → 一行 ANSI 狀態列（改N 讀M · vec✓ · AEC:sev）；取代 UPS 週期性 Reminder 注入
- health-weekly.py — 週健檢（Task Scheduler `Claude-Memory-WeeklyHealth`，pythonw 靜默跑）：audit/health-check/索引 --check/vector/注入效果/管線鮮度 → `workflow/health-reports/` + `health-last-run.json`（SessionStart `_health_advisory` 死人開關讀取）
- memory-effect-report.py — 注入效果報表：access.json（曝光+α/β）+ rescue-log + recall-miss.jsonl → 四節（top 有用 / token 稅 / 死重候選 / D 失念聚合）+ 30 天週趨勢；`/memory health` 與週健檢共用
- memory-vector-service/starter.py — Vector 啟動器自癒（SessionStart / UPS re-kick 共用）：stderr 落 `Logs/vector-service.log`、hang 死 kill-restart、120s 等待窗 + spawn lock
- native-memory-bridge.py — 核心 atom 索引 → CC 原生 memory 指標鏡像（harness 清單格式，掃描不誤納；`--create` 首次建目錄）

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
- prompts.py — plan review / turn audit / architecture review / **handoff review**（2026-06-24，交接文件對抗式他評）模板，含 SANDBOX_CONSTRAINT 紅線；`verify/verify_handoff_review.py` 12 測
- state.py — per-session 狀態 + per-turn assessment cache（含 metric API + 白名單）
- heuristics.py — 規則式軟閘（< 10ms 無 LLM）；Silent Advisory Mode 預設啟用
- scorer.py — turn-level risk scoring（五因子加權 0-10），< score_threshold 跳過 codex

> Codex Companion 設計原則：軟閘屬「背景品質觀測」，不干擾使用者對話流。`silent_advisory: true` + `max_inject_severity: high` 預設，多數 advisory 走「靜默落盤 + metric 計數」路徑。

### 其他
- read-excel.py（openpyxl + xlrd）
- rag-engine.py（CLI wrapper）
- sprite_contact_sheet.py
- gdoc-harvester/（Playwright 網頁收割 + dashboard）

## 7. 記憶層

- **MEMORY.md**（always loaded via @import，**core-only**）— core atom 主表（人類可讀）+ 末尾一行指標；本地範疇段已抽出（2026-06-04 catalog 層 realm 拆分）
- **_local_catalog.md**（`memory/`，`_` 前綴非 atom）— 本地範疇 catalog；**V6 階層化**：always-load 只列 Lv1 根（World/Tools/MemDev/OS/Else）+ 遞迴計數 + drill 指標，深層走各層按需 `_INDEX.md`（O(根數) 不隨 atom 量膨脹）。僅核心環境由 SessionStart hook 注入，外部專案零負擔。由 `sync-memory-index.py` 與 MEMORY.md 同步雙輸出
- **_atom_index.json**（JSON SoT）— 機器源真相，<!-- atom-total -->85<!-- /atom-total --> atoms 完整索引
- **_ATOM_INDEX.md**（自動生成 mirror）— 人類可讀備援 parser
- **全域 Atoms** = **core**（住 `memory/`：decisions / decisions-architecture / preferences / workflow-rules·icld·svn·parallel-agents / toolchain·-ollama / goal-driven-verify-loop / 自己flag-維護動作直接做完 / escalation-hook-false-fire辨識 / 併發-session-共用工作樹…）+ **feedback + 失敗模式**（feedback-* / cognitive-patterns / memory-pipeline-silent-failure-2026-05，物理在 `_AIDocs/Failures/`）+ **local**（realm=local，住 `_AIDocs/_atoms/<domain 多段階層>/`，只在 cwd∈~/.claude 注入；World / Tools / MemDev / OS / Continuity / Vision）。各房實際計數以 `_atom_index.json` path 前綴為準（勿在此複製數字）。**V6 sweep 自動搬遷**：`memory-index-caption-regen` 於 2026-06-04 由 core 經 LLM fallback 判 local 自動搬到 `MemDev/MemoryIndex/`（記憶系統內部知識，判 local 正確）；OS root 為 wsl2 dogfood 新增；`realm-範疇分區機制-v5` 亦已由 core 搬入 local/MemDev
- **_AIDocs/_atoms/**（realm=local）— 非核心範疇 atom（多段階層 domain：World / Tools / MemDev / OS / Else，如 `OS/Windows/WSL/`）；scope 仍 global、外部專案不注入（例外：`CROSS_PROJECT_LOCAL_DOMAINS` 如 `Continuity` 跨專案注入）。各層按需 `_INDEX.md`（`_` 前綴非 atom）。見 SPEC_ATOM_V5 §2.2 V6 塊
- **_AIDocs/Failures/**（atom 子族） — feedback-* + 失敗模式 atom（跨專案踩坑記錄，屬 core）
- **templates/** — icld-sprint-template 等（仍由 workflow-icld atom 引用）
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
- _AIDocs/ — 知識庫（Architecture / context-memory-governance / SPEC_ATOM_V5 / SPEC_ATOM_V4 / DevHistory / Failures / ClaudeCodeInternals / Tools）
- _AIDocs/context-memory-governance.md — 上下文與記憶治理設計憲法（context rot / 4 失效模式 / memory governance / CLT；注入·萃取自檢 hook 的對齊標的）
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
