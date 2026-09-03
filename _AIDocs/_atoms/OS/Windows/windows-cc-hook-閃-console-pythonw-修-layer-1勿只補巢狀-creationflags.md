# windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 閃 console, console 視窗, 黑窗, 閃窗, pythonw, CREATE_NO_WINDOW, windowsHide, MCP 閃窗, hook 閃窗, WindowsTerminal, 上GIT, git commit 閃窗, subprocess spawn
- Created-at: 2026-06-09

- Related: mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口, cognitive-patterns, feedback-workflow-discipline, cc-能力查證反編譯實跑-binary, feedback-tooling-reliability, feedback-memory-system-doc-sync

## 知識

- [臨] 黑窗真身＝`WindowsTerminal.exe -Embedding` host 窗：無 console 的父行程（claude GUI、GUI pythonw hook）spawn console-subsystem 子行程未帶 `CREATE_NO_WINDOW` 即彈。不只 hook——MCP、worker、git 皆然。
- [臨] bare `pythonw` 可能是 venv console trampoline（subsystem=3）；用前驗 PE subsystem（PE+0x5C，2=GUI），穩定選 `AppData\Local\Python\bin\pythonw.exe`。
- [臨] 修法：hook 解譯器換 GUI pythonw 全路徑；MCP/stdio 子行程包 `hooks/run-hidden.py`；worker spawn 用 GUI pythonw；bash hook 走 `run-bash-hidden.py`；hook 內每一處 `subprocess.run` 必帶 `creationflags=CREATE_NO_WINDOW`。
- [臨] 改 settings.json hook 指令後必端到端真跑一條驗 hookSpecificOutput（曾因丟空格 hooks 全滅 3 天零報錯）。
- [臨] 2026-09-02 定案（修後同場景 trace 零事件實證）：「上GIT/開 session 閃窗」真因＝自家 hook 裸 spawn git/python——主犯 pre_tool_use 隱私閘（每次 git commit）、session_start 未push檢查/followup（每次開 session）、aec_ledger、extract-worker；全補 creationflags 已修。**曾誤寫主因**：「PowerShell 工具生 pwsh 會閃」——閃窗時間與 pwsh 啟動巧合，實為同刻 PreToolUse 閘 spawn git；純 pwsh 不含 git 的 probe 不閃即否證。歸因靠對照實驗/修後驗證，勿靠時間巧合。CC 本體 shell snapshot 漏 windowsHide 的官方 issue 仍在，使用者定案無視。
- [臨] 防回歸：`hooks/verify/verify_no_window_spawn.py`（AST 掃 hooks/lib 全部 subprocess 呼叫，漏帶旗標即 FAIL；豁免註記 `# no-window-exempt:`）。診斷：`tools/console-window-trace.ps1`。完整案卷：`_AIDocs/ClaudeCodeInternals/console-window-forensics.md`。

## 行動

- hook/worker 內任何 subprocess 呼叫一律帶 creationflags=CREATE_NO_WINDOW（或 startupinfo）；verify_no_window_spawn 會把漏帶變 FAIL
- 閃窗歸因先跑 console-window-trace.ps1 直擊＋對照實驗（含/不含嫌疑動作），勿靠時間巧合定罪
- 選 pythonw 前驗 PE subsystem；MCP/stdio 子行程包 run-hidden.py；改 hook 指令後端到端驗一條
