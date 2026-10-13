# 退回看紅的腳本把main沒有的新檔列進git-checkout會整條失敗而沒退回-看起來全綠其實沒驗-退回清單只放基底真有的檔並檢查checkout退出碼

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/_console/verify_g12w_snapshot_c3ef006e.log；g12w_revert_fix_c3ef006e.log
- Confidence: [臨]
- Trigger: 退回看紅, git checkout main --, pathspec did not match, 快照腳本, 退回段, 假綠, 新檔退回, 總控台快照, 改前版紅
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的「調度」總控台（新任，接 claude-9f；對人總控台是 claude-91）。職責：派工、對帳、快照複跑、合併、推送、與各工作 session 通訊；不改碼、不開子代理、不回答原設計者（那是 claude-91 的）。第一步 ToolSearch 載入 SendMessage 與 ListAgents，ListAgents 看自己的名字，SendMessage claude…」

## 知識

- [臨] 實踩（調度總控台快照 g12w 002）：退回段寫 `git checkout main -- a.py b.py hooks/wg_reading_path.py`，其中 wg_reading_path.py 是該軌新增、main 沒有的檔 → git 對一個 pathspec 比不到就整條失敗（`error: pathspec ... did not match`），一個檔都沒退回；接著跑的「新案應紅」全綠（372 passed 0 failed），如果只看尾行會把「退回沒生效」誤讀成「新案沒測到東西」或直接跳過。正解：退回清單只放基底真有的檔（新增檔留著不動，或用 `git ls-tree main -- <檔>` 先過濾），`git checkout` 後必查退出碼（`|| exit 97`），並把「退回後紅數 > 0」當成該段的通過條件，紅 0 要當成腳本壞掉而不是通過。

## 行動

- 寫退回看紅的腳本：PROG 只列基底有的檔、checkout 後查退出碼、紅 0 視為 FAIL
- 讀別人的退回結果：先找有沒有 pathspec 錯誤行，再信紅數
