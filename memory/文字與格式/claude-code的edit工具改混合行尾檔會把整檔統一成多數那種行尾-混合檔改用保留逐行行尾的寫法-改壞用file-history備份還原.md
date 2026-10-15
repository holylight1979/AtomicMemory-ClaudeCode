# claude-code的edit工具改混合行尾檔會把整檔統一成多數那種行尾-混合檔改用保留逐行行尾的寫法-改壞用file-history備份還原

- Scope: global
- Author: holylight
- Source: 2026-10-15 改一份混合行尾的變更記錄檔時實測
- Confidence: [臨]
- Trigger: 混合行尾, CRLF, LF, Edit 工具, 行尾漂移, 整檔 diff, svn diff 全檔, file-history
- Created-at: 2026-10-15
- Quote: 「再給我一次確定版的 修改前後token差異表」

## 知識

- [臨] Claude Code 的 Edit 工具改「同一檔既有 CRLF 又有 LF」的檔時，會把整檔統一成多數那種行尾（實測 210 CRLF＋159 LF，只插一行就變 370 行全 CRLF，版控 diff 變整檔）。純 LF 或純 CRLF 的檔不受影響。
- [臨] 混合行尾檔改用保留逐行行尾的寫法（bytes 級 splice、或專案的安全改檔工具）；已經被統一的，用 `~/.claude/file-history/<session>/` 裡的改前備份還原，再只插入自己那一行；改完數 CRLF／LF 行數跟改前對。

## 行動

- Edit 前先用 file 或數 CRLF／LF 確認是不是混合行尾，是就不用 Edit
