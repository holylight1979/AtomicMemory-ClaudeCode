# windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 閃 console, console 視窗, hook 閃窗, MCP 閃窗, 黑窗, pythonw, venv pythonw, CREATE_NO_WINDOW, Windows hook, settings.json hook, GUI subsystem, subsystem, 視窗標題, WindowsTerminal, Embedding, console host, run-hidden, GetStdHandle, STARTUPINFO, MCP server 閃窗
- Created-at: 2026-06-09
- Related: feedback-memory-system-doc-sync, cc-能力查證反編譯實跑-binary, cognitive-patterns, feedback-tooling-reliability

## 知識

- [臨] **黑窗真身＝`WindowsTerminal.exe -Embedding`（Win11『預設終端機=Windows Terminal』的 console host 視窗）。** `claude.exe`（GUI、無 console）spawn 任何 **console-subsystem** 子行程（node/cmd/uvx/python.exe/**含某些 pythonw**）且未帶 `CREATE_NO_WINDOW` → Windows 替它彈一個 host 窗，標題＝被托管 exe 的 image 路徑（故看到 `C:\Users\…\AppData\Local\…python.exe`）。**不只 hook——MCP server、worker subprocess 亦然**；與 hook 機制無關，所以光改 hook 永遠改不掉。
- [臨] **致命坑（推翻舊認知）：bare `pythonw` 不一定是 GUI。** 本機 `pythonw` 經 PATH 命中 **hermes uv-venv 的 `Scripts\pythonw.exe`，其 PE subsystem＝3(Console)**——uv venv 的 pythonw 是 trampoline，會 re-exec 成 base `python.exe`（console）→ 早年「`python -c`→`pythonw -c`」的 layer-1『真修』被它沖掉、照閃。**鐵律：用前驗 PE subsystem**（讀 bytes：DOS@0x3C 取 PE 偏移；`Subsystem` 在 PE+0x5C；**2=GUI 永不配 console、3=Console**）。只認 subsystem=2 的 pythonw。
- [臨] **真修 A（hook 解譯器）：settings.json 全 hook 的 bare `pythonw` → 真 GUI pythonw 完整路徑。** 本機穩定選擇＝uv default-shim `C:\Users\holylight\AppData\Local\Python\bin\pythonw.exe`（subsystem=2、**路徑無版本號** → uv 升級 python 版本不破；反之 venv 與 `…\cpython-3.11.x-…` 路徑會易變）。實證：GUI pythonw 在 claude 重導向下 `sys.stdin/stdout` **仍可用**（hook JSON 收發正常）、可 import 全部 hook 模組（純 stdlib+local、無 venv 套件依賴）→ 換置安全。settings 改動下個 session 生效。
- [臨] **真修 B（MCP server／任何 claude-spawn 的 stdio console 子行程）：包 `hooks/run-hidden.py`。** 形式 `<GUI-pythonw> run-hidden.py <真 exe> <args>`。**坑**：pythonw 下 `sys.std*`＝None、**裸繼承不會把 claude 的 MCP pipe 接力給子行程**（實測 stdin/stdout 雙向皆斷、node EPIPE）。故 run-hidden 用 **ctypes `GetStdHandle` 取 OS 標準handle → `subprocess.STARTUPINFO` + `STARTF_USESTDHANDLES` 直接交給子行程 ＋ `CREATE_NO_WINDOW`**（真透傳、免 byte-pump）。套法 `claude mcp add NAME -s user [-e K=V] -- <GUI-pythonw> run-hidden.py node <server.js>`；驗證＝`claude mcp list` 全 √Connected ＋ trace 零彈窗。
- [臨] **真修 C（layer-2 worker spawn）**：hook 內 `subprocess.Popen([sys.executable,…], creationflags=CREATE_NO_WINDOW|DETACHED_PROCESS)` 仍會閃——`sys.executable` 在 venv trampoline 下＝console `python.exe`，且 `CREATE_NO_WINDOW|DETACHED_PROCESS` 組合在 console 子行程**不保證**壓窗。改用 GUI pythonw spawn（subsystem=2 永不配窗、flags 變 moot）。`wg_extraction._spawn_extract_worker` 已改 `_gui_python()`（回穩定 GUI pythonw，找不到退回 sys.executable）。其餘 spawner（codex/ensure-mcp/wg_atoms/wg_docdrift）已帶 `CREATE_NO_WINDOW` 且 trace 未見閃，暫不動。
- [臨] **診斷鐵律 + 工具**：先看**視窗標題＝執行檔路徑**認 layer/來源（python.exe→解譯器；node/cmd/uvx→MCP；git/svn→巢狀）。`tools/console-window-trace.ps1`：列舉全機 console-class 視窗、抓『新建 ∨ 隱藏→可見』翻轉＋完整父鏈，記 `Logs/console-window-trace.log`（抓 transient 黑窗）。`Get-CimInstance Win32_Process` 比對 `ParentProcessId` 追鏈、抓 console-subsystem 新生行程命令列。**WT host 窗的 owner＝WindowsTerminal 本身**（被托管行程經 ConPTY 連、非父子）→ 認來源靠『時間相關 + 新生 console 行程命令列』，非視窗 owner。
- [臨] **bash hook**：`bash.exe` 是 console-subsystem 且無 `bashw` 變體 → 用 `hooks/run-bash-hidden.py`（GUI pythonw 跑啟動器→ python 全中介 pipe I/O 餵 `usr\bin\bash.exe` `CREATE_NO_WINDOW`；MSYS bash 讀不了繼承的原生 pipe 故須 python proxy，與 node 可直接吃 handle 不同）。SessionStart/WebFetch 兩 bash hook 適用。
- [臨] **續集事故（2026-06-09→12，hooks 全滅 3 天）**：黑窗根治 v2 把 settings.json 18 條 hook 指令轉全路徑時**丟失執行檔與參數間的空格**（`pythonw.exe-c`/`pythonw.exe"$HOME`），cmd/bash 都找不到執行檔 → 全部 hook 靜默死亡（hook 崩潰=結果被忽略、工具照常跑，零報錯）。當時驗證只驗「JSON 合法 18/18 轉換」沒驗指令能跑。**鐵律：改 settings.json hook 指令後，必須擷取實際 command 字串、餵 hook 格式 stdin 端到端真跑一條，看到 hookSpecificOutput 才算驗證**；事後偵測信號=workflow/state-*.json 與 Logs/atom-debug-* 的 mtime 斷流。

## 行動

- Windows hook/MCP 閃黑窗：先用 console-window-trace.ps1 認標題/layer/來源，勿假設是 hook
- 選 pythonw 前**驗 PE subsystem（PE+0x5C：2=GUI）**——bare pythonw 可能是 venv console trampoline；用真 GUI pythonw 完整路徑（穩定選 AppData\Local\Python\bin\pythonw.exe）
- MCP server／stdio console 子行程閃窗 → 包 run-hidden.py（GUI pythonw + ctypes GetStdHandle/STARTUPINFO 直傳 + CREATE_NO_WINDOW）；裸繼承在 pythonw 下會斷 stdio
- 改 hook 解譯器/worker spawn 後驗證：subsystem=2 + GUI pythonw 重導向 stdio 通 + import 全模組 OK + claude mcp list 全 Connected + trace 零彈窗
