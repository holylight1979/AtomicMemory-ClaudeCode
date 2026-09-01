# scope-shared-無主題子夾路由-專案靠-project-hooks-sweep-分層

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: scope=shared, 主題子夾, 專案 atom 分層, _resolve_target, project_hooks, classify-project-atoms, _unclassified, shared 扁平落根, project delegate hook, 專案記憶分類, atom_write append 失敗, Atom not found, locate_existing_atom, 落點 vs 定位, subdir atom, subdir, scope 沿用, atom-move scope, memory/projects 分區, trigger 長度
- Created-at: 2026-06-26

- Related: auto-capture碎片sweep污染詞庫-defer根治, realm-範疇分區機制-v5, 專案等級-mcpskillhookslog-不放全域根層, atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人

## 知識

- [臨] **落點規則**：`lib/atom_io.py:_resolve_target` 對 realm=local（→ `_AIDocs/_atoms/<domain>/`）與 feedback-（→ `_AIDocs/Failures/`）做物理子夾路由；scope=shared 預設扁平落 `shared/`，另可用 `subdir` 參數（**相對 memory root**、僅 scope=shared、僅影響 create 落點）一次寫到 `memory/projects/<專案名>/` 等分區；逐段 `_clean_segment` 沙盒化，personal/roles/episodic 等保護段拒絕（py `project_subdir_target` / js `resolveSubdirTarget` 鏡像）。敏感 audience → `_pending_review` 路由優先於 subdir。auto-capture 草稿另由 extract-worker._flush_route 隔離到 `shared/_drafts/auto-capture/`。
- [臨] **落點 ≠ 定位**：append/replace（及 create 撞名防叉）統一走 `lib/atom_locations.locate_existing_atom`：`_atom_index.json` path 優先 → 落空 rglob → 撞名列候選明確報錯。防護是**段層級**（相對路徑含 `_LOCATE_SKIP_DIRS`/`_archive*` 段即拒，含 personal/roles），非整棵搜尋根限制；shared 搜尋根＝整個 memory root，所以歸位到 `projects/<X>/` 等兄弟子夾的 atom 一步命中；role/personal 維持窄根不跨界。
- [臨] **scope 沿用鐵律**：索引 scope 由 create 寫 scope_label；replace/edit_metadata/`write_index(scope=None)` 一律**沿用既有條目**（新條目才預設 global）；atom-move 含 cross-root 一律沿用、`--scope` 明給才變、scope_changed 據實。frontmatter `- Scope:` 是漂移偵測的正確源（sync-atom-index scope_drift）。
- [臨] trigger 長度上限 `TRIGGER_MAX_LEN=30`（lib/atom_index_json 單一常數）在**寫入當下**即驗（py write_atom/write_index + js toolAtomWrite 雙入口，create/replace 才驗）；append 不動既有 triggers，legacy 超長 atom 仍可 append。atom_edit_meta 支援專案層：index root 以 `find_index_dir` 上溯最近 `_atom_index.json`（lib.atom_index_json 單一實作，atom-move 共用），不硬編 ~/.claude。
- [臨] 專案要把 curated shared atom 分層 → **自建 taxonomy classifier 接 core 的 project delegate hook**（`hooks/handlers/_shared.py:_call_project_hook`），core 只在 session_start 呼 `<project>/.claude/hooks/project_hooks.py`；不把專案分類器硬接進 core wg_atoms.py。`_unclassified` 命名安全關鍵：`_` 前綴不在 sync-atom-index EXCLUDED_DIR_PARTS 內 → 仍入索引/注入；改用排除清單內名稱會讓 atom 靜默消失。
- [臨] 同族缺口辨識法：寫入端與維護端（promote/edit_meta/move）定位邏輯若各寫一份，子夾化後會「部分功能正常、只有 append/replace 壞」；除錯時別因 promote 能跑就排除定位問題。
- [臨] MCP `atom_write` 實際執行體是 **js**（`atom-tools.js` 解析路徑 → spawn `lib.atom_io_cli`）：只改 py 修不好 MCP 症狀；定位規則 py 單一來源（js 扁平落點 miss 才 spawn `locate`）。**js 改動需重啟 MCP server 才生效**。

## 行動

- 專案分區寫入：atom_write 加 subdir="projects/<名>" 一步到位，不必寫完再搬
- 改已歸位 atom 直接 replace/append（索引定位），禁四步 workaround
- 要變索引 scope 用 atom-move --scope 明給，不靠搜移點默改
- 改 atom 寫入/定位：py 改完必查 js 入口，並重啟 MCP server 驗證
- 新增待分類夾務必確認名稱不在 sync-atom-index EXCLUDED_DIR_PARTS
