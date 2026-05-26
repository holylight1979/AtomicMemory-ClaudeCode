# V5 原子記憶系統升版計畫

> 對齊 Anthropic Claude Code 最新原生機制（skills / deferred MCP / plugin packaging / prompt cache），全面檢修 V4.1 設計過載與災難級災情。
> 設計重點：**4 波平行執行** + **prompt cache 最大化** + **分 session handoff 不失憶**。

---

## Context（為什麼要做這次升版）

V4.1 原子記憶系統累積到 2026-05 出現五類問題（詳見審計 atom [memory/v5-overhaul-audit-2026-05.md](../memory/v5-overhaul-audit-2026-05.md)）：

1. **災難級**：`workflow/guardian-crash.log = 114 GB` 無 rotation，吃滿磁碟
2. **架構過時**：Anthropic 官方明文「Custom commands have been merged into skills」（[code.claude.com/docs/en/skills](https://code.claude.com/docs/en/skills)），使用者 26 個 `commands/*.md` 是 legacy 格式，缺三大新能力（auto-invocation by description、body 按需載入、subagent 執行）
3. **歸類錯誤**：MCP 7 tool 中 4 個（workflow_signal/status/memory_queue_*）是內部 IPC 不該暴露給 AI
4. **過度設計**：16 個 wg_*.py + 1640 行 dispatcher、4 套自我評估互相重疊、Codex daemon @ 3850 / Vector daemon @ 3849 對全域層 30 atoms 殺雞用牛刀
5. **Token 浪費**：session start ≈1100 tok 常駐（反退避契約與 wg_evasion.py 重複防呆、atom 索引重複等）

**V5 目標**：對齊原生 → 災情清零 → 架構瘦身 → 不失憶接力。

---

## 設計原則

| 原則 | 落實方式 |
|------|---------|
| **對齊原生** | commands → skills（不重造輪子）；MCP 只暴露多步驟業務動作；deferred tool 機制天然省 context |
| **災情先解** | P0 緊急救火與後續架構解耦，可獨立完成 |
| **平行最大化** | 經實際檔案衝突分析後的 4 波次設計（見下） |
| **Cache 友善** | 每 session 內部操作順序鎖定「先讀全部 stable context → 集中改動 → 最後寫 atom + handoff」，避免 mid-session 動 @import 鏈 |
| **不失憶** | 每 phase 結束 `atom_write mode=append` 追記 + `_staging/next-phase.md` + 上 GIT；下個 session 開頭 `/continue` 自動接力 |
| **可回滾** | 每 phase 對應一個 commit；走砸了 `git revert` 單一 commit 即可 |

---

## V5 升版期間「全域 disable 策略」

> 使用者 2026-05-26 授權：升版期間若有「會嚴重擋作業、產生多餘 token 耗用、且真的太多餘」的機制，**全部先關掉**，準備「正確安置位置 + 更好作用時機」，到適當的波次再塞回（最晚 GA 後全面啟動 + 驗證）。**盡量一次到位**。

### 開工日（2026-05-26）已 disable 的機制

| 機制 | disable 動作 | 原因 | 重啟時機 |
|------|--------------|------|---------|
| `.git/hooks/pre-commit`（atom-index drift check）| `mv pre-commit pre-commit.disabled-during-v5` | parser 對動態變化的 _ATOM_INDEX 反覆誤報，每次 commit 都卡關 | Wave 3 P3b 完成（_ATOM_INDEX → JSON）後重寫成 JSON schema check，再 rename 啟用 |

### V5 期間禁用清單（持續更新）

Wave 推進中若再發現多餘機制，在此追記。每項記錄：**機制名 / disable 方式 / 原因 / 重啟時機**。

### GA 前必跑「重啟驗證 sweep」

GA 收尾必須跑一遍：
- 把所有 `*.disabled-during-v5` 改回 active 對應檔
- 確認 hook chain 全綠
- 跑一個完整對話驗證 trigger / evasion / Stop gate 全功能

---

## 修正後的 4-Wave 執行計畫

> Plan agent 實地驗證後修正：原本「P0+P3+P4 並行」設計有隱性衝突——`wg_atoms.py` / `workflow-guardian.py` 是三方爭用熱點，P2（hook/MCP 重整）必須先打基線，後續才能放心並行。

```
┌─ Wave 1（純並行，~1 session）─────────────────────────┐
│  P0  log rotation                hooks/wg_core.py    │
│  P3a feedback 24→5 atom 整併      memory/feedback/   │
│  P4a 文件層瘦身（不動 hook）       IDENTITY/USER/CLAUDE/MEMORY.md │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Wave 2（序列必須，~1-2 sessions）────────────────────┐
│  P2  hook/MCP 重整（共用底座）+ P4b wg_evasion 禁語同步 │
│       — 改造 wg_atoms / wg_intent / workflow-guardian   │
│       — 砍 MCP 4 內部 tool                              │
│       — 4 套自評整合（保留 evasion + Codex judge）       │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Wave 3（基於 P2 新基線並行，~1-2 sessions）─────────┐
│  P3b _ATOM_INDEX.md → JSON + parser 改寫                │
│  P1  commands → skills 遷移 + config.json docdrift     │
│  P5a Vector Service 精簡（全域層 in-memory BM25）        │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Wave 4（單獨，~1 session）─────────────────────────┐
│  P5b Codex Companion daemon → hook + subprocess       │
│       — 與 P5a 都動 dispatcher，必須序列                │
└──────────────────────────────────────────────────────┘
                          │
                          ▼
┌─ Wave 5 / GA Cleanup（單獨，~1 session）─────────────┐
│  P6 殘舊全清 + 升級檔案歸檔 + disable 機制重啟         │
│       — 詳見 P6 區塊                                    │
└──────────────────────────────────────────────────────┘
```

**預估 session 數**：4-6 session（純序列要 6-9 session，省 30-40%）。

---

## Phase 詳細實作

### Wave 1 — P0 緊急救火

**目標**：消除 114 GB 磁碟黑洞，建立 log rotation 機制。

**改動檔案**：
- `c:/Users/holylight/.claude/hooks/wg_core.py` — 加 `rotate_log_if_oversized(path, max_mb=10)` 函式
- `c:/Users/holylight/.claude/hooks/workflow-guardian.py` — SessionStart handler 開頭呼叫 rotation
- **不動**：`tools/codex-companion/service.py` 既有 log 路徑（避免破壞 daemon）

**步驟**：
1. `truncate -s 0 c:/Users/holylight/.claude/workflow/guardian-crash.log`（立刻釋放 114 GB）
2. `wg_core.py` 加 rotation：>10 MB 自動 mv 為 `*.log.1`，超過 5 份就刪最舊
3. SessionStart hook 呼叫一次（每 session 只跑一次，<10ms）
4. **驗證**：`du -sh c:/Users/holylight/.claude/workflow/`（應 <500 MB）；新開 session 確認 hook 正常

**回滾**：刪掉 `rotate_log_if_oversized` 函式 + dispatcher 呼叫即可，crash.log 已 truncate 不可逆但本來就無價值。

---

### Wave 1 — P3a feedback atom 整併

**目標**：24 個 feedback-* atom → 5 主題 atom，遵守 `feedback-pointer-atom` 規則。

**改動檔案**：
- `c:/Users/holylight/.claude/memory/feedback/*.md` × 24（讀 → 主題分群 → 新建 5 → archive 舊的到 `_distant/2026_05_consolidation/`）
- `c:/Users/holylight/.claude/memory/MEMORY.md`（更新索引）
- **不動 hook**：純記憶層操作

**5 主題分群（暫定，實際依讀檔調整）**：
| 新主題 atom | 合併來源（部分例） |
|------------|------------------|
| `feedback-workflow` | feedback-clean-before-build, feedback-handoff-self-sufficient, feedback-fix-escalation |
| `feedback-code-quality` | feedback-pre-completion-test-discipline, feedback-end-to-end-smoke, feedback-research-first |
| `feedback-tooling` | feedback-bg-subprocess-stderr, feedback-codex-collaboration, feedback-codex-companion-model, feedback-global-install |
| `feedback-memory-system` | feedback-memory-path, feedback-pointer-atom, feedback-scope-sensitive-values |
| `feedback-discipline` | feedback-fix-on-discovery, feedback-no-outsource-rigor, feedback-precedent-drift-excuse, feedback-decision-no-tech-menu |

**驗證**：grep `feedback-` 在 hooks/、tools/、_AIDocs/ 確認無人 hardcode 舊 atom 名；不行就保留 alias atom（內容指向新名）。

---

### Wave 1 — P4a 文件層瘦身（不動 hook）

**目標**：壓縮 session start 注入從 ≈1100 → ≈500 tok，但**保留** `wg_evasion.py` 禁語清單不變（避免破壞防呆，留到 Wave 2 同步）。

**改動檔案**：
- `c:/Users/holylight/.claude/IDENTITY.md` — 壓縮「反退避契約」說明文字（保留「禁語清單」原文，因為 wg_evasion.py 還沒同步）；壓縮「核心/程式行為準則」抽象描述
- `c:/Users/holylight/.claude/USER.md` — 「縮寫指令」改為 `[[preferences]]` 連結
- `c:/Users/holylight/.claude/CLAUDE.md` — 刪「規則」section 註解（已 @import rules/core.md）
- `c:/Users/holylight/.claude/memory/MEMORY.md` — 改為一行說明 + 知識庫表，刪重複 atom 列表
- **不動**：`hooks/wg_evasion.py`、`rules/core.md`、`memory/_ATOM_INDEX.md`

**驗證**：開新 session 看 system prompt 字數對照（用 /context 或讀 transcript），目標 500 tok 範圍。

---

### Wave 2 — P2 hook/MCP 重整 + P4b wg_evasion 同步

**這是最重的 phase，建議單獨 1 session（可拆 2 session：P2 hook + P2 MCP）。**

**目標**：建立 V5 hook 基線——16 → 5 模組、dispatcher 拆 dispatcher/handlers、MCP 砍 4 內部 tool、4 套自評整合。

**改動檔案**：
- `hooks/wg_*.py` × 16 — 合併方案：
  | 保留 | 吸收 |
  |------|------|
  | `wg_core.py` | + `wg_paths.py`（路徑工具）+ `wg_pretool_guards.py`（小） |
  | `wg_atoms.py` | + `wg_intent.py` 的 trigger 部分 |
  | `wg_extraction.py` | + `wg_user_extract.py` + `wg_hot_cache.py` |
  | `wg_episodic.py` | （獨立保留）|
  | `wg_evasion.py` | + `wg_session_evaluator.py` + `wg_iteration.py` 中與評估重疊部分 |
  | **刪除** | `wg_atom_observation.py`（REG-005 觀察用，任務已結束）、`wg_roles.py`（單人環境）、`wg_content_classify.py`（合入 wg_extraction） |
  | **保留獨立** | `wisdom_engine.py`、`wg_docdrift.py`（領域單一）|
- `hooks/workflow-guardian.py` — 拆為 `dispatcher.py`（純路由 <400 行）+ `handlers.py`（8 個 event handler，按 event 分節）
- `tools/workflow-guardian-mcp/server.js` — 砍 `workflow_signal` / `workflow_status` / `memory_queue_add` / `memory_queue_flush` 4 tool；改由 hook 自動執行 + 注入到 UPS context
- `hooks/wg_evasion.py` 禁語清單 — 與 IDENTITY.md 互為 single source（建議：禁語清單從 IDENTITY.md 抽到 `memory/_meta/forbidden-phrases.json`，IDENTITY 與 wg_evasion 都讀此 JSON）
- `workflow/config.json` — 更新 docdrift `hooks/wg_*.py` 映射

**驗證**：
- pytest（如有）/ 跑一個對話確認 trigger 注入、evasion 攔截、Stop 閘門都正常
- `/atom-debug on` 看日誌確認新模組路徑正確

**回滾**：保留 `hooks/_v4_archive/` 子目錄存舊 wg_*.py，commit 拆兩個（一個 archive 舊檔、一個 land 新檔），revert 第二個 commit 即回到 V4.1。

---

### Wave 3 — P3b _ATOM_INDEX 結構化

**目標**：脫離 markdown table 解析脆性（commit e11b800 才修空行 bug）。

**改動檔案**：
- `memory/_ATOM_INDEX.md` → `memory/_atom_index.json`（schema：`{atoms:[{name, path, triggers:[], scope, last_used}]}`）
- `hooks/wg_atoms.py` — `_parse_trigger_table` 改為 `_load_atom_index_json`
- `tools/atom-injection-summary.py`（如有讀 INDEX）— 同步改

**trigger 列同時去重**：以 P3a 整併後的 5 atom 為例，每組 trigger ≤20 字、無跨 atom 重複（「codex」現在出現在 4 個 atom，整併到 `feedback-tooling`）。

---

### Wave 3 — P1 commands → skills 遷移

**目標**：26 commands 對齊原生 skill 格式，獲得「auto-invocation by description / body lazy-load / subagent 執行」三大新能力。

**遷移規格**（基於官方 [skills 文件](https://code.claude.com/docs/en/skills) frontmatter）：

```yaml
---
description: <50 字內 Claude 自動觸發判斷用，必填>
when_to_use: <額外觸發語境，選填>
disable-model-invocation: true   # 有副作用的工具（commit, deploy）設此
user-invocable: false             # 純背景知識不出現在 / menu
allowed-tools: Read Grep          # 自動授權避免問
context: fork                     # 大任務跑 subagent 不污染主 context
paths: "memory/**/*.md"           # glob 命中才 auto-load
---
```

**26 commands 遷移分類**：

| 處理方式 | commands |
|---------|----------|
| **直接遷移**（1:1 → SKILL.md）| harvest, journal, conflict, conflict-review, fix-escalation, generate-episodic, extract, read-project, browse-sprites, atom-debug, vector, upgrade, consciousness-stream |
| **合 1 個 /memory**（5→1）| memory-health, memory-peek, memory-undo, memory-review, memory-session-score → `skills/memory/SKILL.md` 用 `$0` 取 subcmd |
| **刪除**（內建已提供）| `resume`（CC 內建 --resume）、`init-project`（內建 /init）|
| **改名為 debug 工具**（hook 已自動）| changelog-roll → `/changelog-debug`（`disable-model-invocation: true`，純除錯用） |
| **下沉到專案層** | unity-yaml、svn-update → 不在全域而在 `<project>/.claude/skills/`（保留全域 alias 引導） |
| **保留全域**（與 V5 機制相關）| handoff、continue、codex-companion、init-roles |

**`paths` frontmatter 妙用**：
- `skills/atom-debug/SKILL.md` 加 `paths: "memory/**"` → 只在動 memory 時 auto-load
- `skills/unity-yaml/SKILL.md` 加 `paths: "**/*.unity, **/*.prefab, **/*.asset"`

**改動檔案**：
- 新建 26 個 `skills/<name>/SKILL.md`
- 暫時保留 `commands/*.md`（skill 同名優先生效，零停機）
- `workflow/config.json` 的 docdrift `commands/*.md` 映射改為 `skills/*/SKILL.md`
- 驗證完一週後刪除 `commands/`

**驗證**：
- 開新 session 打 `/memory health`、`/harvest`、`/handoff` 確認都觸發 skill 版而非 commands 版
- 試 auto-invocation：說「幫我看記憶健康」應自動觸發 `/memory`
- 確認 USER.md 推廣的 `/verify`, `/simplify`, `/run` 等內建 skill 可用

---

### Wave 3 — P5a Vector Service 精簡

**目標**：全域層（30 atoms）trigger 匹配改 in-memory BM25，**保留** vector 給 episodic / cross-session / dedup / 衝突偵測（不可退役）。

**改動檔案**：
- `hooks/wg_atoms.py`（P2 後的新版）— 加 `_bm25_match(query, atom_index_json)`；trigger 匹配優先走 BM25，命中 0 才 fallback 到 vector
- `tools/memory-vector-service/indexer.py` — 加 stale chunk 清理（atom 被 supersede / archive → 自動 evict 對應 chunk）
- `workflow/config.json` — 加 `vector_search.global_layer: "bm25"` 開關

**BM25 實作**：用 `rank_bm25` Python package（小、純 Python、無 GPU），或手刻 ~30 行（30 atoms × 數百 token 規模，BM25 dict 全在記憶體）。

**驗證**：
- 全域 atom trigger 匹配延遲 200-500ms → <10ms
- episodic search 仍走 vector（測：問「上次處理 hook 是什麼」應回憶得到）
- `_vectordb/` 大小減少（stale chunk 清掉）

---

### Wave 4 — P5b Codex Companion daemon → subprocess

**目標**：去 daemon 化，保留功能（LLM-as-judge 仍有價值），但消除 360 companion-state 檔案累積、port 3850 管理、guardian-crash.log 風險源。

**改動檔案**：
- `hooks/codex_companion.py` — 移除 HTTP dispatch，改為直接 `subprocess.Popen(codex.cmd, ...)`（fire-and-forget detached）+ 寫 state 到 `workflow/companion-state-{session}.json`
- `tools/codex-companion/service.py` — **刪除**（HTTP layer 不再需要）
- `tools/codex-companion/assessor.py / heuristics.py / scorer.py / prompts.py / state.py` — 保留（純函式 / 邏輯模組）
- `hooks/workflow-guardian.py` dispatcher — 改用新 `codex_companion.py` 函式而非 HTTP

**新流程**：
```
Hook trigger → codex_companion.detect_checkpoint() → 若需評估
  → subprocess.Popen("codex.cmd ...", stdout=assessment.json, detached=True)
  → hook 立即返回，不等
下次 UPS hook → 讀 assessment.json 若存在則注入 context → 刪檔
```

**workflow/companion-* 檔案清理**：P5b 結尾跑一次 `tools/cleanup-old-files.py --target=workflow --pattern="companion-*" --keep-days=7`，把 360 個壓到 ~30 個。

**驗證**：
- 開 plan mode → ExitPlanMode → 確認 Codex assessment 仍會注入 next UPS
- `netstat | grep 3850` 應為空（daemon 不再啟動）
- 多開 session 連測，確認無 zombie subprocess

---

### Wave 5 — P6 殘舊清理 + GA 收尾（純使用者安裝零垃圾）

> 使用者 2026-05-26 指示：V5 完工後須讓「純使用者安裝原子記憶系統時最沒垃圾的狀態」。升版 plan、archive 子目錄、過渡檔通通要妥善處理（刪除或搬到記憶備存區）。

**目標**：V5 GA 後的 `~/.claude/` 應該乾淨到可以打包成 plugin / template 分享。

**改動清單**：

| 處理 | 標的 | 動作 |
|------|------|------|
| **刪除（git rm）** | `~/.claude/commands/` 整個目錄（P1 已遷 skills 一週驗證後）| `git rm -r commands/` |
| **刪除（git rm）** | `hooks/_v4_archive/`（Wave 2 留的舊 wg_*.py）| `git rm -r hooks/_v4_archive/` |
| **刪除** | `tools/codex-companion/service.py`（P5b 已重寫，HTTP layer 不再需要）| `git rm tools/codex-companion/service.py` |
| **刪除** | `tools/memory-vector-service/` 的 stale chunk（P5a 已加 evict）| `python tools/cleanup-vector-stale.py` |
| **刪除** | `workflow/companion-state-test-sprint2-*` / `*-sprint3-*`（測試遺留）| `rm workflow/companion-*test-sprint*.json` |
| **刪除** | `workflow/config.json.bak-precision-routing-20260507-131002`（舊 backup） | `rm` |
| **刪除** | `.last-cleanup`（root 殘留） | `rm` |
| **刪除** | `workflow/companion-state-*` 超過 7 天的舊 session state | `python tools/cleanup-old-files.py --keep-days=7` |
| **歸檔到 _distant** | `_AIDocs/V5-upgrade-plan.md` → `memory/_distant/2026_05_v5_overhaul/V5-upgrade-plan.md` | `git mv` |
| **歸檔到 _distant** | `plans/wondrous-humming-spark.md`（gitignored，純本地） | `mv plans/wondrous-humming-spark.md memory/_distant/2026_05_v5_overhaul/` 然後刪 plans/ |
| **歸檔到 _distant** | `memory/v5-overhaul-audit-2026-05.md` audit atom | atom `Status: archived`，內容保留作為「V4→V5 升版檔案」歷史證物 |
| **歸檔到 _distant** | `memory/feedback/feedback-*.md` 24 個舊 atom（P3a 已合 5）→ `_distant/2026_05_consolidation/` | （P3a 已做，這裡只確認）|
| **歸檔到 _distant** | `_AIDocs/SPEC_ATOM_V4.md` / `V4.1-design-roundtable.md`（V4 文件）| `git mv` to `_AIDocs/DevHistory/v4-archive/` |
| **更新文件** | `_AIDocs/Architecture.md` 反映 V5 架構（取代 V4.1 描述）| Edit |
| **更新文件** | `TECH.md` 反映 V5 設計（取代 V4.1）| Edit |
| **更新 README** | 確認 GA 後乾淨度可作為 template 分享 | Edit |
| **重啟 disabled hooks** | `pre-commit.disabled-during-v5` → 改寫成 V5 版本後 → `pre-commit` | 見上方「全域 disable 策略」表 |
| **晉升 atom** | `v5-overhaul-audit-2026-05` confidence `[臨]` → `[固]`（代表升版完成 + 證物保留）| atom_write mode=replace |

**「乾淨安裝」自檢**：

執行：
```
tree ~/.claude -L 2 -I '__pycache__|*.pyc|workflow/companion-state-*|workflow/companion-metrics-*'
```

期望：
- 沒有 `commands/`（已遷 skills/）
- 沒有 `_v4_archive/`
- 沒有 `plans/`（升級計畫已歸檔）
- 沒有 `*.bak-*` 檔案
- 沒有 `_AIDocs/V5-upgrade-plan.md`（已歸檔到 _distant）
- 工作檔（workflow/）只有當前 session 狀態
- _distant/ 子目錄整齊：`2026_05_v5_overhaul/`、`2026_05_consolidation/`
- 重啟所有 `.disabled-during-v5` 機制 → 全綠

**驗收**：
- `du -sh ~/.claude/` < 200 MB（核心系統 + 必要索引）
- 新使用者 git clone 後跑 `~/.claude/Install-forAI.md` 流程零干擾

**回滾**：P6 是純清理工作，每筆刪除 / 歸檔個別 commit，需要時 `git revert` 任意一筆。歸檔到 `_distant/` 可以隨時拉回。

---

## 「升版類 plan 的 lifecycle 政策」（V5 之後永久原則）

未來任何 V6/V7 升級計畫的 lifecycle：

1. **規劃期**：`plans/<name>.md`（CC 原生位置，gitignored）+ `_AIDocs/<name>-upgrade-plan.md`（git tracked）
2. **執行期**：相關 atom 標 `[臨]`，next-phase.md 滾動更新
3. **GA 後 7 天**：plan 與 audit atom 歸檔到 `memory/_distant/{year}_{month}_{slug}/`
4. **GA 後立即**：legacy 檔（被新版取代的）`git rm`，避免新使用者誤用
5. **新使用者乾淨度檢核**：每次 GA 跑「乾淨安裝」自檢腳本

---

## Prompt Cache 最大化策略

> Anthropic 官方 prompt cache TTL = 5 分鐘。每次 cache miss 重讀全部 system prompt + @import 鏈 ≈ 數千 token 損失。

### 每 session 的操作順序（共用樣板）

1. **開頭 30 秒讀全部 stable context（一次性 cache 填充）**：
   - 並行：Read `CLAUDE.md` / `IDENTITY.md` / `USER.md` / `memory/MEMORY.md` / `memory/v5-overhaul-audit-2026-05.md` / `_staging/next-phase.md`
   - 並行：Read 本 phase 要改的所有檔案（一次到位）
2. **集中改動（cache 有效期內）**：所有 Edit/Write 在 ~5 分鐘內密集執行
3. **長時等待用 background agent**：跑測試、跑 worker、跑 LLM 評估 → `run_in_background:true`，主 thread 不阻塞 cache
4. **避免 mid-session 動 @import 鏈**：除非本 phase 目標就是改 IDENTITY/USER/CLAUDE（P4a/P4b），否則絕對不動——一動全部 cache miss
5. **收尾 atom append 不破 cache**：`atom_write mode=append` 只寫子檔，不動 CLAUDE.md @import 鏈

### Phase 內平行調度

每個 phase 內部用以下機制平行：
- **單 message 多 tool call**：所有獨立 Read/Edit/Grep 同 message 發出（CC harness 並行執行，省 roundtrip + 不破 cache）
- **Agent subagent 隔離**：Plan agent / Explore agent 跑「污染性」探查（不污染主 context cache）
- **Background agent**：長跑工作（runtime > 30s）用 `run_in_background:true`，例如：
  - P2 wg_atoms 重構後跑 pytest（背景）
  - P3a 把 24 feedback 餵 LLM 做主題分群（背景）
  - P5b Codex subprocess 真實調用測試（背景）

### Phase 之間的 cross-session cache 不可恢復

每個 session 是獨立 cache scope。所以：
- 不要把一個 phase 切兩個 session（cache 全失），除非 phase 太大
- Wave 1 三 phase 可同 session 串接（同 cache 期內密集做，總共 < 30 分鐘可完成）
- Wave 2 是大 phase，單獨 session 完整跑（cache 利用最大化）

---

## Handoff 機制（不失憶接力）

每 phase 結束（不分 wave）必做四件事：

1. **append audit atom**：
   ```
   mcp__workflow-guardian__atom_write(
     title="v5-overhaul-audit-2026-05",
     mode="append",
     knowledge=["[臨] {date} 完成 P{n}: <做了什麼> | 改動檔案: <清單> | 待續: <下一 phase 入口>"]
   )
   ```
2. **寫 _staging/next-phase.md**：下個 session 的 prompt 入口（含本 phase 結束狀態 + 下一 phase 第一步指令）
3. **執P 收尾**（USER.md 縮寫）：執行 + 驗證 + 上 GIT（每 phase 一個 commit，commit message 格式 `feat(v5): P{n} <主題> — <關鍵變更>`）
4. **更新 TODO**：本 phase markedcompleted，下一 phase 入口寫進 TodoWrite

**下個 session 啟動樣板**：
```
> /continue
（自動讀 _staging/next-phase.md + v5-overhaul-audit-2026-05.md → 拿到完整接力 context）
```

---

## Critical Files（執行時必讀）

按修改頻率排序：

| 檔案 | 改動 phase |
|------|-----------|
| `hooks/workflow-guardian.py` | P0, P2, P5a, P5b |
| `hooks/wg_atoms.py` | P2, P3b, P5a |
| `hooks/wg_core.py` | P0, P2 |
| `hooks/wg_evasion.py` | P2, P4b |
| `hooks/codex_companion.py` | P5b |
| `tools/workflow-guardian-mcp/server.js` | P2 |
| `tools/memory-vector-service/indexer.py` | P5a |
| `tools/codex-companion/service.py` | P5b (刪除) |
| `workflow/config.json` | P1, P2 |
| `memory/_ATOM_INDEX.md` → `.json` | P3b |
| `memory/MEMORY.md` | P3a, P4a |
| `memory/feedback/*.md` × 24 | P3a |
| `IDENTITY.md` / `USER.md` / `CLAUDE.md` | P4a |

---

## 驗證與回滾

### 每 phase 驗收項

| Phase | 驗收 |
|-------|------|
| P0 | `du -sh workflow/` < 500MB；新 session 開啟正常 |
| P3a | `ls memory/feedback/` 剩 5 個；舊 24 個在 `_distant/2026_05_consolidation/`；grep 無 hardcode 殘留 |
| P4a | 新 session system prompt token 數 < 700（用 `/cost` 或 transcript 對照）；evasion 仍正常攔截 |
| P2 | hook 鏈完整跑通；MCP `/mcp` 看 workflow-guardian 只剩 3 tool；4 套自評整合測試 |
| P3b | _atom_index.json 存在；wg_atoms 載入正常；trigger 注入測試案例通過 |
| P1 | 26 → ~17 skill；`/memory health` 等可用；auto-invocation 測試（不打 / 也能觸發） |
| P5a | 全域 trigger 匹配 <10ms；episodic 仍走 vector；`_vectordb/` 縮小 |
| P5b | port 3850 無人聽；companion-* 檔案 < 30；assessment 注入仍生效 |

### 回滾路徑

每 phase 一個 commit + `_v4_archive/` 保留舊檔。`git revert <commit>` 即回滾單一 phase，不波及其他。Wave 2（P2）是最危險的——commit 拆兩個（archive + new），便於精準 revert。

### 完工 GA Checklist

V5 完成條件：

- [ ] `du -sh ~/.claude/workflow/` < 500 MB（確保沒有再次膨脹）
- [ ] `~/.claude/commands/` 已刪除（純走 skills）
- [ ] `~/.claude/skills/` 內所有 SKILL.md 有 `description` 欄位
- [ ] `tools/workflow-guardian-mcp/server.js` 暴露 ≤ 3 tool
- [ ] `hooks/wg_*.py` ≤ 6 個檔案
- [ ] `port 3850` 無 daemon 監聽
- [ ] session start system prompt < 700 token
- [ ] V5 audit atom 標 `[固]`（從 `[臨]` 晉升，代表升版完成）
- [ ] 更新 `_AIDocs/Architecture.md` 反映 V5 架構
- [ ] 更新 `TECH.md` 反映 V5 設計
- [ ] 上 GIT（總計 6-9 個 commit，按 phase 分）

---

## 風險清單

| 風險 | 緩解 |
|------|------|
| Wave 2（P2）合併 wg_*.py 改太大破壞既有功能 | 拆 commit；保留 `_v4_archive/`；單獨 session；先跑覆蓋率測試 |
| commands/ 與 skills/ 同名期間混淆 | 官方規格：skill > command，但仍建議遷移後 1 週才刪舊 commands |
| BM25 套件選擇影響部署 | 用 `rank_bm25` 或手刻 ~30 行，避免新增複雜依賴 |
| _ATOM_INDEX.md JSON 化破壞外部讀檔工具 | 保留 .md 為 deprecated alias 一段時間；同步改外部工具 |
| Codex Companion 重構漏掉某個 hook event | 對齊改前舊 `service.py` 的 event handler 表，逐一覆蓋 |
| 多 session 進行中 atom 寫衝突 | V4 衝突偵測機制本來就在；每 phase 結束等 1 分鐘讓 vector index 完成才開下個 |

---

## 起手式

**第一個 session（Wave 1）prompt**：

```
讀 plans/wondrous-humming-spark.md 與 memory/v5-overhaul-audit-2026-05.md，
開始 Wave 1：P0（log rotation）+ P3a（feedback 整併）+ P4a（文件瘦身）。
每 phase 完成立即執P + atom append + 寫 _staging/next-phase.md。
```
