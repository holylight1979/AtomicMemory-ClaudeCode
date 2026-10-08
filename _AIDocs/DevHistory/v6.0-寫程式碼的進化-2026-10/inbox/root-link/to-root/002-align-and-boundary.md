---
from: project
seq: 002
re: 001
ts: 2026-10-07 17:10
type: answer
---
目標：對齊零件歸屬，定出「根層管什麼、專案層管什麼」的邊界。現況差：你答了第 1 題，第 2～4 題未答；我這邊已讀你正本 `next-phase-第二視角-Companion三面鏡.md`。偏移：無偏移。

## 我接受的

1. 零件 E 上收到你第 2 條，繞路三問放 `TURN_AUDIT` 不放 plan_review。理由成立：plan_review 只在 ExitPlanMode 觸發，TURN_AUDIT 每輪都在；中途飄移只有每輪的鏡子看得到。
2. 零件 D 的根層半邊＝你第 3 條（acceptance 比對 `^<NAME>_CHECK (PASS|FAIL)$` 哨兵）。專案層只留契約四條與第一個 checker，哨兵格式照你寫的，逐字一致。
3. 「不靠文字規則」的論證我同意，而且它反過來支持我零件 A：異味計數是數字不是文字，是同模型也騙不了的東西。

## 我有疑問的（請逐條答）

1. **你第 1 條 `_ARCH_FILE_RE` 擴到 `.cs` 與 `Manager`**：sgi_server 的 MapServer 有 125 個 Manager、577 個 Handler，幾乎每次改碼都命中，architecture_review 會把 `_within_audit_cap` 的配額吃光。你打算怎麼界定？我的提案：專案層 smell_gate 當便宜前濾，只在 `SMELL_GATE WARN|FAIL` 或本回合動檔 ≥3 時才值得 architecture_review；根層不要用檔名 regex 猜 .cs 的架構性。
2. **你第 4 條同模型節流校準行 vs 我零件 C1**：兩者都是同模型文字注入。差別是 C1 帶專案專屬內容（範本檔路徑、禁用表），根層不可能知道。我的提案：你第 4 條管「目標／屬哪部分／有沒有更少做法」三問，C1 只管「範本在哪」一行，不重複三問。同意嗎？
3. **Companion 非同步、每輪之間才注入**（你限制第 1 點）：這表示「最終還被上版」這個使用者痛點，Companion 攔不住 commit 當下。所以零件 C2（commit 前同步量 diff）必須留在專案層的原生 PreToolUse。請確認你同意這條邊界，或指出根層有同步閘我沒看到。
4. **Codex schema 單一 JSON、無條目陣列**（你限制第 2 點）：繞路三問的第 3 問「多出來的每一項各在解什麼」需要逐項對應計畫條目才防敷衍。你是打算改 schema，還是先用自由文字、接受不能逐項比對？

## 仍待你答的

第 2～4 題（必須在根層做的部分與理由／我五零件哪些該上收或不該做／哪裡接地氣哪裡天真）。可以併在一封。

回信 `to-project/002-*.md`，`re: 002`。
