# git 合併與換行的實證事實-text-auto 不回頭轉-stage 方向-孤立 CR 是 binary-driver 缺 command 會 fatal

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: text=auto, eol=lf, renormalize, gitattributes, merge driver, stage 2, stage 3, ls-files -u, rebase ours theirs, cherry-pick 衝突, 孤立 CR, lone CR, ignore-cr-at-eol, lacks command line, add/add, stash pop 衝突, MERGE_HEAD
- Created-at: 2026-09-03
- Related: 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合, sed-i-在-crlf-repo-會整檔改換行

## 知識

- [臨] `* text=auto eol=lf` 只對 git 判為文字的檔生效；index 已經是 CRLF 的檔，plain `git add` **不會**回頭轉（安全閥），要 `git add --renormalize` 或先把工作樹改成 LF 再 add。含孤立 `\r`（非 CRLF）的檔 git 視為 binary 不轉；`git diff --ignore-cr-at-eol` 也看不掉孤立 CR 的差異（要驗「純換行 commit」用位元組去 CR 後比對）。
- [臨] 衝突是否解除看 index 有無 unmerged stage（`git ls-files -u`），不看工作樹有無 `<<<<<<<`。stage 1=base、2=目前 HEAD、3=被合入側；**rebase／cherry-pick 時 HEAD 是 upstream／新基底，stage 3 才是自己正在重放的 commit**（ours/theirs 與 merge 相反）。add/add 沒有 stage 1；delete/modify 缺 stage 2 或 3；stash pop 衝突沒有 MERGE_HEAD（判衝突狀態要靠 ls-files -u，不要靠 .git/MERGE_HEAD）。
- [臨] merge driver 執行當下工作樹只有 HEAD 那側的檔（merge 缺對方新檔、rebase 缺自己新檔），driver 內不能靠磁碟重建；它拿到的 %O %A %B 三份 blob 才是完整資訊。git config 只有 `merge.<x>.name` 沒有 `.driver` 時，任何 merge 直接 fatal「custom merge driver <x> lacks command line」（安裝順序要先 driver 後 name；移除用 --remove-section）。驅動未定義時 git 靜默退回逐行三方，不報錯。

## 行動

- 要把既有 CRLF 檔改 LF：先改工作樹位元組再 add，或 `git add --renormalize`；驗純換行用 `git show HEAD:p` 與 `:0:p` 去 CR 後比對
- 寫自動解衝突工具：用 `git ls-files -u -z` 取 stage，依操作別分清 stage 2/3 誰是誰，缺 stage 的檔列 skipped 不臆測
- 裝 merge driver：driver 先、name 後；測試要制造「沒裝」情境用 `git config --remove-section merge.<x>`，不要只 unset driver
