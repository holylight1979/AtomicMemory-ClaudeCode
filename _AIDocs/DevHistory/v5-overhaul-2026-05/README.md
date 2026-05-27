# V5 全面汰舊 — 從「過度設計 + 114 GB 災難」到 GA

> **期間**：2026-05-26 V5 計畫定版 → 2026-05-27 V5 GA 簽收
> **規模**：5-Wave / 14+ commits / 4-Wave 主動升級 + 1-Wave 全面汰舊
> **核心交付**：對齊 Anthropic 原生機制（skills / deferred MCP / plugin packaging）+ 子系統去 daemon 化 + 全域 BM25 + JSON SoT + 文件層瘦身 + 114 GB 災難根治
>
> **取代 atom**：本紀錄取代 `memory/v5-overhaul-audit-2026-05.md`（已歸檔 `_distant/2026_05_v5_overhaul/`）。

---

## 1. 起因 — V4.1 GA 之後的問題清單

V4.1 GA（2026-04-16）後 1 個月，累積問題到了不可忽視的程度：

### 1.1 災難級
- `workflow/guardian-crash.log = 114 GB`（**無 rotation**），佔 100% 磁碟膨脹源頭。停止後磁碟立刻釋放，但 NTFS 索引損毀導致該檔程式無法刪除 → 需 chkdsk 重開機才能根治。

### 1.2 架構過時
- Anthropic 官方明文「Custom commands have been merged into skills」（code.claude.com/docs/en/skills）— 但我們 `commands/` 仍有 22+ legacy `.md`。
- Skill 模式（`.claude/skills/{name}/SKILL.md`）才能享有「Claude 自動觸發 + body 按需載入 + subagent 執行 + dynamic context injection」，commands 模式全沒有。

### 1.3 過度設計
- 16 個 `wg_*.py` + 1640 行 `workflow-guardian.py` dispatcher，邏輯切過細
- 四套自評重疊：`wg_evasion` / `wg_session_evaluator` / `wg_iteration` / `codex_companion soft_gate`
- Codex Companion daemon @ port 3850（30 audits/session 對全域 ~17 atoms 規模殺雞用牛刀）
- Vector Service @ port 3849 對全域層（~17 atoms）也是大砲打蚊子
- 24 個 `feedback-*.md` 違反 `feedback-pointer-atom` 自己定的「指標型」原則（平均 1.2 KB / atom 含失效項）

### 1.4 歸類錯誤
- MCP 7 tool 中 4 個（`workflow_signal` / `workflow_status` / `memory_queue_add` / `memory_queue_flush`）是**內部 IPC** 不該暴露給 AI；只有 `atom_write` / `atom_move` / `atom_promote` 3 個合理走 MCP。

### 1.5 機器源脆性
- `_ATOM_INDEX.md` table 為機器源，parser 對格式脆性高（commit `e11b800` 才修空行污染）

### 1.6 Token 浪費
- Session start context 注入 ≈1100 token：IDENTITY 反退避契約 + 行為準則 + USER.md 縮寫 + MEMORY.md 索引大量重複，可壓縮 ≈55%

---

## 2. 計畫演化 — 6-phase 線性 → 4-Wave + Wave 5

### 2.1 原規劃 6-phase

最初設計（2026-05-26 起手）為 6-phase 線性執行：
- P0 緊急救火（log truncate + rotation）
- P1 commands → skills 遷移
- P2 hook / MCP 重整
- P3 atom 整併（feedback 合 + index JSON 化）
- P4 context budget 瘦身
- P5 子系統退役（vector / codex companion）

預估 6-9 session。

### 2.2 改為 4-Wave（Plan agent 驗證後）

Plan agent 對 `wg_atoms.py` / `workflow-guardian.py` 識別出為三方爭用熱點（多 phase 同時要動），故重排：

| Wave | Phase 組合 | 時序考量 |
|------|----------|---------|
| 1 | P0 + P3a + P4a | log rotation 必須先（root cause）；feedback 合併 + 文件瘦身 可並行 |
| 2 | P2 + P4b | hook/MCP 重整 + 禁語 JSON 抽離 |
| 3 | P3b + P1 + P5a | JSON SoT + commands→skills + 全域 BM25（**三方爭用熱點**全 Wave 一氣呵成） |
| 4 | P5b + P6 + 文件定稿 | Codex daemon→subprocess + dead code 清理 + SPEC_ATOM_V5.md 定稿 |

預估 4-6 session（省 30-40%）。

User 2026-05-26 批准，plan 寫入 `plans/wondrous-humming-spark.md`。

### 2.3 為什麼又加 Wave 5

Wave 1-4 完成（4 個 session）後實況：
- 主要架構升級已就位（skills 19 個、hooks 8 wg_* + handlers、BM25、JSON SoT、subprocess Codex）
- 但 GA 候選盤點時發現大量「歷史殘留」：
  - `workflow/guardian-crash.log = 114 GB`（chkdsk 前無法解）
  - `projects/` 4 個過時 cwd（17 MB）
  - Vector DB 累積 152 MB（多 chunk 已 stale）
  - 17 個 tools/tests 過時檔
  - REG-005 觀察期 atom 採樣 dead path
  - 8 個 runtime state 檔被誤 tracked

→ 新增 Wave 5（4 session）全面汰舊，含 user 手動 chkdsk SOP。

---

## 3. 各 Wave 交付摘要

### 3.1 Wave 1 — 急救 + 文件瘦身（commit `09ec026`）

| Phase | 交付 |
|-------|------|
| **P0** | `wg_core.py` 加 `LOG_ROTATE_THRESHOLD_BYTES`（預設 100 MB）；guardian-crash.log / extract-worker.log 自動輪轉為 `.1` / `.2` / `.3`，最多 3 份 |
| **P3a** | 24 個 `feedback-*.md` 整併為 5 個主題 atom：`feedback-workflow-discipline` / `feedback-completion-gates` / `feedback-tooling-reliability` / `feedback-memory-structure` / `feedback-rigor-standards`。原 24 個歸 `_distant/2026_05_consolidation/feedback/` |
| **P4a** | `IDENTITY.md` 禁語清單抽出（為 P4b 鋪路）；`MEMORY.md` 索引壓縮為 ≤30 行 |

handoff: commit `fa86ba1`。

### 3.2 Wave 2 — Hook + MCP 重整（commit `f1e0cbc`）

| Phase | 交付 |
|-------|------|
| **P2** | 16 `wg_*.py` → 6 主模組（core/atoms/extraction/episodic/evasion/docdrift）+ 2 shim（roles/atom_observation）；dispatcher 2651 → ~75 行；handlers/ 拆 8 個 event 各一檔；`workflow-guardian.py` 1 行 shim |
| **P2** | MCP 7 tool → 3 tool（`atom_write` / `atom_move` / `atom_promote`）；砍 4 內部 IPC（改 Stop gate 內化） |
| **P4b** | `memory/_meta/forbidden-phrases.json` 為禁語 single source；IDENTITY.md + wg_evasion.py 都讀 JSON |

Archive: commit `2fc7aed`（`_v4_archive/` 存 19 個舊 hook 副本作參考）。

### 3.3 Wave 3 — JSON SoT + skills 遷移 + BM25（commits `b0f98c1` + `f3854c8`）

| Phase | 交付 |
|-------|------|
| **P3b** | `memory/_atom_index.json` (Schema v1.0) 為唯一機器源；`lib/atom_index_json.py` 全套 API；`_ATOM_INDEX.md` 改為自動生成 mirror；`.git/hooks/pre-commit` 重啟做 JSON validate + MD mirror drift check |
| **P1** | 22+ `commands/*.md` → 19 個 `skills/{name}/SKILL.md`（13 直遷 + 4 全域保留 + 5 memory 合 1 + 1 改名 + 4 刪除）。Skill frontmatter 含 description / when_to_use / disable-model-invocation / user-invocable / allowed-tools / context / paths |
| **P5a** | 手刻 BM25 ~80 行於 `wg_atoms.py`（ASCII word + 中文 char-bigram tokenization；k1=1.2, b=0.75）；注入流程：trigger → BM25（≤2 trigger 命中時 / min_score=1.0 / top_k=3）→ Vector fallback；Vector Service 保留給專案層 + episodic |

### 3.4 Wave 4 — Codex subprocess + 文件定稿（commit `04b35b4` / `a7e5be4`）

| Phase | 交付 |
|-------|------|
| **P5b** | Codex Companion daemon → subprocess 模型：`tools/codex-companion/audit.py` one-shot subprocess（stdin JSON → assessor → state.write_assessment）；`tools/codex-companion/service.py` 刪除；port 3850 無人聽；`hooks/codex_companion.py` 重寫去 urllib/socket/_http_post |
| **P6** | dead code 清理（無效 hook / 廢 helper / V4 殘留） |
| **文件定稿** | `_AIDocs/SPEC_ATOM_V5.md` 為 V5 GA 規格主檔（取代 V4 SPEC；V4 保留為對照證物）；`Architecture.md` 同步 V5 |
| **收尾** | commands/ 22 檔提前刪除（原訂 7 天緩衝經對拍 100% identical 後提前廢止） |

### 3.5 Wave 5 — 全面汰舊（5 session）

Wave 5 涵蓋 user-driven 全面盤點：

| Session | 交付 | Commit |
|---------|------|--------|
| **plan** | 全面汰舊計畫寫入 next-phase（無源碼變更） | `9c56a56` |
| **1** | A+B 組：runtime 88 MB + 17 tools/tests + REG-005 dead path 清除 | `d76bba1` |
| **1 audit** | 5 條進度 knowledge + 2 條 Session 2 actions 入 atom | `10cd1ab` |
| **2** | C+D+E 組：DevHistory 歸檔 + V5 plan 退役 + 8 runtime 檔 untrack | `651be4a` |
| **3** | F+H+G+I 組：projects 歸檔 + Vector DB rebuild（152 MB → 36 MB）+ atom 晉升決議 + 4 綠自檢 | `f937589` |
| **3 audit** | 4 組執行紀錄入 atom | `f937589` |
| **4** | user 手動操作：chkdsk C: /f 重開機 → guardian-crash.log 物理刪除（114 GB → 329K）→ GA Checklist 驗收 | _（本 commit）_ |

---

## 4. GA Checklist 驗收（Session 4）

| 項目 | 期望 | 實際 |
| --- | --- | --- |
| `workflow/` < 500 MB | < 500 MB | **218K**（114 GB → 0.0002%） |
| `hooks/wg_*.py` | 8 | **8** ✓ |
| `skills/*/SKILL.md` | 19 | **19** ✓ |
| MCP atom 工具 | 3 | **3** ✓ |
| pytest baseline | 40/414/52 | **40/414/52** ✓ |
| `guardian-crash.log` 物理刪除 | 不存在 | **不存在** ✓ |
| git working tree | clean | **clean** ✓ |
| `commands/` 全刪 | 0 | **0** ✓ |
| port 3850 daemon | 無人聽 | **無人聽** ✓ |

---

## 5. 後續

### 5.1 [臨] → [觀] 自然累積

Wave 5 期間 17 個 atom 與審計用 atom 都還是 [臨]，依「Confirmations ≥ 20 + 跨 session 出現」自然累積，**不人工晉升**。

### 5.2 Wave 5 期間衍生規則（寫入 IDENTITY + feedback atom）

- **收尾檢核 4 項全項檢視**（非二選一）：(a) 缺失修補 / (b) AI 逃避通報 / (c) Token 警示 / (d) 衍生暫存清單
- **完工清暫存原則**：工具自動產生 + 無 git track + 無人工填值 + 僅服務當次任務 → 預設直接刪
- **IDENTITY 索引化**：能透過 atom trigger 注入的規則移到 atom（職責 / 發現門檻 → atom），IDENTITY 只留每 session 必載硬契約

### 5.3 後續可選

- **Vector Service 全域層**：V5 已改 BM25 替代；專案層仍走 vector（避免上百 atoms BM25 退化）
- **Codex Companion**：daemon → subprocess 完成；assessment 延遲從 ~1ms HTTP → ~10-50ms spawn，可接受
- **多職務目錄**：`shared/` + `role/{name}/` + `personal/{user}/` 代碼就緒，未啟用環境（單人 holylight）仍走 personal/holylight/

---

## 6. 參考

- 規格主檔：[`../../SPEC_ATOM_V5.md`](../../SPEC_ATOM_V5.md)
- V4 對照證物：[`../../SPEC_ATOM_V4.md`](../../SPEC_ATOM_V4.md)
- V4.1 開發歷程：[`../v41-journey.md`](../v41-journey.md)
- Wave 1-5 commits：`09ec026` / `f1e0cbc` / `b0f98c1` `f3854c8` / `04b35b4` `a7e5be4` / `d76bba1` `651be4a` `f937589`
- 計畫檔：`plans/wondrous-humming-spark.md`（Wave 5 Session 2 退役 → 已歸檔）
- 歸檔 audit atom：[`../../../memory/_distant/2026_05_v5_overhaul/v5-overhaul-audit-2026-05.md`](../../../memory/_distant/2026_05_v5_overhaul/v5-overhaul-audit-2026-05.md)
