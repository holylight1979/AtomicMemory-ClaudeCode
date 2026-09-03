# heredoc反斜線三連踩post-mortem-含反斜線的腳本一律Write成檔再跑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: heredoc, 反斜線, python - <<EOF, replace 沒中, SyntaxError unterminated, assert old in s, post-mortem, Write 工具
- Created-at: 2026-09-03
- Related: bash-heredoc-會折掉一層反斜線-精確字串比對靜默失敗, hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定

## 知識

- [臨] 始末：同一 session 三次用 `python - <<'EOF'` 內嵌腳本做檔案字串取代，腳本寫 `"\\r\\n"`→工具層折掉一層反斜線→Python 收到真的 CR/LF。三型症狀：`assert old in s` 失敗但錯訊看起來「就是那行」（CR 不可見）；寫進 .py 的字串常數變實體換行→`SyntaxError: unterminated string literal`；連鎖腳本在 assert 前已印「已修」假訊號。最終正確做法：用 Write 工具把腳本寫成 scratchpad .py 再 `python 該檔`，三次都一次過。
- [臨] 根因：既有 atom（bash-heredoc-會折掉一層反斜線）只以一行 cold 路標注入，而我把每次都當「小取代不至於」；設計面是 Bash 工具對命令字串的轉譯層在 heredoc 引號之外，'EOF' 引號擋不住；verify_lf_writes 等守衛都在檔案層，擋不到輸入層。
- [臨] 防再犯：腳本含任何反斜線（\\n \\r \\t regex Windows 路徑）→一律 Write 成檔再跑，禁 heredoc；取代腳本先 assert 再印成功；改完 .py 立刻 ast.parse 或跑該測試。

## 行動

- 含反斜線的 Python 一律 Write 成檔再執行；取代腳本先 assert 再印成功；改 .py 後立刻 ast.parse
