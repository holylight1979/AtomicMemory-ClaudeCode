# CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令

- Scope: global
- Author: holylight
- Source: session:c5b0a814#c9c2cf0f 2026-09-14；2026-10-22 stop-gates 減量實測
- Quote: 「此session的經驗與知識，需要記憶的就atoms記起來吧。都記好以後 上GIT 、上乾淨。」
- Related: cc同伴訊息封裝只轉義正文裡的cross-session-message閉合標籤-其他harness標籤原樣保留, 使用者原話權威判斷只吃單一清理函式-前綴判斷會被夾帶繞過-先截長會截掉口令-寫入端過濾會打開無紀錄放行
- Confidence: [臨]
- Trigger: CommitOrder, 本回合使用者原話沒有版控口令, 上GIT 被擋, git commit 被 hook 擋, 重下口令, 背景事件後 commit, 口令持續到 push, v6 開時口令
- Created-at: 2026-09-14

## 知識

- [臨] CommitOrder 閘看「本回合使用者原話」＝state.turn_prompts（ups_gates.track_turn_prompts 維護；Stop 入口設 turn_open=False 關回合，下一則真使用者訊息重開）。同回合先說「上GIT」再補一句別的不會蓋掉口令；回合中途送的使用者訊息也有進 UserPromptSubmit、有進清單。
- [臨] 背景 agent／task 完成通知（整則 `<task-notification>`）也以 prompt 形式走 UserPromptSubmit，但不是使用者說的話：內文永不進 turn_prompts（否則 sub-agent 回報裡的「未 commit」會被當口令放行）；它在回合關閉後進來＝上一回合的延續，使用者原話沿用，所以「完工後直接上GIT」的預先授權跨得過背景等待。v6 開時：口令撐到這批 push 完或使用者打字開新回合為止；push 完＝收尾和口令閘判口令前都補掃 transcript，認跑成功的 git push／svn commit，echo、commit 訊息字樣、--dry-run 不算；續跑回合裡使用者打的第一則字也算新回合。v6 關：照舊 commit 過就清空。
- [臨] 已知邊界：使用者新打一則字＝口令失效（這是設計，不是誤擋）；push 之後同回合再 commit 要新口令，多個 repo 要先全部 commit 再 push。被擋就引用原話請使用者重下，不繞閘（不用 python subprocess 包 git commit；記憶庫 vcs-sync worker 是使用者裁決的例外）。
- [臨] 查這類「閘漏收」先翻 session 對話紀錄 jsonl 的事件順序（queued_command／hook_additional_context／task-notification 的時間線），不要只從閘的讀取端與 harness 顯示文案推測——先前兩個候選根因（中途訊息不走 UserPromptSubmit、state 重建丟失）都被紀錄否定。守門：hooks/verify/verify_git_commit_order_gate.py。
- [臨] bash 裡 `cat > file` 沒給 stdin 會讓工具背景卡死，提交訊息用 `git commit -F -` 搭 heredoc。
- [臨] 同家族第三案：Claude in Chrome「Enabled by default」開著時，harness 把約 2900 字的 `<browser_instruction>` 區塊塞在使用者訊息前面（本機最近 4 場 16 則中 7 則有）；sanitize_harness_noise 沒列這個標籤，而口令閘只存清理後前 500 字，尾端的「上GIT」被截掉 → 誤擋。修：`_HARNESS_TAG_RE` 加 `browser_instruction`（hooks/wg_core.py），測試在 verify_episodic_noise_filter。根因通則：任何新的 harness 注入標籤都要進 `_HARNESS_TAG_RE`，否則 500 字截斷會吞掉口令。
- [臨] 同伴 session 訊息不算口令。記憶系統 repo 與它的 git worktree 的 commit 不等口令，但只認 `&&` 串的 `cd <絕對路徑>`／`git [-C <字面路徑>] add|commit|push…` 句型，尾巴接管線或 `;`、訊息含反斜線就要口令（細節：TECH.md guard.commit_order 列、_AIDocs/_CHANGELOG.md 段）。
- [臨] 使用者用一般說法授權時可附 `# 授權原句：「…」`，程式核對逐字與否定。

## 行動

- （依知識內容判斷）
