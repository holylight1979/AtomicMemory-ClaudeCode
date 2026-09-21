# CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CommitOrder, 本回合使用者原話沒有版控口令, 上GIT 被擋, git commit 被 hook 擋, 重下口令, 背景事件後 commit
- Created-at: 2026-09-14

## 知識

- [臨] Guardian 的 CommitOrder 閘判定「本回合使用者原話」只看最新一則來自使用者的訊息；若使用者說了「上GIT」但之後先進了系統通知（Monitor 事件、背景工作完成），到 commit 時會被擋「本回合原話沒有版控口令」。正解：收到口令就先 commit+push，不要先去做別的；被擋了就引用原話請使用者重打一次，不要繞閘。另：bash 裡 `cat > file` 沒給 stdin 會讓工具背景卡死，提交訊息用 `git commit -F -` 搭 heredoc。
- [臨] 2026-09-21 根因已修，上面「請使用者重下口令」只剩舊 state 退路：閘改看整回合原話 state.turn_prompts（ups_gates.track_turn_prompts 維護；Stop 入口設 turn_open=False 關回合，下一則 prompt 重開），使用者先說「上GIT」再排隊補一句別的話不再被擋。觸發情境：使用者「好，上GIT」後 mid-turn 補「計畫檔沒價值就刪」，閘只看 recent_user_prompts[-1] 就否決。為什麼會寫成這樣：recent_user_prompts 是 Evasion Guard 的滑窗，口令閘借用時假設一回合只有一句，連測試都把這個錯前提寫成規格。已知邊界：Stop 被 block 後再來的 mid-turn 訊息會被當新回合，只多擋一次。

## 行動

- 口令一到先跑 git，其他事後做
- 被 CommitOrder 擋下→引原話請重下，不自行繞過
