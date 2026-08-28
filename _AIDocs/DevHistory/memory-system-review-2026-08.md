# 原子記憶系統三方比對評估 — 自家設計 × CC 原生記憶 × 業界主流（2026-08-28 判讀）

> 裁決：**架構方向正確、不推倒**（三路檢索＋RRF＋活化＝業界已實證主流）。真正的弱點在**注入端曾被預算閘掐死**（已修）與**積累端多段停產、萃取物無出處**（待辦）。
> 本檔為評估紀錄；as-built 事實逐項以本機檔案核對（檔案:函式），業界／原生依據只引路徑不重述。

## 1. 判讀目的與範圍

- **目的**：使用者 2026-08-28 質疑「記憶注入變弱」，查證修復後，回頭問一個更大的問題——這套自製系統的**核心設計理念**放在 2026 年的 Claude Code 原生記憶與業界做法旁邊，哪些站得住、哪些該補、哪些該改。
- **範圍**：`~/.claude` 原子記憶系統的檢索／注入／積累／回饋四段；CC 原生 auto-memory 與 hooks 接點；業界公開研究與產品（Zep、Mem0、Mastra、claude-mem 等）。
- **不在範圍**：PAN 閘門（已有 [pan-deny-judgement-2026-08-06.md](pan-deny-judgement-2026-08-06.md) 終局判讀）、多使用者治理（USER.md 明示當前非此狀態）。
- **證據等級**：本機事實＝實證（Read/Grep 核對）；業界數據＝引述（來源見 §6）；「待確認」項＝推測，明標。
- **判讀方法**：先把系統自述（`TECH.md`）逐條對到實碼，確認「說的」與「做的」一致，再拿一致的部分去比原生與業界；自述與實碼不符者直接列進 §4.4「該修正」，不拿來比。三方比對只比**同一面向**（真源、跨專案、檢索、新鮮度、注入、積累、信任、回饋、可觀測、部署），避免拿自家強項比別人弱項。

## 2. 三方比對表

| 面向 | 原子記憶系統（as-built） | CC 原生（2026-08） | 業界主流（2026-08 調查） |
|------|------|------|------|
| 真源型態 | Markdown atom + `_atom_index.json` 機器索引；每顆有 Trigger/Confidence/Related | `projects/<slug>/memory/MEMORY.md` + 自由 md | Markdown 或 DB 真源皆常見，重點在索引層 |
| 跨專案 | 有：`memory/<範疇>/` 全專案注入；跨專案 alias 掃描（`ups_search.py` 上限 20 專案、trigger ≥2 命中才收） | **無**：記憶綁 project slug | 多為使用者級／組織級 scope，跨專案是標配 |
| 檢索 | trigger（ASCII 詞界／CJK 子字串）→ BM25（`bm25_min_score` 7.0、top 3、trigger ≤2 命中才跑）→ vector（專案層補充）→ RRF k=60 × `exp(0.25·activation_rank)` | 只載 MEMORY.md 前 200 行／25KB，其餘靠模型按需 Read | hybrid BM25+vector+RRF 為共識（Zep/Mem0/memsearch）；cross-encoder rerank 再進一步 |
| 時間／新鮮度 | ACT-R activation `ln(Σt^-d)`、d 個別化；`supersedes` 過濾 | 無 | 決定性新鮮度規則勝 LLM 判斷（82% vs 18%）；衰減「減量不提準」 |
| 注入 | 每 prompt 主動注入；hot/cold、同題去冗、三態 ok/fallback/skip、`TURN_BUDGET_LIMIT` 1200、總額 1000/2000/3000 依 token 分級 | 無主動注入（prompt 本身除外） | 社群共識每 prompt ≤6 條、SessionStart ~1,200 tok；context-rot 研究：單一干擾項即傷 |
| 積累 | 顯式策展 `atom_write` 為主；自動萃取 L0→L1 qwen3→L2 gemma4、conf ≥0.92 直寫／0.70–0.92 pending／<0.70 丟；per-turn capture、session_end flush 已停產 | 模型自己決定寫 MEMORY.md，無品質閘 | 原文勝萃取物（67.4 vs 45.4）；入場閘以內容型別先驗最有效 |
| 品質／信任 | [臨]→[觀]→[固]；晉升靠效用 Wilson 下界 ≥0.6（z=1.28、n≥3）；write-gate 去重 `dedup_score` 0.8；3KB 硬拒線 | 無 | 多數產品無分級；Mastra 以固定前綴觀察式記憶取勝（LongMemEval 94.87） |
| 回饋迴路 | access sidecar（read_hits/useful/used_fail/Wilson/decay）、rescue-log、recall-miss、effect-report、health-weekly、followups 回訪 | 無 | 多數只有「存了多少」，缺「用了多少」（SuperBrain：8,785 條零自動浮現） |
| 可觀測性 | JSONL audit、`Logs/injection-turns.jsonl`、`[Context budget: x/y | trim]` 尾行 | 無 | 產品級多有 dashboard，開源多無 |
| 部署 | 全本地：Ollama gemma4:e4b / qwen3:1.7b、LanceDB | 內建 | 多數雲端 API |

## 3. 原子系統設計理念與管線（as-built 摘要）

一句話講這套系統：**LLM 的 context window 是工作記憶，長期記憶靠外掛**——把知識切成一顆顆帶關鍵字（Trigger）的 Markdown 卡片（atom），每次使用者打字時由 hook 翻卡、挑最相關的幾顆塞進 context；用過有效就加分、久沒用就淡出、反覆驗證才升信心等級。設計重心明顯偏「取用端」（檢索與注入佔了絕大多數程式碼與量測），「積累端」則以人（Claude 顯式 `atom_write`）為主、機器萃取為輔。

### 3.1 六原則（`TECH.md` §1，已核對）

精確度>token 節省；漸進信任；最小侵入（全走 hooks，settings.json 9 事件：SessionStart/UPS/PreToolUse/PostToolUse/PreCompact/PostCompact/PostToolBatch/Stop/SessionEnd）；雙 LLM；可審計不刪只歸檔；對齊原生。治理鐵律 Native-first 與「fail-open 必浮訊號」（`rules/core.md`）。

### 3.2 分類與 realm

atom 只住 `memory/<範疇>/[Lv2]`，Lv1 閉合清單在 `memory/_meta/taxonomy.json`（`core` 節，含 slug/aliases/sub/terms 詞庫）；`atom_write(mode=create)` 無 domain 拒寫、無 Else。realm core/local 由路徑推導（`lib/atom_locations.classify_realm`）；`realm.llm_fallback.enabled=false`，只跑決定性詞庫。

### 3.3 注入管線（每 prompt）

1. `handlers/ups_search.py:collect_matched_atoms` — 索引組裝（global + project）→ 跨專案 alias（`count_trigger_hits ≥2`）→ trigger → BM25（`len(matched) ≤2` 才跑；`wg_atoms.BM25_MIN_SCORE_DEFAULT=7.0`、`bm25_top_k=3`）→ vector（`_semantic_search`，enrichment 模式只取專案層）→ supersedes → `rrf_fuse`（`RRF_K_DEFAULT=60`、`RRF_ACTIVATION_GAIN=0.25`；`fusion:"legacy"` 可回退）。
2. `wg_atoms.compute_activation` — ACT-R `ln(Σ t_k^-d)`，無 access 紀錄回中性 0.0（非最低分）；`compute_injection_rank` 再減分心懲罰 `w·log10(read_hits+1)·(1−lb)`，核心策展 atom 豁免。
3. `handlers/ups_inject.py:assemble_injection` — `classify_hot_cold`（trigger 恆 hot）→ 同題去冗 `redundant_with`（trigger 精確重疊 ≥`min_shared_triggers` 3 → 節錄）→ 三態 vs `wg_core.TURN_BUDGET_LIMIT=1200` → `spread_related` + `_filter_related_by_relevance`（`max_related` 6）。
4. `wg_core.compute_token_budget` — `TOKEN_BUDGET_TIERS=((15,1000),(80,2000))`、超過 3000，依 `_estimate_tokens`（中文 1.5 tok/字）分級；超支由 `wg_atoms._truncate_context_by_activation` 依 activation 高→低回填，犧牲者留 ≤3 行指標（`injection.truncated_pointer_max`）。

### 3.4 積累與回饋

- 萃取：`hooks/user-extract-worker.py` conf 路由（≥0.92 confirm／0.70–0.92 `_pending.candidates`／<0.70 skip）；`response_capture.per_turn.enabled=false`、`session_end_flush.enabled=false`（2026-07-01 停產，理由「write-only 死路、0 下游消費」）；失敗萃取與 episodic（TTL 24d，`wg_episodic.py`）保留。
- 回饋：`lib/atom_access.py`（`WILSON_Z_DEFAULT=1.28`、`PROMOTE_LB_DEFAULT=0.6`、降候選 n≥5）；`Logs/rescue-log.jsonl`、`Logs/recall-miss.jsonl`、`Logs/injection-turns.jsonl`；`tools/memory-effect-report.py`、`tools/health-weekly.py`、`tools/followup-check.py`（`workflow/followups.json`）。
- MCP 5 tool：atom_write／atom_promote／atom_move／atom_edit_meta／anti_evasion_report。

## 4. 優點／缺點／可補強／該修正

### 4.1 優點（站得住）

| # | 點 | 依據 |
|---|----|------|
| 1 | 三路檢索＋RRF＋活化調節 = 業界共識，且本機已實證（Recall@1 34→53.6%、MRR 0.584→0.709，`tools/memory-eval/` 223 條回歸集） | 本機 atom「檢索融合與回歸集調參」；業界 §6-1 |
| 2 | 顯式策展＋信心分級避開自動萃取噪音——claude-mem v3「全塞污染」正是反例 | §6-1 社群案例 |
| 3 | rescue-log／useful／used_fail 是「記憶真的被用到」的直接證據，業界普遍缺此軌 | `Logs/rescue-log.jsonl`、`lib/atom_access.record_usefulness` |
| 4 | 全本地、無雲、可審計 | `config.json vector_search.ollama_backends` |
| 5 | 每回合主動注入直接對治「有存無用」（SuperBrain 8,785 條零浮現） | §6-1 |
| 6 | 跨專案記憶是原生完全沒有的能力 | §6-2 |

### 4.2 缺點（實證）

| # | 點 | 證據 | 狀態 |
|---|----|------|------|
| 1 | 注入冗餘：一句「git 收尾」同時 3 顆同題全文 ~1,000 tok | 2026-08-28 實機探針 | **已處理**（commit `6cd4353` 同題去冗） |
| 2 | 注入曾被預算閘掐死：每回合 1.0 顆全文、熱 atom 全文率 22% | `memory-effect-report` 近 14 天 | **已處理**（`3a4809c`、`fc1a888`） |
| 3 | 萃取物無出處：atom 不指回 transcript／原文，無法回讀驗證；業界數據原文勝萃取物 | atom frontmatter 無 provenance 欄（`_AIDocs/Architecture.md` §metadata 列表） | 待辦 |
| 4 | 活化衰減只能減量不能提準——與 2605.08538 結論一致；本機亦只當排序調節不當過濾 | `compute_injection_rank` | 認知正確，無需改 |
| 5 | 積累端弱於注入端：per-turn capture、session_end flush、Confirmations 軌三段停產；自動晉升唯一路徑 Wilson 軌 | `config.json response_capture.*._disabled_2026_07_01`；`TECH.md` §8.2 註 | 待辦（見 4.3-5） |
| 6 | 量測多為定性：缺跨 session 保留率、注入→採用率等硬指標；effect-report 只有曝光／效用 | `tools/memory-effect-report.py` 三清單 | 待辦 |
| 7 | 自承限制：跨 session first-write race、realm LLM fallback 關 | `hooks/wg_coordination.py`、`config.json realm` | 已知、defer |

### 4.3 可補強（依投資報酬排序）

排序原則：先修「已量到的痛」（冗餘、預算），再補「業界證明有效且本機基礎已在」的項（出處、rerank、型別先驗），最後才是需要新機制的（整併）。每項只做到能量測為止，不預建。

1. **同題去冗**——已做。
2. **atom 附 provenance 指標**：frontmatter 加 `Source: <transcript path>#<turn>` 或 commit hash；`atom_edit_meta` 已能外科改 frontmatter，成本低。對治 4.2-3。
3. **本地 cross-encoder rerank**：業界 5/6 指標最佳；本機已有 Ollama 通道，可在 RRF 後對 top-N 做 yes/no 相關判斷（qwen3:1.7b），但每 prompt 多 200–500ms，需先量 UPS 30 秒上限內的延遲預算。
4. **入場閘內容型別先驗**（A-MAC）：`taxonomy.json terms` 詞庫已是雛形，補「型別→預設信心／預設 hot-cold」表即可。
5. **背景週期整併（sleep-time consolidation）**：取代已停產的 per-turn／session_end 兩段，改為週健檢時對 `_pending.candidates` + episodic 做一次合併／晉升／封存，讓積累端有唯一、可觀測的入口。

### 4.4 該修正

| # | 項 | 狀態 |
|---|----|------|
| 1 | 橋接檔 `projects/<slug>/memory/atom-index-bridge.md` 13/13 路徑失效 7 週 | **已修**（`db899d2`，接上 `sync-memory-index --write` 尾端重產） |
| 2 | 預算三閘：硬頂 500→1200、裁切改回填、分級改依 token | **已修**（`3a4809c`、`fc1a888`） |
| 3 | 新鮮度／supersedes 必須決定性（業界 82% vs 18%）：本機 `_SUPERSEDES_RE` 為規則式，符合；但 `memory-conflict-detector` 裁決含 Evidence 等級→recency，是否有 LLM 介入待確認 | 待確認 |
| 4 | JIT 參考文件 `memory/_reference/internal-pipeline.md` 寫「Intent→Trigger→Vector Search→Ranked Merge」、`DevHistory/memory-pipeline.md` 同；實碼為 trigger→BM25→vector→RRF。此檔每輪注入 250 tok，錯的管線描述會誤導模型 | 待更新（本檔不改） |
| 5 | prompt cache 批評：每輪 additionalContext 變動使該輪不在 cache——但新回合內容本就不在 cache，前綴仍命中，影響有限 | 不需改 |

### 4.5 收束

診斷：取用端（檢索＋注入）經 2026-08-28 三處修正後已回到設計初衷「精確度>token 節省」；積累端是目前最弱的一段——三條自動管線停產後，新知識幾乎只靠 Claude 當下記得寫 `atom_write`，而寫進去的東西又指不回原文。

決策點（單一）：**下一步是否啟動「provenance 指標＋週期整併」這一組積累端補強**（§4.3-2 與 §4.3-5，兩者共用 `_pending.candidates` 入口）。建議做，理由：成本低（frontmatter 一欄＋健檢一步）、直接對治 §4.2-3/5 兩個待辦、且業界原文>萃取物的數據替它背書。缺的資訊：回訪 2026-09-04 的一週真實數據——若注入端門檻未過，先回頭修注入，不動積累。

## 5. 數據附錄

| 指標 | 修前（近 14 天） | 修後（2026-08-28 當日） | 回訪門檻（due 2026-09-04） |
|------|------|------|------|
| 完整注入 atom／回合 | 1.0 | 3.5–3.67 | ≥2.5 |
| 熱 atom 全文率 | 22%（87 命中／19 全文） | 58–65% | ≥55% |
| 中文中等問句 | 1 全文／5 丟 | 4 全文／0 丟 | dropped/回合 ≤1.0 |
| 高曝光零使用 atom | 0 | — | ≤0 |

回訪登記：`workflow/followups.json` id `injection-budget-2026-08-28`（since 2026-08-29，排除調校當日探針）。檢索品質基線：Recall@1 53.6%、MRR 0.709（`tools/memory-eval/`）。

## 6. 參考

1. 業界調查：[_AIDocs/Research/agent-memory-industry-survey.md](../Research/agent-memory-industry-survey.md)
2. CC 原生記憶／hooks／MCP 查證：[_AIDocs/ClaudeCodeInternals/cc-native-memory-hooks-mcp.md](../ClaudeCodeInternals/cc-native-memory-hooks-mcp.md)
3. 注入預算調查：[injection-budget-investigation-2026-08.md](injection-budget-investigation-2026-08.md)
4. 本機規格：[TECH.md](../../TECH.md)、[_AIDocs/Architecture.md](../Architecture.md)
5. 相關 atom：`_AIDocs/_atoms/MemDev/注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產.md`、`activation負值不是負相關-…`、`檢索融合與回歸集調參-rrf-min-score-定案`
