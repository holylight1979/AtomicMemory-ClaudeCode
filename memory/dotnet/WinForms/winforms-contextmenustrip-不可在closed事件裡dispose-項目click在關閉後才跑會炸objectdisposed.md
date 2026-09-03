# winforms-contextmenustrip-不可在closed事件裡dispose-項目click在關閉後才跑會炸objectdisposed

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: ContextMenuStrip, ObjectDisposedException, Closed 事件, Dispose, 右鍵選單, ToolStripMenuItem Click, WinForms 釋放, GDI 洩漏, CreateHandle
- Created-at: 2026-09-03

## 知識

- [臨] WinForms 右鍵選單每次 new 一份想釋放，**不能** `menu.Closed += (_, _) => menu.Dispose()`：選單是先關閉（Closed）才執行項目的 Click，Click 裡开 MessageBox／ShowDialog 時 WinForms 會回頭碰選單（CreateHandle），已被 Dispose 就炸 `ObjectDisposedException: System.Windows.Forms.ContextMenuStrip`。實機（2026-09-03）：右鍵「刪除」項目一點就跳當。
- [臨] 正解：留一個欄位記上一份選單，開下一份時才 Dispose 上一份（或視窗 Dispose 時收）；要不就把選單建一次重複用。審查工具提「選單沒 Dispose 是洩漏」沒錯，但修法選錯時機就是回歸——視窗資源釋放這類改動沒實機點過不要當零風險。

## 行動

- 右鍵選單釋放：欄位記上一份、開新的才 Dispose 舊的
- 視窗資源釋放類改動上版前至少實機點一次該選單的每個項目
