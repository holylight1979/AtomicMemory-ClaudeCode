# 雙claude協作實戰認知-fable監工opus主力的分工手感

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: Opus, 雙 Claude, 監工, 主力寫碼, 交叉驗證, 分工提案, 無人值守, 夜班, 預先 ok, 實機一輪, to-opus, to-fable, 雙 session
- Created-at: 2026-08-26
- Related: grok協作實戰認知-特質與監工分工手感, 並行llm即時通訊-inbox機制, 混改檔hunk級選擇性staging, 驗證腳本判準要錨結果句不能錨系統有反應-catch-all關鍵字等於自動通過, 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源, 實驗性改動的復原要驗回快照-送一次指令不算復原

## 知識

- [臨]（2026-08-25 MudClient 戰役後八包一夜完工）雙 Claude 分工模式：Fable 監工（commit 權唯一在我）兼實作自己最熟的線，Opus 實作另一線；**每包一邊實作、另一邊驗證**（自己 build、自己跑自測、讀碼）。開場一封信：計畫檔路徑＋分工表＋檔案所有權（共用檔只 Edit 小範圍、信裡列動了哪些方法）＋各自 build 輸出目錄＋實機共用行程要先 ack。Opus 回「同意即開工不必再等信」很有效。
- [臨] Opus 特質：規格內自決附理由、會對規格提否決（三次全對：戰鬥窗不擋自己 rest、血條看前景、RoomDetailReady 餵 NPC）、誠實回報意外並自行修復（remove all 後 wear all 少 7 件→逐格對帳）；弱點：**驗證腳本判準太鬆**（catch-all 關鍵字把「未收斂」標通過）——監工必須自己讀逐字稿行號原文，不信 RESULT 行。
- [臨] 共用工作樹的代價：對方半成品隨時在樹上，`git add <檔>` 兩次掃進對方 hunk；解法見 [[混改檔hunk級選擇性staging]]（隔離匯出 index 建置是最後一道閘）。一夜七個 commit 全靠它。
- [臨] 無人值守規則實踐：遇本該問使用者的遊戲事實→先實機取證，取不到採最保守（不送／不改態／做成設定）並標「待使用者確認」不停工；實機一輪合併多包取證、預先 ok 附條件（備份／quit 確認句／不勾自動戰鬥／地圖還原）；15 分鐘靜默看門狗（背景 bash 從現在起計時，不要用最新檔 mtime 否則掃到就觸發）。
- [臨] 收尾必做：雙方 build 都在暫存目錄時，**最後要就地 `dotnet build` 一次**，不然使用者開到的 exe 是舊的（使用者第一句就問「沒有編譯出 exe??」）。
- [臨] 通道做法：同一個 `.ai-inbox` 加開 `to-opus\`／`to-fable\`，規則與 Grok 通道完全相同、寫進 `PROTOCOL.md` 末段即可，不另建協定檔；兩條通道並存互不干擾。Opus 側用 Monitor persistent bash **每 2 秒比目錄檔名差集**喚醒，一晚 20+ 封零漏接。
- [臨] 共用資源分兩級：port／行程（headed client、4321）**寄 `status-*` 打招呼就可以動手**、不等回信；真獨佔（連遊戲）才用 `ack` 等 `ok`。實測這樣分級一晚沒撞過一次。

## 行動

- （依知識內容判斷）
