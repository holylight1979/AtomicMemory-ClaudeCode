# CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CommitOrder, 本回合使用者原話沒有版控口令, 上GIT 被擋, git commit 被 hook 擋, 重下口令, 背景事件後 commit
- Created-at: 2026-09-14

## 知識

- [臨] CommitOrder 閘看「本回合使用者原話」＝state.turn_prompts（ups_gates.track_turn_prompts 維護；Stop 入口設 turn_open=False 關回合，下一則真使用者訊息重開）。同回合先說「上GIT」再補一句別的不會蓋掉口令；回合中途送的使用者訊息也有進 UserPromptSubmit、有進清單。
- [臨] 背景 agent／task 完成通知（整則 `<task-notification>`）也以 prompt 形式走 UserPromptSubmit，但不是使用者說的話：內文永不進 turn_prompts（否則 sub-agent 回報裡的「未 commit」會被當口令放行）；它在回合關閉後進來＝上一回合的延續，使用者原話沿用，所以「完工後直接上GIT」的預先授權跨得過背景等待。例外：口令之後已 commit 過（last_commit_turn_seq ≥ turn_prompts_seq）→ 清空，再 commit 要新口令。
- [臨] 仍會被擋的已知邊界（都是多擋一次、fail-safe）：Stop 被 block 後使用者才補的訊息會被當新回合；同回合 commit 過之後才補的預先授權，跨到通知回合不沿用。被擋就引用原話請使用者重下，不繞閘（不用 python subprocess 包 git commit；記憶庫 vcs-sync worker 是使用者裁決的例外）。
- [臨] 查這類「閘漏收」先翻 session 對話紀錄 jsonl 的事件順序（queued_command／hook_additional_context／task-notification 的時間線），不要只從閘的讀取端與 harness 顯示文案推測——先前兩個候選根因（中途訊息不走 UserPromptSubmit、state 重建丟失）都被紀錄否定。守門：hooks/verify/verify_git_commit_order_gate.py。
- [臨] bash 裡 `cat > file` 沒給 stdin 會讓工具背景卡死，提交訊息用 `git commit -F -` 搭 heredoc。

## 行動

- （依知識內容判斷）
