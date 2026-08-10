# atom-edit-meta與atom-heal對專案層atom的缺口與繞法

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_edit_meta, atom-heal, broken_refs, 專案層 atom, trigger 編輯, file not under, L2 自癒, 死連結修復, sync-atom-index, --fix, --memory-dir, mirror 重生
- Created-at: 2026-08-04

- Related: realm-範疇分區機制-v5, 取用端稽核與瘦身規範-atomaudit與3kb預算

## 知識

- [臨] `atom-heal.py`（L2 死連結自癒）仍寫死全域根（`ahc.MEMORY_ROOT`，無 CLI 覆寫參數）→ 對專案層 atom 一律回「找不到此 atom」。專案層死連結只能手修：逐顆查正主名（多數是錯字／改名級：底線 vs 連字號、漏字母、舊短名），再用 `atom_edit_meta` 換 Related 整行。
- [臨] `atom_edit_meta` 對專案層 atom **全欄位可直接用**（含 triggers）：`lib/atom_io.py:edit_metadata` 的 index root 以 `find_index_dir` 上溯最近 `_atom_index.json` 定位，不再硬編 ~/.claude（舊「file not under」拒寫已根治；索引 scope 沿用既有值不被蹍 global）。守門 `lib/verify/verify_atom_locate_scope.py:test_edit_metadata_project_layer_atom`。舊繞道（手 Edit index → sync-atom-index --fix → 手重生 mirror）已不需要。

## 行動

- 專案層 broken_refs → 別呼 atom-heal，查正主名 + atom_edit_meta 換 Related
- 專案層改 trigger/related/tags → 直接 atom_edit_meta，勿再走三步繞道
- 根治待辦：atom-heal.py 補 project-root 支援後本 atom 可廆
