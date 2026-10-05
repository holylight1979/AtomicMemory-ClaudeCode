# SessionStart的提示只有模型看得到-要使用者做決定就寫成叫模型用AskUserQuestion問的指示-問到有答案為止不要只提示一次

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: SessionStart 提示, 只提示一次, 只邀請一次, AskUserQuestion, advisory, 使用者沒被問到, 首次設定, 尚未接上, 需要使用者決定, onboarding 提示, declined
- Created-at: 2026-10-05
- Related: hook-systemmessage-只給使用者看-模型讀不到-要回饋模型用additionalcontext或deny-reason

## 知識

- [臨] 實踩（2026-10-05）：公司層未接上時，SessionStart 出一行「對我說『接上公司記憶』」，而且整台機器只出一次。同事更新後回報「資料夾不會建立、也沒被問」。兩個錯疊在一起：① SessionStart 的 additionalContext **只有模型看得到**，那句話卻是寫給使用者的說明，模型沒被要求做任何事就不會做；②「只提示一次」是我在交接檔裡裁決的（怕擾民），結果那一次一過就永遠沒機會。
- [臨] 規則：需要使用者做一次性決定的首次設定（路徑、要不要啟用），SessionStart 要寫成**給模型的指示**：「第一則回覆前先用 AskUserQuestion 問使用者：(1)…→ 執行 `指令`；(2)…；(3) 先不要 → `指令`」，每個選項附對應指令（先例：`[Guardian:ProjectRoot] ❓`）。**問到有答案為止**：狀態機三態——已設定／已拒絕（記 `declined`）／未回答；只有未回答時出指示，回答後永不再出。「不擾民」靠「答過就不問」達成，不是靠「只說一次」。
- [臨] 答案存本機不進版控的檔（例 `workflow/org-memory.local.json`），共用設定只留全公司相同的值（repo 網址、預設路徑）。實作錨點：`hooks/handlers/session_start.py _org_advisory`、`tools/org-memory.py --join／--decline`、守門 `verify_org_layer::test_unjoined_machine_is_asked_until_answered`。

## 行動

- 設計首次設定提示：寫成叫模型用 AskUserQuestion 問的指示，選項含「先不要」且每項附指令
- 三態狀態：已設定／已拒絕／未回答；未回答每次都問
- 驗收時印出「全新機器的模型實際會收到的那一行」看它是不是指示句
