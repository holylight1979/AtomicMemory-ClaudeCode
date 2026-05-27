# v5-overhaul-audit-2026-05

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: V5, 升級, overhaul, 原子記憶升版, audit 2026-05, 全面檢修, commands skill 遷移, workflow 114GB, guardian-crash.log, skill plugin 結構, 重構計畫
- Created-at: 2026-05-26
- Related: decisions-architecture, workflow-rules, workflow-icld, feedback-pointer-atom, feedback-handoff-self-sufficient, feedback-clean-before-build, feedback-no-plan-bound-hook, 記憶機制靜默失效confirmations-零增-episodic-停擺

## 知識

- [臨] 2026-05-26 完成原子記憶 V4.1 全面審計，對照 CC 最新 skill/hook/plugin/MCP/deferred-tool 設計，9 大問題清單見本 atom 知識區。設計目標：V5 = 對齊 Anthropic 原生機制（skills 取代 commands、deferred MCP 降本、plugin packaging），不重複造輪子。
- [臨] 災難級：workflow/guardian-crash.log = 114 GB（無 rotation），佔 100% 磁碟膨脹；停止後磁碟立刻釋放。緊急優先 P0：先 truncate + 加 rotation。
- [臨] 重大歸類錯誤：CC 官方明言『Custom commands have been merged into skills』（code.claude.com/docs/en/skills）— 使用者 commands/ 26 個 .md 是 legacy 格式；skill 模式 .claude/skills/{name}/SKILL.md 才能享有『Claude 自動觸發 + body 按需載入 + subagent 執行 + dynamic context injection』。遷移路徑：每個 .md → 同名資料夾 + SKILL.md。
- [臨] 5 個 memory-* commands（health/peek/undo/review/session-score）應合併為 /memory <subcmd> 單一 skill，少 4 個檔；3 個自訂與內建衝突（/resume 內建已有 --resume；/changelog-roll 已有 hook 自動觸發；/init 內建已存在但被自訂 /init-project 蓋過）— 應刪自訂版或更名為 /<feature>-debug。
- [臨] MCP 歸類錯誤：workflow-guardian MCP 7 tool 中 workflow_signal/workflow_status/memory_queue_add/memory_queue_flush 4 個是內部 IPC 不該暴露給 AI；atom_write/atom_move/atom_promote 3 個保留為 MCP 合理（多步驗證 + 去重 + 索引）。Deferred tool 機制（issue 31002）讓 MCP context 開銷 ≈0，主因不是 token 而是『AI 認知負荷與內部實作洩漏』。
- [臨] Hook 模組過度切割：16 個 wg_*.py + dispatcher 1640 行；wg_evasion / wg_session_evaluator / wg_iteration / codex_companion soft_gate 四套自我評估邏輯重疊。建議：保留 dispatcher + 5 個核心模組（atoms / extraction / episodic / docdrift / evasion），其他併入或刪除；codex_companion 子系統（daemon @ 3850 + 30 audits/session）改 in-process RateLimiter。
- [臨] 24 個 feedback-* atom 違反『指標型 atom』原則（feedback-pointer-atom.md 自己定的規則）— 平均 1.2 KB，含失效項（decision-no-tech-menu、precedent-drift-excuse）。應合併為 3-5 個主題 atom（feedback-workflow / feedback-code-quality / feedback-tooling / feedback-memory-system）。
- [臨] _ATOM_INDEX.md trigger 列平均 46-58 字 + 重疊（codex 出現在 4 個 atom）導致 trigger 注入浮濫；同檔 2026-05-04 才修空行污染（commit e11b800）— parser 對格式脆性高，應改 JSON/YAML 結構化儲存而非 Markdown 表格。
- [臨] Session start context 注入 ≈1100 token（IDENTITY 反退避契約 + 行為準則 + USER.md 縮寫 + MEMORY.md 索引重複），其中反退避契約 250 token 與 wg_evasion.py 程式碼重複防呆。可壓縮到 ≈500 token（省 ≈55%）。
- [臨] 子系統殺雞用牛刀：Vector Service @ 3849（LanceDB + Ollama）對全域 30 個 atom 規模過剩；建議改 BM25 in-memory 或直接靠 MEMORY.md trigger 表，保留 vector 給專案層大規模 atom。
- [臨] V5 升級分 Phase 推進（精確不失憶用本 atom + 各 phase 的 handoff atom 串接）：P0 緊急救火（truncate crash.log + 加 rotation）、P1 commands→skills 遷移 + 內建衝突消除、P2 hook/MCP 重整（4 tool 內化 + wg_* 合併）、P3 atom 整併（feedback 合 + _ATOM_INDEX JSON 化）、P4 context budget 瘦身、P5 子系統評估退役（vector / codex companion）。
- [臨] Handoff 用法：每 Phase 結束寫 `_staging/next-phase.md` + 落本 atom append 新進度（mode=append），下個 session 跑 /continue 自動拉這兩份 → 不失憶。執P 對應 USER.md 縮寫，意指『執行+驗證+上 GIT/SVN』，每 phase 完工後必跑。
- [臨] 2026-05-26 V5 計畫定版 + 使用者批准：plans/wondrous-humming-spark.md。4-Wave 設計取代原 6-phase 線性，預估 4-6 session 完成（原 6-9 省 30-40%）。Plan agent 驗證出 wg_atoms.py / workflow-guardian.py 為三方爭用熱點，故 P2 必須在 P3b/P5a/P5b 之前独立打基線。
- [臨] Wave 1 handoff 寫入 _staging/next-phase.md：下 session 第一句貼本檔頂部 prompt，Claude 自動拉取計畫 + audit atom + Wave 1 參數。Cache 策略：開頭一個 message 並行讀 stable context + 本 phase 改動檔案一次填滿。
- [臨] Wave 1 錃圍鎖定：P0 log rotation、P3a feedback 24→5 整併、P4a 文件層瘦身（不動 wg_evasion、不動 commands）。任何超出錃圍的 drift 記載不當場修，避免 Wave 2 重寫時衰變。
- [臨] 2026-05-26 Wave 1 完成 (commit 09ec026)：P0 rotation 函式上架（hooks/wg_core.py + workflow-guardian.py SessionStart 呼叫）、P3a 24→5 feedback atom 整併 + 舊 24 個歸檔到 memory/_distant/2026_05_consolidation/、P4a IDENTITY.template/USER/CLAUDE/MEMORY 瘦身。遺留：114GB guardian-crash.log 因 NTFS 損毀無法程式刪除，需 user 跑 `chkdsk C: /f` 後才能物理刪除（rotation 機制已防未來再爆）。
- [臨] Wave 2 起手入口 prompt 寫入 _staging/next-phase.md。Wave 2 范圍：P2 hook/MCP 重整（wg_*.py 16→5 + dispatcher 拆 dispatcher/handlers + MCP 砍 4 內部 tool + 4 套自評整合）+ P4b wg_evasion 禁語抽出為 memory/_meta/forbidden-phrases.json（兩處硬編碼收到唯一來源）。預估 1-2 session，是 V5 最重的 phase。
- [臨] disable 清單追列：.git/hooks/pre-commit 在 Wave 1 期間仍保持 disabled（重命名為 pre-commit.disabled-during-v5）。由於 Wave 3 P3b 才重寫 _ATOM_INDEX 為 JSON 來解決 parser 脆性，中間期間1 都走 --no-verify-free 的 commit 路徑（使用者職權來到才重啟）。
- [臨] 2026-05-26 Wave 2 完成（commit 待補）：P2 hook/MCP 重整 + P4b 禁語抽 JSON。改動：hooks/wg_*.py 16→6 主模組 + 2 shim（wg_roles/wg_atom_observation）；workflow-guardian.py 2651 行 → 1 行 shim 轉發 dispatcher.py；dispatcher.py（75 行純路由）+ handlers/ 目錄（_shared.py + 7 個 event handler 各一檔）；MCP server.js 砍 4 內部 tool（workflow_signal/status/memory_queue_add/flush），替代為 Stop gate 自動偵測；memory/_meta/forbidden-phrases.json 為禁語 single source，IDENTITY.template 與 wg_evasion 都讀此檔。tools/ + tests/ 全部 import 一次性修正。
- [臨] Wave 2 順手修補清單：`既有 drift` regex pattern 因 `\s` 排除空白無法匹配「既有 drift」（中間空格）— 原設計避免跨子句誤殺，by-design，P5+ 想擴大可改 `[^，。\n]{0,6}`。
- [臨] Wave 3 入口 prompt 已寫入 _staging/next-phase.md。Wave 3 範圍：P3b _ATOM_INDEX → JSON + P1 commands → skills + P5a Vector 全域 BM25。基於 Wave 2 新 hook 基線並行。
- [臨] 2026-05-27 Wave 3 完成（commit 待補）：P3b _ATOM_INDEX → JSON + P1 commands → skills + P5a Vector 全域層 BM25。改動：(1) lib/atom_index_json.py 新模組（schema v1.0），memory/_atom_index.json 為唯一機器源，17 atoms 一次性遷移 + 5 個跨 atom 重複 trigger 去重；_ATOM_INDEX.md 退化為自動生成 mirror。(2) hooks/wg_atoms.py:parse_memory_index 優先讀 JSON；wg_episodic._update_memory_index + lib/atom_io.write_index + MCP server.js:appendToIndex 全部走 upsert_atom funnel。(3) .git/hooks/pre-commit 重啟為 JSON schema check + MD mirror drift（取代脆性的 _ATOM_INDEX.md table parser）。(4) skills/ 目錄建立 19 個 SKILL.md（13 直遷 + 4 全域保留 + 1 合併 /memory + 1 改名 changelog-debug）；刪 5 個 legacy（resume/init-project/svn-update/unity-yaml/changelog-roll）；22 個剩餘 commands 保留 1 週緩衝。(5) hooks/wg_atoms.py 加 bm25_match（手刻 ~80 行，BM25 over trigger+name，中文 char-bigram tokenize），user_prompt_submit 注入流程改 trigger→BM25→Vector fallback；tools/memory-vector-service/indexer.py 加 cleanup_stale_chunks + CLI flag。
- [臨] Wave 3 順手修補清單：無（本次無發現 drift）。
- [臨] Wave 4 入口 prompt 已寫入 _staging/next-phase.md。Wave 4 範圍：P5b Codex Companion daemon → subprocess + P6 dead code 清理 (wg_atoms._ensure_vector_service / _v4_archive / legacy commands 過期者) + 文件最終化（SPEC_ATOM_V5.md / Architecture.md / DocIndex-System.md 更新）。預估 1 session 收尾。
- [臨] V5 disable 清單最新狀態：.git/hooks/pre-commit ✓ Wave 3 重啟；Codex Companion daemon 仍跑（Wave 4 P5b 改 subprocess）；legacy commands/22 檔保留至 2026-06-03 緩衝期滿。
- [臨] 2026-05-27 MCP server.js reload smoke：使用者重啟 VS Code + Claude Code 後，驗證 funnelWriteIndex 路徑有動。預期本寫入後 _atom_index.json 的 v5-overhaul 條目 triggers 變 15 個（原 14 + 新增 MCP reload smoke）、MD mirror 同步、pre-commit 仍 PASS。

## 行動

- P0 立即：truncate guardian-crash.log 並加 size-based rotation（hooks 啟動時檢查 > 10MB 就轉）
- P1：把 commands/*.md 遷到 .claude/skills/{name}/SKILL.md 結構；5 個 memory-* 合成 /memory；刪自訂 /resume、/init-project（改用內建）；/changelog-roll 改為 hook debug 工具
- P2：MCP server.js 砍 workflow_signal/workflow_status/memory_queue_add/memory_queue_flush；hook 內化；wg_* 合併為 5 模組；codex_companion daemon → in-process
- P3：合併 24 feedback-* → 3-5 主題 atom；_ATOM_INDEX.md 改 JSON 結構
- P4：壓縮 IDENTITY.md 反退避契約段、USER.md 縮寫、MEMORY.md 重複；目標 session start < 500 token
- P5：評估退役 Vector Service（全域層）+ Codex Companion；用 deferred MCP 取代內部 IPC 思維
- 每 Phase 收尾呼叫 atom_write mode=append 本 atom，記錄完成項 + 下一 phase 入口
- 下個 session 開頭：讀本 atom + /continue 抓 _staging/next-phase.md
