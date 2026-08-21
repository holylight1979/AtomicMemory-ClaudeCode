---
task_slug: injection-noise-control
session_id: 32f0555d-d57e-4de1-978e-d92c090d6b12
created_at: 2026-08-21
source: multifile
status: done
---
## 必須發生
- 查證 activation 語意後才動手：確認負值是否 ACT-R log 尺度天然跨零（是 → 不加 activation<=0 過濾，修門檻/顯示設計）
- 最終裁切「寧缺勿截」：truncated 指標行設上限（預設 3），超出者整塊不注入；被略過/降級者落 atom-debug log 且尾行 budget 標記附裁切統計
- 截斷行移除誤導性 activation 數值顯示（移入 debug log）
- 查清 budget 上限為何有時 750、有時 2550 並照實記錄（compute_token_budget 起始額 − build_context 逐段扣減）
- same_file_3x 白名單：README/_CHANGELOG/DocIndex-*/各種 _INDEX 等高頻正常改動檔不產生、不採計覆轍信號；生成端（wg_episodic）與掃描端（wg_evasion）都過濾；被略過者留 debug log
- 補三項 regression verify 案例；跑 verify 全套無迴歸
- 修改處同步文件（Architecture.md per docdrift）；新認知寫 atom
## 禁止發生
- 不加 activation<=0 注入過濾（會誤殺低近期性但高相關的策展 atom）
- 不關掉覆轍警報本身（降噪非關警報）
- 不推倒重來；live 檔不留版本操作脈絡
## 驗證指令
- python run_verify.py（或 python -m pytest hooks/verify/ -q）
- 檢查 hooks/verify/verify_injection_noise_control.py 三案例通過
