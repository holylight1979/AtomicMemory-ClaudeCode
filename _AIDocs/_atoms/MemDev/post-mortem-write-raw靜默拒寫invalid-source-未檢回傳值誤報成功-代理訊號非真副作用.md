# post-mortem-write_raw靜默拒寫invalid-source-未檢回傳值誤報成功-代理訊號非真副作用

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: write_raw, atom_io, VALID_SOURCES, WriteResult, ok=False, 靜默失敗, 未檢回傳值, funnel, fail-soft, invalid source, 代理訊號, post-mortem, 批次寫入驗收, sync-atom-index
- Created-at: 2026-06-30
- Related: atom-元資料編輯與晉升閘真相, goal-driven-verify-loopkarpathy-吸收, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, escalation-hook-在-edit-count-proxy-上-false-fire-的辨識

## 知識

- [臨] **始末**：SGI Step-0 scope/index drift 修復，批次腳本以 `write_raw(p, new, source="tool:drift-fix", op="scope-correct")` 改 setsiegetime frontmatter `project→shared`。腳本以 `new != txt`（in-memory regex sub 成功）判定並印「FRONTMATTER FIX project->shared」，但**檔案實際沒變**。事後 `sync-atom-index.py --check` 仍報該顆 scope_drift（frontmatter=project）才抓到。正解＝改用合法 source `tool:sync-atom-index` 重寫，並以 `--check` 0 drift 為唯一驗收（write 回 ok=True、audit id 落地、Scope 實讀=shared）。
- [臨] **根因（非表面）**：拿「中間代理訊號」(字串替換在記憶體成功) 當「實際效果」(已落檔) 的證據。`write_raw` 是 **fail-soft**——source 不合法時回 `WriteResult(ok=False, error=...)` 而非 raise；呼叫端**沒接 WriteResult、沒 assert `res.ok`**→靜默吞錯。表面症狀「沒寫進去」，根因是「未驗證真實副作用 ＋ 未檢 funnel 回傳值」。
- [臨] **該區設計原理**：`write_raw` 用 `VALID_SOURCES` allowlist（lib/atom_io.py:46-65）＋回 `WriteResult`(不 raise) 是刻意治理——所有 atom 寫入須**具名來源**走 audit log / PreToolUse 放行清單；fail-soft 回傳讓 caller 自行處置、不中斷批次（適配 server.js spawn / 批次 caller）。代價＝靜默，把「檢成敗」責任轉嫁 caller。合法 source 例：`tool:sync-atom-index`、`tool:atom-move`、`mcp`、`test`…（完整見 lib/atom_io.py:46）。
- [臨] **運作邏輯／斷點**：`write_raw` 先 `if source not in VALID_SOURCES: return WriteResult(ok=False)` **在 `_atomic_write` 之前**即 return（lib/atom_io.py:409-411）→整個落檔被跳過。斷點＝caller 沒檢回傳。同批次 index 端 `upsert_atom`（4 顆 rescope + 2 顆 add）source 合法、正常落地，**只有** write_raw 那條被擋——「部分成功」更易掩蓋單點靜默失敗。
- [臨] **防再犯**：① 呼叫 atom_io funnel（`write_raw`/`write_atom`/`append_atom_file`）後**必檢 `result.ok`**（assert 或印 error），**勿用「輸入 diff 非空」當成功證據**；② source 必取自 `VALID_SOURCES`（lib/atom_io.py:46-65），勿自編字串；③ 批次記憶寫入永遠以**獨立 end-state 驗證**（此處 `sync-atom-index.py --check` 0 drift）為唯一驗收，不信腳本自報——本次正是 verify gate 救回（goal-driven-verify-loop 價值實證）。

## 行動

- 呼叫 write_raw/write_atom/append_atom_file 後檢 result.ok，失敗即停/報錯，勿信腳本自印成功
- 寫入 source 必取自 lib/atom_io.py VALID_SOURCES，勿自編
- 批次記憶寫入以獨立 end-state 驗證（如 sync-atom-index.py --check 0 drift）收尾，不信中間代理訊號
