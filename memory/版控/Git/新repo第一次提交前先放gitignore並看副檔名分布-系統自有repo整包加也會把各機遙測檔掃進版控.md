# 新repo第一次提交前先放gitignore並看副檔名分布-系統自有repo整包加也會把各機遙測檔掃進版控

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 新 repo, 第一次提交, gitignore, access.json, git rm --cached, 整包加入, 公司記憶 repo, repo 永遠髒, 誤提交
- Created-at: 2026-10-05
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [臨] 實踩（2026-10-05）：新建的公司記憶 repo 沒有 `.gitignore`，我以「這是系統自有的 repo、整包加沒關係」為由兩次用 `git add -A` 提交，把 25 個各機使用遙測檔 `*.access.json` 掃進版控。背景 vcs-sync 又排除這類檔（`vcs_sync.exclude`），結果 repo 永遠有未提交變更、多機會互撞；事後另開 commit `git ls-files -z -- '*.access.json' | xargs -0 git rm -q --cached --` 補救（本機檔保留）。
- [臨] 規則：「勿整包加入」不分 repo 歸屬。新 repo 第一次提交前先做兩件事：① 放好 `.gitignore`（記憶 repo 至少 `**/*.access.json`；`tools/org-memory.py --init` 現已自動寫入，守門 `verify_org_layer::test_init_tree_ignores_access_sidecars`）；② 看 `git status --porcelain` 的副檔名分布，有非預期類型就先處理。慢點的對照法：看同類型的既有 repo 追蹤了什麼（SGI 專案 0 個 access.json 被追蹤）。

## 行動

- 任何 repo 提交一律列明路徑 staging
- 新 repo 首次提交前：先 .gitignore、再看副檔名分布
- 已誤提交的檔：開新 commit 用 git rm --cached 移出，不改寫已推的歷史
