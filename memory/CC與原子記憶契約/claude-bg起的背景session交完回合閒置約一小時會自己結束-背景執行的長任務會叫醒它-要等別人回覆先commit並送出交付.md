# claude-bg起的背景session交完回合閒置約一小時會自己結束-背景執行的長任務會叫醒它-要等別人回覆先commit並送出交付

- Scope: global
- Author: holylight
- Source: 2026-10-23 state 讀改寫握鎖修補實測
- Confidence: [臨]
- Trigger: claude --bg, 背景 session 結束, 背景 session 消失, ListAgents 找不到, 閒置一小時, idle 結束, cost-state, 背景 session 接續, 收件人不在名單
- Created-at: 2026-10-22
- Related: claude-cli沒有ps子指令-未知子指令會被當成提問另開一次性session耗token-查背景session用transcript檔名或listagents

## 知識

- [臨] 用 `claude --bg` 起的背景 session，交完一個回合後如果閒置、沒有背景工作在跑，大約一小時會自己結束：實測兩次都在交完報告後約 60 分鐘，transcript 最後一筆寫 cost-state，ListAgents 就找不到它。
- [臨] 它用背景執行跑的長任務（run_in_background 的指令）跑完會叫醒它，這種情況不受影響。
- [臨] 要它等別人回覆時，等待前先把工作 commit 好、交付送出，下一個接手的才接得上。
- [臨] 要找它的一方發現 ListAgents 名單裡沒有它：先讀它的 transcript 最後幾則判斷停在哪，再在同一個工作樹（worktree）起新 session 接續。

## 行動

- 背景 session 要等人回覆：等之前先 commit 並送出交付
- ListAgents 找不到背景 session：先讀它 transcript 最後幾則，再在同一工作樹起新 session 接續
