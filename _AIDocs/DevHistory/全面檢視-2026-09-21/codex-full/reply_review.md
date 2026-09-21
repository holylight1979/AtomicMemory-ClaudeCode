**這份計畫方向成立，但不宜整份直接開工；先修正歸因驗收標準、幾項證據口徑，以及 Phase 的依賴與精簡邊界。**

已完整閱讀[彙整報告](/C:/Users/holylight/.claude/memory/_staging/next-phase-全面檢視-2026-09-21.md)、十位審查者的摘要／摘錄及 `reply_1–5.md`，並核對相關程式碼。原始審查檔實際位於報告 §7 指定的 `scratchpad/review/`，以下以檔名引用。全程未改檔；本輪另做了不落盤的函式探針，歷史統計則核對原始審查記錄，沒有冒稱全部重跑。

- **【§1 R1】正確，但應補上量測口徑。** → cold／skip 路標確實未增加 `used_tokens`，組裝時已提交記帳，最後才裁切；Related 曝光也確實漏走同一條路。依據：`hooks/handlers/ups_inject.py:213、282、381、440`、`hooks/handlers/user_prompt_submit.py:398`。但 **133/175、最高 2,225 是離線正例組裝、使用本機估算器的結果**，不是線上超額率或供應商 tokenizer 實測；原文 `reply_5.md:45–50` 有說清楚。→ 保留修復項目，在 R1 本列就補齊限制，不只放報告末尾。

- **【§1 R2】需修正：數字抄對，名次關係寫錯，且少了一項關鍵限制。** → `1.033` 是單一路徑**第 1 與第 3 名**的比值，不是相鄰名次；本輪重算第 1／2 名為 `62/61≈1.0164`，activation 差約 `0.065` 即可翻轉。公式中的 A 實際是含分心懲罰的 `compute_injection_rank`。依據：`reply_5.md:68–86`、`hooks/handlers/ups_search.py:314–338`。原文另明載：最終預期卡片「出現」只從 **162/175 增至 164/175**，且可能只是路標。→ 改正名次，將此送達數字與「全域索引、新 session、關 vector」放在 R2 旁；排序改善值得測，但不能推成回答品質改善。

- **【§1 R3】需修正：機制缺陷成立，「幾乎全判有用」的證據不夠。** → 本輪重現 Agent prompt 進入歸因文字、舊 `wisdom_retry_count=2` 使無當輪失敗的回合仍判 fail；DF 未接線與整卡比對也有直接程式依據。但 Stop 分別累計主回合與子代理卡片，因此「主回合注入 9、判用 10」是**分母／集合未對齊**，不能直接證明全部誤判。依據：`hooks/handlers/stop.py:439–466`、`claude_F_extraction_summary.md:8`。此外，90 天零降級不能單獨證明降級路徑失效，現行程式本來只產出「需裁決」候選：`hooks/wg_atoms.py:2596–2605`。→ 標題改為「歸因存在自我命中及跨回合污染，真實錯判率未標註」；保留 0.629 與零降級作描述性統計，勿當因果證明。

- **【§1 R4】正確。** → Supersedes 僅掃當次候選，卻回傳未過濾的 `all_atoms` 供 Related 使用，資料流確實允許舊卡回流。依據：`hooks/handlers/ups_search.py:293–344`、`hooks/handlers/ups_inject.py:302–305`。原文 `reply_2.md:96–102` 明確限定為合成函式案例，報告也保留了這點。→ 維持修復；補上「正式 session 發生率未知」，以及原文要求的**歷史查詢例外**，避免查舊決策時也一律隱藏。

- **【§1 R5】需修正：評估器錯位成立，最後一句過度絕對。** → 舊評估器確實沒有 RRF／activation 等階段，且 `compare_baseline()` 回傳值被忽略；但它仍可驗到 trigger、BM25 分數／門檻／gating 的變化，不能寫「所有排序調參都驗不到」。依據：`tools/memory-eval/run.py:77–98、293–295`。67.0%、53.6%、64.6% 的數字與原文一致，惟 baseline 的正例是 209，本次為 175，不能視為同母體退步。→ 改成「無法驗證線上融合排序與最終內容送達」，每個基準附索引快照、有效題數及 vector 狀態。

- **【§1 R6】需修正：把歷史故障、量測盲區與仍存缺口拆開。** → `claude_D_telemetry_summary.md:21` 明載 advisory 在 **09-18 commit 後未再現**，報告漏掉這句，容易讀成現在仍每次 crash。episodic 有專案層產出，能推翻「整條管線停擺」，但不能解釋每個無產出的 session；同摘要第 20 行還記載一場改 11 檔、跑兩小時仍無產出。→ 分列「已修、但缺可見告警」「健檢漏掃專案層」「個別跳過原因未釐清」。recall-miss 字串例外本輪已重現，保留為確定缺陷。

- **【§1 R7／Phase 0】正確，但完成範圍須限定。** → 本輪確認兩個入口已使用新 guard，通知會被過濾、一般使用者文字不被過濾；指定錯誤 atom 不存在，post-mortem atom 存在。依據：`hooks/wg_friction.py:217`、`hooks/wg_extraction.py:157`、`hooks/wg_core.py:227`。不過 `_is_real_user_prompt()` 仍把 `<task-notification>` 字串當成真實回合邊界，本輪亦重現，見 `hooks/wg_evasion.py:566–583`。→ 寫「已修糾正／失敗萃取兩入口」，並將歸因取文的通知邊界納入 Phase 2，不能擴張成 harness 污染已全面解決。

- **【§1 R8】需修正：大部分缺陷成立，但估算、路徑與版本要分清。** → 全量 worker 被停用設定擋住、稽核器要求自訂 triggers 均有程式依據；`/extract` 空結果則只適用於**路徑 A 的既定 worker 指令**，路徑 B 仍可從對話整理。依據：`hooks/handlers/session_end.py:207–224`、`skills/extract/SKILL.md:49–61`、`skills/skill-creator/scripts/audit-skill.py:72`。always-load 的 4,500–5,800 是估算，非「實際 token」；本輪按程式估算器重算列出的五檔為 **5,459**。官方確實記載 SessionEnd 可依 settings 的 per-hook timeout 提高總預算至 60 秒，但未在本機實跑 timeout。→ 改為「估算偏低／特定路徑失效／現行官方契約」，保留本機版本驗收。[官方 SessionEnd 規格](https://code.claude.com/docs/en/hooks#sessionend)

- **【§6 依賴順序】大方向成立，整個 Phase 串行不成立。** → R2 排序比較需要可重播的評估器；「只比對送出節錄」需要 R1 最終記帳。但 recall-miss 型別護欄、Agent prompt 排除、retry 當輪化、skill 指令修正，都能用局部案例先修，不必等待完整 Phase 1。R4 也能先做合成案例修復，再用對齊評估器驗收。→ 改成項目依賴：**記帳→送達歸因；評估器→排序／Related 實驗；可靠結果歸因＋有效性過濾→撤銷研究**。獨立止血項目可提前。

- **【Phase 1 R1＋精簡 hint】應合併處理同一函式，避免誤刪曝光。** → `_emit_usefulness_hints()` 名稱像純提示，實際同時做 ReadHits 增量；整支移除會把 R1 正在修的曝光一起拔掉。依據：`hooks/handlers/ups_inject.py:409–449`。→ 保留單一「最終送達提交」入口，Related、曝光、去重、rescue watch 共用；只刪 hint 的稽核支線。這是必要的最小結構調整，無須另建通用事件框架。

- **【Phase 1 R5／§6「全跑 <2 秒」】需补隔離規格，撤掉耗時保證。** → 原始研究要求固定索引／正文、sidecar、時間及 vector 回應，且不得更新正式 sidecar；計畫只明寫其中兩項。`reply_2.md:30、81–84` 的約 0.97 秒是**舊評估器且 vector 關閉**，不是未完成的新評估器。→ 固定完整輸入並替換所有落盤副作用，覆蓋新 session、重複注入、project/local scope；耗時留待量測。舊評估結果可作診斷欄，不必成為第三套永久門檻。

- **【Phase 1 episodic】「加 turn_seq≥3」不是已證實的根因修復，應拆出。** → 三輪聊天不等於值得保存；而修改此門檻也解釋不了已改 11 檔仍無產出的個案。更直接的陷阱是摘要建議用 `_atom_debug_log("episodic:skip", …)`，但該函式在 `atom_debug=false` 時不寫非 ERROR 訊息。依據：`claude_F_extraction_summary.md:18`、`hooks/wg_core.py:1150–1153`。→ 先修健檢範圍、補不受 debug 開關吞掉的節流原因記錄；是否放寬生成資格另以有價值的唯讀 session 驗證。

- **【§5 hint 精簡／Phase 1 健檢】需修正，現方案會重造誤報。** → 「hint 無讀者」只能指無業務消費者；健檢目前仍把 audit 任意尾筆當活性。若改為只看 `auto_observe/manual`，正常掃描但無晉升事件仍會報死。程式已具備 `log_promotion_heartbeat()`，並在無晉升時呼叫。依據：`tools/health-weekly.py:96–105`、`hooks/wg_core.py:1097`、`hooks/wg_atoms.py:2622–2624`。→ 停寫 hint 可做，健檢改讀**掃描 heartbeat／掃描完成訊號**；不要再新增一套心跳。

- **【Phase 2 R3／Phase 4 TEPA 驗收】應刪除「判用／注入 <0.5」硬門檻。** → 這是 Claude F 的建議值，沒有標註資料證明它代表正確；真正相關的卡全被用到，也可能是好結果。用它驗收會獎勵漏判，再把漏判當成可自動撤銷的通行證。Codex #5 明載真實假陽性率未知：`reply_5.md:138`。→ 改用已規劃的採用／引用／拒用／修正／未知標註集，分別量誤判與漏判；判用比例只作監測值。

- **【Phase 2 rescue＋lexical＋延後結算】方向可留，但目前低估語意與狀態成本。** → rescue 是工具參數詞命中，不保證成功，更不是因果效益；它按 `(atom, token, session)` 去重，後續回合沒新 log 不等於沒使用。依據：`hooks/wg_rescue.py:145–186`。原計畫的「無 rescue」也未說清楚是該 atom、本回合或整個 session。→ 明定 atom／回合對應，rescue 作較強使用佐證，不直接當成功 α。下一 UPS 的糾正先標待查，不把前輪所有卡一併判負；延後結算另補最後一輪無下一 UPS、通知回合、重複 Stop、重啟等規則，否則先不引入 pending 狀態。

- **【Phase 2 晉升確定化】需拆開；兩個改法不是單純修時序。** → `record_usefulness` 目前按使用結果計數，改成 per-session 去重是在更換統計單位，也必須定義同 session 先失敗後成功如何結算。每日衰減下，三個 session 各一勝，到第三次衰減前也可能只有 **1＋0.97＋0.97²＝2.9109**，所以「先 eligible 再 decay」不保證三勝達 `n≥3`。依據：`lib/atom_access.py:439–522、571–579`。→ 先修同一 atom／同一 turn 被主、子代理重複計數；session 封頂與樣本門檻另列政策選擇。Python／JS 鏡像也須一併驗證。

- **【Phase 2 activation＋BM25】不能一次混改後只看總分。** → gain、最終裁切排序、BM25 gating 都會改結果；原文特別要求分開比較，且 BM25 的證據是排序小幅改善，**沒有找到補回大量漏召回的案例**。依據：`reply_5.md:86、111–125`。→ 同一快照依序測 gain、裁切一致性、BM25 gating，保留各自結果；棄權與 Related 實驗採用固定後的排序版本，避免無法識別收益來源。

- **【Phase 3 AEC-Pending dormant】裁決尚不足，應暫緩。** → 零真實觸發不證明與 DeferralGate 等價。前者讀結構化 `aec.d_pending`；後者讀最後文字，另要求完成／commit，且受 context 比例限制。依據：`hooks/handlers/stop.py:716–743、819–827`、`hooks/wg_evasion.py:295–298`。Codex #4 也明確反對把不同 Stop 閘視為重複。→ 先補「結構化 pending，但最後文字無退縮句」「高 context」的涵蓋案例；未證明被取代前保留。

- **【Phase 1–3 工時／PostToolUse 合併】整體估時過低，且合併範圍用語不一致。** → Codex #5 對 R1 單項估 1–2 人日，評估器另 0.5–1；Phase 1 卻連其他修復共估 1.5。Codex #4 對程序整合單項估 1–2 人日，Phase 3 全部也只估 1.5。原提案是**後兩支併入 guardian、Codex companion 保持獨立**，不是四支全合。依據：`codex_5_retrieval_summary.md:18–19`、`reply_4.md:12、25、66`。→ 程序合併獨立列為可延後項，先量真實延遲；不能把空程序 311ms 直接乘二當收益。

- **【§5／Phase 2 `build_atom_df`；§5 零使用 skill】主持者裁決正確，但有一項尚未裁清。** → 保留 DF helper 接線，優於只因目前零 caller 就刪；先看可見性成本、不直接搬走 17 個零使用 skill，也正確吸收了「9 個原已手動限定」的反證。依據：`codex_4_trim_summary.md:6`、`codex_5_retrieval_summary.md:11`、`codex_1_official_summary.md:3`。但 `read-project` 尚有兩案混在一起：#4 主張 atom 留摘要錨點，#3 主張可再生導覽不進 atom。→ 在 Phase 3 寫清楚：**純導覽放文件；另有不可再生的決策／踩坑才寫 atom**，不要把目錄縮短就算通過新 write gate。

- **【Phase 3／漏項：Claude F】漏掉的保護與可追溯性，比新增研究更值得先處理。** → `claude_F_extraction_summary.md:19–22、30` 的 worker 起訖可觀測、failure provenance，以及 forget 保護前綴缺口，均未進 checklist。本機確實只用 EXACT 保護，未用已有的 `is_core_protected_name()`；user-extract 則**已經有**來源註記，不應再概括說全系統無 provenance。依據：`hooks/wg_atoms.py:2136–2144`、`hooks/user-extract-worker.py:384`。→ 補一個小項目接回共用保護判定；其餘併入 worker 可觀測與 failure 來源定位，不建 heartbeat／lease 新框架。

- **【Phase 3／漏項：Codex #3】報告提到了，執行清單卻沒接住。** → 固定九次代理、無條件四題訪談、真正 skill 成效對照，出現在 §4／§5，Phase 3 沒有明確工作與驗收；寫入契約又只修 `read-project`，漏了 `consciousness-stream` 的推測迴寫／手改 MEMORY，以及 `upgrade` 的舊配方。依據：`codex_3_skills_summary.md:9–11、18–21`、`skills/consciousness-stream/SKILL.md:119–125`。→ 合併為「active skill 寫入契約與固定儀式校正」，配少量有／無 skill 案例；若暫不做，明列延後理由。

- **【§4／Phase 1 9,000 字元硬頂】需降為待驗候選，來源被收斂得過頭。** → issue 原文只回報 **約 10K 通過、約 16K 未通過**，沒有證明「超過 10K 就截斷」。Claude C 本來也註明待本機驗證。→ 先記錄實际序列化輸出大小、在本機版本探邊界，再決定上限；若先採 9,000，必須標為保守工程值，並定義非 atom／Guardian 訊息本身超限時的處置。[原始 issue #91473](https://github.com/anthropics/claude-code/issues/91473)

- **【§4 context-mode／skill description／ECC】有未完成的來源裁決。** → 官方目前已明載 `updatedToolOutput`，所以「官方查無」需要更新；但 3 個 session、65 次呼叫的樣本仍不足以支持優先導入壓縮器，暫緩結論可留。description「只寫何時用」是 superpowers 偏好，Codex #3 原文已區分官方的「做什麼＋何時用」，不能包裝成一致共識。ECC 跨專案升 global 在 Claude C 是增量、Codex #3 是重疊，報告未附本機等價機制定位。→ 分別改成「已確認 API、需求不足」「採情境＋產出短描述」「跨專案升級未立項，先釐清 Scope 與 Confidence」。[官方 PostToolUse 規格](https://code.claude.com/docs/en/hooks#posttooluse-decision-control)

- **【§3 D／Phase 4 constraint pinning】不依賴 Phase 1–2，但更應先做缺口驗證，不能直接稱十分鐘快贏。** → Claude A 已指出 compact 後重讀根層 CLAUDE.md；本機 `CLAUDE.md:2` 又已匯入 IDENTITY。官方亦明載根層規則會重新注入。現有 `post_compact.py:95–106` 是 stash 後由 PostToolBatch 送出，並非 PostCompact 直接注入。→ 可提前驗證這三條契約是否真的遺失；未證明缺口就砍此新增項，避免複製第二份規範。[官方壓縮後記憶行為](https://code.claude.com/docs/en/memory#instructions-seem-lost-after-compact)

- **【§3 B／Phase 4 TEPA＋Hindsight】需重寫機制對應，現在容易誤接兩種 α。** → Hindsight 的 α 是 **0–1 信心更新步長**，不是本系統 `useful_hits` 的 Beta 計數；TEPA 的 support／conflict 則來自**同一 key 的值是否相容**，不能直接代入整個回合成敗。→ 將 Hindsight 步長改記 η，明列本機尚缺的「同鍵反證」來源；兩者先分開實驗，不直接對既有 α 做減法，也不新增另一套重複計數。[Hindsight §5.5](https://arxiv.org/html/2512.12818v1#S5.SS5)、[TEPA 生命週期](https://arxiv.org/html/2608.07429v1)

- **【§6 交付／遷移】還缺兩個收尾條件。** → 一是修好歸因後，舊 α／β 仍混有歷史污染；「重算 17 顆候選」若只重新套公式，並不會洗掉污染。二是 `cross_session` 在 Phase 1 要關，卻到「Phase 3 前」才多機確認，順序矛盾。另週報既有 broken refs 5／duplicates 7 未被處理或明確排除。→ 保留舊 sidecar 快照，從明確切點觀察新歸因，不宣稱無證據的歷史重算；多機條件放在對應變更之前；健檢存量另列沿用既有工具處理或不在本輪範圍。

**這份計畫可以直接開工嗎？整份不行；獨立的止血修復可以。先改三處：① 重寫 R1–R8 的證據口徑，尤其 R3 分母、R6 歷史／現況及 R8 估算；② 刪掉「判用率 <0.5」驗收，定義送達、使用、成功與反證的界線，並交代舊 α／β 如何處理；③ 將大 Phase 串行改為項目依賴，修正 heartbeat 健檢，暫緩 AEC 停用、未驗證的 9,000 字元硬頂及程序合併，再重估工時。**
