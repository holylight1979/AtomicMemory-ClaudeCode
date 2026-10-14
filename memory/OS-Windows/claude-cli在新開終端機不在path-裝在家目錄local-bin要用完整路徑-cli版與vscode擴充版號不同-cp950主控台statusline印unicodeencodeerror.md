# claude-cli在新開終端機不在path-裝在家目錄local-bin要用完整路徑-cli版與vscode擴充版號不同-cp950主控台statusline印unicodeencodeerror

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: claude 不是內部或外部命令, 無法將 claude 字詞辨識, 終端機開 claude, CLI 版 claude, statusline UnicodeEncodeError, claude.exe 在哪, 另開工作目錄跑 claude
- Created-at: 2026-10-14
- Source: session:242d1f2a#2403ee73 2026-10-14
- Quote: 「B5 q1 開了」

## 知識

- [臨] 這台機新開的 PowerShell 找不到 claude（PATH 只有 AppData\Roaming\npm，裡面沒有 claude）。CLI 本體在 `%USERPROFILE%\.local\bin\claude.exe`，用 `& "$HOME\.local\bin\claude.exe"` 啟動。要在指定專案與資料根開 session：`$env:WG_CLAUDE_DIR='<資料根>'; cd <專案>; & "$HOME\.local\bin\claude.exe"`（cmd.exe 不吃這語法）。CLI 版號（2.1.252）與 VS Code 擴充內建的 claude.exe（2.1.296）不同步，兩者共用同一套 ~/.claude hooks 與 MCP。CLI 在 cp950 主控台跑時 statusline 印 UnicodeEncodeError（狀態列腳本印中文，純顯示問題，不影響 hooks）。

## 行動

- 終端機跑 claude 用 $HOME\.local\bin\claude.exe 完整路徑，用 PowerShell 不用 cmd
- statusline 腳本要防 cp950：輸出前 reconfigure stdout utf-8 或 errors=replace
