# 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 索引衝突, _atom_index.json 衝突, MEMORY.md 衝突, _ATOM_INDEX.md 衝突, merge driver, 合併驅動, rebase 衝突, pull --rebase 衝突, CRLF 衝突, 索引三檔, merge-atom-index, gitattributes, --resolve, IndexConflict, MergeDriver, svn update 衝突, svn resolve, svn:eol-style
- Created-at: 2026-09-02
- Related: git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, repo-全面-lf-決策與守衛鏈, workflow-svn

## 知識

- [臨] 現象：兩台機器各自新增 atom 後 pull --rebase／merge／svn update，atom 本體不衝突，但索引三檔（MEMORY.md 範疇計數表、_ATOM_INDEX.md、_atom_index.json）在同區塊各加一列必衝突；另一型是一側索引檔被寫成 CRLF → 整檔衝突（專案 repo 實例 5d92e64 對 3af00d1、469875e）。
- [臨] 正解＝三層防線，不手合、不在 driver 內從磁碟重掃（driver 執行當下工作樹只有 HEAD 側 atom，重掃丟另一側）：(1) 全 repo LF（.gitattributes `* text=auto eol=lf`、寫檔一律 `lib.atom_io.write_text_lf`、巡檢 `normalize-eol.py --root --check`；專案記憶樹由 `sync-memory-index.py` 專案模式 `--write` 後自動轉 LF＋git `.gitattributes` 區塊／svn `svn:eol-style=LF`，不靠人貼 prompt）；(2) `~/.claude/tools/merge-atom-index.py` 註冊為 git merge driver `atomindex` 做語意三方（JSON 以 path 為 key 逐條合、triggers 聯集、MEMORY.md 範疇計數 = ours+theirs−base），PreToolUse 在 CC 跑 `git pull/merge/rebase/cherry-pick/stash pop` 前自動 `--install`（訊息 `[Guardian:MergeDriver]`）；(3) 備案 `--resolve`：git → 套在三檔的 stage（:1 base／:2 HEAD／:3 對方；rebase 時 :2 是 upstream＝同事那邊）上寫回並 git add，PreToolUse 在 `git rebase --continue / merge --continue / cherry-pick --continue / commit / stash pop` 前自動跑；SVN → 拿 svn update 留下的 `.mine`（ours）／`.r舊`（base）／`.r新`（theirs；路徑取自 `svn info --xml`）跑同一套驅動、寫回、`svn resolve --accept working`，PreToolUse 在 `svn commit / ci / resolve` 前自動跑（`svn update` 本身不自動：SVN 無驅動可裝，TortoiseSVN 停在衝突屬正常）。訊息皆 `[Guardian:IndexConflict]`。只碰路徑在 memory 樹的三檔；svn 只掃 memory dir 候選不掃整個 WC（大 WC 的 svn status 要 3～6 秒）。config `merge_driver.{auto_install,auto_resolve}`、`eol.auto_normalize_project` 預設 true。細節 `_AIDocs/MultiMachineMemorySync.md`。
- [臨] 殘留只會是 MEMORY.md 表外手寫段兩側同改：驅動寫回含 `<<<<<<<` 標記的結果、不 add／不 resolve、列 remaining，交正在 pull／update 的 CC 依方向看內容判斷（不選邊）。git 分支只在工作樹仍等於原始衝突輸出時覆蓋；svn 沒有 stage 可重建，仍含標記就當未動過（人解一半又留著標記會被蓋）。不在保證範圍：checkout 還是舊 hook、驅動裝好前 CC 以外的 git pull 停一次、svn tree/property conflict、TortoiseSVN 衝突檔命名未實測（路徑取自 svn info 不依賴檔名）。

## 行動

- 專案 session 遇索引三檔衝突：git 直接 `git rebase --continue`、svn 直接 `svn commit`（hook 會先自動 --resolve 並回報），或手動 `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <repo 或 svn 工作副本>`；有 remaining → 開該檔看標記判斷後 git add／清掉標記再 svn commit；其他非索引檔衝突照常處理。
- 自檢 `python ~/.claude/tools/merge-atom-index.py --status` 末行「已安裝」；專案記憶樹想立刻釘 LF：`python ~/.claude/tools/normalize-eol.py --memory-dir <proj>/.claude/memory --auto`（平常不必，atom 寫入後自動）；三檔全被改壞的最後手段（rebase --continue 前、工作樹已含兩側 atom 時）：`sync-atom-index.py --memory-dir <dir> --add-from-frontmatter --fix-scope-from-path` + `sync-memory-index.py --memory-dir <dir> --write` 後 git add。
