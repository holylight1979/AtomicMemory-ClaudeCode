# feedback-大型多量條列計畫用總控台配靜默cli-session派工-claude-bg起軌不佔分頁-啟動時就設好模型-先決條件是有總控台

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-21 原設計者原話（G16 背景軌實跑後）
- Quote: 要加，負責執行項目的model，如你所說 必須在你啟動這類靜默Cli session時就設置好；且這個方法還不錯、可以記下來 未來長期對大型、多量條列項目計劃時用。那一個先決條件就是要是 "有總控台"。
- Confidence: [臨]
- Trigger: 靜默 CLI session, claude --bg 派工, console-spawn, 大型計畫派工, 多量條列項目, 總控台派工方法, 背景工作軌模型, --model 派工, 不佔分頁
- Created-at: 2026-10-21
- Related: claude-bg起的工作軌收尾會卡在askuserquestion沒人答-總控台看transcript最後一則是提問就直接對帳合併再claude-stop-worktree目錄要等程序退出才刪得掉

## 知識

- [臨] 原設計者定：大型、多量條列項目的計畫，長期用「總控台＋靜默 CLI session」派工：總控台用 tools/console-spawn.py（底層 `claude --bg`）在工作樹起背景 session 送開工句，不佔 VS Code 分頁、不用人貼 prompt，工作軌對完交付由總控台對帳合推。先決條件：**要有總控台**（沒人盯畫面，卡住、交付、收尾都靠總控台讀 transcript 與收信）。
- [臨] 負責執行項目的模型必須在起 session 時就設好（`claude --bg --model <id>`），不能事後改；沒指定就吃 CC 預設（實測是 Opus）。派工報備要寫模型與理由：閘本體與小修軌 Opus，對人裁定密集才 Fable。
- [臨] 背景軌的派工單要寫死：收尾不發 AskUserQuestion（沒人答）、每個改過的程式檔都要有案例、被擋滿要問人就把擋訊息寫進交付信給總控台裁。人要看它：`claude attach <短 id>`；停：`claude stop <短 id>`。

## 行動

- 大型多項目計畫：先開總控台，再用 console-spawn 起背景軌，起時帶 --model
- 沒總控台就不用這套，回到人貼開工句的分頁軌
