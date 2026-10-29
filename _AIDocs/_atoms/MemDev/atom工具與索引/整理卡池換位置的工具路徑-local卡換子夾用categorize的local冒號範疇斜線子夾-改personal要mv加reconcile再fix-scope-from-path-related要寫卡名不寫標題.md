# 整理卡池換位置的工具路徑-local卡換子夾用categorize的local冒號範疇斜線子夾-改personal要mv加reconcile再fix-scope-from-path-related要寫卡名不寫標題

- Scope: global
- Author: holylight
- Source: session bc7c5340 MemDev 分 11 子夾與 v6總控台卡池復活
- Confidence: [臨]
- Trigger: 整理卡池, 分子夾, 換子夾, atom-categorize, local:MemDev, 改 personal, fix-scope-from-path, Related 斷連, 從 _distant 還原, memory-audit --restore
- Created-at: 2026-10-29
- Related: realm-範疇分區機制-v5, atom-move-v5-sot-correct-化與半遷移工具辨識
- Quote: 「對了，提醒：完成以後請記得要檢查一次所有 INDEX檔案是否都有正確更新。」

## 知識

- [臨] local 卡（`_AIDocs/_atoms/`）換子夾：寫 map `{"atoms": {slug: "local:MemDev/<子夾>"}}`，`atom-categorize.py plan` 看 errors＝0 再 `apply`（委派 atom-set-realm，`.md`＋`.access.json` 一起搬、索引同步、落 undo.json）。跨到別的 local 範疇同法寫 `local:<範疇>`。
- [臨] 卡改成 personal 跨專案：`atom_move` 的 move 目標走範疇閉合清單會拒 `personal/<user>`；做法是手動 mv 兩檔到 `memory/personal/<user>/` → `atom_move reconcile`（它不改 scope，scope 參數無效）→ `sync-atom-index.py --fix-scope-from-path` 把索引 scope 與檔頭 `- Scope:` 改成 `personal:<user>`。跑 fix 前先算懸空條目數，它會順手刪懸空條目。
- [臨] 從退役區拉回卡用 `memory-audit.py --restore <_distant 下的檔>`，之後跑 `sync-atom-index.py --add-from-frontmatter` 確認有登進索引，再搬目標夾。
- [臨] Related 要寫卡名 slug（全小寫、空白與 `=` 等變 `-`），照標題原樣寫（大寫、空白）會靜默斷連，健檢不報；整理完用卡名集合掃一次 Related 斷連。
- [臨] 收尾：`sync-memory-index.py --write` → `--check` 要 `MEMORY_INDEX_CHECK PASS`；`sync-atom-index.py --check` exit 0；`native-memory-bridge.py --slug <slug>` 重產橋接檔；find 確認範疇子夾裡沒有多出 `_atom_index.json`／`_ATOM_INDEX.md`。

## 行動

- 整理卡池前先 plan 再 apply，留 undo.json 路徑
- 整理完掃 Related 斷連、重產索引與橋接檔、find 假索引檔
