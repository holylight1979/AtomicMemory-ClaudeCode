# 第二意見要在commit前送-已commit時工作樹diff為空-codex只拿到摘要判證據不足指不出缺陷

- Scope: global
- Author: holylight
- Source: track-realm-entry-pin 001／002 代寫 2026-10-22
- Confidence: [臨]
- Trigger: second_opinion_start, diff 為空, 證據不足, commit 後送審, stage-review
- Created-at: 2026-10-21
- Entry: E16

## 知識

- [臨] second_opinion_start 打包的是工作樹相對 HEAD 的 diff；已經 commit 才送審，回傳寫「diff 為空」，Codex 只拿到交付摘要與收據，只能判「證據不足」、指不出缺陷。要審程式就在 commit 前送，或先把改動留在工作樹。

## 行動

- （依知識內容判斷）
