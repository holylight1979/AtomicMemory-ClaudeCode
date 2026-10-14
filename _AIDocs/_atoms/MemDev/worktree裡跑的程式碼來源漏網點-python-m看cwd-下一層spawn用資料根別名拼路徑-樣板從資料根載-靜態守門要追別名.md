# worktree裡跑的程式碼來源漏網點-python-m看cwd-下一層spawn用資料根別名拼路徑-樣板從資料根載-靜態守門要追別名

- Scope: global
- Author: holylight
- Source: session df3c2d29（v6 退件 017／020）
- Confidence: [臨]
- Trigger: worktree, 程式碼根, 資料根, CODE_DIR, CLAUDE_DIR, WG_CLAUDE_DIR, spawn cwd, python -m, 載到 live, code root 守門, 資料根別名
- Created-at: 2026-10-13
- Related: 工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上

## 知識

- [臨] 原則：程式碼的位置一律從檔案本身推（Python 的 Path(__file__)、JS 的 __dirname），資料一律走 lib/project_root.claude_data_dir()。在 worktree 裡跑時，要做到「程式碼是 worktree 的、資料是真的」。
- [臨] MCP（node）spawn `python -m lib.x` 時，cwd 決定載到哪一份 lib：-m 和 -c 會把 cwd 放在 sys.path 第一位、排在 PYTHONPATH 前面，所以 cwd 要設成程式碼根。
- [臨] 下一層 spawn 也會漏：工具用 `memory_dir.parent` 這類資料根別名拼出另一支腳本的路徑，結果跑到家目錄那份舊版，而且沒有任何訊號。
- [臨] LLM 判斷用的樣板（prompts/）如果從資料根載入，在 worktree 改的樣板不會生效。shell hook 寫死 ${HOME}/.claude/tools 也一樣：要先用 readlink -f 找到腳本自己所在那棵樹的 tools/，找不到才退回家目錄，解析失敗要寫 stderr。
- [臨] 靜態守門只認字面名字會漏，要追資料根的別名：memory_dir.parent、HOME=Path.home() 再接 .claude、外面包 Path()／resolve()、條件式、import as。同一個名字的值同時來自 __file__ 和資料根時，保守當成資料根。CLAUDE_DIR／MEMORY_DIR 是命名約定：就算是從 __file__ 推出來的也照資料根看待，逼它改名成 CODE_DIR。
- [臨] 資料根不吃 WG_CLAUDE_DIR 是另一個問題（A2c）：lib/atom_locations、atom_taxonomy、realm_gate、MCP paths.js 要同一批改，常數名不動。盤點全文是 v6-inbox 裡的 A2c 盤點交付信（025）。
- [臨] 現況（A2c 合進 main 後，取代上面「資料根不吃 WG_CLAUDE_DIR 是另一個問題」那句）：資料根一律走 claude_data_dir()：lib（project_root、atom_locations、atom_taxonomy、realm_gate）、wg_core 的 Logs、MCP paths.js、約 30 支 tools 都已對齊，常數名沒變。刻意留在家目錄的只有 CC 自己的目錄（plugins、shell-snapshots、debug）、~/.claude.json、找執行檔、~/.codex；version.json 看程式碼根。
- [臨] 刻意放在資料根、但路徑段剛好含 tools/ 的（例：usage-snapshot 的 Chrome 登入 profile `CLAUDE_DIR / "tools" / "usage-snapshot" / "browser-data"`），會被 hooks/verify/verify_code_paths_from_code_root.py 判成「資料根接程式碼」。要進它的 ALLOWLIST 附理由，鍵是那一整行去頭尾空白的原文（含行尾註解），改註解就要同步改鍵。改路徑常數的工作 session，交付前要把這支守門放進目標 verify：它在 live 補驗的標準清單裡，派工單沒列也要跑。
- [臨] 実踩：worktree 裡用 scratchpad 腳本直接 import lib.atom_io 做実測、沒設 WG_CLAUDE_DIR，write_raw 的稽核記錄落到 live `~/.claude/memory/_meta/atom_io_audit.jsonl`（多一行 test 記錄）。驗證腳本 import 會寫檔的 lib 前，先把 WG_CLAUDE_DIR 指到暫存。

## 行動

- 改或寫會 spawn 的程式：腳本路徑和 python -m 的 cwd 都用程式碼根；下一層 spawn 也要查
- 寫誘餌案來驗：在 HOME／資料根放一支同名、一跑就寫標記的腳本，斷言標記沒有出現
- 靜態守門加了規則，先對整棵樹跑一遍，抓到的同類一起修
