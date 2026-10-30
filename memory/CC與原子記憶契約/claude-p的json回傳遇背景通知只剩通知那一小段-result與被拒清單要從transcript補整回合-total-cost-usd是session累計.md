# claude-p的json回傳遇背景通知只剩通知那一小段-result與被拒清單要從transcript補整回合-total_cost_usd是session累計

- Scope: global
- Author: holylight
- Source: session fa073ade 2026-10-21（實測第三跑 transcript 與回合 JSON 對照）
- Confidence: [臨]
- Trigger: claude -p, output-format json, task-notification, 背景通知, permission_denials, total_cost_usd, 串跑腳本, result 收錯, --resume 成本
- Created-at: 2026-10-21
- Related: claude-p無頭跑會被hook判成無法互動-問人類流程驗不到-預設claude-code-entrypointclaude-vscode可保留但-p沒有askuserquestion

## 知識

- [臨] `claude -p --output-format json` 回合收尾後若有背景工作完成（task-notification），同一行程會再起一小段回應通知；stdout 那一個 JSON 只描述那一小段：`origin.kind=task-notification`、`result` 是通知的短訊息，`num_turns`、`permission_denials`、`duration_ms` 也只算那段（實例：主體被 PreToolUse 擋 16 次，回傳 num_turns=1、permission_denials=0）。拿它判「這回合 AI 說了什麼、哪個工具被擋」會整段收錯。
- [臨] 整回合要讀 transcript（`~/.claude/projects/<路徑 slug>/<session>.jsonl`）：從內文等於送出那句的 user 紀錄起算，到下一則真的使用者話為止。isMeta 的 user 紀錄是 Stop hook 擋訊息，屬同一回合、之後的回覆照算；`origin.kind=task-notification`（或內文以 `<task-notification>` 開頭）之後是通知觸發段。被擋的工具呼叫，tool_result 內文以「PreToolUse:<工具> hook error:」開頭、後面接擋訊息全文（claude 回傳的 permission_denials 不帶擋訊息，要分辨是哪個閘擋的只能看這裡）。
- [臨] `total_cost_usd` 是整個 session 的累計，`--resume` 接續會帶上前面回合（實例七回合 2.99→14.02 單調遞增）：合計取同一 session 最後一筆，逐回合相加會重複算。
- [臨] 同一個回傳 JSON 裡欄位口徑不一：`usage` 是這一次 claude -p 呼叫的量（--resume 時下一回合的 cache_read 會比上一回合小），`modelUsage` 跟 `total_cost_usd` 才是整個 session 的累計。逐回合 token 用 usage（輸入＝input＋cache_creation＋cache_read），整段取最後一回合的 modelUsage 或把各回合 usage 加總。實測 2026-10-22：一段兩回合 usage.cache_read 2.36M→0.22M，modelUsage 輸入 2.46M→2.69M。

## 行動

- 寫 claude -p 串跑腳本：回合結果與被拒清單從 transcript 補齊，看 origin 欄判斷有沒有通知尾段
- 條件要判「哪個閘擋的」就讀 tool_result 的擋訊息，不看 permission_denials
- 合計成本取每個 session 的最大值
