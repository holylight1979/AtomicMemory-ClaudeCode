# Claude Code 全域設定 — 核心架構（Index）

> 本檔為**索引型**。穩定子系統細節放 `DevHistory/` 子檔；本檔只留現役、演化中 feature + 關鍵索引。
> 詳盡規範：[`SPEC_ATOM_V5.md`](SPEC_ATOM_V5.md)（V5 原子記憶 — 取代 V4）、`rules/core.md`（行為規則）、`Project_File_Tree.md`（頂層目錄角色說明，30 行；完整檔樹用 `tree -L 3`）。

## Hooks 系統（V5 架構，2026-05-27）

**9 個 hook 事件**（settings.json 註冊：SessionStart / UserPromptSubmit / Pre·PostToolUse / Pre·PostCompact / PostToolBatch / Stop / SessionEnd；Stop 兼同步閘門與 async 萃取，且 2026-07-01 起同時掛 3 支 standalone Stop hook — guardian / codex_companion / lang_guard；2026-06-01 選配 #4 加 `PostCompact`+`PostToolBatch`；handlers/ 另含未註冊事件的 `notification.py`，共 10 handler 模組）。**V5 Wave 2** 把 V4.1 的 2651 行 `workflow-guardian.py` 拆成 `dispatcher.py`（純路由）+ `handlers/{event}.py` 模組；16 個 `wg_*.py` 整併為 6 主模組 + 1 shim（Wave 5 Session 6 砍 `wg_atom_observation.py`）。V4 終態的 19 個檔案歸檔在 [`DevHistory/v4-archive/`](DevHistory/v4-archive/)。

| Hook | 觸發時機 | 用途 |
|------|---------|------|
| `UserPromptSubmit` | 使用者送出訊息 | RECALL 記憶檢索 + intent 分類（含 handoff）+ Context Budget 監控 + Wisdom 情境分類 + Failures 偵測 + Evasion 注入 |
| `PreToolUse` (Write/Edit) | Write/Edit 工具呼叫前 | (1) Atom Format Gate：阻擋 `/.claude/memory/*.md` 不符原子格式的寫入；(2) Atom Confidence Gate：新建 atom 的 frontmatter `Confidence:` 與內文 `- [固]/- [觀]` 標籤必須全為 `[臨]`，鏡射 MCP `atom_write` mode=create 規則（[server.js:1109-1117](../tools/workflow-guardian-mcp/server.js)）封堵 Write tool 繞過路徑；(3) **Memory Path Block**：阻擋寫入 `~/.claude/projects/{slug}/memory/`（原子記憶專案自治層覆寫此路徑），對應 atom `feedback-memory-path`；(4) **Cross-Realm Write Block**（方案甲 2026-06-12，v1.1 同日擴充）：外部專案 session（cwd∉~/.claude）寫入核心層 `~/.claude/{skills,tools,hooks,lib,rules}/` **或根層敏感檔（settings.json/CLAUDE.md/IDENTITY*.md/USER*.md）** → deny 並指路專案層 `.claude/skills|tools/`（SGI 跨層污染教訓；config `guard.cross_realm_write` 可關/設 allowlist；核心開發 session 不受影響）；(5) **跨 session 衝突預警**（`wg_coordination.py`）：Write/Edit/NotebookEdit 目標檔在其他活 session state 的 `modified_files`（entry 級 session_id 歸屬、mtime 窗過濾、10min 同檔抑制）→ warn-only（additionalContext 隨工具結果下一輪可見 + systemMessage；deny 觸發時警告只留 stderr）；Bash `git add -A`/`reset --hard` 等收尾指令且同 cwd 有他人未收改動 → 同型警告（選擇性 staging 規範）。全程 fail-open，log 落 `Logs/session-coordination/<sid>.jsonl`（per-session 分檔）；config `coordination.*` 一鍵關；(6) **實作前預告閘門 PAN**（Hermes 技轉 2026-08-05）：每使用者回合首次「會動手」工具（Write/Edit/NotebookEdit/非唯讀 Bash/非唯讀 PowerShell）呼叫前，檢查本 turn transcript 可見文字是否含「執行目標」+「預估/概估」+ 實質內容（`pan_validate_notice` 純驗證器：剝標點/佔位符 `<…>` span/code fence、時間冒充目標防禦）；mode 三態 `observe`（只落 `Logs/guard-pre-action-notice.jsonl`）/`warn`（systemMessage，現行值——實測 VSCode 環境「文字+工具」訊息 text block 常不落 transcript、同回合偵測不可靠，故不直上 deny）/`deny`（攔 + 補救模板，每回合上限 `max_denies_per_turn` 次、超過強制放行；`lenient_first_miss=true` 時首 miss 降 warn、第 2 次起才 deny）；通過寫 `workflow/pan-pass/{sid}-t{turn}.flag`（armed 快路徑，回合內全放、marker 抗併發）；sidechain/resume 保底 state 無 turn_seq 即 fail-open、fail-open log 同 (sid,turn) 節流 3 筆；compaction continuation 回合（turn 首 user 訊息命中 harness 續接敘述特徵）整回合豁免；豁免 `exempt_path_substrings`（plans/_staging/scratchpad/workflow）；MCP 工具不在 matcher 天然不管；config `guard.pre_action_notice` 一鍵關 + 4 週日落條款 |
| `PreToolUse` (Bash) | Bash 工具呼叫前 | (1) **SVN Test Block**：阻擋 `svn commit/ci` 含 `tests?/` `__tests__/` 路徑或 `*Test.<ext>` 檔案（r10854 教訓），對應 atom `feedback-no-test-to-svn`；(2) **Cross-Realm MCP Block**（guard v1.1 2026-06-12）：外部專案 session 的 `claude mcp add -s user` / `claude mcp remove` 未限定 project\|local scope → deny（防全域 ~/.claude.json 被專案 session 污染），指路 `-s project`；(3) **PAN 預告閘門**（同上列 (6)）：非唯讀 Bash 與非唯讀 PowerShell（共用白名單前綴分類器 `pan_is_readonly_bash`：git 唯讀子命令/ls/cat/rg/pytest/get-* 等唯讀 cmdlet，heredoc/redirect 非 null device/複合段未命中/`find -delete\|-exec`/變數賦值段一律視為動手）納入 gated 名單（settings.json PreToolUse matcher 含 PowerShell） |
| `PostToolUse` (Edit/Write/Bash) | 工具呼叫後 | 追蹤修改檔案 + 增量索引 + Test-Fail 偵測（Bash）+ _CHANGELOG auto-roll + **late-collision 補償**（write_state 落盤後查 60s 內 peer 同檔寫入——雙方同時首寫時寫前互看不見，寫後告警；log 恆記、advisory 受同檔抑制窗防洗版）（Read 不在 matcher——accessed_files 由 Stop 從 transcript 尾段一次回收，省 per-Read hook 行程）。另掛 2 支 standalone PostToolUse hook：**version_guard**（Write/Edit 後掃版本操作脈絡殘留 → warn-only；config `version_guard`）、**acceptance_spec**（驗收規格工件分級啟動：ExitPlanMode 獲同意 → 注入指示從 plan 落 `<專案根>/.claude/verify/acceptance-<slug>.md`（frontmatter 綁定 + 必須發生/禁止發生/驗證指令三段）；無 plan 但同 session 修改 ≥3 檔 → 一次性建議；規格檔落盤 → sidecar `workflow/acceptance-spec/<sid>.json` 抑制重複提醒；advisory-only、小任務零打擾；config `acceptance_spec`） |
| `PreCompact` | Context 壓縮前 | 快照 state + 快照 `injected_atoms`（`pre_compact_injected_atoms`，供壓縮後內文復原，不受 SessionStart(compact) 清空順序影響）+ **Auto-Handoff Layer 2**：壓縮前自動寫六區塊 stub 到 `_staging`（核心保底，不依賴 token 量測） |
| `PostCompact` | Context 壓縮後 | 依 PreCompact 快照 stash 已注入 atom 的緊湊內文 + 設 `pending_reinjection` flag（**本身不注入**，PostCompact 不支援 additionalContext） |
| `PostToolBatch` | 一批（含並行）工具全解析後，每批一次 | idle 時極輕 early-exit；見 flag 時一次性 `additionalContext` 重注入壓縮前 atom 內文 + 清 flag + 名單 merge 回 `injected_atoms`（閉 mid-turn auto-compact 失憶缺口，選配 #4）；**Auto-Handoff Layer 3**：與 `pending_reinjection` blob 合流注入 stub 補全提示 |
| `Stop` | 對話結束前 | （3 支 standalone Stop hook）**guardian**：Sync 閘門 + Fix Escalation + TestFailGate（阻擋完成宣告）+ Evasion Detection + **AtomAudit Gate**（取用端閉環：trigger 命中但僅一行路標注入且整場未 Read → 三選一表態）+ **Deep Post-Mortem Gate**（高 effort 失敗訊號 → 注入指令要 Claude 用 atom_write 補完整 post-mortem，獨立預算一次性）+ **Auto-Handoff Layer 1**（token 預警 piggyback）；**codex_companion**：完成證據/handoff 第二意見複審；**lang_guard**（P8b）：終版訊息英文佔比 >0.5 → 注入繁中提醒 |
| `Stop (async)` | 對話結束後 | ~~V3 quick-extract~~（**孤兒·已撤，無 caller**）；hot_cache 現僅由 deep_extract 覆寫路徑餵 |
| `SessionStart` | Session 開始 | 初始化 state + 去重 + Wisdom 盲點 + 定期檢閱 + 專案自治層 delegate |
| `SessionEnd` | Session 結束 | Episodic 生成 + 回應萃取 + 鞏固 + 衝突偵測 + Wisdom 反思 + **Auto-Handoff Layer 4**：session 直接結束（非壓縮）兜底寫客觀 stub（補 PreCompact 未觸發缺口） |

### Hook 模組拆分（V5 6+2 主模組）

| 模組 | 職責 |
|------|------|
| `workflow-guardian.py` | 20 行薄 shim 轉發 `dispatcher.main()`（保留 V4.1 entry path 相容） |
| `dispatcher.py` | ~75 行純路由：讀 stdin event → 找 handler → 呼叫 |
| `handlers/_shared.py` | 跨 handler 共用常數/helper（MEMORY_MD 標頭、project hook caller、cleanup_old_states 等） |
| `handlers/session_start.py` | SessionStart：init state + 去重 + V4 role bootstrap + AIDocs bridge + Wisdom + MCP health + log rotation + Vector service bg subprocess + **週健檢死人開關**（`_health_advisory` 讀 `workflow/health-last-run.json`：缺檔/逾 10 天/red>0 → advisory 浮出，健康時零 context）+ **未推送提醒**（`_unpushed_advisory`：`git rev-list --count @{u}..HEAD` > 0 → 浮一行；補 SessionEnd 晉升自動提交「背景 push 失敗當下無人知」的可見性缺口。唯讀、無 upstream/非 repo 一律靜默、健康時零 context） |
| `handlers/user_prompt_submit.py` | UPS orchestrator（2026-06-12 熱點重構 790→195 行）：串聯 ups_* 四段 + 收尾（blind-spot / fix escalation / evasion 舉證 / handoff / topic / sync context（僅 sync 關鍵字觸發；週期性 `[Guardian] Reminder` 已退役 → statusline 常駐顯示）/ turn_injected / debug 摘要 / budget 截斷輸出）＋ **UPS 被 kill 哨兵**（開頭 arm `workflow/ups-sentinel/<sid>.json`、正常結尾 clear；見殘留＝上輪注入被 harness timeout 砍 → 告警）＋ AEC (d) 刪除決策後驗 |
| `handlers/ups_gates.py` | UPS detect 段：evasion 追蹤 + V4.1 decision gate + confirmed extractions + long_die + Hot Cache + Atom-Write Guard |
| `handlers/ups_context.py` | UPS context build 段：session context（episodic + proactive）+ wisdom 分類 + parallel 建議 + AIDocs keyword + JIT internal-pipeline |
| `handlers/ups_search.py` | UPS search pipeline 段：index 組裝 + 跨專案 alias + trigger → BM25 全域層 → Vector（全空 fallback / 專案層 enrichment：trigger 命中 <3 才打）+ supersedes + **RRF 三路融合 × ACT-R**（個別化 decay；`fusion:"legacy"` 回退純 ACT-R 排序；含**分心懲罰** `compute_injection_rank`，Memory Governance A） |
| `handlers/ups_inject.py` | UPS injection assemble 段：hot/cold + per-turn budget（ok/fallback/skip）+ related spread（含 **relevance gate** `_filter_related_by_relevance` 最小集裁切，Memory Governance C）+ ReadHits++/效用晉升提示 + **injection_log 記錄**（name/path/source/form/turn_seq 落 state，cap 100，供 Stop AtomAudit）+ 一行注入（cold/skip）附帶 atom 選填 `Status:` 現況 |
| `handlers/pre_tool_use.py` | PreToolUse：Write/Edit atom format gate + memory path block + Bash SVN test block + **PAN 實作前預告閘門**（`pan_validate_notice`/`pan_is_gated`/`_check_pre_action_notice`，可見文字源 `wg_evasion.get_current_turn_visible_text`） |
| `handlers/post_tool_use.py` | PostToolUse：file tracking + 增量索引 + test-fail 偵測 + changelog auto-roll（read tracking 移 Stop 端回收） |
| `handlers/stop.py` | Stop：sync 閘門 + Fix Escalation + TestFailGate + Evasion Detection + **AtomAudit Gate**（`_audit_pointer_atom_consumption`：injection_log 中 source=trigger 且 form∈{skip,cold} 且非本 turn 注入、accessed_files 無對應 Read → 三選一表態 (a)他源等價 (b)無關理由 (c)補讀；per-atom 一次 `atom_audit_prompted`、沿用 `stop_gate_max_blocks` 預算、fail-open stderr；config `atom_audit.enabled`）+ **Deep Post-Mortem Gate**（`_should_deep_postmortem`：(effort：retry≥2 ∨ fix_escalation_triggered) **AND** (真失敗：failing_tests ∨ evasion_flag ∨ 未宣告完成) → 指示 Claude 深寫 post-mortem；effort 已由 track_retry 以 failing_tests error-gate（不採同檔 edit 次數＝正常重度迭代不誤觸）；`deep_postmortem_done` 一次性＝**獨立預算 1（P5 起不與 Sync/Scan/TestFail 共用 `stop_gate_max_blocks`，止餓死）**）+ Auto-Handoff Layer 1（token 預警 piggyback 既有 block）+ outcome 三值計數（`outcome_stats`，隨 α/β 歸因 once-per-turn，供 unknown 比率遙測）；**transcript 單次 tail-read**（`read_transcript_tail` 2MB 尾窗，last_text / token 預警 / turn 文字 / accessed_files 回收全共用，取代逐消費者全檔讀；Stop hook timeout 得以 20→10）+ `_detect_uncommitted_files` 按 VCS root 分組 batch status（零 per-file subprocess） |
| `handlers/session_end.py` | SessionEnd：Episodic 生成 + 回應萃取 + 衝突偵測 + Wisdom 反思 + **selective forgetting**（`apply_selective_forget` 隔離 `_distant/`，預設 dry-run，Memory Governance D）+ docdrift advisory + Auto-Handoff Layer 4（SessionEnd 兜底寫客觀 stub）+ **outcome unknown 比率遙測**（`flush_outcome_stats` → `workflow/outcome_stats.jsonl` 滾動 50 筆；連續 `window` session > `threshold` → 寫 marker → 下個 SessionStart 注入 advisory 後清除。防完成語 regex 與模型輸出失配 → α/β 晉升軌靜默停滯；config `usefulness.unknown_watch`）+ **失念偵測**（`wg_recall_miss.detect_recall_misses` → `Logs/recall-miss.jsonl`，config `recall_miss.enabled`）+ **晉升自動提交**（`_auto_commit_promotions`：`[臨]→[觀]` sweep 改到的 atom 當場 `git commit -- <paths>` pathspec 提交——**不下 `git add`**，別的 session 已 stage 的檔原封不動，共用工作樹安全；push 走背景 detached → `Logs/auto-commit.log`；index.lock 競態短重試，任何失敗 fail-open + stderr 出聲、改動留工作樹。config `self_iteration.auto_commit_promotions` / `auto_push_promotions`） |
| `handlers/pre_compact.py` | PreCompact：state snapshot + `injected_atoms` 快照 + Auto-Handoff Layer 2（壓縮前自動寫六區塊 stub） |
| `handlers/post_compact.py` | PostCompact：依快照複用 `wg_atoms.load_atoms_within_budget` stash 壓縮前 atom 緊湊內文 + `pending_reinjection` flag（不注入；選配 #4） |
| `handlers/post_tool_batch.py` | PostToolBatch：idle early-exit；見 flag 一次性 `additionalContext` 重注入 + 清 flag + 名單 merge 回 `injected_atoms`（選配 #4）+ Auto-Handoff Layer 3（合流注入 stub 補全提示） |
| **主模組 6 + shim 1**（V5 §5）| |
| `wg_core.py` | 路徑唯一真相 + config/state IO + **token budget 單一來源**（CONTEXT_BUDGET_DEFAULT / TURN_BUDGET_LIMIT / compute_token_budget，2026-06-12 集中；兩估算器口徑見該檔註解）+ log rotation + PreToolUse guards（合 wg_paths + wg_pretool_guards） |
| `wg_atoms.py` | atom index 解析 + trigger 匹配（any_trigger_hit/count_trigger_hits 共用原語）+ **BM25 全域層** + ACT-R + vector search + atom 晉升（合 wg_intent + wg_iteration atom 晉升部分） |
| `wg_extraction.py` | per-turn 萃取 + worker + failure + hot cache + user-extract + content classify（合 wg_user_extract + wg_hot_cache + wg_content_classify） |
| `wg_episodic.py` | episodic 生成 + 衝突偵測 + 品質回饋（摘要經 `sanitize_harness_noise` 剔 harness 標籤/hook 殘渣；知識段只收 LLM 萃取項 + 覆轍信號，統計歸摘要/閱讀軌跡） |
| `wg_evasion.py` | Evasion Guard + Test-Fail + ScanReport + 4 套自評整合（合 wg_session_evaluator + wg_iteration 自評部分） |
| `wg_docdrift.py` | src → _AIDocs 映射 drift 偵測 |
| `wg_roles.py` | V4 sub-layer 探勘 shim（V4 角色機制） |
| `wg_coordination.py` | **跨 session 衝突預警**：同檔衝突掃描（唯讀他人 `state-*.json`、entry 級歸屬、oversize/mtime 過濾）+ Bash git 收尾指令偵測（剝引號註解、指令段錨定）+ warn-cache 去重 + per-session observation log。純檔案方案（不依賴 3848 daemon）；warn-only、fail-open。多大師計畫定案：Stage 2 收件匣/Phase 3 認領制 defer，重啟條件見 config `coordination._doc` 日落條款反向 |
| `wg_handoff.py` | **Auto-Handoff**（2026-06-09，跨 session 無損交接）：`build_handoff_stub` 六區塊 stub（客觀區塊自動填 git/files/atoms + 主觀區塊 TODO 佔位）+ `should_write_stub`（不覆蓋手寫 handoff）+ `estimate_context_usage`/`token_warn_payload`（Phase 2 Stop Layer 1 token 預警，純函式無副作用）。被 `pre_compact`(L2)/`post_tool_batch`(L3)/`stop`(L1)/`session_end`(L4) 共用（L4 為 Phase 3 SessionEnd 兜底）。設計：`plans/wise-wobbling-gem.md` |
| **獨立保留** | |
| `wisdom_engine.py` | 反思引擎 + Fix Escalation |
| `codex_companion.py` | **V5 P5b 重寫**：HTTP daemon → subprocess（in-process state + spawn `tools/codex-companion/audit.py`）。**2026-06-24**：新增第四類審計 `handoff_review`——偵測 `_staging/next-phase*.md`/handoff 檔寫入 → 把 `skills/handoff` Step 3.5 八問當對抗 checklist 餵 codex 對交接文件做獨立第二意見複審（自評→他評），降注入門檻 medium（`soft_gate.handoff_review`，預設開）。**輸入組成鐵律**：hook 只傳觸發事實（artifact_path/tail/score），artifact 內容實體化與 prompt 材料組裝集中在 `tools/codex-companion/artifact_io.py` + `assessor.build_prompt()`（規則唯一來源）——引用檔案類 artifact 必附實體內容（超長頭尾採樣 + in-band 標記），動作紀錄不得替代內容本體，集合截斷附計數標頭；plan_review 由 trace 反掃 `plans/*.md` 讀實體（解析不到 → skip + metric，不空審），僅 ExitPlanMode 觸發。**2026-08-06：第五類審計 `acceptance_review`（影子驗收裁判）**——Stop 完成宣稱或規格檔 status→done 時，`tools/codex-companion/acceptance.py` 解析任務↔規格檔綁定（四分流：本 session 唯一 open 規格＝bound 才發審計；ambiguous/other_session/none 記 uncertain 不發、不猜最新一份）→ 組案卷（需求原話 + 驗收清單 + diff 頭尾採樣附標記 + 測試輸出）發 codex 回 verdict（pass/fail/uncertain）；`assessor.map_acceptance_verdict` 程式化強制紅線（unbound→uncertain、fail 無證據→uncertain、裁判逾時→uncertain 揭露）；判定寫 `workflow/acceptance-audit.jsonl` + advisory；配額分桶 `audit_quota`（acceptance 上限 8/保底 6，與其他審查互不餓死）。**enforce 閘（config `acceptance_review.enforce`）**：Stop 時同步審（settings.json codex Stop timeout 150s），fail 且 severity≥`enforce_severity_threshold`（high）→ block 收尾附逐條證據；沿用 top-level `stop_gate_max_blocks=2`，同 spec 第 3 次不再審強制放行＋揭露 advisory；裁判逾時→uncertain 放行＋degraded metric；unbound/無證據 fail 經 `map_acceptance_verdict` 強制 uncertain 永不 block；規格檔標 done 的觸發維持 async 影子；一鍵退影子=enforce:false。回測工具 `backtest_acceptance.py`（歷史回放+種缺陷 20 案，Q5 評估依據） |
| `extract-worker.py` | SessionEnd 萃取子程序（共用 `lib/ollama_extract_core.py`）。**對談結束自動落地**：`_session_end_writeback` 把 session_end 全文萃取 + 累積 `knowledge_queue` flush 成 [臨] auto-capture 草稿（**2026-06-18：依 session cwd 路由 scope=shared/global，見 `_flush_route`**；**2026-06-24：草稿一律隔離到 `_drafts/auto-capture/` 子層，`_flush_item_to_atom` 改 `build_atom_content`+`write_raw` 直寫——`sync-atom-index` 排除 `_drafts` → 不入索引/不注入/不計數，根治 content-as-filename 碎片污染 memory/ 根**；過品質閘、只清寫成功項、`session_end_flush.max_atoms` 上限）。**失敗深記**：`_failure_writeback` 寫多區塊骨架（始末/根因/設計原理/運作邏輯/防再犯；小模型填始末＋拆根因，餘段留待 Claude 深寫） |
| `lib/ollama_extract_core.py` | 萃取共用核心 |
| `quick-extract.py` | ~~Stop async 快篩~~（**孤兒·Stop hook 已撤、無 caller；檔案保留供回滾**）|

> V4.1 終態的 16 個 `wg_*.py` + 2651 行 dispatcher 歸檔在 [`DevHistory/v4-archive/`](DevHistory/v4-archive/)（19 檔），含演化對照表。

### Auto-Handoff 四層自動交接（2026-06-09）

大型工項跨 session 時，原本只靠使用者記得手動 `/handoff` 才有六區塊交接；context 自動壓縮或 token 將盡而未先 handoff → 下個 session「裸奔」失真。核心模組 `wg_handoff.py`，四層協作（皆包 `config.auto_handoff.*` 開關、fail-open、`enabled=false` 一鍵全關回現狀）：

| 層 | Hook | 角色 | 觸發信號 |
|----|------|------|---------|
| **Layer 2** 核心保底 | `PreCompact` | 壓縮真發生時 `should_write_stub` 通過 → `build_handoff_stub` 寫客觀 stub 到 `resolve_staging_dir`，設 `pending_handoff_emit` | 壓縮事件（**不依賴 token 量測**，最可靠） |
| **Layer 3** 品質補全 | `PostToolBatch` | 壓縮後首批工具呼叫見 `pending_handoff_emit` → 與 `pending_reinjection` blob **合流**注入提示叫模型補全主觀 TODO 區塊 + 清 flag | `pending_handoff_emit` |
| **Layer 1** 提前預警 | `Stop` | `token_warn_payload` 算 usage ratio≥`token_warn_ratio`(預設 0.85) → piggyback 既有 block 附 token 預警（一次性 `token_warn_emitted`，零額外打斷） | usage ratio（讀 `message.usage` 真實 token；分母自我校準 200k/1M〔曾破 200k 必為 1M〕、預設 1M；無 usage 時 fallback char-proxy；僅信號） |
| **Layer 4** 直結兜底 | `SessionEnd` | session 直接結束（非壓縮）、有未完成工作且無既有 handoff → 補寫客觀 stub（不設 `pending_handoff_emit`，已無 PostToolBatch 可消費） | `should_write_stub`（modified_files；與 `sync_pending` 同源） |

- **stub 六區塊**：前置脈絡/已完成/權威來源/產出位置（客觀，自動填 git branch+commit / modified+accessed files / injected atoms / knowledge_queue）+ 做法/決策依據/why（主觀，留 `TODO(模型補全)` 佔位）。第一行為 `/continue` 選單摘要、檔名 `next-phase-auto.md`（/continue glob `next-phase*.md` 涵蓋）。
- **state 欄位**（additive，舊 state 讀不到當 False）：`pending_handoff_emit` / `handoff_stub_path` / `handoff_stub_at` / `token_warn_emitted`。
- **IDENTITY 收尾 (c) 串接**：Layer 1 程式化 token 量測取代「純 AI 自估」；見 `[Auto-Handoff]` 預警則由 AI 語意判斷是否已處理失真（語意層保留，見 `stop.py` ScanReport gate (c) 文字）。
- **Phase 4（PoC 完成，獨立於 hook · 實驗性 · 非正式上線）**：`tools/auto-continue/auto_continue.py` 外部編排 watcher——監看 `resolve_staging_dir` 的 `next-phase*.md` → 起 headless `claude -p "/continue"` 自動接續 → 完工寫新 stub → 遞迴。四道 guard（`max_consecutive_spawns` / `budget_usd` 累計成本 / `confirm_every_n` 人工確認 / `kill_switch` flag）＋ single-stub 不變式（多 stub 時 headless `/continue` 會選單卡死 → 停手）。**已實證**（VSCode 擴充套件 binary 2.1.169）：`claude -p "/continue" --output-format json` 在隔離空目錄回 `is_error:false`/exit 0、`result` 為 /continue skill 0-stub 原文 → headless 確實執行 slash-command skill（依 atom [[cc-能力查證反編譯實跑-binary]]，binary 字串表 + 實跑雙查證）。spawn 接 stdin DEVNULL 避 3s 卡。設計與可行性邊界見 `plans/wise-wobbling-gem.md` line 50-58/81-82；用法/風險見 `tools/auto-continue/README.md`。

### 輔助 Hook 腳本

| 檔案 | 用途 |
|------|------|
| `user-init.sh` | 多人 USER.md 初始化（SessionStart） |
| `ensure-mcp.py` | MCP server 可用性確認 |
| `webfetch-guard.sh` | WebFetch 安全護欄 |

### 常駐可觀測層（statusline + 週健檢）

零 token 的使用者可見層，把「純資訊性 chat 注入」移出 context：

| 元件 | 機制 |
|------|------|
| `tools/statusline.py` | settings.json `statusLine` 指入（refreshInterval 10s + 每則訊息事件驅動）。stdin 吃 CC status JSON（session_id/model/context_window），純 stdlib 讀 `state-<sid>.json`（改檔/讀檔/知識佇列數）+ `vector_ready.flag` + `aec-report/<sid>-t*.json` 最大 turn severity → 一行 ANSI 狀態列。fail-open 必告知：state 壞 → `WG:?`；任何錯誤仍印一行 |
| `tools/health-weekly.py` | Windows Task Scheduler `Claude-Memory-WeeklyHealth`（週一 09:00，StartWhenAvailable 補跑）驅動，無 CC session 依賴。唯讀聚合：memory-audit + atom-health-check + 兩索引 --check + vector + **注入效果**（memory-effect-report --json：token 稅/零效用證據 → 黃）+ **管線鮮度**（有 session 但 promotion audit/episodic 停 14 天 → 紅）→ `workflow/health-reports/`（留 12 份）+ `health-last-run.json`。SessionStart `_health_advisory` 為死人開關：排程器本身死了也會在 session 浮出 |
| `tools/memory-effect-report.py` | 注入效果報表（唯讀）：access.json 曝光+α/β Wilson 下界 + `Logs/rescue-log.jsonl` 使用證據 → 三清單（top 有用 / 高曝光零使用 token 稅附 trigger 收斂建議 / 零曝光死重候選）+ 30 天週趨勢。入口：`/memory health` step 4 + 週健檢 5b。詳見 TECH §5.10 |

取捨：CC 原生 CronCreate 為雲端 agent、碰不到本機 `~/.claude`，故健檢採 Task Scheduler。OTEL export 評估不做（兩目標指標 per-hook 延遲/注入 token 稅皆不在匯出面，見 atom [[otel-遙測評估結論-不實作-兩目標指標皆測不到]]）。

## Skills（V5 全域 <!-- skill-count -->21<!-- /skill-count --> 個 active，2026-05-27 起；記憶系統 skill + 1 外部〔karpathy-guidelines〕；unity-mcp-skill 2026-06-12 已搬遷專案層；**init-roles / conflict-review 於 P8a 2026-07-01 單人環境降 dormant → `skills/_archived/`**，故不計入 21）

V5 Wave 3 把 V4 的 `commands/*.md` 遷到 `.claude/skills/{name}/SKILL.md`（對齊 Anthropic 官方「commands merged into skills」）。Legacy `commands/` **2026-05-27 已刪除**（原 7 天緩衝經對拍 100% identical 驗證後提前廢止）。

**invocation 硬化**：9 個重炮/儀式/debug 型 skill 設 frontmatter `disable-model-invocation: true`（atom-debug / changelog-debug / codex-companion / continue / extract / fix-escalation / generate-episodic / heal-review / upgrade）——模型不可呼叫（含自然語言請求）、description 不佔 context，僅使用者 `/slash` 可觸發；codex-companion 另有反逃避意涵（模型不得自關監督器）。保留模型可呼叫的例外依據：consciousness-stream（rules/core.md「用識流…」映射由模型代打）、handoff（`wg_handoff.py` 注入「建議主動 /handoff」）、skill-creator / karpathy-guidelines（設計上要自動觸發）、其餘工具型（browse-sprites / harvest / journal / memory / conflict / read-project / refile / vector）自然語言觸發利大於誤觸。

| Skill | 檔案 | 用途 |
|-------|------|------|
| ~~`/init-roles`~~ | `skills/_archived/init-roles/SKILL.md` | V4 多職務模式啟用引導（**P8a archived·dormant**；tools/init-roles.py 仍在）|
| `/continue` | `skills/continue/SKILL.md` | 讀 _staging/next-phase.md 續接 |
| `/consciousness-stream` | `skills/consciousness-stream/SKILL.md` | 識流處理 |
| `/handoff` | `skills/handoff/SKILL.md` | 跨 Session Handoff Prompt Builder |
| `/journal` | `skills/journal/SKILL.md` | 工作日誌產出 |
| `/upgrade` | `skills/upgrade/SKILL.md` | 環境升級 |
| `/fix-escalation` | `skills/fix-escalation/SKILL.md` | 精確修正升級 |
| `/extract` | `skills/extract/SKILL.md` | 手動知識萃取 |
| `/generate-episodic` | `skills/generate-episodic/SKILL.md` | 手動生成 episodic atom |
| `/conflict` | `skills/conflict/SKILL.md` | 記憶衝突偵測 |
| ~~`/conflict-review`~~ | `skills/_archived/conflict-review/SKILL.md` | V4 管理職裁決 Pending Queue（**P8a archived·dormant**；tools/conflict-review.py 仍在）|
| `/memory` | `skills/memory/SKILL.md` | **5 合 1**：health / peek / undo / review / session-score（subcmd 分派） |
| `/atom-debug` | `skills/atom-debug/SKILL.md` | Debug log 開關 |
| `/harvest` | `skills/harvest/SKILL.md` | 網頁收割→Markdown |
| `/read-project` | `skills/read-project/SKILL.md` | 系統性閱讀→doc-index atom |
| `/vector` | `skills/vector/SKILL.md` | 向量服務管理 |
| `/changelog-debug` | `skills/changelog-debug/SKILL.md` | 手動滾動 _CHANGELOG（hook 已自動，僅 debug） |
| `/browse-sprites` | `skills/browse-sprites/SKILL.md` | 批次圖片預覽 |
| `/codex-companion` | `skills/codex-companion/SKILL.md` | Codex Companion 開關（V5 subprocess 模型） |
| `/skill-creator` | `skills/skill-creator/SKILL.md` | **新增 meta-skill**：寫/改/審 skill（Progressive Disclosure 三層 + 5 設計模式 + audit/new-skill/cost-measure 工具） |
| `/heal-review` | `skills/heal-review/SKILL.md` | 管理職裁決記憶自癒失敗佇列 |
| `/refile` | `skills/refile/SKILL.md` | V6 手動歸檔（核心檔護欄 + realm 分類提議 + doc-ref 掃描） |
| `/karpathy-guidelines` | `skills/karpathy-guidelines/SKILL.md` | **外部 skill（MIT，源 multica-ai）**：寫/審/重構碼行為準則；on-demand 被動，非 always-on；加值的 verify-loop 另萃 atom [[goal-driven-verify-loop]] |

> V5 已刪除（與內建衝突）：`/resume`（內建 --resume）、`/init-project`（內建 /init）、`/svn-update` / `/unity-yaml`（下沉專案層）、`/changelog-roll`（改名 changelog-debug）。

## 演化中 feature（保留細節於主檔）

### Evasion Guard / Test-Fail Gate（`wg_evasion.py`，2026-04-17+）

程式碼強固 LLM「錯誤的迴避」行為——不依賴模型自律，兩層擋住。

| 觸發點 | 偵測 | 動作 |
|---|---|---|
| PostToolUse (Bash) | 測試指令（pytest/tsc/node --check/jest/go test/cargo test）→ 解析 stdout+stderr | 失敗最後 20 行寫 `state["failing_tests"][]`；同 cmd 重跑成功 → 清舊紀錄 |
| Stop | `failing_tests` 非空 + last assistant text 命中完成宣告 regex | `output_block` 硬阻擋，要求 (a)修復 (b)標為 regression (c)降級任務 |
| Stop | last assistant text 命中退避 regex（不在本範圍/既有 drift/pre-existing/留給未來/非本次；**時間性延後**：下次/下回/之後/晚點/稍後/有空/有時間 + 再 + 處理/修/補/做/看/弄；未來處理/待後續/另行處理/留給使用者） | 寫 `state["evasion_flag"]` + `evasion_events` 證據暫存（供 AEC (b) cross-check，不受 UPS 清旗影響）+ 觸發落 `Logs/guard-evasion.jsonl`（誤攔率可量測；docdrift/lang_guard 同款 `guard-*.jsonl`） |
| Stop | **ScanReport Gate（Anti-Evasion HUD）**：宣告完成 + **本 session 自己 Edit/Write 的** `modified_files` 觸及 core 檔（hooks/lib/tools/rules/根層契約設定）或達 `min_files_to_block` + **本回合未 emit `anti_evasion_report`** + 無使用者豁免 + **本 turn 未跑 git/svn commit** | `output_block` 硬阻擋，要求呼叫 MCP tool `anti_evasion_report(a,b,c,d)`（(a) 缺失修補 (b) 逃避通報 (c) token 警示 (d) 衍生暫存；內容走 HUD、chat 只留折疊 chip）。滿足判定用 **turn_seq+session_id 雙鍵**（sibling 隔離：共用工作樹/merged state 下隔壁 session 的 emit 不誤放行本 session）。每 session 只觸發一次（`scan_report_warned`）。他 session 改的 core 檔（`session_id` 不符）不誤觸發——只數 `own_mod_files`（legacy fail-open）。**純 VCS commit turn 豁免**（`last_commit_turn_seq==turn_seq`；工作已可稽核、綁「真的 commit」非「本 turn 沒 Edit」）。**one-writer**：MCP tool 只回 chip、不碰 state；Python `post_tool_use` 獨佔寫 state+落 per-turn `aec-report/<sid>-t<turn>.json`。**(b) 欄 cross-check**：emit 時 hook 實測退避證據（`evasion_events`/`evasion_flag`，窗口＝上次 emit 之後）非空而 (b)=「無」→ one-writer 升 severity=real-evasion + report 附 `hook_evidence`（不信模型自評；Node chip 純內容判定無 state 可查，以 report 檔/Stop fallback 為準）。**(d) 刪除決策後驗**：HUD delete 決策注入後，下輪 UPS `exists()` 實查——檔案仍在 → 重注入一次（`reinjected`），再仍在 → 告警後結案（`verified`，不無限 nag）。HUD 不可達+notable → Stop 大聲 fallback 回 chat（不 fail-silent；cross-check 升級時附 hook 證據） |
| UserPromptSubmit | `evasion_flag` 非空 | 注入 `[Guardian:Evasion]` 舉證要求，注入後清旗 |
| UserPromptSubmit | prompt 命中放行詞（「先這樣/跳過/known regression」） | 清 `failing_tests`；近 3 則 user prompt 有放行詞 → skip evasion flag |

state 以 `setdefault` 增量，不升 schema_version。相關 atom：`memory/feedback/feedback-fix-on-discovery.md`；相關文件：`IDENTITY.md` 反退避契約節（針對 Opus 4.7 Effort=High「精準縮限範圍」傾向）。

### _CHANGELOG Auto-Roll（`tools/changelog-roll.py`，2026-04-17+）

PostToolUse hook 偵測 `_CHANGELOG.md` 寫入 → 行數 >`config.changelog_auto_roll.threshold`（預設 8）→ detached subprocess 跑 roll 工具 → 超額條目搬到 `_CHANGELOG_ARCHIVE.md`。Fail-open。手動入口 `/changelog-roll`。

## 規則模組

`.claude/rules/core.md`（合併版）由 Claude Code 自動載入；CLAUDE.md 瘦身至 ~50 行。Hook 自動執行可程式碼化的部分（同步、品質函數、震盪偵測）。

**治理原則（P5 2026-07-01 入 `rules/core.md`）**：① **Native-first** — 原生機制（CLAUDE.md / skills / memory / resume）優先，自製 atom/hook 只做原生做不到的「結構化·可稽核·跨-session 高價值」，不為想像中的需求長枝葉（過度工程的正解是誠實化＋修剪，非推倒重來）；② **可觀測性鐵律** — 所有 fail-open 必「不阻斷但要告知」，降級/靜默失敗要浮出訊號（反例：vector service 靜默死 27 天無人知）。

## 記憶系統（原子記憶 V5）— 子系統索引

> V5 概覽：[`SPEC_ATOM_V5.md`](SPEC_ATOM_V5.md)。
> V5 vs V4 差異：`_atom_index.json` 為機器 SoT（取代脆性的 _ATOM_INDEX.md table parser）；全域檢索層 BM25 in-memory（取代 Vector daemon 殺雞用牛刀）；Codex Companion daemon→subprocess（拔 port 3850）；commands→skills 對齊原生。

雙 LLM 架構：Claude Code（雲端）= 決策/分類；Ollama Dual-Backend（本地）= embedding/萃取/re-ranking。

| 主題 | 詳情文件 | keywords |
|---|---|---|
| Dual-Backend Ollama 退避 | [DevHistory/ollama-backend.md](DevHistory/ollama-backend.md) | 退避, DIE, rdchat, failover |
| 記憶檢索管線 + 回應知識捕獲 | [DevHistory/memory-pipeline.md](DevHistory/memory-pipeline.md) | pipeline, JIT, vector, hot_cache |
| V3 三層即時管線 | [DevHistory/memory-pipeline.md](DevHistory/memory-pipeline.md) | V3, quick-extract, deep extract |
| V4.1 使用者決策萃取 + P4 Session 評價 | [DevHistory/v41-journey.md](DevHistory/v41-journey.md) §10 | user-extract, L0, L1, L2, gemma4, session_score |
| SessionStart 去重 + Merge self-heal | [DevHistory/session-mgmt.md](DevHistory/session-mgmt.md) | dedup, merge_into, orphan cleanup |
| 專案自治層 + V4 三層 Scope + JIT | [DevHistory/v4-layers.md](DevHistory/v4-layers.md) | scope, personal, shared, role, vector layer |
| V4 三時段衝突偵測（Phase 5+6） | [DevHistory/v4-conflict.md](DevHistory/v4-conflict.md) | conflict, pending_review, CONTRADICT, EXTEND |
| Wisdom Engine + Fix Escalation + 跨 Session 鞏固 | [DevHistory/wisdom-engine.md](DevHistory/wisdom-engine.md) | wisdom, reflection, fix_escalation |
| settings.json 權限 + 工具鏈 | [DevHistory/settings-config.md](DevHistory/settings-config.md) | permissions, 權限, tools |

資料層：`MEMORY.md` 索引（always-loaded）+ atom 檔（按需）+ LanceDB vector + episodic + wisdom + 專案自治層。

### 召回可靠性 + 效果實證（E 組）

| 機制 | 一句話 |
|------|--------|
| Vector 啟動器自癒（`tools/memory-vector-service/starter.py`） | SessionStart/UPS 共用：service stderr 落 `Logs/vector-service.log`、hang 死 kill-restart、等待窗 120s + spawn lock；UPS 端 flag 缺失 re-kick（`wg_atoms._ensure_vector_ready`，cooldown 120s）——服務中途死下一 prompt 自癒 |
| 救援日誌（`hooks/wg_rescue.py`） | 注入 atom 抽高特異 token（確定性、寧缺勿濫）→ 後續工具呼叫命中落 `Logs/rescue-log.jsonl`＝「記憶真被用上」直接證據 |
| 效果報表（`tools/memory-effect-report.py`） | 四節：top 有用 / token 稅 / 死重候選 / **D 失念（recall-miss 30 天聚合）** + 30 天趨勢 |
| 失念偵測（`hooks/wg_recall_miss.py`） | SessionEnd 比對「本 session 失敗證據（failing_tests/evasion/failure_kw）× 庫中未注入 atom trigger」（≥2 非泛用詞命中才算）→ `Logs/recall-miss.jsonl`；週健檢 14 天 ≥3 次 → 黃燈 |
| 專案層 vector enrichment（`ups_search`） | trigger 命中後、**專案層 atom 存在且 trigger 命中 <3** 才跑 vector 且只取專案層命中；訊號充足或無專案層跳過 |
| 原生記憶橋接（`tools/native-memory-bridge.py`） | 核心 atom 索引指標行鏡像進 `projects/<slug>/memory/`（harness 清單格式，掃描不誤納） |

詳見 TECH §5.10–5.12；驗證 `verify_{vector_starter,rescue_log,effect_report,project_enrichment,native_bridge,recall_miss}.py`。

### 檢索品質工程（RRF 融合 + 回歸評估）

| 機制 | 一句話 |
|------|--------|
| RRF 三路融合（`wg_atoms.rrf_fuse` + `ups_search`） | trigger/BM25/vector 三路 rank 融合 `Σ 1/(60+rank)` × activation 調節 `exp(0.25·rank)`；config `vector_search.fusion`（"legacy" 回退純 ACT-R 排序） |
| ACT-R 個別化 decay（`wg_atoms`） | `d = clamp(0.5 − γ·wilson_lb, 0.3, 0.5)`，γ=`usefulness.stability_gamma`(0.3)——高效用 atom 衰減慢；新 atom（無 access log）activation 回中性 0.0 |
| 回歸評估集（`tools/memory-eval/`） | 223 條合成查詢 + Recall@1/@3/MRR/誤注入 + baseline 比對——調參秒級 A/B（bm25_min_score 7.0、RRF 落地皆以此定值） |
| 效用校準 | `wilson_z` 1.28（3 連勝可升）+ `demote_min_n` 5 + decay 每日護欄（`last_decay_date`） |

詳見 TECH §5.11；SPEC §13/§14（Depends/Evidence + 檢索融合規格）。

### Atom 寫入單點收束（funnel，S1–S4，2026-05-04）

> 全系統所有 atom 寫入經過 `lib/atom_io.py` 唯一入口；違者由 PreToolUse 強制門禁攔截。

**架構：**

- `lib/atom_spec.py` — atom 格式規則純函式（slugify / build_atom_content / validate / SKIP_DIRS / VALID_SCOPES），audit/health/atom_io 共用 import 避免規則漂移
- `lib/atom_io.py` — knowledge funnel 入口：`write_atom()` (build+validate+atomic write+index+audit log) / `write_raw()` (escape hatch for failures/episodic 子族) / `write_index_full()` (整檔重組 sync 用) / `edit_metadata()` (元資料外科編輯：Trigger/Related/Tags，只替換 frontmatter 對應行、byte-stable 不重建知識區；triggers 變更時 **先寫 `_atom_index.json`(SoT) 再寫 frontmatter**，內部複用 write_index + write_raw funnel；取代「直 Edit atom .md（被 guard 擋）」與「整檔 atom_write replace」。2026-06-02)。Wave 2（2026-05-05）：`update_atom_field()` 已移除，計數類欄位（read_hits / last_used / confirmations）改走 `lib/atom_access.py`
- `lib/atom_access.py` — telemetry funnel 入口（Wave 2）：`<atom>.access.json` 旁路檔讀寫單一通道；`init_access` / `increment_read_hits` / `increment_confirmation` / `record_promotion` / `read_access` / `write_access_field` / `bulk_read`；**Phase 2 (#2) 效用閉環**：`record_usefulness`(α/β) / `decay_usefulness` / `wilson_lower_bound` / `usefulness_stats` / `usefulness_promote_eligible` / `usefulness_demote_candidate` / `usefulness_hint_tier`（注入提示分級）；CLI 入口 `python -m lib.atom_access` 給 MCP server.js spawn 用
- `lib/atom_io_cli.py` — stdin JSON → write_* → stdout JSON，供 MCP server.js spawn。**2026-06-12 parity 方案 B** 加 `build`（build_atom_content+validate，回 content 不落檔）/ `append`（`atom_io.append_atom_file`：拼接+validate+write_raw 落檔）兩 action——server.js toolAtomWrite 的內容構造（create/replace）與 append 拼接統一 spawn py 單一實作，js `buildAtomContent`/`renderKnowledgeLines` 退役為 test_13 parity fixture、append CRLF 混寫面根除（守門 test_24/25）

**Caller 接線（contract: source 必填，記入 `_meta/atom_io_audit.jsonl`）：**

| Caller | source 名稱 | 切入點 |
|---|---|---|
| MCP server.js (toolAtomWrite/Promote) | `mcp` | `spawnAtomCli("build"/"append")` + `funnelWriteRaw()` + `funnelWriteIndexFull()` + `spawnAtomAccess()` |
| MCP server.js (toolAtomEditMeta) | `mcp` | spawn inline python → `lib.atom_io.edit_metadata`（改全域 server 需重啟生效） |
| hooks/workflow-guardian.py (atom 注入計數) | `hook:atom-inject` | `atom_access.increment_read_hits` |
| hooks/extract-worker.py (failure atom) | `hook:extract-worker` | `_failure_writeback` + `_create_failure_atom` |
| hooks/wg_episodic.py (cross-session confirm) | `hook:episodic-confirm` | `atom_access.increment_confirmation` |
| hooks/wg_episodic.py (episodic atom) | `hook:episodic` | `write_raw` + `atom_access.init_access` |
| hooks/quick-extract / user-extract | `hook:user-extract` | (S2 接) |
| tools/migrate-v3-to-v4.py | `tool:migrate` | `write_raw` migration patch |
| tools/memory-undo.py | `tool:undo` | `write_raw` reject footer |
| tools/atom-move.py | `tool:atom-move` | `write_raw` (atom) + `write_index_full` (index) |
| tools/memory-audit.py | `tool:memory-audit` | demote / compact / log_evolution `write_raw` + `atom_access.write_access_field` |
| tools/sync-atom-index / sync-memory-index | `tool:sync-*` | `write_index_full` |

**Atom 知識／遙測切分（Wave 2 落地）：**

- atom `.md` 檔頭只放知識性 metadata：`Scope` / `Confidence` / `Trigger` / `Type` / `Author` / `Tags` / `Related` / `Created` / `description` / `name`
- `<atom>.access.json` 旁路檔（schema `atom-access-v3`）放運行期遙測：`read_hits`（純曝光） / `last_used` / `confirmations` / `useful_hits`(α) / `used_fail`(β)（Phase 2 效用，Laplace prior 1，v2→v3 冪等 migration） / `last_promoted_at` / `first_seen` / `timestamps`（最多 50 筆）/ `confirmation_events`
- 1:1 對應 atom；刪 atom 自然連帶刪遙測；無集中檔競態風險
- 任何 atom .md 出現在 `git status` modified 都必然是知識內容變更（語意改動），便於 review

**強制門禁（PreToolUse）：**

- `hooks/wg_core.py:check_memory_path_block`
  - (a) `~/.claude/projects/{slug}/memory/` 殘骸 → deny [P1]（⚠ 2026-06-12 認知更新：新版 CC harness 原生 file-based memory 重新合法佔用此路徑且自建 MEMORY.md，與 atom 索引 marker 撞名；cross-project 掃描已改 `_has_atom_index_marker` 內容辨識（`dad9783`），P1 gate 是否續擋 harness 寫入待裁決——詳 atom [[harness原生memory與atom索引marker撞名辨識]]）
  - (b) `~/.claude/.claude/memory/` 雙層路徑 → deny [P6]
  - (c) `.claude/memory/` 樹下 atom .md 直 Write/Edit 不走 funnel → deny [S3.3]
  - (d) `_AIDocs/Failures/` 下「註冊 atom」(feedback-* / cognitive-patterns / memory-pipeline-* 等失敗 atom) 直 Write/Edit → deny（`_is_failures_atom_path` 以 `failures_atom_stems()` 比對 `_atom_index.json` 精準鎖定，不誤擋同目錄混居的 legacy 失敗筆記與 `_INDEX.md`）
- 白名單：`MEMORY.md` / `_ATOM_INDEX.md` / `_` 前綴檔 / `_meta`/`_staging`/`episodic`/`wisdom`/`personal` 子目錄。**不含 `Failures`**——Failures atom 由 (d) 主動 gate，非白名單豁免（白名單若含 `Failures`，未來一旦把 caller intersect 改 case-insensitive 會豁免整個目錄、廢掉 (d)，覆蓋缺口復發）
- 緊急 bypass：env `WG_DISABLE_ATOM_GUARD=1`

**MCP cwd-scope 雙向防護（server.js:resolveMemDir）：**

- P3：scope=global 配 project root cwd（非 `~/.claude`）→ reject（避免污染 global），可用 `force_global=true` escape
- P4：scope=shared/role/personal 配 cwd 在 `~/.claude` 下 → reject（V4 sub-scope 在專案層才有意義）

**反向證明工具：**

- `tools/check-bypass.py` — 靜態掃 hooks/tools/lib/plugins 內所有 `write_text`/`open(..., w)`/`fs.writeFileSync` 出現在 memory 路徑附近的點，white-list 之外 → 印警告（CI exit 1）
- `tools/audit-reconcile.py` — 動態對拍：列近期 mtime atom × audit log entries（`--since 30s/2h/1d`，也接 `2h ago`）。S4 強化分類：每筆 unmatched 走 `git diff` 判定 `counter_only`（diff 只動 Last-used / Confirmations / ReadHits / Related 欄位 + [臨]/[觀]/[固] 信心 tag promotion，hook:read-counter 設計直寫）/ `knowledge`（動到知識內容 → 真實 bypass）/ `unknown`（無 git / 未追蹤）。預設只在 knowledge 有 unmatched 時 exit 1；`--strict` 則 unknown 也視為 bypass

**驗證腳本（H-test-prune 後 verify 化）：**

- `lib/verify/verify_atom_io_equivalence.py` — 11 cases 對拍 server.js byte-identical
- `tools/verify/verify_check_bypass.py` — 5 cases 驗 white-list 比對 + violation 偵測
- （`test_guardian_atom_write_gate.py` 與 `test_audit_reconcile.py` 已歸檔到 `_AIDocs/DevHistory/v5-overhaul-2026-05/tests-archive/`）

**S4 收尾（2026-05-04）：**

- 知識 atom 入庫（走 funnel source=`mcp`）：`feedback-clean-before-build` / `feedback-checker-rule-consolidation` / `decisions-architecture` 加印象 bullet
- 殘骸清理：移除 `~/.claude/projects/c--users-holylight--claude/memory/` 空目錄（Layers 2→1）
- audit-reconcile classifier：counter_only/knowledge/unknown 三分類，53 unmatched → 0 knowledge bypass

### Realm 範疇分區（核心 vs 非核心，2026-06-03）

> 全貌見 [`SPEC_ATOM_V5.md` §2.2](SPEC_ATOM_V5.md) + atom `realm-範疇分區機制-v5`。

非核心（local）記憶（腦內世界 / 特定外部工具踩坑 / Guardian 特定實例開發）**只在 ~/.claude 內才有用**，跨專案時佔 token 又是雜訊。補上 realm 維度後外部專案零負擔（例外：`CROSS_PROJECT_LOCAL_DOMAINS` 如 `Continuity`，storage 在 _atoms 但跨專案注入，對偶 feedback-*）。

- **realm 由 index `path` 前綴推導**（不存欄位、與 scope 正交）：path 落 `_AIDocs/_atoms/<domain>/`（World/Tools/MemDev）⇒ local（**仍 `Scope=global`**）；否則 core。沿用 feedback-* 同一招（物理在 `_AIDocs/` 下、靠 index path 注入），零新管線。
- **注入閘門**：`hooks/handlers/session_start.py` 建候選快取處依 `wg_core._is_under_claude_dir(cwd)` 濾掉 local 候選；外部專案完全略過、core（含 `_AIDocs/Failures/*`）不誤殺。
- **分類器 `classify_realm`**（lib + server.js mirror）：安全預設 core、核心保護清單硬擋、詞庫只用實例專屬名（不用記憶系統通用詞）、只掃 name+triggers。**詞庫/保護清單/權重單一來源 `memory/_meta/realm-lexicon.json`**——py/js 兩端模組載入時讀同檔（缺失/損毀 fallback 內建最小保護清單＋stderr 告警），取代兩份手抄常數。**詞庫污染根治（2026-06-24，SGI 第三度污染後）**：① sink 端第三護欄 `_RESERVED_LEXICON_TERMS` exact 拒收系統 trigger 標籤/realm 自名/已知外部專案名（sgi/uba）；② SessionEnd sweep 對未確認 auto-capture 碎片（`_is_unconfirmed_autocapture`：trigger 含 auto-capture ∨ Author=auto-captured∧[臨]）整體 defer 不搬不喚 LLM，斷詞庫自汙染源；③ 核心保護 exact 集補 `自己flag…`（Author=holylight/[臨] 故 P2 不護→反覆誤搬後列硬擋）。
- **搬遷工具 `tools/atom-set-realm.py`**：`_AIDocs/_atoms/` path 唯一寫者，連 `.access.json` sidecar 原子搬、Scope 保 global、`--to-core` 可逆；**不**走 `atom-move`。
- **印象層（catalog 層 realm，2026-06-04）**：`sync-memory-index` 雙輸出——core atom → `MEMORY.md`（CLAUDE.md `@import`，全專案，fail-safe 退路）；local atom → 側檔 `memory/_local_catalog.md`（依 domain 分組），僅核心環境由 `session_start.py` 共同尾段（`_is_under_claude_dir` gate）注入。MEMORY.md 末尾僅留一行指標 → **外部專案 always-load 不再含本地範疇段（`_local_catalog.md` 546 字元，實務 ~180 tok；CJK-aware 保守估 ~330）**，補完 realm 在 index 層的一致性。fail-safe：hook 掛掉/缺檔僅損核心環境本地「目錄顯示」（atom 仍 trigger 注入），外部專案不受影響。
- **find-fallback**：server.js promote/edit_meta/find 對物理在 memory/ 外的 atom 加 `findAtomFileRecursive(LOCAL_ATOMS_DIR)`（鏡像 feedback fallback），否則 scope=global 的 local atom 會 `Atom not found`。
- **V6 LLM-assisted recall + 階層 domain（2026-06-04，全貌見 SPEC §2.2）**：詞庫封閉 allow-list 漏判（wsl2 漏進 core）的根治。① 詞庫 miss 的 unknown-core 在 **SessionEnd sweep** 喚本地 LLM（`tools/realm_llm_classify.py`，**熱路徑不掛**）判 realm + 多段階層 domain，Fail-safe 四態（`error`→defer 留原地、`core`→留、`local`→搬 canon、`unsure`/低信心→`Else`；protected 永不喚 LLM）。**⚠ P3（2026-07-01）起 `realm.llm_fallback.enabled=false` 預設關 — 只跑 deterministic 詞庫（含 learned）保確定性 sweep；改回 true 才復原 LLM recall**；② domain 變**關聯式分級階層**（`normalize_domain_path` snap 既有兄弟 + 增量深度閘 depth=volume，新分支封頂 3、絕對天花板 7）；③ validated terms 回寫 `memory/_meta/realm-lexicon-learned.json` 自學（py-only，js 維持 base-only 保 parity）；④ catalog `_local_catalog.md` always-load 只 Lv1 根、深層按需 `_INDEX.md`；⑤ 手動前端 **`/refile` skill**（`skills/refile/`）含核心檔辨識護欄 + 移檔後 doc-ref 掃描。
- **守門**：`verify_atom_io_equivalence.py` test_14–22（常數/routing/分類器零誤判/py↔js parity/canon/深度閘/自學）+ `verify_realm_injection_gate.py` + `tools/verify/verify_realm_llm_classify.py`（V6 LLM 分類器函式）+ `hooks/verify/verify_realm_sweep.py`（V6 SessionEnd sweep Fail-safe 四態決策）+ `verify_local_catalog_split.py`（深樹 + stale）。

## MCP Servers（V5：4 tool）

V5 Wave 2 砍 4 個內部 IPC tool（`workflow_signal` / `workflow_status` / `memory_queue_add` / `memory_queue_flush`），改由 Stop gate hook 自動偵測。

| Server | 傳輸 | 用途 | 暴露 tool |
|--------|------|------|----------|
| workflow-guardian | stdio (Node.js) | session 管理 + Dashboard (port 3848) | `atom_write` / `atom_move` / `atom_promote` / `atom_edit_meta`（4 個業務 tool） |

### atom_write 工具（V4 三層 scope，2026-04-15+）

| 參數 | 行為 |
|------|------|
| `scope=global` | 寫 `~/.claude/memory/` |
| `scope=shared`（預設） | 寫 `{proj}/.claude/memory/shared/` |
| `scope=role` + `role=...` | 寫 `roles/{role}/`，metadata `Scope: role:{role}` |
| `scope=personal` + `user=...` | 寫 `personal/{user}/`，metadata `Scope: personal:{user}` |
| `scope=project`（legacy） | 透明轉 `shared` + stderr deprecation hint |

新 metadata 自動帶入：`Author`（server 端 env/OS user）、`Created-at`（今日）、`Audience`/`Pending-review-by`/`Merge-strategy`（optional）；選填 `status` 參數 → `- Status:` 現況一行（cold/skip 一行注入時附帶；只寫現況、禁版本敘事）。
**SPEC 7.4 敏感類別自動 pending**：`scope=shared` 且 `audience ∈ {architecture, decision}` → `shared/_pending_review/` + `Pending-review-by: management`。
**Knowledge 區大小預算（瘦身規範）**：`lib/atom_spec.KNOWLEDGE_BUDGET_BYTES`（3KB，依據見常數註解）——write-gate 排最前硬拒（explicit_user/pitfall 不豁免，config `write_gate.knowledge_budget_bytes` 可調/停用）＋落檔端 floor（`atom_io_cli` build/create_atom 覆蓋 create/replace、`atom_io.append_atom_file` 覆蓋 append——肥大化實際路徑，以拼接後總量計；`skip_gate` 繞不過）。`write_raw` escape hatch（episodic/failures）豁免；validate（讀取/heal 路徑）不檢大小＝存量肥 atom 讀取不受影響、不回溯整改。另有樣式軟警（逐筆表格/路徑清單 → 建議收斂為文件錨點一行，附在 create 成功訊息尾端）。

### atom_promote

晉升門檻（Phase 2 #2，py↔js 鏡像，SYNC: `lib/atom_access` ↔ `server.js`）—— **Confirmations 主軌 OR 效用 Wilson 下界**：
- **Primary**: Confirmations（跨 session 萃取命中）[臨]→[觀] ≥4, [觀]→[固] ≥10
- **Usefulness**: 效用 Wilson 下界 lb≥`promote_lb`(0.6) 且 n≥`min_n`(3)，z=`wilson_z`(1.28，3 連勝 lb=0.6468 可升)（注入→使用→結果 α/β 校準；降級候選 lb≤0.35 且 n≥`demote_min_n`(5)）
- **ReadHits 已退出晉升、降為純曝光計數**（取代舊 Auxiliary ≥20/≥50 + 7 天 fallback；依 Xiong 2505.16067 純檢索/注入頻率晉升會劣化品質）。注入時僅 `usefulness_hint_tier` 判定接近/已達升門才提示主動確認

`merge_to_preferences=true`（global only，[觀]→[固] 時）把「## 知識」合併到 `preferences.md` 並搬原 atom 到 `memory/_archived/`。

### atom_edit_meta（元資料外科編輯，2026-06-02）

暴露 `lib/atom_io.edit_metadata` 給 AI：只改 atom frontmatter 的 `Trigger`/`Related`/`Tags` 行、byte-stable，不重建知識區。triggers 變更走 SoT-first（先 `_atom_index.json` 後 frontmatter）。取代被 guard 擋的「直 Edit atom .md」與會重建整檔的「atom_write replace」。契約細節見 [SPEC_ATOM_V5.md §3.4](SPEC_ATOM_V5.md)、code [server.js:toolAtomEditMeta](../tools/workflow-guardian-mcp/server.js)。**改全域 server 需重啟生效。**

### UserPromptSubmit Atom-Write Guard

偵測「記住/存起來/寫 atom/存成 [固]」關鍵字 → 注入硬規則（新 atom 一律 [臨]、晉升走 `atom_promote`、更新既有走 `mode=append`），降低 Claude 建議錯誤的 retry 成本。

詳見 [SPEC_ATOM_V5.md](SPEC_ATOM_V5.md)（V4 留作對照證物：[SPEC_ATOM_V4.md](SPEC_ATOM_V4.md)）。

---

## Testing & Verify

V5 GA 後 tests/ 已 verify 化重組（H-test-prune，2026-05-28）。

**四原則**（決定砍/留）：

1. 預設砍，留下要有強理由
2. 「必須觸發」≠「每輪觸發」：拔了系統會壞才留；不會壞 → 連 source 一起拔
3. 越容易飄移、模糊的越該刪
4. 強雙向高頻連動的驗證腳本 → verify 化搬 source 同層

**目錄結構**：

```
hooks/verify/                                ← 68 個（atom/evasion/extract/wisdom/rrf_fusion/stability_decay/recall_miss 等 hook 守衛）
tools/verify/                                ← 12 個（check_bypass / memory_eval / stale_deps / conflict_evidence / vector_service 等）
tools/codex-companion/verify/                ← 6 個（assessor_retry / scorer / heuristics / handoff_review / artifact_sampling / prompt_input_integrity；另有 smoke_plan_review.py 手動冒煙不被收集）
tools/auto-continue/verify/                  ← 1 個
lib/verify/                                  ← 8 個（atom_io_equivalence contract / edit_metadata / atom_spec_depends_evidence / usefulness_access 等）
```

**命名與 pytest 規則**：

- 檔名：`verify_*.py`（拿掉 `test_` 改前綴；pytest.ini 設 `python_files = test_*.py verify_*.py`）
- 函數名：保留 `test_*()`（pytest 預設認）
- import：`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` → source 同層；不深度 package 化（V5 dispatcher 仍用 `from handlers import` 裸名 + sys.path）

**統一入口**：

`python run_verify.py` — 跨平台 entrypoint，動態掃 `{src}/verify/` + `skills/{name}/verify/`，跑 `pytest -v --tb=short`。完成宣告前必跑（取代 `pytest tests/`）。

---

## 腦內世界 v3（記憶可視化 + Command Bus + 真・自癒）

`tools/workflow-guardian-mcp/world.html` 把每個 atom 畫成生物（房間=專案、體型=資深、★=戰力、🤢=壞掉）。v3 在純視覺上加三層，由 :3848 dashboard server 服務。

**硬約束**：對話/本地判斷共用單張 3090（Gemma-4-31B 序列）。準則：行為分**免費層**（移動/罐頭/機械修，純前端或腳本）與**昂貴層**（LLM，節流/可配置並行）。

### P1/P2 前端（world.html，純前端零後端成本）
- **個性** `personaOf(c)`：類別(name/type)×年資(confidence)×狀態(sick/lonely/elder) → 注入 `creatureChat` 的 sys prompt，不增 LLM 呼叫數。
- **自主行為** `wander()`/`sickWalk()`：房內漫步；生病生物自走 🏥 觸發自動 L1。`dialogueDirector()` 每 18–30s 在 `chatBusy` 空閒時挑一對聊一次 → LLM 速率封頂、與生物數無關。`autoOn` 總開關。
- **Command Bus**：單一 `WORLD_COMMANDS` registry 衍生「選項式指令台」UI + executor + `/api/world-*` 輪詢。加指令＝改 registry 一處。Claude 用 `curl POST /api/world-command` + `GET /api/world-snapshot` 同套 API 驅動/觀測。

### P3 記憶自癒（`tools/atom-heal.py`＝單一來源）
腳本主導、判斷才呼 LLM、修完即驗證：
- **L1** `missing_reverse_refs` → 機械補反向連結（`edit_metadata`，免 LLM）。
- **L2** `broken_refs`/格式 → 呼 LLM 出結構化提案（repoint/remove/needs_human）→ 腳本經 funnel 套用 → 驗證。**禁盲刪**、repoint 只能指真實候選、LLM 失敗一律 needs_human。**P5（2026-07-01）：server.js `apiHealAll` 背景 sweep 抽出 `missing_reverse_refs`（已由 SessionEnd `--fix-refs` L1 補）＝只掃 `broken_refs`，與腦內世界解耦；SessionEnd/`/memory health` 事件接線待後續。**
- **L3** `stale` → 喚醒（不修）。
- 重用 `atom-health-check.py`（importlib：`single_atom_report` + `--atom` 過濾）/ `lib.atom_io.edit_metadata`(source=`tool:atom-heal`) / `lib.atom_spec.validate_atom_content` / `tools/ollama_client.get_client`。
- **後端可插拔**：`config.json` `heal.backend` 預設 `ollama`（本地免費、序列 `max_concurrent=1`）；`cloud` 為選配（並行 cap=N，adapter 待接）。
- **修不好 → `memory/_heal_review/<atom>.json` 診斷卡** + `_merge_history.log`；`/heal-review` skill（`tools/heal-review.py`）人工 resolve/dismiss（需 management）。

### server.js
- **`makeJobRunner` + `execJson`**：抽 testJobs 的「Map+鎖+輪詢+TTL 清除」共用，test 與 heal 共用（DRY）。
- 路由：Command Bus（`/api/world-command|world-commands|world-result|world-snapshot`）+ 自癒（`/api/heal/:atom?auto=1`、`heal-job/:id`、`heal-all`、`heal-review`）。spawn `atom-heal.py` 前 `ATOM_NAME_RE` 擋 shell 注入。
- **誠實痊癒**：前端只有 server 回 `fixed` 才移 `.sick`；修不好貼 🩹「轉診人工」不假裝。
- ⚠️ **改 server.js 需走重啟 SOP**（讓新實例透過協作式交棒接管 :3848；見 atom `guardian-dashboard-孤兒佔埠與新碼重啟`）。孤兒本身現由 **stdin-EOF 自行退出**預防（父 CC client 一斷線即隨之退出、自然釋放埠），交棒降為 abrupt-kill / 新舊碼升級路徑的兜底。

---

## 腦內世界 · 區域環境演化（放置式，Phase 1-5）

每個房間（=專案/記憶 scope）的生物（=atom）依現有對話頻率自主討論，依生物個性自決環境風格（城堡/花園/聚落/遊樂場/農場/港口/主題樂園/奇觀），想法擴散→鎖定→隨發展度逐步「長出」建築。**引擎＝瀏覽器驅動**（world.html 開著就跑、關了暫停、狀態存 server 故重開續長）。

**★硬約束＝零影響原子記憶**：只**讀**生物個性，發展狀態只**寫**獨立 `workflow/world-dev.json`（gitignore），**絕不**碰 `memory/` 樹、`_atom_index.json`、`*.access.json`、funnel/atom_write。驗收用 `git status` 證 memory 跑前後零 diff（結構性隔離：獨立 API + 獨立檔，server.js 既有碰記憶的路徑一律不呼）。

### 資料流
```
world.html(唯一推進引擎)
  ├─ ENV_CATALOG ← fetch environment-catalog.json(8 風格家族 × 6 tier 累加目錄；相對路徑→須 :8899 同層伺服)
  ├─ regionDev:Map(模組級持久，鏡像 world-dev.json；★絕不存進每5s重建的 model.c)
  ├─ engineTick()(TICK_MS=1000)：免LLM(擴散/共識/dev累加/tier解鎖/鎖定/多風格閘/完工) + LLM 2點(種子/定案)
  └─ reconcileDev/renderEnv/placeEnv → POST /api/world-dev(節流落盤)
server.js：GET /api/world-dev(讀檔/空骨架) · POST(深合併+debounce+原子 .tmp→rename)
workflow/world-dev.json：唯一存檔(與 memory/ 不同目錄＝隔離)
```

### 演化狀態機（每 region 獨立）
`IDLE ─種子→ PROPOSAL ─配對擴散(免LLM,consensus+1/dev+=step×diminish)→ 定案(dev≥35&cons≥3)→ STYLE(rank N) ─dev累加/跨0·20·40·60·80·100門檻解鎖該tier元素→ dev∈[60,80]准開第二風格(回IDLE並行) → dev≥80 COMPLETED`
- `devStep(dev)=max(0.3, dev_step×(1−dev/140))`＝diminishing 收斂不震盪、單調夾頂 100。
- 完工門檻：**rank1.dev≥80**（次風格續長不影響）。/loop 停止＝全部活躍區（list≥2）皆完工。

### LLM 僅 2 點 + fallback 鐵則
- 種子(`envBrainstorm`#1) + 定案(`envDirection`#2)，複用 `/api/creature-chat`(world-chat.js 不改)，共用 `chatBusy` 序列鎖 + 硬閘 `ENV_LLM_MIN_GAP`≈4s。其餘全免 LLM（fast 只加速免LLM 路徑，LLM 不加速）。
- prompt：sys 帶「區生物個性(聚合 fits_personality) + 8 家族白名單」→ 要 `{family_id,theme,seed_element,line}`；`cleanLine` 剝 crack 模型洩漏 token → `JSON.parse`（失敗抓 `/\{[\s\S]*\}/` 重試）；family 須∈白名單。
- **fallback 鐵則**：LLM 斷網/逾時/解析失敗 → 純前端依個性投票選 family + 目錄種子 + 罐頭台詞，**仍建 proposal/仍鎖定**（永不阻塞）。每區到 80% 約 2 次 LLM；fallback 命中可 0 次。

### 跨區串門子（`_visiting`）
tick 低頻挑「攜帶想法」生物 lerp 走向他區中心（**只動 el._x/_y、不改 c.region**，掛 tick 位移軸＝守 reconcile-render 動畫狀態歸屬鐵律）；作客配對→該區同 family 共識+1、dev+=step×CROSS_FACTOR（免LLM），無同 family 則以 carry 為種子建提案；到期歸位。

### 渲染層
- **env-layer**：房間建一次性 append `<svg preserveAspectRatio="none">`，z 夾 floor 與 `.cr` 間。
- **`placeEnv` deterministic**：seeded LCG(`hash32(key+"|"+id)`，**禁 Math.random**)→ 同 (region,element) 每 render 必同位；同 pos 類用 element.id 字典序（插入舊元素不位移）。emoji `<text>` 點綴／center 大地標 `<use href="#env-{svg_hint}">`／fallback 永有 emoji。
- **reconcile 友善**：`el._envSig=style|dev|style2|dev2|unlocked` 髒檢查，sig 沒變不碰 DOM。招牌第二行「風格 emoji+中文名+dev%」+ `.devbar` 進度條，dev≥80 加 ✅。

### 雙軌時間
config `world_dev.modes`：slow(env_chance .01/pair .05/dev_step 1.2) · fast(.55/.75/6.0)；經 world-dev.json 持久 / `?fast=1` / 指令台 `worlddev slow|fast|status|reset` 覆寫。

### 關鍵檔
`world.html`(引擎主體) · `server.js`(world-dev 原子讀寫 + GET/POST 路由) · `environment-catalog.json`(風格目錄) · `workflow/world-dev.json`(唯一存檔,gitignore) · `workflow/config.json`(`world_dev` 旋鈕) · `world-chat.js`(不改,LLM 通道沿用)。
