# shell=True子行程帶CREATE_NO_WINDOW輸出整個不見-要直接印給人看的指令用no-window-exempt-壓窗守門紅了別一律補旗標

- Scope: global
- Author: holylight
- Source: session:57afce55 2026-10-21
- Confidence: [臨]
- Trigger: CREATE_NO_WINDOW, shell=True, no-window-exempt, 子行程輸出不見, 壓窗旗標, verify_no_window_spawn, creationflags, 閃窗, subprocess.run 輸出不見, 子行程沒有主控台, 重跑仍紅
- Created-at: 2026-10-21
- Related: 字面掃描型守門看不到常數未定義-壓窗守門只查有無creationflags字樣-補錯的常數名也pass-要配一個真的斷言旗標值的案例

## 知識

- [臨]（實測 Windows、Python 3.14）`subprocess.run(cmd, shell=True)` 不接管 stdout 時，子行程輸出照樣印到呼叫端；同一行加 `creationflags=CREATE_NO_WINDOW` 後輸出整個不見（cmd.exe 沒有主控台，它叫起的程式拿不到繼承的輸出）。明傳 `stdout=sys.stdout, stderr=sys.stderr` 才會回來，但 sys.stdout 被換掉（pytest 擷取）時沒有 fileno 會炸。
- [臨] 所以壓窗守門（掃 subprocess 有沒有帶旗標）紅了不要一律補旗標：先問這個子行程的輸出是不是要直接給跑工具的人看（例：工具的 --run 抽樣指令、互動 CLI）。是就在那一行上方寫 `# no-window-exempt: <理由>`，不改行為；只有被 hook、排程、MCP 這類沒主控台的行程叫起、輸出又不必給人看的才補旗標。
- [臨] 補完要有一個真的跑子行程、斷言輸出還在的案例；只靠掃描守門轉綠驗不到輸出不見（同類：字面掃描只看有沒有 creationflags 字樣）。測試自己用壓窗旗標啟動被測工具時，工具底下的 shell 子行程輸出一樣會不見，案例不要帶旗標。
- [臨]（實測，Bash 工具裡跑）不只 shell=True：worktree 的版控啟動器用 `subprocess.run(["git", ...], creationflags=CREATE_NO_WINDOW)` 直接跑 git.exe、不接 stdout，`status`／`diff` 在工具輸出裡一樣是空的，看起來像沒改動、diff 0 行。啟動器要 `capture_output=True` 再把 stdout／stderr 原樣寫回自己的 sys.stdout.buffer／sys.stderr.buffer，壓窗旗標照帶。
- [臨] 別的案例因補了旗標而紅：第一次紅就查機制（輸出被旗標吃掉），別靠重跑確認；重跑兩次才回頭查是踩過的。

## 行動

- 壓窗守門點名 shell=True 的呼叫：先判輸出要不要給人看，要就加 no-window-exempt 註記不改行為
- 改完跑一次真的子行程，斷言輸出與 exit code
