# 全量驗證與agent測試並行跑會互相干擾出假失敗-作準的全量要單獨跑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: run_verify, 全量驗證, flake, 假失敗, 並行 pytest, agent 跑測試, 跑序相依, 單跑會過, 共用 tmp
- Created-at: 2026-10-01
- Related: feedback-completion-gates, 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源
- Source: session:a7ac6c34#b5e73654 2026-10-01
- Quote: 「反正你也閒著(?XD) 可以上GIT的就先上。」

## 知識

- [臨] 2026-10-01 兩次全量 run_verify 各失敗 1 案（tools/verify/verify_atom_categorize、verify_merge_atom_index 不同案），單跑、整檔跑、整目錄跑全過；共同點是當時有 sub-agent 在同一個 repo 同時跑 pytest。等 agent 全部收工後單獨跑一次 → 2167 passed 零失敗。
- [臨] 判法：全量失敗案單跑就過、且每次失敗的是不同案 → 先疑並行干擾（共用 %TEMP%、共用全域 git 設定、共用 workflow/ 執行期檔、index.lock），不要先去改測試或程式。作準的全量驗證一律在沒有其他 agent 跑測試時單獨跑。
- [臨] 總控台多 worktree 合併夜實證三次：live 全量期間在 worktree 跑目標 pytest 或 codex 審查（codex 會自己跑小量 pytest），全量各紅一案（verify_atom_categorize 的 undo 案、verify_merge_atom_index 的 resolve 案——都做真實 git／tmp 目錄操作），單獨重跑都綠；第三次把全量單獨跑 2495 案 0 失敗。另：`run_verify.py` 不認 `--help`，打了就整套跑起來，是當晚一次干擾源。

## 行動

- 派了會跑 pytest 的 agent 時，不要同時跑 run_verify；等全部回報再單獨跑一次作準
- 全量有失敗案：先單跑該案與該檔，都過就記為並行干擾，不改碼
