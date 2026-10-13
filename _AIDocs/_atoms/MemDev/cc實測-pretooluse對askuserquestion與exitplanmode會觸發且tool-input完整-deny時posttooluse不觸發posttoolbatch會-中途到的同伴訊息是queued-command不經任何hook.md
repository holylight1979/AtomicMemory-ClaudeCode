# cc實測-PreToolUse對AskUserQuestion與ExitPlanMode會觸發且tool_input完整-deny時PostToolUse不觸發PostToolBatch會-中途到的同伴訊息是queued_command不經任何hook

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: AskUserQuestion hook, ExitPlanMode hook, PreToolUse deny, PostToolBatch, queued_command, 同伴訊息不經 hook, 提問關鍵點, ask_probe, D(1) 實測
- Created-at: 2026-10-13
- Source: session:72133ffb#9fa7652c 2026-10-13
- Quote: 「一樣被擋下來了而且在plan mode就中斷了」

## 知識

- [臨] 實測（2026-10-13，原設計者親跑 `_console/ask_probe.py` 探針，VS Code 擴充）：PreToolUse 對 AskUserQuestion 與 ExitPlanMode 都會觸發，tool_input 完整（題目文字、選項、plan 全文與 planFilePath），deny 的理由 AI 讀得到並能複述；deny 時 PostToolUse 不觸發，PostToolBatch 仍會觸發（事後提醒／審計那條路可用）。deny 不保證 AI 自我修正：使用者口令與 hook 要求衝突時，AI 聽人、不重送（ask_retry=0），所以 deny 理由要寫到能直接照做。
- [臨] 實測（track-b-hooks 取樣 transcript 53 筆）：工作中途到的跨 session 訊息在 transcript 是 attachment.type=queued_command、origin kind=peer，**不經任何 hook**（不走 UserPromptSubmit）；只有在回合間隙到的才走 UPS。要對同伴訊息做任何關鍵點處理（例如裁定前三問），得在 PostToolBatch 從上次位置讀 transcript 尾段補掃。

## 行動

- 要在提問／交計畫前擋：用 PreToolUse deny，理由附可照做的修法；審計走 PostToolBatch
- 要處理同伴訊息：不能只靠 UPS，PostToolBatch 補掃 transcript queued_command
