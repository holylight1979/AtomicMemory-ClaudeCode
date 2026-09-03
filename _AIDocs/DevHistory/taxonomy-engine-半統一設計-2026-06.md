# 分類／去蕪統一引擎（半統一）設計與執行紀錄 — 2026-06

> **歸檔狀態（2026-09-03 自 `memory/_staging/next-phase-draft-taxonomy-engine.md` 移入）**：
> - 核心側已落地且仍在用：`lib/atom_classify.py`（`score_by_lexicon` 單一計分源 + `classify_taxonomy` + `classify_project_atom` 逃逸閘）、`lib/atom_locations.py::is_core_protected_name` 單源、晉升閘 `ea5ab32`。
> - 已停產：DedupStage 去蕪引擎（§3／§9）於 commit `755ce07`「自動萃取層淨值審查」整套拔除（write-only 死路）；§11 Q1／Q2 隨之作廢。
> - 未執行、屬專案 session：Phase B（`c:/Projects/.claude/tools/classify-project-atoms.py` 227 行退 thin shim 呼核心）與 Phase C（其他專案複本）；Q4（realm sweep LLM fallback 誤降）未根治。要做時以本檔 §2／§7／§11 為設計依據，在專案 session 開工。
> - 以下為原文，內含的「待做」「本 session」等時態一律以上述狀態為準。

---

# 階段計畫：分類/去蕪＝核心通用邏輯（統一引擎 + 多層 taxonomy + 去蕪）

> 來源：2026-06-30 多輪設計 + 4 個工作流 + 對抗性壓測 + SGI 真實記憶實證。
> 狀態：**架構定案（有條件可行/半統一）；Step 0 + Phase A（classify_realm 退核心）+ 兩個必修核心地基（晉升閘 `ea5ab32` / 跨 realm 逃逸閘核心地基 `c8ec0f4`）+ DedupStage 去蕪引擎與 core SessionEnd 接線（§3，core live hook ✅ 已接、project 端未接）已落地；Phase B/C 專案端遷移待做**。本檔為跨 session 執行 SoT，自足。
> 範疇：local realm / MemDev。**舊版（game_taxonomy 為主 + 三路 jury）已被本版取代，勿據舊版。**

---

## ⚑ 核心方向與不可違反約束（任何接手 session 先讀，防偏離）

**為何做**：分類/去蕪＝原子記憶系統的**核心通用邏輯、單一來源不漂移**；各專案只給 `_taxonomy.json` 當「範圍基礎」，邏輯不複製進專案（bug 根源＝N 份複本各自漂移、噴破碎 atom）。服務 user 三大目標：① 歸既有類/否則建新類+索引 → **關聯記憶注入更精準** ② **开枝散叶记重点**：不是什麼都記，越深的細節在「深度追錯 / 大幅改造架構」時要能浮現「**可扭轉 AI 判斷、或 AI 最易誤判繞遠路**」的關鍵報告 ③ **scope 感知**：高效隨時感知範疇、避免過度限縮、避免飄移/幻覺。

**不可違反（6/24 污染覆轍，user 極度在意「別把未整理碎片亂塞亂丟」）**：四軸物理分離——軸1 歸夾(folder)可全自動，但軸2 晉升 [臨]→[觀] / 軸3 學 realm 詞庫 / 軸4 進注入+git **各自閘門不得被軸1 連帶觸發**；draft 永遠待在 `_drafts/` 牢籠（cage_assert fail-closed）、未確認碎片不入索引/注入/git；不污染 realm 詞庫；不繞過 [臨]→[觀] 確認閘；content 不當 filename。

**設計原則（對抗性壓測定案，別重新發明 / 別過度工程）**：**半統一**——只統一計分骨架 `score_by_lexicon`，決策語意（realm vs taxonomy）保持 **adapter 並存**，別硬揉成一個 schema（=泥球）；user 鐵則只要「LOGIC 單源不漂移」，不是把 realm 硬塞進 taxonomy。**多層樹**——職能根（程式/企劃/美術…伺服器級**跨專案核心框架**）是 ROOT、有核心價值；專案細節是其下**更深子樹**（程式/客戶端/Unity/CSharp…），**不是二選一**。**別憑截斷/採樣斷言品質**——判去蕪/完整性要讀完整內容或全量掃描（[[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]）。blocker 宣稱先實證；動任何 repo 前先確認 working tree 乾淨。

---

## 0. 真實狀態（實證校正，load-bearing）

| 項目 | 早期口徑 | 實測真值 |
|---|---|---|
| SGI draft 池 | 142 | **75**（142 含已分類歷史口徑）|
| draft 品質 | 「不是垃圾」（我憑 excerpt 誤判）| **40% 截斷損壞或近重複**（讀完整內容實證；GM Blocker 5 份、RebuildBlobAsync 4 份）|
| 去蕪真問題 | is_real 低價值 | **截斷 + 近重複**（確定性可測），非主觀價值 |
| SGI scope | 概念風險 | **曾爆發 42 顆 shared 誤標 global，已修** |
| 主記憶近重複 | — | **0**（84/88 curated atom 零重複 → 去重不作用於主記憶）|
| 分類邏輯 | — | **N 份專案複本各自漂移**（classify-project-atoms.py），bug 根源 |

> 我的失誤已記 atom [[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]：憑 excerpt 斷言品質、未讀完整內容。

---

## 1. 架構裁決：半統一（對抗性壓測結論）

**user 鐵則**：分類/去蕪是**核心通用邏輯、單一來源不漂移**；各專案只給 `_taxonomy.json` 當範圍基礎。
**對抗性裁決**：realm 軸（core/local + 保護清單 + lexicon 自學）與 taxonomy 軸（subsystem domain）是**正交兩範式，不可硬揉成一個 schema（=泥球）**。正確＝**統一機械骨架、保留決策語意為 adapter**。

| 層 | 內容 | 統一？ |
|---|---|---|
| **L1 純計分核心** | `score_by_lexicon`（兩端實證 ~100% 同構：子字串掃 name+trigger、name 權重10>trigger1、累分、override、tiebreak 為注入 callable）+ `_clean_segment` path 清洗 | **真能統一**（換 config 即可；專案層白賺目前缺的 path guard）|
| **L2 決策策略** | `RealmStrategy`(core) vs `TaxonomyStrategy`(project)：見下表 | **必須 adapter 並存** |
| **L3 共用 effect** | `relocate_atom`（含凍結 Confidence）/ `collect_unclassified` / `resolve_scope`(per-env) | **真能統一** |

**L2 差異（不可統一，否則丟資訊）**：

| 維度 | RealmStrategy(core) | TaxonomyStrategy(project) |
|---|---|---|
| 判定軸 | core-vs-local（注入範疇）| technical-subsystem domain |
| 無命中 | **不動留原地**（安全預設 core）| 主動落 `_unclassified` 可見夾 |
| 保護硬擋 | 有 PROTECTED_* | **無（永遠 null）**|
| LLM fallback / learned-lexicon | 有 | **無（專案零 Ollama 依賴）**|
| tiebreak | sorted-domain 序 | priority 數值序 |

---

## 2. 核心引擎 `lib/atom_classify.py`（首版＝最小治本，決策點 A）

- `score_by_lexicon(name, triggers, lexicon, *, name_w=10, trig_w=1, tiebreak) -> (bucket, matched, score)`
- `RealmStrategy` / `TaxonomyStrategy`（共用 L1 計分、決策語意各走各的）
- `relocate_atom(name, new_rel, mem_dir, scope, triggers)`：src==dst no-op → shutil.move(含 .access.json)→ `lib.atom_index_json.upsert_atom` → regen 鏡像。**一律凍結 Confidence**（堵晉升閘漏洞）。
- `resolve_scope(text, idx_entry, env)`：body `- Scope:` 行優先、index fallback **per-env**（project='shared'/core='global'）→ 杜絕 42 顆漂移覆轍。
- `detect_env(cwd)` 純 path 前綴三態：core(~/.claude→realm)／project(.claude/memory/ 且非 ~/.claude→taxonomy，無 _taxonomy.json=no-op skip)／storage 三態不可建模成二元。
- `EnvConfig` 薄外殼 + 兩 adapter：`load_core_config()`（投影 LOCAL_REALM_* hardcode 常數，**詞庫仍 hardcode 在 lib 保 js mirror parity，adapter 只讀取轉接不搬家**）/ `load_project_config(_taxonomy.json)`。

**多層 taxonomy 零改碼**：domain 被當純路徑片段（`scope_dir/domain` + `mkdir(parents=True)`）→ `_taxonomy.json` key 改 `"Server"`→`"程式/伺服器"` 即造多層夾、索引寫多段 path、注入 `**/*.md` 照命中。**folder 不參與注入命中**（只導覽/範疇）。

---

## 3. 去蕪 DedupStage（全新能力，與確定性 classify 主路正交，物理隔離）

> **狀態（2026-06-30）✅ 引擎 + verify + core 接線已落地**：`lib/dedup_stage.py`（複用 Phase 0 牢籠原語
> `lib.taxonomy_jury.cage_assert/_drafts_root`，不重造）+ `hooks/verify/verify_dedup_stage.py`（26）
> + `hooks/verify/verify_session_end_dedup_wiring.py`（5）（run_verify 651→**688 passed**）。
> **✅ 已接線 core SessionEnd 全生命週期**（user 眼驗 dry-run 批准）：`session_end.py::_dedup_sweep_core()`
> = ① `sweep_drafts(env=core)`（只清截斷不去重）+ ② `purge_expired_trash`（14 天閘硬刪過期 trash＝唯一硬刪）；
> fail-soft 吞例外不弄垮 SessionEnd。實測真 SessionEnd 已 soft-delete 1 真截斷 draft（可逆）。
> commit `ed51b48`(引擎)+`20dd4d2`(atom)+`604e898`(sweep接線)+`20c698e`(changelog)+`f3dadfe`(purge接線)。
> **DedupStage core 側＝100% 完成（偵測→soft-delete→14天可逆窗→時間閘硬刪全閉環）**；
> **project 端接線＝Phase B 另議**（user 同意先只接 core）。

信任模型不同（classify=確定性 term-match；dedup=可逆 soft-delete），**絕不混入 classify 入口**：
- **只在 `_drafts/` 牢籠運作**（cage_assert fail-closed；CI grep 鎖死禁索引寫入/詞庫學習符號）。draft 生命週期 auto-capture→by-class/<類>→_trash 全在 `_drafts/`。
- **截斷三訊號** `is_truncated_fragment()`：①行內未閉合(奇數反引號/未閉 fence/括號) ②連接符(=(:、，)收尾 ③`## 行動` 佔位符。**須三訊號全中**才判（`## 行動` 也可能是合法 atom 真實段）。**禁用全文末字**（主記憶 26% 假陽性）。✅ **80 份真實 draft 實證**：訊號③ 80/80（builder 統一附加→單獨無意義，其真正用途是排除有真實行動項的 curated atom）、三訊號全中 1/80（真截斷）；`task-23-pitfall`（未閉反引號但 `K` 收尾非連接符）正確留下＝高精度低召回設計（caged fragment 留著無害、誤刪才有噪音）。
- **per-env dedup**：project draft 走叢集去重；core 主記憶走碎片吸收（近重複=0，不去重）。✅ **首版＝substring subsumption（零知識損失保證）**：只刪「內容字元序列完整內含於某保留者」者（含完全相等）；**paraphrase 換句話說的近重複（如 3 份不同措辭講 atom-move 同一缺陷）刻意不自動去**——需 LLM 語意判斷，違 dedup=確定性+可逆 信任模型→留待人工 /refile。⚠ 故 §0 的「41% 實證可省」**首版未達成**（那是 LLM 級語意去重；本版只收 literal 子集冗餘，安全優先）。paraphrase 級語意叢集＝**後續可選增強**（須另設機制、不混入確定性主路）。
- soft-delete 到 `_drafts/_trash/`（+ `.trashmeta.json` sidecar 記原位/時戳/理由；14 天時間閘 `purge_expired_trash`＝唯一硬刪路徑 + `restore_from_trash`/refile 救回，禁即時硬刪）。
- **後端離線→draft 留原地不動**（DedupStage 全確定性、零 LLM 依賴，「後端」指 by-class LLM jury 步，與本 stage 正交）；SessionEnd sweep 持單一 file-lock（`_drafts/.sweep.lock`，非阻塞 NBLCK/LOCK_NB）拿不到即 skip（`status=skipped-locked`、零搬動）。

---

## 4. 兩個獨立必修（與統一引擎正交，可先做）

> **狀態（2026-06-30）✅ 兩項核心地基已落地**：晉升閘漏洞 commit `ea5ab32`（晉升掃描面串 `_autocapture_unconfirmed_from_text`）；跨 realm 逃逸閘**核心地基** commit `c8ec0f4`（`is_core_protected_name` 單源 + `classify_project_atom` 注入式閘，**專案端 /refile 接線仍 Phase B**）。下列為原始問題描述，保留供溯源。

- **晉升閘漏洞（去蕪上線前必堵）**：實證 `_self_iterate_atoms`（[hooks/wg_atoms.py:1948](hooks/wg_atoms.py#L1948)）晉升掃描面以 `confirmations>=threshold` 晉升、**無 `_is_unconfirmed_autocapture` 過濾**（該過濾只在 line 1768 sweep 路徑）→ 14 顆佔位符 auto-capture 碎片已被算晉升。修：晉升掃描面加該過濾 + relocate 凍結 Confidence。
- **跨 realm 逃逸閘（遷移前必補）**：SGI `_unclassified/` 躺著 feedback-* 跨專案規則 atom、MemoryMeta self-admit 誤捕。專案層無保護→誤捕固化。修：跨 realm 邊界比對核心 PROTECTED_PREFIXES（feedback-/atom-/decisions/workflow-），命中送人工 /refile 而非歸業務夾。

---

## 5. 分階段遷移（每階段執驗上P、不破 SGI 活躍 repo + 其他專案）

> **狀態（2026-06-30）**：Phase 0.5 + Phase A ✅ 已落地；Phase B/C/D + DedupStage 待做。

- **Phase 0.5**（前置）✅：Phase 0/1 牢籠檔（`lib/game_taxonomy.py`/`lib/taxonomy_jury.py`/`lib/taxonomy_classify.py` + `verify_taxonomy_caging.py`/`verify_taxonomy_classify.py`）**已 git-tracked/committed**（核實 2026-06-30，原「仍 ??」已解：皆 tracked）。
- **Phase A**（零行為改變、純抽取）✅ commit `208344b`：`lib/atom_classify.py` 已建（`score_by_lexicon` + `classify_taxonomy` + `classify_project_atom`）；`classify_realm` 退薄包裝委派 `score_by_lexicon`。**verify byte-equal 對拍**：核心 lexicon == classify_realm（hand-rolled oracle）、**server.js base 子集 py↔js 真 node parity**（test_17/22）、SGI 全 atom == 舊輸出（test_taxonomy_byte_equal_all_sgi_atoms，SGI 在機才跑）。SGI 零感知。**注**：`classify-project-atoms.classify` 退薄包裝屬 Phase B（專案 repo，未動）。
- **Phase B**（治本，刪漂移源）：`classify-project-atoms.py` 266 行→~12 行 thin shim 呼核心；`project_hooks._auto_classify_shared_atoms` import 核心。SGI 先 dry-run 比對 by-domain==舊輸出才 --apply。**短詞命中(s21/h-7/bag/present/fresh-d)逐 atom 人工抽查**（子字串無 word-boundary）。每 Phase 留還原路徑。
- **Phase C**（deprecate）：掃所有專案複本→全換 thin shim/直接 import；各專案只剩 `_taxonomy.json`。先 SGI（有人盯）→觀察→滾其他。無 _taxonomy.json 專案=no-op。
- **Phase X**（獨立並行）：晉升閘漏洞 + 跨 realm 逃逸閘。
- **Phase D**（延後、user 認可才推）：生命週期收斂（project SessionStart→SessionEnd）——可感知行為改變 + failsafe 可見度降，不在治本同時疊加。

---

## 6. 必守不變式（CI/固定邏輯守）

- **INV-LOGIC-SINGLE-PY-SOURCE-JS-MIRROR**：score_by_lexicon 唯一 py 計分源，但 core 端 server.js mirror 仍需同步、parity test 對 base 子集 byte-equal 守門（**誠實標「py 單源+js mirror」，勿宣稱跨語言單源**）。
- **INV-STRATEGY-ISOLATION**：Realm 的保護/LLM/learned/通用詞黑名單絕不下放成 Taxonomy 必填；Taxonomy 的 protection/llm/learned 永遠 null。
- **INV-DEFAULT-SEMANTICS-PER-STRATEGY**：default_bucket nullable；realm 無命中=留原地、taxonomy 無命中=落 _unclassified，不統一成單一常數。
- **INV-SCOPE-FALLBACK-PER-ENV**：resolve_scope fallback 帶 env 分支（project='shared'/core='global'）。
- **INV-PROMOTION-GATE-ON-SCAN-FACE**：_self_iterate_atoms 晉升掃描面(1948)加 is_unconfirmed_autocapture 過濾；搬入分類夾前凍結 Confidence。
- **INV-DRAFT-STAYS-CAGED**：DedupStage 終點 path 必含 _drafts；物理零 import write_atom/upsert_atom/append_learned_terms。
- **INV-DELETE-IS-SOFT-AND-REVERSIBLE**：soft-delete + 14 天閘 + /refile 救回。
- **INV-CROSS-REALM-ESCAPE-HATCH**：跨 realm 邊界對核心 PROTECTED_PREFIXES 反向判定，命中送 /refile。
- **INV-INDEX-PER-ENV-ISOLATION**：relocate 的 upsert 嚴守傳入正確 per-env mem_dir。

---

## 7. 決策點（建議都明確）

1. 統一範圍 → **A 最小治本**（抽 4 純函式 + 兩端退薄包裝，不引入 EnvConfig 三態 strategy 抽象為正式入口；B 半統一結構為長期骨架延後）。
2. js 單源口號 → **B 誠實標「py 單源 + js mirror base 子集 byte-equal」**。
3. 生命週期收斂 → **B 延後 Phase D、user 認可才推**。
4. 短詞 word-boundary → **B 首版保子字串 + dry-run 人工抽查 + override；word-boundary 另開同步改兩端**。
5. 跨 realm 逃逸閘時機 → **B 遷移前先補**。

---

## 8. 三大目標如何達成（user 原始訴求對映）

1. **歸既有類/否則建新類 → 注入更精準**：確定性 term-taxonomy 歸既有 domain；無命中落 `_unclassified` 待補詞畢業（建新類）。**但注入精準度槓桿是 trigger 品質非 folder**（folder 只導覽/範疇）。
2. **开枝散叶记重点**：多層樹（職能根→子系統→具體）+ key_flag 把高槓桿 atom 的 trigger 詞上提到各層 `_INDEX`（≤8，靠 trigger 直命中=hot 全文，非偽造注入特權）。深度錯誤/大改架構的「可扭轉判斷」報告靠此浮現。
3. **scope 感知防飄移**：detect_env 三態純 path 判 scope；分類視野用全 index 不限縮；closed-list + 保護前綴 + cross-realm 逃逸閘防誤捕/幻覺；body=Scope single source 防漂移。

---

## 9. 已完成

- **DedupStage 去蕪引擎（2026-06-30，commit 待填，建在乾淨基線 8701aa5 上）**：
  - `lib/dedup_stage.py`（新）：`is_truncated_fragment`（截斷三訊號全中）/ `resolve_dedup_policy`（per-env：project=截斷清除+叢集去重，core=只截斷清除不去重）/ `find_redundant`（substring subsumption 零知識損失）/ `soft_delete`+`restore_from_trash`+`purge_expired_trash`（可逆 + 14 天閘）/ `sweep_drafts`（非阻塞 file-lock，拿不到 skip）。**牢籠原語複用** `lib.taxonomy_jury`（不重造）。
  - **§9-vs-§1 真相釐清（接手 session 免再查）**：`lib/taxonomy_jury.py`(cage_assert/_drafts_root/relocate_within_cage) + `lib/game_taxonomy.py`(seed slugs/TAXONOMY_CATCHALL) = **Phase 0 牢籠地基，保留複用**（DedupStage 直接 import）。§1「已取代」指的是**舊『atom 分類』走 game_taxonomy-為主 + 三路 jury** → 已被 `lib/atom_classify.py::score_by_lexicon`（確定性）取代；`lib/taxonomy_classify.py`（單後端 LLM jury）是 by-class 分類雛形，**DedupStage 不用它**（去蕪純確定性、禁 LLM）。三者正交。
  - `hooks/verify/verify_dedup_stage.py`（新）：**26 verify 綠**——截斷真/假陽性（含 2 份真實 draft fixture：`跨層引用缺陷`真截斷、`task-23-pitfall`未閉但非連接符收尾→不判）、soft-delete 可逆 byte-identical、cage_assert fail-closed、14 天閘、file-lock skip、per-env 策略、subsumption 零損失、CI grep 禁索引/詞庫符號、sweep 不碰索引/詞庫。
  - 驗證基線：`run_verify.py` **651→677 passed**。working tree 乾淨基線上建。
  - **⚑ 未接線（刻意，待 user 認可）**：`sweep_drafts` 未掛任何 live SessionEnd hook（會對 SGI+他專案活躍 repo 產生可感知行為改變＝Phase D 性質，§5/§7.3 已定「延後、user 認可才推」）。接線時一行 wire-up 即可；接線前先在 SGI dry-run（`dry_run=True` 只算不搬）比對。
  - **⚑ 首版範圍誠實標記**：cluster_dedup 只收 **literal substring 冗餘**，§0「41% 實證可省」的 paraphrase 級語意去重**未達成**（安全優先、禁 LLM）→ 列後續可選增強。
- **本 session（2026-06-30）核心側三治本（core，已 push 雙 remote）**：
  - **Phase A：classify_realm 退核心**（commit `208344b`）：`lib/atom_locations.py::classify_realm` 內聯計分 → 委派 `score_by_lexicon`（realm/taxonomy 共用單一計分源，INV-LOGIC-SINGLE-PY-SOURCE）；決策語意（無命中=core / sorted tiebreak / 段 guard）仍 RealmStrategy；**server.js 零改**（py 單源 + js 手寫 mirror，parity test_17 守）。`verify_atom_classify.py::reconstruct_realm` 翻 hand-rolled 獨立 oracle（不呼 score_by_lexicon）→ byte-equal 對拍維持真 oracle。
  - **必修(a) 晉升閘漏洞**（commit `ea5ab32`）：`_self_iterate_atoms` 晉升掃描面串 `_autocapture_unconfirmed_from_text`（與 sweep 路徑 1768 同源規則、body 全文 adapter，body `- Trigger:` 已實證 byte-mirror index triggers）→ 未確認 auto-capture 碎片 confirmations 達標也不自動晉升。relocate freeze：`set_realm` 走 `move_atom_pair`（純 rename）不重寫 body → Confidence 結構性凍結（已驗）；formal `relocate_atom`「一律凍結」為 Phase B。手動 atom_promote（js）為人工確認路徑、不受限（py-only 自動晉升、無 js parity）。verify=`verify_promotion_gate_autocapture.py`。
  - **必修(b) 跨 realm 逃逸閘核心地基**（commit `c8ec0f4`）：`lib/atom_locations.py::is_core_protected_name`（EXACT+PREFIXES）抽為**單一來源**，classify_realm 保護硬擋退用之（不漂移）；`lib/atom_classify.py::classify_project_atom` = 逃逸閘（前置，escape_protected **注入** 避 cycle）+ classify_taxonomy（後置 pure，INV-STRATEGY-ISOLATION）；命中核心 PROTECTED → `('_refile', ['<cross-realm-escapee>'])`。**專案端 /refile 路由接線 = Phase B thin shim**（本 session 只備核心地基，§7.5「遷移前先補」）。verify=`verify_cross_realm_escape_hatch.py`。
  - 驗證基線：`run_verify.py` **651 passed**（含 test_17/22 真 node py↔js parity）。
- **drift ①②③ 已處理（2026-06-30 後續 session；commit `a6ec085` 乾淨基線 + `8701aa5` 護欄，已 push 雙 remote）**：
  - **① 後設 atom 誤降已還原 + 護**：`品質完整性判定…` + `escalation-hook-…false-fire…`（兩顆跨專案 meta-cognitive atom）被 realm sweep LLM fallback 從 core 誤降 local → `set_realm --to-core` 還原回 `memory/`(core) + 加進 `LOCAL_REALM_CORE_PROTECTED_EXACT`（py+js mirror）防再降。index/catalog/caption 重生（core 17/local 33/MemDev 15）。
  - **② 詞庫污染已清 + 補漏（本機實證為真，非虛驚）**：working-tree `realm-lexicon-learned.json` 確多學 5 概念詞（excerpt/截斷/品質判定/源根驗證/post-mortem，HEAD 37→working 42）→ 退回 HEAD 37 + `_LEXICON_GENERIC_TOKENS` 補這些概念詞 sink 端拒收。（⚠ user 在另一 read-only session 看到「只有 1 詞」與本機 working-tree 對不上，疑不同環境/branch/checkout 落差；本機已逐 key 實證污染存在並清除——若你那邊真只有 1 詞，請反查兩環境是否同步。）
  - **③ confirmations=38 cognitive-patterns**：確認**合法**（真確認 atom 非漏洞），撤出待辦。
  - **⚑ 未解問題（廣義 bug，本 session 僅護 family、未根治）**：realm sweep 的 **LLM fallback 會把「作者置於 core 的跨專案 meta/認知/紀律 atom」系統性誤判 local**（非 auto-captured、作者 realm 意圖未被尊重）；本月已反覆（goal-driven/自己flag/記憶汙染/品質完整性判定/escalation-hook…逐顆補 `PROTECTED_EXACT` = 打地鼠）。**根治方向待議**：(i) LLM classify prompt 補「meta/cognitive/discipline atom core-bias」；(ii) 對 holylight-authored 且詞庫零實例命中的 [臨] atom 預設 defer 不搬（尊重作者 realm 意圖）；(iii) PROTECTED 升級為「family 規則判定」而非逐顆 exact 名單。
- **Step 0（scope bug 治本）**：`classify-project-atoms.py:152` scope 改 body single-source（SGI commit `2bf3d75`）+ SGI 42 顆 scope global→shared（資料修正，未 commit、在你 working tree）。
- **Phase 0（牢籠安全地基）**：`lib/game_taxonomy.py`+`lib/taxonomy_jury.py`+`verify_taxonomy_caging.py`（core commit `741f84a`，10 verify 綠）。
- **Phase 1 雛形**：`lib/taxonomy_classify.py`+`verify_taxonomy_classify.py`（8 verify 綠，待 commit）。
- **核心 drift**：`_distant` 補進 EXCLUDED_DIR_PARTS（sync-atom-index.py）。
- 失誤記憶：[[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]。

---

## 10. 規則連結

- 反 6/24 覆轍：`_AIDocs/_atoms/MemDev/auto-capture碎片sweep汙染詞庫-defer根治.md`、`realm-範疇分區機制-v5.md`。
- 行為：[[feedback-workflow-discipline]]、[[feedback-atom-write-initial-confidence]]（新知識首寫 [臨]）、[[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]。
- 實作完成後 atom 候選：「半統一 score_by_lexicon 核心引擎」「兩個獨立必修」落 MemDev atom（[臨] 起）。
- DedupStage 設計知識已落：`_AIDocs/_atoms/MemDev/dedup-stage-牢籠去蕪設計….md`（[臨]）。

---

## 11. 下一步 / 未解問題（接手先讀；每項皆可回答的具體問句 + 涉及檔 + 已驗狀態 + 禁止假設）

> ⚠ 本 repo（~/.claude）有**並行 session + triage 程序**同時改 realm/atom 檔。動手前 `git status`，
> commit 一律 `git add <指定路徑>` 只收自己範圍；別 `git add -A`。

| # | 問句（待決/待做） | 涉及檔 | 已驗狀態 | 禁止假設 / 先驗 |
|---|---|---|---|---|
| Q1 | **DedupStage project 端要不要接線？** project SessionEnd 接 `sweep_drafts(env="project")` 啟動截斷清除**+叢集去重**。| `<project>/.claude/.../project_hooks.py`（**SGI 在 c:\Projects**，**非 ~/.claude，須 project session 做**；CrossRealmWriteBlock 擋跨域）| core 側已完成可參照；project 側 0% | 動前先 SGI `dry_run=True` 比對；⚠ cluster 首版只收 literal substring，paraphrase 近重複抓不到（實證 0 redundant）——**先答 Q2 再決定要不要接** |
| Q2 | **要不要補 paraphrase 語意叢集？**（atom-move×3 等換句近重複，substring 抓不到）| `lib/taxonomy_classify.py`（已有單後端 LLM jury 雛形）+ 新隔離模組 | 雛形存在、未接 dedup | 必與確定性主路**物理隔離**、仍 soft-delete 可逆、禁寫索引/詞庫（同 DedupStage 牢籠約束）；別把 LLM 判斷混進確定性 classify 入口 |
| Q3 | **Phase B 治本（刪漂移源）何時做？** `classify-project-atoms.py` 266行→~12行 thin shim 呼核心；`project_hooks._auto_classify_shared_atoms` import 核心 | **project repo**（c:\Projects 等）| core 引擎 `lib/atom_classify` 已備（Phase A `208344b`）；project shim 0% | **須 project session**；SGI 先 dry-run 比對 by-domain==舊輸出才 --apply；短詞命中(s21/h-7/bag…)逐 atom 人工抽查 |
| Q4 | **廣義 realm-sweep bug 要走哪個方向根治？**（LLM fallback 系統性誤降跨專案 meta/認知/紀律 atom，本月逐顆打地鼠）| `hooks/wg_atoms.py`(sweep ~1629-1641 / 1768)、`lib/atom_locations.py`(realm classify) | 已護 family（PROTECTED_EXACT），未根治；⚠ **並行 session 正改這些檔** | 架構級→先 Plan；三方向擇一/組合：(i) LLM prompt 補 meta core-bias (ii) holylight-authored 且詞庫零命中 [臨] 預設 defer 不搬 (iii) PROTECTED 升 family 規則判定。**動前確認並行 session 未同時改 wg_atoms/atom_locations** |
| Q5 | **Phase C/D**（deprecate 專案複本 / 生命週期收斂）| 各專案 repo | 未開始 | Phase D 明列「user 認可才推」；Phase C 先 SGI→觀察→滾其他 |

**本 session（2026-06-30）已 100% 完成**：DedupStage 引擎 + verify(26) + core SessionEnd 全生命週期接線(sweep+purge) + verify(8) + atom + changelog，run_verify **651→691**，5 commit 雙 remote。**未做的全部是 project 側（跨域做不了）或需 user 決策方向（Q2/Q4）或並行衝突高風險（Q4）**。
