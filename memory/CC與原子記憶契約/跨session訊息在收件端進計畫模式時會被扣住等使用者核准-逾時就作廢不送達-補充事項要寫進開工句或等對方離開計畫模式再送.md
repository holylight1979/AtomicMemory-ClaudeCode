# 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送

- Scope: global
- Author: holylight
- Source: 調度總控台 track-workflow-cleanup 補充訊息逾時 2026-10-14
- Quote: 「確認看看還有什麼沒做或者沒收割的，要關session了」
- Confidence: [臨]
- Trigger: 跨 session 訊息被扣住, Cross-session delivery notice, held by that session, not approved before expiry, 計畫模式 收不到訊息, 權限模式不同, crossSessionInbound, 開工句補充
- Created-at: 2026-10-15

## 知識

- [臨] 收件端權限模式跟寄件端不同（例：工作分頁照指示進計畫模式）時，Claude Code 預設把跨 session 訊息扣住，要使用者在那個分頁按核准，沒人按就逾時作廢、對方完全看不到；寄件端會收到 held 與 not approved before expiry 兩則通知，重送只會再被扣。
- [臨] 使用者設定 `crossSessionInbound: "accept"` 後不再扣，計畫模式的分頁也直接收得到。本系統根層 settings.json 已設；看到 held 通知先查收件端那台機器的這個設定。

## 行動

- 收到 held 通知：先確認 settings.json 有 crossSessionInbound: "accept"；沒有就告訴使用者那個分頁有訊息待核准，不重送
- 別台機器或別的設定檔起的 session 不保證有這個設定：要說的事仍盡量一次寫進開工句
