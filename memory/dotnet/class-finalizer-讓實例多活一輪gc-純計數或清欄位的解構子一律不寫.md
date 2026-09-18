# class-finalizer-讓實例多活一輪gc-純計數或清欄位的解構子一律不寫

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: finalizer, 解構子, ~ClassName, 終結器, GC 多一輪, FInstCount, 實例計數, finalization queue, f-reachable, IL2CPP GC, Boehm
- Created-at: 2026-09-18

## 知識

- [臨] class 宣告 `~Finalizer()` 的代價：`new` 時登記進終結名單（配置變慢）；GC 判定無人引用後不能當次釋放，先進「等跑解構子」隊列、連同它引用的物件一起繼續活著，終結執行緒跑完後要等下一次 GC 才真釋放，且會被升到較老世代（更少被掃、拖更久）。IL2CPP（Boehm GC）同樣有這套兩階段成本。
- [臨] 解構子裡寫 `field = null` 毫無作用：物件已經不可達，它的欄位引用也只經由它可達，清不清都一樣。只為 Editor 實例計數（`FInstCount--`）而加的解構子，若無人讀該計數 → 整段刪；有人讀也要知道它讓每個實例都付上述成本，高頻配置的物件（每次播音效配一筆指令）尤其不宜。
- [臨] 合理的 finalizer 只有一種：持有非受控資源（原生 handle）且要防 Dispose 漏呼的安全網。純 managed 物件一律不寫。

## 行動

- 看到 `~ClassName()` 先問裡面釋放的是不是非受控資源；不是就刪
- 刪前 grep 計數器有無讀者（Inspector / Editor 工具），沒人讀連計數器一起刪
