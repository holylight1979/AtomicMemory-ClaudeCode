# 檢索融合與回歸集調參-rrf-min-score-定案

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: RRF, 融合檢索, min_score 調參, memory-eval, 回歸集, 誤注入率, Recall@3, 檢索品質
- Created-at: 2026-07-25
- Related: atom-usefulness-loop, 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證, 佛法三缺口工程化-失念壞滅緣了義

## 知識

- [臨] 全域檢索排序現行架構：trigger/BM25/vector 三路 RRF 融合（k=60，config `vector_search.fusion: rrf`，`legacy` 可回退）× ACT-R activation 乘性調節（`exp(0.25×rank)`）；各路 min_score 仍是入場過濾，RRF 只管排序。實測：Recall@1 34→53.6%、MRR 0.584→0.709，誤注入不變。
- [臨] bm25_min_score=7.0 由回歸集掃參定案（3.5→7.0：負例誤注入 21.4%→0%、R@3 僅 -1.5pt，漏網由 vector fallback 補）。改檢索參數前先跑 `python tools/memory-eval/run.py`（223 條合成查詢、0.5s）對比 baseline.json，盲調參已終結；參數變更後重建 baseline。
- [臨] UPS 主路徑延遲熱點實證：_kw_match per-keyword regex 重編譯（詞彙量超 re 內建 512 cache → thrash，佔 ~85% CPU）；子字串預篩 + lru_cache 後 median 90→16ms。同類問題先疑 regex cache 溢出。

## 行動

- （依知識內容判斷）
