# 無頭探針驗skill行為-claude-p加setting-sources-project與strict-mcp-config不載使用者層hook與MCP

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測
- Confidence: [臨]
- Trigger: 無頭探針, claude -p, --setting-sources project, --strict-mcp-config, skill 行為實測, stream-json, 探針不寫 live
- Created-at: 2026-10-22
- Related: 無頭受測要關掉全部hook用claude--settings的disableAllHooks旗標-hooks只來自使用者層settings-資料根放空settings不生效, Git-Bash傳斜線開頭參數給Windows原生程式會被轉成路徑-例claude-p的slash指令-MSYS_NO_PATHCONV只能加在那一次呼叫-全域export會讓python讀不到斜線c路徑

## 知識

- [臨] 要實測某個 skill 或設定對模型的效果，又不想讓使用者層 hook 寫進正式資料：在暫存目錄放 `.claude/skills/<探針>/SKILL.md`，從那個目錄跑 `claude -p "<問題>" --setting-sources project --strict-mcp-config --no-session-persistence --model <小模型> --output-format stream-json --verbose`；`--setting-sources project` 只載專案層設定（使用者層 hook 不掛），`--strict-mcp-config` 不載使用者的 MCP，結果從輸出裡的 tool_use／tool_result 讀。
- [臨] Git Bash 傳以 / 開頭的參數要只在那一次呼叫前加 MSYS_NO_PATHCONV=1；claude.exe 不在 PATH 時用 tools/codex-companion/judge_backend.resolve_claude_bin 找路徑。

## 行動

- 實測 skill／設定效果：暫存目錄放專案層 skill，claude -p 加 --setting-sources project --strict-mcp-config 跑，讀 tool_use／tool_result
