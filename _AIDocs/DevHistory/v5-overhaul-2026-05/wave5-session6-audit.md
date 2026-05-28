# Wave 5 Session 6 — V5 文件 vs 運作邏輯 對齊檢定 audit 報告

> 時間：2026-05-27 ~ 2026-05-28
> 性質：V5 GA 簽收（commit `7667cb3`）後的實證對齊檢定。前盤點都是「文件 vs 文件」，本 session 補上「文件描述的機制是否實際運作」實測。
> Commits：里程碑 1 `6d1855d`（A+B RT + 4 doc fix）、里程碑 3 `a1e0781`（B/D/E/C 落地）
> 來源：原 `memory/_staging/next-phase.md` sections 6-9 歸檔（_staging 為 gitignored，歸至此處作永久證物）

## 摘要

- **RT1-13 對齊檢定 13/13 全綠**（含當場修補後）
- **中優先 B/D/E/C 全動**，F 已最簡不動
- 共 5 處 doc drift 當場修 + IDENTITY.md 整檔同步 template（後者 gitignored）+ 砍 4 檔（3 inbox + 1 shim）+ 建 1 目錄（failures/）

---

## RT 對齊檢定總結表

| 階段 | RT | 結論 | 修補 |
| --- | --- | --- | --- |
| A | RT11 SessionStart hook | ✅ PASS | — |
| A | RT12 hot_cache | ✅ PASS | — |
| A | RT13 audit source | ✅ PASS | — |
| B | RT1 BM25 | ✅ PASS | — |
| B | RT2 Codex subprocess | ✅ PASS | — |
| B | RT4 Dispatcher | ⚠️ PARTIAL→修正 | 4 處 doc drift 當場修 |
| B | RT5 MCP 3 tool | ✅ PASS | — |
| B | RT8 禁語 single source | ❌ FAIL→已修 | IDENTITY.md 整檔同步 template（gitignored 不入 commit） |
| B | RT10 Log rotation | ⚠️ PARTIAL→修正 | 1 處 doc drift 當場修 |
| C | RT3 JSON SoT | ✅ PASS | — |
| C | RT6 Stop quick-extract | ✅ PASS | — |
| C | RT7 funnel guard | ✅ PASS | — |
| C | RT9 Vector 全域退役 | ✅ PASS | — |

---

## 階段 A — session-start 即時驗

### RT11 SessionStart hook 復活 — ✅ PASS

- 證據 1：`workflow/state-c1a76b0e-aead-4af0-8988-4bbf11e312af.json` 為本 session 新檔，mtime `2026-05-28 08:58`（now=08:59:38）→ SessionStart 寫入正常
- 證據 2：舊孤兒 state file `04ef12ee` / `7138ec9a` 已被分層 TTL 清理刪除，僅保留 `c1a76b0e`（本 session）+ `e3fff2e3`（外部活躍）
- 結論：22 天靜默失效（2026-04-29 ~ 2026-05-21）已修復

### RT12 hot_cache 寫入 — ✅ PASS

- 證據 1：`workflow/hot_cache.json` size=1173 mtime=`2026-05-27 20:27:16`
- 證據 2：內容含 `"source": "deep_extract"` + `"injected": true` + `"knowledge": [...]` 完整結構
- 結論：5/18 後停擺證據消失（5/27 確有新寫入）

### RT13 atom_io_audit source contract — ✅ PASS

- 證據：`memory/_meta/atom_io_audit.jsonl` tail -8 全部 entries 為 `"source": "hook:atom-inject"`，ts `2026-05-28T00:58:34+00:00`（UTC，台灣 08:58:34）
- 8 筆 access_increment 操作均符合 source=`hook:*` 契約
- 結論：先前全 `mcp` 的 drift 已消失

---

## 階段 B — 純 grep / wc / ls / stdin smoke

### RT4 Dispatcher + handlers 模式 — ⚠️ PARTIAL（運作 PASS / 文件 drift→修正）

- 證據 1：`hooks/workflow-guardian.py` 20 行（5 行可執行 code：`import sys / Path / sys.path.insert / from dispatcher import main / main()`）
- 證據 2：`hooks/dispatcher.py` 純路由 + main entry，`HANDLERS` dict 註冊 **7 個** event handler
- 證據 3：stdin smoke 模擬 `{"hook_event_name":"SessionStart"}` → dispatcher 成功回 `additionalContext`，exit=0
- 證據 4：`hooks/handlers/` 7 檔（session_start / user_prompt_submit / pre_tool_use / post_tool_use / pre_compact / stop / session_end）
- 證據 5：`settings.json:32-94` 也只配 7 個 event entry，無 Notification
- DRIFT 1：Architecture.md:26 + DocIndex-System.md:72 寫「1 行 shim」實際 20 行（5 行 code）
- DRIFT 2：SPEC_ATOM_V5.md:170 + v5-overhaul-2026-05/README.md:101 寫「8 個 event handler」實際 7 個，且檔名列表含不存在的 `notification.py`
- 📝 修補：4 處全部當場修為「20 行薄 shim」+「7 個 event handler」+ 移除 notification（user 拍板）。Architecture.md:8「8 個 hook 事件（含 async Stop）」分類角度合理（含 PreToolUse 雙 matcher + Stop sync/async），保留不動

### RT2 Codex Companion subprocess — ✅ PASS

- 證據 1：`netstat -an | grep :3850` 無輸出（無 listener）→ 確認砍掉 daemon
- 證據 2：`tools/codex-companion/service.py` 確認已刪
- 證據 3：`codex_companion.py:30` `AUDIT_SCRIPT = COMPANION_DIR / "audit.py"`
- 證據 4：`codex_companion.py:142` `subprocess.Popen([sys.executable, str(AUDIT_SCRIPT)], **kwargs)` fire-and-forget detached
- 結論：V5 P5b subprocess 模型實作完整

### RT5 MCP 3 tool — ✅ PASS

- 證據：`tools/workflow-guardian-mcp/server.js` 3 個 tool name 註冊（L317 atom_write / L391 atom_promote / L414 atom_move），對應 case handler L442/444/447
- 結論：3 tool 砍 4 IPC 落實

### RT8 禁語 JSON single source — ❌ FAIL→已修

- 證據 1：`wg_evasion.py:39` `_PHRASES_JSON = ... / "forbidden-phrases.json"` ✓
- 證據 2：`wg_evasion.py:76` `_load_phrases()` 從 JSON 讀取 ✓
- DRIFT 1：IDENTITY.md:40-46 **硬編碼禁語清單**（4 條 phrase 字面列出）
- DRIFT 2：IDENTITY.md:55-60 **硬編碼舊 2 項收尾格式** (a)(b)，與 IDENTITY.template.md:25-37 已升的 4 項格式 (a)(b)(c)(d) 不一致
- DRIFT 3：系統 prompt 注入內容（41 行 template）vs 磁碟 IDENTITY.md（68 行舊版）不一致
- 結論：user 上 session 自評「✅ IDENTITY.md 升級 4 項收尾」**只升了 template，IDENTITY.md 從未實際升級**
- 📝 修補：user 拍板用 template 覆蓋 IDENTITY.md（68→41 行）。註：IDENTITY.md gitignored 為 personal instance，本機修補不入 commit。後續觀察：磁碟可能再被某機制污染回舊版，需獨立 session 追溯污染源

### RT10 Log rotation — ⚠️ PARTIAL→修正

- 證據 1：`wg_core.py:113` `rotate_log_if_oversized(log_path, max_mb=10, keep=3)` 實作完整
- 證據 2：caller `session_start.py:204-207` 3 個 log 都用 `max_mb=10`
- DRIFT 1：文件聲稱常數名 `LOG_ROTATE_THRESHOLD_BYTES` **不存在** — 實際是 function param `max_mb`
- DRIFT 2：文件聲稱「100 MB 自動輪轉」— 實際 caller 全部 `max_mb=10`（10 MB）
- 📝 修補：v5-overhaul-2026-05/README.md:91 改為「`rotate_log_if_oversized(log_path, max_mb=10, keep=3)`」+ 加入 codex-companion.log

### RT1 BM25 全域層 — ✅ PASS

- 證據：`wg_atoms.py:227-306` BM25 區塊完整
  - L232 `_BM25_K1 = 1.2` ✓
  - L233 `_BM25_B = 0.75` ✓
  - L236 `_bm25_tokenize` / L251 `_bm25_score` / L299 `bm25_match` (top-k) ✓
- 結論：BM25 全域層落地

---

## 階段 C — 動態 smoke

### RT6 Stop async quick-extract — ✅ PASS

- 證據：`settings.json:85-89` `"Stop"` hook 設 `async: true`，跑 `quick-extract.py` timeout=30
- `quick-extract.py:32` `from wg_extraction import write_hot_cache`；`quick-extract.py:139` 實際呼叫
- 結論：Stop async → quick-extract → write_hot_cache → hot_cache.json 寫入路徑完整

### RT3 JSON SoT — ✅ PASS

- 證據 1：`memory/_atom_index.json` mtime `2026-05-27 19:35:01`（源，6197 bytes）
- 證據 2：`memory/_ATOM_INDEX.md` mtime `2026-05-28 09:14:43`（本 session 自動 regenerate，比 JSON 新）→ mirror 機制運作
- 證據 3：`user_prompt_submit.py:286` `atom_index.get("project_root", "")` 直接從 JSON object 讀取（非 MD parse）
- 結論：JSON 為機器源、MD 為 deprecated mirror auto-regenerate，符合 V5 P3b 設計

### RT7 PreToolUse atom funnel guard — ✅ PASS

- 證據：故意 Edit `memory/decisions.md` 改第 1 行標題，hook 即時擋下
- Deny 訊息：`[Guardian:AtomFunnelBlock] 直接 Write/Edit atom .md 不走 funnel 被禁止` + 提示正確做法（MCP atom_write / lib.atom_io / WG_DISABLE_ATOM_GUARD bypass）
- 結論：PreToolUse funnel guard 即時生效，未被任何路徑繞過

### RT9 Vector Service 全域層退役 — ✅ PASS

- 證據 1：vector port 3849 LISTENING + ollama processes 存活（service 仍跑，預期，**專案層仍需**）
- 證據 2：`user_prompt_submit.py:351-372` BM25 邏輯 `vs_cfg.get("global_layer", "bm25") == "bm25"` 預設走 BM25
- 證據 3：L355 `global_atoms = [e for e in all_atoms if e[1] == MEMORY_DIR.parent]` 精準篩 global layer
- 證據 4：L380-385 Vector fallback：`only when BM25/trigger gave 0 hits, OR for project layer enrichment`
- 證據 5：L352 註解明寫「Project layer still uses vector below」
- 結論：全域層 BM25 取代 vector，vector 只在 (a) BM25/trigger 0 hits fallback (b) 專案層 enrichment 時用，符合 V5 P5a 設計

---

## 中優先 B/D/E/C/F 執行結果（里程碑 3 commit `a1e0781`）

### B `scripts/inbox-*.js` 三檔 — ✅ 砍

- 證據：settings.json + hooks/ + 全域 grep 皆 0 引用
- 動作：`git rm scripts/inbox-check.js scripts/inbox-watcher.js scripts/inbox-write.js`

### E `wg_atom_observation.py` REG-005 shim — ✅ 砍

- 證據 1：`grep "from wg_atom_observation"` 全域 — 唯一 import 在 `_AIDocs/DevHistory/v4-archive/workflow-guardian.py`（archive 不執行）
- 證據 2：實作（log_injection）已搬至 `wg_extraction.py:556`
- 動作：`git rm hooks/wg_atom_observation.py`

### D `memory/failures/` 目錄 — ✅ 建

- 證據：原目錄不存在，7 個 _AIDocs 文件引用
- 動作：`mkdir memory/failures/ + touch .gitkeep`（藍圖儲位，未來 failures atom 子族落地）

### C `_AIDocs/Architecture.md` 版號註清 + 配套同步 — ✅

連同 B+E 動作影響的「6 主模組 + 2 shim」描述同步調整：

- Architecture.md:8/26/36/44：6+2 → 6+1，「1 行 shim」→「20 行薄 shim」，移除 wg_atom_observation row，去純註記日期 `(2026-04-27)` x1 + `(2026-04-28)` x2
- SPEC_ATOM_V5.md:152-157：Shim（2）→（1）+ 移除 row + 加註
- SPEC_ATOM_V5.md:170-171：「8 個 event handler」→「7 個」+ 移除 notification.py + 「1 行 shim」→「20 行薄 shim」
- DocIndex-System.md:68/72/90：「8 wg_*」→「7 wg_*」+「1 行 shim」→「薄 shim」+ 移除 wg_atom_observation row
- _AIDocs/_INDEX.md:30：「6+2 shim + 8 handler」→「6+1 shim + 7 handler」
- v5-overhaul-2026-05/README.md:91/101：LOG_ROTATE 描述對齊實作 + 7 event handler + 20 行薄 shim

### F codex_companion hook 配置 — ✅ 已最簡（不動）

- settings.json 5 處 entry：SessionStart (timeout 5) / UPS (3) / PostToolUse (3) / Stop (10) / SessionEnd (5)
- 每個 hook event 1 個 entry，5 個 event 各自做不同階段任務
- 結論：1:1 對應已是最簡，無冗餘

---

## 留下 session

- G `next-phase-hardcoded-paths.md` 執行（V5 寫死路徑全面盤點，獨立 staging 已存）
- H `next-phase-tests-prune.md` 執行（tests/ 進一步精簡決議，本 session 新建 staging）

兩條互不依賴，可並行 / 順序皆可。
