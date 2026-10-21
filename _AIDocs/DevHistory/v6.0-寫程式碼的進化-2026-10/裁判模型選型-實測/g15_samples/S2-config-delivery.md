---
from: track-config-consistency（claude-da）
to: 總控台 claude-e3
seq: 003
type: 交付（派工 002：程式端真不一致修補）
received: 2026-10-20 深夜
---
分支 config-consistency HEAD 03327f72（前一筆 063e7f96 先合 main 含 T2.16～T2.19；CHANGELOG 兩邊都留），未推。驗證範圍 20 支 403 passed（R234）；commit 前 --commit-check PASS；merge-atom-index 改了 → verify_vcs_sync_worker 與 verify_merge_atom_index 約 100 個錄製檔重錄一起 commit。

## 改了哪裡（每條先紅後綠，新檔 tools/verify/verify_g8_config_fixes.py 10 案＋verify_config_consistency +3 案本樹重跑）
1. (c) usefulness.wilson_z：wg_atoms 三處與 ups_inject 改讀 lib.atom_access.WILSON_Z_DEFAULT（1.28）。
2. (c) vcs_sync.exclude：DEFAULTS 補 `memory/_meta/**`；三處 `.get("exclude", [])` 改讀 DEFAULTS["exclude"]。
3. (c) session_context：wg_atoms 改讀 wg_core.DEFAULTS（逾時 8000 → 1500）。
4. (c) vector 服務：indexer／reranker 改讀 config.py DEFAULTS（reranker 保留 min(…,0.4)）；同類加修 search_timeout_ms DEFAULTS 2000 → 8000（服務不讀，只 hook 讀）。
5. (c) 同類加修 sync_keywords：user_prompt_submit 改讀 wg_core.DEFAULTS。
6. (d) 資料根：wg_core._is_core_session／check_cross_realm_write、pre_tool_use._privacy_globs、lib/vcs_ignore._CLAUDE_DIR、tools/merge-atom-index._load_toggles 改走 CLAUDE_DIR／claude_data_dir()。
7. (b) 接回三個開關：write_gate.enabled（放在繞閘拒寫、現況帳、預算、導讀卡檢查之後，等同 skip_gate，不關掉 T2.19）；provenance.quote_max_chars（lib.provenance.quote_max_chars()，0＝不截）；cross_session.enabled（extract-worker `_cross_session_search` 進門先判）。
- 改舊測試三支（先宣告）：verify_cross_realm_guard、verify_cross_realm_bash_guard、verify_git_privacy_gate 的寫死家目錄改 wg_core.CLAUDE_DIR，斷言不變。
- 偶發：verify_vcs_sync_worker::test_pull_edit_during_isolated_rebase_aborts_before_update_ref 重負載紅過一次，單跑新舊都綠，判偶發。

## 本樹重跑
`CONFIG_CONSISTENCY DONE keys=510 read_not_defined=22 defined_not_read=23 default_mismatch=1 path_self_computed=2`：(c) 9→1（只剩 memory-eval 刻意值）、(d) 7→2（都刻意）、(b) 26→23（新冒 6 個是 live 今天新加的 P8／G16／G14 鍵，讀取端在別軌）、(a) 20→22（兩個選填鍵，刻意）。
- 要裁：response_capture.session_end_timeout_seconds 無自然讀取點（SessionEnd 萃取是脫離主程序的 worker）→ 建議合併時刪鍵並改 TECH。

## 接健檢（合併時加 config `tool_selftests[]`）
`{"name": "config-consistency", "cmd": "python -X utf8 tools/config-consistency.py --notes workflow/inbox/from-track-config-consistency/config-consistency-notes.json.txt --out memory/_staging/g8-config-consistency-report.md", "expected": "DONE", "sentinel": "CONFIG_CONSISTENCY", "timeout_s": 120}`

## live 未動
live 無新檔與改動；atom_write 新建一張 MemDev 卡「讀取點從家目錄改走資料根時寫死家目錄的舊測試會一起紅…」。notes 全文已落 `config-consistency-notes.json.txt`（同資料夾）。

我在等：對帳合併；合併時 (1) 刪死鍵與 TECH 說法（含 session_end_timeout_seconds）(2) 落 notes (3) tool_selftests 加健檢。
