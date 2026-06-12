# runtime鏡射宿主生命週期判定與反射差分測試

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: runtime 鏡射, cache 洩漏, ConditionalWeakTable, stale cache, 差分測試, 反射測試, write-through, 解耦
- Created-at: 2026-06-12

## 知識

- [臨] runtime 鏡射（存檔=runtime 解耦）的宿主生命週期判定：mirror 掛「與資料同生死的宿主」（entity/info 物件）→ 普通欄位即可；mirror 宿主比資料長壽（module/manager 層 cache）→ 用 `ConditionalWeakTable<資料實例, Mirror>` 以資料實例為 key，否則資料重載換實例時舊鏡射 stale+洩漏（id 當 key 是陷阮）
- [臨] 行為等值差分測試可反射呼叫「真實上線碼」而非複製邏輯：private static 字典 lambda、private helper 都能 `GetField/GetMethod(NonPublic)` 取出直接測；ctor 帶 null 依賴繞開 server 依賴（只要測試路徑不觸發該依賴）；`FormatterServices.GetUninitializedObject` + 反射補欄位可跳過重依賴 ctor。出處：SGI r13315/r13316 差分測試 11/11
- [臨] 既有 `Dictionary<K, Func<Proto,V>>` static 字典改鏡射時，把 lambda 簽章換成 `Func<宿主型別,V>`保持 static；不要搬進建構子變 instance 字典（每實例配置=記憶體 regression）

## 行動

- module 層 per-data cache 一律先問：宿主比資料長壽嗎？是→ CWT
- 差分測試優先反射真碼，不複製邏輯
