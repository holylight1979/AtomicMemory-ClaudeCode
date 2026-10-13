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

## 行動

- 改或寫會 spawn 的程式：腳本路徑和 python -m 的 cwd 都用程式碼根；下一層 spawn 也要查
- 寫誘餌案來驗：在 HOME／資料根放一支同名、一跑就寫標記的腳本，斷言標記沒有出現
- 靜態守門加了規則，先對整棵樹跑一遍，抓到的同類一起修
