# 背景驗證未收就結束回合-Stop閘裁判只看當下事證不看未來承諾

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: run_in_background, 背景任務, 等通知, Stop 閘, 驗收裁判, 提前結束回合, run_verify 背景, 收尾被擋
- Created-at: 2026-09-03
- Related: feedback-completion-gates, 專案工作驗收裁判的分級啟動與殺閘設計

## 知識

- [臨] 始末（2026-09-03 svn-resolve-project-lf）：實作、測試、探針、文件全完成後，把 run_verify 全套丟 `run_in_background`，以「跑完會自動接續 commit→push→acceptance→anti_evasion_report」結束回合等通知 → 驗收裁判（fail/high）與 ScanReport 同時擋收尾。最終正解：同一回合內等到結果、做完全部收尾再結束。
- [臨] 根因：把「背景任務完成會喚醒我」誤當「可以結束回合」的理由。Stop 閘的設計是：結束回合＝宣告本輪收尾，裁判對照 acceptance 清單只看工具軌跡裡已發生的事證，未來式承諾（「跑完會接續」）一律算未達標；背景通知是下一回合的輸入，回溯不了上一回合的判定。focus mode 下使用者又只看最後一則，對他而言就是「說完成但沒 commit」。
- [臨] 防再犯：驗證能在 10 分鐘內跑完就前景跑（Bash timeout 最大 600s）；非得背景就用 Monitor/until-loop 阻塞到結果，不結束回合。結束前自問「工作樹已 push？驗收檔已 done？anti_evasion_report 已發？」任一否就不許結束。真的非結束不可：首句「尚未完成、等候中」，不列已落地清單（同 [[feedback-completion-gates]] 2026-08-14 條）。

## 行動

- 全套驗證前景跑（timeout 600s）或 Monitor 等到結果，同回合內 commit→push→acceptance done→anti_evasion_report 再結束。
