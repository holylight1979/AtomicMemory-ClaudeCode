# 量測收據要認DONE帶k=v-sentinel_regex會把普通pytest統計行也轉成PYTEST_MEASURE-DONE-閘的反例案例要斷言回傳值不是斷言輸出沒某字樣

- Scope: global
- Author: holylight
- Source: G7 軌（claude-12 [1493d2]）2026-10-20 交付 003 與收割代寫清單；總控台代寫
- Confidence: [臨]
- Trigger: PYTEST_MEASURE, sentinel_regex, 量測收據, DONE k=v, 熱路徑量測, 反例案例, 斷言回傳值, 擋空訊息, [null, null], 閘壞成恒擋
- Created-at: 2026-10-20
- Quote: 「我剛才手動關了G16，才想到要問.. attach 是要怎麼測? 開 console ??」

## 知識

- [臨] workflow/config.json 的 sentinel_regex 會把普通 pytest 的統計行同時轉成 `PYTEST:PASS` 與 `PYTEST_MEASURE:DONE`，所以任何閘拿「有 DONE 哨兵」當量測證據，跑一次普通測試就满足了。量測收據要認 `<NAME> DONE k=v` 帶數字的（G7 熱路徑閘的 has_measure 已這樣判）；對帳 (b)「量了」可能同病，待查。
- [臨] 閘的「不該觸發」反例若只斷言「輸出裡沒有某字樣」，閘壞成擋空訊息也會綠（實例：回傳型別從元組改單值、漏改提早 return，元組恒真，每次 Stop 都擋、reason 是 [null, null]，只有真 hook 行程的測試抓到）。反例要直接斷言閘的回傳值是 None（或明確的放行值）。

## 行動

- 寫量測類閘：收據要帶 k=v 數字，不認裸 DONE
- 寫閘的反例：斷言回傳值，不斷言輸出缺字樣；多一支真 hook 行程的案
