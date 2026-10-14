# 改索引產生器時背景記憶同步會先用工作樹的新版重產並自動commit索引-產物比程式先進版控

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: sync-memory-index, 索引產生器, vcs-sync, 背景記憶同步, knowledge harvest commit, 產物先進版控, 未提交的程式
- Created-at: 2026-10-14
- Related: 在記憶系統worktree分支做驗證或修正的環境坑-背景同步會自動commit文件-scratchpad快照碰過刪不掉-bash不能設home, knowledge-harvest-階段收割與vcs-sync機制指標與踩坑
- Source: session:8f368a10#99aa6d5b 2026-10-14
- Quote: 「再收割一次知識與經驗?」

## 知識

- [臨] 背景記憶同步（hooks/wg_vcs_sync.py）提交前會跑 `sync-memory-index.py --write`，用的是工作樹裡的程式，包含還沒 commit 的修改。別的 session 一收割就會觸發；實例：改產生器加語言視圖、還沒自己跑 --write，另一 session 的收割就把新產的 MEMORY.md 與 `_by_language/_INDEX.md` 以「knowledge harvest」為名 commit 了（9 分鐘後程式才 commit）。
- [臨] 後果：產生器改壞時，壞掉的索引會先被 commit（若待推段只有記憶 commit 還會被推出去）。改 sync-memory-index／索引相關程式時：先在暫存記憶樹或測試裡驗完再存檔到 live 程式，或在 worktree 改；live 改完立刻 `--check`，不要留半成品在工作樹。排查「索引怎麼自己變了」先看 Logs/vcs-sync.log 的 start reason=harvest sid=…

## 行動

- 改索引產生器前先在暫存記憶樹驗過，改完立刻 --check，不留半成品在 live 工作樹
- 索引被不明 commit 時先查 Logs/vcs-sync.log 的 harvest 觸發來源
