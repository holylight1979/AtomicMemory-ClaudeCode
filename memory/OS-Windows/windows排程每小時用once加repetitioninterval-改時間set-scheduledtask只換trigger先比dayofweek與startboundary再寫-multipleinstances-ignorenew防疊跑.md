# windows排程每小時用once加repetitioninterval-改時間set-scheduledtask只換trigger先比dayofweek與startboundary再寫-multipleinstances-ignorenew防疊跑

- Scope: global
- Author: holylight
- Source: GitLab ClaudeCode-AtomMemory !13 usage_snapshot.align_schedule、!14 usage-watch.schedule（作者 prog_katana_batch，合併 68cd06d9／d09f9640）
- Confidence: [臨]
- Trigger: Task Scheduler, 排程, ScheduledTask, New-ScheduledTaskTrigger, Set-ScheduledTask, RepetitionInterval, 每小時, MultipleInstances, StartBoundary, DaysOfWeek, pythonw 排程, Register-ScheduledTask
- Created-at: 2026-11-03
- Quote: 「收割，我希望是從他們推的MR中，汲取此電腦所用LLM所欠缺的知識、經驗」

## 知識

- [臨] PowerShell 建「每小時一次」的排程沒有 -Hourly：用 `New-ScheduledTaskTrigger -Once -At <下個整點過 5 分> -RepetitionInterval (New-TimeSpan -Hours 1)`；每天固定時間用 `-Daily -At HH:MM`，指定星期用 `-Weekly -DaysOfWeek Monday,Wednesday -At HH:MM`。
- [臨] 只要改既有排程的觸發時間，`Set-ScheduledTask -TaskName X -Trigger $new` 只換 trigger、Action／Settings 不動，不必 Unregister 重建。寫之前先讀 `(Get-ScheduledTask X).Triggers[0]`，比 `DaysOfWeek` 與 `([datetime]$cur.StartBoundary).ToString('HH:mm')`，一樣就回 same 不寫，避免每次跑都動排程。
- [臨] 腳本自己可能跑超過排程間隔時，Settings 加 `-MultipleInstances IgnoreNew`（上一輪沒跑完就跳過這輪）和 `-ExecutionTimeLimit`；靜默跑用 `pythonw.exe` 當 Action，腳本裡 sys.stdout／stderr 會是 None，要先導到 devnull。
- [臨] 腳本回報排程狀態：Get-ScheduledTask 查不到回 'none'、沒變回 'same'、改了回 'moved'，三種字串以外或 returncode≠0 就當失敗印 stderr——排程器的錯不能靜默。

## 行動

- 建每小時排程：-Once ＋ -RepetitionInterval 1h，起點取下個整點過幾分
- 改排程時間：先比現有 trigger，一樣不寫；不同用 Set-ScheduledTask -Trigger 只換 trigger
- pythonw 跑的腳本開頭先把 None 的 stdout／stderr 導 devnull
