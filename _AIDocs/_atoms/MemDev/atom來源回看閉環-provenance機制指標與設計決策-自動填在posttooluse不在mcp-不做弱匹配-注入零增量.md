# atom來源回看閉環-provenance機制指標與設計決策-自動填在PostToolUse不在MCP-不做弱匹配-注入零增量

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: provenance, Quote 欄, Source 欄, atom_source, atom-source, 來源回看, 這張卡片哪來的, provenance-backfill, wg_provenance, 回填原句, A 級 B 級, 原對話已逾保留期
- Created-at: 2026-10-06
- Source: session:f1e8b9d8#501adf46 2026-10-06
- Quote: 「而且，肯定會動到code， 全面完工也全面驗證完成無誤後，我在此先直接授權你 ** 上GIT **。」

## 知識

- [臨] **SoT 指標**：寫入端 `hooks/wg_provenance.py autofill_from_receipt`（PostToolUse 在 atom_write receipt 入帳後呼叫）；共用 `lib/provenance.py`（sanitize_quote／format_source_session／parse_source／find_transcript／last_human_record／resolve_context／atom_source）；讀取端 `tools/atom-source.py`、`atom_io_cli` action `source`、MCP `atom_source`、skill `skills/atom-source/`；回填 `tools/atom-provenance-backfill.py`（SessionStart `_maybe_spawn_provenance_backfill` 觸發；鎖／log／marker 在 Logs／workflow）；防腐 `tools/health-weekly.py _provenance_anti_rot`；config `provenance`。文件 TECH §4.1／§5.8／§8、SPEC §13.3。
- [臨] **為什麼自動填在 PostToolUse 不在 MCP js**：MCP server 進程只有 process.cwd()，不知道 session id；state.turn_prompts 是純字串無 uuid；只有 PostToolUse hook input 同時有 session_id、transcript_path 與 receipt 路徑。
- [臨] **回填不做弱匹配**（同日最近訊息配 atom）：配錯原句會以 session: 格式永久固化、日後無法與真配區分；寧可 B 級「原對話已逾保留期」。同檔名多層且無精確路徑命中 → ambiguous 不寫。本機實跑 920 顆：A 136、B 746。
- [臨] **每回合 token 增量 0**：注入端 `_FRONTMATTER_KEEP_RE` 只留 Confidence／Trigger／Last-used／Status，Source／Quote 不進注入；知識段 HTML 註解（`<!-- src -->`）也剔掉。固定前綴只多一個 MCP tool schema 與一個 skill 描述。
- [臨] 已知限制：自動填的 Quote 是「atom_write 發生那一回合的最後一則使用者訊息」。收割時才寫的 feedback 卡片，Quote 會是收尾問句（例：「可以關 session 了？」）而不是當初的指正原話。要留正確原話：寫 feedback 卡片時自己把指正句放進 quote 參數（呼叫者給了就不自動覆蓋），或在指正發生的那一回合就寫。

## 行動

- 改 provenance 任一端前先讀 lib/provenance.py 檔頭與 TECH §5.8；py/js 渲染改動必跑 verify_atom_io_equivalence
- 使用者問「這張卡片哪來的」→ 走 skill atom-source，不自己翻 transcript
