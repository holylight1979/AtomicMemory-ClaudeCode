# 分析 01：記憶注入、hooks 相容、context 管理、原生記憶層

> 面向：記憶怎麼送進對話（hooks）、官方行為改了會不會踩到我們、context 怎麼省、原生記憶要不要用。
> 依據：[`../../../ClaudeCodeInternals/Docs/_現況對帳-原子記憶系統用到的CC機制.md`](../../../ClaudeCodeInternals/Docs/_現況對帳-原子記憶系統用到的CC機制.md)、官方收割原文（各卡寫 slug）、程式碼，以及對本機逐字稿（`~/.claude/projects/*/*.jsonl` 最近 300～400 份）、`workflow/state-*.json`、`Logs/injection-turns.jsonl` 的實測。執行中的 CC 版本為 2.1.317（逐字稿 `version` 欄）。
> 連結相對本檔：`../../../ClaudeCodeInternals/Docs/` ＝ 官方文件收割夾（Docs），`../../../../` ＝ repo 根 `~/.claude`。
> 歸檔說明：本檔是 v6.1 動工前（2026-11-04）的計畫，文中「現況」指動工前；實際做了什麼、驗到哪見 [升級全紀錄](../升級全紀錄.md)。指向 v6.1 已刪檔的連結改成純文字並標「v6.1 已刪」。

## TLDR

最該先做的三件，都是「官方行為已經變了，我們還照舊做法，結果記憶有一段沒送到」：

1. **子代理吃到哪些卡、有沒有用，這筆帳目前 100% 落空**：子代理改成預設背景跑之後，PostToolUse 拿不到子代理的輸出；state 裡 30 筆子代理注入紀錄全標 `no_output`（P1）。
2. **hook 送的提示超過 10,000 字元，會被換成「檔案路徑＋前 2KB 預覽」**，模型多半不會去讀；近期逐字稿已發生 36 次，今天就有一次是 resume 開場（P2）。
3. **壓縮後把卡片內文送回去，原生的 `SessionStart(compact)` 已經可靠**（18 次壓縮有 17 次觸發），我們卻還在走「等下一批工具才送」的繞路，實測只送到 6 次（P3）。

另外一個純修剪：**關掉原生 auto memory**——它在系統提示詞裡叫模型「直接用 Write 寫進 projects/.../memory/」，跟我們「寫入一律走 atom_write」正面矛盾，每場還多約 500 tok（P4）。

提案共 20 張：A 4、B 9、C 7、D 0（D 級以文末「22 個未用事件判定表」列出，不另開卡）。

---

## 提案（依建議優先序）

### P1. 子代理改背景跑以後，「子代理吃到的卡有沒有用」這筆帳全數落空——改從 SubagentStop 收子代理的最後回覆
- 官方機制：子代理預設背景執行（v2.1.198；Desktop／VS Code 主對話一律背景，v2.1.302）。背景啟動時 PostToolUse(Agent) 的 `tool_response` 只有 `status: "async_launched"`、`agentId`、`prompt`、`outputFile`，**沒有 `content`**；SubagentStop 輸入帶 `agent_id`、`last_assistant_message`、`agent_transcript_path`（`last_assistant_message` 自 v2.1.47）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「PreToolUse 輸入 › Agent」「SubagentStop」、[sub-agents](../../../ClaudeCodeInternals/Docs/02-build/sub-agents.md)「哪些 subagents 在背景中執行」。
- 現況：[`post_tool_use.py`](../../../../hooks/handlers/post_tool_use.py) `_record_subagent_injection` 從 `tool_response.content` 擷取 `output_summary`；[`stop.py`](../../../../hooks/handlers/stop.py)（約 672–695 行）拿 `output_summary` 比對做注入歸因，空的就標 `skipped: "no_output"`。實測：近 300 份逐字稿 Agent 結果 **352 筆 async_launched、1 筆 completed**；26 個 state 檔裡 30 筆 `subagent_injections` **全是 async_launched、全標 no_output**。
- 落差／機會：子代理注入照送，但「送了有沒有被用」永遠記不到，Wilson 效用軌少一路證據；而且只是安靜地標 skipped，沒有訊號浮出來（違反可觀測性鐵律）。
- 做法（改寫法避衝突）：
  - SubagentStop（`stop.handle_subagent_stop`，已掛）依 `agent_id` 找到 `state.subagent_injections` 對應那筆，把 `last_assistant_message` 截 400 字填進 `output_summary`、`status` 改 completed。
  - Stop 結算時，仍是 async_launched 且還沒收到 SubagentStop 的紀錄標「等待中」而不是 no_output；結算改為「依 agent_id 收到結果才結」，不受「只結算本回合」限制（背景子代理常在下一回合才結束）。
  - 寫碼守門關閉時也要分派這段記帳（[`dispatcher.py`](../../../../hooks/dispatcher.py) 的 `PRE_V6_EVENTS` 目前不含 SubagentStop）。
- 代價與風險：每次子代理結束多一次 state 讀寫（已有 `STATE_RMW_LOCKED`）；SubagentStop 也會為內部 agent（提示建議、`/btw`）觸發，`agent_id` 對不到就略過。
- 驗法：起一個背景 Explore 子代理（任務文字含某張卡的 trigger）→ 結束後讀 state：該筆 `output_summary` 非空、`attributed` 為真且無 `skipped`。上線後掃所有 `state-*.json` 的 `skipped` 分布，`no_output` 應從 100% 降到接近 0。
- 分級：**C**

### P2. Hook 送的提示超過 10,000 字元會被換成「路徑＋2KB 預覽」——所有注入出口加字元上限
- 官方機制：`additionalContext`、`systemMessage`、純 stdout **每個字串**上限 10,000 字元；超過就存檔，只送檔案路徑與最多前 2,000 字預覽，「Claude Code 不要求 Claude 讀取檔案」，且沒有設定能提高（v2.1.89）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「JSON 輸出」「為 Claude 新增上下文」。
- 現況：注入預算全用 token 算（UPS 每回合 1200、總額 1000／2000／3000，[`wg_core.compute_token_budget`](../../../../hooks/wg_core.py)），hooks 裡沒有任何字元上限。實測近 400 份逐字稿有 **36 次**被換成預覽：
  - SessionStart resume 開場 4 次（9.8–11.1KB，最近一次就是今天、v2.1.317）
  - PostToolUse:Write 1 次 45KB（11-03）、PostToolUse:Bash 的 VerifyScope 3 次、PostToolUse:Read 的 OverviewHub 2 次
  - 已退役的 need_goal 26 次（歷史）
  - 沒被換掉的也貼著牆：UPS 單筆最大 9,335 字元、PostToolUse 9,061、SessionStart 9,475。
- 落差／機會：token 預算管不住字元數——英文、路徑多的卡，3000 tok 就可能超過 10,000 字元。超過時不是截掉尾巴，而是整段只剩 2KB 預覽，排在後面的提示等於沒送。
- 做法（改寫法避衝突）：在每個 hook 的單一出口加同一條規則——組好字串後量字元數，超過 9,000 就照既有優先序丟尾段，被丟的部分自己寫到 `workflow/` 下的檔，留一行「還有 N 項沒送，全文在 <路徑>」，再寫一筆 guard log。出口位置：[`user_prompt_submit.py`](../../../../hooks/handlers/user_prompt_submit.py) 341 行、[`session_start.py`](../../../../hooks/handlers/session_start.py) 1155／1219 行、[`post_tool_use.py`](../../../../hooks/handlers/post_tool_use.py) 343 行、[`post_tool_batch.py`](../../../../hooks/handlers/post_tool_batch.py) 293 行、[`pre_tool_use.py`](../../../../hooks/handlers/pre_tool_use.py) 2165 行。UPS 的 final-trim 在 token 預算之外再加字元預算。SessionStart resume 的清單段落改成「依項目去重」（已有卡：sessionstart 在 resume 與 compact 每次都再跑）。
  - 順手：官方建議注入文字寫成事實陳述，命令句可能觸發 prompt injection 防禦；grep 只有 7 處 `[Guardian:…]` 開頭就接「禁止／必須」，改出口時一起改即可。
- 代價與風險：少送一點內容，不增 token。官方是「每個字串分開量」，多支 hook 各自小於 10k 就安全，不必合起來算。
- 驗法：寫案例餵 12,000 字元的假提示給各出口，斷言輸出 ≤9,000 且尾行指標存在。上線後掃新逐字稿裡 `hook_additional_context` 含 `Output too large` 的筆數，應為 0。
- 分級：**C**

### P3. 壓縮後把卡片內文送回去，改由 SessionStart(compact) 直接送；PostToolBatch 退成補位
- 官方機制：壓縮後「符合 compact 來源的 SessionStart hook：Claude Code 執行它們並將其輸出新增到壓縮的上下文中」；hook 之前加的上下文「與其餘對話一起總結」。頁：[context-window](../../../ClaudeCodeInternals/Docs/01-getting-started/context-window.md)「壓縮後保留的內容」、[hooks-guide](../../../ClaudeCodeInternals/Docs/02-build/hooks-guide.md)「在壓縮後重新注入上下文」、[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md) SessionStart matcher `compact`。
- 現況：[`post_compact.py`](../../../../hooks/handlers/post_compact.py) 暫存 ≤800 tok、設 `pending_reinjection`；[`post_tool_batch.py`](../../../../hooks/handlers/post_tool_batch.py) 等下一批工具結束才送；[`session_start.py`](../../../../hooks/handlers/session_start.py) 的 compact 分支只送約 30 tok 的卡名。理由是 [`../../../ClaudeCodeInternals/cc-hook-system.md`](../../../ClaudeCodeInternals/cc-hook-system.md) 在 2026-06-01（v2.1.159）觀察到一次 SessionStart(compact) 沒觸發。
- 落差／機會：實測近 400 份逐字稿共 18 次壓縮，**17 次之後都有 `SessionStart:compact` 的 hook_success＋additionalContext**（唯一沒有的那場 `7b24f1dd` 整場一支 hook 都沒跑，是關了守門的工作軌）。PostToolBatch 的復原只在 6 次壓縮後出現。PostToolBatch 要等「下一批工具」，壓縮後模型如果先直接回文字，那段時間手上沒有卡。
- 做法（直接換用原生）：session_start.py 的 compact 分支直接讀 PreCompact 快照 `pre_compact_injected_atoms`，組緊湊內文（沿用 800 tok 預算）用 additionalContext 送出，並記「compact 已送」。PostCompact 只在沒有這個記號時才暫存，PostToolBatch 補位邏輯保留。
- 代價與風險：不增 token（同一份內容提早送）。順序上 SessionStart(compact) 早於 PostCompact，所以一定要讀 PreCompact 快照，不能讀 PostCompact 的暫存。
- 驗法：測試 session 先讓兩張卡注入 → `/compact` → 逐字稿 `compact_boundary` 之後第一個 `hook_additional_context` 來自 SessionStart，含兩張卡的名稱與內文；之後的 PostToolBatch 不重送。統計腳本：壓縮後 SessionStart 帶卡的比例 ≥95%。
- 分級：**C**（官方行為已穩定，我們的前提過時了）

### P4. 關掉原生 auto memory，退役橋接檔
- 官方機制：auto memory（v2.1.32）、`autoMemoryEnabled`（false 時「不會從自動記憶目錄讀取或寫入」）、`autoMemoryDirectory`（v2.1.74）、MEMORY.md 前 200 行或 25KB（v2.1.83）、`CLAUDE_CODE_DISABLE_AUTO_MEMORY`。頁：[memory](../../../ClaudeCodeInternals/Docs/01-getting-started/memory.md)「自動記憶」、[settings-reference](../../../ClaudeCodeInternals/Docs/05-configuration/settings-reference.md) `autoMemoryEnabled`。
- 現況：沒設 `autoMemoryEnabled`（預設開）。原生 MEMORY.md 只有 1 行，指向 `atom-index-bridge.md`（188,918 bytes，`tools/native-memory-bridge.py`（v6.1 已刪） 隨索引重產，今天 12:18 才重寫過）。Write／Edit 寫 `projects/*/memory/` 會被 MemoryPathBlock 擋（[`wg_core.py`](../../../../hooks/wg_core.py) 2125 行）。
- 落差／機會：
  - 實測主對話的系統提示詞（逐字稿 `api-request-shape`）有一段原生「# Memory」約 **2,088 字元**，內容是「直接用 Write 工具寫進 projects/.../memory/」。這跟我們「寫入一律走 atom_write」正面矛盾，而系統提示詞的位階比 CLAUDE.md 高；我們靠 MemoryPathBlock 事後擋（全部逐字稿出現 13 次、3 場）。
  - 橋接檔是「主題檔」，啟動時不載入，只在原生 recall 或模型自己 Read 時才碰到；atom 索引本來就靠 CLAUDE.md `@memory/MEMORY.md` 常駐，橋接沒有提供新東西。recall 時整份 188KB 被帶進來的風險排除不了（近 400 份逐字稿沒看到 recall 附件）。
  - [TECH §2.1](../../../../TECH.md) 的比較表寫原生「檢索：無」，已過時：changelog 寫到原生記憶目錄會被「recalled, indexed, or used by memory extraction」。
- 做法（直接換用原生開關）：settings.json 加 `"autoMemoryEnabled": false`；停掉 native-memory-bridge.py 的重產鏈，移除橋接檔與原生 MEMORY.md 那行，`verify_native_bridge.py` 改成驗「原生目錄是空的」；MemoryPathBlock 的 (a) 條保留當保險（成本近 0）；TECH §2.1 與 §4.7 改寫。
- 代價與風險：每場省約 500 tok 系統提示詞＋MEMORY.md 那行；失去「原生 recall 導向 atom」這條路（實測沒在用）。settings.json 進版控，多台機器一起生效。子代理本來就不載主對話的 auto memory，不受影響。
- 驗法：改完新開 session，讀最新逐字稿的 `api-request-shape.system`，斷言不含「# Memory」段與 `projects\…\memory` 路徑；`/memory` 顯示 Auto-memory off。
- 分級：**A**

### P5. webfetch-guard 換成原生 WebFetch 期限
- 官方機制：WebFetch 頁面下載期限預設 5 分鐘，可用 `CLAUDE_CODE_WEBFETCH_DEADLINE_MS` 調整（v2.1.268）。頁：[tools-reference](../../../ClaudeCodeInternals/Docs/06-reference/tools-reference.md)「WebFetch 工具行為」、[env-vars](../../../ClaudeCodeInternals/Docs/06-reference/env-vars.md)。
- 現況：`hooks/webfetch-guard.sh`（v6.1 已刪）（PreToolUse matcher `WebFetch`，timeout 20）每次 WebFetch 前先 curl HEAD（必要時再 GET），各最多 15 秒，沒回應就 deny；檔頭寫的目的是防「14 小時卡住」。deny 理由放在 `reason`，官方欄位是 `permissionDecisionReason`，所以 Claude 收不到理由（現況對帳 §1.3）。
- 落差／機會：原生已經有可調的硬期限。自製探針每次多一趟網路請求、最壞多等 30 秒，還多跑一個 bash 和兩次 python。
- 做法（直接換用原生）：settings.json 加 `"env": {"CLAUDE_CODE_WEBFETCH_DEADLINE_MS": "60000"}`（數值依習慣），移除 PreToolUse 的 WebFetch hook 與 webfetch-guard.sh。真的要留，至少把 `reason` 改成 `permissionDecisionReason`。
- 代價與風險：探針在伺服器完全不回時 15 秒就擋下，原生要等到期限才失敗——期限設 60 秒就差不多。
- 驗法：WebFetch 一個不會回應的位址（例如 `http://10.255.255.1`）→ 約 60 秒內以期限錯誤結束；正常網址的 WebFetch 比舊版少一次 curl 的時間。
- 分級：**A**

### P6. 打 `/continue` 這類指令時，記憶檢索只看得到「/continue」一行——用 UserPromptExpansion 補
- 官方機制：UPS 改成在 skill／自訂命令展開「之前」執行，收到的是使用者打的那一行原文（v2.1.299）；UserPromptExpansion 在命令展開時觸發，輸入有 `command_name`、`command_args`，可以回 `additionalContext`（TIMELINE 沒列首見版本；cc-hook-system 的 v2.1.159 事件清單已有）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「UserPromptSubmit 輸入」「UserPromptExpansion」。
- 現況：UPS 檢索吃使用者打的字（[`user_prompt_submit.py`](../../../../hooks/handlers/user_prompt_submit.py)），沒有針對斜線指令另外處理（grep 無）。`/continue` 也由 `tools/auto-continue/auto_continue.py`（v6.1 已刪） 以 `claude -p "/continue"` 起，走同一條。
- 落差／機會：續接回合真正的任務寫在 `memory/_staging/next-phase*.md`，檢索卻只看到「/continue」，trigger、BM25、vector 都對不到。續接是最需要「該想起的完整送到」的時刻，反而空手。（推論，待實測：開 atom-debug 看 `/continue` 那回合的注入摘要。）
- 做法（接上新能力）：settings.json 加 UserPromptExpansion，matcher 用精確清單（例：`continue|handoff|consciousness-stream`）。handler 依 `command_name` 取任務文字（continue → 最新 next-phase 檔前段；其他 → `command_args`），跑同一條 ups_search 管線、用 additionalContext 送出，並在 state 記「本回合已注入」，讓 UPS 不重複送。
- 代價與風險：這類回合多一次檢索（跟 UPS 同量、不到 1 秒）；預算共用每回合 1200 tok 的同一個桶。
- 驗法：準備一份 next-phase 檔，內含某張卡的 trigger → 打 `/continue` → 逐字稿該回合出現 UserPromptExpansion 的 `hook_additional_context`、含那張卡；同回合 UPS 沒再送同一張。
- 分級：**B**

### P7. 子代理記憶：PreToolUse 繼續依任務挑卡，SubagentStart 補「沒經過 Agent 工具的子代理」
- 官方機制：SubagentStart 的 `additionalContext` 加在子代理對話開頭、第一個提示之前；同一個子代理再跑時，只在副本不在時才補送（自動壓縮丟掉後會再送），不破壞提示快取。SubagentStart 輸入**只有** `agent_id`、`agent_type`，沒有委派提示詞。Explore、Plan 不載 CLAUDE.md。自動模式下 hook 改了 Agent 的輸入，會先被拒一次再重發（Agent 不在免審清單）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「SubagentStart」「自動模式中的 PreToolUse updatedInput」、[sub-agents](../../../ClaudeCodeInternals/Docs/02-build/sub-agents.md)「啟動時載入的內容」。
- 現況：[`pre_tool_use.py`](../../../../hooks/handlers/pre_tool_use.py) 1890–1935 行：Agent／Task 時用 `updatedInput` 把 `[WG:SubagentMemory]` 加在 prompt 前面，預算 700 tok。註解寫「唯一 parent→child 通道是工具 prompt 字串」，已過時。
- 落差／機會：
  - Workflow 工具、skill `context: fork`、agent teams 隊友、`/subtask` 起的子代理不經過 Agent 工具，PreToolUse 抓不到（近 300 份逐字稿：Workflow 6 次、Agent 634 次）。
  - Explore＋Plan 佔 Agent 的 73／634，它們連 CLAUDE.md 的 atom 索引都沒有，只靠這段注入。
  - 自動模式目前沒用（逐字稿 permissionMode 只有 bypass／default／plan），是潛在風險。
- 做法（接上新能力）：settings.json 加 SubagentStart（command 型，走 guardian dispatcher 的新 handler）。PreToolUse 注入時寫一個 30 秒內有效的記號（agent_type＋時間）；SubagentStart 看到記號就什麼都不送，沒有記號的（Workflow 等）就送父 session 目前 `injected_atoms` 的緊湊版（≤700 tok）——這類子代理做的就是父對話手上的事。PreToolUse 的挑卡不動。
- 代價與風險：每次子代理啟動多一個 hook 行程（約 0.1–0.3 秒，花在子代理端）；平行起好幾個同類型子代理時，記號可能誤判成「已注入」——只會少補送，不會重複送。
- 驗法：用 Workflow 起一個 agent，讀它的 `subagents/agent-*.jsonl` 開頭有 `hook_additional_context`、含 `[WG:SubagentMemory]`；用 Agent 工具起 Explore，確認沒有兩份。
- 分級：**B**

### P8. 壓縮摘要直接拿來填交接單
- 官方機制：PostCompact 輸入帶 `compact_summary`，就是壓縮產生的對話摘要（v2.1.76）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「PostCompact」。
- 現況：[`pre_compact.py`](../../../../hooks/handlers/pre_compact.py) 自己產 episodic 與交接單草稿（`next-phase-auto.md`），主觀區塊留 TODO，等 PostToolBatch（Layer 3）叫模型補；[`post_compact.py`](../../../../hooks/handlers/post_compact.py) 沒讀 `compact_summary`（只有 docstring 提到）。
- 落差／機會：壓縮當下已經有一份模型寫好的摘要，我們卻在壓縮後再叫模型補交接單——多花一輪 token；模型如果一直沒呼叫工具，草稿就一直沒人補。
- 做法（接上新能力）：post_compact.py 把 `compact_summary` 寫進草稿的「進度／脈絡」區塊（標「壓縮摘要原文」），Layer 3 的提示只留「確認下一步」那一格；episodic 也可改用 `compact_summary` 當素材。
- 代價與風險：寫檔不進 context，沒有 token 成本。摘要是模型寫的，屬推論層，草稿要標來源。
- 驗法：`/compact` 後讀 `next-phase-auto.md`，主觀區塊已經有內容；PostToolBatch 的補完提示變短或不出現。
- 分級：**B**

### P9. 重開舊 session 時，告訴使用者「這次重開要重寫多少快取」
- 官方機制：SessionStart 在 resume／fork 時多給 `seconds_since_last_response`、`context_tokens`、`prompt_cache_likely_expired`、`estimated_cache_write_usd`（v2.1.251）；訂閱方案的主對話快取預設保留 1 小時。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「SessionStart 輸入」、[prompt-caching](../../../ClaudeCodeInternals/Docs/01-getting-started/prompt-caching.md)「快取生命週期」。
- 現況：[`session_start.py`](../../../../hooks/handlers/session_start.py) 的 resume 分支複用 state、送 `[Guardian:Resume]` 指向 next-phase 檔，不看快取狀態。[`rules/core.md`](../../../../rules/core.md)「Context 壓縮即將發生 → 提醒開新 session」目前只有 Stop 的 0.85 用量預警在做。
- 落差／機會：閒置一小時以上再 resume 一場 60 萬 token 的對話，第一句話就要整包重寫快取；原生已經把成本算好交給 hook 了。
- 做法（接上新能力）：resume 分支讀這四個欄位。`prompt_cache_likely_expired` 為真、而且 `context_tokens` 超過門檻（例：30 萬）時，開場送一行事實陳述：「這場閒置 X 小時，重開會重寫約 N 萬 token 快取；交接單在 <路徑>，開新 session 接續比較省」，同時用 `systemMessage` 給使用者看。用 token 表示即可，不必換算美金。
- 代價與風險：一行（不到 80 tok），只在條件成立時送。
- 驗法：resume 一場閒置超過 1 小時的大 session → 開場出現這行；閒置 5 分鐘內 resume 不出現。
- 分級：**B**

### P10. 「SessionEnd 只有 1.5 秒」這個前提過時了：文件改正，SessionEnd 加計時
- 官方機制：SessionEnd 預設 1.5 秒，但會自動提高到設定檔裡最高的單支 hook `timeout`，最多 60 秒；也可以用 `CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS`（v2.1.268 起這個變數也套到沒設 timeout 的 hook）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「通用欄位」「SessionEnd」、[env-vars](../../../ClaudeCodeInternals/Docs/06-reference/env-vars.md)。
- 現況：settings.json 的 SessionEnd：guardian timeout 30、codex 5 → 實際預算 30 秒。[TECH §2.1](../../../../TECH.md) 表格和 §6.3 仍寫「共 1.5 秒硬牆、timeout 30 無效，所以萃取改走 detached」。[`wg_hook_timing.py`](../../../../hooks/wg_hook_timing.py) 只計 SessionStart／UPS／PreToolUse／PostToolUse／Stop。
- 落差／機會：現在 handler 卡住時，使用者關 session 最多要等 30 秒，卻沒有計時帳看得到；文件的理由也是錯的。detached 該留，理由應該改成「LLM 萃取可能超過 60 秒，也不該讓使用者關窗時等」。
- 做法（改寫法避衝突）：改寫 TECH §2.1、§6.3、[`../../../ClaudeCodeInternals/cc-native-memory-hooks-mcp.md`](../../../ClaudeCodeInternals/cc-native-memory-hooks-mcp.md) §8；`hook_timing.fallback_limit_s` 加 SessionEnd，讓它也出計時帳；timeout 依實測中位數 ×3 調小（例：10 秒）。
- 代價與風險：沒有 token 成本，要同步文件。
- 驗法：`tools/hook-timing.py` 出現 SessionEnd 各段中位數；讓 session_end 故意 sleep 40 秒 → 30 秒被取消，guard log 有 overrun 紀錄。
- 分級：**C**

### P11. 家目錄的 AGENTS.md 被當成 `~/.claude` 的專案指令載入
- 官方機制：AGENTS.md 支援（v2.1.277）——工作目錄或上層沒有 `CLAUDE.md`／`.claude/CLAUDE.md`／`CLAUDE.local.md` 時就讀 AGENTS.md，而 `~/.claude/CLAUDE.md` **不算**；可以在 `/config`「專案指示」或 `pluginConfigs.cc-plugin-agents-md@builtin.options.instructionFiles` 改；`claudeMdExcludes` 用絕對路徑 glob 排除。頁：[memory](../../../ClaudeCodeInternals/Docs/01-getting-started/memory.md)「AGENTS.md」「排除特定 CLAUDE.md 檔案」。
- 現況：`C:/Users/holylight/AGENTS.md`（485 bytes，給 Codex 用、不在 repo）在 cwd＝`~/.claude` 或 `~/.claude-wt/*` 時被載入（本 session 的 context 看得到）。它的 `@IDENTITY.md` 等匯入是相對家目錄解析，檔案不存在；內文還寫「專業規則已模組化至 `.Codex/rules/`，Codex 自動載入」。
- 落差／機會：根層 session 每場多一段無效、又跟我們規則矛盾的指令（量小，約 150 tok）；子代理也會跟著載（AGENTS.md 當專案指令載入時，子代理同樣會載）。
- 做法（改寫法避衝突）：首選把這個檔移到 Codex 的全域位置 `~/.codex/AGENTS.md`（推論：Codex 從 repo 根往下讀 AGENTS.md，家目錄這份對 `~/.claude` repo 本來就讀不到；Codex 端怎麼用待使用者確認）。不想動 Codex 的話，在 settings.json 加 `"claudeMdExcludes": ["**/Users/*/AGENTS.md"]`——官方只說 claudeMdExcludes 適用於 AGENTS.md 的處理，能不能排除 AGENTS.md 本身待實測。
- 代價與風險：幾乎為 0。不要用 `instructionFiles: "claude-md"` 全關，那會讓其他只有 AGENTS.md 的專案失去指令。
- 驗法：在 cwd＝`~/.claude` 新開 session，開場不再出現 `AGENTS.md loaded: C:\Users\holylight\AGENTS.md`，逐字稿的 instructions 附件也不含這個路徑。
- 分級：**C**

### P12. 收尾閘：提醒類改用 Stop 的 additionalContext，擋次總和壓在原生上限以下
- 官方機制：Stop 回 `hookSpecificOutput.additionalContext` 是「非錯誤回饋」：對話繼續，逐字稿標 `Stop hook feedback`，不顯示 hook 錯誤；它和 `decision: "block"` 共用 `stop_hook_active` 與連續 8 次上限（`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`；v2.1.163）。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「Stop 決策控制」、[env-vars](../../../ClaudeCodeInternals/Docs/06-reference/env-vars.md)。
- 現況：[`stop.py`](../../../../hooks/handlers/stop.py) 各閘都用 `decision: block`＋`reason`（118 行），預算分散：`stop_gate_max_blocks` 2、reconcile `max_blocks_per_turn` 2，harvest、DPM、提問閘各自計次；[`lang_guard.py`](../../../../hooks/lang_guard.py) 已改用 additionalContext。實測近 300 份逐字稿：每個使用者回合的 Stop 續跑多半 1 次，最高 7 次（`f0055a0d`）。
- 落差／機會：(a) 只是提醒的閘也用 hook error 呈現，看起來像「出錯」；(b) 各閘預算加起來可能撞到原生 8 次上限，撞到時 CC 直接結束回合，我們的帳卻記成「擋了」。
- 做法（改寫法避衝突）：不要求修正的提醒類閘（SyncReminder、ReloadAdvice、KnowledgeHarvest 提示等）改送 additionalContext；stop.py 讀 `stop_hook_active` 加上自家「本回合已續跑次數」，總數到 7 就只記帳不再擋，並寫 guard log。
- 代價與風險：不增 token，只改呈現方式。
- 驗法：構造一個回合同時觸發 4 個閘 → 逐字稿顯示 `Stop hook feedback` 而不是 hook error；壓測連擋 9 次 → 第 8 次之前自家就放行，且有 log。
- 分級：**A**（續跑上限原生已經有，我們在重複管）

### P13. 掛 InstructionsLoaded，只記帳，確認規則與索引真的載入（含壓縮後）
- 官方機制：InstructionsLoaded（v2.1.69）在 CLAUDE.md、`.claude/rules/*.md` 載入時觸發，`load_reason` 分 `session_start`、`nested_traversal`、`path_glob_match`、`include`、`compact`；非同步、只供觀測。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「InstructionsLoaded」、[memory](../../../ClaudeCodeInternals/Docs/01-getting-started/memory.md)。
- 現況：系統依賴「壓縮後原生會重載 CLAUDE.md」和 rules 的 `paths:` 按需載入，但沒有掛 hook 驗證（現況對帳 §1.2）；TECH §11.1「碰到程式檔再加約 3,560 tok」是估算，沒有實際載入次數。
- 落差／機會：載入了沒、壓縮後有沒有重載、code-thinking／coding-style 一天載幾次，現在都是推定。
- 做法（接上新能力）：settings.json 加 InstructionsLoaded（command 型，輕量腳本只 append 一行 JSONL 到 `Logs/instructions-loaded.jsonl`：file_path、memory_type、load_reason、session_id、agent_type）；`/memory health` 或週健檢讀它出兩個數——壓縮後的 `compact` 重載率、path_glob_match 規則的載入次數。
- 代價與風險：每場開頭約 4–6 次極輕量行程，非同步不擋。直接讀取的 AGENTS.md 不會觸發這個事件。
- 驗法：開 session → log 出現 CLAUDE.md 與 3 個 include（IDENTITY、USER、MEMORY）、rules/core.md；讀一個 .py → 出現 code-thinking、coding-style 的 path_glob_match；`/compact` → 出現 compact。
- 分級：**B**

### P14. Codex 背景審查改用 asyncRewake：有問題立刻叫醒 Claude
- 官方機制：command hook 加 `async: true` 就在背景跑、不擋，結果下一回合送；`asyncRewake: true` 在退出碼 2 時即使閒置也立刻喚醒 Claude，stderr 以系統提醒交給 Claude；timeout 照算；`-p` 結束時會被終止，要活過 session 的工作仍要用完全分離的程序。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「在背景執行 hooks」（TIMELINE 沒列 asyncRewake 首見版本）。
- 現況：[`codex_companion.py`](../../../../hooks/codex_companion.py) 在 PostToolUse 到檢查點時 Popen 一個 detached audit（200 行），結果寫成 `companion-assessment-*.json`，要等下一則 UPS 才帶回。
- 落差／機會：審查發現問題，要等使用者下一則訊息才送到；做法是自製 spawn＋檔案信箱＋UPS 汲取三段。
- 做法（直接換用原生）：codex_companion 的 PostToolUse 拆成兩支——「是否到檢查點」的快速同步判斷保留；審查本身改成同 matcher 的另一組 `async`＋`asyncRewake: true` command hook，有發現就 exit 2＋stderr 寫結論，沒發現就 exit 0。SessionEnd 萃取、vcs-sync、vector 常駐服務照舊 detached（它們必須活過 session）。
- 代價與風險：每次符合 matcher 都起一個背景行程（不擋，但 Windows 上 Python 啟動約 0.1–0.3 秒 CPU）；async 行程會隨 CC 結束被收掉，進行中的那份審查會遺失（現在 detached 不會）；asyncRewake 會打斷 Claude 手上的事，頻率要控制。
- 驗法：故意寫一個 Codex 會挑的錯 → Claude 閒置時收到系統提醒（使用者不必打字）；`Ctrl+O` 看得到 async hook 完成通知。
- 分級：**B**

### P15. 自家 MCP 加 server instructions，熱門工具免延遲載入
- 官方機制：工具搜尋預設開啟，MCP 工具開場只載名稱和 server instructions；server instructions 與預先載入的工具描述上限 4,096 字元（v2.1.296）；單支工具可在 `_meta["anthropic/alwaysLoad"]` 標成永遠載入，整個 server 則用 `alwaysLoad`（v2.1.121）。頁：[mcp](../../../ClaudeCodeInternals/Docs/02-build/mcp.md)「使用 MCP 工具搜尋進行擴展」。
- 現況：[`lib/mcp.js`](../../../../tools/workflow-guardian-mcp/lib/mcp.js) 的 initialize 只回 `capabilities.tools`，沒有 instructions；9 支工具全部被延遲（本 session 的 deferred 清單看得到 atom_write、memory_search 等），要先 ToolSearch 才能呼叫。rules/core.md 又要求「寫入一律走 atom_write」。
- 落差／機會：每次寫卡或查卡都多一趟 ToolSearch；模型不知道「什麼時候該搜這些工具」，只能靠規則檔提醒。
- 做法（接上新能力）：initialize 回 `instructions`（1,000 字元內，用事實陳述說明這個 server 管記憶卡的寫入與檢索、哪種情況用哪支）；atom_write、memory_search 兩支加 `_meta: {"anthropic/alwaysLoad": true}`，其餘 7 支維持延遲。
- 代價與風險：兩支工具的 schema 常駐系統提示詞（估 1–2k tok，需實測）；這屬於系統提示詞層，改動會讓整段快取失效，所以一次定案、不要常改。
- 驗法：新 session 的 deferred 清單不再有這兩支；逐字稿 `api-request-shape.tools` 有 atom_write；`/context` 比較 MCP 佔用前後差。
- 分級：**B**

### P16. `/cd` 換目錄後，專案層記憶仍指著舊專案
- 官方機制：`/cd` 移動 session 的主要工作目錄，載入新目錄的 CLAUDE.md、專案設定與 hooks（v2.1.169；v2.1.246 起立即套用）；hook 的 `${CLAUDE_PROJECT_DIR}` 維持啟動時的根，輸入的 `cwd` 會跟著變；CwdChanged（v2.1.83）在 cwd 變更時觸發，但沒有 additionalContext，只有 `watchPaths`／`systemMessage`。頁：[permissions](../../../ClaudeCodeInternals/Docs/05-configuration/permissions.md)「將工作階段移動到另一個目錄」、[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「CwdChanged」「以路徑參照指令碼」。
- 現況：[`ups_search.py`](../../../../hooks/handlers/ups_search.py) 294 行用 `state.session.cwd`（SessionStart 時記下的）決定候選池與專案層；沒掛 CwdChanged。
- 落差／機會：`/cd` 之後注入的仍是舊專案的 shared／personal 卡，新專案的卡進不來。（推論：`/cd` 會不會觸發 CwdChanged 或 SessionStart 未查到，待實測。）
- 做法（改寫法避衝突）：UPS 每回合比對「輸入 cwd 推出的專案根」和「state.session 的專案根」，不同就重建候選池並更新 state。只認專案根變了，Bash 裡 cd 到子目錄不算。如果實測 `/cd` 會觸發 CwdChanged，就改由 CwdChanged 更新 state，UPS 不必每回合比。
- 代價與風險：每回合一次路徑比較（微秒級）；只在換專案時才重建候選池。
- 驗法：在 A 專案開 session → `/cd` 到 B 專案 → 說一句會命中 B 專案某張 shared 卡 trigger 的話 → 注入該卡，而且不再注入 A 專案的卡。
- 分級：**C**

### P17. skill 的自訂 `triggers` 欄改成原生 `when_to_use`
- 官方機制：skill frontmatter 的 `when_to_use` 寫觸發短語或範例請求，附加在 skill 列表的 description 後面，兩者合計 1,536 字元截斷。頁：[skills](../../../ClaudeCodeInternals/Docs/02-build/skills.md)「Frontmatter 參考」。
- 現況：12 個 skill 有自訂的 `triggers`、`pattern`，hook 沒讀（現況對帳 §3.1），CC 也不讀，等於只給人看。
- 落差／機會：觸發詞寫了，卻不在模型看得到的 skill 列表裡。
- 做法（直接換用原生）：`triggers:` 改名為 `when_to_use:`（內容改成「使用者說…時」一句），description＋when_to_use 控制在 1,536 字元內、關鍵詞放前面；`pattern` 保留（skill-creator 的慣例，不進 context）；skill-creator 的範本一起改。
- 代價與風險：skill 列表每個多幾十字（常駐 context）；`disable-model-invocation: true` 的不進列表，可以不加。
- 驗法：`/skill-doctor` 或 `/context` 看 skill 列表；用 when_to_use 的觸發句測一次會不會自動叫起。
- 分級：**A**

### P18. 定期跑 `/doctor prompt-audit`，補「指令寫法過時、互相矛盾」這一塊
- 官方機制：`/doctor prompt-audit`（v2.1.283）審查 CLAUDE.md、CLAUDE.local.md、AGENTS.md，以及 `~/.claude` 下的 rules、skills、commands、agents、輸出風格；找舊模型寫法、指向不存在的檔案或命令、互相矛盾的內容，只出報告不改檔。頁：[memory](../../../ClaudeCodeInternals/Docs/01-getting-started/memory.md)「審計您的指令檔案」。
- 現況：[`tools/config-consistency.py`](../../../../tools/config-consistency.py) 只量設定鍵一致性；memory health 管卡片；沒有工具審查「規則與 skill 的寫法」。
- 落差／機會：31 個 skill、rules、IDENTITY／USER 的文字，沒人系統性查過過期路徑與矛盾（P11 那種就是例子）。
- 做法（接上新能力）：週健檢清單加一項「手動跑 `/doctor prompt-audit`」（互動命令，能不能用 `claude -p` 跑待確認）；結果寫到 `memory/_staging/prompt-audit-<日期>.md`，由人挑要改的。config-consistency 保留，兩者不重疊。
- 代價與風險：一次審查的模型 token（量不確定，需實測）；需要內建的 `/claude-api` skill 沒被關。
- 驗法：跑一次，報告至少有過期路徑、互相矛盾兩類，人工抽 3 條核實。
- 分級：**B**

### P19. 回合因 API 錯誤結束時要留帳（StopFailure）
- 官方機制：StopFailure（v2.1.78）在回合因 API 錯誤結束時「取代 Stop」執行，輸入有 `error`（rate_limit、overloaded…）與 `error_details`；除了 `terminalSequence`，輸出都會被忽略。頁：[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「StopFailure」。
- 現況：沒掛。這種回合裡 Stop 的整串閘（紅測、對帳、收割、同步…）完全不跑，也沒有任何紀錄。
- 落差／機會：撞到 rate_limit 或 overloaded 時，那回合的收尾債務靜靜留著，要等下一回合的 Stop 才可能補到；usage-watch 也不知道撞了限額。
- 做法（接上新能力）：掛 StopFailure（command，matcher 留空），只做兩件事：在 state 記「上回合因 <error> 中斷」，讓下一回合 UPS 送一行事實提示；rate_limit 時寫一筆事件給 usage-watch 讀。
- 代價與風險：只在出錯時跑；多一行提示。
- 驗法：單元測試餵一份 StopFailure JSON，斷言 state 與事件檔有寫入（真實的 overloaded 不好製造）。
- 分級：**B**

### P20. 守門類 PreToolUse hooks 對官方權限優先序的相容檢查（大多不用改）
- 官方機制：PreToolUse 回 allow 蓋不過 deny／ask 規則；plan mode 中 hook 的 allow 對非唯讀呼叫無效；多支 hook 的決策優先序是 deny > defer > ask > allow；`defer` 只在 `-p` 生效；Windows 沒有 Git Bash 時，shell 形式的 PreToolUse 失敗可能改成擋下工具；`disableAllHooks`、`--safe-mode`、`--bare`（`CLAUDE_CODE_SIMPLE`）會把 hooks、CLAUDE.md、auto memory 一起關掉。頁：[permissions](../../../ClaudeCodeInternals/Docs/05-configuration/permissions.md)「規則、hook 與 mod 之間的優先順序」「plan mode 中的 hook 核准」、[hooks](../../../ClaudeCodeInternals/Docs/06-reference/hooks.md)「PreToolUse 決策控制」「將工具呼叫延遲到稍後」「Windows 上沒有 Git Bash 時失敗的 hook」、[settings-reference](../../../ClaudeCodeInternals/Docs/05-configuration/settings-reference.md) `disableAllHooks`、[cli-reference](../../../ClaudeCodeInternals/Docs/06-reference/cli-reference.md)。
- 現況：PAN（pre_tool_use）、MemoryPathBlock、plan_bash_guard、webfetch-guard 都只回 deny、從不回 allow（現況對帳 §1.2）；所有 hook 都是 shell 形式（`"$LOCALAPPDATA/..."` 要靠 bash 展開）。背景軌用 `claude --bg`，不是 `-p`。
- 落差／機會：allow 優先序與 plan mode 限制對我們沒影響；`defer` 對背景軌不適用，提問閘照留。唯一風險：哪台機器沒裝 Git Bash，shell 形式指令就會在 PowerShell 跑、`$LOCALAPPDATA` 不會展開 → hook 啟動失敗 → PreToolUse 可能每個工具都被擋。
- 做法（改寫法避衝突）：[`tools/install.py`](../../../../tools/install.py) `--verify` 加「找得到 Git Bash」這項（或提示設 `CLAUDE_CODE_GIT_BASH_PATH`）；其他不動。webfetch 的欄位問題見 P5。
- 代價與風險：0。
- 驗法：在沒有 Git Bash 的環境（或改 PATH 模擬）跑 `install.py --verify`，印出明確 FAIL。
- 分級：**C**

---

## 對任務提問的直接回答

| 問題 | 結論 | 卡 |
|---|---|---|
| 22 個未用事件哪些有用 | SubagentStart、UserPromptExpansion、InstructionsLoaded、StopFailure 有用；CwdChanged 先實測；其餘見下表 | P7、P6、P13、P19、P16 |
| async／http／mcp_tool／prompt／agent、`if`、onFailure、defer、updatedToolOutput 能取代哪些自製 | `asyncRewake` 可取代 Codex 背景審查的 spawn＋檔案信箱；SessionEnd 的 detached 不能換（async 會隨 session 結束被殺）；agent／prompt hook 不取代裁判與 Codex（見「不建議」）；defer 只限 `-p`、不適用背景軌；`if`、onFailure、updatedToolOutput 目前沒有好的對接點 | P14、不建議 |
| 10,000 字元上限 | **已經踩到**：近期 36 次被換成預覽，含今天 | P2 |
| UPS 改在 skill 展開前跑 | 沒有東西壞掉（我們的 skill 沒用 `` !` `` 注入，也沒有 frontmatter hooks）；但斜線指令回合的檢索只看得到指令名 | P6 |
| SessionEnd 可拉到 60 秒 | 我們設 30 已經生效，TECH 的「1.5 秒牆」前提過時；detached 照留，理由要改寫 | P10 |
| matcher 含連字號改精確比對（v2.1.195） | 相容：PreToolUse／PostToolUse 的 matcher 只有字母、`_`、`-`、`\|`，走精確清單；`mcp__workflow-guardian__atom_write` 等全名精確命中。以前因為含 `-` 走正規式，`Task` 會順帶命中 TaskStop／TaskOutput、`Agent` 會命中 ListAgents，現在不會了，handler 本來就再判一次 tool_name，不受影響 | — |
| 原生 auto memory、MemoryPathBlock＋橋接要不要改 | 要：關原生、退橋接、MemoryPathBlock 留作保險 | P4 |
| AGENTS.md、rules `paths:`、@import 4 層、壓縮後重注 | AGENTS.md 有踩到（P11）；@import 只有 1 層，沒問題；有 `paths:` 的 code-thinking／coding-style 壓縮後會被摘要掉、下次碰程式檔才重載，符合設計；`--bare`／`--safe-mode`／`CLAUDE_CODE_SIMPLE` 會全關，judge 與 auto_continue 用一般 `-p`，不受影響 | P11、P13、P20 |
| 注入預算三態設計的新對接點 | 四個：字元硬牆（P2）、SessionStart(compact) 直送（P3）、SubagentStart 管道（P7）、UserPromptExpansion 管道（P6）；另外 resume 時的快取成本欄位（P9） | — |
| `/doctor prompt-audit`、disableAllHooks、allowManagedHooksOnly、權限優先序 | prompt-audit 可補缺口（P18）；後三者對我們只回 deny 的守門沒有影響（P20）；allowManagedHooksOnly 屬受管設定，本機沒有 managed 層，不適用 | P18、P20 |

## 22 個未用事件判定表

| 事件 | 判定 | 一句理由 |
|---|---|---|
| SubagentStart | B（P7） | 補不經 Agent 工具的子代理 |
| UserPromptExpansion | B（P6） | 斜線指令回合的檢索 |
| InstructionsLoaded | B（P13） | 載入觀測 |
| StopFailure | B（P19） | API 錯誤中斷時留帳 |
| CwdChanged | 待實測（P16） | 沒有 additionalContext；只拿來更新 state |
| Setup | D | 只在 `--init-only`／`-p --init`／`--maintenance` 跑；我們用 install.py＋schtasks，換入口沒有收益 |
| MessageDisplay | D | 只改畫面顯示，不進 context |
| PermissionRequest | D | `defaultMode: bypassPermissions`，幾乎不會觸發 |
| PermissionDenied | D | 只在 auto mode 觸發，逐字稿沒用過 auto mode |
| Notification | D（本面向） | `agent_needs_input` 可給總控台用，屬多 session 面向 |
| TaskCreated／TaskCompleted／TeammateIdle | D | 屬 agent teams 與任務工具，本面向用不到 |
| ConfigChange | D | settings.json 被 git pull 改動時可記帳，但 systemMessage 被丟棄、價值低 |
| DirectoryAdded | D | `/add-dir` 加另一個 repo 時可把它的專案層記憶併進候選池；使用頻率低 |
| FileChanged | D | 索引變動已靠 mtime 簽章偵測（[`wg_atoms.py`](../../../../hooks/wg_atoms.py) 455／500 行） |
| WorktreeCreate／WorktreeRemove | D（本面向） | 屬 worktree 面向 |
| PreModelSwitch／PostModelSwitch | D | 可依模型注入指引；目前 effort 已用 `modelSettings` 分模型設，沒有缺口 |
| Elicitation／ElicitationResult | D | 自家 MCP 沒用 elicitation |

## 不建議做的

1. **用 agent／prompt 型 hook 取代 Codex 第二意見與驗收裁判**：它們會同步擋住流程（prompt 預設 30 秒、agent 60 秒），只能用 Claude 模型，失去跨廠牌觀點；每 session 同時最多 24 個（v2.1.312）。現在的「不等結果、背景跑」比較合適。
2. **重新打開 idleCompaction 來省快取**：使用者已經定案關掉（commit 818ed88a：避免離開一下回來細節就被摘要掉）；P3 做完也不改變這個判斷。
3. **用 PreCompact 擋自動壓縮來保住注入**：擋掉主動壓縮只是延後；真的撞到上限時，擋壓縮會讓請求直接失敗（hooks.md PreCompact）。
4. **把原生 auto memory 改成「收件匣」**（`autoMemoryDirectory` 指到 `_staging` 再收割）：等於讓系統提示詞繼續叫模型繞過 atom_write 的驗證和去重，再多寫一套收割程式；直接關掉比較乾淨（P4）。
5. **用 PostToolUse `updatedToolOutput` 壓縮大型工具輸出來省 context**：改的只是 Claude 看到的內容，錯誤細節被刪會讓模型誤判；要省 context，官方建議把大檔讀取交給子代理。
