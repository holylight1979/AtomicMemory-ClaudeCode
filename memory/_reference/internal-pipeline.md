# Internal Pipeline Reference

> 記憶系統內部管線技術細節。JIT 按需注入，僅在記憶系統開發場景載入。
> 來源：decisions.md + decisions-architecture.md

## 記憶檢索管線

- [固] UserPromptSubmit（ups_gates → ups_context → ups_search → ups_inject）：L0 意圖偵測 → Trigger 匹配（ASCII 整詞邊界／CJK 子字串）→ 跨專案 alias（命中他專案別名只帶其 MEMORY.md 目錄；他專案 atom 不進候選池、候選池已依 scope 可見性收窄）→ BM25（僅 trigger 命中 ≤2 時；min_score 7.0、top 3）→ Vector（只補專案層）→ Supersedes 過濾 → RRF 融合 × activation → hot/cold → 同題去冗（trigger 精確重疊 ≥3 → 節錄）→ per-turn 三態 ok/fallback/skip（TURN_BUDGET_LIMIT）→ related spread（max 6）→ 總額裁切（依 activation 由高到低回填）→ additionalContext（尾行 `[Context budget: x/y]`）
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
