# atom 元資料編輯與晉升閘真相

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: edit_metadata, atom 元資料編輯, atom_edit_meta, trigger 裁減, 改 trigger, atom 晉升, ReadHits, usefulness, 晉升閘, access.json, sidecar, 行尾損壞
- Created-at: 2026-06-02
- Related: feedback-tooling-reliability, memory-pipeline-silent-failure-2026-05, atom-usefulness-loop, feedback-memory-system-doc-sync

## 知識

- [臨] 改 atom 的 metadata（Trigger/Related/Tags）走 `lib/atom_io.edit_metadata()` 或 MCP `atom_edit_meta`（改全域 server 需重啟生效）：只替換 frontmatter 對應行、byte-stable、triggers 變更時先寫 `_atom_index.json`(SoT) 再寫 frontmatter（衍生）。**禁**直接 Edit atom .md（Guardian funnel guard 擋）或整檔 atom_write replace（重建知識區、風險高）。2026-06-02 新增。
- [臨] atom 晉升真閘 = usefulness Wilson 下界(lb≥0.6 且 n≥3) 或 confirmations(≥4/≥10)；**ReadHits 純曝光、不參與晉升**。memory-audit.py 舊版用退役 ReadHits 閾值(≥20/≥50) 吐假晉升，2026-06-02 已對齊 `lib/atom_access.usefulness_promote_eligible`（server.js:1607 的 py 鏡像）。判讀/質疑晉升一律看 usefulness lb + confirmations，勿信純 ReadHits。
- [臨] atom 計數欄（read_hits/confirmations/last_used）存 `<atom>.access.json` sidecar（Wave 2 後 .md inline 已移除）；讀取走 `lib/atom_access.read_access(path)`。工具若仍讀 .md inline 會全 atom 誤報 missing（atom-health-check.py 2026-06-02 已修）。
- [臨] memory-audit parser 已容忍 `\r\r\n` 雙CR（讀 bytes→正規化→splitlines）並對壞檔 emit「行尾損壞」warning；壞行尾根因（atom_write append 混 EOL）見 [[feedback-tooling-reliability]]。

## 行動

- 改 atom trigger/related/tags → edit_metadata / atom_edit_meta，不直接 Edit .md
- 判讀或質疑 atom 晉升 → 看 usefulness lb + confirmations，非 ReadHits
- 工具讀 atom 計數 → read_access(sidecar)，非 .md inline 欄位
- 改完 trigger 跑 `python tools/sync-atom-index.py --check` 驗 SoT↔frontmatter 0 drift
