# scope-shared-無主題子夾路由-專案靠-project-hooks-sweep-分層

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: scope=shared, 主題子夾, 專案 atom 分層, _resolve_target, project_hooks, classify-project-atoms, _unclassified, shared 扁平落根, project delegate hook, 專案記憶分類, atom_write append 失敗, Atom not found, locate_existing_atom, 落點 vs 定位, subdir atom
- Created-at: 2026-06-26
- Related: realm-範疇分區機制-v5, auto-capture碎片sweep污染詞庫-defer根治, 專案等級-mcpskillhookslog-不放全域根層

## 知識

- [臨] **落點規則**：`lib/atom_io.py:_resolve_target` 只對 realm=local（→ `_AIDocs/_atoms/<domain>/`）與 feedback-（→ `_AIDocs/Failures/`）做物理子夾路由；scope=shared/role/personal 的**新** atom 一律扁平落 `<project>/.claude/memory/{shared | roles/<r> | personal/<u>}/<slug>.md`——write 端不猜主題子夾，curated 專案 atom 的分層是**事後** classifier sweep 的職責。auto-capture 草稿另由 extract-worker._flush_route 隔離到 `shared/_drafts/auto-capture/`（不入索引、不注入）。
- [臨] **落點 ≠ 定位**：append/replace 的實體檔常已被 sweep 歸位到子夾，只看扁平落點會誤判 `Atom not found`（子夾化的專案 memory 會 append/replace 全線失效；realm=local 的 global atom 在 domain 給錯/沒給時同理）；而 Guardian AtomFunnelBlock 又擋直接 Write/Edit .md → 「唯一合法入口打不到檔」死結。定位統一走 `lib/atom_locations.locate_existing_atom`：`_atom_index.json` 的 path 優先（需落在該 scope 搜尋根內，跨 scope 保護）→ 落空 rglob scope 子樹（跳過 _drafts / _pending_review / personal / _archive* 等草稿與封存）→ 撞名列出全部候選明確報錯、不靜默取第一個；索引回寫 path 由定位到的實體路徑推導，不寫扁平假路徑。守門 `lib/verify/verify_atom_subdir_locate.py`。
- [臨] 專案要把 curated shared atom 分層 → **自建 taxonomy classifier 接 core 的 project delegate hook**（`hooks/handlers/_shared.py:_call_project_hook`：subprocess / 5s timeout / never-raises），core 只在 session_start 呼叫 `<project>/.claude/hooks/project_hooks.py`（session_start.py:442）。不該把專案分類器硬接進 core wg_atoms.py（會耦合單一專案 taxonomy + 打全專案最熱寫入路徑，違反 realm 分區）。
- [臨] C:/Projects 的實作：project_hooks.handle_session_start → `_auto_classify_shared_atoms` → importlib in-process 載 `tools/classify-project-atoms.apply_classification`（taxonomy 計分 name×10>trigger×1；無命中 → `shared/_unclassified/`，每次重掃 _unclassified → 補詞庫後自動畢業到主題夾）。搬移後當 session 不靜默、注入提示行——仿核心 `_sweep_realm_auto_migrate` + `REALM_AUTOMOVE_MARKER` 的 1-session-lag 慣例。
- [臨] `_unclassified` 命名安全關鍵：`_` 前綴**不在** sync-atom-index `EXCLUDED_DIR_PARTS`（=_drafts/_archived/_pending_review/_staging/templates/wisdom/episodic/_reference）內 → 落此夾的 atom **仍入索引/注入**（curated 知識不轉暗），`_` 只作視覺「待補詞庫」標記。若改用排除清單內名稱會讓 atom 靜默消失。
- [臨] 同族缺口辨識法：atom 的**寫入端**（atom_write）與**維護端**（atom_promote / atom_edit_meta / atom-move）定位邏輯各寫一份，而維護端本就用 `findAtomFileRecursive` / `locate_md` 遞迴 → 子夾化後 promote/edit_meta 正常、只有 append/replace 壞。「部分功能正常」正是這類缺口難被發現的原因；除錯時別因為 promote 能跑就排除定位問題。
- [臨] MCP `atom_write` 的實際執行體是 **js**（`tools/workflow-guardian-mcp/lib/atom-tools.js:toolAtomWrite` 解析路徑 → spawn `python -m lib.atom_io_cli` 落檔）：只改 `lib/atom_io.py` **修不好 MCP 症狀**，js 端路徑解析才是入口。定位規則不在 js 維第二套：js 於扁平落點 miss 時 spawn `atom_io_cli` 的 `locate` action（正常路徑零額外 spawn），`findAtomFileRecursive` 只留給 promote/edit_meta。**js 改動需重啟 MCP server 才生效**（同 realm.js 慣例）。

## 行動

- 專案要 shared atom 分層：寫 taxonomy classifier + 接 project_hooks session_start，勿動 core
- 判斷 atom 是否該分類：有 .access.json/已索引=curated 該分；_drafts/auto-capture 下=草稿不動
- 新增待分類夾務必確認名稱不在 sync-atom-index EXCLUDED_DIR_PARTS，否則 atom 會脫索引
- 改 atom 寫入/定位：py 改完必查 js 是否才是真正入口，並重啟 MCP server 驗證
