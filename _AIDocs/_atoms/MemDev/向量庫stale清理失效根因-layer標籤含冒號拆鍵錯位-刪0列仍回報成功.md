# 向量庫stale清理失效根因-layer標籤含冒號拆鍵錯位-刪0列仍回報成功

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 向量庫, vector, reindex, stale, 孤兒, orphan, LanceDB, indexer.py, _delete_stale_keys, write-gate, dedup, similar to existing atom, 幽靈 atom, rag-engine, 重複 chunk, dedupLayersFor, layers
- Created-at: 2026-08-28
- Related: memory-pipeline-silent-failure-2026-05, realm-範疇分區機制-v5, pythonw-下-stdout-為-none-排程腳本秒死陷阱

## 知識

- [臨] 向量庫「檔案系統沒有、向量庫有」的孤兒與重複 chunk 根因：`indexer.py` 把 `layer` 與 `atom_name` 合成 `"layer:atom"` 字串再 `split(":", 1)` 拆回，V4 layer 標籤本身含冒號（`shared:c--proj`／`extra:failures`／`personal:slug:user`）→ 拆成 `layer='shared'`、`atom_name='c--proj:xxx'`，LanceDB 述詞永遠比不中；只有 `global` 層沒冒號所以正常。症狀：孤兒全落在非 global 層、重複 chunk 也全在非 global 層、global 零重複。現行修法：`_delete_atom_rows(table, layer, atom)` 分開傳值，不再合成字串。
- [臨] LanceDB `table.delete(where)` 述詞沒命中會靜默成功並照樣 commit 新版本（版本史看得到：版本號跳、`total_rows` 不變）。統計若拿「預期刪除數」回報就是假成功——增量索引回「已刪 93 顆」但 DB 一列沒少，持續 23 天沒人發現。現行修法：刪除數以 `count_rows()` 前後差為準、另計 `failed_atoms`；判 stale 清理是否真的生效，看 `/status` 的 `total_chunks` 有沒有掉，不看回報數。
- [臨] write-gate 去重只比「寫入者能 append 到」的層：`realm.dedupLayersFor(scope, memBase, {role,user})` 算出 global（`global`+`extra:local-atoms`）或再加當前專案 `shared:<slug>`／`role:<slug>:<r>`／`personal:<slug>:<u>`，經 `execWriteGate` stdin `layers` → `memory-write-gate.check_dedup(layers)` → daemon `/search?layers=a,b`（`searcher._build_layers_clause` 組 `layer IN (...)`）。以前不限層掃全庫 27 層，在 c:\Projects 寫 atom 被 c:\TSLG `personal/wellstseng` 的 atom 以 0.807 擋下（不能 append 過去只能 skip_gate）。拒寫訊息帶 `searched layers:` 可直接看比了哪幾層；看到「similar to existing atom」但本地找不到檔，先看那行。專案 slug 規則 JS `projectSlugOf` 對拍 `wg_core.cwd_to_project_slug`（`c:\Projects` → `c--projects`）。
- [臨] `rag-engine.py start` 用 `sys.executable` 起 daemon：bash PATH 若先命中別的 venv python（例：hermes venv，無 lancedb/pyarrow），daemon 起得來、`/health` 回 OK，但 index/search 一跑就 `No module named 'pyarrow'`。有 lancedb 的直譯器是 `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`；`cmd_start` 現已先驗 import 缺就拒起。
- [臨] 盤點手法（非 daemon 行程直接讀 LanceDB）：`indexer.discover_layers()`→`discover_atoms()` 得檔案系統鍵集合，`table.search().select([layer,atom_name,file_path]).limit(count_rows()).to_list()` 得 DB 鍵集合，兩邊差集即孤兒／漏索引；`chunk_id` 去重比對列數即重複量。`role.md`／純指標檔沒有條列知識段 → 0 chunk 不進 DB，屬正常不是漏索引。

## 行動

- write-gate 報 similar 但檔案找不到 → 看拒寫訊息的 searched layers，再 /vector search 看命中項 layer 標籤
- 懷疑向量庫髒 → 跑非 daemon 行程的盤點腳本對照檔案系統，看 ORPHANS 與 dup chunk_id 數，不信 index_job 回報數
- 改 indexer 刪除邏輯後必跑 `tools/verify/verify_vector_service.py`（含冒號 layer 案例）；改去重層清單必跑 `verify_write_gate_pitfall.py` + `verify_mcp_funnel_hardening.py`
- /vector start 一律用有 lancedb 的直譯器；起完打一次 /index/incremental 看 result 沒 error 才算活
