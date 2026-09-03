# SVN 工作流規則

- Scope: global
- Confidence: [固]
- Type: procedural
- Trigger: svn, svn-update, TortoiseSVN
- Created: 2026-03-18
- Tags: svn, vcs
- Related: workflow-rules, git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉

## 知識

### SVN 更新優先規則

- [固] 每個 session 中，AI 首次修改程式碼（Edit/Write .cs/.xml/.proto 等原始碼）之前，若該 session 尚未執行過 SVN update，必須先詢問使用者
- [固] 適用條件：專案根目錄存在 `.svn/`（SVN 工作副本）
- [固] 非 SVN 專案（如 Git）跳過此規則
- [固] 使用者拒絕後，本 session 不再重複詢問（每 session 最多問一次）
- [固] 使用者同意 → 執行 `/svn-update` skill

### SVN 工具優先順序

- [固] 優先 TortoiseSVN GUI（`TortoiseProc.exe`，非阻塞啟動）
- [固] 降級 svn.exe CLI（加 `--non-interactive` 防掛住）
- [固] 都沒有 → 引導安裝 TortoiseSVN

### 衝突處理策略

- [固] 混合模式：AI 分析衝突內容、提出合併建議，使用者逐一確認才套用
- [固] 生成檔衝突（Proto/Binding/Design）→ 建議接受遠端版本後重新生成
- [固] 二進位檔衝突 → 建議用 TortoiseSVN 或選擇版本
- [固] Pre-update 必做 `svn status` 檢查本地 .cs 修改
- [臨] 「衝突不自動解決」的例外：記憶索引三檔（MEMORY.md／_ATOM_INDEX.md／_atom_index.json）——svn update 停在這三檔衝突後，CC 下 `svn commit / ci / resolve` 前 PreToolUse hook 自動跑 `merge-atom-index.py --resolve`（語意三方、寫回、`svn resolve --accept working`），不需要使用者確認；只有 MEMORY.md 表外手寫段兩側同改才留 `<<<<<<<` 標記交人判斷。其他檔的衝突仍走「AI 分析＋使用者確認」。細節 [[記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合]]。

## 行動

- 首次 Edit/Write 原始碼前，檢查 `.svn/` 存在 + session 內未 update → 簡短詢問
- 詢問格式簡潔：「要先 svn update 嗎？」
- 使用者拒絕 → 記錄已詢問，不再重複
- 衝突不自動解決，AI 分析 + 使用者確認

