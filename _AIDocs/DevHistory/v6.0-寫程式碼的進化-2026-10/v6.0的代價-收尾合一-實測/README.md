# 收尾三段合一 量測證據

- closing_merge_replay.py：只讀 004 實跑帳（`workflow/inbox/wave2-kit/results/2026-10-23-CCon-*`），第一回合收尾段的事件帳重播：砍前＝收尾類工具呼叫次數；砍後＝合一走法（收尾檢核一次帶 reconcile、harvest_items）照該跑實際載入工具的時點（嚴格）與照新提示提早載入兩種；省的重讀量＝被拿掉那幾次呼叫的輸入 T，省的秒＝那幾次呼叫的送出到回完。
- replay-R1R2.md：主樣本 R1、R2 的輸出；replay-cross.md：同日交叉樣本 CCon-1～3 的輸出。
- 重播不是 hook 輸出重播：被合併的那段回覆（目標對照收下）走同一個 `wg_need_goal.apply_op`，逐字相同由 `hooks/verify/verify_closing_merge.py::test_reconcile_field_reply_identical_to_need_goal` 證。
