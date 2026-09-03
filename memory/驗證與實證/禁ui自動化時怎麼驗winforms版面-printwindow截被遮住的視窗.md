# 禁UI自動化時怎麼驗WinForms版面-printwindow截被遮住的視窗

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 截圖驗證, PrintWindow, CopyFromScreen, WinForms 版面, FlowLayoutPanel, 被遮住的視窗, GUI 驗收, 禁 UI 自動化
- Created-at: 2026-08-21
- Related: winforms自繪捲動畫布-版面算內容座標-捲動只在繪製端套用, designer控制項初始值設太早-事件處理器讀到還沒建好的欄位-啟動即靜默崩潰

## 知識

- [臨] 不能用 UI 點擊自動化時，**截圖是合規的觀察手段**（只讀不操作），而且是驗版面的**唯一**方法——REST／日誌只能驗資料，驗不到「欄位被截斷」「按鈕被切出視窗」這種問題。
- [臨] `Graphics.CopyFromScreen` **只能拍最上層**：目標視窗被別的程式蓋住時，拍出來的是蓋在上面那個程式（實測拍到 VS Code）。正解是 `PrintWindow(hwnd, hdc, 2)`（flag 2 = PW_RENDERFULLCONTENT），**被遮住也拍得到**，不必把視窗拉到前面（那才是「操作 UI」）。
- [臨] PowerShell 實作的坑：`Add-Type` 的 C# 區塊裡**不要**碰 `System.Drawing`（.NET 8+ 型別轉送到 System.Drawing.Common，要補一堆組件參考才編得過）。C# 區塊只放 P/Invoke 宣告，Bitmap／Graphics／`GetHdc()` 留在 PowerShell 側做。拿視窗清單用 `EnumWindows` + `GetWindowThreadProcessId` 篩行程，不要只看 `MainWindowHandle`（它只給得出一個，且未必是你要的那個）。
- [臨] ⚠ **WinForms `FlowLayoutPanel` 搭 `WrapContents=false` 溢出時是靜默切掉**：往已經快滿的工具列加控制項，新控制項不會折行也不會報錯，就是看不見（實測：加兩顆按鈕，第二顆整顆消失）。加完一定要截圖看，不夠寬就去收窄旁邊的下拉框或縮小按鈕。
- [臨] `GetWindowTextW` 的 DllImport **必須標 `CharSet = CharSet.Unicode`**——只靠函式名的 W 尾碼不夠，StringBuilder 預設走 ANSI marshal，中文視窗標題會整串亂碼、依標題找視窗永遠找不到（實測踩過）。
- [臨] Add-Type 的型別**不跨 PowerShell 工具呼叫存活**（每次呼叫是新行程）——列舉視窗＋截圖要包在同一次呼叫裡。

## 行動

- 改完 GUI 版面（新控制項、欄寬、表頭）一律截圖自檢，不要只信「建置成功」
- 目標視窗可能被遮住 → 用 PrintWindow flag 2，不要用 CopyFromScreen，也不要把視窗拉到前面
