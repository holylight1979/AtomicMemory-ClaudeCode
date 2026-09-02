# 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 索引衝突, _atom_index.json 衝突, MEMORY.md 衝突, _ATOM_INDEX.md 衝突, merge driver, 合併驅動, rebase 衝突, pull --rebase 衝突, CRLF 衝突, 索引三檔, merge-atom-index, gitattributes
- Created-at: 2026-09-02
- Related: git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [臨] 現象：兩台機器各自新增 atom 後 pull --rebase／merge，atom 本體不衝突，但索引三檔（MEMORY.md 範疇計數表、_ATOM_INDEX.md、_atom_index.json）在同區塊各加一列必衝突。另一型：某機把 _atom_index.json 寫成 CRLF（lib 寫檔沿用既有行尾，翻了就黏住）→ 兩側行尾不同、2800 行整檔衝突（專案 repo 實例 5d92e64 對 3af00d1；469875e 已是第二次）。
- [臨] 正解不是手合、也不是「合併時從磁碟重建索引」：merge driver 執行當下工作樹只有 HEAD 那側的 atom 檔（merge 缺對方新檔、rebase 缺自己新檔，實測），磁碟重建會把另一側弄丟。`~/.claude/tools/merge-atom-index.py` 拿三份 blob 做語意三方（JSON 以 path 為 key 逐條合、_ATOM_INDEX.md 表列同鍵、MEMORY.md 範疇計數 = ours + theirs − base），配 attributes `text eol=lf` 讓 blob 永遠 LF。
- [臨] 每台機器各裝一次（merge driver 是 git config 機器級設定，版控帶不動）：`python ~/.claude/tools/merge-atom-index.py --install`；`--status` 查。沒裝時 git 靜默退回逐行三方 → 又見索引三檔衝突 ＝ 那台沒裝。根層 repo 靠 ~/.claude/.gitattributes，專案 repo 靠全域 attributes 的 `**/.claude/memory/*` 規則，專案不必改任何檔。

## 行動

- 專案 session 遇索引三檔衝突：先 `python ~/.claude/tools/merge-atom-index.py --status`；未裝 → `--install`，然後 `git rebase --abort`／`git merge --abort` 重來一次即自動合；已裝仍衝突 → 看 stderr `[merge-atom-index]` 那行（真衝突只會落在 MEMORY.md 人寫段落）。
- 若已手合過：`python ~/.claude/tools/sync-atom-index.py --memory-dir <proj>/.claude/memory --fix-scope-from-path` 清懸空條目、`sync-memory-index.py --memory-dir <同上> --write` 重算計數。
