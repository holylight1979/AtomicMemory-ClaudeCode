# worktree測試裡資料根的斷言要對被測模組自己算的CLAUDE_DIR比-對本樹路徑比會隨別支測試先跑的setdefault變

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-a2c/001-delivery.md
- Confidence: [臨]
- Trigger: WG_CLAUDE_DIR, 資料根斷言, setdefault 收集順序, worktree 測試紅, 單跑綠合跑紅, claude_data_dir, verify_project_layer_smoke, verify_locate_single_authority
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的「調度」總控台（新任，接 claude-9f；對人總控台是 claude-91）。職責：派工、對帳、快照複跑、合併、推送、與各工作 session 通訊；不改碼、不開子代理、不回答原設計者（那是 claude-91 的）。第一步 ToolSearch 載入 SendMessage 與 ListAgents，ListAgents 看自己的名字，SendMessage claude…」

## 知識

- [臨]（track-a2c 001 實踩）worktree 裡的 verify 若斷言「資料根＝本樹路徑」，結果會隨收集順序變：別支測試在模組層 setdefault 了 WG_CLAUDE_DIR 先跑時綠、單跑時紅（或反過來）。正解是斷言對「被測模組自己 import 時算出的 CLAUDE_DIR」比，不對本樹路徑比；兩種順序都要綠。同根因曾讓 verify_locate_single_authority、verify_project_layer_smoke、verify_project_root_claim::test_A、verify_realm_project_term_gate 根層 cwd 案、verify_overview_map_scaffold::test_detect_layer_and_kwargs 在 worktree 紅。
- [臨]（track-a2c 補）要證明「舊測試會寫真家目錄」：子行程把 HOME／USERPROFILE 指到 tmp 假家，假家放一份完整的 lib／hooks／tools 副本（舊版從家目錄載碼才載得到），用 `git show HEAD:<測試檔>` 換成舊版跑一次、新版再跑一次，比假家前後的檔案快照。要證明「舊測試從家目錄載碼」，就在假家放 import 就丟例外的誘餉模組。

## 行動

- worktree 裡資料根相關的案紅：先看斷言是對本樹路徑還是對模組常數，再查是不是 setdefault 收集順序
- 寫資料根斷言：取被測模組的常數比，不寫死本樹路徑
