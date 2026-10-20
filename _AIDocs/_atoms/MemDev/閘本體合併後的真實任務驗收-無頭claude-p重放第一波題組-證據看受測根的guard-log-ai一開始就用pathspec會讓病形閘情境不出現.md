# 閘本體合併後的真實任務驗收-無頭claude-p重放第一波題組-證據看受測根的guard-log-AI一開始就用pathspec會讓病形閘情境不出現

- Scope: global
- Author: holylight
- Source: session cb4c9c8e 2026-10-20 總控台 claude-e3（根治四軌合併後無頭重跑題 A／B／C）
- Confidence: [臨]
- Trigger: 無頭驗收, claude -p, 真實任務實跑, 根治驗收, 合併後驗收, wave1-kit, run_headless, 受測根, guard log 證據, --resume, 閘沒被逼出來, pathspec 排除
- Created-at: 2026-10-20

## 知識

- [臨] 閘本體合進 main 後「在真實任務裡動不動」的驗法：用 VS Code 擴充那支 claude.exe 無頭 `-p <題組第一句> --permission-mode bypassPermissions --output-format json`，cwd 指受測專案、環境 WG_CLAUDE_DIR／WG_TEST_LOGS_DIR 指乾淨受測根；後續句用 `--resume <session_id>`（json 裡的 session_id）。證據不看 AI 的收尾文字，看受測根 Logs/guard-<閘>.jsonl 有沒有 denied／declared，與 projects/<cwd-slug>/<sid>.jsonl 裡的工具呼叫序列。腳本正本 workflow/inbox/_console/root-fix-run/run_headless.py.txt；受測環境用 wave1-kit 的 w1_build_env.py --dest 另建一份，不重用跨過的。
- [臨] 同一題重跑，AI 的路徑會變：第一波題 A 它整個暫存區 commit 被病形閘擋；重跑時它一開始就用 pathspec 只提自己的檔，別人的髒檔從沒進 commit 範圍，病形閘與繞閘閘都沒有情境可觸發。要驗「被擋之後」的閘，得用 --resume 補一句把那個檔逼進 commit（「把 X 也一起 commit 進去」），再看序列；否則「沒被擋」不等於「閘有效」。重跑也會挖出回歸（本次：第一波被擋的 retry.py 重跑時病形閘回「沒有病形」、--amend 進了版）。

## 行動

- 合閘本類分支後：建乾淨受測環境 → 無頭重放題組 → 看受測根 guard log 與 transcript 序列 → 看到閘動了才推
- 閘沒被觸發時先問「情境有沒有出現」，沒出現就用 --resume 逼出來，不當成通過
