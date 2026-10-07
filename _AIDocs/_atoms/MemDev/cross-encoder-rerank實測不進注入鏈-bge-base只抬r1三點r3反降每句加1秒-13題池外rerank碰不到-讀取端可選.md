# cross-encoder-rerank實測不進注入鏈-bge-base只抬R1三點R3反降每句加1秒-13題池外rerank碰不到-讀取端可選

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/rerank-cross-encoder-evaluation-2026-10.md
- Confidence: [臨]
- Trigger: rerank, reranker, cross-encoder, sentence-transformers, fastembed, bge-reranker, jina-reranker, 重排, 檢索精度, R@1, memory-eval 對照, 要不要加 rerank
- Created-at: 2026-10-07
- Quote: 「有鑑於 TECH.md 寫到 rerank 仍是可補強.. 我想深入知道 cross-encoder sentence-transformers 對於原子記憶系統、我們使用向量資料庫..等等而言，這兩項增加的必要性、優缺點與目前的比較，以及 使用者 長期使用CC協作開發時的體驗感 差異? 我希望同codex一起深入探索並且整理回報給我。」

## 知識

- [臨] 實測（175 題回歸集、含向量路、凍結時鐘 1789981315，CPU）：RRF 原序 R@1 81.7%／R@3 92.6%；bge-reranker-base（ONNX）R@1 85.1%／R@3 92.0%、p50 1.18 s；jina-v2-multilingual R@1 88.6% 但 CC-BY-NC 不可商用；MiniLM 英文模型中文變差（54.9%）。理想上界 92.6%：13 題期望卡不在候選池、另 13 題池內只一顆，rerank 碰不到。
- [臨] 裁定：不進 hook 注入鏈（收益落在使用者看不到的「第 2 名變第 1 名」，代價是每句 +1.2 s）；讀取端 memory_search／atom_source 與離線評估可加可選 reranker。門檻（Codex）：錯卡減 ≥20%、召回不降、p95 新增 ≤300 ms 才值得上。現在的痛是召回（13 題池外）與預算（38% 候選被 1200 tok 砸）。
- [臨] 環境事實：hook 直譯器（%LOCALAPPDATA%\Python\bin\python.exe → pythoncore-3.14）已裝 sentence-transformers 5.2.3＋torch 2.10 CPU；預設 python 3.11 與 hermes venv 沒裝——查「有沒有裝」要用 hook 的直譯器。torch 路徑 CrossEncoder 冷啟動 56 s，只能常駐；fastembed ONNX 載入 2.6 s、不裝 torch。Ollama 無 rerank 端點；用 LLM 逐條打分（reranker.py）慢 8–17 倍且不穩。全文 _AIDocs/DevHistory/rerank-cross-encoder-evaluation-2026-10.md。

## 行動

- 再有人提「加 rerank」：先讀評估檔，要翻案必須用同凍結時鐘重跑 memory-eval 並過 Codex 門檻
- 檢索改善優先順序：池外卡（trigger／BM25 召回）→ 預算與去冗 → 才是排序
