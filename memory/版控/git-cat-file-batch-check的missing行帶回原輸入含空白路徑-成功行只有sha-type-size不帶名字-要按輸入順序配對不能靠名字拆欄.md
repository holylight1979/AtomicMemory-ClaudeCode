# git-cat-file-batch-check的missing行帶回原輸入含空白路徑-成功行只有sha-type-size不帶名字-要按輸入順序配對不能靠名字拆欄

- Scope: global
- Author: holylight
- Source: track-gate-small-fixes 004 交付信代寫 2026-10-21
- Confidence: [臨]
- Trigger: cat-file --batch-check, git 批次查詢, missing 行, 按輸入順序配對
- Created-at: 2026-10-21

## 知識

- [臨] `git cat-file --batch-check` 的 missing 行會帶回原輸入（含空白的路徑），成功行只有 sha、type、size、不帶名字；解析要按輸入順序配對，不能靠名字拆欄。每個 git 根固定 3 支（batch-check、hash-object、cat-file --batch）就能取代每檔一支 git show。

## 行動

- （依知識內容判斷）
