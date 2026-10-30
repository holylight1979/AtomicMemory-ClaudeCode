# 子代理改碼時寫碼查核的三個實況-子代理共用主session讀檔帳寫檔前要交定位行-主session擋訊息不帶子代理歸屬只在state看得到-刪掉對照引用的案例檔會讓已交對照失效

- Scope: global
- Author: holylight
- Source: track-data-root-2 A8 實走 006（session 616e4407）2026-10-14
- Confidence: [臨]
- Trigger: 子代理改碼, SubagentStop, agent_modified_files, 子代理 定位三行, 子代理 Write 被擋, 對照證據失效, 案例檔不在磁碟上, A8 實走
- Created-at: 2026-10-14
- Related: 寫碼查核擋滿後要等人時立刻發askuserquestion停住-靠結束回合等會每回合再被擋一次次數累加-派工單寫走到要問那步停下要先確認人在或直接發題掛著, worktree隔離session改部位檔被overviewhub閘連擋-證據只認read事件與bash註解三行-git-c-live與python-heredoc與變數路徑一律被拒

## 知識

- [臨] 派子代理在部位表管到的目錄寫程式檔，它第一次 Write 就被 OverviewHub 擋「還沒交出定位三行（注入導讀卡後讀了 17 個檔）」，但子代理自己一個檔都沒讀：讀檔計數是主 session 的帳，定位行卻要子代理自己交。把定位四行（含目標節點）寫進派工 prompt、要它先放進一個 Bash 註解再 Write，就過了。
- [臨] 子代理改了碼又沒驗證時，它自己的收尾會被 SubagentStop 擋到底（訊息標「無法互動，不能放行……（子代理 Stop）」，實測同一則擋 9 次、用掉 7 萬多 token）。主 session 之後宣告完成也會被 (d) 擋，但擋訊息只寫「改了程式碼（檔名）」，不說是子代理改的；歸屬只在 state 的 agent_modified_files[<agentId>] 看得到，同一筆也進主帳 modified_files。派子代理改碼時，案例與量尺要寫進它的任務，否則它會在收尾空轉。
- [臨] 完整對照（need_goal reconcile）引用的案例檔之後被刪，Stop 的 (f2) 會把已交的對照判成缺證據（「驗證案例 <路徑> 不在磁碟上」），要用還存在的證據（改動之後跑的收據、仍在的檔）重交一次對照。拋棄式探針與案例實走完要刪時，對照的證據就不要指到它們。

## 行動

- 派子代理在部位目錄寫碼：prompt 附定位四行要它先放 Bash 註解，並交代它補案例、跑量尺
- 查「是不是子代理改的」：看 state 的 agent_modified_files，不看主 session 擋訊息
- 要刪對照引用過的案例檔：刪完用仍在的證據重交 reconcile


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（OverviewHub 定位行寫入閘與需求目標樹完整對照 f2）已從寫碼守門拔除；SubagentStop 與 agent_modified_files 那段仍有效，已併入「子代理的對話紀錄是獨立檔」卡 | memory-audit --delete |
