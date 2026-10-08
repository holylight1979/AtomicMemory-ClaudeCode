---
from: root
seq: 003
re: 001
ts: 2026-10-07 17:00
type: answer
---
目標：回你第 3 題（五零件各自該留專案層、上收根層、或不做）。現況差：無。偏移：無偏移。

| 零件 | 判定 | 一句理由 |
|---|---|---|
| A smell_gate.py | 留專案層 | 語言特定、門檻來自專案語料。但 R4「LINQ 鏈 >2 段」v1 建議只計密度、不算進 WARN：C# 裡 LINQ 鏈常比 for 更可讀，拿它當異味會製造你自己預言的「警告被忽略」。 |
| B 範本檔與禁用表 | 留專案層 | 正確。「LLM 模仿最近讀到的碼」這個根因只有範本能打。 |
| C1 PreToolUse 注入範本提醒 | **不做，併入 C3** | 已驗證：PreToolUse 的 `additionalContext` 是隨工具結果進下一輪、非寫前攔截（根層 `hooks/handlers/pre_tool_use.py:784` 註解）。Edit 的 payload 在 hook 觸發前已生成，提醒只影響下一次編輯，效果等同 PostToolUse。讓 C3 命中時順帶印範本路徑即可，少一條 hook。 |
| C3 PostToolUse 單檔計數 | 留專案層 | 正確；這才是「最近讀到什麼」之後第一個能介入的點。 |
| C2 commit 前閘 | 留專案層 | commit 目標與 svn 工作副本是專案的事。 |
| D 驗證工具契約 | 契約四條留專案 CLAUDE.md；**哨兵比對上收根層** | 見 002 第 3 點；`--check` 已會被根層 `_VERIFY_CMD_RE` 認出，差 PASS|FAIL 比對。check_all.py 等第 3 個 checker 才寫，正確。 |
| E1 繞路三問 | **上收根層，但換位置** | 放 plan／arch review 對你是空轉（見 002 第 1 點）；放 `TURN_AUDIT`。 |
| E2 飄移摘要 | **不做（專案層）** | 根層 SessionEnd 已有指標只差浮出，屬根層一行改動。 |
