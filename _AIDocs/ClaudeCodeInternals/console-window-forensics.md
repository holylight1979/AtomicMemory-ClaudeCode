# Console 黑窗（閃窗）Forensics — 完整案卷

> 結論與行動守則見 atom `windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags`；本檔存完整技術細節與歷次實測。

## 機制

- 黑窗真身＝`WindowsTerminal.exe -Embedding`（Win11「預設終端機=Windows Terminal」的 console host 視窗）。`claude.exe`（GUI、無 console）spawn 任何 **console-subsystem** 子行程（node/cmd/uvx/python.exe/含某些 pythonw）且未帶 `CREATE_NO_WINDOW` → Windows 替它彈一個 host 窗，標題＝被托管 exe 的 image 路徑。不只 hook——MCP server、worker subprocess、shell 皆然。
- **bare `pythonw` 不一定是 GUI**：uv venv 的 `Scripts\pythonw.exe` PE subsystem＝3(Console)，是 trampoline、會 re-exec 成 console `python.exe`。用前驗 PE subsystem（DOS@0x3C 取 PE 偏移；`Subsystem` 在 PE+0x5C；2=GUI 永不配 console、3=Console）。本機穩定 GUI pythonw＝`C:\Users\holylight\AppData\Local\Python\bin\pythonw.exe`（uv default-shim、路徑無版本號）。

## 修法三式（已上線）

1. **hook 解譯器**：settings.json 全 hook 用 GUI pythonw 完整路徑。GUI pythonw 在 claude 重導向下 `sys.stdin/stdout` 仍可用（hook JSON 收發正常）。
2. **MCP / stdio console 子行程**：包 `hooks/run-hidden.py`——pythonw 下 `sys.std*`＝None、裸繼承不會把 MCP pipe 接力給子行程（實測雙向斷、node EPIPE），故用 ctypes `GetStdHandle` → `STARTUPINFO` + `STARTF_USESTDHANDLES` 直傳 + `CREATE_NO_WINDOW`。套法 `claude mcp add NAME -s user -- <GUI-pythonw> run-hidden.py node <server.js>`；驗證＝`claude mcp list` 全 Connected + trace 零彈窗。
3. **layer-2 worker spawn**：`CREATE_NO_WINDOW|DETACHED_PROCESS` 在 console 子行程不保證壓窗；改用 GUI pythonw spawn（subsystem=2 永不配窗）。`wg_extraction._spawn_extract_worker` 已改 `_gui_python()`。
4. **bash hook**：`bash.exe` 無 GUI 變體 → `hooks/run-bash-hidden.py`（GUI pythonw 啟動器、python 中介 pipe I/O 餵 bash `CREATE_NO_WINDOW`；MSYS bash 讀不了繼承的原生 pipe，故須 python proxy，與 node 可直接吃 handle 不同）。

## 驗證鐵律

- 改 settings.json hook 指令後：擷取實際 command 字串、餵 hook 格式 stdin 端到端真跑一條、看到 hookSpecificOutput 才算驗證。曾因全路徑轉換丟失空格 → 18 條 hook 靜默死亡 3 天（hook 崩潰=結果被忽略、零報錯）；事後偵測信號＝workflow/state-*.json 與 Logs/atom-debug-* 的 mtime 斷流。

## 診斷工具

- `tools/console-window-trace.ps1`：列舉 console-class 視窗、抓「新建 ∨ 隱藏→可見」翻轉＋完整父鏈，記 `Logs/console-window-trace.log`。
- 視窗標題＝執行檔路徑 → 認 layer/來源（python.exe→解譯器；node/cmd/uvx→MCP；git/svn→巢狀）。
- WT host 窗的 owner＝WindowsTerminal 本身（被托管行程經 ConPTY 連、非父子）→ 認來源靠「時間相關 + 新生 console 行程命令列」。

## 2026-09-02 實測：殘餘閃窗源判定

環境：VSCode extension session。方法：console-window-trace 三輪 + 對照實驗（trace log 同日段落）。

| 操作 | 結果 |
|------|------|
| 工具指令**含 `git commit`** 的呼叫（PreToolUse 隱私閘裸 spawn git） | ★ 閃（WT -Embedding NEW-WINDOW 11:10:39；HIDDEN→VISIBLE 11:11:53——兩次閃窗的呼叫指令皆含 git commit） |
| 純 pwsh probe（指令不含 git） | 零事件（否證「pwsh 生成閃窗」說） |
| 既有 shell 內跑 `git status` / console `python -c` / `git commit` 的 pre-commit 子行程 | 零事件（子行程附掛父 console） |
| hooks（GUI pythonw）/ MCP（run-hidden）/ statusline（10s refresh 涵蓋於 idle 觀察窗） | 零事件＝先前修復仍有效 |

**定案（修復後同場景 trace 零事件實證）**：閃窗真因＝**自家 hook（GUI pythonw、無 console）裸 spawn console git/python**，漏帶 `CREATE_NO_WINDOW`：

- `hooks/handlers/pre_tool_use.py` 隱私硬閘 `_git_lines`——**每次 git commit 必閃**（＝「上GIT 閃」主犯）
- `hooks/handlers/session_start.py` 未push檢查（git rev-list）＋ followup 檢查（console python）——**每次開 session 跑**（開場閃的自家成分）
- `hooks/handlers/aec_ledger.py` vcs_tracked、`hooks/extract-worker.py` catalog sync——同類
- 以上全數補 `creationflags=CREATE_NO_WINDOW` 修畢；防回歸掃描 `hooks/verify/verify_no_window_spawn.py`（AST 掃 hooks/lib 全部 subprocess 呼叫，漏帶即 FAIL，豁免註記 `# no-window-exempt:`）

**更正記事**：同日稍早曾誤判主因為「PowerShell 工具生成 pwsh 實例」——兩次閃窗時間與 pwsh 啟動巧合，實為同一時刻 PreToolUse 隱私閘 spawn git；「純 pwsh 不含 git 的 probe 不閃」即已否證，據此建的「版控走 Bash tool」core atom 已刪除。教訓：歸因勿靠時間巧合，要靠對照實驗（含/不含嫌疑動作）＋修復後驗證。

## 外部佐證（anthropics/claude-code 官方 issue，2026-05～06）

上述判定與官方 repo 多條 issue 的分析一致，皆指向 claude 本體 `child_process.spawn()` 缺 `windowsHide: true`／`CREATE_NO_WINDOW`：

- [#64163](https://github.com/anthropics/claude-code/issues/64163)（2026-05-31，closed as duplicate）：根因點名 **shell snapshot 建立**（session 啟動時跑 `bash --login -i -c "declare -p; declare -f; …"`）與 hook executor 路徑缺 windowsHide；並指出 **Bash 工具主路徑已帶 windowsHide:true**——正好解釋本機實測「Bash 呼叫不閃、shell 生成才閃」。
- [#58606](https://github.com/anthropics/claude-code/issues/58606)（2026-05-13，open/stale）：Bash/PowerShell 工具呼叫閃 conhost，建議補 `CREATE_NO_WINDOW`，無官方回應。
- [#66540](https://github.com/anthropics/claude-code/issues/66540)（2026-06-09，open/duplicate）：每個 subprocess spawn（MCP stdio、subagent、工具）皆閃；多 session 併發時每分鐘數十次。
- 另有 #58773（`claude --print` 子行程彈窗）、#51867（statusline/hook spawn bash 無 hide）、#15572/#16880/#28138/#61051 等同族 issue。

狀態：截至 2026-06 皆未修（open/stale/closed-as-duplicate，無官方修復版本公告）。這些 issue 描述的是 **CC 本體**的漏帶（shell snapshot、部分工具路徑）——與本機「自家 hook 漏帶」是同機制、不同肇事者；本機自家部分已全修＋掃描防回歸，CC 本體殘餘（如開場 snapshot）使用者定案無視、等官方。
