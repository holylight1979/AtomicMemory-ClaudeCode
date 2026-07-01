# Internal Pipeline Reference

> 記憶系統內部管線技術細節。JIT 按需注入，僅在記憶系統開發場景載入。
> 來源：decisions.md + decisions-architecture.md

## 記憶檢索管線

- [固] UserPromptSubmit: Intent 分類 → Trigger 匹配 → Vector Search → Ranked Merge → additionalContext
- [固] 索引 2 層：global → project，`**/*.md` 遞迴掃描 + `_` 前綴目錄跳過

## Hot Cache 機制

- [觀] hot_cache.json: session_id + timestamp + source + injected flag + knowledge[] + summary
- [觀] File lock: sidecar .lock + msvcrt.locking()（Win）/ fcntl.flock()（Unix），失敗時 best-effort
- [觀] 注入順序: quick_extract 5s → PostToolUse/UPS 讀取 → deep_extract 30s 覆寫
- [觀] wg_hot_cache.py API: write_hot_cache(data) / read_hot_cache(sid) / mark_injected(sid)

## Async Hook 行為

- [觀] Stop async hook: systemMessage 自動注入下一輪；不支援 additionalContext
- [觀] quick-extract.py: str.format() prompt 內的 JSON 範例需 {{ }} 跳脫
- [觀] PostToolUse additionalContext 即時生效（同一 turn 內 Claude 可見）

## SessionStart 去重

- [觀] _find_active_sibling_state(): 掃描同 cwd + phase=working + 60s 內 → 複用 state
- [觀] merged_into redirect: _ensure_state() 自動跟隨，後續 hook 透明使用目標 state
- [觀] vector_ready.flag: SessionStart 清除 → 背景 subprocess 寫入 → _semantic_search 檢查
