# 第二意見材料只看git-diff不含未追蹤新檔-送審前先git-add-N新檔否則codex看不到新模組

- Scope: global
- Author: holylight
- Source: track-entrypoint-contract 001（第一輪 codex 材料沒帶到新檔全文、第二輪先 add -N 再跑）
- Confidence: [臨]
- Trigger: second_opinion_start, 第二意見 材料, codex 看不到新檔, git add -N, intent-to-add, 未追蹤新檔
- Created-at: 2026-10-21
- Quote: 「A」

## 知識

- [臨] 第二意見（second_opinion_start）的材料用 git diff 組，未追蹤的新檔不在 diff 裡，codex 會對著半份改動審（新模組全文沒帶到）。送審前先 git add -N <新檔>（intent-to-add），diff 就會含新檔全文；不會改變 commit 內容。

## 行動

- 跨 second_opinion_start 前：git status 看到 ?? 的新程式檔先 git add -N
