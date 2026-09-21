# Claude Code 全域設定 — 核心架構（Index）

> 本檔為**索引型**：只放「檔案在哪、誰負責什麼、為什麼這樣設計」。機制現況、常數、設定一律以 [`TECH.md`](../TECH.md)（與實碼）為準；本檔與之不符時以 TECH 為準並回報修正。
> 相關文件：`TECH.md`（機制現況）、[`SPEC_ATOM_V5.md`](SPEC_ATOM_V5.md)（atom 規格）、[`DocIndex-System.md`](DocIndex-System.md)（逐檔導覽）、`rules/core.md`（行為規則）、`Project_File_Tree.md`（頂層目錄角色）。

## Hooks 系統

9 個 hook 事件掛哪些腳本、timeout、職責：TECH §3.1；一個回合的序列圖：TECH §3.2。入口鏈：`settings.json` → `hooks/workflow-guardian.py`（薄 shim）→ `dispatcher.py`（純路由、惰性 import）→ `handlers/<event>.py`。

### 事件 × handler 入口表

| 事件 | handler 檔 | 一句話 | 機制細節 |
|------|-----------|--------|---------|
| `SessionStart` | `handlers/session_start.py` | init state + 去重 + 候選池／supersedes 集合 + vector 啟動器 + advisory（健檢死人開關／未 push／回訪／personal 同步／索引三檔衝突／ProjectRoot） | TECH §3.1、§8 |
| `UserPromptSubmit` | `handlers/user_prompt_submit.py`（orchestrator）→ `ups_gates.py`（detect：evasion 追蹤、使用者決策 L0、long_die、Atom-Write Guard）→ `ups_context.py`（episodic、wisdom、parallel／research 建議、_AIDocs 指標、JIT）→ `ups_search.py`（找）→ `ups_inject.py`（裝） | 記憶注入主路徑 + guard 提醒；UPS 被 kill 哨兵；AEC 刪除決策後驗 | TECH §5、§5.7 |
| `PreToolUse` | `handlers/pre_tool_use.py` | 寫入守門（下節）+ PAN + 跨 session 同檔預警 + 索引三檔合併閘 + git 隱私閘 + commit 口令閘 + subagent 記憶注入 | TECH §7.3、§7.5、§4.5、§12 |
| `PostToolUse` | `handlers/post_tool_use.py`（末段同程序呼叫 `version_guard.run()`／`acceptance_spec.run()`） | 改檔追蹤 + 增量索引 + test-fail 偵測 + changelog auto-roll + AEC one-writer + late-collision | TECH §7.2、§7.4、§7.5 |
| `PreCompact`／`PostCompact`／`PostToolBatch` | `handlers/pre_compact.py`／`post_compact.py`／`post_tool_batch.py` | 壓縮前快照 state + `injected_atoms` + handoff stub；壓縮後 stash 緊湊內文 + `pending_reinjection`；下一批工具一次性重注入 + stub 補全提示 | 本檔 Auto-Handoff 節 |
| `Stop` | `handlers/stop.py`；standalone `codex_companion.py`／`lang_guard.py` | 閘序：同步閘 → DeferralGate → ScanReport → AEC-Pending → 驗收裁判 enforce → Deep Post-Mortem → 迴歸提示；效用歸因；token 預警 piggyback；退避偵測（`detect_evasion` 對 last assistant text 於此執行）；transcript 單次 tail-read 供各消費者共用 | TECH §7.1、§6.4 |
| `SessionEnd` | `handlers/session_end.py` | episodic 生成 + 使用者決策萃取 spawn + decay 每日護欄 + selective forget（預設 dry-run）+ recall-miss + 晉升自動 commit／push + outcome 遙測 + GC（SessionEnd 全量萃取**未啟動**） | TECH §6.3、§6.4、§8 |

### 模組職責（一行）

| 模組 | 職責 |
|------|------|
| `handlers/_shared.py`／`aec_ledger.py` | 跨 handler 共用 helper（含 HUD 窗活性 `_hud_alive`、GC）／AEC 殘檔帳本唯一 writer |
| `wg_core.py` | 路徑唯一真相（專案根委派 `lib/project_root.py`）+ config／state IO + token budget 常數單一來源 + 覆轍白名單 + log rotation + PreToolUse guards |
| `wg_atoms.py` | atom index 解析 + trigger／BM25／vector client／RRF／ACT-R + 晉升 + 最終裁切（回填）+ 判用 v2 `detect_atom_use_v2` |
| `wg_extraction.py` | 失敗關鍵字萃取 + worker spawn + user-extract L0 + content classify |
| `wg_episodic.py` | episodic 生成 + 衝突偵測 + 品質回饋（harness 噪音清洗、覆轍白名單） |
| `wg_evasion.py` | 退避偵測 + Test-Fail + ScanReport + DeferralGate 判定 + AEC cross-check + outcome 遙測 |
| `wg_docdrift.py` | src → `_AIDocs` 映射 drift 提醒 |
| `wg_handoff.py` | Auto-Handoff：stub 六區塊 + token 預警純函式 |
| `wg_coordination.py` | 跨 session 同檔互寫預警 + git 收尾指令預警（純檔案、warn-only） |
| `wg_rescue.py` | 救援日誌：注入 atom 高特異 token → 後續工具呼叫命中＝「真被用上」 |
| `wg_recall_miss.py` | 失念偵測：失敗證據 × 庫中未注入 atom trigger |
| `wg_friction.py` | 工具結果體積 + 使用者糾正訊號 → Deep Post-Mortem |
| `wg_parallel.py`／`wg_research.py` | 並行 agent 建議／研究 fan-out 提示（後者命中時抑制前者） |
| `wg_roles.py` | 多職務雙向認證 shim（保留能力） |
| `wisdom_engine.py` | 反思引擎 + Fix Escalation |
| `codex_companion.py` | Codex Companion hook：in-process state + spawn `tools/codex-companion/audit.py`；五類審計與裁判後端鏈見 TECH §7.4、§7.5 |
| `extract-worker.py`／`user-extract-worker.py` | detached workers：失敗深記 `_failure_writeback`（→ `Failures/<主題>/`，永不拒寫）／使用者決策 L1→L2；共用 `lib/ollama_extract_core.py` |
| `lang_guard.py` | standalone Stop hook（TECH §7.5） |
| `version_guard.py`／`acceptance_spec.py` | 模組：`run(input_data, config) -> list[str]`，由 guardian PostToolUse 呼叫（TECH §7.5） |
| `run-hidden.py`／`run-bash-hidden.py`／`ensure-mcp.py`／`user-init.sh`／`post-git-pull.sh`／`webfetch-guard.sh` | 不閃窗 spawn／MCP 可用性／USER.md 初始化／pull 後審計／WebFetch 護欄 |

> V4 終態（16 個 `wg_*.py` + 2651 行單檔 dispatcher）歸檔在 [`DevHistory/v4-archive/`](DevHistory/v4-archive/)。

### PreToolUse 寫入守門（本段為唯一來源；PAN／同檔預警／合併閘／隱私閘／口令閘見 TECH §7.3、§7.5、§4.5、§12）

Write／Edit／NotebookEdit：
- **Atom Format Gate**：`.claude/memory/*.md` 不符 atom 格式 → deny。
- **Atom Confidence Gate**：新建 atom 的 `Confidence:` 與內文 `- [固]/- [觀]` 標籤必須全為 `[臨]`，鏡射 MCP `atom_write` mode=create 規則，封堵 Write tool 繞過路徑。
- **Memory Path Block**（`wg_core.check_memory_path_block`）：(a) `~/.claude/projects/{slug}/memory/`（CC 原生 auto-memory 目錄，不是記憶層；橋接檔由 `native-memory-bridge.py` 產）；(b) `~/.claude/.claude/memory/` 雙層路徑；(c) `.claude/memory/` 樹下 atom .md 不走 funnel 的直寫；(d) `memory/Failures/<主題>/` 已註冊 atom（`failures_atom_stems()` 對 `_atom_index.json` 精準比對，不擋 `_reference/` 與 `_INDEX.md`）。白名單：`MEMORY.md`／`_ATOM_INDEX.md`／`_` 前綴檔／`_meta`、`_staging`、`episodic`、`wisdom`、`personal` 子目錄（**不含 `Failures`**，由 (d) 主動 gate）。緊急 bypass：環境變數 `WG_DISABLE_ATOM_GUARD=1`。
- **Cross-Realm Write Block**（`wg_core.check_cross_realm_write`）：外部專案 session（cwd ∉ `~/.claude`）寫核心層 `~/.claude/{skills,tools,hooks,lib,rules}/` 或根層敏感檔（settings.json／CLAUDE.md／IDENTITY*.md／USER*.md）→ deny 並指路專案層 `.claude/skills|tools/`；config `guard.cross_realm_write`（可關／allowlist）。

Bash／PowerShell：
- **SVN Test Block**：`svn commit/ci` 含 `tests?/`、`__tests__/` 路徑或 `*Test.<ext>` → deny（atom `feedback-no-test-to-svn`）。
- **Cross-Realm MCP Block**：外部專案 session 的 `claude mcp add -s user`／`claude mcp remove` 未限定 project|local scope → deny，指路 `-s project`。
- **Cross-Realm Bash Block**（`wg_core.check_cross_realm_bash`）：外部專案 session 在根層上下文（`cd ~/.claude`、`git -C`、命令列指到 hooks/lib/tools/skills/rules/prompts 或根層設定檔）做動手操作（heredoc、內嵌 python、redirect、`sed -i`、cp/mv/rm、git add/commit/push、PowerShell 寫入 cmdlet）→ deny，要求寫成 prompt 交使用者到 `~/.claude` session 執行；純跑 `python ~/.claude/tools/x.py`（不 cd）與唯讀命令放行，且「跑根層工具」本身不構成根層上下文；config `guard.cross_realm_bash.{enabled,allowlist}`。

全部 fail-open；核心開發 session（cwd ∈ `~/.claude`）不受 Cross-Realm 三閘影響。

### Auto-Handoff 四層自動交接（本段為唯一來源；TECH §7.5 只有一列）

大型工項跨 session 時，原本只靠使用者記得手動 `/handoff` 才有六區塊交接；context 自動壓縮或 token 將盡而未先 handoff → 下個 session「裸奔」失真。核心模組 `wg_handoff.py`，四層協作（皆包 `config.auto_handoff.*` 開關、fail-open、`enabled=false` 一鍵全關）：

| 層 | Hook | 角色 | 觸發信號 |
|----|------|------|---------|
| **Layer 2** 核心保底 | `PreCompact` | 壓縮真發生時 `should_write_stub` 通過 → `build_handoff_stub` 寫客觀 stub 到 `resolve_staging_dir`，設 `pending_handoff_emit` | 壓縮事件（**不依賴 token 量測**，最可靠） |
| **Layer 3** 品質補全 | `PostToolBatch` | 壓縮後首批工具呼叫見 `pending_handoff_emit` → 與 `pending_reinjection` blob **合流**注入提示叫模型補全主觀 TODO 區塊 + 清 flag | `pending_handoff_emit` |
| **Layer 1** 提前預警 | `Stop` | `token_warn_payload` 算 usage ratio ≥ `token_warn_ratio`（預設 0.85）→ piggyback 既有 block 附 token 預警（一次性 `token_warn_emitted`，零額外打斷） | usage ratio（讀 `message.usage` 真實 token；分母 `context_window_tokens`，曾破 200k 必為 1M；無 usage 時 fallback char-proxy；僅信號） |
| **Layer 4** 直結兜底 | `SessionEnd` | session 直接結束（非壓縮）、有未完成工作且無既有 handoff → 補寫客觀 stub（不設 `pending_handoff_emit`，已無 PostToolBatch 可消費） | `should_write_stub`（modified_files；與 `sync_pending` 同源） |

- **stub 六區塊**：前置脈絡／已完成／權威來源／產出位置（客觀，自動填 git branch+commit、modified+accessed files、injected atoms、knowledge_queue）+ 做法／決策依據／why（主觀，留 `TODO(模型補全)` 佔位）。第一行為 `/continue` 選單摘要、檔名 `next-phase-auto.md`（`/continue` glob `next-phase*.md` 涵蓋）。
- **state 欄位**（additive，舊 state 讀不到當 False）：`pending_handoff_emit`／`handoff_stub_path`／`handoff_stub_at`／`token_warn_emitted`。
- **IDENTITY 收尾串接**：Layer 1 程式化 token 量測取代「純 AI 自估」；見 `[Auto-Handoff]` 預警則由 AI 語意判斷是否已處理失真（語意層保留，見 `stop.py` ScanReport gate (c) 文字）。
- **Phase 4 外部編排 watcher**（`tools/auto-continue/`，實驗性、非正式上線）：監看 `next-phase*.md` → 起 headless `claude -p "/continue"` 自動接續 → 完工寫新 stub → 遞迴；四道 guard 與 headless 實證見 `tools/auto-continue/README.md`。

### 常駐可觀測層

statusline／週健檢／效果報表／救援日誌／失念偵測／回訪／guard JSONL：TECH §8。取捨：週健檢用 Windows Task Scheduler 而非 CC 原生 CronCreate／Routines——後者為雲端 agent，碰不到本機 `~/.claude`；OTEL export 不做（TECH §8 末段）。

## Skills（全域 <!-- skill-count -->21<!-- /skill-count --> 個 active）

逐 skill 檔案與用途：DocIndex-System §5。`init-roles`／`conflict-review` 單人環境 dormant → `skills/_archived/`（不計入）；V5 從 `commands/*.md` 遷移與已刪除清單：SPEC §4。

**invocation 硬化**（本段為唯一來源）：9 個重炮／儀式／debug 型 skill 設 frontmatter `disable-model-invocation: true`（atom-debug／changelog-debug／codex-companion／continue／extract／fix-escalation／generate-episodic／heal-review／upgrade）——模型不可呼叫（含自然語言請求）、description 不佔 context，僅使用者 `/slash` 可觸發；codex-companion 另有反逃避意涵（模型不得自關監督器）。保留模型可呼叫的例外依據：consciousness-stream（`rules/core.md`「用識流…」映射由模型代打）、handoff（`wg_handoff.py` 注入「建議主動 /handoff」）、skill-creator／karpathy-guidelines（設計上要自動觸發）、其餘工具型（browse-sprites／harvest／journal／memory／conflict／read-project／refile／vector）自然語言觸發利大於誤觸。

## 演化中 feature

### 反退避：Evasion Guard／Test-Fail Gate／ScanReport（`wg_evasion.py`）

程式碼強固 LLM「錯誤的迴避」行為——不依賴模型自律。Stop 閘序、禁語單一來源、九欄報告、one-writer cross-check、殘檔帳本受保護路徑、刪除後驗、AEC-Pending、遙測：TECH §7.1、§7.2。以下為 TECH 未收的判定細節（本段為唯一來源）：

- **Test-Fail Gate 資料流**：PostToolUse(Bash) 解析測試指令（pytest／tsc／node --check／jest／go test／cargo test）stdout+stderr → 失敗尾 20 行寫 `state["failing_tests"][]`；同 cmd 重跑成功即清舊紀錄。Stop 見 `failing_tests` 非空 + last assistant text 命中完成宣告 → block，要求 (a)修復 (b)標為 regression (c)降級任務。使用者放行詞（先這樣／跳過／known regression）清 `failing_tests`；近 3 則 user prompt 有放行詞 → 不掛 evasion flag。
- **退避偵測時點**：Stop 對 last assistant text 跑 `detect_evasion`（禁語表 `memory/_meta/forbidden-phrases.json`）→ `evasion_flag` + `evasion_events` 證據暫存（不受 UPS 清旗影響，供 AEC (b) cross-check）→ 下輪 UPS 注入 `[Guardian:Evasion]` 舉證要求後清旗。
- **ScanReport 觸發條件**：宣告完成 + **本 session 自己 Edit/Write 的** `modified_files` 觸及 core 檔（hooks/lib/tools/rules/根層契約設定）或達 `min_files_to_block` + 本回合未 emit `anti_evasion_report` + 無使用者豁免 + **本 turn 未跑 git/svn commit**（`last_commit_turn_seq==turn_seq` 豁免：工作已可稽核，綁「真的 commit」非「本 turn 沒 Edit」）。滿足判定用 **turn_seq+session_id 雙鍵**（共用工作樹／merged state 下隔壁 session 的 emit 不誤放行本 session）；每 session 只觸發一次（`scan_report_warned`）；他 session 改的 core 檔不計（只數 `own_mod_files`）。
- **HUD 窗活性**（`handlers/_shared._hud_alive`，emit 時與 Stop 各查一次）：Node `beat-status` 的 `clients`（HUD 頁 SSE 常駐連線數）≥1 → 活，頁被瀏覽器休眠／凍結心跳全停也不誤判；無連線才看心跳 `age_s < hud_stale_s`；判死原因（逾時／拒連／404／無連線）落 `Logs/guard-aec_hud.jsonl`；HUD 不可達且 notable → Stop 大聲 fallback 回 chat（不 fail-silent）。
- state 以 `setdefault` 增量，不升 schema_version。相關 atom：[[feedback-workflow-discipline]]；`IDENTITY.md` 反退避契約節為語意層對應。

### _CHANGELOG Auto-Roll（`tools/changelog-roll.py`；本段為唯一來源）

PostToolUse 偵測 `_CHANGELOG.md` 寫入 → 行數 > `config.changelog_auto_roll.threshold`（預設 8）→ detached subprocess 跑 roll 工具 → 超額條目搬到 `_CHANGELOG_ARCHIVE.md`。Fail-open。手動入口 `/changelog-debug`。

## 規則模組

`rules/core.md`（治理原則、知識庫、記憶、對話）與 `rules/coding-style.md` 由 Claude Code 自動載入；`CLAUDE.md` 只 `@IDENTITY.md @USER.md @memory/MEMORY.md`。治理原則本文與反例：TECH §1.3；always-load 成本：TECH §11.1。Hook 已程式化強制的規則不在 rules 重述。

## 記憶系統（原子記憶 V5）— 子系統索引

現況（資料層、檢索注入、寫入積累、晉升／降級、降級策略、常數、設定）：TECH §4–§6、§12；規格：[`SPEC_ATOM_V5.md`](SPEC_ATOM_V5.md)。

召回可靠性與效果實證（vector 啟動器自癒、救援日誌、效果報表、失念偵測、專案層 enrichment、原生橋接）：TECH §8、§5.1、§4.7；守門 `hooks/verify/verify_{vector_starter,rescue_log,effect_report,project_enrichment,native_bridge,recall_miss}.py`。檢索品質（RRF 融合、activation 增益 0、BM25 每輪跑＋停用詞、Supersedes 池層、ACT-R 個別化 decay、對齊評估器）：TECH §5.1–§5.3、§5.6；SPEC §13／§14。

**歷史設計文件**索引（含當時脈絡；現況以 TECH 為準）：

| 主題 | 詳情文件 | keywords |
|---|---|---|
| Dual-Backend Ollama 退避 | [DevHistory/ollama-backend.md](DevHistory/ollama-backend.md) | 退避, DIE, rdchat, failover |
| 記憶檢索管線 + 回應知識捕獲（含已除役 hot cache／quick-extract） | [DevHistory/memory-pipeline.md](DevHistory/memory-pipeline.md) | pipeline, JIT, vector, hot_cache |
| V4.1 使用者決策萃取 + P4 Session 評價 | [DevHistory/v41-journey.md](DevHistory/v41-journey.md) §10 | user-extract, L0, L1, L2, gemma4, session_score |
| SessionStart 去重 + Merge self-heal | [DevHistory/session-mgmt.md](DevHistory/session-mgmt.md) | dedup, merge_into, orphan cleanup |
| 專案自治層 + V4 三層 Scope + JIT | [DevHistory/v4-layers.md](DevHistory/v4-layers.md) | scope, personal, shared, role, vector layer |
| V4 三時段衝突偵測 | [DevHistory/v4-conflict.md](DevHistory/v4-conflict.md) | conflict, pending_review, CONTRADICT, EXTEND |
| Wisdom Engine + Fix Escalation + 跨 Session 鞏固 | [DevHistory/wisdom-engine.md](DevHistory/wisdom-engine.md) | wisdom, reflection, fix_escalation |
| settings.json 權限 + 工具鏈 | [DevHistory/settings-config.md](DevHistory/settings-config.md) | permissions, 權限, tools |
| 核心記憶分類階層化（範疇資料夾、寫入閘、realm） | [DevHistory/核心記憶分類階層化-2026-08.md](DevHistory/核心記憶分類階層化-2026-08.md) | taxonomy, domain, realm |
| 注入變弱調查（根因鏈、五次修正） | [DevHistory/injection-budget-investigation-2026-08.md](DevHistory/injection-budget-investigation-2026-08.md) | budget, 回填, 1200 |
| V5 升版全紀錄 | [DevHistory/v5-overhaul-2026-05/](DevHistory/v5-overhaul-2026-05/) | JSON SoT, BM25, subprocess, tests-archive |

### Atom 寫入 funnel — 檔案地圖與 caller 接線

閘門序、落點單一裁決（py `locate_atom` 一份、js 不鏡像）、write gate 評分、去重限層：TECH §6.1–§6.2；atom 知識／遙測切分（`.access.json` sidecar）：TECH §4.1。

**lib 檔案地圖：**

- `lib/atom_spec.py` — atom 格式規則純函式（slugify／build_atom_content／validate／SKIP_DIRS／VALID_SCOPES），audit／health／atom_io 共用 import 避免規則漂移。
- `lib/atom_io.py` — funnel 入口：`write_atom()`（build+validate+atomic write+index+audit log）／`write_raw()`（escape hatch：failures／episodic）／`write_index_full()`（整檔重組）／`edit_metadata()`（只改 Trigger／Related／Tags 行、byte-stable；triggers 變更先寫 `_atom_index.json` 再寫 frontmatter）／`locate_atom()`（落點單一裁決）。
- `lib/atom_access.py` — 遙測 funnel：`<atom>.access.json` 讀寫單一通道（read_hits／α β／Wilson／decay／promotion）；CLI `python -m lib.atom_access` 給 MCP spawn。
- `lib/realm_gate.py` — 「專案專屬內容不得落 global」閘（TECH §6.1）。
- `lib/atom_io_cli.py` — stdin JSON → `write_*`／`build`／`append`／`locate`／`realm_check` → stdout JSON，供 MCP server.js spawn（內容構造 py 單一實作，js 不再自組）。

**Knowledge 區大小預算**（本段為唯一來源）：`lib/atom_spec.KNOWLEDGE_BUDGET_BYTES`（3072）——write-gate 排最前硬拒（explicit_user／pitfall 不豁免；config `write_gate.knowledge_budget_bytes` 可調／停用）＋落檔端 floor（`atom_io_cli` build／create 覆蓋 create／replace、`atom_io.append_atom_file` 覆蓋 append，以拼接後總量計；`skip_gate` 繞不過）。`write_raw` 豁免；validate（讀取／heal 路徑）不檢大小＝存量肥 atom 不回溯整改。另有樣式軟警（逐筆表格／路徑清單 → 建議收斂為文件錨點一行）。

**Caller 接線**（contract：`source` 必填，記入 `memory/_meta/atom_io_audit.jsonl`；本表為唯一來源）：

| Caller | source 名稱 | 切入點 |
|---|---|---|
| MCP server.js（toolAtomWrite／Promote） | `mcp` | `spawnAtomCli("build"/"append")` + `funnelWriteRaw()` + `funnelWriteIndexFull()` + `spawnAtomAccess()` |
| MCP server.js（toolAtomEditMeta） | `mcp` | spawn python → `lib.atom_io.edit_metadata`（改全域 server 需重啟生效） |
| `hooks/handlers/ups_inject.py`／`ups_context.py`（atom 注入曝光計數） | `hook:atom-inject` | `atom_access.increment_read_hits` |
| `hooks/extract-worker.py`（failure atom） | `hook:extract-worker` | `_failure_writeback` + `_create_failure_atom` |
| `hooks/wg_episodic.py`（cross-session confirm） | `hook:episodic-confirm` | `atom_access.increment_confirmation`（資料源停產，TECH §14.2） |
| `hooks/wg_episodic.py`（episodic atom） | `hook:episodic` | `write_raw` + `atom_access.init_access` |
| `hooks/user-extract-worker.py` | `hook:user-extract` | L1／L2 決策萃取落地；落點三分：`~/.claude` → global／專案規則（`_is_project_rule`）→ shared＋`Author=使用者`／其餘 → 本人×專案 personal |
| `tools/memory-undo.py` | `tool:undo` | `write_raw` reject footer |
| `tools/atom-move.py` | `tool:atom-move` | `write_raw`（atom）+ `write_index_full`（index） |
| `tools/memory-audit.py` | `tool:memory-audit` | demote／compact／log_evolution `write_raw` + `atom_access.write_access_field` |
| `tools/sync-atom-index`／`sync-memory-index` | `tool:sync-*` | `write_index_full`；`--fix-scope-from-path` 索引 scope 以 path 為準回寫（冪等）；`--all-projects` |
| `tools/classify-project-scope.py` | `tool:atom-move`（沿用） | 專案記憶 scope 分層整理 `status`／`plan`／`apply`／`mark`；SOP 在 `/memory classify` |

**反向證明**：`tools/check-bypass.py` 靜態掃 hooks／tools／lib／plugins 內所有 memory 路徑附近的寫檔點，white-list 之外 → 警告（CI exit 1）；守門 `tools/verify/verify_check_bypass.py`。舊 `audit-reconcile.py` 已歸檔 `DevHistory/v5-overhaul-2026-05/tools-archive/`。

### Realm 範疇分區（core vs local）

對照表與判定三問：TECH §4.3；全貌（兩根、realm 由 index path 推導、注入閘、分類器與詞庫單一來源 `memory/_meta/realm-lexicon.json`、詞庫污染護欄、階層 domain、LLM fallback 預設關）：SPEC §2.2；決策脈絡：`DevHistory/核心記憶分類階層化-2026-08.md`。

檔案地圖：`lib/atom_locations.classify_realm`（+ server.js mirror，base-only 保 parity）、`tools/atom-set-realm.py`（`_AIDocs/_atoms/` path 唯一寫者，連 `.access.json` sidecar 原子搬、Scope 保 global、`--to-core` 可逆，不走 `atom-move`）、`tools/realm_llm_classify.py`（SessionEnd sweep 用，`realm.llm_fallback.enabled` 預設 false）、`memory/_local_catalog.md`（local 目錄，僅 `~/.claude` 注入）、`skills/refile/`（手動歸檔前端）。守門：`lib/verify/verify_atom_io_equivalence.py`（分類器零誤判／py↔js parity／canon／深度閘／自學）、`lib/verify/verify_realm_injection_gate.py`、`tools/verify/verify_realm_llm_classify.py`、`hooks/verify/verify_realm_sweep.py`、`tools/verify/verify_local_catalog_split.py`。

## MCP Server（5 tool：atom_write／atom_promote／atom_move／atom_edit_meta／anti_evasion_report）

服務表與不在時行為：TECH §9；`atom_write` 閘門序：TECH §6.1；scope 落點：TECH §4.4；晉升條件（只走效用 Wilson 軌、ReadHits 純曝光）：TECH §6.4；`atom_edit_meta` 契約：SPEC §3.4；create／append／replace 落點 vs 定位分離：SPEC §2.3；砍掉的 4 個內部 IPC tool：TECH §14.2。

檔案地圖：`tools/workflow-guardian-mcp/server.js`（stdio MCP + `:3848` dashboard + `/aec/hud` 同進程）、`lib/mcp.js`（tool 註冊）、`lib/atom-tools.js`（每 tool 先 `spawnAtomCli("locate")` 再照用回傳路徑）、`lib/funnel.js`、`lib/anti-evasion.js`、`lib/aec-hud-html.js`／`dashboard-html.js`、`lib/http-api.js`、`lib/realm.js`（只剩 `getCurrentUser`／`dedupLayersFor`）、`lib/atom-access.js`、`lib/paths.js`、`lib/state.js`；模組對照 `lib/_MAP.md`。

TECH 未收的行為（本段為唯一來源）：
- `atom_write` 選填 `status` → `- Status:` 現況一行（cold／skip 一行注入時附帶；只寫現況、禁版本敘事）；`scope=project`（legacy）透明轉 `shared` + stderr deprecation hint。
- `atom_promote merge_to_preferences=true`（global only，[觀]→[固] 時）：把「## 知識」合併到 `preferences.md`、原 atom 搬 `memory/_archived/`。
- 改 `server.js` 或全域 MCP 設定需重啟才生效；重啟 SOP 見 atom `guardian-dashboard-孤兒佔埠與新碼重啟`。孤兒 server 由 **stdin-EOF 自行退出**預防（父 CC client 一斷線即隨之退出、釋放埠），協作式交棒為 abrupt-kill／新舊碼升級的兜底。

## Testing & Verify（本段為唯一來源；TECH §10 只有入口一行）

**四原則**（決定砍／留）：

1. 預設砍，留下要有強理由
2. 「必須觸發」≠「每輪觸發」：拔了系統會壞才留；不會壞 → 連 source 一起拔
3. 越容易飄移、模糊的越該刪
4. 強雙向高頻連動的驗證腳本 → verify 化搬 source 同層

**目錄結構**（verify 檔與 source 同層）：

```
hooks/verify/                 ← hook 守衛（atom／evasion／extract／wisdom／rrf_fusion／recall_miss／lf_writes／merge_driver_gate／attribution／injection_delivery…）
tools/verify/                 ← check_bypass／memory_eval／stale_deps／vector_service／merge_atom_index／normalize_eol／doc_counts…
tools/codex-companion/verify/ ← assessor／scorer／heuristics／handoff_review／artifact_sampling／prompt_input_integrity（smoke_plan_review.py 手動冒煙不被收集）
tools/auto-continue/verify/
lib/verify/                   ← atom_io_equivalence contract／edit_metadata／atom_spec_depends_evidence／usefulness_access／locate_single_authority／realm_injection_gate…
skills/<name>/verify/         ← skill 自帶守衛
```

**命名與 pytest 規則**：檔名 `verify_*.py`（`pytest.ini` `python_files = test_*.py verify_*.py`）；函數名保留 `test_*()`；import 用 `sys.path.insert(0, <source 同層>)`，不深度 package 化（dispatcher 仍用 `from handlers import` 裸名）。

**統一入口**：`python run_verify.py` — 動態掃 `{src}/verify/` + `skills/{name}/verify/`，跑 `pytest -v --tb=short`。完成宣告前必跑。歷史 tests 歸檔：`DevHistory/v5-overhaul-2026-05/tests-archive/`。

---

## 腦內世界 v3（記憶可視化 + Command Bus + 真・自癒）（本段為唯一來源）

`tools/workflow-guardian-mcp/world.html` 把每個 atom 畫成生物（房間=專案、體型=資深、★=戰力、🤢=壞掉）。v3 在純視覺上加三層。world.html 為靜態檔（瀏覽器 file:// 直接開，server.js 無路由服務它），資料與指令走 :3848 dashboard server 的 `/api/*`。

**硬約束**：對話/本地判斷共用單張 3090（Gemma-4-31B 序列）。準則：行為分**免費層**（移動/罐頭/機械修，純前端或腳本）與**昂貴層**（LLM，節流/可配置並行）。

### P1/P2 前端（world.html，純前端零後端成本）
- **個性** `personaOf(c)`：類別(name/type)×年資(confidence)×狀態(sick/lonely/elder) → 注入 `creatureChat` 的 sys prompt，不增 LLM 呼叫數。
- **自主行為** `wander()`/`sickWalk()`：房內漫步；生病生物自走 🏥 觸發自動 L1。`dialogueDirector()` 每 18–30s 在 `chatBusy` 空閒時挑一對聊一次 → LLM 速率封頂、與生物數無關。`autoOn` 總開關。
- **Command Bus**：單一 `WORLD_COMMANDS` registry 衍生「選項式指令台」UI + executor + `/api/world-*` 輪詢。加指令＝改 registry 一處。Claude 用 `curl POST /api/world-command` + `GET /api/world-snapshot` 同套 API 驅動/觀測。

### P3 記憶自癒（`tools/atom-heal.py`＝單一來源）
腳本主導、判斷才呼 LLM、修完即驗證：
- **L1** `missing_reverse_refs` → 機械補反向連結（`edit_metadata`，免 LLM）。
- **L2** `broken_refs`/格式 → 呼 LLM 出結構化提案（repoint/remove/needs_human）→ 腳本經 funnel 套用 → 驗證。**禁盲刪**、repoint 只能指真實候選、LLM 失敗一律 needs_human。現況：server.js `apiHealAll` 背景 sweep 只掃 `broken_refs`（`missing_reverse_refs` 已由 SessionEnd `--fix-refs` L1 補），與腦內世界解耦；SessionEnd／`/memory health` 事件接線未做。
- **L3** `stale` → 喚醒（不修）。
- 重用 `atom-health-check.py`（importlib：`single_atom_report` + `--atom` 過濾）/ `lib.atom_io.edit_metadata`(source=`tool:atom-heal`) / `lib.atom_spec.validate_atom_content` / `tools/ollama_client.get_client`。
- **後端可插拔**：`config.json` `heal.backend` 預設 `ollama`（本地免費、序列 `max_concurrent=1`）；`cloud` 為選配（並行 cap=N，adapter 待接）。
- **修不好 → `memory/_heal_review/<atom>.json` 診斷卡** + `_merge_history.log`；`/heal-review` skill（`tools/heal-review.py`）人工 resolve/dismiss（需 management）。

### server.js
- **`makeJobRunner` + `execJson`**：抽 testJobs 的「Map+鎖+輪詢+TTL 清除」共用，test 與 heal 共用（DRY）。
- 路由：Command Bus（`/api/world-command|world-commands|world-result|world-snapshot`）+ 自癒（`/api/heal/:atom?auto=1`、`heal-job/:id`、`heal-all`、`heal-review`）。spawn `atom-heal.py` 前 `ATOM_NAME_RE` 擋 shell 注入。
- **誠實痊癒**：前端只有 server 回 `fixed` 才移 `.sick`；修不好貼 🩹「轉診人工」不假裝。
- ⚠️ 改 server.js 需走重啟 SOP（見上節 MCP Server）。

---

## 腦內世界 · 區域環境演化（放置式）（本段為唯一來源）

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
旋鈕唯一來源 `world.html` 的 `ENGINE.modes`（slow／fast 倍率；`workflow/config.json` 不再鏡像）；mode 經 world-dev.json 持久 / `?fast=1` / 指令台 `worlddev slow|fast|status|reset` 覆寫。

### 關鍵檔
`world.html`(引擎主體) · `server.js`(world-dev 原子讀寫 + GET/POST 路由) · `environment-catalog.json`(風格目錄) · `workflow/world-dev.json`(唯一存檔,gitignore) · `world-chat.js`(不改,LLM 通道沿用)。
