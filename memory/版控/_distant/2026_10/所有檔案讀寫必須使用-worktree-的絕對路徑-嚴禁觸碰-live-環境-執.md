# 所有檔案讀寫必須使用-worktree-的絕對路徑-嚴禁觸碰-live-環境-執

- Scope: global
- Audience: programmer
- Author: holylight
- Source: session:18986b41 2026-10-12
- Quote: 「你是 v6.0 的工作 session track-b2，總控台是 claude-4b。派工 prompt 在 C:\Users\holylight\.claude\workflow\v6-inbox\to-track-b2\000-prompt.md，用絕對路徑讀完全文照做。worktree C:\Users\holylight\.claude-wt\track-b2（分支 v6/track-…」
- Confidence: [臨]
- Trigger: 絕對路徑, worktree, live, 讀寫規範, 目標 verify
- Created-at: 2026-10-12

## 知識

- [臨] 所有檔案讀寫必須使用 worktree 的絕對路徑，嚴禁觸碰 live 環境；執行範圍僅限於目標 verify，不進行全量運行。
- <!-- src: 18986b41-6167-4d57-a782-9cd795ab2e16-0 -->

## 行動

- （依知識內容判斷）


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-12 | 退役移入 _distant/：自動萃取把 v6.0 工作 session 的派工開工句（一次性、限該 worktree 的作業指令）當成跨專案版控知識寫進 memory/版控/；標題截斷、內容是派工規矩不是知識，總控台（claude-4b）退役。規矩本體在 workflow/v6-inbox/_console/開工句模板.md。 | memory-audit --delete |
