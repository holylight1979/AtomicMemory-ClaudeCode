# bash-heredoc-會折掉一層反斜線-精確字串比對靜默失敗

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: heredoc, 反斜線, escape, python 腳本, 字串比對失敗, assert, 批改程式碼
- Created-at: 2026-08-20
- Related: windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff

## 知識

- [臨] 用 `python - <<'PY' ... PY` 跑批改腳本時，**heredoc 會折掉一層反斜線**：腳本裡寫 `'\\n'`（本來要表示「反斜線+n」兩個字元），python 收到的已經是真換行。後果是拿來匹配 C#/JS 原碼裡的 `string.Join("\n", ...)` 永遠 False，**assert 挂掉但看不出原因**（以為是編碼問題，實際是傳途中被改掉）。診斷法：把待匹配字串 `repr()` 印出來看是 `\\n` 還是 `\n`。
- [臨] 正解：要改**含反斜線**的程式碼就不要用 heredoc 包 python——改用 Edit 工具做精確取代，或先把腳本寫成檔案再 `python 檔名` 執行。不含反斜線的批改（中文、一般標點）heredoc 是安全的。
- [臨] 同源新坑兩條：① 單張 Bash 指令約超過 8KB 會被**截斷**（heredoc 尾部直接不見，報 unexpected EOF），大檔/大 patch 一律用 Write 工具落地成 .py 再 `python 腳本`；② 折反斜線連 C# 字串都中標：寫雙反斜線+n 進來變真換行，編譯報 **CS1010 常數中包含新行字元**——看到這個錯就先懷疑工具層折反斜線，不是程式邏輯問題。
- [臨] 再犯（2026-09-01 scope 三階段）：同一 session 連中三次同類坑——① quoted heredoc 寫測試檔，`\\n` 被折成真換行、字串字面斷行致 SyntaxError；② Python 批次改檔用 `open()` 預設讀（universal newline）再寫回，CRLF 檔整檔變 LF，diff 1100 行；③ 同一支批次腳本用 `'\\n'` 多行 pattern 比對 CRLF 檔，`assert count==1` 全部不中。**根因**不是不知道（atom 早就有），是寫批次改檔腳本時沒把「先查換行格式」當固定前置步驟。**防再犯（固定流程）**：寫檔含反斜線或多行字串 → 一律 Write/Edit 工具，不走 bash heredoc；Python 批次改檔 → `io.open(p, newline='')` 讀寫、pattern 先 `.replace('\\n', nl)`（nl 由檔內偵測）；改完 `git diff --stat`，行數異常膨脹即換行被改，用 `git show HEAD:` 對照還原。
- [臨] 不只字串比對：寫 JS 的場合也中——`node -e` 內 `/\\\\/g`、heredoc 寫 .js 內 `replace(/\\\\/g)`、heredoc python 把 `\\\\n` 寫進 js 字串，三種都退化成單一反斜線（regex 未閉合 → `missing ) after argument list`；字串裡出現真換行 → `SyntaxError: Invalid or unexpected token`）。解法：JS 用 `String.fromCharCode(92)`（`s.split(String.fromCharCode(92)).join("/")` 取代 `/\\\\/g`）、python 用 `chr(92)` 拼字串；要寫進檔案的內容含反斜線就直接用 Write/Edit 工具不走 heredoc；寫完必 `node --check` / import 驗證一次。

## 行動

- 批改檔案前先問：要匹配的字串裡有反斜線嗎？有就改用 Edit 工具
- heredoc 腳本的 assert 挂掉時，先 repr() 印待匹配字串而不是改寫匹配邏輯
