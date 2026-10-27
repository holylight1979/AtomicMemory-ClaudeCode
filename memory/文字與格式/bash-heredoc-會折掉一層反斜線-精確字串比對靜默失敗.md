# bash-heredoc-會折掉一層反斜線-精確字串比對靜默失敗

- Scope: global
- Author: holylight
- Source: commit:fa0a90e 2026-08-20（原對話已逾保留期）；2026-10-22 stop-gates 減量實測；2026-10-23 斷路器與紅測閘修補實測
- Confidence: [臨]
- Trigger: heredoc, 反斜線, escape, python 腳本, 字串比對失敗, assert, 批改程式碼
- Created-at: 2026-08-20
- Related: windows-python-write-text-缺-newline-把-lf-翻-crlf-整檔假-diff, heredoc反斜線三連踩post-mortem-含反斜線的腳本一律write成檔再跑

## 知識

- [臨] 用 `python - <<'PY' ... PY` 跑批改腳本時，heredoc 會折掉一層反斜線，`'EOF'` 加引號也擋不住（Bash 工具交給 bash 前的轉送層先吃一層）：腳本裡寫 `'\\n'`（要表示反斜線+n 兩字元），python 收到的已是真換行。
- [臨] 症狀一，比對靜默失敗：拿來匹配 C#/JS 原碼的 `string.Join("\n", ...)` 永遠 False、assert 掛掉看不出原因（像編碼問題，其實是傳途中被改掉）；`'\\n'` 多行 pattern 比對 CRLF 檔，`assert count==1` 全不中。診斷：`repr()` 印待匹配字串看是 `\\n` 還是 `\n`。
- [臨] 症狀二，寫出斷行字串：寫進 .py 的 `newline="\\n"`、測試檔字串被真換行斷開 → SyntaxError: unterminated string literal（腳本自印的 ok 照樣綠）；寫進 C# → CS1010 常數中包含新行字元；寫 JS（`node -e` 的 `/\\\\/g`、heredoc 寫 .js 的 `replace(/\\\\/g)`、python 把 `\\\\n` 寫進 js 字串）→ regex 未閉合 `missing ) after argument list` 或 `SyntaxError: Invalid or unexpected token`。看到這些先懷疑工具層折反斜線，不是程式邏輯問題。
- [臨] 再犯實例：'EOF' 加引號照樣中，兩次用 heredoc 跑 Python 改檔腳本，一次比對失敗、一次寫出斷行字串。
- [臨] 正解：改檔內容含反斜線（\n \r \t、regex、Windows 路徑）或多行字串 → 一律用 Edit 工具精確取代，或 Write 成腳本檔再 `python 檔名`；不含反斜線的批改（中文、一般標點）heredoc 安全。非組反斜線不可就 python 用 `chr(92)`（如 `chr(92)+'n'`）、JS 用 `String.fromCharCode(92)`（如 `s.split(String.fromCharCode(92)).join("/")` 取代 `/\\\\/g`）；改完 .py 跑 `ast.parse` 或 import、.js 跑 `node --check`，再跑測試。
- [臨] 同環境其他坑：單張 Bash 指令約超過 8KB 會被截斷（heredoc 尾部直接不見，報 unexpected EOF），大檔／大 patch 一律 Write 落地成 .py 再跑；printf 遇 Windows 路徑的 `\U` 會被當成 unicode 跳脫報錯。
- [臨] 批次改檔也要顧換行：`open()` 預設讀（universal newline）再寫回，CRLF 檔整檔變 LF（diff 1100 行）→ 用 `io.open(p, newline='')` 讀寫、pattern 先 `.replace('\\n', nl)`（nl 由檔內偵測）；改完 `git diff --stat`，行數異常膨脹即換行被改，用 `git show HEAD:` 對照還原。根因不是不知道，是沒把「先查換行格式」當寫批次改檔腳本的固定前置步驟。
- [臨] 另一例：用 heredoc `cat >> 測試檔` 附加測試碼，碼裡的反斜線同樣被吃掉一層。

## 行動

- 批改檔案前先問：要匹配的字串裡有反斜線嗎？有就改用 Edit 工具
- heredoc 腳本的 assert 挂掉時，先 repr() 印待匹配字串而不是改寫匹配邏輯
