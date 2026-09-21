# 原子記憶系統全面檢視（對照 Claude Code 2026-09 生態）— 報告與執行計畫

> **歸檔（2026-09-21）**：本計畫全部 Phase 已完成、驗證 1,987/1,986 過並提交；原位 `memory/_staging/` 已移除，本檔只作決策與證據紀錄。尚未做的兩項（不擋任何功能）：Phase 3 ⑤ Codex 裁判 awaiting 識別、Phase 4 查詢—卡片相關性標註，見 §6。

> **本檔完整路徑**：`C:\Users\holylight\.claude\memory\_staging\next-phase-全面檢視-2026-09-21.md`
> **專案根**：`C:\Users\holylight\.claude`（git repo，branch `main`）。驗收規格（已全過、status done）：`C:\Users\holylight\.claude\.claude\verify\done\acceptance-全面檢視-2026-09-21.md`。審查證據：`C:\Users\holylight\.claude\_AIDocs\DevHistory\全面檢視-2026-09-21\`。
> **接手順序（唯一入口，2026-09-21 晚間更新）**：[使用者] 當日授權「把所有 Phase 推進到完工」，所以 Phase 0／1a／1b／2 與 Phase 3 大部分**已在同一個工作樹內完成、全部未提交**（§6 各 Phase 打勾即完成；變更檔見下列與 `git status`）。① 先等 [使用者] 下「上GIT」把本次整批提交（選擇性 staging，排除他 session 的檔）；② 之後新 session `/continue` 讀本檔，剩餘項目只有：Phase 3 ⑤ Codex 裁判 awaiting 識別、Phase 4「查詢—卡片相關性標註」（原延後四項已全部收掉，見 §6）；③ 舊指示「從 Phase 1b 開始」**作廢**。
> **Phase 0／1a 變更檔（未提交，23 個路徑）**：`hooks/wg_core.py`、`hooks/wg_friction.py`、`hooks/wg_extraction.py`、`hooks/wg_evasion.py`、`hooks/wg_atoms.py`、`hooks/wg_episodic.py`、`hooks/wg_recall_miss.py`、`hooks/extract-worker.py`、`hooks/handlers/{stop,user_prompt_submit,ups_inject,post_tool_use,session_start}.py`、`tools/health-weekly.py`、`TECH.md`、`_AIDocs/_CHANGELOG.md`、`_AIDocs/DevHistory/_INDEX.md`、`_AIDocs/DevHistory/全面檢視-2026-09-21/`（新）、`hooks/verify/verify_attribution_turn_identity.py`（新）、`hooks/verify/verify_harness_prompt_guard.py`（新）、`hooks/verify/{verify_personal_sync_advisory,verify_unpushed_advisory,verify_usefulness_loop_phase2}.py`、`_AIDocs/_atoms/MemDev/糾正與失敗偵測把sub-agent完成通知當使用者輸入-…md`（新 atom）、索引重生檔（`memory/_atom_index.json`、`_ATOM_INDEX.md`、`MEMORY.md`、`_local_catalog.md`、各層 `_INDEX.md`）、本檔、驗收規格。（此段是 Phase 1a 當時的快照；**最終以 §11 的納入／排除清單為準**。他 session 的 `.gitignore`／`tools/usage-snapshot/` 已由對方自行提交 d958302；本次只在 `usage_snapshot.py` 補兩處 `newline=`，該檔**納入本次提交**，補完後 `verify_lf_writes` 單項 PASS，整套曾有這 1 失敗；修後只做了該單項複驗 PASS，整套未重跑——待 PostToolUse 併程序的 agent 收工後會再跑一次整套，以那次為準。）
> **最終驗證（全部收尾後，2026-09-21 晚間；含 PostToolUse 併二）**：`python -X utf8 run_verify.py` 1,987 案例／1,986 過／1 跳過／0 失敗（exit 0）→ **可提交**。對齊評估器與線上基線比對 exit 0（R@1 81.1%／MRR 0.870／content 88.0%／負例 4.5%）；判用 v2 P 0.67／R 0.84。
> **未解問題（現況裁決）**：① 09-18 一場改 11 檔跑兩小時的 ~/.claude session 為何無 episodic 產出？——仍未知；事件 log（`Logs/guard-episodic.jsonl`）自本日起累積，下次重現時可答，不阻擋任何事。② 真實 session 的效用歸因假陽性率？——已由標註集回答：v1 precision 0.35（有沒有用到）／0.18（嚴格採用）；v2 0.67／0.38；標籤為 AI 判定未人工複核，`review_flag` 5 筆待人工挑錯（剩餘項）。③ Supersedes 回流在正式 session 的發生率？——機制已從池層堵住（含子代理、歷史查詢例外），發生率不再需要量。④ Codex 裁判 34 次 0 pass 是抓不到還是沒東西可抓？——分母修正後真裁判 56 筆 uncertain 46%、綁定覆蓋率 12.6%；答案要等 20 筆人工標註（延後清單 ④）。
> **Phase 4 剩餘項「查詢—卡片相關性標註」規格**：資料源＝`tools/memory-eval/queries.jsonl` 全部 231 題各取 `run.py --online --dump` 的前 5 候選（約 1,000 對）；標籤 `relevant|irrelevant|partial`，AI 先標、`review_flag` 標最不確定 30 筆給人挑錯（同 usage_labels 慣例）；產物 `tools/memory-eval/relevance_labels.jsonl`＋`eval_relevance.py`（誤送率＝送出且 irrelevant／送出總數；漏送率＝relevant 未送出／relevant 總數）；之後才允許實驗單一棄權閘（每次只開一個：IDF 閘、margin 閘、τ_gate）；採用門檻：誤送率下降 ≥5pp 且 R@3 不降超過 1pp 且負例不升；達不到就不上線、config 保持現狀。

> 人稱約定：[使用者]＝holylight；[AI]＝主持本次檢視的 Claude session；[審查者]＝並行的 5 支 Claude sub-agent 與 5 支 Codex（gpt-6-astra）；[Codex 審查]＝第 6、7 支 Codex 分別對計畫初稿與拍板做的審查，發現已逐條裁決併入（§8）。
> 證據分級：**實測**＝本機探針／統計腳本／實跑；**程式核對**＝讀碼定位到檔:行；**外查**＝官方文件／論文／專案原始碼（附 URL）；**推論**＝未驗。所有探針數字都是**離線、本機估算器口徑**，不是線上發生率或供應商 tokenizer。
> 名詞速查：atom＝記憶卡片；UPS＝UserPromptSubmit hook（每個 prompt 的檢索注入）；RRF＝多路排名融合；activation＝ACT-R 使用頻率＋時間衰減分（進排序時已含分心懲罰）；α/β＝atom 被判「有用／誤導」的 Beta 計數（含 +1 先驗），餵 Wilson 晉升；Supersedes＝新 atom 取代舊 atom 的標記；Related＝atom 之間的連結；sidecar＝每顆 atom 旁的 .access.json 遙測；rescue-log＝工具參數命中 atom 專屬 token 的紀錄。

## 0. 一句話結論

系統**不是過重，是幾個核心量測與記帳失真**：注入記帳在裁切前提交、排序被 activation 乘數支配、效用歸因有自我命中與跨回合污染、回歸評估器驗不到線上的融合排序與送達。外部生態（官方新功能、熱門 skill、記憶論文）能直接借的東西不多；「什麼時候不要注入」與「用後續結果自動撤銷」值得研究，但**要先修好記帳、評估器與歸因標註集才量得出效果**。

> **權威執行邊界（以此為準，2026-09-21 晚間定稿；與 §9 同義）**：
> - Phase 0／1a／1b／2 **已完成**；Phase 3 除「延後」清單外**已完成**；Phase 4 只剩「查詢—卡片相關性標註」——全部在本 session 完成、**未提交**，等「上GIT」。
> - 已上線（config 可一鍵回滾）：`vector_search.rrf_activation_gain: 0`、`bm25_gate_max_trigger_hits: 999`、`injection.related_gate.query_gate_min: 5`、`usefulness.attribution_policy: v2`。觀察一週 usefulness 切點資料。
> - 未來 session 只做 §6 Phase 3「延後」與 Phase 4 剩餘項；§3 外部演算法（棄權閘、TEPA）仍**只離線驗證不上線**。
> - 舊敘述「Phase 1b／2／3 下一個 session 起可以改碼」「Phase 2 排序參數待離線比較後上線」**已作廢**（都已做完）。

## 1. 重大發現（前置獨立成節）

| # | 發現 | 證據與限制 | 交叉來源 |
|---|------|-----------|---------|
| R1 | **注入記帳與實際送出不一致**：cold／skip 路標不計 `used_tokens`、全文標頭未完整計費，所以 atom 段 1,200 tok「硬頂」不硬；尾端 Guardian 訊息會隨 atom 被裁掉；`injected_atoms`／曝光／去重在裁切**之前**提交；Related 專有候選送出卻不加曝光；JIT/episodic 預算重複扣額 | 程式核對（`ups_inject.py:213/282/381/440`、`user_prompt_submit.py:398`、`wg_atoms.py:1251`、`ups_context.py:95/175`）。「175 正例中 133 次超過、最高 2,225」是**離線正例組裝、本機估算器**的結果，不是線上超額率 | Codex #5 |
| R2 | **排序被 activation 乘數支配**：`F = Σ1/(60+rank) × exp(0.25×A)`，k=60 使單路第 1／2 名 RRF 比只有 1.016（第 1／3 名 1.033），activation 差約 0.065 即可翻轉；A 是含分心懲罰的注入 rank。離線重播真正搜尋函式（全域索引、新 session、關 vector、寫入端替身）：現行 R@1 41.7%／R@3 83.4%／MRR 0.619 → gain=0 時 80.0%／93.1%／0.860，82/189 首名改變 | 實測（`ups_search.py:314-338`、`wg_atoms.py:370/585`）。**限制**：預期卡片在最終輸出「出現」只從 162/175 到 164/175，且可能只是路標——這是排序改善，不是回答品質改善 | Codex #5；Codex #2 獨立指出 Related 排序只看 activation 不看 query |
| R3 | **效用歸因存在自我命中與跨回合污染，真實錯判率未標註**：(a) 派工 sub-agent 時 atom 原文塞進 Agent prompt，`get_current_turn_text` 把 prompt 欄攤平 → 必中；(b) `build_atom_df`（IDF 過濾）寫好但零呼叫，Stop 未傳 df_map；(c) 「共享 token ≥2 或 containment ≥0.18」對中文 bigram 太鬆——合成無使用負控制 59/579 配對判 used，接 DF 且 max_df_ratio=0.1 後 9/579（預設 0.5 完全無效）；**但 OR 分支使短節錄的 containment 更易達標（節錄兩詞命中一詞即 0.5 → used），單調門檻 2→3 封不住**；(d) 回合文字寫「不要使用，已過時」仍 used=true；(e) Stop 比對整張 atom，即使當輪只送一行路標；(f) `wisdom_retry_count` 只增不清，一場 session ≥2 後無當輪失敗的回合也判 fail；(g) **回合身分不統一**：子代理注入紀錄沒有來源回合，Stop 掃所有未歸因紀錄套當輪 outcome；同 atom 父回合成功、子代理失敗會寫入一勝一敗；通知型 prompt 仍讓 UPS 遞增 turn_seq、覆寫 turn_injected | 實測＋程式核對（`stop.py:347-482`、`wg_atoms.py:1079-1157`、`wg_evasion.py:566-660`、`wisdom_engine.py:317`、`post_tool_use.py:85`、`user_prompt_submit.py:352`）。**限制**：「注入 9 判用 10」的單場數字是主回合與子代理集合未對齊的分母，不能直接當全誤判；87 顆 n≥3 平均成功率 0.629、90 天降級 0 筆是描述性統計（降級路徑本來只出候選），不是因果證明。rescue-log 30 天 417 筆是較強的「使用」佐證，不是成功證據 | Claude F、Codex #5、#2、#7、Claude D |
| R4 | **Supersedes 有漏洞**：取代過濾只掃當次命中候選，卻把未過濾的 `all_atoms` 傳給 Related 擴散 → 合成函式案例證實被取代的舊 atom 被帶回；只有舊 atom 命中、新 atom 沒命中時取代聲明讀不到 | 實測（合成）＋程式核對（`ups_search.py:293-344`、`ups_inject.py:302-305`、`wg_atoms.py:302`）。正式 session 發生率未知；修復須保留「查舊決策」的歷史查詢例外；路徑清單須含子代理注入（`wg_atoms.py:940`）與 compact 復原 | Codex #2、#7 |
| R5 | **回歸評估器驗不到線上融合排序與最終送達**：`tools/memory-eval/run.py:77` 只做 trigger → BM25 → vector（仍能驗 trigger／BM25 門檻與 gating），無 RRF／activation／Supersedes／Related／裁切；負例量測只回答「負例是否回傳任何候選」，量不到「正例夾入無關卡」；223 題中 34 題目標已不在索引被跳過；`compare_baseline()` 回傳被忽略。三處基準（baseline.json R@1 67.0%、正例 209；TECH.md 53.6%；本次實跑 64.6%、正例 175）母體不同 | 實測 | Codex #2、#5、#7 |
| R6 | **靜默失效群，分三類**：(a) 確定缺陷：recall-miss 對字串型 knowledge_queue 拋 AttributeError（08-26～09-18 共 16 個真實時刻，重現）；(b) 已修但缺可見告警：SessionStart 三個 advisory 08-26 起每次啟動 crash，09-18 commit 後未再現——三週間訊號只進 debug log；(c) 量測盲區：episodic「停擺」是週健檢只掃根層（09-18 產出在 TSLG 專案層、C:\Projects 專案層 113 檔），且唯讀／sub-agent session 過不了「有改檔或 Read」閘（bypass 模式用 cat 讀檔 Read 恆 0）；跳過原因無 log、舊 state 已清——**個別 session（含一場改 11 檔跑兩小時）無產出的原因仍未釐清**。另：`_promotion_audit.jsonl` 94% 是無業務讀者的 hint 列；pytest 直接寫進正式 Logs/ | 實測（`wg_recall_miss.py:90`、`health-weekly.py:222`、`wg_episodic.py:42`、`ups_inject.py:477-486`） | Claude D、Claude F |
| R7 | **本 session 現場實證兩起誤觸**：糾正偵測與失敗萃取把 sub-agent 的 `<task-notification>` 整則當使用者輸入 → DeepPostMortem 誤報「使用者糾正 2 次」、FailureDetect 觸發背景萃取並**捏造**一顆 Failures atom。**已修兩個入口**（`wg_core.is_harness_generated_prompt`）、捏造 atom 已刪、post-mortem atom 已寫。**未修**：回合身分（R3g） | 實測 | [AI]、[Codex 審查] |
| R8 | **文件與現況不符／特定路徑失效**：TECH §6.3 寫 SessionEnd 全量萃取「在跑」，實際 `session_end_flush.enabled=false` 不 spawn（`session_end.py:207-224`），連帶 `cross_session` 觀察（只在該 worker 內呼叫）也是死路；「SessionEnd 1.5 秒不可調」已過時（官方：per-hook timeout 可把預算拉到 60 秒；本機未實跑）；always-load 按本機估算器五檔合計約 **5,459 tok**（估算值；文件寫 1,500–2,000 偏低）；Architecture.md 與 TECH.md 矛盾；memory skill 兩處指令衝突、`--self-iterate` 不存在；`/extract` skill **路徑 A**傳的 JSON 缺 session_id/cwd → 永遠空結果，路徑 B 仍可用；skill 稽核器把本機自訂 `triggers` 當必填 → 21 個 skill 19 個假失敗；Codex 裁判紀錄 30 天 206 列中 182 列未綁定佔位，**但 `promotion_stats()` 把它們算進分母**（拿掉列會讓轉正判定從 false 變 true）——所以不能單純停寫 | 程式核對＋外查（`codex_companion.py:542`、`tools/codex-companion/acceptance.py:477`） | Codex #1、#3、#4、#7、Claude D、F |

## 1b. 為什麼會寫成這樣（每條一句精要判斷；標「猜」的是有邏輯的推測，未標的是讀碼可證）
- R1 記帳在裁切前：注入組裝（assemble）與總額裁切（trim）是兩個時期分別加上的功能，裁切後加時只處理輸出文字、沒回頭改前面已提交的記帳——典型的「後加功能沒補前段契約」，非邏輯錯誤而是耦合遺漏。路標／cold 行不計費：當初把它們視為「幾乎免費的一行」，沒料到會累積到 30% 回合撞頂。
- R2 activation 支配排序：RRF 的 k=60 是論文預設，設計者把 `exp(0.25×rank)` 想成「±2 級只造成 ×0.6～1.6」的小調整（TECH 原文如此），但沒算到 RRF 相鄰名次比只有 1.016——**兩個各自合理的常數疊在一起才出事**；當時的回歸評估器又跑不到這段（R5），所以沒被數字打臉。
- R3 判用假陽性：「共享 2 個稀有 token 就算用到」是中文 bigram 下的樂觀假設；IDF 過濾寫好沒接線是**單純遺漏**（函式存在、呼叫端漏傳參數，測試只測函式本身）。Agent prompt 自我命中：sub-agent 記憶注入（後加）把 atom 原文塞進 prompt，而歸因取文（先有）把所有工具參數攤平——同一個「後加功能沒補前段契約」模式。retry 計數不清零：註解裡就寫著 not yet cleared，是**已知 TODO 被遺忘**。
- R4 Supersedes 只掃候選：當初設計只想到「新舊同時命中」的情境，沒想到 Related 擴散會從未過濾的全池取——猜：Supersedes 與 Related 由不同時期加入、各自只看自己的資料流。
- R5 評估器不對齊：評估器建立時刻意排除 activation（怕隨時間漂移），之後 RRF、Supersedes、裁切陸續加入線上管線，評估器沒跟——**「為了確定性而簡化」的決定沒有到期重審**。
- R6 靜默失效群：recall-miss 字串 queue 是資料格式演進（queue 元素從字串變 dict）沒清舊資料；advisory 例外只進 debug log 是 fail-open 寫成「不告知」（違反自家鐵律，猜：寫的時候 debug log 開著、看得到就以為夠）；episodic「停擺」是健檢寫在 episodic 只落根層的年代，後來 episodic 改依 cwd 落專案層，健檢沒跟。
- R7 通知誤觸：糾正偵測是本月剛加的量測，寫時假設「進 UserPromptSubmit 的都是人打的字」，background agent 的 `<task-notification>` 是 CC 較新的行為——假設過期。
- R8 文件不符：全量萃取關掉時只改了 config 沒改 TECH；SessionEnd 逾時上限是官方後來放寬的；always-load 數字用的估算口徑不一致（本 atom 早已記過兩個估算器分歧）。skill 稽核器把本機 `triggers` 當必填：**LLM 寫錯**——把自家慣例當成平台規格。
- state 被 fallback 覆蓋：`read_state` 用一個 None 同時表示「沒檔」與「讀壞」——**訊號合併**是這類覆蓋事故的常見根因；TTL 30 分鐘則是「idle session」假設下的合理值，沒考慮長背景任務。

## 2. 對照 Claude Code 官方（2026-05 → 09-21，本機 2.1.252，官方最新 2.1.278）

**可被原生取代的自製部件：無。** 原生仍無跨專案記憶、無檢索、無品質分級、無效用迴路。

可借力（小）：`prompt_cache` statusline 欄位（2.1.251）；fork 子代理（2.1.232）繼承父對話——`pre_tool_use.py:1032` 對所有 Agent 都 prepend atom、未辨 fork（**一般子代理不繼承，不可把 already_injected 套到所有子代理**）；`/skill-doctor`＋`skillOverrides`；hook timeout 契約文件修正；PostToolUse `updatedToolOutput` 官方已載但需求不足（30 天 65 次呼叫達 20K 門檻 0 筆）；SubagentStop 驗子代理回報（次選）。

不做：改 plugin、換原生 auto memory、AGENTS.md 遷移、壓縮前阻擋迴圈、OTel collector、Routines 取代週健檢、`context: fork` 套在依賴當前對話的 skill。

## 3. 外部演算法（本輪只做離線驗證）

| 演算法 | 機制一句話 | 本輪裁決 |
|--------|-----------|---------|
| **注入決策層／棄權**（RSCB-MC 2604.27283；Memory-as-Infrastructure 2609.05510；SYNAPSE τ_gate 2601.02744） | 「一條都不注入」是一等公民；margin／熵／IDF／session 被糾正次數低於門檻就不注 | **不上線**。「30% 撞頂、40% 被砍」是容量數字，證明不了被送出的內容錯——先建查詢—卡片相關性標註，分開量誤送與漏送，一次只測一個閘 |
| **Related 一跳 query-aware＋度數正規化**（SYNAPSE fan；HippoRAG 2 PPR） | 鄰居須過 query 相關性再競爭預算；P 按出邊數正規化 | 做**離線三組對照**（關閉／現況／傳播+gate）；關閉不差就砍擴散 |
| **constraint pinning**（Governance Decay 2606.22528） | compact 後 ≤50 tok 釘回硬規則 | 只驗缺口：本機 CLAUDE.md 已 @import IDENTITY、官方 compact 後重讀根層、PostToolBatch 已復原 atom；沒缺口就砍 |
| **TEPA 衝突鍵撤銷／Hindsight 不對稱信心** | 同鍵不同值計 support/conflict；信心步長 η 矛盾扣 2η | **本輪砍**：本機已有 Evidence／Depends／Supersedes 裁決，須先找到「現有機制修好後仍處理不了」的實例；且 η 與本系統 Beta 計數語意不同，不能對既有 α 做減法 |
| **寫入節流**（SAGE／RecMem） | 灰帶才送 LLM；復現 ≥4 才鞏固 | 低優先，不立項 |

刻意不做：完整知識圖譜、RL 訓練類、永久刪除類、每輪反思或整庫重寫、per-line α/β、第二套衰減、LLM importance 進排序。

## 4. 社群 skill／hook：採用的設計

- skill-creator：baseline 先跑、藉口表、先寫 3 個 eval、`claude plugin eval`；description 採「適用情境＋產出」短描述（官方與 superpowers 說法不一致，非共識）；同時修稽核器契約。
- write gate：「能從最終程式碼／測試／文件讀出的不寫」。
- 不立項：ECC 跨專案自動升 global（Scope/Confidence 對應未釐清）；context-mode 截斷（需求不足）；hook 輸出字元上限（issue #91473 只說「約 10K 過、約 16K 不過」，邊界未知 → R1 修記帳時先記錄實際字元數探邊界）。
- 已有不重做：PreCompact flush、Related 擴散、session 內重複抑制、handoff／continue、一次一題、PAN。

## 5. 精簡裁決

| 項目 | 數字 | 裁決 |
|------|------|------|
| hint 稽核列 | 90 天 1,286/1,372 列 | **做**：只停 `_emit_usefulness_hints()` 的 hint 支線（ReadHits 增量保留）；健檢活性改讀既有 promotion heartbeat |
| Codex 裁判未綁定佔位列 | 182/206 列，但進 `promotion_stats` 分母 | **已做**（Phase 3）：寫入端改綁定列、`promotion_stats` 只算 bound 列並另算綁定覆蓋率、轉正條件改人工標註三類；裁判本體保留，不因零 pass 決定去留 |
| `cross_session` | 唯一消費端在不 spawn 的 worker 內 | **不動 config**（開關無行為差異），TECH 標除役 |
| AEC-Pending 閘 | 30 天真觸發 0 | **暫緩**：與 DeferralGate 訊號不同，補涵蓋案例再裁 |
| 孤兒 helper 3 個＋config 2 鍵 | 本 repo 零呼叫 | **做**（先 grep 已登記專案外部引用，零引用才刪）；`build_atom_df` 是接線不是刪 |
| PostToolUse 後兩支併入 guardian | 收益未量 | **延後**：先量真實延遲 |
| 零使用 skill 可見性 | 17 個 0 呼叫；9 個已手動限定 | **延後**：先 `/skill-doctor` 出本機成本基線；零呼叫≠沒價值；不刪不搬 |
| read-project 雙目錄、Architecture 矛盾、consciousness-stream 推測迴寫、upgrade 舊配方、fix-escalation 固定 9 次代理、skill-creator 四題訪談 | 程式核對 | **做**（Phase 3） |
| **不砍**：注入端、PAN、Codex 裁判本體、Stop 各閘、tools CLI、[臨] >60 天 31 顆 | | |

## 6. 執行計畫（定案；[AI] 執行）

依賴是項目級：記帳（R1）→ 送出節錄歸因；評估器（R5）＋標註集 → 排序／Related 實驗；回合身分 → 去重與結算。**Phase 是驗證與交付切點，commit／push 一律等「上GIT」口令，不自動 commit。** 每項寫成「錯哪裡／改什麼／成效」；驗收看**同一批案例的錯誤是否真的減少且無新增漏判**，不看「變綠」「比例下降」這類會隨分母改變的指標。

### Phase 0（已完成）
- [x] 糾正偵測／失敗萃取兩入口過濾 harness 生成 prompt；捏造 atom 已刪；post-mortem atom 已寫
- [x] 審查證據歸檔 `_AIDocs/DevHistory/全面檢視-2026-09-21/`（摘要、遙測腳本、Codex 全文）

### Phase 1a 獨立止血（2026-09-21 完成，等「上GIT」）
- [x] **recall-miss 護欄**｜錯：字串型 knowledge_queue 讓失念偵測炸了 16 次｜改：`wg_recall_miss.py` 型別判斷｜效：失念偵測恢復
- [x] **retry 計數差分**｜錯：session 重試數 ≥2 後每回合都判失敗、所有判用 atom 吃 β｜改：UPS 在 turn 起點快照 `wisdom_retry_turn_base`，`_detect_turn_outcome` 看本回合增量；FixEscalation 等仍用累計｜效：β 不再整場連帶
- [x] **回合身分統一**｜錯：atom 原文塞進 Agent prompt 被自己命中；子代理紀錄沒來源回合，Stop 掃所有未歸因紀錄套當輪 outcome；同 atom 同輪父成功子失敗寫一勝一敗｜改：`get_current_turn_text` 跳過 Agent/Task 的 prompt 欄（鏡像 wg_rescue）；`subagent_injections` 記 turn_seq，Stop 只結算本輪、更早的標 stale_turn；同 atom 多來源先收齊再寫一筆，結果衝突 → unknown 不動 α/β、留 conflicted 紀錄｜**裁決註記**：通知型 prompt 仍算一個 UPS 回合（turn_seq 照增、turn_injected 照覆寫）——取文邊界與記帳邊界維持同一定義（UPS＝turn），比「取文忽略通知、記帳不忽略」的錯位更安全；使用者訊號類偵測（糾正／失敗）已另行過濾 harness prompt｜效：派工回合的假「有用」消失，n 不再虛胖
- [x] **forget 保護共用判定**｜改：`select_forget_candidates` 改用 `is_core_protected_name()`（EXACT＋前綴）
- [x] **episodic 健檢語意**｜改：`wg_episodic` 新增 `_episodic_skip_reason` 與 `log_episodic_event`（skipped／generated／failed → `Logs/guard-episodic.jsonl`，不受 atom_debug 開關）；`health-weekly` 產物看根層＋所有專案層、無產物時依事件分「正常跳過（原因分布）／失敗→紅／無事件→黃（首週）／有 generated 卻無檔→紅」；生成資格未改｜離線驗證：本機根層最新產物 09-21 14:33（今天 guardian session），可直接推翻「停擺」
- [x] **SessionStart 例外浮出＋測試 Logs 隔離**｜改：`_unpushed_advisory`／`_personal_sync_advisory` 內部錯誤回一行 ⚠（health／followup 原已有）；`wg_core.logs_dir()`：pytest（PYTEST_CURRENT_TEST）或 `WG_TEST_LOGS_DIR` → 暫存目錄，guard log 與 atom-debug 都走它；monkeypatch 過的 GUARD_LOG_DIR 仍尊重
- [x] **hint 支線停寫**｜改：`_emit_usefulness_hints` 只剩 ReadHits++；健檢 promotion 鮮度標籤改「heartbeat／晉升事件」（heartbeat 本來就在寫）
- [x] **worker 起訖 log**｜改：`Logs/guard-worker-runs.jsonl`：spawn（wg_extraction）／start／finish（items、elapsed_s）／crash（extract-worker）
- [x] **文件三處**｜改：TECH §2.1 Hook 硬牆、§6.3 全量萃取「未啟動」、§6.3 detached 理由、§11 always-load 估算 5,459、§14.2 cross_session 註記；Architecture.md 未動（審查未釘出具體矛盾行，留 Phase 3 收斂）
- 驗：新增 `hooks/verify/verify_attribution_turn_identity.py`（8 案例：Agent prompt 不進比對／非派工工具 prompt 照比對／retry 增量三情境／同 atom 兩來源只寫一筆／衝突不寫且留 conflicted／stale 子代理紀錄不套當輪／舊格式紀錄相容）、`verify_harness_prompt_guard.py`（4 案例）；既有三個測試依新契約更新（內部錯誤回警告、UPS 無 hint）；受影響 9 個 verify 檔 110 案例全過；完整 `run_verify.py` 第一輪 1,888 案例 4 失敗皆為上述契約變更已修，另 1 筆 `verify_lf_writes` 失敗來自他 session 未追蹤的 `tools/usage-snapshot/`，非本次改動
- 未做（留 Phase 1b／3）：episodic 首週事件 log 才開始累積，健檢對「無產物且無事件」暫報黃燈

### Phase 1b 記帳與評估器（2026-09-21 完成）
- [x] **最終送達單一入口**｜改：`assemble_injection` 內 `_push()` 對 cold 行／skip 路標／標頭全部計費，塞不下記 `dropped` 不送（1,200 tok 變真硬頂）；skip 路標標題截 80 字；`_truncate_context_by_activation` 改「lines 一元素＝一區塊」（Guardian 尾訊息不再被裁）；新增 `reconcile_injection_after_trim`：對照最終 lines 把整塊裁掉的標 `dropped_trim`、撤 injected_atoms／rescue watch、不計曝光，降成指標的標 `pointer_trim`；曝光（ReadHits）與回合 log 改在結算後寫且以送出記錄的 path 計（Related 專有候選也記曝光）；UPS 的 `turn_injected` 只放實際送出者；最終裁切改用總額（不再被 episodic/JIT 保留量扣兩次）；回合 log 多記 `out_chars`、`delivered`｜驗：`verify_injection_delivery_accounting.py` 5 案＋既有 94 案全過
- [x] **對齊評估器**｜改：`tools/memory-eval/online_replay.py`（凍結時鐘、vector 替身、不掃他專案、不寫曝光；走 collect_matched_atoms→assemble→裁切→結算）＋ `run.py --online`（三層指標、`--set` 覆寫、`--frozen-time`、`--dump`、`--baseline baseline_online.json` 退步 exit 2、skip 分類 archived／relocated／renamed?／missing）；34 條跳過全為 `_distant/` 封存（屬預期）；補 8 條「幫我／我想」請求措辭負例（負例 14→22）｜效：Codex #5 的探針數字已由 [AI] 親自重跑證實（gain 0.25 R@1 42.3% vs gain 0 80.0%）
- [x] **舊 sidecar 快照與切點**｜改：不重算歷史 α/β；切點＝2026-09-21 本 commit（判用政策 v2 上線）
- [x] **使用判定標註集**｜產出：`tools/memory-eval/usage_labels.jsonl` 57 筆（真 38／合成 19；adopted 10／corrected 9／cited 9／rejected 9／unknown 20；AI 標註未人工複核，`review_flag` 標最需複核 5 筆）＋ `eval_usage.py`（v1 網格）＋ `eval_usage_v2.py`（v1 vs v2）｜發現：v1 詞彙重疊 precision 0.18（adopted）／0.35（adopted+corrected），12 組門檻全 0.17–0.22——門檻是死路，要換判定依據

### Phase 2 歸因與排序（2026-09-21 完成）
- [x] **歸因判定校準 → 判用 v2**｜錯：門檻調不動（見上）；FP 主因是路標／cold 行的路徑片段與泛雙字；否定與引用靠共享 token 必中｜改：`wg_atoms.detect_atom_use_v2`：① 否定線索（不要用／已過時／被取代／無關…）緊鄰 atom 錨點（[Atom:name]、slug 片段、或 ≥2 專屬 token）→ rejected；② rescue 特異 token（≥8 字、非純路徑、非泛 git 指令）命中 → used；③ 引用線索（講的是／指的是…）→ cited 不算；④ 只送路標／cold 且未 Read 該檔 → 不算；⑤ 去路徑噪音後共享 ≥6（Read 過放寬 ≥2）。Stop 依 `usefulness.attribution_policy`（v2；`v1` 回滾）呼叫，rescue 證據由 `wg_rescue.rescue_hits_for_turn` 讀本 turn log、送出形式由 injection_log 取｜效：同一標註集「有沒有用到」P 0.35→**0.67**、R 1.00→0.84；rejected 判 used 9/9→1/9、cited 9/9→3/9、unknown 18/20→4/20（Codex #8 反例修正後的最終數字：否定／引用改「綁定到這顆 atom」的句型規則、Read 證據只認工具行、路標未讀時 rescue 也不算）｜驗：`verify_attribution_v2.py` 9 案；既有閉環測試固定 v1 語意照過
- [x] **晉升去重**｜1a 已做同 atom 同輪去重；統計單位與門檻不動；demote 候選以切點後資料重看（Phase 4 觀察）
- [x] **排序離線對照 → 已採用**｜同凍結時鐘、175 正例／22 負例：現行（gain 0.25、BM25 只補位）R@1 45.1%／MRR 0.639／全文送達 78.9%／負例 4.5% → **gain 0＋BM25 每輪跑** R@1 81.1%／MRR 0.870／全文送達 88.0%／負例 4.5%（三層同升、負例不升 → 依採用規則以 config 上線：`vector_search.rrf_activation_gain: 0`、`bm25_gate_max_trigger_hits: 999`）；BM25 剔除請求框架 bigram（`_BM25_CJK_STOP`）讓補負例後的誤注入 31.8%→4.5%；`workflow-research-fanout` 移除「我想知道／想了解」兩個泛 trigger；限幅 ±0.4 未測（gain 0 已在三層全勝）｜基線 `baseline_online.json` 已建
- [x] **Supersedes 全路徑不變條件**｜改：`collect_superseded_names`（鏈式）在 SessionStart 算一次存 `atom_index.superseded`，UPS 候選池先過濾（舊 state 沒有就補算），子代理注入 `build_injection_blob` 用 mtime 快取版；歷史查詢語（以前／舊版／被取代…）放行｜驗：`verify_supersedes_pool_and_bm25_stop.py` 8 案（含 New.Related→Old 不回流、只有舊卡命中也不出現、歷史查詢保留、子代理池）
- [x] **Related 擴散 query gate**（原 Phase 4 三組對照提前）｜同凍結時鐘：gate 關 extras 4.33 顆／gate BM25≥3.5 → 2.95／≥5 → 2.52／完全關閉 → 2.14；期望 atom 三層在前三組完全相同，完全關閉反而多 1 題 missing → 採 **gate ≥5**（`injection.related_gate.query_gate_min`；`related_depth` 0 可整個關）；線上遙測 Related 佔曝光 110/206 而判用率與 trigger 相當（22% vs 25%，v1 口徑有污染）→ 不砍只收窄
- 裁決（不再是延後）：「糾正標待查」**取消**——會在 UPS 多一個待辦狀態與邊界規則（最後一輪無下一 UPS、通知回合、重複 Stop），噪音大於收益，v2 已用否定線索與拒用規則涵蓋主要情境；「session 封頂政策」**不立項**——統計單位維持現狀，同輪去重（1a）已擋掉「一場刷三次」，其餘等一週切點資料再看。

### Phase 3 skill 與精簡（2026-09-21，由 Claude agent 分檔執行）
- [x] `/extract` 整檔重寫：移除路徑 A（傳給 worker 的 JSON 缺 session_id/cwd 永遠空結果，且 per_turn 回寫會復活停用管線）、只留「從對話整理 → atom_write」、新建一律 [臨]、可再生內容不收、不手改 MEMORY.md
- [x] skill 稽核器契約：`audit-skill.py` 改 pyyaml 解析；fail 只剩「SKILL.md 不存在／YAML 壞／缺 description」（官方文件今日外查：沒有任何欄位必填、500 行是 Tip），name／legacy 拼法／非官方欄位／>500 行／triggers·pattern·evals 全 warning 並標 `src: official|local`；`userInvocable`→`user-invocable`（SKILL.md、模板、5 個 pattern、refile）；稽核表與程式對齊｜實跑：21 個 skill 19 fail → 0 fail；新 `verify_audit_skill.py` 7 案
- [x] active skill 寫入契約與固定儀式：read-project（導覽只寫 `_AIDocs/DocIndex-*`，atom 只留矛盾／隱含決策／踩坑，走 atom_write）、consciousness-stream（反省句不落地、只有證實的坑與拍板才 atom_write）、upgrade（V4 手工配方隔離到「歷史遷移」段）、fix-escalation（≤2 代理根因＋獨立驗證 → 判定閘 → 才開會議）、skill-creator（先填已知只問缺口）；`tools/memory-write-gate.py` 新增 `regenerable_signals()` 只警告不擋分（新 `verify_write_gate_regenerable.py` 6 案）
- [x] memory skill：無參數＝直接 health；review 改六步只看不動；`--self-iterate` 改指向 SessionEnd `_self_iterate_atoms`
- [x] Codex 裁判紀錄分母：`_record_unbound` 改寫「綁定列」不帶 verdict；`promotion_stats()` 只算 bound 列並另算綁定覆蓋率／人工標註三類；轉正條件改「人工標註 ≥20 且三類各 ≥5 ∧ precision ≥0.60 ∧ 無理由棄權率 ≤0.30」；新增 `acceptance.py --stats | --list-unlabeled | --label`｜對照：全檔 443 列 uncertain 93.2% → 真裁判 56 列 46.4%，綁定覆蓋率 12.6%（350 筆 other_session）——瓶頸是綁定不是裁判
- [x] failure provenance：reader 改回 `[{text, uuid, ts}]`（順修 `f.tell()` 在 for 迭代中拋錯致增量 offset 永不前進的既有 bug）；`_attach_failure_sources` 用同一把 `extract_distinctive_tokens` 對回 LLM 看過的 3,000 字窗內各段，知識行下寫 `<!-- src: {sid8}#{uuid8} -->`，對不回寫 `#unresolved 未對回原句`，不補造行號｜新 4 案
- [x] fork 子代理去重：`pre_tool_use.py` 只在 `subagent_type=="fork"` 時把 `state.injected_atoms` 當 `already_injected` 傳給 `build_injection_blob`（fork 繼承父對話；一般子代理不繼承、行為照舊）｜`verify_subagent_injection_phase1.py` +3 案（24/24）
- [x] `prompt_cache` statusline：`tools/statusline.py` `_cache_segment`（`hit_ratio`→`cache91%`，warm 綠／冷 dim，缺欄不顯示；官方 2.1.251 起提供、本機 CLI 2.1.252）｜`verify_statusline.py` +3 案（11/11）。本機 VS Code／SDK 模式的 session 不呼叫 statusline，未能實看 JSON
- [x] 孤兒清理：刪 `wg_atoms._parse_atom_index_file`、`wg_core.get_scope_dir`／`get_project_claude_dir`（全 repo＋`C:\Projects\.claude`、`C:\TSLG\.claude` 零 live 引用）；config 刪 `heal.run_full_verify`、`world_dev` 區塊；同步 `world.html:981` 註解與 Architecture.md 兩行
- [x] **merge-atom-index --resolve 效能**：瓶頸是 14 個序列 git 子行程（Windows 每個 ~0.15s）；`_resolve_git` 改 ThreadPoolExecutor 三段併行（ls-files → check-attr∥cat-file∥install 讀 → install 寫∥merge-file×3∥驅動合併 → add），省掉 `rev-parse`，合併結果逐 byte 同前｜安靜機器 hook 全程 2.55／2.56／2.78s（逾時）→ 1.50／1.61／1.86／2.02s；`verify_merge_driver_gate.py` 27 過、`verify_merge_atom_index.py` 39 過；預算題單獨三跑三過。限制：他 session 同時重負載（CPU 50%+）時 git 子行程漲到 0.3–0.5s 仍可能偶發逾時；固定成本 python 啟動＋import 0.3–0.45s。順帶發現未改：check-attr 未通過的 unmerged 索引檔被靜默略過、不進 `remaining`
- [x] Architecture.md 收斂為索引：433 → 274 行；機制細節改為指向 TECH／SPEC／DevHistory 的一行指標，只留唯一來源段（PreToolUse 寫入守門、Auto-Handoff 四層、反退避判定細節、CHANGELOG Auto-Roll、Knowledge 3072 bytes 預算、funnel 接線表、MCP 孤兒防治、Testing 原則、腦內世界兩段）；順帶更正 Skills invocation 與 funnel caller 的實況。agent 另指出 TECH 兩處與實碼不符（token 預警實在 Stop 非 PostToolBatch；退避偵測實在 Stop 非 PostToolUse）與 DocIndex 計數過時——已由 [AI] 回寫（見 §10）｜錯：`verify_merge_driver_gate::test_resolver_fits_hook_budget` 在本機負載 16–25%（他 session 14 支 pythonw＋12 支 node）時 resolver 跑 2.55–2.58s，超過 PreToolUse 內 2.5s 預算 → 使用者會看到「⚠ 索引檔自動解逾時」而非自動解；stash 回 HEAD 版 wg_core 仍同樣，與本次改動無關，是既有邊界問題｜改：用 `GIT_TRACE` 量 `_resolve_git` 的 git 子程序數（`_git()` 呼叫點 16 處），三檔 × 三 stage 的 `git show` 批次化或改讀 index blob；預算 2.5s 不放寬｜效：負載機器上自動解仍在預算內｜驗：同測試在負載下三跑三過
- **原延後四項（2026-09-21 晚間再收）**：① skill 可見性——`/skill-doctor` 是 CC 內建指令、hook 無法代跑；改用可回滾的 frontmatter：對 60 天零呼叫且純手動用途的 browse-sprites／harvest／journal 加 `disable-model-invocation: true`（changelog-debug／generate-episodic／upgrade 原本就有），read-project／skill-creator／consciousness-stream／karpathy-guidelines 保留自動觸發（它們的描述就是觸發條件）；② PostToolUse 併二——**已做**：先量真實延遲（三支並跑中位 651.9ms → 只剩 guardian 490.9ms，關鍵路徑省 ≈161ms，過 100ms 門檻才合），再把 `version_guard.py`／`acceptance_spec.py` 改成 `run(input_data, config)` 由 `post_tool_use.py` 同程序呼叫，`settings.json` 刪兩 hook、matcher 加 `MultiEdit|ExitPlanMode`；39 案事件等價回放 `verify_post_tool_use_companion_merge.py` 全過；回滾＝settings.json 加回兩區塊＋revert post_tool_use.py；③ AEC-Pending——**裁決保留不動**：30 天 0 真觸發代表沒人違約、不代表閘沒用，不觸發時零成本，且它守的是「記憶寫入不得推給下回合」這條硬契約；④ Codex 裁判標註——**已做 33 筆**（AI 標、逐筆附 transcript 證據：known_good 6／known_defect 20／insufficient 7；`--stats` labeled 2→35、precision 0.95、miss_rate 0.136、無理由棄權 0.286、promotion_ready 翻 true）。**[AI] 裁決不照單轉正**：20 筆「defect」裡 13 筆是代理人明說「還在等背景／外部」的等待回合，裁判把等待當完工宣稱擋下，precision 是被這種假陽性撐起來的；真考眼力的只有 2 筆，且 3 筆真漏放都是「測試綠但輸出語意錯」。→ 新增剩餘項 ⑤：裁判加 awaiting 識別（最後一段 assistant 文字明示等待背景／外部時只 warn 不 enforce，並在 audit 列標 `awaiting`），做完重算 precision 再談轉正；⑥ sub-agent 紅測混入主 session failing_tests（本 session TestFailGate 兩次誤火即此因）——**已做**：`post_tool_use._track_test_result` 對帶 `agent_id` 的 hook 事件不記不清（官方 hooks 文件 Common input fields：子代理內才有 agent_id／agent_type），5 案測試。報告：`_AIDocs/DevHistory/全面檢視-2026-09-21/acceptance-labels-2026-09-21.md`；標籤寫在 `workflow/acceptance-audit.jsonl`（gitignore，不進版控）
- 週健檢存量 broken refs 5／duplicates 7：沿用 `/memory health`，不在本計畫範圍

### Phase 4 離線研究
- [x] Related 四臂對照 → 已採 query gate ≥5（見 Phase 2）
- [x] constraint pinning 缺口驗證 → **砍**：官方 memory 文件（2026-09-21 查）明載「Project-root CLAUDE.md survives compaction: after /compact, Claude re-reads it from disk and re-injects it」，本系統三條硬契約（動手前預告、上GIT、收尾誠實）都在根層 CLAUDE.md @import 的 IDENTITY／USER 裡，且各有程式化閘（PAN／git commit 口令閘／ScanReport／DeferralGate）不靠 prompt 記得；PostToolBatch 另會把壓縮前的 atom 內文重注入。使用者層 `~/.claude/CLAUDE.md` 在專案 session 壓縮後是否重讀未實測，但 hook 閘兜底 → 不加第二份規範
- [ ] 查詢—卡片相關性標註 → 誤送／漏送分開量 → 一次只測一個棄權閘（未開始；現有評估器的「額外送出顆數」只是代理指標；需要先有相關性標註）
- 砍：TEPA／Hindsight（本輪不加 conflict_key）

### 分工
- [AI]：全部修改、驗證、文件；每 Phase 完成後報告「改了什麼／驗了什麼／數字前後」。
- [使用者]：看 Phase 報告；下「上GIT」。**無其他待拍板事項**——gain、DF 門檻、session 封頂、裁判去留全由驗證數據決定；共享性變更（skill 可見性、helper 刪除）本輪不做或只在零外部引用時做。

## 7. 證據位置（持久）
`_AIDocs/DevHistory/全面檢視-2026-09-21/`：brief.md（共同簡報）、claude_{A,B,C,D,F}_*.md、codex_{1..5}_*_summary.md、claude_decision_draft.md（[AI] 獨立評分稿）、telemetry_audit*.py 與輸出、`codex-full/reply_{1..5,review,decide}.md`（Codex 全文）。

## 8. [Codex 審查] 裁決紀錄
- #6（計畫初稿）：全部採納（R2 名次、R3 分母、R5 母體、R6 三類、R7 未修項、R8 估算、hint 與 ReadHits 同函式、刪 <0.5 門檻、rescue 語意、晉升拆開、gain／裁切／BM25 分開、episodic 拆、AEC 暫緩、併二非併四、pinning 先驗、TEPA α 混用、9,000 字元降為待驗、漏項五件、舊 α/β 切點、broken refs 沿用）。
- #7（拍板）：B1 回合身分 → 採納，合併為 1a「回合身分統一」；B2 裁判分母 → 採納，佔位列改法延後到 Phase 3 與報表同改、裁判保留；B3 門檻 → 採納，撤 2→3、改標註集共同校準；B4 健檢語意 → 採納；B5 provenance → 採納；B6 棄權閘 → 採納，改為先標註再單閘離線；B7 TEPA → 採納砍；B8 commit 契約 → 採納改寫。**[AI] 保留裁決一處**：2-5 gain 採用規則——Codex 要求端到端證據才部署，[AI] 判定端到端無法便宜量測、以三層指標＋負例＋config 回滾＋一週觀察為採用條件（靈活不 zombie）。cross_session：Codex 建議保留共享預設，[AI] 查證唯一消費端在不 spawn 的 worker 內，故不動 config、只文件標除役（兩者結果一致）。
- 帶偏檢討（#7 指出，[AI] 承認）：把容量數字推成需要棄權演算法；為借 TEPA 先加欄位；把觀測指標當成果；把工程判斷（gain／封頂／裁判去留）推給使用者。已全部改正。
- #8（Phase 1b／2 diff 零容忍審查）：5 個 BLOCK 全部修正並各補反例測試——B1 專案 `_AIAtoms/` Supersedes 掃錯根目錄（SessionStart 改與 UPS 同一 base 規則）；B2 「不要用以前的…」被當歷史查詢（改「有查閱動詞且無否定」才放行）；B3 否定／引用 ±80 字窗口誤殺正常採用（改綁定到 atom 的句型規則；轉述句拿掉再比對）；B4 路標未讀的兩條穿透（Read 證據只認工具行；pointer_trim 撤 rescue watch、rescue 不能繞過未讀）；B5 子代理借父證據製造假衝突（子代理只用自身產出）。WARN 全部處理：三態決策含標頭且全文不行先試節錄、同顆不再留兩筆；rescue 本 turn 命中進 state；Supersedes 快取 key 加 atom mtime；health episodic 按 session 計且失敗獨立報紅；報表送達欄改名並註明只量 atom 段；缺鍵預設與 config 值的差異已在 §9 列明。數字核對：新設定 R@1 81.1%／MRR 0.870 重現；舊設定 45.1 vs 44.6 的差異來自 sidecar 在兩次跑之間被線上 hook 更新（凍結時鐘不凍結輸入）——已在 README 註明。判用 v2 最終：P 0.67／R 0.84（adopted+corrected）。

## 9. 執行邊界（與 §0 同義，接手者以此為準）
Phase 0／1a／1b／2 已完成，Phase 3 除「延後」清單外已完成，Phase 4 只剩相關性標註（本 session，全部未提交，等「上GIT」）。已上線且可 config 回滾的行為變更：`vector_search.rrf_activation_gain: 0`、`bm25_gate_max_trigger_hits: 999`、`injection.related_gate.query_gate_min: 5`、`usefulness.attribution_policy: v2`；觀察一週 usefulness 切點資料（`Logs/injection-turns.jsonl` 的 delivered／dropped_trim、sidecar 新 α/β）。下一 session 入口：`/continue` 讀本檔 §6 Phase 3「延後」與 Phase 4；舊指示「從 Phase 1b 開始」作廢。

## 11. 「上GIT」提交清單（精確路徑，供選擇性 staging）
**納入（本次全面檢視所有產出）**——直接 `git add` 下列路徑；`memory/`、`_AIDocs/_atoms/` 下的索引重生檔與新 atom 也納入：
```
_AIDocs/_CHANGELOG.md  _AIDocs/_INDEX.md  _AIDocs/Architecture.md  _AIDocs/DevHistory/_INDEX.md  _AIDocs/DocIndex-System.md
_AIDocs/DevHistory/全面檢視-2026-09-21/
TECH.md  workflow/config.json  skills/_skill_index.json
hooks/codex_companion.py  hooks/extract-worker.py  hooks/wg_atoms.py  hooks/wg_core.py  hooks/wg_docdrift.py  hooks/wg_episodic.py
hooks/wg_evasion.py  hooks/wg_extraction.py  hooks/wg_friction.py  hooks/wg_recall_miss.py  hooks/wg_rescue.py
hooks/handlers/_shared.py  hooks/handlers/post_tool_use.py  hooks/handlers/pre_tool_use.py  hooks/handlers/session_start.py
hooks/handlers/stop.py  hooks/handlers/ups_inject.py  hooks/handlers/ups_search.py  hooks/handlers/user_prompt_submit.py
hooks/verify/verify_acceptance_review.py  hooks/verify/verify_failure_skeleton.py  hooks/verify/verify_merge_driver_gate.py
hooks/verify/verify_personal_sync_advisory.py  hooks/verify/verify_statusline.py  hooks/verify/verify_subagent_injection_phase1.py
hooks/verify/verify_unpushed_advisory.py  hooks/verify/verify_usefulness_loop_phase2.py
hooks/verify/verify_attribution_turn_identity.py  hooks/verify/verify_attribution_v2.py  hooks/verify/verify_harness_prompt_guard.py
hooks/verify/verify_injection_delivery_accounting.py  hooks/verify/verify_state_loss_guard.py  hooks/verify/verify_supersedes_pool_and_bm25_stop.py
settings.json  hooks/version_guard.py  hooks/acceptance_spec.py  hooks/verify/verify_acceptance_spec.py  hooks/verify/verify_post_tool_use_companion_merge.py
skills/browse-sprites/SKILL.md  skills/harvest/SKILL.md  skills/journal/SKILL.md  _AIDocs/DevHistory/全面檢視-2026-09-21/acceptance-labels-2026-09-21.md
skills/consciousness-stream/SKILL.md  skills/extract/SKILL.md  skills/fix-escalation/SKILL.md  skills/memory/SKILL.md
skills/read-project/SKILL.md  skills/refile/SKILL.md  skills/upgrade/SKILL.md  skills/skill-creator/SKILL.md
skills/skill-creator/assets/skill-template.md  skills/skill-creator/assets/patterns/generator.md  skills/skill-creator/assets/patterns/inversion.md
skills/skill-creator/assets/patterns/pipeline.md  skills/skill-creator/assets/patterns/reviewer.md  skills/skill-creator/assets/patterns/tool-wrapper.md
skills/skill-creator/references/principles.md  skills/skill-creator/scripts/audit-skill.py  skills/skill-creator/verify/
tools/codex-companion/acceptance.py  tools/health-weekly.py  tools/memory-write-gate.py  tools/merge-atom-index.py  tools/statusline.py
tools/workflow-guardian-mcp/world.html  tools/verify/verify_write_gate_regenerable.py
tools/memory-eval/README.md  tools/memory-eval/run.py  tools/memory-eval/online_replay.py  tools/memory-eval/eval_usage.py
tools/memory-eval/eval_usage_v2.py  tools/memory-eval/queries.jsonl  tools/memory-eval/baseline.json  tools/memory-eval/baseline_online.json
tools/memory-eval/usage_labels.jsonl  tools/memory-eval/usage_eval_report.md
memory/_atom_index.json  memory/_ATOM_INDEX.md  memory/_local_catalog.md  memory/MEMORY.md
memory/Failures/_INDEX.md  memory/Failures/工作流/_INDEX.md  memory/Failures/行為契約/_INDEX.md  memory/行為契約/_INDEX.md  memory/驗證與實證/_INDEX.md
_AIDocs/_atoms/MemDev/_INDEX.md
memory/工作流/協作與並行/workflow-research-fanout.md（trigger 修剪）
memory/_staging/next-phase-全面檢視-2026-09-21.md  .claude/verify/done/acceptance-全面檢視-2026-09-21.md
tools/usage-snapshot/usage_snapshot.py（他 session 已提交的檔，順手補兩處 newline= 讓 verify_lf_writes 轉綠）
_AIDocs/DevHistory/全面檢視-2026-09-21/codex-full/reply_review_diff_block.md（Codex #8 全文）
_AIDocs/_atoms/MemDev/糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem.md
_AIDocs/_atoms/MemDev/活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞.md
memory/Failures/工作流/feedback-暫時偵錯碼插進被外部程序持續執行的-live-檔案前後必-py-compile-一次語法錯誤讓使用者-statusline-整個失效.md
memory/Failures/行為契約/feedback-建檔或改名後回報一律給絕對路徑-相對連結與中途改名讓使用者找不到報告.md
memory/行為契約/所有決策和報告必須提供清晰的問題-數據佐證-並以易懂的白話形式-指出錯誤-優化點.md
memory/驗證與實證/時間預算類測試量測時同回合不得並行其他重負載工具呼叫-否則數字被自己污染.md
```
**排除（他 session 在本次開始前就已修改、非本次產出）**：
```
_AIDocs/_atoms/CC與原子記憶契約/codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated.md
_AIDocs/_atoms/MemDev/禁語-hook-不開引用豁免誤報噪音-vs-契約破洞不對稱.md
memory/Failures/CC與原子記憶契約/feedback-原子記憶核心理念-知識經驗全積累分門別類-高精準零token浪費.md
memory/Failures/工作流/feedback-workflow-discipline.md
memory/驗證與實證/在使用者活躍桌面彈視窗做gui實驗會被順手關掉污染數據-改headless-edge加cdp或先查前景視窗.md
```
**只有 Last-used／access 更新的 atom（注入時 hook 自動蓋章，非內容變更）**——可納可不納，不影響功能：`_AIDocs/_atoms/MemDev/posttooluse的tool-response…md`、`_AIDocs/_atoms/Tools/codegraph與agent-retro評估結論…md`、`memory/CC與原子記憶契約/escalation-hook-…md`、`memory/Failures/工作流/feedback-收尾報告使用者視角四要素-…md`、`memory/工作流/節奏與收尾/handoff-綜觀品質與抗失真寫法.md`。

## 10. 本 session 執行中的額外發現（已修）
- **壓縮後自動接續**：SessionStart 在 `source=compact|resume` 時多注入一行 `[Guardian:Resume]`，指向最新的 `_staging/next-phase-*.md`（專案層優先、其次根層）並要求先 Read、覆述現狀＋下一步再動工——不靠模型記得該去讀；PreCompact 的 handoff stub 與 PostToolBatch 的 atom 重注入照舊。
- **活躍 session state 被 fallback 覆蓋**（turn 15 歷史歸零）：`read_state` 把「檔在但讀失敗」當遺失 → `_ensure_state` 建 fallback 覆蓋；`_cleanup_old_states` 對有 prompt 的 working state 30 分鐘沒寫就刪。已修（`read_state_status`＋重試三次不覆蓋；TTL 6h），`verify_state_loss_guard.py` 4 案。
- `wg_docdrift` 對 `result.stdout=None` 的 `.splitlines()` 例外（每次 PostToolUse 落 ERROR log）已修。
- 另一支 agent 暫留在 `tools/statusline.py` 的 TEMP-DUMP 行含真換行 → statusline SyntaxError 對使用者當下失效；已移除並還原，該 agent 後續正式落地 `_cache_segment`（prompt_cache 顯示）。
