# claude-bg起的工作軌收尾會卡在askuserquestion沒人答-總控台看transcript最後一則是提問就直接對帳合併再claude-stop-worktree目錄要等程序退出才刪得掉

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-21 背景工作軌（claude --bg）卡放行題 12 小時
- Confidence: [臨]
- Trigger: claude --bg, console-spawn, bg session waiting, 背景工作軌, claude stop, claude attach, ListAgents bg waiting, 收尾放行題沒人答, 工作樹 Permission denied
- Created-at: 2026-10-21
- Quote: 「喔最後一個也關掉了。」

## 知識

- [臨] 用 `claude --bg`（總控台的 console-spawn）起的工作軌沒有人在畫面前：它改完、commit 完都會做，但收尾閘擋滿發「收尾放行確認」（例無新案例的放行題）時會永遠卡在 AskUserQuestion：ListAgents 顯示 `bg · waiting`，後續 SendMessage 進不去（收件要等下一次工具呼叫），交付信送不出來。實例：某軌第二件做完後卡了 12 小時。
- [臨] 總控台的處理：讀它的 transcript（projects 下該 worktree slug 資料夾裡的 <sid>.jsonl）最後一則 assistant，是 AskUserQuestion 就知道卡在哪題；分支 HEAD 比上次交付前進了就自己對帳（git show --stat、merge-tree、跑目標 verify）合併，再 `claude stop <短 id>` 停掉；要人答才用 `claude attach <短 id>`。停掉後 worktree 目錄會有幾十秒 Permission denied，稍後再 rm。
- [臨] 預防：給 bg 軌的派工單要寫「收尾被擋滿要問人時不發 AskUserQuestion，把擋訊息原文寫進交付信給總控台裁」；改舊測試／無新案例這類會觸發放行題的事先在派工單裡裁好。

## 行動

- ListAgents 看到 bg waiting → 先讀它 transcript 最後一則，再決定 attach 還是自己對帳合併＋stop
- 寫給 bg 軌的派工單：收尾放行題不發，寫進交付信
