# 工具鏈實戰記憶

- Scope: global
- Author: holylight
- Source: commit:f916780 2026-03-11（原對話已逾保留期）；分支 inject-budget e096049f
- Confidence: [固]
- Trigger: 工具鏈, 環境設定, MCPControl, MCP新增, npm全域, 螢幕截圖, Excel MCP, LanceDB, MSYS2, cp950, PowerShell截圖, 向量服務
- Type: procedural
- Tags: toolchain, environment, commands
- Related: toolchain-ollama, decisions, cc-能力查證反編譯實跑-binary, codex-log-bloat-analytics, guardian-dashboard-孤兒佔埠與新碼重啟, wsl2-0x80070569-gpo鎖診斷繞法vhdx救援移除, bash-呼叫-msbuild-用-dash-參數, windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff, winget-升不動-powershell-msi-與-msix-通道分裂, atom-write-global必須省略project-cwd

## 知識

- [固] Claude Code 的 bash 環境是 MSYS2，路徑格式 `/c/Users/` 而非 `C:\Users\`
- [觀] MSYS 只轉命令列參數裡的 `/c/`（`python x.py /c/Users` 收到 `C:/Users`）；寫在 `python -c` 字串或檔案內容裡的不轉，Python 報 FileNotFoundError——給 Python 的路徑一律寫 `C:/`
- [固] Windows 上 bash 指令的 `/dev/null` 有效（MSYS2 模擬），不需改成 `NUL`
- [觀] 長指令限時用 `timeout N cmd`：bash 有 `/usr/bin/timeout`，正常結束照傳退出碼、逾時回 124；Python 內部用 subprocess 的 timeout
- [固] Windows 環境變數用 `$env:VAR`（PowerShell）或 `$VAR`（bash），混用易出錯
- [固] Ollama 啟動: `ollama serve`（背景）→ `ollama list`（驗證模型可用）；models 預設在 `~/.ollama/models/`；雙後端詳見 `toolchain-ollama.md`
- [固] 向量服務啟動: `python ~/.claude/tools/memory-vector-service/service.py`（port 3849），健康檢查 `curl http://127.0.0.1:3849/health`；LanceDB 資料在 `~/.claude/memory/_vectordb/`（ChromaDB 已棄用：i7-3770 不支援 AVX2）
- [固] 記憶格式檢查: `python ~/.claude/tools/memory-audit.py`
- [固] MCPControl（computer-use-mcp）：`npm i -g computer-use-mcp`，目前版本 1.7.1；工具 `mcp__MCPControl__computer`（action: get_screenshot / left_click / type / key 等）
- [固] MCPControl **跨專案可用**：螢幕截圖、滑鼠點擊/拖曳、鍵盤輸入、捲動，任何 session 都能操控任意桌面 App（Unity Editor、瀏覽器），做 UI 驗證、截圖比對、GUI 自動化、幫使用者確認視覺結果
- [固] **使用者明確要求**：需要看畫面時優先用 MCPControl，不要說「看不到」。未連線就 PowerShell 截圖：`Add-Type System.Windows.Forms + System.Drawing` → `Bitmap` → `Graphics.CopyFromScreen` → `.Save()` 存 PNG → Read tool 讀取；`Bitmap.Clone(Rectangle)` 可裁切
- [固] Excel MCP：`npm i -g @negokaz/excel-mcp-server`，目前版本 0.12.0；describe_sheets / read_sheet / write_to_sheet / create_table / format_range / screen_capture；`~/.claude.json` User scope 跨專案可用
- [固] Excel MCP 支援 xlsx/xlsm/xltx/xltm；**不支援舊版 .xls**（舊版用 `tools/read-excel.py` + xlrd）
- [固] **全域 MCP 設定在 `~/.claude.json` 的 `mcpServers`** → 所有專案顯示為 "User" scope；`~/.claude/.mcp.json` 是專案層，只在 `~/.claude` 作為工作目錄時生效，其他專案看不到
- [固] **新增 MCP 一律全域安裝 + 絕對路徑**：`npm i -g {pkg}` → 用 `node.exe` + 絕對路徑指向 `AppData/Roaming/npm/node_modules/{pkg}/dist/{entry}.js`；入口查 `package.json` 的 `bin` 欄位
- [固] **禁用 npx 啟動**：`cmd /c npx` 在 VSCode 擴充環境不穩定，MCP server 會無法啟動
- [固] MCP 範本：`"command": "C:\\Program Files\\nodejs\\node.exe", "args": ["C:\\Users\\holylight\\AppData\\Roaming\\npm\\node_modules\\{pkg}\\dist\\{entry}.js"]`
- [固] workflow-guardian.py stdout/stderr 強制 UTF-8（Windows 預設 cp950 會導致中文亂碼）

## 行動

- build/setup/config intent 時自動載入
- 成功執行新工具指令後，評估是否值得記錄（跨 session 重用性 ≥ 2 次預期）
- 環境問題 debug 時，優先查此 atom 再嘗試盲目探索
- 版本資訊在確認後更新，不猜測
