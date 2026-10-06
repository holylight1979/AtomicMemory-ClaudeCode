# vcs-sync的git-add兩個真實環境失敗-已追蹤但被gitignore蓋到的檔刪除要加-f-前一輪已stage的刪除不得再add

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: vcs-sync, git add 失敗, did not match any files, paths are ignored, memory/personal, role.md, wg_vcs_sync, 已 staged, unpushed 標記, 背景 commit 卡住
- Created-at: 2026-10-01
- Source: session:d892b7c9#160556c3 2026-10-01
- Quote: 「你會繼續推進到全部完工吧?」

## 知識

- [臨] 始末（2026-10-01）：刪了根層 `memory/personal/holylight/role.md`（已追蹤但路徑被 `.gitignore` 的 `memory/personal/` 蓋到）後，vcs-sync worker 每輪都停在「git add 失敗」、留 `.unpushed` 標記，記憶庫背景同步整個停擺。
- [臨] 兩層根因（tmp repo 重現）：① `git add -A -- :(literal)<已刪的追蹤檔>` 對被 ignore 的路徑回 rc=1「paths are ignored」——但刪除其實已 stage 進 index；② 下一輪該 path 既不在工作樹也不在 index，再 add 回 rc=128「did not match any files」。兩種訊息同一件事的兩個階段。
- [臨] 修法（`hooks/wg_vcs_sync.py _git_sync_body`）：`_git_changed_files` 改回 `(xy, path)`；只對 Y 欄非空白（工作樹仍與 index 不同）的項 `git add -A -f`，已 staged 的項直接進 commit pathspec。`-f` 不會順手加進被忽略的未追蹤檔，因為 specs 只含 status 列出的變更檔（`!!` 已濾）。回歸案 `verify_vcs_sync_worker.py::test_git_tracked_but_ignored_file_deleted_is_committed`、`::test_git_already_staged_deletion_is_committed`。
- [臨] 配套踩坑：`hooks/verify/verify_unpushed_advisory.py` 只 monkeypatch `CLAUDE_DIR`，但 `_unpushed_advisory()` 會掃真實 `workflow/vcs-sync/roots.json` 列的每個 root，本機一有 `.unpushed` 標記測試就紅→ fixture 要連 `wg_vcs_sync.load_roots` 一起 monkeypatch 成 `{}`。

## 行動

- worker 卡在 git add 失敗 → 先 `git status --porcelain -- memory` 看是否有 `D ` 或被 ignore 的追蹤檔，再看 `.unpushed` 標記的 reason
- 要刪記憶目錄下被 ignore 但已追蹤的檔：直接刪即可（worker 現已能處理），不需手動 git rm
- 寫任何讀 roots.json 的 advisory 測試：連 load_roots 一起隔離
