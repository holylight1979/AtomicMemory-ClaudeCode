# 記憶系統repo上版免口令只認純git串-把python改檔或heredoc跟git寫在同一條指令整條被commit-order閘擋-先跑改檔再單獨下git串

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CommitOrder 擋, 無版控口令, 純 git 串, heredoc 跟 git, python 改檔後 commit, 貁免只認, 記憶系統 repo 上版, git 串分兩次
- Created-at: 2026-10-29
- Source: session:bc7c5340#13bc0220 2026-10-29

## 知識

- [臨] 原子記憶系統自己的 repo 免口令上版的貁免，只認「整條指令由 && 串起、每段都是 git 子指令」的形狀；前面多一段 python heredoc 改檔、或用 ; 、管線，整條被 CommitOrder 擋、連改檔那段也沒跑（同一場連犯三次）。被擋後要先查改檔有沒有落到，再分兩條重做。

## 行動

- 改檔（python／sed／Edit）跟 git add && git commit && git push 永遠分兩次工具呼叫
- 被 CommitOrder 擋下後先 git status 確認前段改檔有沒有發生
