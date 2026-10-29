# 背景記憶同步預設連tech-md一起上版-別的session正在改tech-md時會被當記憶同步推上去-手動跑同步要把它從pathspec拿掉

- Scope: global
- Author: holylight
- Source: session bc7c5340 上GIT 時另一個 session 正拆 TECH.md
- Confidence: [臨]
- Trigger: vcs-sync, root_extra_pathspecs, TECH.md 被同步, 併發 session, 手動跑同步, vcs-sync-worker, 記憶同步帶到別人的檔
- Created-at: 2026-10-29

## 知識

- [臨] 背景記憶同步的根層 pathspec 除了 `memory`、`_AIDocs/_atoms`，還預設帶 `TECH.md`、`_AIDocs/_INDEX.md`、`_AIDocs/DocIndex-System.md`（計數標記連動）。它整檔 add，不管改動是不是只有計數：另一個 session 正在大改 TECH.md 時，同步會把它做一半的內容當「knowledge harvest」推上去。
- [臨] 手動跑 `hooks/vcs-sync-worker.py` 前先 `ListAgents` 看有沒有 busy 的 session、`git status` 看那三個檔是不是別人在改；是就用 `collect_sync_targets` 取 targets、把該檔從 pathspecs 拿掉，經 stdin 的 `targets` 欄位餘給 worker。

## 行動

- 手動跑記憶同步前先查併發 session 與 TECH.md 狀態，必要時用 targets 排除
