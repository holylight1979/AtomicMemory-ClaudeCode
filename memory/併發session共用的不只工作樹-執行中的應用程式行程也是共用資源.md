# 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 並行 session, 併發 session, Stop-Process, 重啟應用程式, 部署新版, 共用行程, 測試循環, 重啟服務, CoordWarn
- Created-at: 2026-08-19
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, 混改檔hunk級選擇性staging, 輸出exe被執行中行程鎖住-建置驗證改輸出目錄-行為驗證add-type載dll跑自測, 並行llm即時通訊-inbox機制, 雙claude協作實戰認知-fable監工opus主力的分工手感

## 知識

- [臨] 併發 session 共用的不只是 git 工作樹，**還包括正在跑的應用程式行程、它的連線與進行中的長工作**。「編新版 → Stop-Process 關舊 → 啟新」這種標準部署循環在單 session 是安全的，在併發下會**直接砸掉另一個 session 正在跑的任務**。
- [臨] 實例（2026-08-19 MudClient-withAI）：我為了驗證自己的改動，兩次 `Stop-Process -Name <app> -Force` 重啟 client，而另一個 session 正在同一個 client 上跑需要數十分鐘的資料抓取。那個功能有續傳所以資料沒壞，但對方的迴圈停在半路。**Guardian 的 CoordWarn 只提醒檔案衝突，不會提醒行程衝突**。
- [臨] 辨識訊號：畫面／日誌裡出現**你沒送過的指令或請求**（本例是逐條 `sattr xxx`），就代表這個行程同時被別人驅動。別當雜訊忽略。
- **Why:** 行程重啟不可逆，且影響的是別人進行中的工作，不是自己的檔案——事後無法像 hunk 那樣拆回來。
- **How to apply:** 重啟共用行程前先看一眼它現在在做什麼（畫面／狀態端點）；確定有別人在用就改用不殺行程的驗證手段（純函式測試、另起一個埠的實例），非重啟不可則在收尾報告明說打斷了什麼、對方要怎麼接回去。 [[併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a]]
- [觀] ⚠ **2026-08-20 又犯一次（這條 atom 當時已經被注入）**：MudClient 任務裡我先好好地每次 kill 前都先 `curl /status` 確認未連線，但最後一次「只是補個測試而已」的小改動就把這道檢查省掉，`taskkill` 直接下去——使用者正在用該程式玩遊戲（斷線後角色 link-dead 留在遊戲裡）。**進度到尾聲、改動看起來很小、先前幾次都沒事——這三個條件同時成立時最容易省掉守門。**
- [觀] 機械化防線：把「確認沒人在用」**串在同一行指令裡**，不要當成另一步。例：`curl -s $STATUS | grep -q '"connected":false' && taskkill /F /IM app.exe`——連線中就自動不執行，不靠我記得要檢查。

## 行動

- 部署／重啟任何共用行程前，先確認它此刻沒在跑別人的長工作
- 看到自己沒送過的指令出現在畫面上，先假設是別的 session 在驅動同一個行程
- 真的打斷了就在收尾報告明講，附上怎麼續接
