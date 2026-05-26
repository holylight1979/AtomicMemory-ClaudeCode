# feedback-workflow-discipline

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: handoff, 續接, 下 session, next-phase, 順手修補, drift 修補, 重複失敗, fix-escalation, 裁決, 決策推薦, plan 路徑, SessionStart hook, commit message, 上 GIT
- Created-at: 2026-05-26
- Related: feedback-completion-gates, feedback-tooling-reliability, v5-overhaul-audit-2026-05

## 知識

- [臨] handoff prompt 含六區塊自足性：現狀/改動清單/驗證/下一步/危險/規則連結，不靠模型記憶
- [臨] SessionStart hook 禁寫死特定 plan/phase 路徑，phase 狀態走 _staging/next-phase.md 或 hook 獨立 config
- [臨] 途中 drift ≤ 5 行 → 當場修；5-20 行 → 修 + diff；cross-檔 → handoff 明寫超出原因
- [臨] 重複失敗 ≥ 2 次啟動 fix-escalation（6 Agent 精確修正會議）
- [臨] 裁決 / 技術選擇不列選單；先推薦一個 + 理由 + 主要權衡
- [臨] git commit message 繁體中文（prefix 與 Co-Authored-By footer 保留英文）
- [臨] 「前例」/「既有 drift」/「pre-existing」 需附「檢測時點 + 不修風險」才可跳過

## 行動

- handoff 寫足六區塊
- drift 按門檻當場修
- 重複失敗 ≥ 2 次 → fix-escalation
- 裁決先推薦 + 理由
- Wave 1 保育期過後手動晉升 [觀] 或 [固]
