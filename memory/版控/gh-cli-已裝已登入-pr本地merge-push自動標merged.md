# gh-cli-已裝已登入-PR本地merge-push自動標merged

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: gh, gh cli, pull request, PR, 合併 PR, github api, merge, 審 PR
- Created-at: 2026-09-02

## 知識

- [臨] 本機已裝 gh CLI（winget GitHub.cli v2.98.0，MSI 寫入 machine PATH）且已 gh auth login（keyring、repo scope）。GitHub PR/issue 操作直接用 gh，不必繞 api.github.com + Invoke-RestMethod。安裝前開啟的舊 session 叫不到 gh → 先刷 PATH（Machine+User 合併）再叫。
- [臨] 無 gh 時替代流程實證可行：git fetch origin pull/N/head → 本地 merge 解衝突 → push base 分支；PR head sha 進入 base 後 GitHub 自動標 merged 並關閉，全程不需 API 寫入權限。
- [臨] 審 PR 前先 git ls-tree HEAD <檔> 比對 PR base blob：blob 相同＝該檔可乾淨套用、衝突必在其他檔，省下逐檔比對。

## 行動

- 處理 GitHub PR/issue 先試 gh；不可用再走 git fetch pull/N/head + REST 唯讀查詢
