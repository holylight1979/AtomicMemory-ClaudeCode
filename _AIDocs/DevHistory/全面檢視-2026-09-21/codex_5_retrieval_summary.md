# Codex #5（gpt-6-astra）檢索注入管線內審 — 摘要（全文 reply_5.md，158K tokens）

結論：先修「實際送出內容與記帳不一致」、讓回歸評估走真正管線、再降 activation 對排序的支配；無證據支持新增模型式 reranker。

## 已重現的問題（本地探針，不落盤）
1. **1,200 tok 不是真硬頂**：175 正例跑真正 collect_matched_atoms()+assemble_injection()，**133 次超過 1,200**，最高 2,225（同一估算器口徑）。cold/skip 路標不計 used_tokens，全文標頭未完整計費（ups_inject.py:213）。
2. **尾端 Guardian 訊息會隨 atom 被裁掉**：_truncate_context_by_activation()（wg_atoms.py:1251）以「下一個 Atom 標頭」界定區塊，把尾端非 atom 訊息包進最後一顆 atom。合成案例證實。
3. **記帳在裁切之前**（ups_inject.py:381 → user_prompt_submit.py:397）：被裁掉的 atom 仍留在 injected_atoms / 去重 / 效用歸因 / recall-miss 排除；重播中 2 回合 4 顆。
4. **預算重複扣額**：build_context() 把 JIT/episodic 加進 lines 又扣保留預算，最後拿扣後預算檢查整包（ups_context.py:95/175）。
5. **activation 乘數支配排序**：F = Σ1/(60+rank) × exp(0.25×A)；k=60 使第 1 與第 3 名 RRF 比僅 1.033，activation 差 0.129 就翻轉；快照 rank −7.61～0.003 → 乘數 0.149～1.001（6.7 倍）。**離線重播真正搜尋函式（全域索引、新 session、關 vector）：現行 R@1 41.7% / R@3 83.4% / MRR 0.619 → gain=0：80.0% / 93.1% / 0.860**；82/189 首名改變。但最終輸出「出現」只 162→164/175，且可能只是路標 → 不可宣稱回答品質同幅提升。
6. **detect_atom_use() 假陽性**：條件是「共享 token ≥2 **或** containment ≥0.18」（wg_atoms.py:1079/1141），Stop 未傳 df_map/n_docs。三組無使用負控制：15/24/20 顆判 used → 接 DF 且 max_df_ratio=0.1 → 4/2/3（59/579 → 9/579）；預設 0.5 完全無效。Stop 讀整張 atom 比對，即使當輪只送路標（stop.py:445）；「宣告完成且無失敗訊號」即成功（stop.py:347）。
7. **BM25 gating**（trigger ≥3 命中即不跑）：BM25 對 193 顆中位 8.45ms、p95 12ms；每輪都跑 → gain=0 下 R@1 80.0→82.3%、MRR 0.860→0.875。負例「幫我想三個晚餐菜色」命中 workflow-research-fanout（BM25 11.22，共享詞「幫我」「我想」）——請求措辭當內容證據，非 CJK 子字串問題。
8. **零曝光語意**：報表「零曝光」= 近 30 天 timestamps 空；Related 專有候選未進 _emit_usefulness_hints() 的 matched_with_dir 迴圈 → 送出卻不加曝光（有 state 實例）。35 顆 = 19 無歷史曝光 + 15 曾曝光。
9. **遙測母體**：636 sidecar = memory/ 546 + _AIDocs/_atoms/ 90，其中 **409 在 _distant/**；有效索引 193 顆中 read_hits=0 者 19、有曝光 174、其中無 α 正向證據 28、α β 皆無結果證據 15。α/β 先驗各 1 且衰減。
10. 回歸評估：223 條 → 175 正例 / 14 負例 / 34 跳過；R@1 64.6%；baseline.json 67.0%（正例 209）；compare_baseline() 結果被忽略（退步不回非零碼）。

## 前五（Codex 排序）
1. **輸出／預算／記帳一致性**（1–2 人日，併 #8）：每個 lines 元素保留類型與邊界、按完整輸出計費、裁切後才提交 turn_injected / 去重 / 曝光 / rescue watch；Related 注入走同一筆記帳。驗證：加「Atom 後接 Guardian」「只有路標」「JIT 已占額度」「Related-only」案例。現有 10 項純預算測試全過但沒覆蓋這些。
2. **回歸評估對齊**（0.5–1）：固定時間+固定 sidecar 快照呼叫實際搜尋函式；三層輸出（舊評估／實際搜尋／最終注入）；34 條先辨識移名/移 realm/除役；退步回非零碼。
3. **activation 降為次要訊號**（0.5–1）：gain 可配置，gain=0 候選；最終裁切沿用搜尋優先序不再按裸 activation 重排；rank 限幅 ±0.4 探針 73.7%。回滾只恢復 gain。
4. **效用歸因接 DF 過濾**（1–2）：max_df_ratio=0.1 待驗；只比對最終送出節錄或有 Read 證據的全文；提到卡名/否定引用不算成功 α。
5. **BM25 每輪跑、門檻不放寬**（0.5–1）：保留 7.0/3；加「幫我／我想」類負例。

## 不建議
宣稱 CJK 子字串大量假陽性（14 負例唯一命中來自 BM25）；trigger 命中密度排序（R@1 80→69.1%）、trigger IDF 加權（79.4%）；每輪 Ollama embedding 二次排序（現有 tiebreak 序列產兩份向量、timeout 3s）；按「零曝光 35」刪卡或擴 trigger；重建 friction/rescue。

## 未查到
35 顆逐顆流失原因（injection-turns.jsonl 只有回合彙總；atom_debug=false）；真實效用歸因假陽性率；端到端回答品質與 UPS p95（受控子流程 p95 30.5ms）；recall-miss 近 30 天 8 筆聚合 5 atom，亦受裁切前記帳影響。
