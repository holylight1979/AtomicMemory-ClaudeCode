# 原子記憶版本遷移紀錄

> 從 decisions.md「核心架構」段落移出的版本遷移敘述。描述的是「怎麼遷過來的」而非「現在是什麼」。

## 版本表

原載 `TECH.md` §14.1，整表移此；現況以 `TECH.md` 與實碼為準。

| 版本 | 日期 | 白話 | 核心變更 |
|------|------|------|---------|
| V1.0 | 2026-03-02 | 三層可信度 + 格式健檢 | `[固]/[觀]/[臨]` + memory-audit |
| V2.0 | 2026-03-03 | 語意搜尋上線 | Hybrid RECALL（keyword + vector + rerank） |
| V2.1 | 2026-03-04 | 品質閘門擋垃圾 | Write Gate + intent classifier + 衝突偵測 + decay |
| V2.4 | 2026-03-05 | AI 回答自動存 + 跨 session 升級 | 回應萃取 + 向量鞏固 + 兩層分類 |
| V2.5–2.10 | 2026-03-06~11 | 萃取 + 反思 + 閱讀軌跡 | JSON 強制 / Wisdom Engine / Read Tracking |
| V2.11–2.18 | 2026-03-13~24 | Dual-Backend + 失敗自動化 + Section-Level | 三階段退避 + Fix Escalation + Token Diet |
| V2.20–2.21 | 2026-03-27 | 路徑集中化 + 專案自治層 | `wg_paths.py` + `{project}/.claude/memory/` |
| V3.0–3.4 | 2026-04-02~09 | 三層即時管線 + Gemma 4 萃取 | Hot Cache + DocDrift + gemma4:e4b |
| V4.0 | 2026-04-15 | 多職務團隊知識分層 | 四層 scope + `_roles.md` 雙向認證 + 三時段衝突 + pending review |
| V4.1 | 2026-04-16 | 使用者決策自動寫成記憶 | L0→L1→L2 + 240 tok budget + `/memory-*` |
| V5 GA | 2026-05-27 | 對齊原生 + JSON SoT + Subprocess + BM25 | log rotation；hook 16 模組→6+shim；MCP 7→3 tool；commands→skills；JSON SoT；BM25 全域層；Codex daemon→subprocess；workflow 114GB→329K |
| audit | 2026-07-01 | 誠實化 + 修剪 | vector 復活（靜默死 26.7d）+ 可觀測告警；dispatcher 惰性 import；死碼清理；BM25 min_score 1.0→3.5；Realm 停 LLM；per-turn／session_end flush 停產；FixEscalation 改 error-based；USER 單人化；多人層 archive；lang_guard；治理原則入 rules |
| V5.1 | 2026-07-25 | 檢索精準化 + 記憶完備性 | RRF 三路融合 × 個別化 decay；memory-eval 223 條（R@1 34→53.6%、MRR 0.584→0.709；bm25_min_score 3.5→7.0）；wilson_z 1.28 + demote n≥5 + decay 每日護欄；recall-miss；Depends/Evidence + fast-refute；向量服務修復；token 口徑統一；新 atom activation 0.0；UPS 90→16ms |
| 5.1 後續 | 2026-07-31~08-06 | 協作與驗收 | 跨 session 衝突預警（純檔案）；PAN 預告閘門（終局 warn）；驗收裁判四段閉環 + 裁判後端鏈 |
| 5.1 後續 | 2026-08-25~31 | 分類階層化 + 注入根治 + 落點單源 | 核心 atom 進 `memory/<範疇>/`、MEMORY.md 目錄化、寫入閘 domain 必填；AEC 殘檔帳本；DeferralGate；per-turn 硬頂 500→1200、裁切回填、分級依 token、同題去冗；write-gate 去重限層；realm 閘；橋接檔重產；回訪機制；跨專案索引快取；專案層判定單源；atom 落點單一裁決（js 鏡像全拔）；退避偵測引號內不觸發 |

## 4.x → 5.1：升級後確認清單

原載於 `Install-forAI.md`「升級」章，安裝 runbook 化（升級改由 `tools/install.py --upgrade` 一條指令）時移入。清單描述的是 5.1 當時的形狀，後續演進以 `TECH.md` 與實碼為準。

- [ ] `version.json` 為 `atom_memory: "5.1"` / `guardian: "5.1.0"`
- [ ] `hooks/dispatcher.py` 存在；`hooks/handlers/` 有 9 個事件 handler（session_start / session_end / user_prompt_submit / pre_tool_use / post_tool_use / stop / pre_compact / post_compact / post_tool_batch）+ `ups_*.py` 四段 + `_shared.py` + `aec_ledger.py`
- [ ] `hooks/wg_*.py` 為：wg_atoms / wg_coordination / wg_core / wg_docdrift / wg_episodic / wg_evasion / wg_extraction / wg_friction / wg_handoff / wg_harvest / wg_parallel / wg_recall_miss / wg_rescue / wg_research / wg_roles / wg_vcs_sync（wg_roles＝身份／職能／裁決，不再是 shim）；detached worker 有 extract-worker / user-extract-worker / vcs-sync-worker
- [ ] `hooks/` 內沒有 `quick-extract.py`、`wg_atom_observation.py`（已刪）；`commands/` 已刪（併入 `skills/`）
- [ ] `skills/` 的 active skill 數與 `skills/_skill_index.json` 一致；`skills/_archived/` 放 dormant 的 init-roles / conflict-review
- [ ] `lib/atom_index_json.py` + `memory/_atom_index.json` 存在；`memory/_meta/taxonomy.json` + `forbidden-phrases.json` 存在
- [ ] 核心 atom 已階層化在 `memory/<範疇>/`，`memory/` 根目錄無平鋪 atom；`taxonomy.gate_enabled=true`
- [ ] `workflow/config.json`：`vector_search.global_layer="bm25"`、`bm25_min_score=7.0`、`fusion="rrf"`；無 `codex_companion.subprocess_timeout` 死鍵；`ollama_backends` 在 `vector_search` 底下
- [ ] `tools/workflow-guardian-mcp/server.js` 暴露 8 tool（atom_write / atom_promote / atom_move / atom_edit_meta / atom_retire / anti_evasion_report / knowledge_harvest_report / memory_search）；`workflow/config.json` 有 `harvest`、`vcs_sync`、`review`、`roles.ad_group_map`、`org_memory` 區段（舊鍵 `self_iteration.auto_commit_promotions/auto_push_promotions` 由 `vcs_sync` 接管）
- [ ] `tools/codex-companion/judge_backend.py` 存在；無 codex CLI 的環境確認 `claude` 可被找到（備援裁判）
- [ ] Stop hook 只掛 guardian / codex_companion / lang_guard（無 quick-extract）
- [ ] 升級到 scope 分層後，各專案的存量記憶要整理一次（現況做法見 `TECH.md` §4.6「存量專案的 scope 整理」）

舊升級步驟（供對照）：`cd ~/.claude && git pull` → `python tools/fix-hook-python.py` 重驗直譯器路徑 → `python tools/merge-atom-index.py --install`（可選；hook 會在下一次合併類 git 指令前自動裝）。pull 本身卡在索引三檔衝突時 `python tools/merge-atom-index.py --resolve` 後 `git rebase --continue`（`GIT_EDITOR=true` 可免開編輯器）。

## V2.21 Phase 4：現有資料遷移
- `migrate-v221.py`（tools/）：_AIAtoms/*.md + 個人 memory/*.md 合併 → {project_root}/.claude/memory/
- 舊 MEMORY.md 改指標型（Status: migrated-v2.21）
- project-registry.json 自動更新
- 已遷移：三個專案（各自的專案層）

## V2.21 Phase 3：專案自治層建置
- `init-project` skill Step 6 建立 `.claude/` 結構（memory/, hooks/, .gitignore, MEMORY.md 模板, project_hooks.py delegate 模板）
- `_call_project_hook()` subprocess 隔離呼叫（5s timeout, 全例外吞噬）
- `handle_session_start` 末尾呼叫 on_session_start delegate

## V2.21 Phase 2：Project Registry + 路徑切換
- `register_project()` SessionStart 自動呼叫
- `get_project_memory_dir()` 新路徑優先（{project_root}/.claude/memory/）
- `find_project_root()` 加 `.claude/memory/MEMORY.md` 辨識
- _AIAtoms merge 邏輯移除

## V2.20：路徑集中化 + bug 修復
- wg_paths.py 路徑集中化
- Bug 修復 C5~C7, W8~W13

## V2.18：Section-Level 注入 + Trigger 精準化
- V2.17 全功能 + Section-Level 注入 + Trigger 精準化 + 規則精簡 + 反向參照自動修復

## 歷史決策
- 記憶檢索統一用 Python（Node.js memory-v2 已於 2026-03-05 退役）
- Stop hook 只保留 Guardian 閘門
