# gitignore未釘根層的規則在不分大小寫檔案系統會吃掉同名開頭的檔-IDENTITY-星號md誤傷identity開頭的atom

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: gitignore, core.ignorecase, 被忽略的 atom, 索引有檔案沒有, broken_refs, _INDEX.md drift, 乾淨 clone 索引不一致, check-ignore
- Created-at: 2026-10-05

## 知識

- [臨] 實查 2026-10-05：`.gitignore` 寫 `IDENTITY-*.md`（沒有開頭的 `/`）會套到整棵樹；Windows／macOS 預設 `core.ignorecase=true`，所以 `memory/<範疇>/identity-….md` 這類 atom 也被忽略——本機索引有它、檔案卻進不了版控，其他機器與乾淨 clone 的索引檢查因此報 drift，而本機檢查永遠是一致的。
- [臨] 只該在根層生效的規則一律寫成 `/檔名`。診斷：`git status --short --ignored -- <目錄>` 看 `!!` 列，或 `git check-ignore -v <路徑>` 直接問是哪一條規則。「本機一致、乾淨 clone 不一致」的索引問題先懷疑有檔案被忽略。

## 行動

- 新增 gitignore 規則前先想它該不該套到子目錄；根層專用就加開頭斜線
- 索引與檔案對不上時用 git status --ignored 找被忽略的 atom
