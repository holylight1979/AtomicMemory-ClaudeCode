# 使用者貼上的內容在transcript包成pasted_content區塊-拿原話當他說的之前先剔掉-閉合id要逐字比-data-id不算id

- Scope: global
- Author: holylight
- Source: 分支 subagent-quote-fix 46fac1a0
- Confidence: [臨]
- Trigger: pasted_content, 貼上內容, 貼上區塊, 使用者原話, Quote, 引句, 開工句貼上, 閉合 id, data-id
- Created-at: 2026-10-27
- Related: 使用者原話權威判斷只吃單一清理函式-前綴判斷會被夾帶繞過-先截長會截掉口令-寫入端過濾會打開無紀錄放行, 從transcript回找使用者原話要停在開回合的紀錄-越過同伴訊息與背景通知會走到開工句

## 知識

- [臨]（實查 transcript）Claude Code 把使用者貼上的文字包成 `<pasted_content id="…">…</pasted_content id="…">`，閉合標籤也帶同一個 id。貼上的是從別處拿來的材料（例：別的 session 寫好的開工句、日誌、文件），不是本人打的字；要把使用者原話當「他說的」（引句、出處）之前先剔掉這些區塊。
- [臨] 剔除寫法：開標籤帶 id 時，閉合標籤的 id 要逐字相同才算結束（貼上材料裡夾著別的貼上區塊不會提早結束）；屬性名 id 前面不能接字母或連字號，否則 `data-id` 會被當成 id、提早結束剔除；沒閉合就剔到字串尾；剔完還殘留 pasted_content 標籤字樣 → 整則不認（分不出哪段是本人打的）。
- [臨] 剔的範圍看用途：要分「本人字跡」的地方（引句、出處）才剔；口令、糾正這類要看整則訊息意思的判斷照舊看整則（原子記憶系統只在卡片 Quote 剔）。

## 行動

- 從使用者訊息取引句前，先剔 pasted_content 區塊再做其他清理
- 剔除的測試要有：閉合 id 不同、data-id 屬性、貼上裡夾貼上、沒閉合 四種案例
