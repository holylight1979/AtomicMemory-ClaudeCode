# SPEC: 原子記憶系統 V5 — 對齊原生 + JSON 機器源 + Subprocess Companion

> **狀態**：規格定稿（V5 GA 候選，2026-05-27）。本檔取代 [SPEC_ATOM_V4.md](SPEC_ATOM_V4.md)。
> **位置**：`_AIDocs/`（長期參考知識，rules/core.md 第 3 條）— 非 atom；由 `_AIDocs/_INDEX.md` 索引。
> **歷史**：V4 SPEC 留作對照證物；V5 在 V4 三層 scope 上加機器索引重構、commands→skills 遷移、Codex Companion 去 daemon 化、BM25 全域檢索層。

---

## 1. V5 相對 V4 的變更摘要

V4.1 累積問題（詳見 [memory/v5-overhaul-audit-2026-05.md](../memory/v5-overhaul-audit-2026-05.md)）：

1. **災難級**：`workflow/guardian-crash.log = 114 GB` 無 rotation
2. **架構過時**：26 個 `commands/*.md` 是 legacy 格式（Anthropic 已合 commands → skills）
3. **歸類錯誤**：MCP 7 tool 中 4 個（workflow_signal/status/memory_queue_*）是內部 IPC
4. **過度設計**：16 個 `wg_*.py` + 1640 行 dispatcher、4 套自評重疊、daemon @ 3850/3849 對 30 atoms 殺雞用牛刀
5. **Token 浪費**：session start ≈1100 tok 常駐

V5 4-Wave 解決：

| Wave | Phase | 目標 |
|------|-------|------|
| 1 | P0 / P3a / P4a | log rotation；feedback 24→5；文件層瘦身 |
| 2 | P2 / P4b | hook/MCP 重整（wg_* 16→6 + handlers/）；禁語抽 JSON single source |
| 3 | P3b / P1 / P5a | `_atom_index.json` SoT；commands→skills；全域 BM25 |
| 4 | P5b / P6 | Codex Companion daemon→subprocess；dead code 清理；本 SPEC |

---

## 2. 三層 Scope（沿用 V4）

V4 的三層 scope 機制不變：

| Scope | 用途 | 位置 |
|---|---|---|
| `global` | 跨專案通用知識 | `~/.claude/memory/` |
| `shared` | 專案內全員共享 | `{proj}/.claude/memory/shared/` |
| `role:{name}` | 特定職務組共享 | `{proj}/.claude/memory/roles/{name}/` |
| `personal:{user}` | 個人在該專案的偏好/筆記 | `{proj}/.claude/memory/personal/{user}/`（gitignore） |

詳細 schema / 衝突偵測 / JIT 注入規則：見 [SPEC_ATOM_V4.md §2–§10](SPEC_ATOM_V4.md)。本 SPEC 只記 V5 增量。

### 2.1 Atom 存放擴展（feedback / 失敗模式類，V5+ Session α/β，2026-05-28）

`global` scope 的 atom 物理位置從單根 `memory/` 擴為**多根**：

| 物理位置 | 收錄對象 | 索引 |
|---|---|---|
| `~/.claude/memory/` | 一般全域 atom（decisions / workflow-rules / toolchain ...） | `memory/_atom_index.json` |
| `~/.claude/_AIDocs/Failures/` | title 以 `feedback-` 開頭的 atom + 失敗模式類（如 `cognitive-patterns`） | 同上（單一索引，path 欄記 `_AIDocs/Failures/...`） |

**路由規則**：title slugify 後若 startswith `feedback-` → 自動寫入 `_AIDocs/Failures/`；其他 `_AIDocs/Failures/` 內 atom 需手動建立但走相同索引。

**規則來源（single source of truth）**：
- Python：[`lib/atom_locations.py`](../lib/atom_locations.py) — `FAILURES_DIR` / `FAILURES_REL` / `FEEDBACK_TITLE_PREFIX` / `is_failures_routed_title` / `atom_search_roots` / `iter_atom_files_multi` / `failures_write_target` / `failures_atom_stems`
- JS mirror：[`tools/workflow-guardian-mcp/server.js`](../tools/workflow-guardian-mcp/server.js) — `FAILURES_DIR` / `FAILURES_REL` / `applyFeedbackRouting` / `findAtomFileRecursive` Failures fallback

**多 root 掃描的 caller（V5+ Session β 收尾）**：
- `hooks/wg_atoms.py:parse_memory_index` — 讀 `_atom_index.json` SoT，path 已含 Failures（α）
- `tools/sync-atom-index.py:scan_atom_files` — 預設走 `iter_atom_files_multi()`（β）
- `tools/memory-vector-service/indexer.py:discover_layers` — 注入 `extra:failures` layer + stems filter（β）
- `tools/atom-health-check.py` / `tools/memory-audit.py` — 已於 α 走多根

**Failures 內參考文件過濾**：`_AIDocs/Failures/` 容納非 atom 文件（如 `_INDEX.md` / `README.md`）。caller 用 `failures_atom_stems()` 從 `_atom_index.json` 抽出真正的 atom stems 過濾，避免把參考文件當 atom 索引。

### 2.2 Realm 範疇分區（核心 vs 非核心，V5+ S3，2026-06-03）

`~/.claude/memory/` 的全域 atom 在**每個專案**都被掃描注入。腦內世界 / codex / guardian-dashboard 這類**只在 ~/.claude 內才有用**的記憶，跨到外部專案工作時仍佔 context token——故補上「範疇（realm）」維度。

**realm 與 scope 正交，由 index `path` 前綴推導（不存欄位、不寫 frontmatter、免 heal）：**

| Realm | 判定（index `path`） | 物理位置 | 注入行為 |
|---|---|---|---|
| `core`（預設） | **不**以 `_AIDocs/_atoms/` 開頭 | `memory/{slug}.md`（feedback-* 在 `_AIDocs/Failures/`，屬 core） | 全專案注入（現狀不變） |
| `local` | 以 `_AIDocs/_atoms/` 開頭 | `_AIDocs/_atoms/<domain>/{slug}.md` | **只在 cwd∈~/.claude 注入**；外部專案完全略過 |

- **local atom 仍 `Scope=global`**——realm 與 scope 正交；沿用 feedback-* 同一招（物理在 `_AIDocs/` 下、靠 index `path` 被 `base_dir=CLAUDE_DIR` join 讀出注入），零新管線。`_AIDocs/_atoms/` 與 feedback 的 `_AIDocs/Failures/` 是不同前綴、零衝突。
- **Domain**：`World`（腦內世界）/ `Tools`（外部工具與環境踩坑）/ `MemDev`（記憶系統/Guardian「特定實例」開發踩坑）；未知 domain warn 不擋。
- **注入閘門**：`hooks/handlers/session_start.py` 在**建候選快取處**（非注入迴圈）依 `_is_under_claude_dir(cwd)` 過濾掉 path 落 `_AIDocs/_atoms/` 的候選；外部專案零負擔。compact/resume 複用舊 state 為已知低頻限制。
- **分類器**（`classify_realm`，新 atom + drift sweep 共用）：**安全預設 core，僅高信心判 local**。核心保護清單（`decisions*`/`workflow-*`/`toolchain*`/`feedback-*`/`memory-pipeline-*`/`atom-*`/`preferences`/`cognitive-patterns`）**硬擋**永不 local；詞庫**只用實例專屬名**（腦內世界/world.html/reconcile/gdoc/codex/electron-uia/guardian-dashboard…），**絕不用記憶系統通用詞**（會誤殺核心 atom）；只掃 name+triggers，**絕不靠 `_AIDocs/` 路徑前綴判 local**（feedback-* 就在 _AIDocs 卻是 core）。
- **搬遷工具 `tools/atom-set-realm.py`**：`set <slug> --domain D` / `--to-core`（undo）。為 `_AIDocs/_atoms/` path 的**唯一寫者**（防 reconcile 誤重算翻轉 realm）；**連 `.access.json` sidecar 原子性搬移**（否則 confirmations/usefulness 歸零、晉升飄移）；Scope 保持 global。**不**走 `atom-move`（它會把新根誤判 project 層、改錯 Scope）。
- **MEMORY.md「本地範疇」段**：`sync-memory-index` 把 local atom 抽出主表、依 domain 收進尾段（R4 印象層指標，人在 ~/.claude 仍找得到）。

**規則來源（single source of truth）**：
- Python：[`lib/atom_locations.py`](../lib/atom_locations.py) — `LOCAL_ATOMS_DIR` / `LOCAL_ATOMS_REL` / `LOCAL_REALM_DOMAINS` / `is_local_realm_path` / `classify_realm` / `local_write_target` / `local_realm_domain` / `atom_index_row_kind`
- JS mirror：[`tools/workflow-guardian-mcp/server.js`](../tools/workflow-guardian-mcp/server.js) — `LOCAL_ATOMS_*` 常數 / `classifyRealm` / `applyLocalRouting` / `findAtomFileRecursive(LOCAL_ATOMS_DIR)` find-fallback

**守門**：`lib/verify/verify_atom_io_equivalence.py` test_14（路徑/realm 常數 py↔js parity）+ test_15（local routing，Scope 仍 global）+ test_16（分類器零誤判：核心保護清單全 core）+ test_17（classifier py↔js parity）；`lib/verify/verify_realm_injection_gate.py`（3 gate 單測）；`tools/verify/verify_memory_index_caption_preserve.py`（本地範疇段 render + caption preserve）。詳見 atom `realm-範疇分區機制-v5`。

---

## 3. Atom Index — JSON SoT（V5 P3b，2026-05-27）

V4 用 `_ATOM_INDEX.md` table 為機器源，但 parser 對格式脆性高（commit e11b800 修空行污染）。
V5 引入 `_atom_index.json` 為唯一機器源。

### 3.1 Schema（v1.0，凍結）

```json
{
  "version": "1.0",
  "atoms": [
    {
      "name": "decisions-architecture",
      "path": "memory/decisions-architecture.md",
      "triggers": ["架構", "決策", "architecture"],
      "scope": "global",
      "last_used": "2026-05-27"
    }
  ]
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `version` | ✓ | 目前 `"1.0"` |
| `atoms[].name` | ✓ | atom slug（與檔名一致，不含 .md） |
| `atoms[].path` | ✓ | 相對 `~/.claude` 的 POSIX 路徑 |
| `atoms[].triggers` | ✓ | trigger 字串陣列；每項 ≤ 30 字 |
| `atoms[].scope` | ✓ | `global` / `shared` / `role:*` / `personal:*` |
| `atoms[].last_used` | optional | ISO 日期；計數類欄位仍由 `<atom>.access.json` 為主 |

新增欄位（如 `confidence` / `audience`）需 bump `SCHEMA_VERSION` 為 `1.1` 並同步 `lib/atom_index_json.SCHEMA_VERSION`。

### 3.2 對應實作

- **lib/atom_index_json.py** — `load_atom_index_json` / `save_atom_index_json` / `upsert_atom` / `delete_atom` / `regenerate_atom_index_md` / `parse_legacy_atom_index_md` / `migrate_md_to_json` / `validate_index`
- **hooks/wg_atoms.py `parse_memory_index`** — 優先讀 JSON，fallback `_ATOM_INDEX.md` → `MEMORY.md`
- **hooks/wg_episodic.py `_update_memory_index`** — 改走 `upsert_atom` funnel
- **lib/atom_io.py `write_index`** — 改走 `upsert_atom` funnel
- **tools/workflow-guardian-mcp/server.js `appendToIndex`** — spawn `lib.atom_io_cli action=write_index` → funnel
- **tools/sync-atom-index.py / sync-memory-index.py** — V5 P6c 改讀 JSON SoT
- **.git/hooks/pre-commit** — V5 P3b 重啟：JSON schema validate + MD mirror drift check

### 3.3 `_ATOM_INDEX.md` 退役狀態

`_ATOM_INDEX.md` 仍存在但改為**自動生成的人類可讀 mirror**。
- 寫入點：`regenerate_atom_index_md(mem_dir)` 在每次 `upsert_atom` 後同步重生
- 讀取點：僅 fallback 用（JSON 缺失時的 backup parser）
- 不再被 MCP / hooks 主路徑讀取

### 3.4 元資料外科編輯 `edit_metadata`（2026-06-02）

atom 已建立後要動 frontmatter 的 `Trigger`/`Related`/`Tags`，不重建知識區的合法入口。實作 [`lib/atom_io.py:edit_metadata`](../lib/atom_io.py)，MCP 經 `atom_edit_meta` 暴露（§9 註）。

| 契約項 | 規範 |
|---|---|
| 可改欄位 | 僅 `triggers` / `related` / `tags`（None 表不動該欄；至少傳一個）。知識區、信心 tag、計數類欄位皆不在範圍 |
| byte-stable | per-label regex 只就地替換目標那一行（`count=1`），其餘 byte 原樣保留（含既有 EOL / BOM）；找不到欄位行 → 不靜默 no-op，回 error |
| SoT 順序 | triggers 變更時 **先寫 `_atom_index.json`（機器唯一源）**，成功才續寫 frontmatter（衍生）；index 領先失敗即中止、不寫 frontmatter，避免不可復原 drift。部分失敗由 `tools/sync-atom-index.py --fix` 冪等復原 |
| 走既有 funnel | triggers 段複用 `write_index`、frontmatter 段複用 `write_raw(op="meta-edit")`，皆入 `_meta/atom_io_audit.jsonl` |
| source 規範 | 須在 `VALID_SOURCES`（預設 `mcp`）|

取代：被 PreToolUse guard 擋的「直 Edit/Write atom .md」、以及會重建整檔知識區的「`atom_write` mode=replace」。

---

## 4. Commands → Skills 遷移（V5 P1，2026-05-27）

Anthropic 官方明文「Custom commands have been merged into skills」。
V5 把 22+ 個 `commands/*.md` 遷到 `.claude/skills/{name}/SKILL.md` 結構。

### 4.1 Skill frontmatter 規範

```yaml
---
name: <kebab-case slug>
description: <50 字內 Claude 自動觸發判斷用，必填>
when_to_use: <額外觸發語境，選填>
disable-model-invocation: true   # 有副作用的工具（commit/deploy）設此
user-invocable: false             # 純背景知識不出現在 / menu
allowed-tools: Read Grep          # 自動授權避免問
context: fork                     # 大任務跑 subagent 不污染主 context
paths: "memory/**/*.md"           # glob 命中才 auto-load
---
```

### 4.2 V5 全域 20 個 skills

| 處理方式 | skills（共 20）|
|---------|-------|
| **直接遷移**（13） | atom-debug, browse-sprites, conflict, conflict-review, consciousness-stream, extract, fix-escalation, generate-episodic, harvest, journal, read-project, upgrade, vector |
| **全域保留**（4） | codex-companion, continue, handoff, init-roles |
| **合 1 個 /memory**（5→1） | memory-health / memory-peek / memory-undo / memory-review / memory-session-score → `skills/memory/SKILL.md` 用 `$0` 取 subcmd |
| **改名為 debug 工具**（1） | changelog-roll → `changelog-debug`（避免與 PostToolUse hook 自動觸發混淆） |
| **後續新增（非遷移）**（1） | skill-creator（meta-skill：寫/改/審 skill；2026-05-29 經 MR !3 合入） |

### 4.3 已刪除（與內建衝突）

- `resume`（CC 內建 --resume）
- `init-project`（內建 /init 已存在）
- `svn-update` / `unity-yaml`（下沉到專案層）
- `changelog-roll`（改名 changelog-debug）

`commands/` 22 個 legacy `.md` **已於 2026-05-27 Wave 4 收尾刪除**。原訂 7 天緩衝（到 2026-06-03）經對拍腳本驗證後提前廢止：13 直遷 commands vs skills 字元數 100% identical（純 frontmatter 包裝差異）、3 全域保留 identical、5 memory 子命令全部在統一 skill 內提及、唯一差異的 codex-companion 是 commands/ 為過時版本（保留反為 noise）。緩衝期當保險而非工程必要的設計被推翻。

---

## 5. Hook 架構（V5 6+2 主模組，2026-05-27）

V4.1 的 16 個 `wg_*.py` + 2651 行 `workflow-guardian.py` dispatcher 整併為：

### 5.1 主模組（6）

| 模組 | 職責 |
|------|------|
| `wg_core.py` | 路徑唯一真相 + config/state IO + log rotation + PreToolUse guards |
| `wg_atoms.py` | atom index 解析 + trigger 匹配 + BM25 + ACT-R + vector search + atom 晉升 |
| `wg_extraction.py` | per-turn 萃取 + worker 管理 + failure 偵測 + hot cache + user-extract + content classify |
| `wg_episodic.py` | episodic 生成 + 衝突偵測 + 品質回饋 |
| `wg_evasion.py` | Evasion Guard + Test-Fail Gate + 4 套自評整合（含舊 wg_session_evaluator / wg_iteration 自評） |
| `wg_docdrift.py` | src → _AIDocs 映射 drift 偵測 |

### 5.2 Shim（1）

| 模組 | 用途 |
|------|------|
| `wg_roles.py` | V4 sub-layer 探勘的 thin wrapper（保留） |

> Wave 5 Session 6 砍 `wg_atom_observation.py`（REG-005 觀察任務 2026-04 結束 + 零活躍引用）。

### 5.3 獨立保留

- `wisdom_engine.py` — 反思引擎 + Fix Escalation（領域單一）
- `codex_companion.py` — V5 P5b 重寫為 subprocess 模型（§7）
- `extract-worker.py` — SessionEnd 萃取子程序（共用 `lib/ollama_extract_core.py`）
- `quick-extract.py` — Stop async 快篩

### 5.4 Dispatcher / Handlers

- `dispatcher.py`（~75 行）— 純路由，無業務邏輯
- `handlers/_shared.py` — handler 共用 helper
- `handlers/{session_start,user_prompt_submit,pre_tool_use,post_tool_use,stop,session_end,pre_compact,post_compact,post_tool_batch,notification}.py` — event handler 各一檔（2026-06-01 選配 #4 加 `post_compact`/`post_tool_batch`：壓縮後 atom 內文重注入）
- `workflow-guardian.py` — 20 行薄 shim（5 行可執行 code）轉發到 `dispatcher.main()`

詳細演化過程：[DevHistory/v4-archive/README.md](DevHistory/v4-archive/README.md)。

---

## 6. BM25 全域檢索層（V5 P5a，2026-05-27）

V4 全域 ~30 atoms 用 Vector Service @ port 3849（LanceDB + Ollama）做語義檢索 — 殺雞用牛刀。
V5 引入 in-memory BM25 替代全域層，**保留 vector 給專案層**（atom 數可上百）。

### 6.1 實作

- **hooks/wg_atoms.py** — `bm25_match` / `_bm25_score` / `_bm25_tokenize`（手刻 ~80 行）
  - ASCII word + 中文 char-bigram tokenization
  - BM25 參數：k1=1.2, b=0.75
- **hooks/handlers/user_prompt_submit.py** — 注入流程：
  1. trigger match
  2. BM25 全域層（≤2 trigger 命中時觸發；min_score=1.0；top_k=3）
  3. Vector fallback（僅當 BM25 + trigger 雙 0 命中 或 `vector_search.global_layer ≠ bm25`）
- **workflow/config.json** — `vector_search.global_layer: "bm25"` + `bm25_min_score: 1.0` + `bm25_top_k: 3`

### 6.2 Vector Service 角色（保留）

- **全域層**：BM25 替代（17 atoms 規模）
- **專案層**：仍走 vector（避免上百 atoms 規模的 BM25 效能退化）
- **Episodic search**：仍走 vector（cross-session 知識）
- **Cross-session dedup / 衝突偵測**：仍走 vector
- **Stale chunk 清理**：`tools/memory-vector-service/indexer.py` 加 `cleanup_stale_chunks` + CLI flag `--cleanup-stale`

---

## 7. Codex Companion — Daemon → Subprocess（V5 P5b，2026-05-27）

V4 的 Codex Companion 用 HTTP daemon @ port 3850 管理 per-session state 與 assessment 工作。
V5 改為 in-process state + spawn `tools/codex-companion/audit.py` 短命子程序。

### 7.1 新架構

```
Hook trigger (PostToolUse / Stop)
  ↓
hooks/codex_companion.py:
  - companion_state.append_event / increment_turn  (in-process file IO)
  - _detect_checkpoint(tool, file, config)        (本檔直接判斷)
  - heuristics.triggered_results                  (本檔直接呼叫)
  - scorer.compute_turn_score                     (本檔直接呼叫)
  - cap check via state.assessments_requested
  ↓ (passes gates)
  - state.record_checkpoint  (increments counter, source-of-cap)
  - subprocess.Popen([python audit.py], stdin=PIPE, detached)
    → audit.py reads turn_data JSON from stdin
    → assessor.run_assessment(...) → codex CLI
    → state.write_assessment → companion-assessment-{sid}-t{N}-{type}.json
```

### 7.2 變更檔案

| 檔案 | 變更 |
|------|------|
| `tools/codex-companion/audit.py` | **新增**：one-shot subprocess（stdin JSON → assessor → state.write_assessment） |
| `tools/codex-companion/service.py` | **刪除**：HTTP daemon 不再需要 |
| `hooks/codex_companion.py` | **重寫**：移除 HTTP client（urllib / socket / _http_post / _ensure_service）；改為直接 `import state as companion_state` + `_spawn_audit_subprocess` |
| `workflow/config.json` | 移除 `codex_companion.service_port`；新增 `codex_companion.subprocess_timeout: 90` |
| `skills/codex-companion/SKILL.md` | 移除 service.py 啟動指令；只切換 config flag |

### 7.3 保留的設計

- `tools/codex-companion/{assessor,heuristics,prompts,scorer,state}.py` — 純函式/邏輯模組，全部保留
- `companion-state-{sid}.json` / `companion-assessment-{sid}-t*.json` / `companion-metrics-{sid}.json` — 檔案 schema 不變
- Silent Advisory Mode（`silent_advisory: true` / `max_inject_severity: "high"`）— 邏輯不變
- Score Gate / Dedup / Max Audits Cap — 邏輯不變，計數源改為 `state.assessments_requested`（subprocess 失敗保守 under-runs）

### 7.4 行為差異

| 項目 | V4 (daemon) | V5 (subprocess) |
|------|-------------|-----------------|
| port 3850 | 監聽中 | 無人聽 |
| `companion.pid` | service.py 維護 | 不存在 |
| Assessment 延遲 | ~1ms HTTP roundtrip → thread queue | ~10–50ms subprocess spawn |
| 失敗模式 | daemon crash 影響全 session | 單 turn 子程序失敗只影響該 turn |
| Log 路徑 | `Logs/codex-companion.log` (daemon stderr) | `Logs/codex-audit.log` (per-subprocess stderr) |

---

## 8. 禁語清單抽 JSON（V5 P4b，2026-05-26）

V4 禁語清單同時硬編碼在 `IDENTITY.md` 與 `hooks/wg_evasion.py`，drift 風險。
V5 抽出為 `memory/_meta/forbidden-phrases.json` 為 single source；`IDENTITY.md` 與 `wg_evasion.py` 都讀此 JSON。

---

## 9. MCP server.js 砍 4 內部 tool（V5 P2，2026-05-26）

V4 暴露 7 個 tool：3 個合理（atom_write / atom_move / atom_promote）+ 4 個內部 IPC（workflow_signal / workflow_status / memory_queue_add / memory_queue_flush）。
V5 砍 4 個 IPC tool，改由 Stop gate 自動偵測（hook 內化）。後續（2026-06-02）加回 `atom_edit_meta`（元資料外科編輯，§3.4）→ 現役 4 個業務 tool。改全域 server.js 須重啟 MCP server 生效。

---

## 10. V5 期間 disable / 重啟清單

| 機制 | 狀態 | 備註 |
|------|------|------|
| `.git/hooks/pre-commit` | ✓ Wave 3 重啟（JSON schema check） | 取代脆性的 _ATOM_INDEX.md table parser |
| Vector Service @ 3849 | ✓ 保留 | 專案層仍用 vector；全域層改 BM25 |
| Codex Companion daemon @ 3850 | ✗ Wave 4 P5b 廢止 | 改 subprocess（本 SPEC §7） |
| legacy commands/ 22 檔 | ✓ 2026-05-27 已刪除（Wave 4 收尾） | 對拍 100% 通過後提前廢止緩衝期 |

---

## 11. 知識區 block 渲染（表格 / 程式碼 fence，2026-05-29）

`## 知識` 區預設逐條加 `- ` bullet。V5+ 起 `atom_write` 的 `knowledge` 陣列中，**單一元素去左空白後以 `|`（markdown 表格）或三反引號（程式碼 fence）開頭者，整段原樣輸出、不加 bullet、前後自動補空行**（GFM 渲染需要）；其餘元素（含多行巢狀 bullet）維持「首行加 `- `」原行為。

- **用法**：表格/程式碼當「獨立 knowledge 元素」傳入；引言句放前一個元素。
- **雙路徑單一邏輯**：`lib/atom_spec.py:render_knowledge_lines`（hooks/tools 經 `atom_io`）與 `tools/workflow-guardian-mcp/server.js:renderKnowledgeLines`（MCP 經 `buildAtomContent` / append）須 byte-identical。
- **create + append 皆 block-aware**；append 對表格/fence 開頭自動補一空行隔開既有知識。
- **守門**：`lib/verify/verify_atom_io_equivalence.py` test_11/12（py funnel）+ test_13（py↔js byte-parity，spawn node 經 `module.exports` 對拍）。
- **下游零衝擊**：conflict-detector 只抽 `- ` 行（表格列被忽略，非誤判）、注入剝離整段保留、write-gate 不檢行格式、逐行 `[固]` parse 不匹配表格列。
- **注意**：server.js 改動需重啟 MCP server 進程才生效；Python funnel（hooks/tools）下次呼叫即生效。

## 12. 注入→使用→結果 閉環效用歸因（Phase 1+2，#1/#2，2026-06-01）

讓記憶觸及 sub-agent，並用「真實效用」而非「曝光次數」校準信心。設計細節 SoT = 程式碼；本節為導覽。

### 12.1 Sub-agent 記憶注入（Phase 1，#1）
- sub-agent（`Agent`/`Task`）開全新 context、不觸發 `UserPromptSubmit`。唯一 parent→child 通道是工具 prompt 字串。
- `PreToolUse` 對 Agent/Task 回 **`updatedInput`**（非 plan 草稿誤記的 `modifiedInput`；CC 版本相依，已 probe 實證採納）prepend 緊湊注入 blob（`wg_atoms.build_injection_blob`，top-k≤3，marker `[WG:SubagentMemory] ... atoms=a,b,c`）。
- `PostToolUse` 從注入後 `tool_response.prompt` 無狀態回推注入清單 + 擷取輸出摘要 → `state["subagent_injections"]`（`post_tool_use._record_subagent_injection`）。

### 12.2 效用閉環 (α,β)（Phase 2，#2）
- **遙測 schema v3**（`<atom>.access.json`，`lib/atom_access.py` funnel）：加 `useful_hits`(α)/`used_fail`(β)，Laplace prior 1，v2→v3 冪等 migration。α/β 只存兩個 scalar、**不寫進 .md**（零索引膨脹，守 token 紅線）。
- **注入記錄**：`state["turn_injected"]`（per-turn 覆寫，補 session 累積 `injected_atoms` 的 per-turn delta 遺失）+ Phase 1 `subagent_injections`。
- **use 偵測（零成本詞彙重疊）**：`wg_atoms.detect_atom_use` 取 atom 稀有 token（識別碼/路徑/API + CJK bigram，去停用詞）與本 turn assistant 活動（`wg_evasion.get_current_turn_text`）求 containment/Jaccard；共享≥`rare_token_min` 或 containment≥`lexical_overlap_min` → used。不確定（差一）時才用 Ollama embedding cosine tiebreak（fail-safe、偶發）。
- **success 偵測（3 值）**：`stop._detect_turn_outcome` 複用 `failing_tests`/`claims_completion`/`evasion_flag`/`wisdom_retry_count`。+1=完成宣告且乾淨；0=error/糾正/retry/evasion；**其餘 unknown=no-op（防雜訊污染關鍵守則）**。
- **更新規則**：`stop._attribute_usefulness` 對 used 且 outcome 決定性者 → `record_usefulness`（success α++/fail β++，走 funnel）；per-turn 一次性（`turn_seq` 守門）。
- **慢衰減**：`_self_iterate_atoms`（SessionEnd）α←1+λ(α−1); β←1+λ(β−1)，λ=0.97，重啟冷啟動。
- **晉升閘改寫**：晉升 = 真實 Confirmations 主軌 **OR 效用 Wilson 下界**（升≥`promote_lb`=0.6 且 n≥`min_n`=3，z=1.96）；**ReadHits 退出晉升、降為純曝光計數**（取代 Phase 0 過渡）。降級候選（Wilson 下界≤`demote_lb`=0.35,n≥3）列 staging 報告供裁決、不自動降。
- **py↔js 鏡像**：`wilson_lower_bound`/`usefulness_*`（`lib/atom_access.py`）↔ `wilsonLowerBound`/`usefulnessStats`（`server.js toolAtomPromote`），`SYNC:` 註解 + `memory/decisions.md` 對齊。**改 server.js 後須重啟 MCP server**。
- **旋鈕**：`workflow/config.json` `usefulness.{lexical_overlap_min,rare_token_min,wilson_z,promote_lb,demote_lb,min_n,decay_lambda,embedding_tiebreak}`。
- **守門**：`lib/verify/verify_usefulness_access_phase2.py`（18）+ `hooks/verify/verify_usefulness_loop_phase2.py`（21）+ `verify_promotion_gate_phase0.py`（效用驅動）+ `verify_subagent_injection_phase1.py`（21）。

## 13. 變更紀錄

| 日期 | 版本 | 變更 |
|---|---|---|
| 2026-06-03 | V5+ S1–S3 | **Realm 範疇分區（§2.2）**：core vs local 由 index path 前綴推導（不存欄位）；local 住 `_AIDocs/_atoms/<domain>/`、scope 仍 global、只在 cwd∈~/.claude 注入。注入閘門（session_start）+ 分類器（`classify_realm` 安全預設 core+核心保護硬擋）+ 搬遷工具 `atom-set-realm.py`（sidecar 原子搬、`_atoms/` path 唯一寫者）+ 8 顆既有 local atom 遷移 + MEMORY.md「本地範疇」段 + py↔js parity（test_14–17）+ `verify_realm_injection_gate.py` |
| 2026-06-02 | V5+ | `edit_metadata` 元資料外科編輯入口（§3.4）+ MCP `atom_edit_meta`；memory-audit 晉升建議改對齊線上 usefulness Wilson 閘；atom-health-check 計數改讀 `.access.json` sidecar；funnel 寫入紀律延伸（health-check / sync-atom-index 裸 write_text → write_raw） |
| 2026-06-01 | V5+ #1/#2 | Sub-agent 記憶注入（Phase 1）+ 注入→使用→結果 (α,β) 閉環效用歸因（Phase 2）；晉升改 Confirmations OR 效用 Wilson 下界、ReadHits 降純曝光 |
| 2026-05-29 | V5+ | 知識區 block 渲染（表格/fence 原樣輸出）；py/js create+append block-aware + py↔js 對拍測試 + server.js module.exports |
| 2026-05-27 | V5 GA candidate | Wave 4 完成：P5b / P6 / SPEC_ATOM_V5.md 定稿 |
| 2026-05-27 | V5 Wave 3 | P3b _atom_index.json SoT + P1 commands→skills + P5a BM25 |
| 2026-05-26 | V5 Wave 2 | P2 hook/MCP 重整 + P4b 禁語 JSON |
| 2026-05-26 | V5 Wave 1 | P0 log rotation + P3a feedback 24→5 + P4a 文件層瘦身 |
| 2026-04-15 | V4 SPEC freeze | 三層 scope 定稿（[SPEC_ATOM_V4.md](SPEC_ATOM_V4.md)） |
