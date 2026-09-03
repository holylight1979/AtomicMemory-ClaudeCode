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
- [臨] personal 分兩種、同一套讀取規則：本人×專案住 `{proj}/.claude/memory/personal/<u>/`，本人×跨專案住 `~/.claude/memory/personal/<u>/`（索引在全域、path 前綴 `memory/personal/<u>/`）。讀取端不需第二套判斷——`scope_from_rel_path` 看到 `personal/<u>/` 就只給 u，不管它在哪個根。寫入端 `atom_write(scope=personal, cross_project=true)` 或從 ~/.claude 呼叫即落跨專案層。
- [臨] personal 在全域根要躲三個會把它當一般核心 atom 的機制：MEMORY.md 目錄產生器（`atom_index_row_kind` 回 personal → 不渲染）、realm 自動搬移（跳過）、vector indexer 的 global 遞迴掃（排除 `personal/`，另立 `personal:global:<u>` 層）。`personal` 因在 `SKIP_DIRS` 而天然不能當範疇名，但 `is_atom_file` 需對 `personal/<u>/<slug>.md` 開例外，否則 sync-atom-index 會報索引條目找不到檔。
- [臨] 寫入端的分界：「這條規則是遷就專案還是遷就我？」——提到專名、此專案、上傳/發布/必須/禁止 的是專案規則 → shared + Author=提出者；自動萃取（user-extract-worker）同規則，Author 不再是硬編來源字串，來源靠知識段 `<!-- src: turn -->`。存量清冊實證：31 顆 personal 裡 19 顆其實是專案規則、自動萃取寫進專案 index 的 scope 欄 45 條是錯的（預設 global）——所以讀取端信 path 不信欄位。

## 行動

- 動任何檢索路前先問：候選池對不對？對了就不要在該路再加過濾
- 新增可見性規則 → 改 wg_atoms.entry_visible 一處 + verify_scope_visibility 加案
- 跨專案需求一律走 MEMORY.md alias 行，不開 atom 級跨專案掃描
