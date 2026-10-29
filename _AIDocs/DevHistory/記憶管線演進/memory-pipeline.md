# 記憶檢索管線 + 回應知識捕獲 + V3 三層即時管線

> 從 Architecture.md 移入（2026-04-17 索引化）。
> keywords: pipeline, JIT, vector, hot_cache, retrieval, 萃取, extract, quick-extract, V3, 注入

## 資料層

1. **MEMORY.md**（always-loaded）：Atom 索引（全域 + 專案層各自索引）
2. **Atom 檔案**（按需載入）：由 Trigger 欄位 + 向量搜尋發現
3. **Vector DB**：LanceDB（`memory/_vectordb/`）
4. **Episodic atoms**：自動生成 session 摘要（`memory/episodic/`，TTL 24d，不進 git）
5. **Wisdom Engine**：反思統計（`memory/wisdom/`）
6. **專案自治層**：`{project_root}/.claude/memory/` — 每專案獨立 atoms + episodic + failures

## 記憶檢索管線

```
使用者訊息 → UserPromptSubmit hook (workflow-guardian.py)
  ├─ [V3] Hot Cache 快速路徑 (injected=false? → 注入)
  ├─ Intent 分類 (rule-based ~1ms)
  ├─ MEMORY.md Trigger 匹配 (keyword ~10ms)
  ├─ Vector Search (LanceDB + qwen3-embedding ~200-500ms)
  ├─ Ranked Merge → top atoms
  ├─ Context Budget: 3000 tokens 上限，ACT-R truncate
  ├─ Fix Escalation: retry_count≥2 → 注入 [FixEscalation] 信號
  ├─ Handoff Protocol: intent=handoff → 注入 [Guardian:Handoff] 提醒走 /handoff
  └─ additionalContext 注入
```

## 回應知識捕獲

| 時機 | 輸入 | 上限 |
|------|------|------|
| Stop hook（逐輪增量） | byte_offset 增量讀取 | 4000 chars, 3 items |
| SessionEnd（全量） | 全 transcript | 20000 chars, 5 items |

情境感知萃取（依 intent 調整 prompt）。萃取結果一律 `[臨]`。注入前 Token Diet strip 9 種 metadata + 行動/演化日誌。

## V3 三層即時管線（被 V4.1 user-extract 疊加，主流程未退役）

```
Claude 回應結束 → [Stop async] quick-extract.py (local qwen3:1.7b, 5s)
                    → hot_cache.json (injected=false)
Claude 使用工具 → [PostToolUse] hot cache check → mid-turn 注入
使用者下一句   → [UserPromptSubmit] hot cache 快速路徑 + 完整 pipeline
Deep extract   → [detached] extract-worker.py (rdchat: gemma4:e4b) → 覆寫 hot cache → 正式 atom
```
