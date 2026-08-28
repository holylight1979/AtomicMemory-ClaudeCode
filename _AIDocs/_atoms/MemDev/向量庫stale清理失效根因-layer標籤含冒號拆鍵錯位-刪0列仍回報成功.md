# 向量庫stale清理失效根因-layer標籤含冒號拆鍵錯位-刪0列仍回報成功

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 向量庫, vector, reindex, stale, 孤兒, orphan, LanceDB, indexer.py, _delete_stale_keys, write-gate, dedup, similar to existing atom, 幽靈 atom, rag-engine, 重複 chunk
- Created-at: 2026-08-28
- Related: memory-pipeline-silent-failure-2026-05, realm-範疇分區機制-v5, pythonw-下-stdout-為-none-排程腳本秒死陷阱

## 知識

- [臨] 向量庫「檔案系統沒有、向量庫有」的孤兒與重複 chunk 根因：`indexer.py` 把 `layer` 與 `atom_name` 合成 `"layer:atom"` 字串再 `split(":", 1)` 拆回，V4 layer 標籤本身含冒號（`shared:c--proj`／`extra:failures`／`personal:slug:user`）→ 拆成 `layer='shared'`、`atom_name='c--proj:xxx'`，LanceDB 述詞永遠比不中；只有 `global` 層沒冒號所以正常。症狀：孤兒全落在非 global 層、重複 chunk 也全在非 global 層、global 零重複。現行修法：`_delete_atom_rows(table, layer, atom)` 分開傳值，不再合成字串。
- [臨] LanceDB `table.delete(where)` 述詞沒命中會靜默成功並照樣 commit 新版本（版本史看得到：版本號跳、`total_rows` 不變）。統計若拿「預期刪除數」回報就是假成功——增量索引回「已刪 93 顆」但 DB 一列沒少，持續 23 天沒人發現。現行修法：刪除數以 `count_rows()` 前後差為準、另計 `failed_atoms`；判 stale 清理是否真的生效，看 `/status` 的 `total_chunks` 有沒有掉，不看回報數。
- [臨] write-gate 去重（`memory-write-gate.py` 打 `/search`）不帶 `layer` 參數，向量庫又是全部專案 27 層共用 → 在專案 A 寫 atom 會撞到專案 B 其他使用者 personal 層的 atom（實例：c:\Projects 寫 SVN 授權 atom 被 c:\TSLG `personal/wellstseng/feedback-svn-上傳必經明確授權` 以 0.807 擋下）。看到「similar to existing atom」但本地找不到檔時，先 `/vector search` 看命中項的 `(layer)` 標籤，別當幽靈條目；去重範圍該不該跨專案／跨使用者是待拍板的設計問題。
- [臨] `rag-engine.py start` 用 `sys.executable` 起 daemon：bash PATH 若先命中別的 venv python（例：hermes venv，無 lancedb/pyarrow），daemon 起得來、`/health` 回 OK，但 index/search 一跑就 `No module named 'pyarrow'`。有 lancedb 的直譯器是 `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe`；`cmd_start` 現已先驗 import 缺就拒起。
- [臨] 盤點手法（非 daemon 行程直接讀 LanceDB）：`indexer.discover_layers()`→`discover_atoms()` 得檔案系統鍵集合，`table.search().select([layer,atom_name,file_path]).limit(count_rows()).to_list()` 得 DB 鍵集合，兩邊差集即孤兒／漏索引；`chunk_id` 去重比對列數即重複量。`role.md`／純指標檔沒有條列知識段 → 0 chunk 不進 DB，屬正常不是漏索引。

## 行動

- write-gate 報 similar 但檔案找不到 → 先 /vector search 看命中項 layer 標籤，確認是別專案／別使用者的 atom 再判斷
- 懷疑向量庫髒 → 跑非 daemon 行程的盤點腳本對照檔案系統，看 ORPHANS 與 dup chunk_id 數，不信 index_job 回報數
- 改 indexer 刪除邏輯後必跑 `tools/verify/verify_vector_service.py`（含冒號 layer 案例）
- /vector start 一律用有 lancedb 的直譯器；起完打一次 /index/incremental 看 result 沒 error 才算活
