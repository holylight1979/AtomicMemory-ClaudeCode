# vcs-sync拉取側機制指標與踩坑-隔離worktree-recover持久化-新編輯保護-冷卻

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: vcs-sync 拉取, _git_pull, 隔離 worktree, recover.json, .behind, pull_error, _git_new_edits, pull 冷卻, 記憶層落後, 自動拉取, update-ref CAS, restore --source
- Created-at: 2026-10-01
- Related: knowledge-harvest-階段收割與vcs-sync機制指標與踩坑, 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a
- Source: session:a7ac6c34#b5e73654 2026-10-01
- Quote: 「反正你也閒著(?XD) 可以上GIT的就先上。」

## 知識

- [臨] **SoT**：`hooks/wg_vcs_sync.py`（`_git_pull`、`_git_cas_and_restore`、`_git_restore_mem`、`_git_new_edits`、`_git_isolated_rebase`、`svn_update_targets`）、`hooks/handlers/session_start.py`（`_spawn_pull_sync`、`_pull_advisory_lines`）；行為權威 `_AIDocs/MultiMachineMemorySync.md` 自動拉取節、TECH.md §6.3；執行期檔 `workflow/vcs-sync/<hash>.{behind,recover.json}`、roots.json 拉側欄位。
- [臨] **共用工作樹上永遠不自動 rebase／autostash**：worker 的鎖只互斥合作 worker，擋不住別的 session 同時寫檔；autostash 還原不保證 staged／unstaged 分界、abort 不是交易。所以整合全在暫時 detached worktree 做，主樹只有兩種寫入：`update-ref`（CAS）與記憶 pathspec 的 `restore --source --staged --worktree`。
- [臨] **ref 已換、restore 沒跟上＝最危險的半套狀態**：index 相對新 HEAD 會出現反向 staged（上游新檔變 staged deletion），下一輪普通 commit 會把上游撤回。對策：update-ref 前先落 `.recover.json`，restore 成功才刪；檔在時任何分支都不 commit／push，每輪先試恢復；restore 拋例外與回傳非零同樣處理（Codex 第四輪抓到的漏洞）。
- [臨] **restore 前三驗**：symbolic HEAD 仍在該分支；HEAD＝to 或是 to 的後代（別人又 commit 了就改以 HEAD 為來源，否則會製造反向 staged）；`_git_new_edits` 逐檔比對工作樹／index 與 from／目標樹，兩者皆不符就是有人在改，不覆蓋；未追蹤檔若與上游新增檔同名也算（git diff 看不到未追蹤檔）。index.lock 重試每次都重做三驗。
- [臨] **svn 不能先 update 再說**：update 會把 missing 檔補回，已退役但尚未 schedule-delete 的 atom 會復活；先對 validated 退役的 missing 做 `svn delete`，其他 missing 存在就不自動 update。
- [臨] **拉入的 atom 下一個 session 才進候選池**（池在 SessionStart 建一次）；advisory 只報同步事實，不宣稱「本 session 已載入」。純 pull 請求有冷卻（`vcs_sync.pull.cooldown_s`），多 session 同時開不會每個都 fetch。

## 行動

- 改拉取側前先讀 MultiMachineMemorySync.md 自動拉取節與本顆；主樹只准 update-ref 與記憶 pathspec restore
- 看到 `.behind`／`.recover.json`：先讀裡面的 reason，再決定是人手 pull --rebase 還是 `git restore --source=HEAD --staged --worktree -- memory`
- 加新的主樹寫入路徑前，先問：失敗在哪一步會留下半套狀態？有沒有標記讓下一輪先恢復？
