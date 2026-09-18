# CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CommitOrder, 本回合使用者原話沒有版控口令, 上GIT 被擋, git commit 被 hook 擋, 重下口令, 背景事件後 commit
- Created-at: 2026-09-14

## 知識

- [臨] Guardian 的 CommitOrder 閘判定「本回合使用者原話」只看最新一則來自使用者的訊息；若使用者說了「上GIT」但之後先進了系統通知（Monitor 事件、背景工作完成），到 commit 時會被擋「本回合原話沒有版控口令」。正解：收到口令就先 commit+push，不要先去做別的；被擋了就引用原話請使用者重打一次，不要繞閘。另：bash 裡 `cat > file` 沒給 stdin 會讓工具背景卡死，提交訊息用 `git commit -F -` 搭 heredoc。

## 行動

- 口令一到先跑 git，其他事後做
- 被 CommitOrder 擋下→引原話請重下，不自行繞過
