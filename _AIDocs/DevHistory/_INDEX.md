# DevHistory — 開發紀錄索引

> 從各 atom / Architecture.md 精簡移出的版本演進、遷移紀錄、實測數據、穩定子系統細節。
> 供需要查閱歷史脈絡時按需閱讀，不自動注入 session context。

| # | 文件名稱 | 說明 | keywords |
|---|---------|------|----------|
| 1 | atom-evolution.md | 各 atom 演化日誌彙整 | 演化, 版本, changelog, 日期, 變更記錄 |
| 2 | version-migrations.md | 原子記憶 V2.18~V2.21 版本遷移敘述 | V2.18, V2.19, V2.20, V2.21, 遷移, migration, Phase |
| 3 | ab-test-ollama.md | Ollama Dual-Backend A/B 萃取品質實測數據（qwen3.5 vs qwen3:1.7b） | A/B, 萃取品質, qwen3, rdchat, 實測, benchmark |
| 4 | ab-test-gemma4.md | Gemma 4 vs Qwen 3.5 三輪 A/B 測試（V3.4 模型切換決策依據） | gemma4, qwen3.5, A/B, 萃取, 溫度, format bug |
| 5 | v41-journey.md | V4.1 圓桌設計與 GA 歷程 + §10 Runtime 架構（user-extract + P4 評價） | V4.1, user-extract, L0, L1, L2, session_score, evaluator |
| 6 | ollama-backend.md | Dual-Backend Ollama 退避機制（三階段 DIE + failover） | ollama, 退避, DIE, rdchat, failover |
| 7 | memory-pipeline.md | 記憶檢索管線 + 回應知識捕獲 + V3 三層即時管線 | pipeline, JIT, vector, hot_cache, 萃取, V3 |
| 8 | session-mgmt.md | SessionStart 去重 + 孤兒清理 + Merge self-heal | sessionstart, dedup, merge_into, orphan, self-heal |
| 9 | v4-layers.md | V4 專案自治層 + 三層 scope + Role-filtered JIT | scope, personal, shared, role, project-registry, JIT |
| 10 | v4-conflict.md | V4 三時段衝突偵測完整流程（Phase 5+6） | conflict, pending_review, CONTRADICT, EXTEND, write-check, pull-audit |
| 11 | wisdom-engine.md | Wisdom Engine + Fix Escalation + 跨 Session 鞏固 | wisdom, reflection, fix_escalation, 鞏固 |
| 12 | settings-config.md | settings.json 權限 + 工具鏈總覽 | settings, permissions, 權限, 工具鏈, tools |
| 13 | multi-agent-cleanup-protocol.md | 多大師協作流程通用版（CC ≥ Codex 席次設計、防 Codex 幻覺、Windows sandbox 修復、Phase 4 audit 重派、收尾 checklist） | multi-agent, codex, 大師, 協作, sandbox, audit, 監督執行 |
| 14 | atom-trigger-source-of-truth.md | Atom Trigger 三源（frontmatter / _ATOM_INDEX / MEMORY.md）真相規格化設計（待拍板） | atom trigger, source of truth, _ATOM_INDEX, frontmatter, MEMORY.md, drift, sync 工具 |
| 15 | vector-threshold-calibration-2026-04.md | Wave 3b probe-burst 數據驅動的 ranked-sections min_score 校準（90 query x 6 threshold 矩陣 + 決策） | vector, threshold, calibration, ranked-sections, min_score, probe-burst, 議題 #6, REG-005 |
| 16 | atom-injection-refactor-2026-04.md | REG-005 atom 注入機制重構收尾（A+B+C+D 4 層 + 觀察期 KEEP 判定 + 設計歸檔） | REG-005, atom, injection, summary-first, budget, hot-cold, related, 4-layer, KEEP, 觀察期 |
| 17 | v4-archive/ | Wave 4 hooks/_v4_archive 19 檔對照證物（V4 hook 模組退役前最後一版） | v4-archive, hooks, 證物, V4 退役 |
| 19 | pan-deny-judgement-2026-08-06.md | PAN 預告閘門 warn→deny 終局判讀（四門檻逐筆證據 + 漏偵決定性反證 + 判讀方法學踩坑） | PAN, 預告閘門, pre_action_notice, 翻 deny, 漏偵率, 假陰性, text_blocks, fail_open_no_transcript |
| 18 | v5-overhaul-2026-05/ | V5 升版完整紀錄（起因 + 4-Wave + Wave 5 全面汰舊 + GA Checklist 驗收 + Session α/β feedback-aidocs 遷移）— 取代原 audit atom | V5, GA, 升版, overhaul, Wave, 全面汰舊, BM25, JSON SoT, Codex subprocess, 114GB, feedback-aidocs, atom_locations |
| 19 | session-coordination-bus.md | 跨 session 衝突預警多大師計畫紀錄（CC 原生無跨 session 管道查證 + 七席共議仲裁 + PreToolUse additionalContext probe 實測 + Stage 2/3 defer 條件） | session 協調, 衝突預警, coordination, 多大師, CoordWarn, probe, Agent Teams, add -A |
| 19 | auto-memory-writeback.md | 對談結束自動記憶 writeback 三 stage 開發脈絡（session_end flush 落點路由 + 失敗五區塊骨架 + Deep Post-Mortem Gate；含 edit-count proxy 拔除、獨立預算演化） | session_end flush, 失敗骨架, deep post-mortem, writeback, 落點路由, extract-worker, stop gate, edit-count proxy |
| 20 | 核心記憶分類階層化-2026-08.md | 核心記憶分類階層化 S1–S5 編年（起因與使用者原則原文 + 兩根／11 個 Lv1 目標形狀 + 被否決方案與理由 + 五階段 commit／驗證數字 + 附帶修掉的 bug + 遺留議題 + 總管模式協作） | 分類階層化, taxonomy, 範疇資料夾, memory/Failures, MEMORY.md 目錄, 寫入閘, domain 必填, atom-categorize, 兩根, 使用面 開發面, 總管模式, S1–S5 |
| 20 | memory-system-review-2026-08.md | 原子記憶系統 × CC 原生記憶 × 業界主流三方比對評估（as-built 管線逐檔核對＋優缺點／可補強／該修正各標已處理／待辦＋修前後數據＋單一決策點：積累端 provenance＋週期整併） | 三方比對, 記憶系統評估, RRF, ACT-R, 注入預算, provenance, cross-encoder, 積累端, CC auto-memory, 業界主流, 2026-08 |
| 21 | injection-budget-investigation-2026-08.md | 注入變弱調查編年（三假設證偽：MEMORY.md 瘦身／分類閘／中文檔名 → 根因 TURN_BUDGET_LIMIT 縮量未回調 → 五次修正各附證據／修法／驗證／commit → 未做與理由 → 回訪四指標 → 教訓） | 注入變弱, TURN_BUDGET_LIMIT, 裁切回填, compute_token_budget, token 分級, 同題去冗, redundancy_gate, 橋接檔 slug, 回訪機制, followup-check, injection-turns.jsonl, 全文率 |

> 2026-05-27 Wave 5 Session 2 已歸檔（移至 `memory/_distant/2026_05_v5_overhaul/`，git 不再追蹤）：`session-logs/` / `memory-cleanup-2026-04/` / `atomic-memory-evolution/` / `ab-test-gemma4/` / `atom-v4/` / `atom-v4-phases/` / `changelog-roll/` / `v41-handoffs/` / `v41-p4-simulation/` / `wg-docdrift/`

> 2026-05-28 Session α/β（commits `082f791` / `89ccb2d` / `6772049`）：feedback-* atoms 5 個 + cognitive-patterns + memory-pipeline-silent-failure-2026-05 物理搬遷至 `_AIDocs/Failures/`，`lib/atom_locations.py` 為單一規則來源；sync-atom-index / vector indexer 多根掃描；SPEC_ATOM_V5 §2.1 章節記錄。完整紀錄詳見上方 v5-overhaul-2026-05/ 及主 [_AIDocs/_CHANGELOG.md](../_CHANGELOG.md) 對應條目。

> 2026-06-03 Realm S3 Phase 5 雞肋稽核：本目錄為「按需閱讀、**不自動注入**」歷史歸檔區（注入成本＝0）。內容已結案/被 V5 超越但**仍被活引用為證物**者——`v4-layers.md`·`v4-conflict.md`（V4 設計，[Architecture.md](../Architecture.md) 引）、`version-migrations.md`（V2.18~21）、`ab-test-ollama.md`·`ab-test-gemma4.md`（核心 atom `toolchain-ollama` + [TECH.md](../../TECH.md) 引）、`vector-threshold-calibration-2026-04.md`（活躍檔 `atom-injection-refactor-2026-04.md` 當「前置」引）——**一律保留原位不再下沉**（歸檔區內再開歸檔零收益、且會斷同層相對連結）。已驗證 [`known-regressions.md`](../known-regressions.md) 仍準確；REG-006 三萃取管線（`quick-extract`/`extract-worker`/`user-extract-worker`）經查**確仍並存**，屬 open 合併研究項、非 stale。
