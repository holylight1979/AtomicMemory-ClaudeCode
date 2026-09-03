---
name: vector
description: 向量服務管理：啟動/停止/重建 Vector Service（LanceDB + Ollama）
---

# /vector — 向量服務管理

> 統一入口管理記憶向量服務：狀態查詢、啟停、索引重建、語意搜尋。
> 全域 Skill，適用任何專案。

---

## 使用方式

```
/vector                    # 預設顯示狀態
/vector status             # 服務狀態 + 索引統計
/vector start              # 啟動 daemon
/vector stop               # 停止 daemon
/vector reindex            # 全量重建索引
/vector reindex --incremental  # 增量索引
/vector search 關鍵字      # 語意搜尋（debug 用）
```

---

## 參數解析

從 `$ARGUMENTS` 取得子指令：
- 空 / `status` → 狀態查詢
- `start` → 啟動
- `stop` → 停止
- `reindex [--incremental]` → 索引重建
- `search <query>` → 語意搜尋

---

## 子指令：status（預設）

用 Bash tool 執行：

```bash
python ~/.claude/tools/rag-engine.py health
```

解讀輸出，報告：
- 服務是否運行中（port 3849）
- 索引檔案數 / 總向量數
- Ollama embedding 模型狀態
- 最後索引時間

## 子指令：start

```bash
python ~/.claude/tools/rag-engine.py start
```

啟動後自動執行 `health` 確認成功。

## 子指令：stop

```bash
python ~/.claude/tools/rag-engine.py stop
```

## 子指令：reindex

```bash
python ~/.claude/tools/rag-engine.py index [--incremental]
```

- 無 flag → 全量重建（刪除舊索引，重新 embedding 所有 atom）
- `--incremental` → 只處理新增/修改的檔案

執行前提醒：全量重建耗時較長（依 atom 數量），確認使用者要繼續。
增量索引直接執行不需確認。

完成後顯示索引統計。

## 子指令：search

```bash
python ~/.claude/tools/rag-engine.py search "查詢內容" --top-k 5
```

顯示搜尋結果：
- 每筆結果的 atom 名稱、相似度分數、匹配片段
- 用途：驗證向量搜尋品質、debug 檢索問題
