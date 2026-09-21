# PostToolUse的tool_response不等於模型看到的結果-Edit帶整份originalFile-量context浪費要按工具取可見欄位

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: tool_response, PostToolUse, tool result size, 工具結果體積, context 浪費, originalFile, ToolResultSize, wg_friction, token 浪費量測, 誤報
- Created-at: 2026-09-18
- Related: codegraph與agent-retro評估結論-codegraph只當專案local-MCP不進記憶-agent-retro只拆量測, 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem

## 知識

- [臨] Claude Code PostToolUse hook 收到的 `tool_response` 是工具的原始回傳物件，**不是模型看到的文字**。Edit/Write/NotebookEdit 的 tool_response 帶 `originalFile`（整份檔案）+ structuredPatch，模型卻只看到一行「已更新」——直接量 `json.dumps(tool_response)` 長度會把每次 Edit 都判成 20K+ 浪費（wg_friction 首版上線 2 分鐘跨 session 誤報 8 筆）。
- [臨] 要量「進 context 的量」得按工具取可見欄位：Bash 取 `stdout`+`stderr`；Read 取 `file.content`；Edit/Write/NotebookEdit 視為 0；其餘 str 直接量、dict/list 以 JSON 長度近似（Grep/Glob/Agent 的 content 大致等於可見）。Bash 輸出超過 ~30K 字元時 CC 會把全文存檔只給模型 2K 預覽，hook 端仍拿到全文，此處量測偏高，可接受。
- [臨] 每個工具呼叫都會進 PostToolUse，量測資料若寫進 state 就是每呼叫一次 R-M-W（併發 hook 行程互蓋窗）；改 append-only 的 per-session jsonl（`workflow/tool-results/<sid>.jsonl`）、SessionEnd 聚合成一筆 guard log 再刪，state 只留 advisory 計數。

## 行動

- 新量測上線後立刻看第一批 log 的 tool 分布，Edit/Write 佔多數＝量錯欄位
- PostToolUse 內高頻寫入一律 append-only 檔，不進 state
