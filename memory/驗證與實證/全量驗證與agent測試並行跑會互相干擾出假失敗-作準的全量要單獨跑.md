# 全量驗證與agent測試並行跑會互相干擾出假失敗-作準的全量要單獨跑

- Scope: global
- Author: holylight
- Source: session:a7ac6c34#b5e73654 2026-10-01
- Quote: 「反正你也閒著(?XD) 可以上GIT的就先上。」
- Confidence: [臨]
- Trigger: run_verify, 全量驗證, flake, 假失敗, 並行 pytest, agent 跑測試, 跑序相依, 單跑會過, 共用 tmp
- Created-at: 2026-10-01
- Related: feedback-completion-gates, 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源, 總控台多軌合併經驗-退回同一面第二次就定死規則或改設計-整批合併後的紅先單跑歸軌補修不reset-接續單要寫舊步驟作廢與停工恢復條件, feedback-全量測試從流程拔掉改增量待補-全量紅了指不出誰修修完又要全量-收尾跑llm適度擴展的可能相關清單

## 知識

- [臨] 2026-10-01 兩次全量 run_verify 各失敗 1 案（tools/verify/verify_atom_categorize、verify_merge_atom_index 不同案），單跑、整檔跑、整目錄跑全過；共同點是當時有 sub-agent 在同一個 repo 同時跑 pytest。等 agent 全部收工後單獨跑一次 → 2167 passed 零失敗。
- [臨] 判法：全量失敗案單跑就過、且每次失敗的是不同案 → 先疑並行干擾（共用 %TEMP%、共用全域 git 設定、共用 workflow/ 執行期檔、index.lock），不要先去改測試或程式。作準的全量驗證一律在沒有其他 agent 跑測試時單獨跑。
- [臨] 多 worktree 合併時實證三次：live 全量期間在 worktree 跑目標 pytest 或 codex 審查（codex 會自己跑小量 pytest），全量各紅一案（verify_atom_categorize 的 undo 案、verify_merge_atom_index 的 resolve 案——都做真實 git／tmp 目錄操作），單獨重跑都綠；第三次把全量單獨跑 2495 案 0 失敗。另：`run_verify.py` 不認 `--help`，打了就整套跑起來，是當晚一次干擾源。
- [臨] 更糟的一種：兩支背景驗證腳本共用同一棵 git 快照樹，後起的那支 `git checkout` 會把檔案換掉，前一支還在跑的 pytest 就測到新舊混合的程式碼（pytest 不改追蹤檔，`git status` 乾淨檢查攔不住）。腳本開頭寫鎖檔（不追蹤的 `.snapshot-running`，有就退出）、trap 收尾刪除，再讓 checkout 在鎖內做。
- [臨] 全量已從流程拔掉（使用者裁定，全量改增量待補）：不再有「作準的全量」要清場單獨跑；本卡的並行干擾判法（單跑該案與該檔都過就記並行干擾）仍適用於增量清單裡的計時案。見 [[feedback-全量測試從流程拔掉改增量待補-全量紅了指不出誰修修完又要全量-收尾跑llm適度擴展的可能相關清單]]

## 行動

- 派了會跑 pytest 的 agent 時，不要同時跑 run_verify；等全部回報再單獨跑一次作準
- 全量有失敗案：先單跑該案與該檔，都過就記為並行干擾，不改碼
