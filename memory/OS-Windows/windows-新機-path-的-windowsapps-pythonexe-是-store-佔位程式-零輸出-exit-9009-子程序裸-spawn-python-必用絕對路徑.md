# Windows 新機 PATH 的 WindowsApps python.exe 是 Store 佔位程式-零輸出 exit 9009-子程序裸 spawn python 必用絕對路徑

- Scope: global
- Confidence: [臨]
- Trigger: Microsoft Store, WindowsApps, python.exe, exit 9009, App Execution Alias, spawn python, 裸 python, Unexpected end of JSON input, WG_PYTHON, resolvePythonExe, 新機安裝, PATH 順位
- Created-at: 2026-09-01
- Related: winget-升不動-powershell-msi-與-msix-通道分裂

## 知識

- [臨] Windows 10/11 出廠 PATH 內有 `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`（App Execution Alias，Microsoft Store 佔位程式）：沒裝 Store 版 Python 時執行它不會報錯，只會零輸出、exit code 9009（互動時跳 Store 頁面）。任何程式裸 spawn `"python"` 在 PATH 順位不利的機器就被它接走，症狀是**子程序 stdout 空、stderr 空**，上層只看到自己的解析錯誤（例：MCP funnel 的 `cli parse fail: Unexpected end of JSON input`），完全沒有線索。
- [臨] 同機 `where python` 的第一順位也未必是預期那支（曾實測第一順位是某工具的 venv python）。結論：跨語言呼叫 Python 一律用**絕對路徑**——Python 內用 `sys.executable`；Node/js 端由單一解析點決定（`tools/workflow-guardian-mcp/lib/paths.js` `resolvePythonExe()`：`WG_PYTHON` 環境變數 → 常見安裝路徑 → 退回裸 `python` 並 stderr WARN）；settings.json hooks 靠 `tools/fix-hook-python.py` 寫死絕對路徑。
- [臨] 排錯法：子程序「零輸出且 exit 9009」= 佔位程式攔走，不是腳本壞；先 `where python` 看順位，再對照呼叫端用的是不是裸名。根治是解析點統一，不是改 PATH 順序（每台機器都要重做）。

## 行動

- Node/js 呼叫 Python 一律經 paths.js PYTHON_EXE，不寫裸 "python"
- 非標準安裝位置：在 ~/.claude.json 的 mcpServers.workflow-guardian.env 設 WG_PYTHON
- 子程序零輸出 + exit 9009 → 先查 where python 順位，勿先懷疑腳本
