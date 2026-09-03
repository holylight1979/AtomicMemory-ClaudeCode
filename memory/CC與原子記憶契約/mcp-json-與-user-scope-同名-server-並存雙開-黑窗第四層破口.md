# mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: mcp.json, MCP 雙開, MCP 行程重複, scope 優先序, user scope, project scope, 黑窗, 閃 console, claude mcp add
- Created-at: 2026-08-10
- Related: windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags

## 知識

- [臨] **`.mcp.json`（project scope）與 `~/.claude.json`（user scope）的同名 MCP server 是「並存雙開」，不是覆蓋。** 實測 4 個 server 各跑兩份行程：parent=pythonw.exe（user scope、經 run-hidden.py 包裹、無窗）另 parent=claude.exe（`.mcp.json` 裸 node.exe、console subsystem 且無 CREATE_NO_WINDOW → 彈 WindowsTerminal host 窗）。
- [臨] 這是黑窗的**第四層破口**：[[windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags]] 的真修 B 只套到 user scope，舊的 project 層定義會把窗帶回來；且只在 cwd 落在該 project 時發作 → 使用者感受是「時有時無」，容易誤判為已修好。
- [臨] **診斷一招**（比目視抓窗快）：`Get-CimInstance Win32_Process -Filter "Name='node.exe'"` 列行程 + 查 ParentProcessId——parent=claude.exe 即裸跑未包裹（會閃窗），parent=pythonw.exe 即已包裹；同名 server 出現兩筆即雙開。
- [臨] `hooks/ensure-mcp.py` 只維護 `~/.claude.json`，**從不碰 `.mcp.json`** → 刪 `.mcp.json` 不會被自動重建；user scope 才是設計上的正本。

## 行動

- 黑窗排查先跑 Win32_Process 查 node.exe 的 parent，parent=claude.exe 即是裸跑來源
- 新增 MCP 一律 `claude mcp add -s user`，不寫專案層 .mcp.json
