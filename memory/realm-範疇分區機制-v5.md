# Realm 範疇分區機制 (V5+)

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: realm, 範疇分區, 核心非核心, local atom, _AIDocs/_atoms, 注入閘門, atom 物理位置, promote fallback, wg_core bootstrap, 記憶系統
- Created-at: 2026-06-03
- Related: decisions-architecture, memory-index-caption-regen, feedback-workflow-discipline, 腦內世界-環境演化-放置式架構

## 知識

- [臨] Realm（核心 vs 非核心）由 index path 前綴 `_AIDocs/_atoms/` **推導**，不存欄位/不寫 frontmatter/免 heal；與 Scope 正交，local atom 仍 `Scope=global`。核心住 memory/、全專案注入；local 住 `_AIDocs/_atoms/<domain>/`（World/Tools/MemDev），只在 cwd∈~/.claude 注入。
- [臨] 沿用 feedback-* 既有機制：物理檔在 `_AIDocs/` 下、靠 `_atom_index.json` 的 path（base_dir=CLAUDE_DIR join）被讀出注入；`_AIDocs/_atoms/` 與 feedback 的 `_AIDocs/Failures/` 不同前綴、零衝突。零新管線。
- [臨] 注入閘門（範疇限定）落在 SessionStart 建候選快取處依 cwd 過濾 path 前綴，**非** user_prompt_submit 注入迴圈（候選只在 SessionStart 建一次，迴圈只讀快取）。
- [臨] 坑（S1 已踩中並修）：物理在 memory/ 外的 atom（Failures / _atoms）必須在 server.js promote/edit_meta/find 加 `findAtomFileRecursive(LOCAL_ATOMS_DIR, ...)` find-fallback（鏡像 feedback fallback），否則 scope=global 的 local atom 會 `Atom not found`。
- [臨] 坑：wg_core 的 `CLAUDE_DIR` 必須**本地定義**（它用來 `sys.path.insert` 定位 lib/atom_locations 本身），不可改成 `from atom_locations import CLAUDE_DIR`（雞與蛋）。MEMORY_DIR 同源同值、改 import 只增 fallback 脆弱性、零實益。
- [臨] 坑：搬遷工具 atom-set-realm（Phase 3）必須連 `.access.json` sidecar 一起原子性搬，否則 confirmations/usefulness 計數歸零、[固] 可能掉回 [臨]。
- [臨] 分類器硬規則：核心保護清單（decisions*/workflow-*/toolchain*/preferences/feedback-*/atom-*）強制 core；**絕不靠 `_AIDocs/` 路徑前綴判 local**（feedback-* 就在 _AIDocs 卻是 core）。py↔js 常數對拍見 lib/verify test_14。
- [臨] Phase 4 文件同步完工（S3）：rules/core.md「記憶」加 Realm 小節（核心判定三問：可重用≥2 專案？／系統規則 vs 特定 app·工具·環境範疇？／月級 vs 週級？）+ SPEC_ATOM_V5 §2.2 Realm 章 + Architecture「記憶系統」Realm 子節 + decisions-architecture 印象 bullet。寫入引導：server.js atom_write schema 的 realm/domain description（S1 已備）+ extract/SKILL 萃取時判 realm 提示。
- [臨] MEMORY.md「本地範疇（~/.claude）」段（防護 R4 印象層斷點）：sync-memory-index render 把 path 落 `_AIDocs/_atoms/` 的 atom 抽出主表、依 domain（MemDev/Tools/World）分組進尾段；lib.atom_locations `atom_index_row_kind` 加 `local_realm` 種類 + `local_realm_domain()` 抽 domain。round-trip 穩定（`--write` 後 `--check` exit 0、idempotent）；caption preserve 沿用一般規則（H1 裸名→用現有人工描述）。與 [[memory-index-caption-regen]] 共用同一 render 函式。
- [臨] 本顆自身判定＝core（不歸 local）：記憶系統「機制」屬系統規則、非特定 app·工具範疇實例，與 decisions-architecture / memory-index-caption-regen / atom-usefulness-loop 同類核心；分類器安全預設 core 守之——`test_16` 鎖 `realm-範疇分區機制-v5` → realm=core, protected=False（詞庫無命中、非保護清單但安全預設）。
- [臨] **catalog 層 realm 拆分（2026-06-04，取代上項「MEMORY.md 尾段」做法）**：realm 原則貫徹到 **index/catalog 層**。原本 gate 只擋 atom **body** 注入，但 catalog（MEMORY.md 全文含本地範疇段）走 CLAUDE.md 靜態 `@import` 漏進每個外部專案 always-load（~450 tok）。修法：sync-memory-index render 雙輸出——`render_core_section`→`MEMORY.md`（@import、全專案、**fail-safe 退路**+免 compact 失憶）；`render_local_catalog`→側檔 `memory/_local_catalog.md`（自含 H1+domain 子表），僅核心環境由 `session_start.py` 共同尾段（`_is_under_claude_dir` gate）注入。共用 `_classify_rows`；caption preserve 跨兩檔合併；`_` 前綴側檔不被任何 scanner 當 atom（server.js / wg_atoms / is_atom_file 皆 skip `_*`）。CLAUDE.md 與 server.js 零改。守門 `tools/verify/verify_local_catalog_split.py`。見 [[memory-index-caption-regen]]。
- [臨] **V6（2026-06-04）LLM-assisted recall + 關聯式分級階層**：詞庫封閉 allow-list 漏判（wsl2 漏進 core）的根治。① **LLM fallback**（`tools/realm_llm_classify.py`，複用 atom-heal Ollama 樣板）掛 **SessionEnd sweep**（`wg_atoms._sweep_realm_auto_migrate`）；server.js 寫入熱路徑**不**掛 LLM。只對「unknown core」（非 protected、詞庫 miss）喚 LLM，`max_per_session` 限額。
- [臨] **V6 Fail-safe 四態**（紅線：protected 永不喚 LLM、恆 core）：`error`(連不到 backend/逾時)→**defer 留原地**（防 Ollama 離線把全部 unknown-core 掃進 Else）；`core`→留；`local`≥`min_confidence`→搬 canon domain；`unsure`/低信心→`_AIDocs/_atoms/Else`（catch-all，取代舊 Misc）。config `realm.llm_fallback{enabled,backend,max_per_session,min_confidence}`。
- [臨] **V6 關聯式分級階層 domain**：多段路徑 `_AIDocs/_atoms/<L1>/<L2>/…/`（Lv 小=範疇廣）。canon `normalize_domain_path`：逐段對同層既有兄弟 snap（大小寫無視精確 ∨ 前綴包含 len≥3 治 Win→Windows ∨ difflib≥0.85）+ `_clean_segment` 拒 path-traversal。**增量深度閘（depth=volume）**：新分支封頂 `LOCAL_REALM_NEW_BRANCH_DEPTH=3`、只能比『既有已積 atom 的最深匹配前綴』深 1 層 → 深度隨內容量長、不被 LLM 一次灌深（絕對天花板 `MAX_DEPTH=7`）。dogfood 揭露 LLM 深度飄移 Lv3~5、靠本閘 deterministic 落實。
- [臨] **V6 詞庫自學閉環**：LLM 判 local 後 validated terms→domain_path atomic append `memory/_meta/realm-lexicon-learned.json`（py-only；`classify_realm(extra_lexicon=)` 合併 base+learned；**js 維持 base-only 保 test_17 parity**）。`_validate_terms` 剔系統通用詞/過短/自身命中 protected 的詞（防 learned 反殺核心）。→ 下次 deterministic 命中免 LLM。
- [臨] **V6 catalog 階層化**：`_local_catalog.md` always-load **只 Lv1 根+遞迴計數+drill**（O(根數) 不隨 atom 量膨脹）；每層 `_INDEX.md` **按需**（有子層 ∨ atom≥2；`_` 前綴非 atom）；單葉 drill 直指 atom 檔（除雞肋）。`sync-memory-index --write` 寫全部+清 stale、`--check` drift/stale→exit1、caption preserve 擴及 _INDEX。sweep 搬後補觸發 --write。
- [臨] **V6 移檔後 doc-sync**（移檔非建檔特有）：`_scan_doc_refs` 掃 `_AIDocs/`(排除 atom 物理區)+根 docs 查舊 path/檔名殘留引用 → sweep marker 附『需同步文件』 / `/refile` 互動列出。Related 用 slug 搬 path 不斷；風險僅 path/檔名引用。
- [臨] **V6 注意**：server.js 改動（applyLocalRouting 多段 / Else / cleanRealmSegment）**需重啟 MCP 生效**；sweep/CLI/set_realm py 端即時生效。set_realm 多段 domain + `_prune_empty_parents` 清空階層夾。守門：test_18/22 + verify_realm_llm_classify(9)/verify_realm_sweep(10)/verify_local_catalog_split(深樹+stale)。

## 行動

- 新 local 知識：atom_write 帶 realm=local + domain（需 MCP server 重啟生效）
- 改任何 atom 物理位置：同步 server.js promote/edit_meta/find 的 fallback + 連 .access.json 搬
- 完整機制/文件同步在 Phase 4；本顆為 S1 種子 [臨]，Phase 4 擴充並決定是否歸 MemDev-local
