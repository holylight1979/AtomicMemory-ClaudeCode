# harness原生memory與atom索引marker撞名辨識

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: discover_all_project, memory_dirs 掃描, harness memory, file-based memory, MEMORY.md 撞名, cross-project 掃描, marker, projects/ memory, flat-legacy, 誤納
- Created-at: 2026-06-12
- Related: realm-範疇分區機制-v5

## 知識

- [臨] 新版 CC harness 內建 file-based memory 路徑 `~/.claude/projects/<slug>/memory/` 與 atom 系統舊版專案記憶路徑完全重合，且 harness 也自建 MEMORY.md（`- [Title](file.md) — hook` 清單格式）→ 與 atom 索引「存在 MEMORY.md 即納入」的 marker 假設撞名。
- [臨] 2026-06-12 實測洩漏點：不是 Phase-0 fallback（至少要求 marker 檔存在），而是 `discover_all_project_memory_dirs()` 的 registry old-path 分支——`is_dir()` 即納入、零 marker 檢查；harness 預建空 dir 就被回傳。一旦 harness 寫入記憶檔，`discover_v4_sublayers` flat-legacy（任意非 `_` 開頭 .md）會把 harness 自寫檔當 shared atom 注入。
- [臨] 修法（dad9783）：`_has_atom_index_marker` 內容辨識——`_atom_index.json`/`_ATOM_INDEX.md` 存在，或 MEMORY.md 含 `| Atom` trigger 表頭 / `Status: migrated-v2.21` slug-pointer stub 才算 atom 索引；registry old-path + Phase-0 兩分支皆套。守門測試 `hooks/verify/verify_native_memory_dir_guard.py`（6 測）。
- [臨] 教訓：以「檔名存在」當系統歸屬 marker 不可靠——外部系統（harness）可在同路徑建同名檔；歸屬判定要看**內容簽章**（表頭/stub 標記）。同理 `check_memory_path_block` (a) 把 `projects/<slug>/memory/` 一律當殘骸 deny [P1] 的假設也已過時：該路徑現在是 harness 的合法地盤，gate 若擋到 harness 記憶寫入需重新裁決。

## 行動

- 改 discover/marker 邏輯前先跑 verify_native_memory_dir_guard.py 確認不變式
- 新增「路徑是否屬 atom 系統」判定時用內容簽章，勿用檔名存在
- 遇 harness 記憶寫入被 P1 gate deny → 對照本 atom 重新裁決 gate 範圍
