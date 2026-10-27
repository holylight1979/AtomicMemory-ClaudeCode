# atom來源回看閉環-provenance機制指標與設計決策-自動填在PostToolUse不在MCP-不做弱匹配-注入零增量

- Scope: global
- Author: holylight
- Source: session:f1e8b9d8#501adf46 2026-10-06
- Quote: 「而且，肯定會動到code， 全面完工也全面驗證完成無誤後，我在此先直接授權你 ** 上GIT **。」
- Confidence: [臨]
- Trigger: provenance, Quote 欄, Source 欄, atom_source, atom-source, 來源回看, 這張卡片哪來的, provenance-backfill, wg_provenance, 回填原句, A 級 B 級, 原對話已逾保留期, QUOTE_FROM_USER_OPENED_TURN
- Created-at: 2026-10-06

## 知識

- [臨] **SoT 指標**：寫入端 `hooks/wg_provenance.py autofill_from_receipt`（PostToolUse 在 atom_write receipt 入帳後呼叫）；共用 `lib/provenance.py`（sanitize_quote／is_human_record／is_kickoff_text／resolve_context／atom_source）；讀取端 `tools/atom-source.py`、MCP `atom_source`、skill `skills/atom-source/`；回填 `tools/atom-provenance-backfill.py`（SessionStart `_maybe_spawn_provenance_backfill` 觸發）；防腐 `tools/health-weekly.py _provenance_anti_rot`；config `provenance`。文件 TECH §4.1／§5.8／§8、SPEC §13.3。
- [臨] **自動填放 PostToolUse 不放 MCP js**：MCP 進程只有 process.cwd()、不知道 session id；只有 PostToolUse hook input 同時有 session_id、transcript_path 與 receipt 路徑。
- [臨] **回填不做弱匹配**（同日最近訊息配 atom）：配錯會以 session: 格式永久固化、日後無法與真配區分；寧可 B 級「原對話已逾保留期」。同檔名多層且無精確路徑命中 → ambiguous 不寫。
- [臨] **每回合 token 增量 0**：注入端 `_FRONTMATTER_KEEP_RE` 只留 Confidence／Trigger／Last-used／Status，Source／Quote 與知識段 HTML 註解都不進注入。
- [臨] 已知限制：自動填 Quote 只取寫卡那一回合是使用者本人打字開的原話（規則 QUOTE_FROM_USER_OPENED_TURN，回填同一條 not_user_turn）：同伴訊息、背景通知開的續跑回合不填；子代理寫卡用子代理檔第一筆 promptId 對回派它的那一回合，是真人訊息才填；原話先剔掉貼上區塊（lib/harness_text.strip_pasted）。
- [臨] 已知限制：收割時才寫的 feedback 卡，自動填的 Quote 會是收尾問句而不是當初的指正原話 → 寫 feedback 卡時自己把指正句放進 quote 參數（呼叫者給了就不覆蓋），或在指正那一回合就寫。
- [臨] 寫 Quote 的入口（wg_provenance、回填 `_resolve_quote`、萃取器）都過同一支開工句判定 `lib/provenance.is_kickoff_text`（與 user_typed_text 同源）：只修一個，清掉的 Quote 下次開 session 會被回填補回（實踩 29 張 Quote 是開工句）。修法順序：入口全接同一判定 → 一次性清卡 → 驗再跑回填 diff 為空；新增入口先 grep 既有入口有沒有漏接。

## 行動

- 改 provenance 任一端前先讀 lib/provenance.py 檔頭與 TECH §5.8；py/js 渲染改動必跑 verify_atom_io_equivalence
- 使用者問「這張卡片哪來的」→ 走 skill atom-source，不自己翻 transcript
