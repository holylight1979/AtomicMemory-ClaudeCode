# 記憶管線演進 — atom 從寫入到注入的設計變遷

> atom 怎麼被寫進來、怎麼分類、怎麼被挑出來注入、預算怎麼算——這些機制每次改版「為什麼改、否決了哪些路、數字怎麼變」的紀錄。現況只看 `TECH.md`／`SPEC_ATOM_V5.md`。

| 檔 | 一句話 |
|---|---|
| `atom-evolution.md` | 早期各 atom 的演化日誌彙整（按 atom 分組） |
| `memory-pipeline.md` | 2026-04 記憶檢索管線 + 回應知識捕獲 + V3 三層即時管線（含已除役的 hot cache／quick-extract） |
| `wisdom-engine.md` | Wisdom Engine 反思機制 + Fix Escalation Protocol（V4 時代，已退役） |
| `atom-trigger-source-of-truth.md` | atom trigger 三個來源（frontmatter／_ATOM_INDEX／MEMORY.md）不一致的分析，定案 `_atom_index.json` 為唯一真相源 |
| `atom-injection-refactor-2026-04.md` | REG-005 注入機制重構（摘要優先、預算、冷熱、相關卡四層）收尾報告與設計歸檔 |
| `taxonomy-engine-半統一設計-2026-06.md` | 分類／去蕪統一引擎的半統一裁決：`score_by_lexicon` 單一計分源、晉升閘；去蕪引擎後來停產 |
| `auto-memory-writeback.md` | 對談結束自動記憶 writeback 三階段的開發脈絡（落點路由、失敗骨架、Deep Post-Mortem Gate） |
| `核心記憶分類階層化-2026-08.md` | 核心 atom 從 `memory/` 平鋪改成範疇資料夾（S1–S5）：起因、否決方案、五階段 commit 與驗證數字 |
| `injection-budget-investigation-2026-08.md` | 「注入變弱」調查：三個假設證偽、根因是回合預算上限、五次修正各附證據與 commit |
