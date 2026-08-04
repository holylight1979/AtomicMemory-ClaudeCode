# atom-edit-meta與atom-heal對專案層atom的缺口與繞法

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_edit_meta, atom-heal, broken_refs, 專案層 atom, trigger 編輯, file not under, L2 自癒, 死連結修復, sync-atom-index, --fix, --memory-dir, mirror 重生
- Created-at: 2026-08-04
- Related: realm-範疇分區機制-v5, 取用端稽核與瘦身規範-atomaudit與3kb預算

## 知識

- [臨] `atom-heal.py`（L2 死連結自癒）寫死全域根（`ahc.MEMORY_ROOT`，無 CLI 覆寫參數）→ 對專案層 atom 一律回「找不到此 atom」。專案層死連結只能手修：逐顆查正主名（多數是錯字／改名級：底線 vs 連字號、漏字母、舊短名），再用 `atom_edit_meta` 換 Related 整行。
- [臨] `atom_edit_meta` 的 `related`/`tags` 對專案層 atom 正常；**`triggers` 對專案層 atom 必敗**——`lib/atom_io.py` triggers 變更走「SoT 先行」硬寫全域 index 且要求檔案在 `~/.claude` 下（`file not under` 拒寫）。
- [臨] 專案層 trigger 編輯等效安全路徑（index=SoT 方向一致）：① Edit 專案 `_atom_index.json` 該顆 triggers ② `python ~/.claude/tools/sync-atom-index.py --fix --memory-dir <專案memory根>`（官方語意＝以 index 覆寫 frontmatter Trigger）③ mirror 不自動跟：`from lib.atom_index_json import regenerate_atom_index_md` 手動重生 `_ATOM_INDEX.md`。

## 行動

- 專案層 broken_refs → 別呼 atom-heal，直接查正主名 + atom_edit_meta 換 Related
- 專案層補 trigger → 走 index→--fix→mirror 三步，勿直呼 atom_edit_meta triggers
- 根治待辦：兩工具補 project-root 支援後本 atom 可廢
