# Designer控制項初始值設太早-事件處理器讀到還沒建好的欄位-啟動即靜默崩潰

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: WinForms, Designer, InitializeComponent, SelectedIndex, SelectedIndexChanged, 建構式, 啟動就崩潰, exe 起不來, NullReference, 事件處理器, 初始化順序
- Created-at: 2026-08-18

- Related: 禁ui自動化時怎麼驗winforms版面-printwindow截被遮住的視窗

## 知識

- [臨] 在 Form 建構式裡給 Designer 控制項設初始值（`comboBox.SelectedIndex = 0`、`checkBox.Checked = x`…）會**立刻觸發它的 Changed 事件**。若該事件處理器讀的欄位還在建構式後面才建（readonly 非 null 型別也一樣），就是 NullReference——而且發生在 UI 起來之前，**畫面什麼都不會顯示**，exe 直接沒跡象，build 又是 0 錯誤，很容易誤判成部署問題。
- [臨] 兩道防線一起上：① 把「設初始值」移到所有相依欄位建好之後（並在該行旁寫下為什麼不能提前）；② 事件處理器開頭加守衛（`if (SelectedIndex < 0) return;` 或 null 檢查）。只做① 下次重排建構式又會重現。
- [臨] 診斷手法：WinForms 啟動即死且無視窗時，先檢查建構式裡「跨層讀別的欄位」的行，而不是先懷疑 build 輸出或部署路徑。
- [觀] 同型第二次出現（MudClient 2026-08-25）：不只「Designer 控制項設初始值」會踩到——**任何 `InitXxx()` 尾端呼叫的 `RefreshXxx()`** 都一樣。實例：`InitFlowUi()` 末尾呼叫 `RefreshFlowUi()`，而新加的 `RefreshEnemyHpLabel()` 讀 `_autoCombat`（要到 `InitAutoCombat()` 才建、宣告成 `= null!`）→ 建構式當場 NullReference。`= null!` 讓編譯器閉嘴，等於把這種錯全推到執行期。
- [觀] 症狀與診斷順序不變，但多一個更快的取證手法：headless／無視窗模式下把 stdout+stderr 導進檔案（`app.exe --headless > out.txt 2>&1`）就會拿到完整 stack trace，比從「exe 沒反應」猜起快得多。有視窗版反而看不到（例外在視窗建起來前就炸）。
- [觀] 判準一句話：**Init 系列方法有先後順序，Refresh 系列方法沒有**——Refresh 會被任何一個 Init 呼叫到，所以它必須對「相依欄位還沒建好」免疫。守衛寫在 Refresh 開頭（`if (_dep is null) return;`）比排 Init 順序耐放，因為下次有人插一個新 Init 進來不會再犯。

## 行動

- 建構式裡的控制項初始值一律排在相依欄位建置之後，且事件處理器自己也要能承受「還沒準備好」
- WinForms 啟動即死、無錯誤訊息時，先審建構式的初始化順序
