# codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex exec, codex, 派 codex, 第二觀點, second opinion, 大師會議
- Created-at: 2026-09-03
- Related: feedback-tooling-reliability

## 知識

- [臨] 從 Bash tool 手動派 `codex exec`（非 companion）必帶三件：`--skip-git-repo-check`（cwd 在 scratchpad 等非 git 目錄會拒跑）、`</dev/null`（stdin 非 TTY 時 codex 等 EOF，背景任務卡死）、`-c 'windows.sandbox="unelevated"'`。
- [臨] 缺任一件的症狀都一樣：reply 檔 0 byte 但 exit 0，錯因只在 stderr 檔尾。派完先 `wc -c` 回覆檔 + `tail` stderr 再讀內容，別把 exit 0 當成功。

## 行動

- 模板：cd <dir> && codex exec --skip-git-repo-check -c 'windows.sandbox="unelevated"' "$(cat prompt.md)" > reply.md 2> err.txt </dev/null
