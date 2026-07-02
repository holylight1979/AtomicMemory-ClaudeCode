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
- [臨] 教訓：以「檔名存在」當系統歸屬 marker 不可靠——外部系統（harness）可在同路徑建同名檔；歸屬判定要看**內容簽章**（表頭/stub 標記）。
- [臨] WRITE 側（`check_memory_path_block` (a) 對 `projects/<slug>/memory/` deny [P1]）＝**偽衝突·非工具層·無需改**：該 gate 是 PreToolUse guard、只攔 `tool_name in (Write,Edit)` 的**Claude 工具呼叫**（wg_core L915）；harness 原生 auto-memory 是 harness 內部檔案 I/O、不走工具管線 → PreToolUse 永不對它 firing、gate 見不到它（實證：harness 於 session 啟動即內部預建空 `projects/<slug>/memory/`，全程無 PreToolUse deny）。故 [P1] deny 只會對「Claude 手動 Write 到該 legacy 路徑」firing＝**預期的導流**（改用 atom_write），非誤擋 harness。

## 行動

- 改 discover/marker 邏輯前先跑 verify_native_memory_dir_guard.py 確認不變式
- 新增「路徑是否屬 atom 系統」判定時用內容簽章，勿用檔名存在
- Claude 被新版 harness memory 教學指示手動 Write `projects/<slug>/memory/` → 改用 atom_write（P1 deny 是預期導流，非 bug）；harness 內部 auto-memory 非工具層、不受 gate 影響，勿為此改 guard
