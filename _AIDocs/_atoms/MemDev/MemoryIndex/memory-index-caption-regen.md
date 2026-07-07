# memory-index-caption-regen

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MEMORY.md, sync-memory-index, 描述欄, caption, atom_write regen, 裸名, syncMemoryIndex, 記憶索引, 索引描述, MEMORY.md 描述
- Created-at: 2026-06-01
- Related: atom-table-support, feedback-memory-system-doc-sync, realm-範疇分區機制-v5

## 知識

- [臨] MEMORY.md 的「說明」欄不是手寫真源：`sync-memory-index.py:extract_atom_caption` 讀每個 atom 檔的 **H1 第一行** 當描述。`atom_write`（global, mode=create/replace）會經 server.js `syncMemoryIndex()`（server.js:1320/1438，gated scopeLabel===global）**背景 fire-and-forget** spawn `sync-memory-index.py --write` 重產整個 MEMORY.md（detached/stdio ignore → 靜默、無提示）。
- [臨] 覆轍成因：走 funnel 的 atom `H1=裸 kebab-name`（`build_atom_content` 令 title=slug=H1）→ regen 把描述還原成裸名；多 session 手改 MEMORY.md 描述 → 下次任何全域 atom_write 又被沖。**修法 2026-06-01（Option B 外科保留，僅動 sync-memory-index.py 單檔）**：新增 `parse_existing_captions()`，`render_atom_section()` 在 H1 caption 退化成裸名/空時沿用現有較豐富描述。**精準度：描述性 H1 > 現有人工描述 > 裸名**。故手改 MEMORY.md 描述列現在會持久、不再被沖；`--check` drift 消失。
- [臨] 實務：要給 funnel atom 描述，atom_write 後手編 MEMORY.md 該列一次即永久（preserve 保住）；別期待手改描述「自動」回灌 atom——真源是 H1 / 現在的 preserve。改 `sync-memory-index.py` 後**不需重啟 MCP**（server.js 每次 spawn 讀最新 .py）；只有改 server.js 才需重啟。trigger 注入與此完全無關（走 `_atom_index.json` SoT），本問題純人類/AI 索引可讀性。
- [臨] **同覆轍在 Trigger 上復發（2026-06）**：某「語義去重重生器」把 `_atom_index.json`(SoT)+4 atom frontmatter Trigger 砍到 12（丟 `上 SVN`/`pytest`/`測試上傳`/`並行加速` 等人工策展），然後 `sync-atom-index.py --fix` 把縮水的 index 推回 .md。`TRIGGER_MAX=12` 只是 memory-audit 建議值非截斷器；**重生器無 atom_io_audit 痕跡、未定位**（疑 bypass writer 或 LLM trigger-refine）——若 Trigger 再無故縮減，先查此。
- [臨] **funnel bypass 兩處（已修）**：`atom-health-check.py:fix_reverse_refs` + `sync-atom-index.py:fix_frontmatter_from_index` 原用裸 `Path.write_text` 繞過 lib.atom_io → Windows 翻整檔 EOL(double-CR) + 無 audit。已改走 `write_raw(source=tool:atom-health-audit / tool:sync-atom-index)`。教訓：funnel 合規要掃所有 atom 寫入路徑含 CLI 工具。
- [臨] **查 atom 寫入 corruption 工具鏈**：node byte-level 行尾分類（MSYS2 `grep $'\r\r'`/`file` 對 CR 不可靠、會誤導）+ `_meta/atom_io_audit.jsonl` 看 source/op（無痕=bypass）+ `sync-atom-index.py --check`(has_drift) + git churn `--ignore-all-space` 分 EOL/內容。
- [臨] **caption preserve 跨兩檔（2026-06-04 catalog 層 realm 拆分）**：sync-memory-index 改雙輸出（`MEMORY.md` core-only + 側檔 `memory/_local_catalog.md`）；`main()` 把 `existing_caps` 合併兩檔（`parse_existing_captions(MEMORY.md)` ∪ `parse_existing_captions(_local_catalog.md)`），migration 首跑本地描述仍在舊 MEMORY.md→自動保留進側檔、之後住側檔。原 `render_atom_section` 拆成 `render_core_section`/`render_local_catalog`（+共用 `_classify_rows`），caller 測試已對應更新。`--check` 改驗兩檔任一 drift→exit1。機制全貌見 [[realm-範疇分區機制-v5]]。

## 行動

- 改 MEMORY.md 渲染/描述邏輯後跑 `python tools/sync-memory-index.py --check` 應 exit 0
- 給 funnel atom 描述：atom_write 後手編 MEMORY.md 該列一次（preserve 會保住）
- 別改 atom .md 的 H1 當描述用（funnel atom H1=slug，改了壞檔名映射）
