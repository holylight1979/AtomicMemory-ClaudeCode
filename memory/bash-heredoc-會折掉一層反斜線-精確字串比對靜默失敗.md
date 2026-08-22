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

## 行動

- 批改檔案前先問：要匹配的字串裡有反斜線嗎？有就改用 Edit 工具
- heredoc 腳本的 assert 挂掉時，先 repr() 印待匹配字串而不是改寫匹配邏輯
