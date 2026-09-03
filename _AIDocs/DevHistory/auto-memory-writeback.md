# 對談結束自動記憶 writeback 管線（session_end flush / 失敗骨架 / Deep Post-Mortem Gate）

> 從 MemDev atom「對談結束自動記憶與錯誤加權深記」精簡移出的開發脈絡（gap-fix / 演化 / verify wiring）。
> 現況機制（timeless）留該 atom；本檔存「怎麼演化到現況」的編年敘事，按需查閱、不自動注入。
> 開發期：2026-06 起（版本演進見 [_CHANGELOG.md](../_CHANGELOG.md)）。
> keywords: session_end flush, 落點路由, 失敗骨架, deep post-mortem, writeback, extract-worker, stop gate, _drafts, edit-count proxy

## 定位

兩層自動記憶：一般知識走品質閘全寫入、失敗加權深記。骨架永遠由 hook 自動寫（小模型填能填的），高 effort 時才加碼喚 Claude 深寫。三個 stage 分屬 `hooks/extract-worker.py`（Stage 1/2）與 `hooks/handlers/stop.py`（Stage 3）。

## Stage 1 — session_end flush 落點路由

`extract-worker._session_end_writeback` → `_flush_item_to_atom`：把 session_end 全文萃取 + 累積 knowledge_queue flush 成 [臨] atom。

**落點路由缺口修補**：原本一律 `scope=global`，把專案專屬知識污染進 global core 並注入每個專案。加 `_flush_route`：

- 專案 session（cwd 有 project root 且非 ~/.claude）→ `scope=shared`、落專案層 `{project}/.claude/memory/shared/`（只在該專案注入）
- ~/.claude / 無 root / 空 cwd → `scope=global`

`_flush_item_to_atom` 收 scope/project_cwd/dedup_dir，dedup 對齊落點。守門：`verify_flush_routing`（4 測）+ `verify_session_end_flush` wiring（2 測）。過品質閘、只清寫成功項（失敗留 queue 重試）、config `response_capture.session_end_flush.max_atoms` 上限（預設 8）。

**草稿隔離缺口修補**：auto-capture [臨] 草稿原本 flush 成「正規 atom」入索引 → 大量 content-as-filename 碎片污染 memory/ 根層。改 `build_atom_content` + `write_raw` 直寫 `_drafts/auto-capture/`（即 dedup_dir）；`_drafts` 被 sync-atom-index 排除 → 不入索引 / 不注入 / 不計數。草稿待人工審。詳見 atom `auto-capture碎片sweep污染詞庫-defer根治`。

## Stage 2 — 失敗多區塊骨架

`extract-worker._failure_writeback` 把失敗記錄改寫為五區塊：始末 / 根因 / 設計原理 / 運作邏輯 / 防再犯。

- `_build_failure_skeleton`：LLM 敘事填「始末」
- `_split_root_cause`：從「（根因: …）」尾段拆「根因」
- 餘三段留 `_FAILURE_TODO_MARK` 待補
- `_failure_dedup_hit`：對新骨架始末行 + 舊「- [臨]」單行格式皆去重

## Stage 3 — Deep Post-Mortem Gate

`handlers/stop.py._should_deep_postmortem`（純判定）+ gate。觸發 = (effort 訊號) AND (真失敗訊號)。

**edit-count proxy 拔除**：早期 effort 訊號含「同檔 edit_counts>=3」，但純 edit 次數未 failure-gate、對正常重度迭代開發本就超標（edit 次數 ≠ 失敗）→ 移除。現 effort 只採 `wisdom_retry_count>=2 ∨ fix_escalation_triggered`（兩者都已在 track_retry 層以 failing_tests error-gate，是誠實的「失敗中反覆」訊號）。真失敗 = `failing_tests 非空 ∨ evasion_flag ∨ not claims_done`。必 AND 真失敗，才把「高 effort 成功」與「反覆修不好」分開。辨識脈絡見 atom `escalation-hook-在-edit-count-proxy-上-false-fire`。

**獨立預算**：DPM 曾與 Sync/Scan/TestFail 共用 `stop_gate_max_blocks` → 實測餓死：Sync(1)+TestFail(1) 吃光 2-block 預算，輪到 DPM 時 stop_count>=max 永不觸發，偏偏那正是「反覆修不好」最該補 post-mortem 的 session。改一次性 `deep_postmortem_done`（一設永不再觸，anti-loop 由 one-shot 保證），與眾 gate（sr_count / scan_report_warned 各自自限）對稱。config `deep_postmortem.enabled`。

觸發即 output_block 指示 Claude 結束前用 atom_write 補完整 post-mortem。Stop gate 注入機制 = output_block(reason)（wg_core：`{decision:block, reason}` + sys.exit），DPM gate 排在 correctness/sync gate 之後。

## Verify

- `verify_session_end_flush.py`（Stage 1）
- `verify_failure_skeleton.py`（Stage 2）
- `verify_deep_postmortem_gate.py`（Stage 3，含 handle_stop 端到端 monkeypatch）

連字號檔名 `extract-worker.py` 用 importlib 載入測。跑 `python -m pytest hooks/verify/ -q`。
