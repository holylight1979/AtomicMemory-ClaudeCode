# track-closing-time 001 量測證據

- results/2026-10-27-CT-{1,2,3,5}：題 B′ 第一回合無頭實跑（hook 與 MCP 跑 closing-time worktree；run_ct.py）。CT-1／CT-2 跑的是附著點只認收尾檢核的前一版；CT-3／CT-5 是附著點多認完整對照之後。
- results/2026-10-27-CT-4：被調度點名打斷（transcript 多一則同伴訊息與回覆），作廢不計。
- ftb_ct.py：共用量尺 first_turn_breakdown.py 的複本，只把 RES 改讀 job 暫存的 results（輸入同一批 004 檔時尾行與原表逐位相同）。輸出 ftb-ct*.md。
- closing_baseline.py：計時帳（guard-hook_timing.jsonl kind=run）落在第一回合窗口的各事件耗時、>500ms 段、每次 Stop 的段（CB_BASE 指 results 根）。
- bench_batch.py：PostToolBatch 收尾一輪那段的行程內耗時；live_check.py：live 未動核對；target_verify.py：目標驗證範圍。
