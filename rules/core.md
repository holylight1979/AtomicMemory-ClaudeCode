# 核心規則

## 知識庫
- 開工前查 _AIDocs/_INDEX.md 確認已有文件；禁止憑記憶改碼
- 斷言嚴重度/blocker/「必爆」前先實證（跑/查/追根源）：機制存在≠實際會發生；框架前提跨域複用先驗新對象型別/值域仍符合，未證實先證再修。細節 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]]
- 修改核心結構/新認知/踩坑 → 更新 _AIDocs + _CHANGELOG.md；新增時同步 _INDEX.md
- _AIDocs 只放長期參考知識；規劃/TODO/進行中 → memory/_staging/

## 記憶
- 分類：「記住」→[固]、反覆模式→[觀]、做取捨→[臨]；不寫臨時嘗試/未確認猜測
- 寫入用 atom_write MCP（自動驗證去重索引晉升）；已記錄事實直接引用
- **範疇（Realm，與 scope 正交）**：判定「核心 vs 非核心」三問——① 可重用 ≥2 專案？② 系統規則 vs 單一 app/工具/環境的特定範疇？③ 月級穩定 vs 週級易變？
  - **核心**（預設）：跨專案通用知識（preferences / decisions / workflow / toolchain）→ `scope=global` 住 `memory/`，全專案注入。
  - **非核心（local）**：只在 ~/.claude 內才有用的知識（記憶系統/Guardian 開發、腦內世界、特定外部工具踩坑）→ **仍 `scope=global`**，但自動歸 `_AIDocs/_atoms/<domain>/`（World/Tools/MemDev），**只在 cwd∈~/.claude 注入**、外部專案零負擔（例外：`CROSS_PROJECT_LOCAL_DOMAINS` 內範疇如 `Continuity`，storage 在 _atoms 但跨專案注入，對偶 feedback-*）。realm 由 index path 前綴推導（不存欄位），分類器安全預設 core、核心保護清單硬擋。機制全貌見 atom [[realm-範疇分區機制-v5]]。

## 同步
完成修改後主動提出：_AIDocs→_CHANGELOG | 新知識→atom | .git→commit+push | .svn→commit
（git/svn clean 後 guardian Stop gate 會自動標 sync_completed，不需手動 IPC）

## 對話
- 「用識流…」→ /consciousness-stream
- 獨立子任務可新開對話；拆分前確保知識已存入
- 段落完成即存；Token 快上限時優先存檔；/resume → /continue
- Context 壓縮/任務告段落 → 提醒開新 session
- **多 agent 並行（主動評估）**：開工前先掃 prompt 含幾個獨立切面（調查/實作/重構/比較/批量）；≥2 個不衝突 → 同 message 一次 dispatch ≥2 個 Agent（Explore/Plan/general-purpose 視任務挑）。細節見 [[workflow-parallel-agents]]
