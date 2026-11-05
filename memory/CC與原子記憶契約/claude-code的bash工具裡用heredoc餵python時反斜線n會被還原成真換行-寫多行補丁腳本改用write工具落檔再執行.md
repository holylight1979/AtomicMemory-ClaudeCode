# claude-code的bash工具裡用heredoc餵python時反斜線n會被還原成真換行-寫多行補丁腳本改用write工具落檔再執行

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: heredoc, <<'PY', unterminated string literal, 反斜線 n, 補丁腳本, python - <<, 多行腳本餐 bash
- Created-at: 2026-11-05
- Source: session:9f83cf22#15d1ba32 2026-11-05
- Quote: 「都收割了? 我另外想到 "安裝" 方面有沒有文件需要更新，或者是參閱現有狀態與理解後 改進 的?」

## 知識

- [臨] 在 Claude Code 的 Bash 工具裡 `python -I - <<'PY' … PY` 餐多行腳本，腳本內容裡的 `\\n`（連字串常數內的）兩次都被還原成真的換行，寫進目標檔後變成 unterminated string literal；引號引號 delimiter 沒有挤住。長腳本還會被判成 unexpected EOF。

## 行動

- 超過幾行、或內容含跳脫序列的補丁腳本：用 Write 工具寫進 scratchpad 再 `python -I <路徑>`，不走 heredoc
- 改字串常數裡的跳脫序列用 Edit 工具，不用 bash 串 python
