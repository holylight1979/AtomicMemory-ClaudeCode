# origin標使用者說的要那句原話說出這個動作-只提到同一物件不算-做法與延伸標推出來的

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md E23
- Confidence: [臨]
- Trigger: origin, 使用者說的, 推出來的, quote, 對不到原話, 標使用者說的但對不到原話, 目標樹, need_goal
- Created-at: 2026-10-21
- Quote: 「A」
- Entry: E23

## 知識

- [臨] 要標 origin=user，判準是：拿掉我的推理、只看那句原話，讀的人會不會說「他要的就是這個節點」。原話只提到同一個物件（同一支測試、同一個檔），卻沒要求這個動作 → inferred。
- [臨] 程式只核對字面子串，硬掛一句字面對得上的原話照樣會過。反例：使用者說「test_legacy_report 先不用管它、跳過」，節點寫「刪掉 test_legacy_report 和相容層」並引用這句——字面對得上，但使用者沒說刪，這是推論。
- [臨] 為了防呆、品質自己加的子目標（加回歸測試、補文件）是 grown 或 inferred，不引原話；被降級成 inferred 時不要換一句原話再試。

## 行動

- 標 origin=user 前，把節點文字和 quote 並排讀：quote 有沒有說出節點的動作？沒有 → inferred
