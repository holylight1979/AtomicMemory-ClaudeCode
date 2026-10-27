# TaskStop停背景Bash在Windows只停外殼-腳本與pytest子行程變孤兒繼續跑-要依父行程鏈手動結束

- Scope: global
- Author: holylight
- Source: commit:c107cf94 2026-10-13（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: TaskStop, 背景任務, run_in_background, 停掉背景, 孤兒行程, 子行程還在跑, Stop-Process, Win32_Process, 取消驗證, 快照複跑
- Created-at: 2026-10-12

## 知識

- [臨]（實測 Windows、VS Code 擴充）用 TaskStop 停一個 `run_in_background` 的 Bash 任務（內容是 `bash script.sh > log 2>&1`，腳本裡跑 pytest），回報成功，但只結束了外層殼；`bash.exe script.sh` 與它底下的兩層 python（pytest）都還在跑，繼續佔著那個 worktree 與 CPU。若接著在同一個樹開新的一輪，兩輪會互踩。
- [臨] 確認法：PowerShell `Get-CimInstance Win32_Process` 依 CommandLine 找到 pytest，再看 ParentProcessId 是不是那支腳本的 bash；確定是自己開的才 `Stop-Process -Id <bash>,<python>... -Force`，結束後再查一次數量為 0、樹的 git status 乾淨。
- [臨] 反例觀察：背景任務直接是 `python run_verify.py`（不是 `bash script.sh > log`）時，TaskStop 後整條鏈（3 層 bash、run_verify 兩層 python、pytest 子行程）都已結束，查不到孤兒。差別可能在有沒有中間那支 bash 腳本；不論哪種，停完都用 Win32_Process 依父行程鏈查一次再說「無殘留」。


## 行動

- TaskStop 停掉會跑很久的背景腳本後，立刻用 Win32_Process 查它的 bash 與子行程還在不在，確定是自己的再結束
- 同一個樹要開新一輪前，先確認舊一輪的行程全部結束
