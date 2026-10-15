# episodic衍生提示讀取池要與寫入端同源-專案session不併根層池-全機單檔狀態要依池分格

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 覆轍, Guardian:覆轍, Guardian:Oscillation, oscillation_state, episodic 池, 跨專案洩漏, 開場提示雜訊, _detect_rut_patterns
- Created-at: 2026-10-15
- Related: atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人
- Source: session:afddb6f8#868354d9 2026-10-15
- Quote: 「這是我在專案層做token消耗檢查時CC提出的問題，請找出問題並根治 (最高優先)： ``` <pasted_content id="c0cb"> [根層] 覆轍提示跨專案洩漏，請修根因。 現象：在 某專案 專案 session 啟動時，[Guardian:覆轍] 列出 15 個根層檔（verify_release_rules.py、wg_need_goal.py、overview_hub.py…」

## 知識

- [臨] episodic 衍生的開場提示（[Guardian:覆轍]、[Guardian:Oscillation]）讀取池必須與寫入端 `wg_core.resolve_episodic_dir` 同一目錄（`wg_evasion._session_episodic_pool`）。曾把 `memory/episodic` 併進每個 session 再取最近 3 份：根層 session 多又新，專案自己的歷史整個被擠掉，專案開場列 15 個根層檔（約 260 token）。
- [臨] cwd 沒有專案記憶的 session 沒有自己的池 → 不提示（寫入端落 `memory/episodic`，但那是根層歷史）。全機單檔的衍生狀態（`workflow/oscillation_state.json`）要依池分格、池鍵不分大小寫，否則任一 session 收尾會覆寫或刪掉別專案的狀態。守門 `hooks/verify/verify_rut_scope.py`。
- [臨] 為什麼全量 run_verify 長期全綠卻沒抓到：既有覆轍測試只用單一池（cwd 空、沒有專案池），沒有「兩個池＋專案 session」的案例；全量只重驗既有斷言、防退化，不會發現沒人寫成案例的需求。這類「正確跑、結果對錯人」的問題要靠用本機真資料對專案 cwd 跑一次的探針才看得到。

## 行動

- 新增「讀 episodic／讀 workflow 全機檔」的開場提示前，先問它的讀取池是不是和寫入端同一個、會不會把別的專案的狀態帶進來
