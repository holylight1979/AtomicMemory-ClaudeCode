# feedback-對使用者指稱session一律用分頁標題看得到的軌名-claude-xx是session間通訊名他看不見

- Scope: global
- Author: holylight
- Quote: 哪一些 session 可以關閉，不要給我你們溝通用的名稱，我看不見那些名稱。要給我 title 上就可以看得出來的~!
- Confidence: [臨]
- Trigger: 可以關的 session, 關分頁, session 名字, claude-xx, 軌名, 分頁標題, 多 session 回報, 總控台回報, --name
- Created-at: 2026-10-13

## 知識

- [臨] 使用者原話（自述先前說過）：「哪一些 session 可以關閉，不要給我你們溝通用的名稱，我看不見那些名稱。要給我 title 上就可以看得出來的。」ListAgents 的 claude-xx 是系統替沒指定名字的 session 配的 SendMessage 地址；VS Code 分頁標題顯示的是開工句開頭（軌名＋分支＋工作摘要）。對人回報、請他關或開分頁，一律用軌名＋分支，claude-xx 只在 session 間訊息用。
- [臨] 工作軌目前用 `claude --bg --name <軌名>` 起，地址就是軌名，對人對 session 同一個名字；使用者在 `claude agents` 總覽看到的也是它。開工句第一句仍把軌名放最前面，手開的分頁標題才看得出來。

## 行動

- 對使用者講哪個 session 可關／在做什麼：寫「<軌名> 分頁」，不寫 claude-xx
- 開工作軌用 --name <軌名>，開工句第一句以軌名開頭
