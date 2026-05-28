# 核心規則

## 知識庫
- 開工前查 _AIDocs/_INDEX.md 確認已有文件；禁止憑記憶改碼
- 修改核心結構/新認知/踩坑 → 更新 _AIDocs + _CHANGELOG.md；新增時同步 _INDEX.md
- _AIDocs 只放長期參考知識；規劃/TODO/進行中 → memory/_staging/

## 記憶
- 分類：「記住」→[固]、反覆模式→[觀]、做取捨→[臨]；不寫臨時嘗試/未確認猜測
- 寫入用 atom_write MCP（自動驗證去重索引晉升）；已記錄事實直接引用

## 同步
完成修改後主動提出：_AIDocs→_CHANGELOG | 新知識→atom | .git→commit+push | .svn→commit
（git/svn clean 後 guardian Stop gate 會自動標 sync_completed，不需手動 IPC）

## 對話
- 「用識流…」→ /consciousness-stream
- 獨立子任務可新開對話；拆分前確保知識已存入
- 段落完成即存；Token 快上限時優先存檔；/resume → /continue
- Context 壓縮/任務告段落 → 提醒開新 session
- **多 agent 並行（主動評估）**：開工前先掃 prompt 含幾個獨立切面（調查/實作/重構/比較/批量）；≥2 個不衝突 → 同 message 一次 dispatch ≥2 個 Agent（Explore/Plan/general-purpose 視任務挑）。細節見 [[workflow-parallel-agents]]
