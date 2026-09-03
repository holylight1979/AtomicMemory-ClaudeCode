# svn測試與hook的三個實測事實-diff3相鄰改動自合-整WC status爆預算-只信xml輸出

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn 測試, svnadmin, svn status 耗時, svn diff3, Text conflicts, svn --xml, svn fixture, memory_dir_candidates
- Created-at: 2026-09-03
- Related: 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合, hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定, 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源

## 知識

- [臨] 始末：為 merge-atom-index --resolve 補 SVN 分支時，把 git 版 fixture（一側改 `| Server | 1 |`→2、另一側在其後插 `| Tools | 1 |`）搬到 svnadmin 本地倉，預期三檔衝突卻只出 2 個 C——MEMORY.md 被 svn 標 G（自動合併）。根因：svn 的 diff3 把「改第 N 行」與「在第 N 行後插入」視為不重疊 hunk 直接合，git 的 merge 把相鄰改動算衝突；兩套 VCS 對同一組輸入的判定不同，測 svn 不能沿用 git 的衝突樣本。正解：兩側都改同一列（a 加兩顆→Server 3、b 加一顆→Server 2）才會 Text conflicts: 3，語意合併期望值變 3+2−1=4。
- [臨] 整個工作副本的 `svn status --xml` 是 O(檔數)：本機 d:\MyDev 5.6s、c:\Projects\Tools 2.9s，直接爆 PreToolUse 2.5s 預算；memory dir 只要 0.2s。所以 hook 與 --resolve 都只掃 `wg_core.memory_dir_candidates`（walk-up `.claude/memory`＋根層 `memory/`＋登記專案），不掃整個 WC。svn info --xml 一次可帶多 target（0.19s），resolve 0.1s；整鏈實測 2.16s。
- [臨] svn 純文字輸出走 locale（Windows＝cp950），非 ASCII 路徑會變亂碼；`--xml` 輸出一律 UTF-8 且路徑含反斜線與 `\r`——只信 --xml、用 xml.etree 解、路徑用 Path().resolve().relative_to(root).as_posix() 正規化。propset：明列 unversioned target rc 1（先 `status -v --xml` 濾已版控）、混行尾檔被拒 E135000（先轉 LF 再設）、同值重設 svn 自動 no-op 不標 M。
- [臨] 設計原理：SVN 沒有 client 端可安全掛的 merge driver（全域 diff3-cmd 會套到所有檔、TortoiseSVN 未必吃），所以 update 停在衝突屬正常，備案放在 CC 下 `svn commit/resolve` 前；三份輸入不猜 `.rN` 檔名，取 `svn info --xml` `<conflict type="text">` 的 prev-wc-file／prev-base-file／cur-base-file；沒有 stage 可重建原始輸出 → 仍含 `<<<<<<<` 就當未動過（文件列為邊界）。

## 行動

- 寫 svn 衝突測試：兩側必須改同一行才會真衝突；先用 svnadmin 本地倉實跑一次看 `Text conflicts: N` 再寫斷言。
- hook 內任何 svn 子行程只對 memory dir 候選跑、只用 --xml；預算題用 verify_merge_driver_gate 的兩次取最快樣板守。
