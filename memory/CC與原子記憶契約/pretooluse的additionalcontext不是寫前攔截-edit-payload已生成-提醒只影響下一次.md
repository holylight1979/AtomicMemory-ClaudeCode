# pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次

- Scope: global
- Author: holylight
- Source: c:/Projects/.claude/inbox/root-link/to-project/003-five-parts-verdict.md
- Confidence: [臨]
- Trigger: PreToolUse, additionalContext, 寫前提醒, 寫碼前注入, 範本提醒, hook 注入時序, PostToolUse 等效
- Created-at: 2026-10-07
- Quote: 「開一個跨session溝通的 inbox monitor.. 我想讓你與根層 直接溝通 看看，那個session也在討論類似的議題，只是 你的似乎更接地氣 (?)。 好了以後給我 prompt 讓我去在根層的CC貼上；僅限 先溝通。」

## 知識

- [臨]（根層 session 對碼驗證，`hooks/handlers/pre_tool_use.py:784` 註解）PreToolUse 回的 additionalContext 是隨工具結果進下一輪，不是寫前攝截：Edit/Write 的 payload 在 hook 觸發前已生成，「寫碼前先看範本」這種提醒只能影響下一次編輯，效果等同 PostToolUse。要真正擋寫入只有 deny；要影響寫法就放 PostToolUse 命中時順帶印，少一條 hook。

## 行動

- 設計「寫碼前提醒」類 hook 時不用 PreToolUse 注入，改 PostToolUse 命中時附帶，或直接 deny
