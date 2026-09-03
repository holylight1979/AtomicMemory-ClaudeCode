# winforms-splitcontainer包住控制項後enter事件直接focus會焦點迴圈凍死

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 沒有回應, UI凍死, UpdateFocusedControl, SplitContainer, Focus(), Enter事件, ActiveControl, 焦點迴圈, dotnet-stack, WmSetFocus
- Created-at: 2026-08-21

## 知識

- [臨] **WinForms 地雷：在控制項的 Enter 事件裡直接對別的控制項 Focus()，一旦該控制項被包進 SplitContainer（或任何嵌套 ContainerControl）就會把 UI 執行緒凍死**：WmSetFocus 處理中途搬焦點 → 兩層容器互改 ActiveControl → ContainerControl.UpdateFocusedControl() 永遠收不斂 → 視窗「沒有回應」燒 CPU。同一條規則在控制項直掛 Form 時完全正常，改版面（多包一層容器）才爆——很難聯想到是版面改動引爆舊規則。
- [臨] 修法：焦點搬移一律 `BeginInvoke(() => x.Focus())` 延後一個訊息迴圈拍，跳出 WmSetFocus 的再入戰場；順手把 SplitContainer.TabStop 設 false 擋分隔棒搝焦點。
- [臨] 診斷手法：凍死行程還活著時用 `dotnet-stack report -p <pid>`（dotnet global tool，本機已裝）拍 UI 執行緒堆疊——看到 UpdateFocusedControl 在頂部吃 CPU_TIME 就是這顆雷，不用猜。

## 行動

- 把控制項搬進任何容器（SplitContainer/Panel 嵌套）前，先 grep 它的 Enter/GotFocus 事件有沒有直接 Focus() 別的控制項，有就先改 BeginInvoke
- UI 凍死先 dotnet-stack 拍堆疊再修，不靠猜
