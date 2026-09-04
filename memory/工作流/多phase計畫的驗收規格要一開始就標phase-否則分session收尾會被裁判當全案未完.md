# 多phase計畫的驗收規格要一開始就標phase-否則分session收尾會被裁判當全案未完

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 驗收規格, acceptance, 驗收裁判, 分phase, 分階段, 多session, phase標籤, 收尾被擋, plan-mode 驗收
- Created-at: 2026-09-04
- Related: feedback-completion-gates, workflow-rules

## 知識

- [臨] 從 plan 轉出驗收規格時，若計畫是多 phase 分 session 執行，每条「必須發生」要一開始就標 `[Phase N]`，frontmatter 加 `phases` / `phase_progress`；否則分 session 收尾時驗收裁判會拿全案清單判本 session，把未排定的後続 phase 列為「未達標」擋收尾（2026-09-04 H-4 v2 Phase 0 実例）
- [臨] 每個 phase 收尾只把自己 phase 的条目改 ✅ 並更新 phase_progress，`status` 維持 open 到最後一 phase 才改 done；裁判若仍拿後続 phase 擋，回覆中引用規格檔的 phase 欄說明範圍即可

## 行動

- 寫 acceptance 前先看 plan 是否分 phase；是 → 逐条標 [Phase N] + frontmatter phases/phase_progress
