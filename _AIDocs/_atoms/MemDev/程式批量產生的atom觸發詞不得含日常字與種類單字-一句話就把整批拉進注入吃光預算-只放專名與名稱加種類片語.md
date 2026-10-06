# 程式批量產生的atom觸發詞不得含日常字與種類單字-一句話就把整批拉進注入吃光預算-只放專名與名稱加種類片語

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 工具卡觸發詞, 批量產生 atom, 觸發詞擾民, 注入預算被吃光, scan-tools, _card_triggers, 泛詞 trigger, trigger 設計, refresh_legacy_triggers
- Created-at: 2026-10-05
- Source: session:d892b7c9#67e1307f 2026-10-05
- Quote: 「OK，那就補 Org skill 吧」

## 知識

- [臨] 實踩（2026-10-05）：`org-memory.py --scan-tools` 早期給每張工具卡的觸發詞是「卡名＋裸名＋種類單字＋說明關鍵字」（如 `skill-memory, memory, skill, …`）。使用者一句「那就補 Org skill 吧」→ 七張 skill 工具卡同時 trigger 命中被注入，注入預算 976/1000 全被吃掉，真正相關的記憶進不來。24 張卡每張都帶 `skill` 或 `mcp`，等於句句中獎。
- [臨] 規則：程式批量產生的 atom（工具卡、匯入卡、掃描卡），觸發詞只放**專名**與「名稱＋種類」片語（`skill-memory`、`memory skill`、`工具卡 memory`）；不放裸名（工具名多是 memory／handoff／continue／extract 這類日常字）、不放種類單字、不從說明文字切關鍵字。用名稱查仍找得到：`memory_search` 的 BM25 以卡名與觸發詞斷詞；語意查走向量。
- [臨] 遷移手法：掃描器 `refresh_legacy_triggers` 以「索引觸發詞含種類單字」判定舊世代卡，經 `lib.atom_io.edit_metadata` 只換 Trigger 行與索引（正文不動、人工改過觸發詞的不命中）；索引名是 slug（小寫），卡名可能含大寫（`mcp-MCPControl`）→ 比對前要 `slugify`。守門 `tools/verify/verify_tool_cards.py::test_tool_card_triggers_do_not_fire_on_generic_words`、`::test_legacy_triggers_are_refreshed_but_manual_ones_are_kept`。

## 行動

- 寫任何批量產 atom 的工具：上線前拿三句日常話（含種類字、含常見工具名）跑 `wg_atoms.any_trigger_hit` 確認不命中
- 看到某類 atom 成批被注入 → 先看它們共有的 trigger 字，再回頭修產生器並寫遷移，不逐張手改
- 批量卡比對索引一律用 slug
