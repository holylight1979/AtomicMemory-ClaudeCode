# feedback-暫時偵錯碼插進被外部程序持續執行的-live-檔案前後必-py-compile-一次語法錯誤讓使用者-statusline-整個失效

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 暫時偵錯碼, TEMP dump, statusline, live 檔案, py_compile, 插碼, stdin dump, 臨時 instrumentation
- Created-at: 2026-09-21

## 知識

- [臨] 2026-09-21 為了看 statusline 收到的 stdin JSON，用 heredoc 產生的 Python 字串把 dump 行插進 tools/statusline.py，字串內夾了真換行 → SyntaxError → Claude Code 每 10 秒執行一次的狀態列整個空白，verify_statusline 8 筆全紅；主持者代為回滾。dump 檔一直沒出現（當下只有 SDK／VS Code 模式的 session，不渲染 statusline），偵錯目的也沒達成。
- [臨] 被外部程序持續執行的檔案（statusline、hook handler、MCP server、排程腳本）等於線上服務：插碼＝上線。規矩：①插碼後立刻 `python -m py_compile` 並跑該檔 verify；②能複製到暫存目錄跑就不要動正本；③插碼與移除在同一回合完成，不跨回合留在檔案裡；④確認觸發路徑真的會執行到（本例根本沒有 TTY session），否則白插。
- [臨] 用 Python 腳本改檔時，寫進目標檔的字串含 `\n` 要在來源碼裡寫成兩個字元（`'\\n'`），heredoc 內先 print 出要寫入的行再落檔最保險。

## 行動

- 對 live 檔插偵錯碼：先問「有沒有觸發路徑會執行到」，沒有就別插。
- 插碼前備份或改用複本；插完立即 py_compile ＋ 該檔 verify；同回合移除。
- 改檔腳本先 print 出將寫入的內容核對逸出字元，再寫檔。
