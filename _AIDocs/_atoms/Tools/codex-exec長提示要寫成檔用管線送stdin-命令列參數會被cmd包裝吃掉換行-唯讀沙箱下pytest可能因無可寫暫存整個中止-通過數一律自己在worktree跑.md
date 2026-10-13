# codex-exec長提示要寫成檔用管線送stdin-命令列參數會被cmd包裝吃掉換行-唯讀沙箱下pytest可能因無可寫暫存整個中止-通過數一律自己在worktree跑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex exec 提示檔, 命令列吃掉換行, 唯讀沙箱 pytest 中止, codex 回報沒 pytest, Get-Content -Raw 管線, 第二意見提示
- Created-at: 2026-10-13
- Related: codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated
- Source: session:ea2955fd#61aecc26 2026-10-13
- Quote: 「還是提醒：此session歷經的 知識、經驗，atoms起來了齁?」

## 知識

- [臨]（track-a2c 實測 2026-10-13）codex exec 的長提示不要直接塞命令列參數（.cmd 包裝會吃掉換行）：寫成檔，用 `Get-Content '<prompt>' -Raw | codex exec … -`（stdin）或參數只放「先完整讀 <提示檔絕對路徑>再照做」。`-s read-only` 沙箱讀得到 -C 目錄以外的檔（提示檔放 session scratchpad 可讀）。唯讀沙箱下 pytest 可能因沒有可寫暫存目錄在啟動階段整個中止（不只是 deselect），codex 回報裡就完全沒有 pytest 結果；通過數一律自己在 worktree 跑，codex 只當讀碼審。

## 行動

- 派 codex 審碼：提示寫檔、管線送 stdin；報告裡的 pytest 數字不當證據
