# 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 索引衝突, _atom_index.json 衝突, MEMORY.md 衝突, _ATOM_INDEX.md 衝突, _INDEX.md 衝突, _local_catalog.md 衝突, merge driver, 合併驅動, rebase 衝突, pull --rebase 衝突, CRLF 衝突, 索引三檔, merge-atom-index, gitattributes, --resolve, IndexConflict, MergeDriver, svn update 衝突, svn resolve, svn:eol-style
- Created-at: 2026-09-02
- Related: git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, repo-全面-lf-決策與守衛鏈, workflow-svn

## 知識

- [臨] 現象：兩機各加 atom 後 pull --rebase／merge／svn update，atom 本體不衝突，索引檔（MEMORY.md、_ATOM_INDEX.md、_atom_index.json；根層還有各層 _INDEX.md、_local_catalog.md）在同區塊各多一列必衝突；另一型是一側寫成 CRLF → 整檔衝突。
- [臨] 正解＝三層防線，不手合、不在 driver 內從磁碟重掃（執行當下工作樹只有 HEAD 側 atom）：(1) 全 repo LF（.gitattributes eol=lf、write_text_lf、normalize-eol --check；專案記憶樹由 sync-memory-index 專案模式 --write 後自動轉 LF＋git .gitattributes／svn eol-style）；(2) tools/merge-atom-index.py 註冊為 git merge driver atomindex 做語意三方（JSON 以 path 為鍵、triggers 聯集、計數 o+t−b；_INDEX.md／_local_catalog.md 走通用表格文件三方，根層 .gitattributes 綁），PreToolUse 在合併類 git 指令前自動 --install；(3) 備案 --resolve：git 套在 stage 上寫回並 add（rebase/merge/cherry-pick --continue、commit、stash pop 前自動）；SVN 拿 .mine／.r舊／.r新（路徑取自 svn info --xml）跑同一套、svn resolve --accept working（svn commit/ci/resolve 前自動；svn update 本身不自動、只掃 memory dir 候選）。訊息 [Guardian:MergeDriver]／[Guardian:IndexConflict]；config merge_driver.*、eol.auto_normalize_project。細節 _AIDocs/MultiMachineMemorySync.md。
- [臨] 殘留只會是表外手寫段兩側同改：留標記、不 add／不 resolve、列 remaining，交人判斷不選邊；git 只在工作樹仍等於原始衝突輸出時覆蓋，svn 仍含標記就當未動過。仍逐行衝突（撞到再做）：同一顆 atom 兩機各 append、_meta/*-learned.json。不保證：舊 hook checkout、驅動裝好前 CC 外 pull、svn tree/property conflict、TortoiseSVN 命名未實測。

## 行動

- 遇索引檔衝突：git 直接 `git rebase --continue`、svn 直接 `svn commit`（hook 先自動 --resolve），或手動 `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <repo 或 svn WC>`；有 remaining → 開檔判斷後 git add／清標記再 svn commit。
- 自檢 `merge-atom-index.py --status` 末行「已安裝」；專案樹立刻釘 LF：`normalize-eol.py --memory-dir <mem> --auto`；三檔全壞的最後手段（rebase --continue 前、工作樹已含兩側 atom）：`sync-atom-index.py --memory-dir <dir> --add-from-frontmatter --fix-scope-from-path` + `sync-memory-index.py --memory-dir <dir> --write` 後 git add。
