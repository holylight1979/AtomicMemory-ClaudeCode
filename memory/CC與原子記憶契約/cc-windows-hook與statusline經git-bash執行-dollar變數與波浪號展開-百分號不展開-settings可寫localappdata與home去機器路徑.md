# cc-windows-hook與statusline經git-bash執行-dollar變數與波浪號展開-百分號不展開-settings可寫LOCALAPPDATA與HOME去機器路徑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: hook 指令, settings.json 路徑, 機器專屬路徑, LOCALAPPDATA, $HOME, pythonw 路徑, statusLine, hook shell, Git Bash, 可攜路徑, fix-hook-python
- Created-at: 2026-10-01
- Source: session:87d79838#ef4d737c 2026-10-01
- Quote: 「我注意到上船的 setting.json 裡面有我電腦的路徑。這是不應該發生的啊.. 不能改成 相對路徑嗎!?!?!」

## 知識

- [臨] 實測（CC 2.1.286，Windows）：settings.json 的 hook 指令由 Git Bash（`$SHELL=/bin/bash.exe`）執行，`$LOCALAPPDATA`、`$HOME`、`~`、`$CLAUDE_PROJECT_DIR` 都會展開，`%VAR%` 不會；`$LOCALAPPDATA` 展開為 `C:\Users\x\AppData\Local`（反斜線），接 `/Python/bin/pythonw.exe` 混用分隔符 bash 照跑。所以 hook 與 statusLine 指令寫 `"$LOCALAPPDATA/Python/bin/pythonw.exe"`＋`"$HOME/.claude/..."` 即可跨機器，不必寫死 `C:/Users/<帳號>/...`。驗法：`claude -p --settings '{"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"echo $LOCALAPPDATA %LOCALAPPDATA% > out.txt"}]}]}}'`。
- [臨] 一律加雙引號：`$VAR` 展開後可能含空白（帳號有空格）。`tools/fix-hook-python.py` 認得 `$VAR` 形式（展開後檢查存在），改寫時落在 LOCALAPPDATA／家目錄下的直譯器也以 `$VAR/…` 寫回。
- [臨] 實測範圍只到 hook（`claude -p --debug` 見 SessionStart hook success）；statusLine 是推定同機制（claude.exe 內 statusLine.command 變更會熱重掃，互動 session 看狀態列有無內容即驗），尚未親眼確認。

## 行動

- 寫 hook／statusLine 指令用 $LOCALAPPDATA／$HOME，不寫絕對機器路徑；在 settings.json 看到 C:/Users/<帳號> 就視為要改
- 不確定某變數會不會展開 → 用臨時 --settings hook echo 到檔實測，不猜
