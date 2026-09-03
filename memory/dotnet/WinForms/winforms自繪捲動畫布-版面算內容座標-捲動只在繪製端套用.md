# WinForms自繪捲動畫布-版面算內容座標-捲動只在繪製端套用

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: WinForms, AutoScrollPosition, AutoScrollMinSize, 自繪, Paint, 捲動, scroll, 畫布, isometric, 等距, 命中測試, hit test, 捲到某物
- Created-at: 2026-08-18

- Related: 禁ui自動化時怎麼驗winforms版面-printwindow截被遮住的視窗

## 知識

- [臨] WinForms 自繪捲動 Panel 常見寫法是「算版面時就把 `AutoScrollPosition` 加進每個元素座標」。元素少、畫布小看不出問題，但畫布一大（例如等距投影展開成數千 px）就會踩到：座標同時混了『內容位置』與『目前捲到哪』，於是**寫不出「把某元素捲到畫面中央」**——沒有一組穩定的內容座標可拿來設 `AutoScrollPosition`。實測症狀：開窗只看到一片空白角落，元素其實有畫、只是在畫布別處。
- [臨] 正解是分層：版面計算**只產出內容座標**（原點在畫布左上、與捲動無關）；捲動位移只在繪製端用 `g.TranslateTransform(AutoScrollPosition.X, AutoScrollPosition.Y)` 套一次。之後「捲到某物」＝ `AutoScrollPosition = new Point(cx - view.Width/2, cy - view.Height/2)`（值取正，框架自己轉成負的 offset），一行就成立。
- [臨] 分層之後**滑鼠事件要自己補回換算**：`e.Location` 是 client 座標，命中測試前要減掉 `AutoScrollPosition`（它是負值，寫成 `e.X - AutoScrollPosition.X`）。忘了這步的症狀是「沒捲動時點得到、捲動後點不到」。
- [臨] 大畫布另外值得配「首次開窗自動 fit 縮放」加「目標離開可視範圍才自動捲」：永遠自動置中會跟使用者手動瀏覽打架。fit 的縮放下限要留在文字還讀得懂的比例（實測 0.5 已看不清中文標籤，0.75 可接受）。

## 行動

- 自繪捲動畫布一律讓版面函式回傳內容座標，捲動位移只在 Paint 用 TranslateTransform 套用
- 分層後檢查所有滑鼠事件：命中測試前把 client 座標減掉 AutoScrollPosition
- 畫布遠大於視窗時，加「目標離開視野才自動捲」而非每次置中
