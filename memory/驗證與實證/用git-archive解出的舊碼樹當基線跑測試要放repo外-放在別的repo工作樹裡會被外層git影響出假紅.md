# 用git-archive解出的舊碼樹當基線跑測試要放repo外-放在別的repo工作樹裡會被外層git影響出假紅

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: git archive, 基線樹, 舊碼樹, 基線跑測試, 外層 .git, 假紅, 舊碼對照
- Created-at: 2026-10-27
- Related: 退回檢查的暫存副本要用git-archive整棵解-tar要force-local-副本含部位表會被overviewhub當專案-送codex的diff不能有暫存外絕對路徑, 回歸測試先證明舊版會紅-把舊版受測檔git-show到暫存夾配新測試跑-紅要紅在斷言不是keyerror
- Source: session:17c8cd5c#840617df 2026-10-27

## 知識

- [臨] git archive 解出的樹沒有自己的 .git；放在另一個 repo（例如 worktree）的目錄底下跑測試，樹裡的 git 指令會沿上層目錄找到外層 repo，碰 git 的案例結果被外層狀態左右。
- [臨] 實例：基線樹放在 worktree 裡跑，scaffold 類 9 案紅；同案在真 worktree 上全綠，紅是假象。
- [臨] 做法：基線樹放 repo 外的目錄；放不出去就只當參考，逐條看紅因（是不是 git 找到外層 repo）再跟新碼比。

## 行動

- 解基線樹前先選 repo 外的目錄
- 基線出紅先逐條看紅因，排除外層 git 影響再下結論
