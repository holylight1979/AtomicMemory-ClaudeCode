# 設定總表（TECH §12）
[↑ 主文 §12](../TECH.md#12-設定總表workflowconfigjson)

- 預設欄的「只在程式預設」＝該鍵 config.json 沒寫、值在程式裡；要改就在 config.json 加這個鍵。
- 這台機器專屬的值寫在 `workflow/config.local.json`（不進版控）；合併規則見主文 [§12](../TECH.md#12-設定總表workflowconfigjson)。
- [`tools/config-consistency.py`](../tools/config-consistency.py) 會讀本文件每張表的第一欄，從反引號抓設定鍵當作「有定義」的來源之一。
- 表格放不下的細節，在各表下方用條列補充。

## 設定總表

### 總開關與守門次數

| 鍵 | 預設 | 意義 |
|----|------|------|
| `coding_guard.enabled` / `coding_turn_only` / `slim_reminders` | false / true / true（後兩個沒寫＝true） | 寫碼守門總開關與兩個退回開關 |
| `stop_gate_max_blocks` / `min_files_to_block` | 2 / 2 | Stop 閘每使用者回合最多擋幾次／幾檔以上才擋 |
| `chain_breaker.enabled` / `depth_alarm` / `max_depth` / `max_same_gate` / `snapshot_max_bytes` / `snapshot_max_files` / `restore_retries` | true / false / 2 / 2 / 5000000 / 200 / 3 | 連鎖斷路器（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)），寫碼守門開才跑 |

- **`coding_guard.enabled` / `coding_turn_only` / `slim_reminders`**：
  - 守門總開關見 [§7](../TECH.md#7-守門與收尾) 開頭；`WG_CODING_GUARD=1`／`0` 優先。
  - `coding_turn_only=false`：退回每回合都啟動寫碼守門（[§11.2](../TECH.md#112-寫碼守門的減量原則) [CODING_TURN_ONLY](../TECH/release-rules.md#coding_turn_only)）。
  - `slim_reminders=false`：退回需求目標提示每則附三種情況全文與樹根一行（[§7.7](../TECH.md#77-需求目標樹need_goal)「重看」、[§7.8](../TECH.md#78-放行欠帳判定規則hookswg_release_rulespy) [CRITIQUE_CASES_ONCE_PER_SESSION](../TECH/release-rules.md#critique_cases_once_per_session)／[TREE_LINE_IN_HINTS](../TECH/release-rules.md#tree_line_in_hints)）。
- **`stop_gate_max_blocks` / `min_files_to_block`**：
  - 這是共用擋次的 Stop 閘：一個使用者回合最多擋幾次／幾檔以上才擋。
  - 寫碼守門開時每個使用者回合重新計次；寫碼守門關時整個 session 累計。
- **`chain_breaker.*`**（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）：
  - 寫碼守門開才跑；沒寫這段＝不開。
  - `max_same_gate`＝同一道閘第幾次警報。
  - 深度照算照列；`depth_alarm` 開了才在深度到 `max_depth` 時也警報（沒寫＝不警報）。
  - `snapshot_max_bytes`＝單檔快照上限；`snapshot_max_files`＝一段最多存幾個快照；`restore_retries`＝還原每檔重試次數。

### 寫碼查核與交付閘

| 鍵 | 預設 | 意義 |
|----|------|------|
| `reconcile_gate.block_letters` / `goal_gate` / `max_blocks_per_turn` | ["a","d"] / false / 2 | 寫碼查核（[§7.1](../TECH.md#71-stop-閘序)）的擋收尾範圍 |
| `aec.scan_report_gate` / `hud_stale_s` | false / 75 | 沒交收尾檢核擋不擋收尾／HUD 幾秒沒更新算死 |
| `atom_audit.enabled` | false | 卡片表態閘（[§7.1](../TECH.md#71-stop-閘序) AtomAudit） |
| `second_opinion.auto.enabled` / `min_code_files` / `min_changed_lines` / `risky_prefixes` / `max_blocks_per_turn` / `background` | true / 4 / 150 / [] / 1 / true | 大任務收尾自動要求第二意見（[§7.1](../TECH.md#71-stop-閘序) SecondOpinion） |
| `pick_one.enabled` / `pre_close` | true / true | 交付時順手點出最該修的一件（[§7.1](../TECH.md#71-stop-閘序) PickOne） |
| `acceptance_regression_hint.enabled` | true | 驗收真命中後建議補測試（[§7.1](../TECH.md#71-stop-閘序) 迴歸提示） |
| `reading_path.early_start` | true | 改程式檔那批跑完就起跑拐彎判斷量測（[§7.1](../TECH.md#71-stop-閘序) ReadingPath） |
| `reading_path.remind_only_over_threshold` | true | 沒有任何一條到門檻就不問模型、不附提醒行 |
| `reading_path.turn_judgment.turns` / `nesting` / `bumpy` / `handoff_chain` / `inherit_depth` / `max_items` / `cs_layers` | 2 / 3 / 2 / 2 / 3 / 8 / 3 | 拐彎判斷門檻與一次最多問幾條 |
| `acceptance_spec.min_files_trigger` | 3 | 規格工件建議門檻 |
| `deferral_gate.max_context_ratio` / `min_object_chars` | 0.75 / 6 | DeferralGate |
| `lang_guard.english_ratio_threshold` / `min_lang_chars` | 0.5 / 40 | 英文漂移 |
| `version_guard.mode` | warn | 版本脈絡殘留 |
| `docdrift.path_mappings` / `self_path_mappings` | 空 / hooks→Architecture.md、skills/rules/tools→DocIndex-System.md | 文件漂移（[§7.5](../TECH.md#75-其他守門) DocDrift）的路徑對應 |
| `codex_companion.soft_gate.handoff_review` / `handoff_review_v6` | true / false（後者只在程式預設） | Codex 接續單自檢（[§5.7](../TECH.md#57-其他注入來源同一-additionalcontext)） |

- **`reconcile_gate.block_letters` / `goal_gate` / `max_blocks_per_turn`**（[§7.1](../TECH.md#71-stop-閘序)）：
  - 只有列出的條目字母擋收尾，其餘照判、只印 stderr（規則 [RECONCILE_BLOCK_LETTERS](../TECH/release-rules.md#reconcile_block_letters)）。
  - `goal_gate=false`（沒寫也一樣）時，目標樹對照 (f1)～(f4) 與 commit 前的目標對照不擋（[§7.7](../TECH.md#77-需求目標樹need_goal)）。
  - `max_blocks_per_turn`＝紅測與寫碼查核每個使用者回合共用的擋次，不分哪一條規則（[BLOCK_BUDGET_SHARED](../TECH/release-rules.md#block_budget_shared)）。
  - 另有 `code_exts`（程式檔副檔名）、`verify_case_globs`（案例檔樣式）。
- **`second_opinion.auto.*`**：
  - 高風險部位改在部位表標類別 gate；`risky_prefixes` 只給要另列路徑的專案。
  - `second_opinion` 其餘鍵（model、timeout_s…）管 job 本身。
- **`pick_one.enabled` / `pre_close`**：`pre_close` 在交收尾檢核那批先附。
- **`reading_path.early_start`**：改了程式檔那批跑完就起跑拐彎判斷量測，交收尾檢核那批附結果。
- **`reading_path.remind_only_over_threshold`**：
  - 背景量完沒有任何一條到門檻要問 → 整段不送模型、不附提醒行，只留帳 under_threshold。
  - 有才送條目＋那一題。
- **`reading_path.turn_judgment.*`**：`cs_layers`＝C# 路上拐彎、繼承層數超過幾個才問。
- **`docdrift.path_mappings` / `self_path_mappings`**：
  - 前者由專案自己填。
  - 後者是記憶系統自己的對應，只在改的檔落在 `~/.claude` 底下才套。
- **`codex_companion.soft_gate.handoff_review` / `handoff_review_v6`**：寫碼守門關看前者，寫碼守門開看後者。

### commit 與資料檔閘

| 鍵 | 預設 | 意義 |
|----|------|------|
| `guard.smell_gate.enabled` | true | git／svn commit 前病形閘（[§7.5](../TECH.md#75-其他守門) SmellGate） |
| `guard.commit_order.{enabled,keywords,exempt_cwd_under_claude_dir}` | true / 上GIT、上乾淨、全上、執P… / true | git commit 口令閘：沒口令就 deny |
| `sync_reminder.{enabled,max_reminders,unpushed}` | true / 1 / true | Stop 同步閘；unpushed=true 時已 commit 未 push 也擋 |
| `sync_keywords` | 同步、sync、commit、提交、結束、收工 | 使用者說這些字時注入同步提醒 |
| `privacy.enabled` / `deny_globs` | true / []（追加；只在程式預設） | git commit 隱私硬閘 |
| `guard.data_file_ask.enabled` / `old_test_declare.enabled` / `gate_bypass.enabled` / `origin_user_check.enabled` | true / true / true / true | 改資料檔、改舊測試、繞閘的宣告閘（[§7.5](../TECH.md#75-其他守門)）／目標樹「使用者說的」要對得上原話（[§7.7](../TECH.md#77-需求目標樹need_goal)） |
| `guard.smell_gate.anon_body_block_lines` / `anon_body_list_lines` / `nesting_block_depth` | 20 / 10 / 4 | 病形閘門檻（[§7.5](../TECH.md#75-其他守門) SmellGate） |
| `verify_ledger.enabled` / `sentinel_regex` | true / PASS／FAIL／DONE 兩條＋pytest 映射 | 哨兵收據入帳（[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)） |
| `overview_hub.*` | 見 [§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub) | 部位導讀卡與寫入閘 |
| `scorecard.*` / `refix_churn.*` / `overview_scaffold.*` | — | 過程量報表、反覆修熱點、部位表掃骨架的參數（[§7.6](../TECH.md#76-寫碼守門部位導讀卡overviewhub)） |

- **`guard.commit_order.*`：口令判定**
  - 本回合使用者原話（`state.turn_prompts`，含 mid-turn 排隊訊息；Stop 關回合）無任一口令 → deny。
  - 口令被否定或延後不算：
    - 同一子句（逗號句號分號換行為界，頓號與「或」不斷）裡，它左邊有否定字（不要、不可以、別…）或「等我…」。
    - 或右邊只剩不帶對象的否定（「上GIT 先不要」）。
    - 「上GIT 別碰 X」的否定有自己的對象，照算。
  - 否定詞表只會多擋不會多放。
  - 使用者原話只認剔掉其他 session 訊息與系統注入後的字。
  - 背景通知（task-notification）開的回合視為上一回合的延續：使用者原話沿用、通知內文不算口令。
- **`guard.commit_order.*`：一般說法授權**
  - 「commit／push／提交」這類一般字不是口令。
  - 使用者用一般說法授權時，LLM 判斷是授權就在指令裡附 `# 授權原句：「…」`。
  - 引用沒有提交動作字也行，如在回「回了我才 commit」的「其他照做」，條件是：
    - 引用與所在子句沒被否定。
    - 同一則原話沒有被否定或延後的提交動作。
    - 沒有「等我／我看完」。
  - 程式核對：原句逐字在本回合使用者原話裡、含提交類動作字、至少一個動作字在原話裡沒被否定，才放行（stderr 記放行原句）。
- **`guard.commit_order.*`：口令什麼時候用掉**
  - 寫碼守門開時：撐到這批 push 完或使用者打字開新回合。
    - 只 commit、續跑回合、收尾閘逼出的補修 commit，都不讓它失效。
    - 有一段子命令真的是 git push 或 svn commit 而且跑成功才算 push 完；echo、commit 訊息、`--dry-run` 不算。
    - 多個 repo 一起上要先全部 commit 再 push（規則 [ORDER_UNTIL_PUSH](../TECH/release-rules.md#order_until_push)）。
  - 寫碼守門關時：口令之後已 commit 過就不沿用（USER.md 縮寫指令契約的程式化版本；state 缺失 fail-open）。
- **`guard.commit_order.exempt_cwd_under_claude_dir`**：
  - 每段 commit 實際落在原子記憶系統自己的 repo（~/.claude 本身或它的 git worktree）才不等口令。
  - 只認看得出落點的句型：`&&` 串、第一段可 `cd <絕對路徑>`、其餘每段 `git [-C <字面路徑>] add/commit/push/…`；其他寫法照常要口令。
- **`guard.commit_order.*`：shell 包裝裡的 commit 照常檢查**
  - 保留引號狀態切段：Bash `\`、cmd `^`、PowerShell 反引號續行接回；引號外 token 起頭的 `#` 到行尾當註解略過。
  - 看執行檔 basename（帶引號的 `"C:/Program Files/Git/bin/bash.exe"`、PowerShell `&` 呼叫都認）＋任意啟動選項＋執行旗標（`bash -lc`、`powershell -NoProfile -Command`、`cmd /d /c`…）。
  - 內層拆得出且全是 log/status/diff/show 查詢才放行；真 commit、再包一層、eval／命令替換判不明照查。
  - 逐段判，每段先以外層 shell 語意查整段原文（含包裝內層自己的外層引號）。
  - 子 shell 括號／eval／命令替換照查；雙引號裡的 `$(…)`／反引號算會執行（只有單引號裡是字面）。
- **`guard.commit_order.*`：已知邊界**
  - 命令裡有 `$()` 等展開又含 commit 字樣一律要口令（`cd "$(git rev-parse …)" && git log --grep=commit` 也是），擋訊息會說查詢請拿掉 commit 字樣或改用單引號。
  - heredoc 逐行只剝到第一個結束行（零行內文也算）；起始行後的 `&& git commit` 照查。
  - `Git`／`GIT.EXE` 大小寫同判。
  - Bash 工具的 `cd /c/…`、`-C /c/…` 轉成 `C:/…` 再找落點（PowerShell 工具不轉）。
- **`overview_hub.*`**：
  - 另有 `overview_hub.min_map.enabled`（無表專案的最小地圖）、`overview_hub.equivalence.enabled`（等值與熱路徑閘）。
  - `overview_hub.svn_test_block.enabled`（svn 提交測試路徑閘，預設關，[§7.5](../TECH.md#75-其他守門)）也在這段。
  - 專案可用 [`.claude/overview-hub.json`](../.claude/overview-hub.json) 覆蓋。

### 注入與檢索

| 鍵 | 預設 | 意義 |
|----|------|------|
| `taxonomy.gate_enabled` | true | create 缺 domain 拒寫 |
| `entrypoint.inject_budget_tokens` | 400 | 切入點契約（[§7.10](../TECH.md#710-切入點契約程式問卡教llm-判留帳回看)）每個切入點各自的判準卡知識段預算 |
| `entrypoint.inject_budget_total` | 1200 | 同一則問句所有切入點加起來的上限 |
| `taxonomy.llm_fallback.enabled` / `realm.llm_fallback.enabled` | false / false | 分類只跑決定性詞庫 |
| `vector_search.enabled` / `service_port` | true / 3849 | 向量服務 |
| `vector_search.global_layer` / `fusion` | bm25 / rrf | 全域層演算法／融合策略（legacy 回退） |
| `vector_search.bm25_min_score` / `bm25_top_k` | 7.0 / 3 | BM25 入場 |
| `vector_search.search_top_k` / `search_min_score` / `search_timeout_ms` | 5 / 0.65 / 3500 | vector 入場 |
| `vector_search.fallback_backend` / `fallback_model` | sentence-transformers / BAAI/bge-m3 | 無 Ollama 時的 embedder |
| `vector_search.ollama_backends.*` | rdchat-direct(1) / local(3) | Dual-Backend |
| `injection.redundancy_gate.min_shared_triggers` | 3 | 同題去冗 |
| `injection.related_gate.max_related` / `skip_demoted` | 6 / true | related spread |
| `injection.truncated_pointer_max` | 3 | 總額裁切犧牲者指標行數 |
| `vector_search.rrf_activation_gain` | 0（程式預設 0.25） | 活化對排序的增益；0＝活化不左右相關性排序（[§5.2](../TECH.md#52-深度解說每個設計的意義)） |
| `vector_search.bm25_gate_max_trigger_hits` | 999 | 每輪都跑 BM25；設 2＝只在 trigger 命中 ≤2 時補位 |
| `injection.related_depth` | 1（只在程式預設） | Related 擴散深度；0＝關閉 |
| `injection.related_gate.query_gate_min` | 5（程式預設 3.5） | 鄰居對整池 BM25 分數低於此值不擴散 |
| `session_context.max_episodic` / `reserved_tokens` / `min_score` / `search_timeout_ms` | 3 / 200 / 0.35 / 1500（只在程式預設） | 首次 prompt 帶入的過往 session 摘要：筆數、預留預算、門檻、逾時 |

### 寫入與萃取

| 鍵 | 預設 | 意義 |
|----|------|------|
| `write_gate.quality_floor` / `dedup_score` / `dedupe_declaration` | 0.3 / 0.8 / true | 寫入品質閘 |
| `usefulness.wilson_z` / `promote_lb` / `min_n` / `demote_lb` / `demote_min_n` / `decay_lambda` / `stability_gamma` | 1.28 / 0.6 / 3 / 0.35 / 5 / 0.97 / 0.3 | 效用晉升軌 |
| `usefulness.fix_min_n` | 10 | `[觀]→[固]`（手動 `atom_promote`）要的證據數；下界同 `promote_lb` |
| `usefulness.distraction_enabled` / `distraction_weight` | true / 0.5 | 分心懲罰 |
| `response_capture.session_end_max_chars` / `session_end_max_items` | 20000 / 5 | SessionEnd 全量萃取 |
| `response_capture.failure_extraction.cooldown_seconds` / `max_items` | 180 / 2 | 失敗萃取 |
| `response_capture.per_turn.enabled` / `session_end_flush.enabled` | false / false | 已停產（見下方補充） |
| `userExtraction.tokenBudget` | 240 | 使用者決策萃取每 session 預算 |
| `episodic.auto_generate` / `min_files` / `min_duration_seconds` | true / 1 / 120 | episodic 生成 |
| `harvest.enabled` / `min_turns` / `min_accessed` / `min_turns_between` | true / 3 / 5 / 3 | 階段收割 Stop 閘（[§6.3](../TECH.md#63-自動萃取在跑-vs-已停產)） |
| `harvest.background` / `background_model` / `background_max_cards` / `background_timeout_sec` | true / gemma4:e4b / 3 / 180 | 收割交背景免費模型（[§11.2](../TECH.md#112-寫碼守門的減量原則)） |
| `self_iteration.forget.enabled` / `dry_run` | false / true | selective forgetting |
| `provenance.enabled` / `quote_max_chars` / `anti_rot_days` / `backfill.enabled` | true / 200 / 25 / true | 卡片來源（[§4.1](../TECH.md#41-atom-卡片格式) Source／Quote） |
| `atom_debug` | false | 檢索除錯 log |

- **`write_gate.quality_floor` / `dedup_score` / `dedupe_declaration`**：相似達 `dedup_score` 要 AI 宣告；`dedupe_declaration=false`＝舊的直接拒。
- **`response_capture.session_end_max_chars` / `session_end_max_items`**：萃取是脫離主程序的 worker，沒有逾時鍵。
- **`response_capture.per_turn.enabled` / `session_end_flush.enabled`**：
  - per_turn 已無呼叫端，改 true 不會回滾（要回滾得 revert 程式）。
  - session_end_flush 仍由 [`session_end.py`](../hooks/handlers/session_end.py) 讀，改 true 會恢復 SessionEnd 全量萃取寫 [臨] atom。
- **`harvest.enabled` / …**：活動門檻與冷卻；缺整段＝機制關。
- **`harvest.background` / …**：
  - true 不擋，產待審候選卡與目標樹進度草稿（[`hooks/wg_bg_harvest.py`](../hooks/wg_bg_harvest.py)）。
  - 模型不在只記 failed、不改用付費模型。
  - false 照舊擋。
- **`provenance.*`**（[§4.1](../TECH.md#41-atom-卡片格式) Source／Quote、[§8](../TECH.md#8-可觀測與自我維護) 來源自動填與回填 worker）：
  - `enabled` 是總開關；`quote_max_chars` 是 Quote 上限字數。
  - `anti_rot_days`：週健檢防腐天數，session 來源距今超過此天數仍無 Quote 就補。
  - `backfill.enabled`：SessionStart 回填 worker 開關。
  - 缺整段＝全開。

### 背景服務與同步

| 鍵 | 預設 | 意義 |
|----|------|------|
| `dashboard_port` | 3848 | Dashboard + HUD |
| `hook_timing.enabled` / `degrade_ratio` / `fallback_limit_s` | true / 0.8 / `{"SessionStart": 20, "UserPromptSubmit": 8, "PreToolUse": 5, "PostToolUse": 5, "Stop": 10}` | hook 分段計時（[§7.1](../TECH.md#71-stop-閘序) 表下、[§8](../TECH.md#8-可觀測與自我維護)） |
| `vcs_sync.enabled` / `push` / `root_pathspecs` / `project_pathspecs` / `root_extra_pathspecs` / `org_extra_pathspecs` / `exclude` / `timeout_s` | true / true / [memory, _AIDocs/_atoms] / [.claude/memory] / [TECH.md, _AIDocs/_INDEX.md, _AIDocs/DocIndex-System.md] / [usage-snapshots] / [**/*.access.json, memory/_meta/**] / 60 | 記憶庫背景上版控 worker（[§8](../TECH.md#8-可觀測與自我維護)） |
| `vcs_sync.pull.enabled` / `fetch_timeout_s` / `cooldown_s` | true / 20 / 600（`cooldown_s` 只在程式預設） | 記憶層自動拉取（[§6.3](../TECH.md#63-自動萃取在跑-vs-已停產) 拉段） |
| `self_iteration.auto_commit_promotions` / `auto_push_promotions` | true / true | 舊鍵，已由 `vcs_sync.enabled` / `push` 接管 |
| `coordination.enabled` / `warn_suppress_min` / `scan_mtime_window_s` / `max_scan_files` | true / 10 / 1800 / 20 | 跨 session 預警 |
| `coordination.v6_once` | true（只在程式預設） | 同檔預警同一個檔一個 session 只警一次（[§5.7](../TECH.md#57-其他注入來源同一-additionalcontext)） |
| `parallel_agents.*` / `research_fanout.*` | enabled | 多 agent 拆分／研究 fan-out 判準注入 |
| `parallel_agents.v6_once` / `jit_internal_pipeline.v6_once` / `aidocs.v6_once` / `aidocs.advisory_v6_once` | true / true / true / true（只在程式預設） | 同一提示送過就不再送（[§5.7](../TECH.md#57-其他注入來源同一-additionalcontext)） |
| `self_iteration.oscillation_v6_once` / `rut_v6_once` | true / true（只在程式預設） | 振盪／覆轍提示只列沒列過的項（[§5.7](../TECH.md#57-其他注入來源同一-additionalcontext)） |
| `auto_handoff.token_warn_ratio` / `context_window_tokens` | 0.85 / 1000000 | token 預警 |
| `deep_postmortem.enabled` / `aec.hud_autospawn` | true / true | DPM / HUD 自動開 |
| `friction.enabled` / `min_hits` / `keywords` | true / 2 / 省略＝模組內建表 | 使用者糾正訊號 → DPM |
| `tool_result_waste.enabled` / `oversized_chars` / `max_advisories_per_session` | true / 20000 / 3 | 工具結果體積量測與提醒 |
| `changelog_auto_roll.enabled` / `threshold` | true / 8 | [`_AIDocs/_CHANGELOG.md`](../_AIDocs/_CHANGELOG.md) 條目超過門檻自動滾進 ARCHIVE |
| `skill_index.enabled` | true | 維護 [`skills/_skill_index.json`](../skills/_skill_index.json)，SessionStart 比對 skill 數 |
| `realm.auto_migrate` | true | SessionEnd realm 自動搬移掃描（[§4.3](../TECH.md#43-realmcore-vs-local)） |
| `tool_selftests` / `depends_coverage_min` | config-consistency 一項 / 0 | 週健檢工具自測清單／Depends 覆蓋率門檻（[§8](../TECH.md#8-可觀測與自我維護)） |

- **`hook_timing.*`**：
  - 累計過上限的 `degrade_ratio` 這個比例就降級。
  - `fallback_limit_s`：settings.json 讀不到 timeout 時的上限，也決定哪些事件計時。
  - 只在 `wg_core.DEFAULTS`，config.json 沒寫。
- **`vcs_sync.*`**（[§8](../TECH.md#8-可觀測與自我維護)）：
  - 根層 pathspec 相對 ~/.claude，專案相對專案根。
  - `root_extra_pathspecs`（atom 寫入連動的文件計數標記檔）與 `org_extra_pathspecs`（公司層 repo 根，如週用量截圖）是非記憶但一起自動推拉的路徑，只進 pathspec 不進 mem_dirs。
  - `root_extra_pathspecs` 的單檔文件只代上計數標記的變動：跟 HEAD 比、拿掉 `<!-- x -->…<!-- /x -->` 標記內的數字後要一模一樣才收；人手改到一半的文件留在工作樹、log 印 `EXTRA_DOC_MARKER_ONLY`，等上GIT（[`hooks/wg_vcs_sync._marker_only_change`](../hooks/wg_vcs_sync.py)）。
  - `timeout_s`＝每步 git／svn 指令逾時。
- **`vcs_sync.pull.*`**（[§6.3](../TECH.md#63-自動萃取在跑-vs-已停產) 拉段）：
  - SessionStart 的拉取請求在 `last_pull` 冷卻內且記憶路徑沒有本地變更就跳過。
  - worker 每輪 commit 之後、push 之前 fetch 並併入純記憶 incoming。
  - 與 `push` 開關獨立。
  - fetch 逾時只落 `.behind`、不影響 push 段。
- **`self_iteration.auto_commit_promotions` / `auto_push_promotions`**：晉升 sweep 後改 spawn vcs-sync worker；鍵保留供相容讀取，實際開關以 vcs_sync 為準。
- **`coordination.v6_once`**：
  - 寫碼守門開時同檔預警同一個檔一個 session 只警一次（warn-cache 留 24 小時）。
  - false 或寫碼守門關，照 `warn_suppress_min` 分鐘後重警。
- **`parallel_agents.v6_once` 等四鍵**：
  - 寫碼守門開時：並行建議、JIT 管線說明送過就不再送。
  - AIDocs 相關文件同一份只指一次。
  - 寫暫時性檔名進 `_AIDocs` 的提醒同一個檔只一次。
  - false 或寫碼守門關退回每次送。
- **`self_iteration.oscillation_v6_once` / `rut_v6_once`**：false 或寫碼守門關，每次開場都列全部。

### 公司層與身份

| 鍵 | 預設 | 意義 |
|----|------|------|
| `review.deciders` | `[]` | 待審草稿裁決名單（AD 帳號） |
| `roles.ad_group_map` | 核心程式／伺服器程式／程式→programmer、美術→art、企劃→planner、QA→qa、PM→pm | AD 群組名的職能名子字串對映 |
| `org_memory.repo_url` / `default_root` | 已填公司 repo（見 config）/ `~/CompanyAtomsMem` | 公司層記憶 repo（[§4.4](../TECH.md#44-四層-scope)）全公司相同的值 |
| `org_memory.enabled` / `roots` | false / `[]` | 共用 config 保持預設；實際值在本機檔 |

- **`review.deciders`**：空＝人人可裁決；config 壞 → fail-open True + stderr。
- **`roles.ad_group_map`**：
  - AD 群組名格式 `<網域>\<專案代碼>_<序號>_<職能名>`，取其中職能名做子字串對映（先比長鍵）。
  - 專案 MEMORY.md `> Project-Code: XXX` 可限定只取該專案群組。
- **`org_memory.repo_url` / `default_root`**：`repo_url` 供 `--join` 在本機沒 checkout 時 clone；`default_root` 是 `--join` 沒給路徑時的落點。
- **`org_memory.enabled` / `roots`**：
  - 實際值在本機 `workflow/org-memory.local.json`（不進版控，同名鍵蓋過），用 [`tools/org-memory.py --join`](../tools/org-memory.py)／`--init <root>` 填寫。
  - 只讀 `roots[0].root`，>1 停用並 stderr。
  - 本機檔另有 `declined`（使用者答過先不接，啟動不再問；舊鍵 `advised` 已不讀）。

### 評分與第二意見

| 鍵 | 預設 | 意義 |
|----|------|------|
| `codex_companion.enabled` / `score_threshold` / `max_audits_per_session` | true / 7 / 30 | Codex Companion |
| `codex_companion.fallback.model` / `reprobe_hours` | sonnet / 24 | 裁判備援（只發 advisory、不擋） |
| `codex_companion.max_inject_severity` | high | 驗收裁判（[§7.4](../TECH.md#74-驗收裁判ai-審查-ai-產出四段閉環)）的附說明嚴重度門檻 |
| `codex_companion.codex_extra_args` / `codex_binary` | [] / 不設（只在程式預設：從 PATH 找） | codex exec 的額外旗標／執行檔路徑 |
| `codex_companion.audit_quota.acceptance_review_min/max` | 6 / 8 | 配額分桶 |
| `text_score.judge_model_by_backend` / `judge_model` | {rdchat-direct: gemma4:e4b, local: qwen3:4b-instruct-2507-q4_K_M} / gemma4:e4b | G15 文字規格評分（[§7.11](../TECH.md#711-文字規格評分g15toolstext-scorepy)）裁判模型 |
| `text_score.default_spec` / `timeout_sec` / `num_ctx` | reader-designer / 120 / 8192 | 預設規格、裁判逾時、context 長度 |
| `text_score.enabled` / `min_chars` / `auto_targets` | true / 300 / {final_reply: []} | 只管自動評 |

- **`codex_companion.max_inject_severity`**：
  - 整段歸寫碼守門開關。
  - Stop 永不擋；審查結果 fail 且嚴重度 ≥ 此值才在下一則附完整說明，其餘只附一行。
- **`codex_companion.codex_extra_args` / `codex_binary`**：
  - `codex_extra_args` 原樣附加到 codex exec 的旗標，裁判與第二意見共用。
  - `codex_binary` 是 codex 執行檔路徑。
  - 只有某台機器要的旗標或路徑，寫在 `workflow/config.local.json` 的 `codex_companion` 段；設定的路徑找不到檔也退 PATH。
- **`text_score.judge_model_by_backend` / `judge_model`**：
  - 每台 backend 各自的裁判（正確性為主：內網 e4b、本機跑不動 e4b 用 instruct-2507）。
  - 沒列到的 backend 用 `judge_model`；`--model` 全部覆蓋。
  - 跨機同標籤要比 digest。
- **`text_score.default_spec` / `timeout_sec` / `num_ctx`**：預設規格、每次問裁判的逾時、每次明帶的 context 長度。
- **`text_score.enabled` / `min_chars` / `auto_targets`**：
  - 只管自動評：收尾接線 [`hooks/wg_text_score.py`](../hooks/wg_text_score.py) 與 `--auto-kind`；收尾接線要這段存在且 enabled 為 true。
  - `auto_targets` 是種類 → 來源路徑樣式：空清單不比路徑；沒列的種類不自動評，出廠不評文件。
  - 要跟規格檔「適用」欄一起改；手動指令照跑。

## 功能開關

[↑ 主文 §12.1](../TECH.md#121-功能開關不想要某個功能時逐鍵關)

除另註明外，值設 `false` 即關。

### 總開關與守門

| 鍵 | 關了少什麼 |
|----|-----------|
| `enabled` | 整個 Guardian（所有 hook 直接放行） |
| `coding_guard.enabled` | 出廠 false：寫碼守門全不跑（[§7](../TECH.md#7-守門與收尾) 開頭） |
| `chain_breaker.enabled` | 連鎖斷路器（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)）；一鍵關就寫 false |
| `chain_breaker.depth_alarm` | 連鎖深度到 `max_depth` 也警報（[§7.12](../TECH.md#712-連鎖斷路器hookswg_chainpy-判定libchain_storepy-帳與快照)） |
| `reconcile_gate.enabled` | 整個寫碼查核對帳閘（[§7.1](../TECH.md#71-stop-閘序)） |
| `aec.scan_report_gate` | 沒交收尾檢核就擋收尾（目前 false） |
| `atom_audit.enabled` | 卡片表態閘（目前 false） |
| `second_opinion.auto.enabled` | 大任務收尾自動要求第二意見 |
| `pick_one.enabled` | 交付時順手點出最該修的一件 |
| `overview_hub.enabled` / `overview_hub.min_map.enabled` / `overview_hub.equivalence.enabled` | 部位導讀卡與寫入閘 / 無表專案最小地圖 / 等值與熱路徑閘 |
| `guard.data_file_ask.enabled` / `guard.old_test_declare.enabled` / `guard.gate_bypass.enabled` / `guard.smell_gate.enabled` | 改資料檔、改舊測試、繞閘、commit 前病形的閘 |
| `guard.cross_realm_write.enabled` | 外部專案 session 寫 `~/.claude` 核心層的 deny 閘 |
| `guard.cross_realm_bash.enabled` | 同上，管經 Bash／PowerShell 改核心層 |
| `acceptance_spec.enabled` | 多檔改動要求驗收規格 |
| `deferral_gate.enabled` | Stop 閘攔「推給下個 session」的退縮歸屬 |
| `privacy.enabled` | git commit 前隱私檔硬閘（staged 比對 `deny_globs`） |
| `lang_guard.enabled` | 回應英文比例過高時的繁中提醒 |
| `version_guard.enabled` | 檔內版本操作脈絡殘留的 warn（`mode` warn / off） |
| `docdrift.enabled` | 改碼後提醒對應文件的漂移偵測 |
| `codex_companion.enabled` | AI 裁判（驗收審查／計畫審查／handoff 自檢） |
| `codex_companion.fallback.enabled` | 無 codex 時不退 `claude -p`，直接 heuristics-only |
| `text_score.enabled` | G15 文字規格自動評（見下方補充） |

- **`coding_guard.enabled`**：要開設 true 或 `WG_CODING_GUARD=1`（舊鍵 `v6`／舊變數 `WG_V6` 仍可用）。
- **`chain_breaker.depth_alarm`**：出廠 false，只有同一道閘第 2 次警報。
- **`guard.cross_realm_write.enabled`**：
  - 核心層指 hooks/lib/tools/skills/rules 與根層設定檔。
  - 「專案專屬內容不得落 global」的 realm 閘在 [`lib/realm_gate.py`](../lib/realm_gate.py)，無開關。
- **`guard.cross_realm_bash.enabled`**：config 沒寫、預設開。
- **`text_score.enabled`**：
  - 管收尾接線與 `--auto-kind`；收尾接線要這段存在且為 true。
  - 手動 [`tools/text-score.py`](../tools/text-score.py) 照跑。
- **`version_guard.enabled`**：`mode` 可設 warn／off。

### 檢索、注入與萃取

| 鍵 | 關了少什麼 |
|----|-----------|
| `vector_search.enabled` | 語意搜尋（保留 trigger + BM25） |
| `vector_search.global_layer` | 值 `"bm25"`（預設）或 `"vector"`；全域層改走向量 |
| `vector_search.auto_start_service` | SessionStart 不再自動起向量服務 |
| `injection.redundancy_gate.enabled` | 同題去冗 |
| `injection.related_gate.enabled` | related atom 擴散注入 |
| `taxonomy.gate_enabled` | atom 必須帶範疇才能寫入的閘 |
| `realm.llm_fallback.enabled` | 預設 false；開了用本地 LLM 判 unknown atom 的 realm |
| `response_capture.enabled` | 全部自動萃取（SessionEnd 全量、失敗萃取） |
| `response_capture.failure_extraction.enabled` | 只關失敗關鍵字萃取 |
| `response_capture.per_turn.enabled` / `response_capture.session_end_flush.enabled` | 預設 false，已停產（[§14.2](../TECH.md#142-已停產除役機制)） |
| `userExtraction.enabled` | 使用者決策萃取（L0→L1→L2） |
| `episodic.auto_generate` | session 結束自動生成 episodic 摘要 |

- **`response_capture.per_turn.enabled` / `session_end_flush.enabled`**：
  - per_turn 改 true 不會回滾。
  - session_end_flush 改 true 會恢復 SessionEnd 全量萃取。
- **`userExtraction.enabled`**：只想降負擔改 `userExtraction.tokenBudget`。

### 背景服務與其他

| 鍵 | 關了少什麼 |
|----|-----------|
| `deep_postmortem.enabled` | 高 effort 失敗時要求 Claude 深寫 post-mortem 的 Stop 閘 |
| `cross_session.enabled` | 跨 session 去重／衝突偵測 |
| `coordination.enabled` | 多 session 同檔改動預警 |
| `auto_handoff.enabled` | 壓縮前／token 逼近時自動產 handoff 交接稿 |
| `parallel_agents.enabled` / `research_fanout.enabled` | 多 agent 拆分／研究 fan-out 建議 |
| `aec.hud_autospawn` | 收尾檢核時自動開 HUD |
| `merge_driver.auto_install` / `merge_driver.auto_resolve` | 索引三檔合併驅動的自動安裝／自動解衝突 |
| `eol.auto_normalize_project` | 專案記憶樹自動轉 LF 與寫 VCS 屬性 |
| `heal.enabled` | Dashboard／腦內世界的記憶自癒 API |

- **`merge_driver.auto_install` / `auto_resolve`**：詳見 [`_AIDocs/MultiMachineMemorySync.md`](../_AIDocs/MultiMachineMemorySync.md)。
- **`heal.enabled`**：單顆自癒與 heal-all 回 503；`/heal-review` skill 不讀它。
