**結論：最值得優先做的是修正「實際送出內容與記帳不一致」、讓回歸評估走真正管線，再降低 activation 對排序的支配；目前沒有證據支持新增模型式 reranker。**

本次只讀本地程式與遙測，未上網、未修改檔案。已完成 10 個檔案的語法解析、10 項現有純函式預算測試，以及不落盤的搜尋／組裝／裁切探針。以下主要數字取自 **2026-09-21 14:52–14:56、193 顆索引**；其他流程在審查期間新增了 atom，14:57 的補充統計另行標明。

## 候選清單

成本為工程估算，非實測工時。「實測」指本次本地重播或合成探針，不代表線上效果已驗收。

| # | 名稱 | 來源（檔案:行） | 機制（函式、常數與具體改法） | 類型 | 對本系統的意義 | 第一個 session 看得到的效果 | 成本／風險 | 證據等級 |
|---|---|---|---|---|---|---|---|---|
| 1 | **裁切完成後才提交注入記錄；完整計費** | [ups_inject.py:213](/C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:213)、[user_prompt_submit.py:398](/C:/Users/holylight/.claude/hooks/handlers/user_prompt_submit.py:398)、[wg_atoms.py:1251](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1251) | `assemble_injection()` 的 cold／skip 路標不增加 `used_tokens`，全文標頭也未完整計費。`_truncate_context_by_activation()` 又以「下一個 Atom 標頭」界定區塊，會把尾端 Guardian 訊息包進最後一顆 atom。改成每個 `lines` 元素保留自己的類型與邊界，按完整輸出計費；裁切後才更新 `turn_injected`、session 去重、曝光與救援 watch。 | 補強＋精簡 | 修復排序、預算、曝光、效用歸因與 recall-miss 共用的上游事實來源。Related 注入也須走同一筆最終記帳。 | Guardian 訊息不會跟著 atom 消失；被丟棄的卡不再標成已注入。 | **1–2 人日**；須處理同 session 去重相容性。 | **實測**：133/175 次 atom 段超過 1,200 估算 token；合成案例裁掉 Guardian 訊息。 |
| 2 | **讓回歸評估覆蓋線上排序與最終輸出** | [run.py:77](/C:/Users/holylight/.claude/tools/memory-eval/run.py:77)、[run.py:157](/C:/Users/holylight/.claude/tools/memory-eval/run.py:157)、[run.py:293](/C:/Users/holylight/.claude/tools/memory-eval/run.py:293) | 現行 `retrieve()` 仍是索引序 trigger＋BM25 接尾，沒有 RRF、activation 或預算裁切。改以固定時間、固定 sidecar 快照呼叫實際搜尋函式，另算最終內容保留率，並保留原有純檢索分數供定位。過期標籤與基線樣本數不同須顯式報告；基線退步應回傳非零退出碼，目前 `compare_baseline()` 的結果被忽略。 | 補強 | 避免用不受 RRF 參數影響的工具，驗證 RRF 調參。 | 同次測試能指出問題在召回、排序或裁切哪一段。 | **0.5–1 人日**；主要風險是把活資料漂移誤當改法收益。 | **程式碼＋實測**：223 條中 34 條被跳過；評估排序與真正函式分數顯著不同。 |
| 3 | **將 activation 從主排序乘數降為次要訊號** | [ups_search.py:320](/C:/Users/holylight/.claude/hooks/handlers/ups_search.py:320)、[wg_atoms.py:370](/C:/Users/holylight/.claude/hooks/wg_atoms.py:370)、[wg_atoms.py:585](/C:/Users/holylight/.claude/hooks/wg_atoms.py:585) | 現行公式是 `F = Σ 1/(60+rank) × exp(0.25×A)`，其中 `A` 含分心懲罰。建議先把乘數增益設為可配置，以 **gain=0 作候選方案**，activation 只在相關性同分時破同分；最終裁切亦沿用搜尋優先序，不再另按裸 activation 重排。先以修正後的評估確認，再決定是否保留有限幅度調節。 | 精簡 | 直接減少「歷史曝光強度壓過本題相關性」的作用。 | 本地重播的預期 atom 更常排第一。 | **0.5–1 人日**；低頻但重要卡與慣用卡的取捨需額外案例。 | **實測**：真正搜尋函式 R@1 由 41.7% 到 80.0%；尚未證明回答品質同幅改善。 |
| 4 | **接上既有 DF 過濾，修正效用歸因證據範圍** | [stop.py:425](/C:/Users/holylight/.claude/hooks/handlers/stop.py:425)、[wg_atoms.py:1079](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1079)、[wg_atoms.py:1141](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1141) | `detect_atom_use()` 是「共享 token ≥2 **或** containment ≥0.18」，而 Stop 未傳入已有的 `df_map/n_docs`。先接上既有文件頻率（DF：一個詞出現在多少張卡）過濾，並只比對最終送出的節錄、或有 Read 證據的全文。`max_df_ratio=0.1` 可列入驗證，但不能只靠負例直接定案；一般措辭、提到卡名與否定引用都不應直接寫成功 α。 | 補強 | 修現有晉升訊號，無須再建一套效用系統。 | 一般收尾句造成的假「使用」顯著下降。 | **1–2 人日**；主要風險是提高精度卻漏掉真正遵守的行為規則。 | **實測**：三組無使用負控制由 59/579 個配對判 used，降為 9/579；不是線上假陽性率。 |
| 5 | **BM25 不再因命中三顆 trigger 就完全停跑** | [ups_search.py:228](/C:/Users/holylight/.claude/hooks/handlers/ups_search.py:228)、[wg_atoms.py:496](/C:/Users/holylight/.claude/hooks/wg_atoms.py:496)、[workflow/config.json:58](/C:/Users/holylight/.claude/workflow/config.json:58) | 候選改法是保留 `min_score=7.0/top_k=3`，每輪計算 BM25，讓它提供獨立排序證據。另針對「幫我／我想」這類純請求措辭做負例驗證，避免兩個高 IDF bigram 就越過 7.0。不要同時放寬分數門檻，避免無法判斷收益來源。 | 補強 | trigger 數量不再被當成「已有足夠相關性」的替代指標。 | 在既有資料上改善首名排序；仍低於 100ms 的本地運算目標。 | **0.5–1 人日**；本集未證明召回有新增收益。 | **實測**：BM25 p95 約 12ms；取消 gating 後純 RRF 的 R@1 80.0%→82.3%。 |
| 6 | **校正零曝光／token 稅報表，不另造量測** | [memory-effect-report.py:161](/C:/Users/holylight/.claude/tools/memory-effect-report.py:161)、[ups_inject.py:440](/C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:440)、[wg_recall_miss.py:113](/C:/Users/holylight/.claude/hooks/wg_recall_miss.py:113) | 零曝光現在只指近 30 天 `timestamps` 空；並非一生未注入。Related 專有候選未進 `_emit_usefulness_hints()` 的 `matched_with_dir` 迴圈，因此可能送出卻不加曝光。併入 #1 修記帳；報表區分「窗內未曝光／歷史未記曝光／缺檔」，token 稅另區分無成功證據與完全無結果證據。 | 補強＋精簡 | 避免把量測缺口判成 trigger 冷門或應刪除。 | 報表能解釋候選身分，不再只有一個「死重」標籤。 | **0.5 人日**；宜與 #1 同做，避免增加第二套帳。 | **程式碼＋遙測**：已有 Related 注入記錄但 `read_hits=0` 的實例。 |

**遙測母體先校正。** 簡報的「636 顆 sidecar」本次確認為 `memory/` **546 份**加 `_AIDocs/_atoms/` **90 份**，不是全部位於 `memory/`；其中 **409 份在 `_distant/`**，3 份找不到對應 markdown。不能拿 636 當目前可檢索卡片數。

14:52 快照如下：

| 母體 | sidecar 數 | `read_hits=0` | 有曝光記錄 | 有曝光但 α 沒有正向證據 | 有曝光但 α、β 都無結果證據 |
|---|---:|---:|---:|---:|---:|
| 兩個根目錄全部，含封存 | 636 | 156 | 480 | 325 | 310 |
| 當時索引中的有效卡片 | 193 | 19 | 174 | 28 | 15 |

這裡的 α 是 `useful_hits`、β 是 `used_fail`，各有先驗值 1，而且會衰減。因此「α 沒有正向證據」不能嚴格解讀為「歷史上從未有用」；β 也不是已證明 atom 導致錯誤的次數。[欄位語意與衰減公式](/C:/Users/holylight/.claude/lib/atom_access.py:12)

對 174 顆有曝光的有效卡，159 顆有結果證據；其 **`(α−1)/(α+β−2)` 成功比例**分布為：

| 比例 | 0 | (0,25%] | (25%,50%] | (50%,75%] | (75%,100%) | 100% | 無結果證據 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 卡片數 | 13 | 9 | 20 | 68 | 20 | 29 | 15 |

這是「被判使用且結果可判定後的成功比例」，**不是每次曝光的有用率**；目前 sidecar 不足以精確還原後者。

## 最值得做的 5 件（排序 + 理由）

### 1. 先修最終輸出、預算與記帳的一致性

這是影響面最大的根因，應把候選 #6 併入處理。

已重現的問題：

- **1,200 token 並非完整 atom 段硬頂。** 對 175 個正例跑真正 `collect_matched_atoms()`＋`assemble_injection()`，133 次組裝內容超過此值，最高 **2,225**。這裡仍使用系統自己的 `_estimate_tokens()`，不是供應商 tokenizer；超額不需要依賴估算器誤差才能發生。
- **尾端 Guardian 訊息會隨 atom 被裁掉。** 合成輸入為一個 Atom 區塊加一個獨立 Guardian 訊息，裁切後只剩 atom 路標，Guardian 訊息消失。
- **記帳在裁切之前。** 此次重播有 2 個正例回合、共 4 顆已登記注入的 atom 被最後裁掉；正式流程仍會把它們留在去重與效用歸因資料中。[組裝記帳](/C:/Users/holylight/.claude/hooks/handlers/ups_inject.py:381)、[輸出前裁切](/C:/Users/holylight/.claude/hooks/handlers/user_prompt_submit.py:397)
- `build_context()` 已把 JIT／episodic 加進 `lines`，又扣除保留預算；最後卻拿扣後預算檢查整包，形成重複扣額。[ups_context.py:95](/C:/Users/holylight/.claude/hooks/handlers/ups_context.py:95)、[ups_context.py:175](/C:/Users/holylight/.claude/hooks/handlers/ups_context.py:175)

**驗證方式：** 保留現有 223 條查詢，增加「Atom 後接 Guardian」「只有路標」「兩次 skip 後仍有小卡」「JIT 已占額度」「Related-only 注入」案例。要求完整 atom 段符合配置上限、非 atom 訊息不被誤裁、送出名單與所有記帳一致。現有 10 項純預算測試本次全過，說明它們尚未覆蓋上述組裝問題。

### 2. 修回歸評估的對象與分母

直接執行既有工具所得：

- 223 條中，**175 正例、14 負例參與計分，34 條 expect 已不在索引而被跳過**。
- R@1 **64.6%**、R@3 **91.4%**、MRR **0.774**、負例誤命中 **1/14**。
- 本地 `baseline.json` 實際為 R@1 **67.0%**、MRR **0.789**、正例 **209**；與簡報引用的文件數值不同。[baseline.json:2](/C:/Users/holylight/.claude/tools/memory-eval/baseline.json:2)

MRR 是「正確答案排名倒數的平均」；它和 R@1 一樣，必須量真正使用的排序才有意義。

**驗證方式：** 同一固定快照，同時輸出舊評估、實際搜尋與最終注入三層結果。不要直接刪掉 34 條舊問題來讓測試變綠：先辨識移名、移 realm 或真正除役；對可見性限制設明確預期。回歸失敗退出碼與過期標籤數亦須有測試。

### 3. 簡化 activation 的排序角色

**跨零沒有符號 bug；乘數幅度有問題。**

目前用的是指數，所以 activation 負值只會縮小分數，不會把排序分數變負。但 `k=60` 把 RRF 的相鄰名次差壓得很小：

- 單路第 1 與第 3 名的 RRF 比僅 `63/61 ≈ 1.033`。
- activation 只要相差 **約 0.129**，乘數便足以翻轉這個次序。
- 本次快照注入 rank 約 **−7.61 至 0.003**，對應乘數 **0.149 至 1.001**，差約 **6.7 倍**。

真正搜尋函式的離線重播結果如下；使用全域索引、新 session、關閉向量呼叫，寫入端以不落盤替身隔離：

| 排序方案 | R@1 | R@3 | MRR |
|---|---:|---:|---:|
| 現行 RRF × activation | 41.7% | 83.4% | 0.619 |
| RRF，gain=0 | **80.0%** | **93.1%** | **0.860** |
| rank 限幅至 ±0.4，再乘現行增益〔公式探針〕 | 73.7% | 92.0% | 0.826 |

移除乘數改變了 **82/189** 個有效查詢的首名。不是小幅調節。

不過，預期卡片在最終輸出「出現」的正例數只由 **162/175 到 164/175**，而且出現可能只是路標。因此不能把 R@1 的進步宣稱成同幅回答品質收益。

**驗證方式：** 先用 #2 固定時間與 sidecar，驗 R@1、R@3、最終全文／節錄保留率；再加慣用規則、低頻技術卡及新卡案例。回滾只需恢復 gain；不要同步改 Wilson 或衰減參數。

### 4. 修「使用」與「有用」之間的假訊號

主問題不是 0.18 太鬆，而是它前面有 **`共享 token ≥2` 的 OR 分支**。中文雙字詞並未真的保證稀有，而且 Stop 沒有接上既有 DF 過濾。

本次無使用負控制：

| 合成回覆 | 現行判 used 的卡數／193 | 接既有 DF、排除出現在超過 10% 卡片的詞 |
|---|---:|---:|
| 我已完成修改，重新檢查後沒有問題。 | 15 | 4 |
| 這次先檢查設定，稍後再說明結果。 | 24 | 2 |
| 這張卡並未使用，只是在討論相關問題。 | 20 | 3 |

只接預設 `max_df_ratio=0.5`，三組數字**完全不變**，所以「接好線」仍不足以證明門檻有效。

另有兩個限制：

- Stop 讀整張 atom 比對，即使當輪只送一行路標或 200-token 節錄。[stop.py:445](/C:/Users/holylight/.claude/hooks/handlers/stop.py:445)
- 「宣告完成且無失敗訊號」就算成功，並非實證 atom 帶來成功。[stop.py:347](/C:/Users/holylight/.claude/hooks/handlers/stop.py:347)

**便宜替代的取捨：** 引用 atom 名、Read 路徑或工具參數中的特定識別碼可作較強佐證，但單純提到卡名不等於採用。下一輪糾正可串接已有 friction 訊號做待查證標記，不能將前輪所有 atom 一起判負。

**驗證方式：** 檢索回歸集繼續守住召回；另用 `detect_atom_use()` 的正負配對驗證集評估歸因，包括否定引用、只讀未採用、工具實際採用，以及不用複述文字也能遵守的行為規則。這部分不能只靠 `queries.jsonl` 驗收。

### 5. 放寬 BM25 的執行 gating，但不放寬收錄門檻

`trigger 命中三顆`只表示有三張卡符合字串條件，不表示三張都相關。BM25 在此完全停跑，會喪失重新比較它們的機會。

本次 BM25 對 193 顆索引的耗時：中位 **8.45ms**、p95 **12.00ms**、最大 **14.22ms**。在 gain=0 的公式重播中，每輪都跑 BM25，使 R@1 **80.0%→82.3%**、MRR **0.860→0.875**，R@3 不變。

但要明講：**本集沒有找到「trigger 超過二顆導致期待 atom 完全無法由 BM25 補進來」的案例。** 現有證據支持改善排序，不支持宣稱已修復大量漏召回。

同時找到現有負例：

> 「幫我想三個晚餐菜色」命中 `workflow-research-fanout`。

14:57 的 194 顆索引上，BM25 約 **11.22 分**；共享詞只有「幫我」「我想」。這是請求措辭被當成內容證據，**不是 CJK trigger 子字串造成的誤命中**。

**驗證方式：** 保留 `7.0/3`，先單獨比較 gating；再加入料理、旅遊、一般聊天等帶「幫我／我想」的負例，獨立驗證請求措辭過濾。檢查負例誤命中率及 BM25 耗時，不只看 R@1。

## 明確不建議做的（+ 為什麼）

- **不據此宣稱「CJK 子字串造成大量假陽性」，也不全面改中文詞界。** 可以合成出「重構」誤中「多重構面」的例子，但現有 14 個負例的唯一命中來自 BM25。補充快照中，164 個 query–atom 配對僅由 CJK trigger 命中，其中 125 個不是單一期待標籤；評估集未標完整相關集合，不能把這 125 個全算誤報。
- **不採用單純 trigger 命中密度。** 將排序訊號改成「命中數／trigger 總數」，在 14:57 快照、175 正例的純 RRF 探針上，R@1 從 **80.0% 降到 69.1%**。它會懲罰寫了較多同義詞的卡；trigger IDF 加權也只得到 **79.4%**，未優於現行命中數。
- **不為 `<100ms` 目標加每輪 Ollama embedding 二次排序。** 本次未呼叫模型，不能保證其延遲；既有 embedding tiebreak 會序列產生兩份向量，設定單次 timeout 3 秒，並不是 100ms 路徑。[wg_atoms.py:1175](/C:/Users/holylight/.claude/hooks/wg_atoms.py:1175) 純 RRF＋BM25 已有更便宜的收益證據。
- **不按「零曝光候選 35」刪卡或全面擴 trigger。** 週報的 35 是 30 天窗口值。[週報:14](/C:/Users/holylight/.claude/workflow/health-reports/health-20260921.md:14) 14:52 已變 34，其中 19 顆無歷史曝光記錄、15 顆以前曝光過；14:57 已有 sidecar 的候選再變 33，以早上 09:00 的時間窗口回算可重現 35。這包含正常新卡、歷史使用與記帳缺口。
- **不重建 friction、rescue 或另一套「使用者糾正量測」。** 既有機制已存在；本次的增量應是關聯最終送出內容與證據，避免再加重疊子系統。

## 未查到／不確定的

1. **35 顆各自是 trigger 太冷門，還是被 budget 擠掉：目前不能完整歸因。** `injection-turns.jsonl` 只有回合彙總，缺候選逐顆流失原因；`atom_debug=false`，本地掃描也未找到 `final-trim atom=` 歷史記錄。[設定:2](/C:/Users/holylight/.claude/workflow/config.json:2) 已確認存在第三種原因：Related 注入沒有增加曝光。例如[此 state 的注入記錄](/C:/Users/holylight/.claude/workflow/state-094f7ab1-8a87-441d-af2e-d02590ca659a.json:3820)有「子專案cwd…」的 Related cold 注入，而讀取時 sidecar 仍為零曝光。
2. **真實效用歸因假陽性率未知。** 合成控制證明機制可誤判，尚無人工標註的真實回合對照，不能把探針比例當成正式錯判率。
3. **端到端回答品質與 UPS p95 未測。** 本次隔離了向量呼叫、曝光寫入及其他 context 來源；真正搜尋函式的 gain=.25 重播 p95 約 30.5ms，只能代表該受控子流程。
4. **recall-miss 不能當完整漏召回率。** 近 30 天本地有 8 筆原始紀錄、聚合為 5 個 atom；它會排除 session 中被標記注入過的卡，因此同樣受裁切前記帳影響。[排除邏輯](/C:/Users/holylight/.claude/hooks/wg_recall_miss.py:113)
5. **本次沒有實作變更。** 審查已得到足以推進的具體項目；建議主持者先將 #1 與 #6 合併為一致性修復，再完成 #2，最後用同一固定基線驗 #3–#5。這個順序能避免用失真的量測替排序改動背書。
