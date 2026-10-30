# 架構目錄樹（TECH §10）
[↑ 主文 §10](../TECH.md#10-架構目錄樹)

這份文件回答：每支檔案放在哪、負責什麼。路徑都以 repo 根目錄（`~/.claude/`）為準。

## 頂層概觀樹

```text
~/.claude/
├── CLAUDE.md / IDENTITY.md / USER.md / BOOTSTRAP.md   ← 啟動設定與行為契約
├── settings.json / mcp-servers.template.json / version.json
├── run_verify.py / conftest.py / pytest.ini           ← 全量驗證入口（只留手動排查）
├── rules/ text-specs/ templates/ prompts/ verify/     ← 規則、評分規格、樣板、萃取提示詞、已結案驗收規格
├── .claude/                                           ← 根層自己的部位表與 OverviewHub 設定
├── hooks/                                             ← hook 本體：dispatcher、handlers、wg_* 模組、workers
├── lib/                                               ← 共用函式庫：atom 寫入／讀取、部位表、收據、錄製重播
├── tools/                                             ← 命令列工具與子系統（向量服務、MCP server、驗收裁判…）
├── skills/                                            ← active skill（另有 _archived/）
├── memory/                                            ← 全域記憶層（core realm）
├── _AIDocs/                                           ← 長期知識庫（local realm atom、規格、變更紀錄）
├── workflow/                                          ← 設定與 runtime state（多數 gitignored）
├── Logs/                                              ← 各種執行紀錄
├── projects/<slug>/memory/                            ← CC 原生 auto-memory 橋接（不是記憶層）
└── {project_root}/.claude/                            ← 專案自治層
```

## 根目錄檔案

| 檔案 | 負責什麼 |
|------|----------|
| [`CLAUDE.md`](../CLAUDE.md) | 只 `@IDENTITY.md` `@USER.md` `@memory/MEMORY.md` |
| `IDENTITY.md` | 行為契約（單一真相）；gitignore，[`templates/`](../templates/) 為 tracked 還原源 |
| `USER.md` | 操作者資料；gitignore，[`templates/`](../templates/) 為 tracked 還原源 |
| `IDENTITY-{user}.md` | 個人擴充槽（gitignore） |
| `USER-{user}.md` | USER 編輯點（gitignore；SessionStart 拷成 `USER.md`） |
| [`BOOTSTRAP.md`](../BOOTSTRAP.md) | 不被 `@import`；IDENTITY／USER 為空時的問答引導 |
| [`settings.json`](../settings.json) | 11 個 hook 事件＋statusLine |
| [`mcp-servers.template.json`](../mcp-servers.template.json) | MCP 註冊範本（[§9.3](../TECH.md#93-mcp-註冊hooksensure-mcppy)） |
| [`version.json`](../version.json) | 版本標識 |
| [`run_verify.py`](../run_verify.py) | 全量驗證入口（只留手動排查） |
| [`conftest.py`](../conftest.py) | 根 conftest：`git_cassette` fixture、自寫收據 |
| [`pytest.ini`](../pytest.ini) | pytest 設定 |

## 根層規則與資料夾

| 檔案 | 負責什麼 |
|------|----------|
| [`rules/core.md`](../rules/core.md) | 治理原則、知識庫、記憶、對話規則 |
| [`rules/coding-style.md`](../rules/coding-style.md) | 寫碼傾向（hook 已強制者不重述） |
| [`text-specs/`](../text-specs/) | G15 文字評分規格（資料，[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)） |
| [`templates/`](../templates/) | IDENTITY／USER 還原源、部位病灶清單樣板、打包前檢查樣板 |
| [`prompts/`](../prompts/) | `user-extract-worker` 的決策萃取提示詞（L1／L2） |
| [`verify/done/`](../verify/done/) | 根層已結案的驗收規格 |
| [`.claude/overview-map.md`](../.claude/overview-map.md) | 根層自己的部位表（[附錄 部位表](../TECH/guards.md#部位表)） |
| [`.claude/overview-hub.json`](../.claude/overview-hub.json) | 根層自己的 OverviewHub 設定覆蓋（[附錄 設定來源](../TECH/guards.md#設定來源)） |

- **text-specs/**：不放 [`rules/`](../rules/)，免得每個 session 都載入。

## hooks/

### hooks/ 入口與路由

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/workflow-guardian.py`](../hooks/workflow-guardian.py) | 1 行 shim → `dispatcher.main()` |
| [`hooks/dispatcher.py`](../hooks/dispatcher.py) | 純路由（惰性 import handler）＋hook 分段計時起訖 |
| [`hooks/wg_read_fast.py`](../hooks/wg_read_fast.py) | Read 事件快路徑：只追加讀檔紀錄就結束（READ_FAST_PATH，[§3.1](../TECH.md#31-settingsjson-十一個事件)） |

- **hooks/dispatcher.py**：裁判子 session 走 `JUDGE_HANDLERS`。

### hooks/handlers/

9 個 handler 檔接 11 個事件：`PostToolUseFailure` 走 `post_tool_use`、`SubagentStop` 走 `stop`。

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/handlers/session_start.py`](../hooks/handlers/session_start.py) | SessionStart 事件 handler |
| [`hooks/handlers/session_end.py`](../hooks/handlers/session_end.py) | SessionEnd 事件 handler |
| [`hooks/handlers/user_prompt_submit.py`](../hooks/handlers/user_prompt_submit.py) | UserPromptSubmit 事件 handler |
| [`hooks/handlers/pre_tool_use.py`](../hooks/handlers/pre_tool_use.py) | PreToolUse 事件 handler |
| [`hooks/handlers/post_tool_use.py`](../hooks/handlers/post_tool_use.py) | PostToolUse 事件 handler（兼接 PostToolUseFailure） |
| [`hooks/handlers/stop.py`](../hooks/handlers/stop.py) | Stop 事件 handler（兼接 SubagentStop） |
| [`hooks/handlers/pre_compact.py`](../hooks/handlers/pre_compact.py) | PreCompact 事件 handler |
| [`hooks/handlers/post_compact.py`](../hooks/handlers/post_compact.py) | PostCompact 事件 handler |
| [`hooks/handlers/post_tool_batch.py`](../hooks/handlers/post_tool_batch.py) | PostToolBatch 事件 handler |
| [`hooks/handlers/ups_gates.py`](../hooks/handlers/ups_gates.py) | UPS（UserPromptSubmit）四段之一：閘 |
| [`hooks/handlers/ups_context.py`](../hooks/handlers/ups_context.py) | UPS 四段之一：脈絡 |
| [`hooks/handlers/ups_search.py`](../hooks/handlers/ups_search.py) | UPS 四段之一：搜尋 |
| [`hooks/handlers/ups_inject.py`](../hooks/handlers/ups_inject.py) | UPS 四段之一：注入 |
| [`hooks/handlers/_shared.py`](../hooks/handlers/_shared.py) | handler 共用 |
| [`hooks/handlers/aec_ledger.py`](../hooks/handlers/aec_ledger.py) | AEC 帳本 |

### hooks/ wg_* 核心模組

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/wg_core.py`](../hooks/wg_core.py) | 路徑唯一真相＋state IO＋預算常數＋log rotation |
| [`hooks/wg_atoms.py`](../hooks/wg_atoms.py) | trigger／BM25／RRF／ACT-R／vector client／晉升 |
| [`hooks/wg_extraction.py`](../hooks/wg_extraction.py) | 失敗萃取＋worker spawn＋user-extract L0 |
| [`hooks/wg_episodic.py`](../hooks/wg_episodic.py) | episodic 生成＋TTL purge |
| [`hooks/wg_evasion.py`](../hooks/wg_evasion.py) | 退避偵測＋DeferralGate 判定＋AEC cross-check |
| [`hooks/wg_docdrift.py`](../hooks/wg_docdrift.py) | DocDrift：改了程式、對應的 _AIDocs 沒跟著改時偵測（PostToolUse） |
| [`hooks/wg_handoff.py`](../hooks/wg_handoff.py) | Auto-Handoff：跨 session 自動交接 |
| [`hooks/wg_rescue.py`](../hooks/wg_rescue.py) | 救援日誌：注入的 atom 是否真被用上的直接證據 |
| [`hooks/wg_recall_miss.py`](../hooks/wg_recall_miss.py) | 失念偵測：庫裡有可防的 atom、檢索卻沒命中 |
| [`hooks/wg_friction.py`](../hooks/wg_friction.py) | 工具結果體積（浪費）＋使用者糾正訊號 → DPM |
| [`hooks/wg_hook_timing.py`](../hooks/wg_hook_timing.py) | hook 分段計時：過上限 80% 降級＋計時帳（[§7.1](../TECH.md#71-stop-閘序)、[§8](../TECH.md#8-可觀測與自我維護)） |
| [`hooks/wg_harvest.py`](../hooks/wg_harvest.py) | 階段收割：閘判定／receipt 入帳／items 核對／ledger |
| [`hooks/wg_provenance.py`](../hooks/wg_provenance.py) | 來源自動填：`atom_write` receipt → 補 Source／Quote |
| [`hooks/wg_vcs_sync.py`](../hooks/wg_vcs_sync.py) | 記憶庫上版控的邏輯層（目標集、鎖、請求檔、標記、拉段） |
| [`hooks/wg_coordination.py`](../hooks/wg_coordination.py) | 跨 session 協調（同檔衝突預警） |
| [`hooks/wg_parallel.py`](../hooks/wg_parallel.py) | 多 agent 並行建議偵測（`[Parallel:Suggest]`） |
| [`hooks/wg_research.py`](../hooks/wg_research.py) | 研究 fan-out 建議偵測（`[Research:Fanout]`） |
| [`hooks/wg_roles.py`](../hooks/wg_roles.py) | 身份（AD 帳號）／職能三層解析／裁決資格 `review.deciders` |

- **hooks/wg_hook_timing.py**：過上限 80% 降級，意思是後面的段落只記不問。
- **hooks/wg_harvest.py**：純函式，不落盤。
- **hooks/wg_provenance.py**：補的 Source 是 session 指標，Quote 是使用者原話。
- **hooks/wg_vcs_sync.py**：
  - 目標集、OS 互斥鎖、`.req` 請求檔、`.unpushed`／`.behind` 標記。
  - 拉段：ref＋pathspec restore、ff-only、隔離 worktree rebase、svn update。
  - 另管 `roots.json` 與 spawn。
- **hooks/wg_roles.py**：職能三層解析順序為 `role.md` → AD 群組 → 空。

### hooks/ 部位表與程式檔判準

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/wg_overview.py`](../hooks/wg_overview.py) | 部位設定與查表、讀檔擷取、提醒帳等各守門共用的工具 |
| [`hooks/wg_depends.py`](../hooks/wg_depends.py) | 讀到 Depends 指的檔時召回卡（[附錄 Depends 召回](../TECH/guards.md#depends-召回)） |
| [`hooks/wg_code_path.py`](../hooks/wg_code_path.py) | 判斷一次寫入算不算改程式（寫碼類判準，各閘共用同一份） |

### hooks/ 驗證與放行

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/wg_verify_ledger.py`](../hooks/wg_verify_ledger.py) | 哨兵收據帳本與對帳、量尺閘（[§7.1 收據](../TECH.md#收據)） |
| [`hooks/wg_unknown_write.py`](../hooks/wg_unknown_write.py) | 寫入目標判不出的指令跑完後，從版控狀態補算改了哪些檔 |
| [`hooks/wg_release_rules.py`](../hooks/wg_release_rules.py) | 放行／欠帳具名規則（純函式，[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy)） |
| [`hooks/wg_release.py`](../hooks/wg_release.py) | 擋滿後改問使用者（[§7.3](../TECH.md#73-擋滿之後怎麼放行hookswg_releasepy)） |
| [`hooks/wg_verify_batch.py`](../hooks/wg_verify_batch.py) | 驗證批次閘：同一批改動只驗一次、整組驗證要使用者口令 |

- **hooks/wg_unknown_write.py**：處理的是寫入目標判不出的 Bash／PowerShell 指令，對應 [§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy) `UNKNOWN_WRITE_RECOVERED`。

### hooks/ 宣告閘與收尾輔助

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/wg_data_file.py`](../hooks/wg_data_file.py) | 改資料檔的宣告閘（[§7.5](../TECH.md#75-其他守門)） |
| [`hooks/wg_oldtest.py`](../hooks/wg_oldtest.py) | 改舊測試的宣告閘（[§7.5](../TECH.md#75-其他守門)） |
| [`hooks/wg_gate_bypass.py`](../hooks/wg_gate_bypass.py) | 繞閘的宣告閘（[§7.5](../TECH.md#75-其他守門)） |
| [`hooks/wg_ask_gate.py`](../hooks/wg_ask_gate.py) | 問使用者前每題要附推薦（AskUserQuestion／ExitPlanMode），帳寫 `Logs/guard-ask.jsonl` |
| [`hooks/wg_reading_path.py`](../hooks/wg_reading_path.py) | 閱讀路徑與拐彎判斷（[§7.1](../TECH.md#71-stop-閘序)） |
| [`hooks/wg_closing_round.py`](../hooks/wg_closing_round.py) | 收尾只跑一輪（[§7.1](../TECH.md#71-stop-閘序)） |
| [`hooks/wg_bg_harvest.py`](../hooks/wg_bg_harvest.py) | 收割交背景免費模型（[§11.2](../TECH.md#112-寫碼守門的減量原則)） |
| [`hooks/wg_lazy_re.py`](../hooks/wg_lazy_re.py) | 模組層正規表示式第一次用到才編譯（[§11.2](../TECH.md#112-寫碼守門的減量原則)） |
| [`hooks/wg_chain.py`](../hooks/wg_chain.py) | 連鎖斷路器判定（純函式，[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)） |
| [`hooks/plan_bash_guard.py`](../hooks/plan_bash_guard.py) | Plan Mode 必彈窗的 Bash 寫法 deny＋改寫提示（[§7.5](../TECH.md#75-其他守門)） |

- **hooks/wg_ask_gate.py**：開關跟寫碼守門總開關；沒附推薦的提問提醒補上（ASK_NEEDS_RECOMMENDATION），提問涉及改法選擇時另提醒先讀部位檔（ASK_OVERVIEW_BEFORE_DECISION）。
- **hooks/wg_closing_round.py**：
  - PostToolBatch 起跑拐彎判斷量測。
  - 交收尾檢核那批附結果與最該修（[§7.1](../TECH.md#71-stop-閘序)）。
- **hooks/wg_bg_harvest.py**：Stop 丟背景、產待審候選卡。
- **hooks/wg_lazy_re.py**：每個 hook 事件少編上百條。
- **hooks/wg_chain.py**：涵蓋連鎖狀態、警報、三選一、還原計畫、經過表。

### hooks/ 其他模組與 workers

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/wisdom_engine.py`](../hooks/wisdom_engine.py) | Wisdom Engine：情境分類（硬規則）＋反思（滑動視窗） |
| [`hooks/codex_companion.py`](../hooks/codex_companion.py) | Codex Companion hook：審計觸發與驗收裁判（[§7.4](../TECH.md#74-驗收裁判ai-審查-ai-產出四段閉環)） |
| [`hooks/lang_guard.py`](../hooks/lang_guard.py) | 英文回應漂移攔截（獨立 Stop hook） |
| [`hooks/version_guard.py`](../hooks/version_guard.py) | 版本操作脈絡殘留 warn（PostToolUse 同程序呼叫） |
| [`hooks/acceptance_spec.py`](../hooks/acceptance_spec.py) | 驗收規格工件（PostToolUse 同程序呼叫） |
| [`hooks/extract-worker.py`](../hooks/extract-worker.py) | detached worker：失敗萃取 |
| [`hooks/user-extract-worker.py`](../hooks/user-extract-worker.py) | detached worker：使用者決策萃取 |
| [`hooks/vcs-sync-worker.py`](../hooks/vcs-sync-worker.py) | detached worker：記憶庫上版控 |
| [`hooks/run-hidden.py`](../hooks/run-hidden.py) | 隱藏視窗執行 |
| [`hooks/run-bash-hidden.py`](../hooks/run-bash-hidden.py) | 隱藏視窗執行 Bash |
| [`hooks/ensure-mcp.py`](../hooks/ensure-mcp.py) | 確保 MCP 就緒 |
| [`hooks/user-init.sh`](../hooks/user-init.sh) | shell hook |
| [`hooks/post-git-pull.sh`](../hooks/post-git-pull.sh) | shell hook |
| [`hooks/webfetch-guard.sh`](../hooks/webfetch-guard.sh) | shell hook |

- **hooks/vcs-sync-worker.py**：
  - git：pathspec add＋commit → 拉 → push 守門。
  - svn：`--xml` add／delete／update／commit。

### hooks/verify/

| 檔案 | 負責什麼 |
|------|----------|
| [`hooks/verify/`](../hooks/verify/) | `verify_*.py` 驗證案例 |
| [`hooks/verify/fixtures/`](../hooks/verify/fixtures/) | 案例用的真事件與文字樣本 |
| [`hooks/verify/probe_c_g16.py`](../hooks/verify/probe_c_g16.py) | 真 hook 入口探針：提問閘（C-G16） |
| [`hooks/verify/probe_move_dir.py`](../hooks/verify/probe_move_dir.py) | 真 hook 入口探針：[MOVE_CODE_DIR_NEEDS_SCAN_AND_SAMPLE](../TECH/release-rules.md#move_code_dir_needs_scan_and_sample) |
| [`hooks/verify/probe_release_rules.py`](../hooks/verify/probe_release_rules.py) | 真 hook 入口探針：放行／欠帳判定規則情境 |
| [`hooks/verify/probe_retry_cycles.py`](../hooks/verify/probe_retry_cycles.py) | 真 hook 入口探針：[RETRY_COUNTS_RERUN_CYCLES](../TECH/release-rules.md#red_while_revertedretry_counts_rerun_cyclesgreen_same_case_clears) |
| [`hooks/verify/probe_state_parallel_perf.py`](../hooks/verify/probe_state_parallel_perf.py) | 量測：平行 N 支 hook 改同一份 state 的耗時與掉帳（[STATE_RMW_LOCKED](../TECH/release-rules.md#state_rmw_lockedstate_pending_merged)） |

- **hooks/verify/fixtures/**：`gate005`、`gate006`、`v6` 目錄放寫碼守門樣本；`gate006` 放條件句宣稱文字。

## lib/

| 檔案 | 負責什麼 |
|------|----------|
| [`lib/atom_io.py`](../lib/atom_io.py) | 寫入 funnel＋`locate_atom` 落點單一裁決 |
| [`lib/atom_io_cli.py`](../lib/atom_io_cli.py) | `atom_io` 的命令列；另有唯讀 action `search`／`source`／`realm_check`（[§9.2](../TECH.md#92-外部依賴用途替代缺了會怎樣)） |
| [`lib/memory_search.py`](../lib/memory_search.py) | 讀取端 `search()` |
| [`lib/atom_locations.py`](../lib/atom_locations.py) | 物理位置＋路由規則（core／failures／local／project） |
| [`lib/atom_spec.py`](../lib/atom_spec.py) | 合法性規範 |
| [`lib/atom_taxonomy.py`](../lib/atom_taxonomy.py) | Lv1 閉合清單＋`classify_category` |
| [`lib/atom_index_json.py`](../lib/atom_index_json.py) | JSON SoT API |
| [`lib/atom_access.py`](../lib/atom_access.py) | access sidecar＋Wilson |
| [`lib/realm_gate.py`](../lib/realm_gate.py) | 專案專屬內容不得落 global |
| [`lib/provenance.py`](../lib/provenance.py) | 來源回看（三態） |
| [`lib/ollama_extract_core.py`](../lib/ollama_extract_core.py) | 共享萃取核心＋`SessionBudgetTracker` |
| [`lib/state_rmw.py`](../lib/state_rmw.py) | hook 以外的寫者改 session state 的唯一入口（守同一把鎖，[STATE_RMW_LOCKED](../TECH/release-rules.md#state_rmw_lockedstate_pending_merged)） |
| [`lib/atom_classify.py`](../lib/atom_classify.py) | 統一分類核心：realm 與專案 taxonomy 共用的計分骨架 |
| [`lib/taxonomy_classify.py`](../lib/taxonomy_classify.py) | 單後端批次分類器（jury 的可組合單元） |
| [`lib/taxonomy_jury.py`](../lib/taxonomy_jury.py) | 專案 taxonomy 引擎（最小殼） |
| [`lib/game_taxonomy.py`](../lib/game_taxonomy.py) | 遊戲開發起手分類種子詞庫 |
| [`lib/project_root.py`](../lib/project_root.py) | 資料根／設定目錄算法、`project-tree.json` 尋根（[§4.5](../TECH.md#45-索引json-單一真相)、[§4.6](../TECH.md#46-專案層)） |
| [`lib/transcript_tokens.py`](../lib/transcript_tokens.py) | transcript 找檔＋token 合計（同一則回覆按 message.id 只算一次、含子代理）；`skills/token`、`skill-cost-measure.py` 共用 |

- **lib/memory_search.py**：MCP `memory_search`、cli `search`、[`tools/memory-search.py`](../tools/memory-search.py) 共用。
- **lib/provenance.py**：函式有 `sanitize_quote`、`format_source_session`、`parse_source`、`find_transcript`、`resolve_context`、`atom_source`（三態）。

### lib/ 部位表與閱讀路徑

| 檔案 | 負責什麼 |
|------|----------|
| [`lib/overview_hub.py`](../lib/overview_hub.py) | 部位表查表（[附錄 部位表](../TECH/guards.md#部位表)） |
| [`lib/hub_config.py`](../lib/hub_config.py) | [`overview-hub.json`](../.claude/overview-hub.json) 四層合併（[附錄 設定來源](../TECH/guards.md#設定來源)） |
| [`lib/hub_card.py`](../lib/hub_card.py) | 導讀卡五段與寫卡預算 |
| [`lib/overview_scaffold.py`](../lib/overview_scaffold.py) | 從零掃表（[附錄 部位表](../TECH/guards.md#部位表)） |
| [`lib/turn_metrics.py`](../lib/turn_metrics.py) | Python 函式與類別的側面數據（只量不判，[§7.1](../TECH.md#71-stop-閘序)） |
| [`lib/turn_metrics_cs.py`](../lib/turn_metrics_cs.py) | C# 函式與類別的側面數據（只量不判，[§7.1](../TECH.md#71-stop-閘序)） |
| [`lib/reading_path_cs.py`](../lib/reading_path_cs.py) | C# 改動的一跳範圍閱讀路徑（[§7.1](../TECH.md#71-stop-閘序) ReadingPath） |
| [`lib/cs_roslyn.py`](../lib/cs_roslyn.py) | Roslyn 解析前端（[§7.1](../TECH.md#71-stop-閘序) ReadingPath） |
| [`lib/cs_roslyn/`](../lib/cs_roslyn/) | Roslyn 解析的小程式（[§7.1](../TECH.md#71-stop-閘序) ReadingPath） |

### lib/ 收據、文字與其他

| 檔案 | 負責什麼 |
|------|----------|
| [`lib/self_receipt.py`](../lib/self_receipt.py) | 指令解析與自寫收據 |
| [`lib/git_cassette.py`](../lib/git_cassette.py) | git／svn 錄製重播（見文末） |
| [`lib/harness_text.py`](../lib/harness_text.py) | 取出「使用者本人打的字」 |
| [`lib/narrative_date.py`](../lib/narrative_date.py) | 敘事型日期判式（唯一實作） |
| [`lib/refix_churn.py`](../lib/refix_churn.py) | 反覆修熱點 |
| [`lib/vcs_ignore.py`](../lib/vcs_ignore.py) | 專案記憶衍生檔退出版控 |
| [`lib/codex_models.py`](../lib/codex_models.py) | Codex 模型驗證 |
| [`lib/chain_store.py`](../lib/chain_store.py) | 連鎖斷路器的帳、改檔前快照、還原、使用者答案（I/O） |
| [`lib/config_local.py`](../lib/config_local.py) | `workflow/config.local.json` 蓋到 `config.json` 的規則（唯一一份，[§12](../TECH.md#12-設定總表workflowconfigjson)） |
| [`lib/verify/`](../lib/verify/) | lib 的驗證案例 |

- **lib/chain_store.py**：判定在 [`hooks/wg_chain.py`](../hooks/wg_chain.py)（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）。

## tools/

### tools/ 記憶稽核與維護

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/ollama_client.py`](../tools/ollama_client.py) | Ollama 客戶端 |
| [`tools/statusline.py`](../tools/statusline.py) | statusline |
| [`tools/health-weekly.py`](../tools/health-weekly.py) | 每週健康檢查 |
| [`tools/followup-check.py`](../tools/followup-check.py) | 回訪檢查 |
| [`tools/memory-audit.py`](../tools/memory-audit.py) | 記憶稽核 |
| [`tools/memory-write-gate.py`](../tools/memory-write-gate.py) | 記憶寫入閘 |
| [`tools/memory-conflict-detector.py`](../tools/memory-conflict-detector.py) | 衝突偵測 |
| [`tools/memory-effect-report.py`](../tools/memory-effect-report.py) | 記憶效果報表 |
| [`tools/memory-peek.py`](../tools/memory-peek.py) | 萃取歷史查看 |
| [`tools/memory-undo.py`](../tools/memory-undo.py) | 萃取歷史還原 |
| [`tools/memory-session-score.py`](../tools/memory-session-score.py) | session 評分 |
| [`tools/sync-atom-index.py`](../tools/sync-atom-index.py) | 同步 atom 索引 |
| [`tools/sync-memory-index.py`](../tools/sync-memory-index.py) | 同步記憶索引 |
| [`tools/sync_doc_counts.py`](../tools/sync_doc_counts.py) | 同步文件計數 |
| [`tools/native-memory-bridge.py`](../tools/native-memory-bridge.py) | 原生記憶橋接 |
| [`tools/merge-atom-index.py`](../tools/merge-atom-index.py) | 合併 atom 索引 |
| [`tools/atom-io-audit.py`](../tools/atom-io-audit.py) | 稽核帳壞行檢查（`--check`）與修復（`--repair`） |

- **tools/atom-io-audit.py**：稽核帳是 `memory/_meta/atom_io_audit.jsonl`；`--repair` 時原檔留旁檔。

### tools/ atom 操作

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/atom-move.py`](../tools/atom-move.py) | 搬 atom |
| [`tools/atom-categorize.py`](../tools/atom-categorize.py) | 歸類 atom |
| [`tools/atom-set-realm.py`](../tools/atom-set-realm.py) | 改 realm |
| [`tools/atom-heal.py`](../tools/atom-heal.py) | atom 自癒 |
| [`tools/atom-health-check.py`](../tools/atom-health-check.py) | atom 健檢 |
| [`tools/atom-source.py`](../tools/atom-source.py) | 命令列回看卡片來源（[§5.8](../TECH.md#58-讀取端-memory_search-與-atom_source給其他-ai-與腳本)） |
| [`tools/atom-provenance-backfill.py`](../tools/atom-provenance-backfill.py) | 舊 atom 補 Source／Quote 的回填 worker（[§8](../TECH.md#8-可觀測與自我維護)） |
| [`tools/quote-cleanup.py`](../tools/quote-cleanup.py) | 刪掉被回填成一兩個字回覆的 Quote 行 |
| [`tools/hook-timing.py`](../tools/hook-timing.py) | hook 分段耗時量尺（唯讀，[§8](../TECH.md#8-可觀測與自我維護)） |
| [`tools/memory-search.py`](../tools/memory-search.py) | 命令列查記憶 |
| [`tools/org-memory.py`](../tools/org-memory.py) | 公司層 org 管理 |

- **tools/quote-cleanup.py**：被回填成一兩個字回覆（預設「A」）的 Quote 行才刪；預設 dry-run，`--apply` 走 `atom_io.write_raw`（[§8](../TECH.md#8-可觀測與自我維護)）。
- **tools/hook-timing.py**：各事件跑幾次、降級幾次、各段中位數。
- **tools/org-memory.py**：接上 `--join`、對帳 `--status`、初始化 `--init`、工具卡掃描 `--scan-tools`；使用者入口 `/org` skill。

### tools/ 職能、安裝與外部入口

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/conflict-review.py`](../tools/conflict-review.py) | 待審裁決 |
| [`tools/init-roles.py`](../tools/init-roles.py) | 職能覆寫與對帳（`--me`／`--status`） |
| [`tools/heal-review.py`](../tools/heal-review.py) | 自癒退件 |
| [`tools/realm_llm_classify.py`](../tools/realm_llm_classify.py) | realm 的 LLM 分類 |
| [`tools/skill-index.py`](../tools/skill-index.py) | skill 索引 |
| [`tools/changelog-roll.py`](../tools/changelog-roll.py) | changelog 滾動 |
| [`tools/journal-aggregate.py`](../tools/journal-aggregate.py) | journal 彙整 |
| [`tools/install.py`](../tools/install.py) | 安裝器：`--check`／`--apply`／`--upgrade`／`--verify`（[§9.5](../TECH.md#95-安裝與升級toolsinstallpy)） |
| [`tools/fix-hook-python.py`](../tools/fix-hook-python.py) | 校正 hook 直譯器路徑（[`install.py`](../tools/install.py) 會呼叫） |
| [`tools/ai-client-setup.py`](../tools/ai-client-setup.py) | 其他 AI 客戶端輕量安裝：只註冊 MCP、不裝 hooks（[§5.8](../TECH.md#58-讀取端-memory_search-與-atom_source給其他-ai-與腳本)） |
| [`tools/meeting-transcribe.py`](../tools/meeting-transcribe.py) | 會議錄音 → 逐字稿 → 摘要 → 決議入專案 shared（[§6.6](../TECH.md#66-會議轉錄入庫toolsmeeting-transcribepy)） |
| [`tools/codex-call.py`](../tools/codex-call.py) | 叫 Codex 的唯一入口：把提示詞交給 `codex exec`，回答案或明確失敗（驗收裁判經它叫） |

- **tools/install.py**：操作步驟見 [`Install-forAI.md`](../Install-forAI.md)。
- **tools/codex-call.py**：可當函式 import，也可命令列跑（`--help`）；叫不起來或逾時回非 0 並印原因，不報成功。

### tools/ 評分、閱讀路徑與量測

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/text-score.py`](../tools/text-score.py) | 文字規格評分（[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)） |
| [`tools/text-score-weekly.py`](../tools/text-score-weekly.py) | 文字評分週彙總（[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)） |
| [`tools/project-smells.py`](../tools/project-smells.py) | commit 前病形檢查（[§7.5](../TECH.md#75-其他守門) SmellGate） |
| [`tools/reading-path.py`](../tools/reading-path.py) | 閱讀路徑量尺 |
| [`tools/reading_path_lang.py`](../tools/reading_path_lang.py) | 閱讀路徑語言解析 |
| [`tools/overview-map-scaffold.py`](../tools/overview-map-scaffold.py) | 部位表骨架 |
| [`tools/project-tree.py`](../tools/project-tree.py) | `project-tree.json` 增刪改 |
| [`tools/refix-churn.py`](../tools/refix-churn.py) | 反覆修熱點 |
| [`tools/session-artifacts.py`](../tools/session-artifacts.py) | HUD 保留／刪除背後的產出物帳本 |
| [`tools/move-dir-check.py`](../tools/move-dir-check.py) | 搬程式目錄的兩張收據 |
| [`tools/replay-guard.py`](../tools/replay-guard.py) | 回放實驗洩題守門 |
| [`tools/config-consistency.py`](../tools/config-consistency.py) | 設定鍵一致性 |
| [`tools/atom-date-lint.py`](../tools/atom-date-lint.py) | atom 敘事日期 |
| [`tools/normalize-eol.py`](../tools/normalize-eol.py) | 換行統一 LF |
| [`tools/check-bypass.py`](../tools/check-bypass.py) | 反證沒人繞過 `atom_io` |
| [`tools/classify-project-scope.py`](../tools/classify-project-scope.py) | 專案 scope 分類 |
| [`tools/rag-engine.py`](../tools/rag-engine.py) | RAG 引擎 |
| [`tools/cleanup-old-files.py`](../tools/cleanup-old-files.py) | 清舊檔 |
| [`tools/cleanup-projects-residue.py`](../tools/cleanup-projects-residue.py) | 清專案殘留 |

### tools/ 子系統資料夾

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/memory-eval/`](../tools/memory-eval/) | 回歸集（[`queries.jsonl`](../tools/memory-eval/queries.jsonl) 一行一題）與線上基線 |
| [`tools/memory-vector-service/`](../tools/memory-vector-service/) | 向量服務 |
| [`tools/codex-companion/`](../tools/codex-companion/) | Codex 評估夥伴 |
| [`tools/workflow-guardian-mcp/`](../tools/workflow-guardian-mcp/) | MCP server（Node.js） |
| [`tools/auto-continue/`](../tools/auto-continue/) | 自動續接 |
| [`tools/gdoc-harvester/`](../tools/gdoc-harvester/) | Google 文件收割 |
| [`tools/unity-desktop/`](../tools/unity-desktop/) | Unity 桌面工具 |
| [`tools/usage-snapshot/`](../tools/usage-snapshot/) | 用量快照 |
| [`tools/verify/`](../tools/verify/) | tools 的驗證案例 |

- **tools/memory-vector-service/**：含 [`service.py`](../tools/memory-vector-service/service.py)、[`starter.py`](../tools/memory-vector-service/starter.py)、[`indexer.py`](../tools/memory-vector-service/indexer.py)、[`searcher.py`](../tools/memory-vector-service/searcher.py)、[`reranker.py`](../tools/memory-vector-service/reranker.py)。
- **tools/codex-companion/**：含 `assessor`、`acceptance`、`judge_backend`、[`audit.py`](../tools/codex-companion/audit.py)、`backtest`；`assessor` 經 [`tools/codex-call.py`](../tools/codex-call.py) 叫 codex，codex 不在時退 `claude -p` 由 `judge_backend` 選。
- **tools/workflow-guardian-mcp/**：
  - [`server.js`](../tools/workflow-guardian-mcp/server.js)
  - [`lib/`](../lib/)（[`mcp.js`](../tools/workflow-guardian-mcp/lib/mcp.js)、[`atom-tools.js`](../tools/workflow-guardian-mcp/lib/atom-tools.js)、[`harvest.js`](../tools/workflow-guardian-mcp/lib/harvest.js)、[`funnel.js`](../tools/workflow-guardian-mcp/lib/funnel.js)、[`anti-evasion.js`](../tools/workflow-guardian-mcp/lib/anti-evasion.js) 等）
  - [`verify/smoke_mcp_stdio.js`](../tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js)
  - [`world.html`](../tools/workflow-guardian-mcp/world.html)

### tools/ 其他工具

| 檔案 | 負責什麼 |
|------|----------|
| [`tools/atom-depends-portable.py`](../tools/atom-depends-portable.py) | 把 atom 的 path 型 Depends 從絕對路徑改成可攜寫法 |
| [`tools/generate-episodic-manual.py`](../tools/generate-episodic-manual.py) | 手動觸發 episodic atom 生成 |
| [`tools/read-excel.py`](../tools/read-excel.py) | Excel 讀取工具（.xls／.xlsx） |
| [`tools/sprite_contact_sheet.py`](../tools/sprite_contact_sheet.py) | 為一個資料夾的 sprite 產生縮圖總覽圖 |
| [`tools/console-window-trace.ps1`](../tools/console-window-trace.ps1) | 追蹤來路不明的可見 console 視窗與完整父行程鏈 |

## skills/

<!-- skill-count -->29<!-- /skill-count --> 個 active skill。

| 檔案 | 負責什麼 |
|------|----------|
| [`skills/atom-debug/`](../skills/atom-debug/) | active skill |
| [`skills/atom-source/`](../skills/atom-source/) | active skill |
| [`skills/behavior-preservation/`](../skills/behavior-preservation/) | active skill |
| [`skills/browse-sprites/`](../skills/browse-sprites/) | active skill |
| [`skills/changelog-debug/`](../skills/changelog-debug/) | active skill |
| [`skills/codex-companion/`](../skills/codex-companion/) | active skill |
| [`skills/conflict/`](../skills/conflict/) | active skill |
| [`skills/consciousness-stream/`](../skills/consciousness-stream/) | active skill |
| [`skills/console/`](../skills/console/) | active skill |
| [`skills/continue/`](../skills/continue/) | active skill |
| [`skills/extract/`](../skills/extract/) | active skill |
| [`skills/fix-escalation/`](../skills/fix-escalation/) | active skill |
| [`skills/generate-episodic/`](../skills/generate-episodic/) | active skill |
| [`skills/handoff/`](../skills/handoff/) | active skill |
| [`skills/harvest/`](../skills/harvest/) | active skill |
| [`skills/heal-review/`](../skills/heal-review/) | active skill |
| [`skills/journal/`](../skills/journal/) | active skill |
| [`skills/karpathy-guidelines/`](../skills/karpathy-guidelines/) | active skill |
| [`skills/mailbox/`](../skills/mailbox/) | active skill |
| [`skills/meeting/`](../skills/meeting/) | active skill |
| [`skills/memory/`](../skills/memory/) | active skill |
| [`skills/org/`](../skills/org/) | active skill |
| [`skills/read-project/`](../skills/read-project/) | active skill |
| [`skills/refile/`](../skills/refile/) | active skill |
| [`skills/skill-creator/`](../skills/skill-creator/) | active skill |
| [`skills/text-score/`](../skills/text-score/) | active skill：手動叫文字評分（[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)） |
| [`skills/token/`](../skills/token/) | active skill：量 session 實際處理的 token（含子代理、不換美金；共用 [`lib/transcript_tokens.py`](../lib/transcript_tokens.py)） |
| [`skills/upgrade/`](../skills/upgrade/) | active skill |
| [`skills/vector/`](../skills/vector/) | active skill |
| [`skills/_archived/`](../skills/_archived/) | 封存：`init-roles`、`conflict-review`（單人環境 dormant） |

## memory/

全域記憶層（core realm）。

| 檔案 | 負責什麼 |
|------|----------|
| [`memory/MEMORY.md`](../memory/MEMORY.md) | Lv1 目錄（生成，不手編） |
| [`memory/_atom_index.json`](../memory/_atom_index.json) | JSON SoT |
| [`memory/_ATOM_INDEX.md`](../memory/_ATOM_INDEX.md) | [`_atom_index.json`](../memory/_atom_index.json) 的 mirror |
| [`memory/_local_catalog.md`](../memory/_local_catalog.md) | local realm 目錄 |
| [`memory/_by_language/_INDEX.md`](../memory/_by_language/_INDEX.md) | 依程式語言篩選的跨範疇視圖（生成，只列路徑不搬檔） |
| [`memory/_meta/`](../memory/_meta/) | 詮釋資料與詞庫 |
| [`memory/_meta/migration.json`](../memory/_meta/migration.json) | 雙欄位遷移（dual-field-v1）的執行紀錄：時間、筆數、明細 |
| [`memory/Failures/`](../memory/Failures/) | `feedback-*` 與失敗模式 atom（`Failures/<主題>/`） |
| [`memory/_vectordb/`](../memory/_vectordb/) | LanceDB＋`audit.log` |
| `memory/_promotion_audit.jsonl` | 晉升稽核帳 |
| `memory/project-registry.json` | 專案登錄 |

- **memory/<Lv1>/**：核心 atom，範疇如版控／工作流／…／CC與原子記憶契約；可再分 `<Lv2>/`。
- **memory/Failures/**：另有 `_reference/` 參考文件。
- **memory/ 其他資料夾**：`episodic/`、`wisdom/`、`_staging/`、`_drafts/`、`_distant/`、`_reference/`、`personal/`、[`templates/`](../templates/)。
- **memory/_meta/**：
  - [`taxonomy.json`](../memory/_meta/taxonomy.json)
  - [`forbidden-phrases.json`](../memory/_meta/forbidden-phrases.json)
  - `realm-lexicon*.json`
  - [`taxonomy-lexicon-learned.json`](../memory/_meta/taxonomy-lexicon-learned.json)
  - [`always-load-contracts.json`](../memory/_meta/always-load-contracts.json)（必載檔契約）
  - `atom_io_audit.jsonl`

## _AIDocs/

長期知識庫。

| 檔案 | 負責什麼 |
|------|----------|
| [`_AIDocs/_INDEX.md`](../_AIDocs/_INDEX.md) | 文件索引 |
| [`_AIDocs/_CHANGELOG.md`](../_AIDocs/_CHANGELOG.md) | 變更紀錄 |
| [`_AIDocs/_CHANGELOG_ARCHIVE.md`](../_AIDocs/_CHANGELOG_ARCHIVE.md) | 變更紀錄封存 |
| [`_AIDocs/_changelog.d/`](../_AIDocs/_changelog.d/) | 多軌開發時各工作軌的變更紀錄分段（`<軌>-<NNN>.md`），合併時由 changelog-fold 併進 [`_CHANGELOG.md`](../_AIDocs/_CHANGELOG.md) |
| [`_AIDocs/Architecture.md`](../_AIDocs/Architecture.md) | 架構 |
| [`_AIDocs/DocIndex-System.md`](../_AIDocs/DocIndex-System.md) | 文件導覽 |
| [`_AIDocs/Project_File_Tree.md`](../_AIDocs/Project_File_Tree.md) | 專案檔案樹 |
| [`_AIDocs/SPEC_ATOM_V5.md`](../_AIDocs/SPEC_ATOM_V5.md) | atom 規格 V5 |
| [`_AIDocs/SPEC_ATOM_V4.md`](../_AIDocs/SPEC_ATOM_V4.md) | atom 規格 V4 |
| [`_AIDocs/MultiMachineMemorySync.md`](../_AIDocs/MultiMachineMemorySync.md) | 多機記憶同步 |
| [`_AIDocs/known-regressions.md`](../_AIDocs/known-regressions.md) | 已知回歸 |
| [`_AIDocs/context-memory-governance.md`](../_AIDocs/context-memory-governance.md) | 脈絡與記憶治理 |
| [`_AIDocs/_atoms/`](../_AIDocs/_atoms/) | local realm atom |

- **_AIDocs/_atoms/**：`_atoms/<domain>/`，domain 如 World／Tools／MemDev／OS／Vision 等（[§4.3](../TECH.md#43-realmcore-vs-local)）。
- **_AIDocs/ 其他資料夾**：`ClaudeCodeInternals/`、`Research/`、`Tools/`、`Vision/`、`DevHistory/`。

## workflow/

runtime state（多數 gitignored）。

| 檔案 | 負責什麼 |
|------|----------|
| [`workflow/config.json`](../workflow/config.json) | 統一設定（tracked） |
| `workflow/config.local.json` | 本機專屬設定覆寫（gitignore） |
| `workflow/followups.local.json` | 回訪表本機旁檔：每次跑的結果、提醒日（gitignore） |
| [`workflow/config-consistency-notes.json`](../workflow/config-consistency-notes.json) | 設定一致性量測的備註（tracked） |
| `workflow/state-{sid}.json` | session state |
| [`workflow/followups.json`](../workflow/followups.json) | 回訪表 |
| `workflow/cross-project-index-cache.json` | 跨專案索引快取 |
| `workflow/vector_ready.flag` | 向量服務就緒旗標 |
| `workflow/acceptance-audit.jsonl` | 驗收稽核帳 |
| `workflow/companion-backend.json` | companion 後端 |
| `workflow/outcome_stats.jsonl` | 結果統計 |

### workflow/ 資料夾

| 檔案 | 負責什麼 |
|------|----------|
| `workflow/aec-report/` | AEC 報告 |
| `workflow/aec-tempfiles/` | AEC 暫存 |
| `workflow/ups-sentinel/` | UPS 哨兵 |
| `workflow/health-reports/` | 健康報告 |
| `workflow/verify-ledger/` | 收據帳本 |
| `workflow/tracking/` | 追蹤項 |
| `workflow/old-test-snap/` | 改舊測試快照 |
| `workflow/reading-path/` | 閱讀路徑 |
| `workflow/chain-snap/<session>/` | 連鎖斷路器的改檔前快照（gitignore，[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)） |
| `workflow/inbox/` | 多 session 派工信箱 |
| `workflow/harvest-ledger/<sid>.jsonl` | 收割核對帳本（gitignore） |
| `workflow/vcs-sync/` | 記憶庫上版控的鎖、標記與請求檔（gitignore） |

- **workflow/inbox/**：含 `to-track-*/`、`from-track-*/`、`_console/`；本機資料（[§13.4](../TECH.md#134-多-session-協作雙總控台與工作軌)）。
- **workflow/vcs-sync/**：內容為 `roots.json`、`<root-hash>.{lock,unpushed,behind}`、`<root-hash>.req/`。

## Logs/、projects/ 與專案自治層

| 檔案 | 負責什麼 |
|------|----------|
| `Logs/` | 各種執行紀錄 |
| `projects/<slug>/memory/` | CC 原生 auto-memory；`atom-index-bridge.md` 橋接（不是記憶層） |
| `{project_root}/.claude/` | 專案自治層 |
| `{project_root}/.claude/memory/` | 專案記憶 |
| `{project_root}/.claude/project-tree.json` | 根層列 subs／子層指 root |
| `{project_root}/.claude/overview-map.md` | 部位表（[附錄 部位表](../TECH/guards.md#部位表)） |
| `{project_root}/.claude/overview-hub.json` | OverviewHub 設定覆蓋（[附錄 設定來源](../TECH/guards.md#設定來源)） |
| `{project_root}/.claude/verify/acceptance-<slug>.md` | 專案驗收規格 |
| `{project_root}/.claude/hooks/project_hooks.py` | delegate |

- **Logs/**：`injection-turns`、`rescue-log`、`recall-miss`、`guard-*`、`chain-<session>.jsonl`、`vector-service`、`vcs-sync.log`、`session-coordination/`、`atom-debug-*`。
- **{project_root}/.claude/memory/**：`shared/<Lv1>/`、`failures/<主題>/`、`personal/<user>/`、`roles/<role>/`、`episodic/`、`_staging/`。
- **project-tree.json**：子專案 cwd 歸根層；[`tools/project-tree.py`](../tools/project-tree.py) 增刪改。

## 全量驗證入口

收尾不跑全量：該跑哪些由 AI 判斷，說修好要有改完之後的收據（[§7.1](../TECH.md#71-stop-閘序)）。

- 全量入口 [`python run_verify.py`](../run_verify.py) 已從流程拔掉，只留手動排查（全量改增量待補）。
- 掃描範圍：[`hooks/`](../hooks/)、[`lib/`](../lib/)、[`tools/`](../tools/)、`codex-companion`、`auto-continue` 及 skills 各 [`verify/`](../verify/)。
- `--help` 只印用法不跑。
- 結尾印哨兵 `VERIFY_CHECK DONE cases=<n> failed=0`；有紅印 FAIL 且 exit 1。
- 自寫收據記紅掉的測試名 `failed_cases`。
- 案數看哨兵行的 `cases=`。
- git／svn e2e 族在全量或有其他 git 活動並行時，偶發單案紅、單跑穩定。
  - 涉及案例：`verify_vcs_sync_worker`、`verify_merge_driver_gate`、`verify_merge_atom_index` 內各一案。
  - 推論：工具內 git 子行程 5 秒逾時在負載下觸發。
- MCP js 層另有 [`node tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js`](../tools/workflow-guardian-mcp/verify/smoke_mcp_stdio.js)（不在 `run_verify` 掃描範圍）。

## git／svn 子程序錄製重播

實作在 [`lib/git_cassette.py`](../lib/git_cassette.py)＋根 [`conftest.py`](../conftest.py) 的 `git_cassette` fixture。守門：[`lib/verify/verify_git_cassette.py`](../lib/verify/verify_git_cassette.py)。

測試照舊用真 repo 寫情境，但 git／svn 呼叫平常重播一次真實執行的紀錄，不開子程序。

### 錄製

- 每次呼叫前後掃受測目錄（`tmp_path`）。
- 記下指令、目錄、結束碼、輸出，以及它造成的檔案變化。

### 重播

- 逐筆核對指令、目錄、呼叫前受測目錄內容。
  - 不比：git 的 index、svn 的 `wc.db`、受測程式的 `.log`。
  - 排除：hook 在測試沒導走資料根時寫的守門紀錄 `_tmp/wg-test-logs`，由根 conftest 的 `RUNTIME_EXCLUDE` 排除。
- 全對才交回當時輸出、寫回當時的檔案變化。
- 任何一項不同 → 測試失敗並要求 `pytest --git-record`（或 `WG_GIT_CASSETTE=record`）重錄；那次才跑真 git、照舊驗斷言。
- `WG_GIT_CASSETTE=off`：直接跑真 git，不錄不播。

### 讓換機器、換天都對得上

- 路徑（受測目錄、程式碼樹、直譯器、session 暫存目錄）每種寫法各一個記號，重播時還原成同一種寫法。
- 指令裡的日期正規化。
- fixture 把暫存目錄改成 `tmp_path/_tmp`，暫存檔名與 uuid4 改成序號。
- 受測程式交給 git 的暫存檔也受比對，指令參數每次相同。

### 自動重錄條件

- 會被 git 叫起來的本專案程式（例：合併驅動）列在 `code`，雜湊變了就自動重錄。
- 錄製檔也記下錄製時的 git／svn 版本；這台機器現在的版本不同（升版、同事機器版本不同）就自動重錄。
- 換版後第一次跑會慢一次（版本每個測試行程每種工具只問一次）。

### 檔案位置與限制

- 錄製檔在測試模組旁 `cassettes/<模組>/<測試>.json.gz`（隨程式碼上版控）。
- 限制：受測程式開子程序再叫的 git（例：[`merge-atom-index.py --resolve`](../tools/merge-atom-index.py)）照常真跑。

### 目前套用（共 13 支）

- git 呼叫量最大的一批。
- hooks/verify：`verify_vcs_sync_worker`、`verify_stop_reconcile`、`verify_merge_driver_gate`、`verify_overview_hub`、`verify_unpushed_advisory`、`verify_sync_reminder_unpushed`、`verify_reading_path_hook`、`verify_personal_sync_advisory`、`verify_gate_bypass`、`verify_smell_gate`。
- tools/verify：`verify_reading_path`、`verify_merge_atom_index`、`verify_normalize_eol`。
- `verify_install` 不適用：repo 建在模組共用目錄、git 在 [`install.py`](../tools/install.py) 子程序裡跑。
- 其餘 git 呼叫 10 次以下的測試檔照舊跑真 git。
