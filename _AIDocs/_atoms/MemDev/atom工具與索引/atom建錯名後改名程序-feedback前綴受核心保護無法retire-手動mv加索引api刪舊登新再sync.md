# atom建錯名後改名程序-feedback前綴受核心保護無法retire-手動mv加索引API刪舊登新再sync

- Scope: global
- Author: holylight
- Source: session 2026-10-06 ~/.claude README 重寫
- Confidence: [臨]
- Trigger: atom 改名, atom rename, 標題錯字, core-protected, cannot be retired, feedback 前綴保護, upsert_atom, delete_atom, atom_index_json, 索引重登
- Created-at: 2026-10-06
- Quote: 「你不要草草了事，應該要把說明文件 "根據最新現況(包含CC最新原生狀態)" 都針對使用者可以知道的訊息，建立清楚(而且也要跟TECH.md有說的部份避免不必要的重疊)，給人讀的文件應該要力求精確、簡潔、易懂。」

## 知識

- [臨] atom_write 建立時標題打錯字（「亂磍」），想退役重建：`atom_retire` 對 feedback-* 一律回 core-protected 拒絕（`lib.atom_locations.is_core_protected_name` 的 PREFIXES 含 decisions/workflow-/toolchain/feedback-/memory-pipeline-/atom-），不管是不是剛建的；`atom_move` 只搬路徑不改 slug；`sync-memory-index.py --write` 是從 JSON SoT 重生 MEMORY.md/_INDEX.md，不掃磁磟，光 mv 檔案索引不會跟。
- [臨] 可行程序：mv `.md` 與 `.access.json` → 改檔內 `# 標題` → `lib.atom_index_json.delete_atom(mem_dir, old_name)` + `upsert_atom(mem_dir, new_name, new_rel_path, triggers, scope=)` → `python tools/sync-memory-index.py --write` 再 `--check`。upsert 對 `_atom_index.json` 的 tmp→replace 可能碰 WinError 5（別的 hook 正在讀），重試一次即過。
- [臨] 用 `python -I` 印中文到 cp950 主控台會 UnicodeEncodeError，且 `-I` 含 `-E` 會忽略 PYTHONIOENCODING；要在腳本內 `sys.stdout.reconfigure(encoding='utf-8')`。

## 行動

- 建 atom 前先在訊息裡重讀一次標題與觸發詞錯字；feedback-* 建錯就走上述改名程序，不要再建第二顆留下重複
- python -I 腳本要印中文：開頭 sys.stdout.reconfigure(encoding='utf-8')
