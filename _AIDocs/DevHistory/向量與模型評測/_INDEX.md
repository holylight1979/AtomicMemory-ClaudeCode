# 向量與模型評測 — 實測數據與模型選型紀錄

> 本機模型（Ollama）A/B 實測、向量門檻校準、rerank 要不要進注入鏈的評估。都是「當時怎麼量、量出什麼、為什麼這樣選」，不是現況；現況看 `TECH.md`。

| 檔 | 一句話 |
|---|---|
| `ab-test-ollama.md` | 2026-03 Ollama 雙 backend 萃取品質 A/B（qwen3.5 vs qwen3:1.7b）完整數據 |
| `ab-test-gemma4.md` | 2026-04 Gemma 4 vs Qwen 3.5 三輪 A/B，rdchat 模型切到 gemma4:e4b 的決策依據 |
| `ollama-backend.md` | Dual-Backend Ollama 退避機制（三階段 DIE + failover）的設計說明，實作在 `tools/ollama_client.py` |
| `vector-threshold-calibration-2026-04.md` | 向量 ranked-sections min_score 校準（90 query × 6 threshold 矩陣）與定案 |
| `rerank-cross-encoder-evaluation-2026-10.md` | cross-encoder rerank 要不要進注入鏈：本機 175 題回歸集對照、外部文獻、Codex 審；判定不進 hook、讀取端可選 |
