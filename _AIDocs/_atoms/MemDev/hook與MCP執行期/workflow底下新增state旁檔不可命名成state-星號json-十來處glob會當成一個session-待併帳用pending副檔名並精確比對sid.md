# workflow底下新增state旁檔不可命名成state-星號.json-十來處glob會當成一個session-待併帳用pending副檔名並精確比對sid

- Scope: global
- Author: holylight
- Source: 2026-10-23 state 讀改寫握鎖修補實測
- Confidence: [臨]
- Trigger: state-*.json, state 旁檔, workflow 新檔命名, glob state, 旁檔當成 session, .pending 副檔名, 待併帳檔名, sid 前綴撞名, state.js
- Created-at: 2026-10-22
- Related: state待併帳退路的不變量-基準記讀到的原文與指紋-自己的帳沒落盤只能再留帳-併過帳名與結果同次落盤-不轉給別的session

## 知識

- [臨] workflow/ 底下新增跟 state 放在一起的旁檔，不可命名成 `state-*.json`：清理、跨 session 協調、產出物帳本、MCP 的 state.js 等十來處都 glob `state-*.json`，會把旁檔當成一個 session。
- [臨] 待併帳改用 `.pending` 副檔名；撈同一個 session 的帳用「`<state 檔名>.<數字>-<數字>.pending`」精確比對，不靠前綴 glob，免得 sid `a` 撈到 sid `a.b` 的帳。

## 行動

- 在 workflow/ 新增檔案前先 grep 誰 glob state-*.json，新檔用不同副檔名
