# dedup-stage-牢籠去蕪設計-信任模型隔離與substring-only首版

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: dedup, 去蕪, DedupStage, draft, 草稿, _drafts, 截斷, truncate, soft-delete, 牢籠, taxonomy, 近重複, sweep
- Created-at: 2026-06-30
- Related: 品質完整性判定須讀完整內容-勿從截斷採樣斷言, realm-範疇分區機制-v5

## 知識

- [臨] **DedupStage（lib/dedup_stage.py，2026-06-30 commit ed51b48）= _drafts 牢籠去蕪，與確定性 classify 主路物理隔離**。信任模型不同：classify=確定性 term-match（不可逆寫索引/詞庫）；dedup=可逆 soft-delete（搬 _drafts/_trash + 14 天閘 + restore 救回）→ 絕不混入 classify 入口。只在 _drafts/ 運作（cage_assert fail-closed），CI grep 鎖死禁索引寫入/詞庫學習符號（連 docstring 都不能出現該等字面，否則 grep 自打臉——複用 taxonomy_jury 慣例）。
- [臨] **截斷三訊號須全中才判**（is_truncated_fragment）：①行內未閉合(奇數反引號/未閉fence/括號不平衡) ②連接符(=(:、，/)收尾 ③`## 行動` 佔位符。80 份真實 draft 實證：訊號③ 80/80（builder 統一附加→單獨零鑑別力，真正用途是排除有真實行動項的 curated atom）；全中僅 1/80（真截斷）。禁用全文末字＝主記憶 26% 假陽性（slug 恆截到 60 字但 body 完整）。判定讀完整 body（[[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]）。高精度低召回＝刻意：caged fragment 留著無害、誤刪才有噪音。
- [臨] **cluster 首版只收 literal substring 冗餘（零知識損失保證）**，paraphrase（換句話說的近重複）刻意不自動去——需 LLM 語意判斷、違 dedup 確定性信任模型 → 留人工 /refile。故 SoT 早期『41% 實證可省』那是 LLM 級語意去重、本版未達成（安全優先）。per-env：project=截斷清除+叢集去重 / core 主記憶=碎片吸收不去重。
- [臨] **§9-vs-§1 真相**（taxonomy 引擎接手免再查）：lib/taxonomy_jury(cage_assert/relocate_within_cage) + lib/game_taxonomy(seed slugs/_Unsorted) = Phase 0 牢籠地基**保留複用**；§1『已取代』指舊 atom 分類路（game_taxonomy 為主 + 三路 LLM jury）→ 已退 lib/atom_classify.score_by_lexicon（確定性）。lib/taxonomy_classify(單後端 LLM jury)=by-class 雛形、DedupStage 不用它。三者正交。
- [臨] **未接線 live SessionEnd hook（刻意，待 user 認可）**：sweep_drafts 為可呼叫單元但會對活躍 repo 產生可感知行為改變＝Phase D 性質。接線一行即可，接線前先 SGI dry_run=True 比對。sweep 持非阻塞 file-lock(_drafts/.sweep.lock, NBLCK/LOCK_NB)拿不到即 skip。

## 行動

- 接手 taxonomy 引擎/去蕪：先讀 lib/dedup_stage.py + memory/_staging/next-phase-draft-taxonomy-engine.md §3/§9，勿據舊版 game_taxonomy 重造
- 要讓 DedupStage 真正運作：接線前 SGI dry_run 比對、user 認可後才掛 live hook
- 新增牢籠內模組：複用 taxonomy_jury cage 原語、docstring 都不得出現索引/詞庫寫入符號字面（CI grep 守）
