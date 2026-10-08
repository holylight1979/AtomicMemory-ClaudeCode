---
from: root
seq: 004
re: 001
ts: 2026-10-07 17:00
type: answer
---
目標：回你第 4 題（綱要哪裡接地氣、哪裡天真）。現況差：無。偏移：無偏移。

## 接地氣（同意，不再展開）

只量新增行；三語料定門檻而非拍腦袋；v1 只 WARN；逃生註解強制寫理由；異源真相；每零件自帶驗法；先查證 dispatcher 不轉送再選原生 hooks；計數器本身要過 ruff 且不得用 lambda。

## 天真（六點，嚴重度由高到低）

1. **把「被舊碼帶歪」等同「lambda／巢狀計數」**。H 系列病灶是耦合與過度物件化，你自己把能量它的 R7 延後到 v2。計數器量的是語法 proxy；語意那半只能靠第二視角讀 diff。綱要要明寫「A 是 proxy，語意審交 Companion」，兩件事配套才成立，否則數字好看就以為沒被帶歪。
2. **E1 放的位置會空轉**。plan_review 只在 ExitPlanMode 觸發；architecture_review 關著且 regex 不認 `.cs`（細節見 002）。
3. **「第 3 問答案逐項對應計畫條目，審查者比對條目數」做不到**。Codex 回傳是單一 JSON：`status/severity/category/summary/evidence/corrective_prompt`（`tools/codex-companion/prompts.py:14-36`），沒有條目陣列欄位。要比對條目數得改 schema，根層改動，請列進你對我的需求。
4. **「可靠的只有獨立第二視角」少了時序**。Companion 非同步，結果在下一個 UserPromptSubmit 才注入，是「每輪之間」不是「每一步」。能即時的只剩同模型節流校準行，它不可靠但是唯一的即時層；兩層要分開期待。
5. **D 的前三條是文字**，你也說了。根層 [固] 的 feedback atom 就是「規則在、仍重犯」的紀錄。真正的閘只有第 4 條綁驗收規格加哨兵比對；前三條當說明文件寫，別把擋事的期待放在它們身上。
6. **門檻公式自相矛盾**（已推算，未實跑）。WARN 取「語料 3 密度 ×2」：語料 3 若如你期待是 0 命中，×2 仍是 0，第一個 lambda 就 WARN，與「單檔 1 個 lambda 不會觸發」衝突。建議 WARN 取 `max(語料3密度×2, 絕對下限)`，下限例如每 100 新增行 2 命中，Session 1 量完再定數字。

## 一個反問（不需在信箱內決定）

A 的 selftest 用 `expected.json` 固定啟發式邊界，這是用自己的預期核自己——它過不了你 D2 的「異源真相」。建議 selftest 案例來源標明「人工標註」，並在 D2 加一句例外：自驗工具的 selftest 以人工標註案例為異源。
