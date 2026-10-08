# 導讀卡：排程器（scheduler）

## 它是什麼
`src/sched/` 負責把工作單排進時間槽；入口 `Scheduler.enqueue()`，出口 `Scheduler.drain()`。

## 誰管它
排程只在 `drain()` 裡改狀態；其他模組只能 enqueue，不得直接改 `slots`。

## 以前怎麼摔
- 插播上限用 `len(slots) > cap` 判斷，等號漏掉，第 cap+1 件才擋。
- 歸還工作單時先標完成再寫回，寫回失敗就留下「完成但沒寫」的孤兒。

## 改了怎麼證
`tests/test_sched.py::test_cap_boundary`、`test_return_atomic`。
