# note-git-launcher遇非utf8的py會丟unicodedecodeerror-呼叫端沒包會漏記同批後面的改檔-新呼叫點一律走post-tool-use的note-launcher

- Scope: global
- Author: holylight
- Source: 2026-10-23 Bash 寫入補算改檔實作
- Confidence: [臨]
- Trigger: note_git_launcher, _note_launcher, LAUNCHER_NOT_CODE, UnicodeDecodeError, 非 UTF-8 的 .py, 一次性 git 啟動器, 漏記改檔
- Created-at: 2026-10-23
- Depends: path:C:/Users/holylight/.claude/hooks/wg_verify_ledger.py, path:C:/Users/holylight/.claude/hooks/handlers/post_tool_use.py

## 知識

- [臨] `hooks/wg_verify_ledger.py` 的 `note_git_launcher` 用 utf-8 讀 .py、只接 OSError：遇到非 UTF-8 的 .py 會丟 UnicodeDecodeError。
- [臨] 呼叫端沒包的話，同一批後面的改檔會漏記，失敗路徑還會出現 state 改了卻沒寫回。
- [臨] `hooks/handlers/post_tool_use.py` 已包一層 `_note_launcher`（例外只印 stderr、照算程式、不擋後面的檔）；新的呼叫點要走它，不直接呼叫 note_git_launcher。

## 行動

- 新增「寫完 .py 要判是不是啟動器」的呼叫點：呼叫 post_tool_use 的 _note_launcher，不直接呼叫 note_git_launcher
