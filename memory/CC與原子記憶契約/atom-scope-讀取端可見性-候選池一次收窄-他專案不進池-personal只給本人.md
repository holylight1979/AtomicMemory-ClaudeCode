# atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: scope 可見性, 跨專案注入, personal 洩漏, 候選池, filter_visible, scope_from_rel_path, cross-project, alias 帶入, layers 白名單, 他專案 atom, scope 過濾
- Status: Phase 1 讀取端已封閉；Phase 2 本人跨專案 personal 層、Phase 3 寫入端路由與存量分流待做
- Created-at: 2026-09-01
- Related: realm-範疇分區機制-v5, scope-shared-無主題子夾路由-專案靠-project-hooks-sweep-分層, dashboard-apiatoms-專案-shared-範疇被-frontmatter-scope-覆寫誤歸核心房

## 知識

- [臨] scope 的正確實作位置是**候選池**，不是各檢索路：SessionStart 依 (user, roles) 建一次可見池（global + 本專案 shared/failures + 本人 roles + 本人 personal），trigger / BM25 / vector / related / AtomAudit 全從池取。在六條路各自加過濾必漏（實證：V4 只做了寫入端與 V4 佈局的 role filter，跨專案掃描、V3 佈局、向量 management 免過濾、related 跨層四處全漏）。
- [臨] 他專案 atom 一律不進池；他專案只在 prompt 命中其 `Project-Aliases` 時帶入 MEMORY.md 目錄（去表格列、去 personal/roles 行）。「他專案 trigger ≥2 就撈」這條路的根本問題是**由別的專案的搜尋去評價某專案 atom 的 trigger 泛不泛**——trigger 對它自己專案是對的，錯的只有沒看 scope 的搜尋。
- [臨] scope 由索引 path 推導（`personal/<u>/`、`personal/auto/<u>/`、`roles/<r>/`），不信 index 的 `scope` 欄：自動萃取寫入 index 時未傳 scope，`write_index` 新條目預設 global，實測 43/495 條專案層條目 index 寫成 global。
- [臨] 向量服務索引的是**所有專案**的層，`layer LIKE 'shared:%'` 本身就是跨專案；要用明確 `layers` 白名單（`visible_vector_layers`）而非 user/roles clause。管理職不豁免——管理職多的是待審清單，不是他人 personal（SPEC V4 §8.2）。
- [臨] `to_atom_entries` 把 index 的 scope 欄丟掉是全部 hook 讀取鏈的入口；改 tuple 形狀牽動所有 3-tuple 解包點，所以走「池內只裝可見的 + state 另存 name→scope 表」而非擴 tuple。

## 行動

- 動任何檢索路前先問：候選池對不對？對了就不要在該路再加過濾
- 新增可見性規則 → 改 wg_atoms.entry_visible 一處 + verify_scope_visibility 加案
- 跨專案需求一律走 MEMORY.md alias 行，不開 atom 級跨專案掃描
