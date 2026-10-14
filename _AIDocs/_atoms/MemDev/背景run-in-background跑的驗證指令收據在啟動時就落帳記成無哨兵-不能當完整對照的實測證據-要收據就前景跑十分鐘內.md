# 背景run-in-background跑的驗證指令收據在啟動時就落帳記成無哨兵-不能當完整對照的實測證據-要收據就前景跑十分鐘內

- Scope: global
- Author: holylight
- Source: track-c-g0 001 交付信 2026-10-14（claude-45 實踩：lib/verify 559 passed 背景跑、帳上無哨兵）
- Confidence: [臨]
- Trigger: run_in_background, 收據, 無哨兵, need_goal reconcile, measured, 完整對照, 背景驗證, receipt
- Created-at: 2026-10-14

## 知識

- [臨] 用 Bash run_in_background 跑的驗證指令，need_goal 的收據在指令啟動那一刻就落帳，那時輸出還沒有哨兵行，所以帳上記「無哨兵 exit None」；跑完後也不會回填。这筆收據拿不到 PYTEST:PASS 一類的 verdict，reconcile 引它当 measured 證據不成立。
- [臨] 要讓驗證成為実測證據：前景跑（十分鐘內），或跑完後在前景 `grep -E 'passed|failed|^exit='` 那份 log 一次取收據（輸出里有哨兵字樣就會被蓋號）。超過十分鐘的驗證改自寫收據（self_receipt.write_self_receipt）。

## 行動

- 完整對照要引的驗證前景跑；背景跑完的在前景 grep log 一次取收據再引
