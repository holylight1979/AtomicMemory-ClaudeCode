# 工作流程必須使用-enterworktree-切入指定-worktree-所有讀

- Scope: global
- Audience: programmer
- Author: holylight
- Source: session:2a7705d4 2026-10-12
- Quote: 「你是 v6.0 的工作 session track-verify（獨立實跑驗證），總控台是 claude-ad。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-verify（detached，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\v6…」
- Confidence: [臨]
- Trigger: EnterWorktree, 絕對路徑, worktree absolute path, scratchpad, tmp
- Created-at: 2026-10-12

## 知識

- [臨] 工作流程必須使用 EnterWorktree 切入指定 worktree，所有讀寫操作和資料根目錄（hook探針）一律限定於 worktree 絕對路徑、scratchpad 或 tmp，嚴禁修改程式碼或觸碰 live/其他 worktree。
- <!-- src: 2a7705d4-b27c-4942-8f4c-becd4f46af74-0 -->

## 行動

- （依知識內容判斷）


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-12 | 退役移入 _distant/：背景萃取把原設計者貼給 track-verify 的一次性開工句誤當成跨專案規則寫進根層（範疇錯放版控）；同型第三例，見 checklist C-萃取。 | memory-audit --delete |
