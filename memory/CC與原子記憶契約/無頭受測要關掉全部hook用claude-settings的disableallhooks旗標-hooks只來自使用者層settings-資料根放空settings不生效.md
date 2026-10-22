# 無頭受測要關掉全部hook用claude--settings的disableAllHooks旗標-hooks只來自使用者層settings-資料根放空settings不生效

- Scope: global
- Author: holylight
- Source: commit:8e6ffe3c 2026-10-22（實測）
- Confidence: [臨]
- Trigger: hook 全關, disableAllHooks, --settings, 無 hook 對照組, 量 hook 代價, WG_CLAUDE_DIR settings
- Created-at: 2026-10-22

## 知識

- [臨] 要跑「沒有任何 hook」的對照組：hooks 只從使用者層 ~/.claude/settings.json 載，WG_CLAUDE_DIR 指到的資料根放一份空 hooks 的 settings.json 不會生效；正解是 claude 啟動帶 `--settings '{"disableAllHooks":true}'`（旗標層蓋過使用者層，CLAUDE.md／MCP 照舊）。驗法：一句話探針，transcript hook 列 0、資料根留帳 0；同法在現況要抓得到 hook 列與留帳才算探針有效。

## 行動

- （依知識內容判斷）
