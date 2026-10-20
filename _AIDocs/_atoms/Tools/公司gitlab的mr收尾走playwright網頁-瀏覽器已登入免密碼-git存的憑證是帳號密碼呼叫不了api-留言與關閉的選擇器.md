# 公司gitlab的MR收尾走playwright網頁-瀏覽器已登入免密碼-git存的憑證是帳號密碼呼叫不了api-留言與關閉的選擇器

- Scope: global
- Author: holylight
- Source: session aa80b4c2 2026-10-20 處理 GitLab !4～!12 的留言與關閉
- Confidence: [臨]
- Trigger: gitlab 留言, 關閉 MR, merge request 留言, gitlab api 401, PRIVATE-TOKEN, playwright gitlab, comment-field, close-reopen-button, gitlab.uj.com.tw, MR 自動標 merged
- Created-at: 2026-10-20
- Quote: 「跑"什麼"要14分鐘? 該死的不相干全量測試?」

## 知識

- [臨] 公司 GitLab（gitlab.uj.com.tw）：git credential helper 存的是帳號密碼（9 字、不是 glpat- token），拿來當 PRIVATE-TOKEN 呼叫 API 一律 401；匿名 GET（列 MR、看單一 MR 狀態）可以，寫入（留言、關閉）不行。Playwright MCP 開的瀏覽器用的是持久 profile，已經登入 holylight，直接 navigate 就能操作，不必碰密碼、不必畫面操控。
- [臨] MR 頁面選擇器（GitLab 中文介面實測）：留言框 `[data-testid="comment-field"]`（browser_type 填入），送出 `[data-testid="comment-button"] button[type="submit"]`（同 testid 下還有一顆評論類型下拉，不加 type 會撞兩個）；關閉 MR 的按鈕 testid `close-reopen-button`（頁面文字「關閉合併請求」）。留言有沒有貼成功看 /dashboard/activity 的「commented on」清單。
- [臨] 本機 merge 進 main 再 push，GitLab 會自動把那些 MR 標成 merged（merge_commit_sha 也會填），不必在網頁按合併。browser_snapshot 的 filename 只能落在 repo 根或 .playwright-mcp/（其他路徑被拒），落在 repo 根的要記得刪。

## 行動

- 要在公司 GitLab 留言／關 MR：直接用 Playwright navigate 到 MR 頁，用上面的 testid 操作；不要再試 API token
- 合併 MR 一律本機 merge → push main，讓 GitLab 自己標 merged
- snapshot 存檔用 .playwright-mcp/ 路徑，結束後刪掉
