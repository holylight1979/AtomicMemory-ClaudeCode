# 換資料根的session向量檢索查的是全機共用live向量庫再用資料根可見池過濾-bm25為主時向量只在全沒命中才打-新卡要等向量重建

- Scope: global
- Author: holylight
- Source: session 26d36367（2026-10-21，向量涵蓋實測）
- Confidence: [臨]
- Trigger: 向量檢索, vector search, WG_CLAUDE_DIR, 資料根, global_layer, bm25, 語意找卡, 卡沒注入, _merge_hit, vector_ready.flag, 向量庫沒有新卡
- Created-at: 2026-10-21

## 知識

- [臨] 向量服務全機一支（port 3849），庫照 live 的 memory 建；WG_CLAUDE_DIR 指別的資料根時，hook 照樣查這個共用庫，查回的卡名經 `ups_search._merge_hit` 用資料根的可見池比對，池裡有才注入、讀的是資料根那份檔。所以排除在資料根外的卡就算被向量查回也進不來。
- [臨] `vector_search.global_layer="bm25"` 時全域卡平常靠觸發詞與 BM25；兩者一張都沒命中才走向量（全層退路），專案層卡才會在命中少於 3 時被向量補強。門檻 search_min_score 0.65，一般需求句直查常常 0 筆。
- [臨] 新寫的卡不會自己進向量庫：用卡的完整標題直查也查不到，舊卡查得到。要涵蓋得讓 live 向量服務重建或增量索引，不是改設定鍵。新資料根第一次問時 workflow/vector_ready.flag 還不在，最多等 0.3 秒，等不到這輪就不走向量。
- [臨] 驗法：不開 claude，把 hooks/workflow-guardian.py 用假 SessionStart／UserPromptSubmit 事件（stdin JSON，WG_CLAUDE_DIR 指資料根）跑，看輸出的 [Atom:] 與 Logs/vector-observation.log。

## 行動

- 卡存在卻沒被注入：先看觸發詞有沒有被那句話命中，再看向量庫有沒有這張卡
- 要驗注入結果不必真跑 claude：直接餵 hook 假事件
