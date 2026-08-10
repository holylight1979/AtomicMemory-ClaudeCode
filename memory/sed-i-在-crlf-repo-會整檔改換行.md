# sed -i 在 CRLF repo 會整檔改換行

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: sed -i, CRLF, LF, gitattributes, eol=crlf, 換行差異, 批改多檔, git status 多出檔, autocrlf, 機械式取代
- Created-at: 2026-08-07
- Related: commit-前必須核對-staged-清單而非只信自己-add-了什麼, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [臨] MSYS2 的 `sed -i` 會以 LF 重寫整個檔案。對宣告 `*.cs text eol=crlf` 的 repo，批改後工作樹全改成 LF。
- [臨] `.gitattributes` 會在 commit 時正規化，所以 **`git diff` 看不到換行差異**，但 `git status` 會把一堆**實際沒改到的檔**標成 modified——一不小心就進了 staging，在多 session 共用工作樹裡尤其危險。
- [臨] 判別方式：`git diff --numstat` 列不出來、但 `git status` 標 M 的檔，就是只有換行殘影；`git diff -- <path> | wc -c` 為 0 即可安全 `git checkout -- <path>` 還原。
- [臨] `git diff --stat` 在這種情況會刷一堆 `LF will be replaced by CRLF` warning，那是訊號不是雜訊。

## 行動

- 批改完立刻以 python 把動過的檔還原：`data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")`（先降 LF 再升 CRLF，幂等）
- commit 前用 `git diff --cached --name-only` 逐行核對；只有換行殘影的檔不要 stage
- 改檔前先確認 `.gitattributes` 的 eol 宣告，別預設 repo 是 LF
