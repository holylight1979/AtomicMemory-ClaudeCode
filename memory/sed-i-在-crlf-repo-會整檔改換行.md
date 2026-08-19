# sed -i 在 CRLF repo 會整檔改換行

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: sed -i, CRLF, LF, gitattributes, eol=crlf, 換行差異, 批改多檔, git status 多出檔, autocrlf, 機械式取代
- Created-at: 2026-08-07
- Related: commit-前必須核對-staged-清單而非只信自己-add-了什麼, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [觀] MSYS2 的 `sed -i` 會以 LF 重寫整個檔案。對宣告 `*.cs text eol=crlf` 的 repo，批改後工作樹全改成 LF。
- [觀] `.gitattributes` 會在 commit 時正規化，所以 **`git diff` 看不到換行差異**，但 `git status` 會把一堆**實際沒改到的檔**標成 modified——一不小心就進了 staging，在多 session 共用工作樹裡尤其危險。
- [觀] 判別方式：`git diff --numstat` 列不出來、但 `git status` 標 M 的檔，就是只有換行殘影；`git diff -- <path> | wc -c` 為 0 即可安全 `git checkout -- <path>` 還原。
- [觀] `git diff --stat` 在這種情況會刷一堆 `LF will be replaced by CRLF` warning，那是訊號不是雜訊。
- [臨] **Python 的 `io.open(path,'w')` 是同一個地雷，而且更隱微**：文字模式寫會把 `\n` 轉成 `os.linesep`、讀會把 `\r\n` 歸一化成 `\n`。先讀再寫的「只改一行」腳本，實際會**把整個檔的換行重寫**——git 直接計成全檔修改（實測 358/358 行、232/231 行全點亮）。更陰的是用 `"\r\n" in s` 去偵測原本的換行會**永遠偵測不到**，因為讀取時已經被歸一化掉了。
- [臨] 正解：讀寫兩端都加 `newline=""`（`io.open(p, encoding=..., newline="")`），換行就原封不動。或者干脆不用腳本——**小幅改檔用 Edit 工具，它不動換行**。已踩到的補救：`git checkout -- <path>` 還原後重做（前提是還沒 commit）。
- [臨] 另一個相關坑：**Bash tool 的 heredoc 會吃掉反斜線**——`'\\'` 到了 python 裡變成 `'\'`、`\\n` 變成真的換行，導致語法錯誤或字串比對失敗。要在腳本裡處理包含反斜線的內容，改用 Write 工具寫腳本檔再執行，不要用 heredoc 夾帶。

## 行動

- 批改完立刻以 python 把動過的檔還原：`data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")`（先降 LF 再升 CRLF，幂等）
- commit 前用 `git diff --cached --name-only` 逐行核對；只有換行殘影的檔不要 stage
- 改檔前先確認 `.gitattributes` 的 eol 宣告，別預設 repo 是 LF
