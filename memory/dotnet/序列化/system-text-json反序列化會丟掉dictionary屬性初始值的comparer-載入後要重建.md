# system-text-json反序列化會丟掉dictionary屬性初始值的comparer-載入後要重建

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: System.Text.Json, JsonSerializer.Deserialize, Dictionary comparer, OrdinalIgnoreCase, 大小寫不分, 反序列化, 載入後查不到, StringComparer
- Created-at: 2026-09-03

## 知識

- [臨] `public Dictionary<string,int> Exits { get; set; } = new(StringComparer.OrdinalIgnoreCase);` 經 System.Text.Json 反序列化後，屬性被換成新建的預設比較器字典，初始值的「大小寫不分」丟了（實測 2026-09-03：存 `ExitNames["E"]` 載入後用 e 查不到）。鍵將來都經同一個正規化函數時影響小，但任何直接用原字查的地方都會靈時失效。
- [臨] 解法：Load 後對每個物件跑一次 `RestoreComparers()`（`new Dictionary<>(old, StringComparer.OrdinalIgnoreCase)` 重建），或把屬性改成 init-only 並用 JsonConverter；加一條「存檔再載入後用大寫鍵查」的 round-trip 自測鎖住。

## 行動

- Dictionary 屬性帶自訂 comparer 且會進 JSON 的，Load 後重建並補 round-trip 自測
