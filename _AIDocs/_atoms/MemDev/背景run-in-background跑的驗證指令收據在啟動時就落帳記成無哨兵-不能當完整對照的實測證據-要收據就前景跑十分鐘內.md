# 背景run-in-background跑的驗證指令收據在啟動時就落帳記成無哨兵-不能當完整對照的實測證據-要收據就前景跑十分鐘內

- Scope: global
- Author: holylight
- Source: track-c-g0 001 交付信 2026-10-14（claude-45 實踩：lib/verify 559 passed 背景跑、帳上無哨兵）
- Confidence: [臨]
- Trigger: run_in_background, 收據, 無哨兵, need_goal reconcile, measured, 完整對照, 背景驗證, receipt
- Created-at: 2026-10-14
- Quote: 「你是 v6.0 的「調度總控台」（接任），對人總控台是 claude-06（原設計者只跟它講話，你不直接問原設計者）。第一件事：用絕對路徑讀 C:\Users\holylight\.claude\workflow\v6-inbox\_console\調度交接-2026-10-14-b.md 全文，再讀 C:\Users\holylight\.claude\memory\_staging\next…」

## 知識

- [臨] 用 Bash run_in_background 跑的驗證指令，need_goal 的收據在指令啟動那一刻就落帳，那時輸出還沒有哨兵行，所以帳上記「無哨兵 exit None」；跑完後也不會回填。這筆收據拿不到 PYTEST:PASS 一類的 verdict，reconcile 引它當 measured 證據不成立。
- [臨] 要讓驗證成為實測證據：前景跑（十分鐘內），或跑完後在前景 `grep -E 'passed|failed|^exit='` 那份 log 一次取收據（輸出里有哨兵字樣就會被蓋號）。超過十分鐘的驗證改自寫收據（self_receipt.write_self_receipt）。
- [臨]（實遇）使用者把正在前景跑的驗證指令手動轉到背景（工具結果顯示 manually backgrounded by user），效果跟 run_in_background 一樣：收據當下就落帳成「無哨兵 exit None」，跑完也不回填，驗證範圍與完整對照都不認；要收據就在前景重跑一次。

## 行動

- 完整對照要引的驗證前景跑；背景跑完的在前景 grep log 一次取收據再引
