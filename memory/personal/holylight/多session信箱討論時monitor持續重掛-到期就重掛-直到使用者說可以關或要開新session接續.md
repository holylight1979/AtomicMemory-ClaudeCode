# 多session信箱討論時Monitor持續重掛-到期就重掛-直到使用者說可以關或要開新session接續

- Scope: personal:holylight
- Author: holylight
- Source: session:3e106167#28e84fef 2026-10-07
- Quote: 「"實驗設計被抓到三次洩題": 發現問題，要想辦法從根源解決；無法解決也要記下來LLM有這種問題、日後要持續追蹤解法啊。」
- Confidence: [臨]
- Trigger: Monitor, 信箱, 重掛, 到期, tri-link, 多 session, 盯信
- Created-at: 2026-10-07

## 知識

- [臨] 使用者原話：「monitor 持續掛，掛到我說可以關掉了、或要新開 session 接續了為止。」盯信的 Monitor 每 30 分鐘到期，到期就重掛，不問、不等使用者戒；只有使用者明說關、或宣布開新 session 接續才停。
- [臨] 適用範圍：目前只有檔案信箱要 Monitor 盯（Grok 的 .ai-inbox、跨人跨帳號的 mailbox）。Claude Code session 之間改用 SendMessage，閒置的收件端會自動開回合，不必掛 Monitor 等信。

## 行動

- 盯檔案信箱時收到 Monitor 到期通知 → 立刻重掛同一條，一句帶過
- 跟另一個 Claude Code session 討論：用 SendMessage，不為了等信掛 Monitor
