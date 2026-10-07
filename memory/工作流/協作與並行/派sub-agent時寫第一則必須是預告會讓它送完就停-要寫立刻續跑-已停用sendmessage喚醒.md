# 派sub-agent時寫第一則必須是預告會讓它送完就停-要寫立刻續跑-已停用SendMessage喚醒

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: sub-agent, 並行 agent, 預告, agent 停了, 0 tool uses, SendMessage, 喚醒 agent, 介面契約, 共用檔唯一寫者
- Created-at: 2026-10-01
- Related: workflow-parallel-agents, 並行agent產出併入交付物必須標驗證強度分層
- Source: session:a7ac6c34#f799d45f 2026-10-01
- Quote: 「計畫請考慮盡可能 多開agent分工、以高速進行」

## 知識

- [臨] （四支實作 agent 全中）agent prompt 寫「你的第一則輸出必須是兩行預告」，agent 會把預告當成整個回合的輸出、送完就結束（回報只有預告、0 tool uses）。要寫成「先輸出預告，然後立刻繼續呼叫工具，中途不要停」。
- [臨] 已停的 agent 不必重派：SendMessage 送「預告已收到，現在直接開始呼叫工具」即可從原 transcript 續跑；還在跑的 agent 訊息會排隊到它下一個工具回合送達，順便可補契約變更。
- [臨] 多 agent 並行實作的整合成本取決於派工前有沒有把跨 agent 介面（函式簽名、檔案格式、config 鍵名、receipt 欄位）寫死在每支 prompt，並指定共用檔（config/settings/.gitignore）的唯一寫者；其他 agent 用 try/except import 對接尚未落地的模組。四支零交集整合只花 3 處小修。

## 行動

- agent prompt 的預告句後面一律接「然後立刻繼續呼叫工具」
- 收到 0 tool uses 的回報 → SendMessage 喚醒，不重派
- 派工前先寫介面契約與共用檔寫者表
