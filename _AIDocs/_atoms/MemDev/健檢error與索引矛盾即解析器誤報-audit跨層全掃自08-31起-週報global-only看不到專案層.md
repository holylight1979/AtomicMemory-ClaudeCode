# 健檢error與索引矛盾即解析器誤報-audit跨層全掃自08-31起-週報global-only看不到專案層

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: memory health, memory-audit, 缺少必要欄位, health error, dashboard 問題, 解析器誤報, Decided-by, 跨層掃描, discover_layers, health-weekly, 為什麼會錯那麼多
- Created-at: 2026-09-04
- Related: 記憶索引分類讀寫鏈總審計結論-驗無誤清單與一條龍中斷點, usefulness晉升軌兩級同門檻-同日連跳觀到固的假晉升

## 知識

- [臨] 健檢報 format error（缺 Scope/Confidence/Trigger）時先對照 `_atom_index.json` 該 atom 的 triggers：索引有、audit 說沒有 ＝ audit 解析器與寫入端布局不合，不是資料壞；別去改專案樹的 atom 檔。已知一例：conflict-review 核可插的 `- Decided-by:` 曾把 metadata 區塊切成兩段（已修）。
- [臨] `memory-audit.py` 的 Summary 數字是全機 13 層（根層＋12 個登記專案樹）加總；根層自己的問題要看 atom-health-check 或按檔案路徑過濾。跨層全掃自 2026-08-31 `7d8ad5f` 起（`discover_layers` 改走 registry），之前只掃 `~/.claude/projects/` 舊址，所以專案樹的舊問題會「突然」冒出來，不代表近期改壞。
- [臨] 週健檢 `health-weekly.py` 跑 `--global-only`，專案層 error 永遠不進週報；dashboard 跑全掃。兩邊數字不同是掃描範圍差，不是 py↔js 差（dashboard 直接呼叫 Python audit）。
- [臨] Trigger 數量 info（建議 3~12）是純提示：效果報表 Top 有用 atom 的 trigger 多在 13~24，這條門檻與實務脫節，看 error/warning 就好。
- [臨] atom 檔的 metadata 解析器有三套：`lib/atom_spec.parse_frontmatter`（atom-move／atom-heal／acceptance 共用）、`tools/memory-audit.parse_atom_file`、`tools/atom-health-check.parse_frontmatter`；索引與注入端不解析 .md，只讀 `_atom_index.json`。改 metadata 布局規則（空行、欄位順序、新欄）要三套一起看，新欄名須登記 `OPTIONAL_METADATA` 否則 audit 報「未知欄位」。
- [臨] `move_to_distant` 把 atom 移到「原範疇資料夾」下的 `_distant/<yyyy_mm>/`（例 `memory/OS-Windows/_distant/`），不是 `memory/_distant/`；要数、要搜、要 restore 都要 rglob 所有 `_distant/`。

## 行動

- health 出 format error → 先查索引 triggers，索引正確就查 audit 解析器
- 判斷「近期改壞」前先看該 atom 所在層何時開始被掃到
- 根層健康看 atom-health-check --report；memory-audit 摘要數字要按層過濾再解讀
