# codex-exec的-o輸出目錄不存在時只在stderr報錯-exit仍0-審查正文留在背景任務輸出-要先mkdir或從任務輸出救回

- Scope: global
- Author: holylight
- Source: session:f399cdb2 2026-10-13 多軌審查第一輪
- Confidence: [臨]
- Trigger: codex exec, -o, last message file, 審查檔不存在, os error 3, codex 輸出空, 背景任務輸出, VERDICT 沒落檔
- Created-at: 2026-10-13
- Quote: 「請把知識、經驗，該atoms的都記好，特別是我最後提出的」

## 知識

- [臨] `codex exec … -o <路徑>` 的目標目錄不存在時，審查照跑完、正文印在 stdout，只在 stderr 尾端一行 `Failed to write last message file … os error 3`，外層 exit 仍 0；背景跑時很容易以為審查沒出。正文還在背景任務的 .output 檔裡，用 regex `VERDICT: … (?=\nhook: Stop\n)` 切出來就能救回，不必重跑。

## 行動

- 起 codex exec 前先 mkdir -p 輸出目錄（新軌的收件夾第一次最容易漏）
- 審查檔不存在時先看 stderr log 尾行與任務 .output，再決定要不要重跑
