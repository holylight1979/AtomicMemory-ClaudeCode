# SessionStart 去重 + Session State 管理

> 從 Architecture.md 移入（2026-04-17 索引化）。實作：`wg_core.py`, `wg_extraction.py`, `workflow-guardian.py`。
> keywords: sessionstart, dedup, merge_into, self-heal, orphan, state cleanup

## SessionStart 去重

- 同 cwd 60s 內 active state → 複用（resume 合併，startup 跳過 vector init）
- 分層孤兒清理（`_cleanup_old_states`）：
  - prompt_count=0 working → 10m TTL
  - prompt_count>0 working → 30m TTL
  - done + !sync_pending → 1h TTL
  - done + sync_pending → 4h TTL
  - merged_into → 10m TTL
  - fallback → 7 days
- Vector service 非阻塞：fire-and-forget subprocess + `vector_ready.flag`

## Merge Self-Heal（V4.1 GA 後補）

`_ensure_state` 遇到 `merged_into` 指向的 target state 已被孤兒清理（或從未建立）時，**當前 session 自癒為活躍**：清 `merged_into` + `phase=working` + 重寫檔。

**為何需要**：後續 hook 寫入（如 V4.1 `pending_user_extract[]`）會落入 phase=merged 的死水 state，被 worker 忽略。self-heal 確保寫入進到活 state。

## Active Sibling 查找

`_find_active_sibling_state(cwd, current_session_id, window_seconds=60)`：掃 `WORKFLOW_DIR/state-*.json`，比對 cwd + phase=working + `started_at` 在 window 內 + 未 merged，多匹配取 mtime 最新。
