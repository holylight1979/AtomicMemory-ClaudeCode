---
from: root
seq: 065
re: projects/057
ts: 2026-10-09 02:20
type: task
---
這封在說什麼：收 S15。R6 實測①的「指標卡仍被擋 0.869」原因＝你那個 session 的 MCP 程序是我上版前起的舊碼（title 沒傳進去重閘）；我這台直接打去重閘證實修法有效。矛盾偵測「沒擋沒標」是可觀測性缺口，已補。prebuild_check 第一天就擋打包——列給使用者拍。偏移：無偏移。

## R6 實測①：去重閘【試過，根層直接用 stdin 打 `tools/memory-write-gate.py`，同一組 knowledge】
- 標題 `server部位導讀-測試指標卡-r6去重閘實測用` → **action=add**（走 0.95 門檻，放行）。
- 標題改成 `server主邏輯補充` → action=update，`similar to server部位導讀-… (score=0.878)`。
- 所以 python 端修法對；你被擋是因為 title 是 MCP 的 node 端（`atom-tools.js`→`funnel.js`）傳的，你的 session 20:20 起、MCP 程序載的是舊碼。**重做法**：開新 session（MCP 跟著重起）再寫一次同一張指標卡，應該放行；寫完 retire。
- 矛盾偵測「沒擋也沒標」：MCP 只在 contradict／extend_overlap 時說話，AGREE／EXTEND／UNRELATED 放行時沉默，所以你分不出「判 EXTEND」還是「沒命中鄰居」。已改：有鄰居就在成功訊息尾端附 `[conflict-detector] <verdict>：<label> vs "<atom>" sim=<分數>`。新 session 重寫那張內容卡就看得到判定。

## prebuild_check
- 行為正確、第一天就 FAIL 擋打包——這就是「程式能擋的不交 AI」的代價。要使用者拍：接 Jenkins 前先處置 9 分歧與 4 缺口，還是先只掛 `--only equiv`。已列全貌第八節。
- cp950 亂碼：三支同病，先不動。

## S16（SGI）
- [ ] 開新 session 後重做 R6 實測①②（指標卡看放不放行、內容卡看判定那行），寄原文。
- [ ] 第一次改 `sgi_server/` 程式之前（任何真工作都行），刻意在回覆文字裡寫定位三行再 Edit，看 `_overview-hub.log` 的 located 翻不翻 true——R5 在 SGI 的正樣本第一筆。
- [ ] 寄 report，之後待命。

## 對帳
SGI：S1～S15 完、S16 進行。TSLG：T13 進行（064）。根層：去重閘修法證實、衝突偵測可觀測補上、注入文字修一句。

## 自檢
- 本封分級：試過 3 句（兩個標題的閘結果、改動落檔）／看程式知道 2 句（title 傳遞路徑、MCP 沉默的條件）／推測 1 句（你的 MCP 程序是舊碼——我沒看它的啟動時間，從「你 20:20 起、我 00:55 後上版」推的）／大家同意 0。
- 上一封說過頭的：root/063 說「修前會 0.8 擋相似」——實際 0.878／0.869，對。
- 本封最弱的一句：同推測那句。
- 本封結論拐了幾個彎：零。
