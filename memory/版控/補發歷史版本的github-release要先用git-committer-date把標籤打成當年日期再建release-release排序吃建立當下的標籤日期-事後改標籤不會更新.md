# 補發歷史版本的GitHub-Release要先用GIT_COMMITTER_DATE把標籤打成當年日期再建Release-Release排序吃建立當下的標籤日期-事後改標籤不會更新

- Scope: global
- Author: holylight
- Source: 2026-11-03 原子記憶系統 v1.0～v6.1 release notes 發布
- Confidence: [臨]
- Trigger: GitHub Release, gh release create, release notes, 歷史版本, 補標籤, GIT_COMMITTER_DATE, release 排序, tagger date, Latest
- Created-at: 2026-11-03

## 知識

- [臨] 實測（2026-11）：GitHub Releases 頁與 API 依 release 的 created_at 排序，created_at 取的是建立 release 當下那個標籤的日期（annotated tag 的 tagger date）。今天才補打的舊版本標籤日期都是今天，會排在既有舊標籤前面、順序亂掉。
- [臨] 事後用 git tag -a -f 改日期再 force push，已建好的 release 的 created_at 不會跟著變；要刪掉 release（不刪標籤）重建才會讀到新日期。
- [臨] 做法：補歷史版本時先 `GIT_COMMITTER_DATE=<當年發布日> git tag -a <tag> <commit> -m ...` 再推標籤、最後才 gh release create；最新那版加 --latest、其餘 --latest=false。GitLab Releases API 另有 released_at 欄可直接標歷史日期。

## 行動

- 補發多個歷史版本的 Release 前，標籤先用 GIT_COMMITTER_DATE 打成當年日期，再建 Release
- 排序已亂時：重打標籤日期＋刪 release（保留標籤）重建，不要只改標籤
