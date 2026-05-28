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

### 4.2 V5 全域 19 個 skills

| 處理方式 | skills（共 19）|
|---------|-------|
| **直接遷移**（13） | atom-debug, browse-sprites, conflict, conflict-review, consciousness-stream, extract, fix-escalation, generate-episodic, harvest, journal, read-project, upgrade, vector |
| **全域保留**（4） | codex-companion, continue, handoff, init-roles |
| **合 1 個 /memory**（5→1） | memory-health / memory-peek / memory-undo / memory-review / memory-session-score → `skills/memory/SKILL.md` 用 `$0` 取 subcmd |
| **改名為 debug 工具**（1） | changelog-roll → `changelog-debug`（避免與 PostToolUse hook 自動觸發混淆） |

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

### 5.2 Shim（2）

| 模組 | 用途 |
|------|------|
| `wg_roles.py` | V4 sub-layer 探勘的 thin wrapper（保留） |
| `wg_atom_observation.py` | REG-005 觀察採樣（任務已結束，flag-gated，零開銷） |

### 5.3 獨立保留

- `wisdom_engine.py` — 反思引擎 + Fix Escalation（領域單一）
- `codex_companion.py` — V5 P5b 重寫為 subprocess 模型（§7）
- `extract-worker.py` — SessionEnd 萃取子程序（共用 `lib/ollama_extract_core.py`）
- `quick-extract.py` — Stop async 快篩

### 5.4 Dispatcher / Handlers

- `dispatcher.py`（~75 行）— 純路由，無業務邏輯
- `handlers/_shared.py` — handler 共用 helper
- `handlers/{session_start,user_prompt_submit,pre_tool_use,post_tool_use,stop,session_end,pre_compact}.py` — 7 個 event handler 各一檔
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
V5 砍 4 個 IPC tool，改由 Stop gate 自動偵測（hook 內化）。

---

## 10. V5 期間 disable / 重啟清單

| 機制 | 狀態 | 備註 |
|------|------|------|
| `.git/hooks/pre-commit` | ✓ Wave 3 重啟（JSON schema check） | 取代脆性的 _ATOM_INDEX.md table parser |
| Vector Service @ 3849 | ✓ 保留 | 專案層仍用 vector；全域層改 BM25 |
| Codex Companion daemon @ 3850 | ✗ Wave 4 P5b 廢止 | 改 subprocess（本 SPEC §7） |
| legacy commands/ 22 檔 | ✓ 2026-05-27 已刪除（Wave 4 收尾） | 對拍 100% 通過後提前廢止緩衝期 |

---

## 11. 變更紀錄

| 日期 | 版本 | 變更 |
|---|---|---|
| 2026-05-27 | V5 GA candidate | Wave 4 完成：P5b / P6 / SPEC_ATOM_V5.md 定稿 |
| 2026-05-27 | V5 Wave 3 | P3b _atom_index.json SoT + P1 commands→skills + P5a BM25 |
| 2026-05-26 | V5 Wave 2 | P2 hook/MCP 重整 + P4b 禁語 JSON |
| 2026-05-26 | V5 Wave 1 | P0 log rotation + P3a feedback 24→5 + P4a 文件層瘦身 |
| 2026-04-15 | V4 SPEC freeze | 三層 scope 定稿（[SPEC_ATOM_V4.md](SPEC_ATOM_V4.md)） |
