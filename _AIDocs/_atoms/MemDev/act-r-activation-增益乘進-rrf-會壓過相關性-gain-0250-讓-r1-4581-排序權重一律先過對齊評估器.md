# ACT-R activation 增益乘進 RRF 會壓過相關性-gain 0.25→0 讓 R@1 45%→81%-排序權重一律先過對齊評估器

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: rrf_activation_gain, activation 增益, ACT-R 重排, 排序調參, R@1, MRR, memory-eval --online, 對齊評估器, 檢索排序, 誤注入率, bm25 停用詞, related query gate
- Created-at: 2026-09-21
- Related: 檢索融合與回歸集調參-rrf-min-score-定案, activation負值不是負相關-act-r對數尺度天然跨零-注入噪音修門檻與顯示勿過濾分數

## 知識

- [臨] 2026-09-21 全面檢視實測（175 正例／22 負例，同凍結時鐘）：RRF 分數乘 exp(gain×activation) 的 gain 由 0.25 改 0，R@1 45.1%→81.1%、MRR 0.639→0.870、全文送達 78.9%→88.0%，負例誤注入 4.5% 不變。原因：小語料下「最近被用過」的活性差距遠大於相關性差距，常用 atom 把真正對題的 atom 擠出前 3；這個權重當初是憑直覺設的，沒有任何量測。
- [臨] 同輪另兩個切點：BM25 分詞剔掉請求框架 bigram（幫我／我想／請你／一下…）讓負例誤注入 31.8%→4.5%；Related 擴散加 BM25≥5 的 query gate 讓正例額外送出顆數 4.33→2.52。三者都留 config 回滾鍵（vector_search.rrf_activation_gain、bm25_gate_max_trigger_hits、injection.related_gate.query_gate_min）。
- [臨] 判準：任何進排序公式的權重／門檻，先用 tools/memory-eval/run.py --online 同一 --frozen-time 跑 A/B，三層指標（候選 R@1/@3/MRR、送達 full/pointer/missing、負例）都不退步才上線；憑感覺加的權重預設有害直到被量過。

## 行動

- 改排序／預算／擴散任何參數：同一 --frozen-time 連跑現行與對照，看三層指標＋負例
- 看到「常用 atom 老是排前面但不對題」：先查 rrf_activation_gain 是否又被調回非 0
