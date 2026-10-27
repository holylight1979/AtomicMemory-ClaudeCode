# 用真hook重放對話紀錄量閘的擋次-原session的系統暫存路徑要對到沙箱暫存-計數只認那條閘自己的標記

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 回放探針, transcript 重放, replay, 擋次統計, 沙箱, WG_CLAUDE_DIR, 暫存判定, 修前修後
- Created-at: 2026-10-13
- Source: session:03f81f65 2026-10-13

## 知識

- [臨] 用真 hook 入口重放一份真實 transcript（沙箱的資料根、家目錄、TEMP 全指 tmp）來量「修前／修後擋幾次」時，路徑改寫要兩組：live 根層路徑對到沙箱專案，**原 session 的系統暫存（scratchpad 所在的 %TEMP%，含 8.3 短名寫法）對到沙箱的 TEMP**。只改前者時，原本被當暫存的 scratchpad 改檔在沙箱裡變成普通程式檔，假的 (d) 擋次會覆蓋真正要量的數（實例：修後本該 0，量出 15）。改寫順序也要先改暫存、再改根層，因為沙箱自己就在 %TEMP% 底下。
- [臨] 擋次要用那條閘自己的標記算（例：`[Guardian:ReconcileGate]` 且含「改了程式碼（」）；只找 `(d)` 會把 ScanReport 的「(d) 記憶收錄帳」也算進來。開環重放（hook 擋了也照原紀錄往下送）只能比修前修後，不能推模型會怎麼回應；原 session 若一路合規（例：都交了定位三行），要另跑一個「刪掉合規內容」的變體才量得到那個成本。

## 行動

- 寫重放探針：先映射系統暫存、再映射 live 根；先試跑一次看擋的理由是不是預期的那條閘
- 計數只認閘名標記，不認字母代號
