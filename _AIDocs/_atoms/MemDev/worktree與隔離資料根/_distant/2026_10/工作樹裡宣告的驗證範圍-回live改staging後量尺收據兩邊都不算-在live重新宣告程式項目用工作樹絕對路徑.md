# 工作樹裡宣告的驗證範圍-回live改staging後量尺收據兩邊都不算-在live重新宣告程式項目用工作樹絕對路徑

- Scope: global
- Author: holylight
- Source: v6 T1.4 session 31aa0da5（2026-10-16），宣告 31aa0da5-S3
- Confidence: [臨]
- Trigger: 驗證範圍, SCOPE_ITEM_RECEIPT_AFTER_EDIT, 工作樹, worktree, _staging, 指令換目錄, 別棵樹
- Created-at: 2026-10-16
- Quote: 「checklist文件你有更新嗎??」

## 知識

- [臨] 互卡情境：在工作樹裡宣告驗證範圍（量尺指令項要在宣告時的目錄跑），照接續單規矩 ExitWorktree 回 live 改 memory/_staging 的推進文件後，那筆改動作廢量尺項：在 live 重跑算「指令換目錄」、在工作樹重跑算「跟改檔不同棵樹」，兩邊都不入帳，兩次就擋滿。
- [臨] 解法（實跑有效）：回 live 後重新宣告完整範圍——程式與案例項用工作樹的絕對路徑（target 與 case_for 都寫 C:/…/.claude-wt/<名>/…），沿用工作樹裡已跑綠的收據；文件與記憶量尺在 live 宣告、在 live 重跑。更好的順序是回 live 改完 _staging 再做最後一次宣告。

## 行動

- 工作樹 session 收尾回 live 改 _staging 之後，先在 live 重新宣告驗證範圍再跑量尺


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-29 | 退役移入 _distant/：驗證範圍閘（need_goal verify_scope）已於 2026-10-29 整套拔除（c4314d97），範圍宣告與範圍項目收據不再存在 | memory-audit --delete |
