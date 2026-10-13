# 使用者放行的判定要防偽造-只認tool_use_id對到AskUserQuestion的答案-打字放行要整句嚴格比對-跨回合要承接

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/to-track-e/006-returned.md（codex 審 track-e 001～004 的 B1～B3）
- Confidence: [臨]
- Trigger: 收尾放行確認, 使用者放行, 放行判定, AskUserQuestion 答案, tool_use_id, 偽造放行, 否定句, pending_release, wg_release, 擋滿
- Created-at: 2026-10-12
- Quote: 「這session所有你學到的重要知識、經驗都記好的話，我就關掉了。」

## 知識

- [臨] 「擋滿就問使用者、使用者放行才收尾」的第一版被 codex 抓到三個「看起來擋了、AI 自己能過」的洞：①解析任何 tool_result 裡像 `"題"="答"` 的文字 → Bash 印出就能偽造放行；②「使用者打放行」只排除緊貼的否定字 →「禁止放行」「為什麼會放行？」都算同意；③使用者另送「好，放行」會開新回合、預算歸零，同意被吃掉。
- [臨] 正解：①從 transcript 建「tool_use_id → 工具名」表，只採用對到 AskUserQuestion、且題目含固定標記的 tool_result；②打字放行要 NFKC 正規化後整句符合短肯定句正則；③擋滿記 pending_release，跨回合承接、不重給預算。通則：**任何「人同意了」的判定，來源必須是 AI 無法自己產生的結構欄位**，不能是文字比對。另：無法互動的情境（子代理、headless、裁判）依原設計者裁決一律擋到底；記憶與知識類的閘不套這套。
- [臨] 实踩（2026-10-13，讀碼與 guard-reconcile 日誌核實）：「擋滿才問、問了才看放行」的闘有兩個疊加漏洞——①只在 count≥max 或 pending 才查 user_released，使用者第 1 次被擋就按放行會被忽略；②每回合預算以 turn_seq 計，而 turn_seq 每則 UserPromptSubmit 無條件 +1（同伴 session 訊息、背景通知、AskUserQuestion 答案都算），多 session 並行時預算永遠 count=1、擋不滿。通則：每次擋都要查放行（只認最後一次擋之後的答案）；「回合」預算要以使用者真打字開的回合計，不能用任何 prompt 事件都會動的序號。查這類「闘沒擋滿」先看 Logs/guard-reconcile.jsonl 的 turn_seq→count 序列。
- [臨] 實走（2026-10-13，Logs/guard-reconcile.jsonl 同一 session turn 83／96／101／102 每次 count=1）：放行機制只在「擋滿或 pending」時才查使用者答案，而每回合預算用 turn_seq 計、turn_seq 在每一則 UserPromptSubmit 都 +1（同伴 session 訊息、背景通知、AskUserQuestion 答案都算）。兩者疊加：只要一直有訊息進來就永遠擋不滿、永遠不查放行，使用者連選三次「放行這一回合」都沒用。設計原則：使用者放行必須每次擋都查（只認最後一次擋之後的答案）；「回合」預算要以使用者真打字開的回合計，非使用者訊息不重置；擋滿的 pending 照舊跨回合承接。

## 行動

- 設計「使用者同意」類判定：只認 AI 偽造不了的結構來源，並寫「工具輸出印出同樣文字」的反例
- 放行要考慮跨回合：使用者的同意常在新的一則訊息裡
