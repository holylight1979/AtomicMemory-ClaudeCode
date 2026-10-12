# 所有操作必須使用-worktree-的絕對路徑-嚴禁讀寫-live-目錄-開工前

- Scope: global
- Audience: programmer
- Author: holylight
- Source: session:d8dfd843 2026-10-12
- Quote: 「你是 v6.0 的工作 session track-g12（閱讀路徑掃描器），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-g12（分支 v6/track-g12，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\…」
- Confidence: [臨]
- Trigger: worktree絕對路徑, live目錄限制, target verify, 工作流程
- Created-at: 2026-10-12

## 知識

- [臨] 所有操作必須使用 worktree 的絕對路徑，嚴禁讀寫 live 目錄；開工前需通知 claude-ad；測試範圍僅限於目標 verify (pytest)，不進行全量或輪詢。
- <!-- src: d8dfd843-cbf6-4666-be79-f4ec26cb76ab-0 -->

## 行動

- （依知識內容判斷）


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-12 | 退役移入 _distant/：背景萃取把原設計者貼給 track-g12 的一次性開工句誤當成跨專案規則寫進根層（範疇錯放版控）；內容是單一 session 的派工指示，不是可重用知識。同型第二例，見 checklist C-萃取。 | memory-audit --delete |
