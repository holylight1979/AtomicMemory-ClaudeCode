# 啟動鏈自動覆寫陷阱-user-init每session拷貝來源檔必先驗證管線仍成立

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: user-init, IDENTITY.md 被覆寫, 啟動鏈, SessionStart 覆寫, 雙檔 pipeline, 檔案自動覆蓋, stub 覆寫, 契約檔損毀
- Created-at: 2026-07-08
- Related: 模型行為移植-fable行為契約必載檔

## 知識

- [臨] 「每 session 自動拷貝 A→B」型啟動鏈（如 user-init.sh 的 IDENTITY-{user}.md→IDENTITY.md 雙檔 pipeline）在「來源檔角色變更」後會變成定時炸彈：個人槽被裁決改為空置 stub 後，每次開 session 都把 stub 覆蓋掉目標檔的完整契約，且因發生在啓動瞬間、事後修復注定被下個 session 抹掉（實錄：同一晚連發兩次、修兩次才破案）。
- [臨] 改動任何「被自動流程當作來源/目標」的檔案前，先 grep 全庫找誰在讀/寫它（hooks/settings.json/安裝腳本）；檔案被神祕覆寫時，第一嘤疑人是啓動鏈自動拷貝而非並發 session 誤寫：mtime 落在 session 啓動時點 + 內容恰等於某來源檔 = 鐵證。
- [臨] 防線配套：契約檔改為直接維護單一真相 + tracked template 做災復還原源（只在目標不存在時 cp）+ SessionStart 完整性哨兵（缺核心段/過短→告警）。gitignored 的 per-user 實例檔沒有版控兒安全網，哨兵+template 就是它的備份體系。

## 行動

- 改啟動鏈拷貝邏輯前，先列出所有來源/目標檔的讀寫者並驗證管線前提仍成立
- 檔案被覆寫事故：先查 mtime 是否落在 session 啓動點 + diff 候選來源檔，再怀疑並發誤寫
