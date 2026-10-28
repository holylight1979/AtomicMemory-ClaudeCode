# windows-git-worktree放進claude暫存scratchpad會filename-too-long-一堆檔建不出來-worktree一律放短路徑如c根下

- Scope: global
- Author: holylight
- Source: session 3588eaca 2026-10-28 試套同事 patch 實踩
- Confidence: [臨]
- Trigger: Filename too long, worktree add, git worktree, scratchpad worktree, unable to create file, 套 patch 試跑, git am 試套, 長路徑
- Created-at: 2026-10-28

## 知識

- [臨] Windows 上把 git worktree 建在 Claude 的 scratchpad（AppData\\Local\\Temp\\claude\\<專案>\\<session>\\scratchpad\\…，前綴已逾 100 字）下，checkout 時長檔名（中文 atom 檔名、測試 cassette）整批 `unable to create file … Filename too long`，worktree 建出來是殘缺的、git 還認不得它是 working tree，要 `git worktree prune` 才清得掉。
- [臨] 要試套別人的 patch 或起隔離分支，worktree 放短路徑（例 C:\\wt-<名>），用完 `git worktree remove --force` 再刪分支；不要為了「暫存就放暫存目錄」賠上路徑長度。

## 行動

- Windows 建 worktree 一律用 C:\\ 根下短目錄，不放 scratchpad
- 看到 Filename too long 先 git worktree prune 再換短路徑重建，不要開 core.longpaths 當萬靈丹（中文長檔名仍可能超過 260）
