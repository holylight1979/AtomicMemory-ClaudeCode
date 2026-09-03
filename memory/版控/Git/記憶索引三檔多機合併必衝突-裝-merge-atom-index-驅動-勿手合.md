# 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 索引衝突, _atom_index.json 衝突, MEMORY.md 衝突, _ATOM_INDEX.md 衝突, merge driver, 合併驅動, rebase 衝突, pull --rebase 衝突, CRLF 衝突, 索引三檔, merge-atom-index, gitattributes, --resolve, IndexConflict, MergeDriver
- Created-at: 2026-09-02
- Related: git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, repo-全面-lf-決策與守衛鏈, git-合併與換行的實證事實-text-auto-不回頭轉-stage-方向-孤立-cr-是-binary-driver-缺-command-會-fatal

## 知識

- [臨] 現象：兩台機器各自新增 atom 後 pull --rebase／merge，atom 本體不衝突，但索引三檔（MEMORY.md 範疇計數表、_ATOM_INDEX.md、_atom_index.json）在同區塊各加一列必衝突；另一型是一側索引檔被寫成 CRLF → 整檔衝突（專案 repo 實例 5d92e64 對 3af00d1、469875e）。
- [臨] 正解＝三層防線，不手合、不在 driver 內從磁碟重掃（driver 執行當下工作樹只有 HEAD 側 atom，重掃丟另一側）：(1) 全 repo LF（.gitattributes `* text=auto eol=lf`、寫檔一律 `lib.atom_io.write_text_lf`、巡檢 `normalize-eol.py --root --check`）；(2) `~/.claude/tools/merge-atom-index.py` 註冊為 git merge driver `atomindex` 做語意三方（JSON 以 path 為 key 逐條合、triggers 聯集、MEMORY.md 範疇計數 = ours+theirs−base），PreToolUse 在 CC 跑 `git pull/merge/rebase/cherry-pick/stash pop` 前自動 `--install`（訊息 `[Guardian:MergeDriver]`）；驅動在 git 全域設定裡，所以 Fork 等外部 pull 裝好後也受益；(3) 備案 `--resolve`：把同一套驅動套在三檔的 stage（:1 base／:2 HEAD／:3 對方；rebase 時 :2 是 upstream＝同事那邊、:3 才是自己重放的 commit）上寫回並 git add，PreToolUse 在 `git rebase --continue / merge --continue / cherry-pick --continue / commit / stash pop` 前自動跑（訊息 `[Guardian:IndexConflict]`）；只碰路徑在 memory 樹且 check-attr merge=atomindex 的三檔，只在工作樹仍等於 git 原始衝突輸出時覆蓋。config `workflow/config.json` `merge_driver.{auto_install,auto_resolve}` 預設 true。細節 `_AIDocs/MultiMachineMemorySync.md`。
- [臨] 殘留只會是 MEMORY.md 表外手寫段兩側同改：驅動寫回含 `<<<<<<<` 標記的結果、不 add、列 remaining，交正在 pull 的 CC 依 stage 方向看內容判斷（不選邊）。不在保證範圍：checkout 還是舊 hook（上線一次性：`cd ~/.claude && git pull` 後跑一次 `python tools/merge-atom-index.py --install`）、驅動裝好前 CC 以外的 pull 停一次、git plumbing 寫入、他機 repo-local attributes 覆寫、無 CI。

## 行動

- 專案 session 遇索引三檔衝突：直接 `git rebase --continue`（hook 會先自動 --resolve 並回報），或手動 `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <repo>`；有 remaining → 開該檔看標記判斷後 git add 再 continue；其他非索引檔衝突照常處理。
- 自檢 `python ~/.claude/tools/merge-atom-index.py --status` 末行「已安裝」；三檔全被改壞的最後手段（rebase --continue 前、工作樹已含兩側 atom 時）：`sync-atom-index.py --memory-dir <dir> --add-from-frontmatter --fix-scope-from-path` + `sync-memory-index.py --memory-dir <dir> --write` 後 git add。
