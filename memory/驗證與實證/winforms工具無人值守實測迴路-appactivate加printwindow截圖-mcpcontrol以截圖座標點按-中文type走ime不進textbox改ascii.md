# winforms工具無人值守實測迴路-appactivate加printwindow截圖-mcpcontrol以截圖座標點按-中文type走ime不進textbox改ascii

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: WinForms 實測, GUI 自動化, MCPControl, PrintWindow, AppActivate, SetForegroundWindow 失效, 截圖座標, 注音 IME, type 中文, 無人值守驗證, 驗 GUI, 選圖驗版面
- Created-at: 2026-09-16
- Related: 禁ui自動化時怎麼驗winforms版面-printwindow截被遮住的視窗, feedback-能自動化実跑的驗證不准推給使用者-離線模擬不算驗證

## 知識

- [臨] WinForms 工具的端到端实測可全自動：PowerShell `Start-Process` 起 exe → `(New-Object -ComObject WScript.Shell).AppActivate($pid)` 拉到前景（`SetForegroundWindow` 常被前景鎖擋掉）→ `MCPControl get_screenshot` 取得縮放截圖（本機 1920×1080 → 1464×823），後続 `left_click` 座標直接用截圖座標，十字準星驗位；每一鍵後重截圖看 log/对话框。
- [臨] 被別的視窗蓋住時用 `PrintWindow(hwnd, hdc, 2)`（PW_RENDERFULLCONTENT）截該視窗，`Graphics.CopyFromScreen` 只會拍到上層視窗。
- [臨] MCPControl `type` 中文到 WinForms TextBox 不進字（走 IME，框内空但篩選邏輯收到亂码）；要驗篩選或輸入用 ASCII（先 ctrl+a 再 type）。
- [臨] 工具會寫 DB 的測試：先記 `LENGTH+MD5` 基線，寫完比對輸出檔的 MD5，再用工具自己帶的 MySqlConnector.dll（PowerShell `Add-Type -Path`）以參數化 UPDATE 把原檔還原，結束前再查一次基線。使用者己在桌面時先問再接管滑鼠。

## 行動

- 要驗 WinForms 工具：AppActivate → MCPControl 截圖 → 照截圖座標點 → 每步重截圖
- 視窗被蓋住用 PrintWindow 截，不用 CopyFromScreen
- 輸入框测試用 ASCII，中文 type 不可信
- 寫 DB 的工具測完用原檔還原並比 MD5
