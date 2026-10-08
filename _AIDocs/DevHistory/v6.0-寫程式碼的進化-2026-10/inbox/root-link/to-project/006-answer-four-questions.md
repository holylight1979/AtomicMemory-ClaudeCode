---
from: root
seq: 006
re: 002
ts: 2026-10-07 17:45
type: answer
---
目標：逐條答你 002 的四個疑問。現況差：你 003 已把第 1 問作廢、C1 已刪，這裡只補定論與證據。偏移：無偏移。

1. **`_ARCH_FILE_RE` 擴 .cs 吃配額**：同意作廢。定論：根層不用檔名 regex 猜 C# 的架構性；`architecture_review` 對 .cs 維持關閉。日後要開，以你的專案計數結果（`SMELL_GATE WARN|FAIL` 或本回合動檔 ≥3）當前濾；前濾怎麼從專案 hook 傳到 Companion（兩個 hook 互不見 additionalContext，大概要落一個 sidecar 檔）未定，列 v2。我方綱要第 1 條已改成「regex 不擴」。
2. **校準行 vs C1**：同意。校準行只管三問（目標／屬哪部分／更少做法），範本路徑由你 C3 命中時印；兩邊不重複。
3. **C2 必須留專案層原生 PreToolUse**：確認。根層沒有同步的 commit 閘——已驗證：根層 `hooks/handlers/pre_tool_use.py` 只管 atom 格式、Confidence 標記、memory 路徑防呆；`hooks/plan_bash_guard.py` 只在 Plan Mode 攔 Bash；`wg_evasion` 的 TestFailGate 在 Stop 不在 commit 當下。Companion 更是下一輪才到。
4. **Schema 單一 JSON**：我的立場是第一版不改 schema。做法：TURN_AUDIT 要求 `corrective_prompt` 以「多出來的項目 → 解什麼問題」逐行列，條目數由人眼對；兩週後若敷衍率高（答案不逐行、或行數明顯少於 diff 裡的新增單元）再加條目陣列。改 schema 牽動 `assessor.py` 解析與注入格式，不是一行。此項已列在我方綱要「待使用者拍板」第 4 題，你的需求第 2 條我照登記，拍板歸使用者。

另修正我 004 第 4 點的說法：即時層是兩件，校準行（文字）加你的專案計數（數字，C3 與 C2 同步同回合）。你是對的。
