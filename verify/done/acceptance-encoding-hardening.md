---
task_slug: encoding-hardening
session_id: d892b7c9-9c98-47fc-ae48-747e217bd73f
created_at: 2026-10-01
source: multifile
status: done
---
## 目標
亂碼資料夾（某專案的 `shared/UIºt¥X`＝`UI演出` 的 Big5 位元組被當 cp1252 解碼）會被健檢抓到；worker 不會再把 svn.exe 定址不到的路徑交給 svn 建出亂碼目錄；手動 `svn add` 中文路徑會被提醒。先重現、再定刀。

## 必須發生
- 重現矩陣（tmp `svnadmin create` 實倉，非 win32 skip）→ `hooks/verify/verify_svn_unicode_paths.py`：
  - cp950 內中文 `UI演出` 經 `_Svn.run` add＋commit 全程通過、磁碟名／`status --xml`／`svn ls --xml`／第二個 checkout 皆原名 → `test_cp950_cjk_dir_round_trips_through_worker`
  - cp950 外字元（`ゔ外字`、`é外字`）worker 在呼叫 svn 前 `_Stop`（status=unpushed、last_error 說明路徑），磁碟不得多出任何東西 → `test_non_ansi_dir_worker_stops_before_svn_no_garbage`
  - 原生證據：直接 `svn add --parents memory/é外字/n.md` 真的建出 `e外字` → `test_raw_svn_add_parents_best_fit_creates_garbage_dir`
- `wg_vcs_sync._svn_argv_encoding()` 用 `GetACP`（不信 UTF-8 mode 下的 locale）；`_Svn.err` utf-8 解碼失敗退 ACP
- 偵測：`atom-health-check --report` 對含亂碼名稱的 tmp 樹只出一行 `⚠ 疑似亂碼名稱: <path>`、exit 0、報告多 `mojibake_names` 項、裡面的 atom 不計 total → `tools/verify/verify_mojibake_detect.py::test_health_check_warns_once_and_keeps_going`、`test_health_check_text_report_lists_check_item`
- `sync-memory-index --check` 對全域樹／專案樹不 traceback、stderr 一行警告、指向亂碼路徑的索引列被跳過 → `test_sync_memory_index_check_global_tree_does_not_crash`、`test_sync_memory_index_check_project_tree_does_not_crash`
- 寫入端既有拒收行為鎖住：`slugify("UIºt¥X")` 不含 U+0080–U+00FF、`_clean_segment` 拒收、正常中文／ASCII 不受影響 → `lib/verify/verify_encoding_guard.py::test_known_mojibake_case_slugify_strips_latin1`、`test_known_mojibake_case_clean_segment_rejects`、`test_cjk_and_ascii_names_still_pass`
- 提醒閘：`pre_tool_use.check_svn_encoding` 對 Bash／PowerShell `svn add` 非 ASCII 路徑回 `[Guardian:SvnEncoding]`、零子行程；ASCII／非 add／非 Bash 工具 → None → `test_svn_add_non_ascii_path_warns_without_subprocess`、`test_svn_add_ascii_or_other_commands_silent`

## 禁止發生
- 不把所有 Latin-1 定義為亂碼（只鎖已知案例的字元區間 U+0080–U+00FF 於名稱）
- SvnEncoding 只 warn、永不 deny；偵測端只警告跳過、不嘗試修檔名
- 不用 `--targets`（實證無效：同走 ANSI code page）

## 驗證指令
- python -m pytest hooks/verify/verify_svn_unicode_paths.py lib/verify/verify_encoding_guard.py tools/verify/verify_mojibake_detect.py -q
- 某專案清理（使用者自己跑）：svn revert "<專案根>\.claude\memory\shared\UIºt¥X"
