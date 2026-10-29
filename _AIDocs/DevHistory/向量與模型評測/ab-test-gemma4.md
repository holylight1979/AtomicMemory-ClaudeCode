# Gemma 4 vs Qwen 3.5 A/B 萃取品質實測（2026-04-08~09）

> V3.4 模型切換決策依據。三輪測試，跨 6 題型 × 5 模型。

## 背景

Google 於 2026-04-03 釋出 Gemma 4 系列，rdchat (RTX 3090) 同日安裝。
測試目的：評估 gemma4:e4b 能否取代 qwen3.5:latest 作為記憶系統 LLM 萃取模型。

## 測試模型

| 標籤 | 模型 | think | temp | 量化 | 大小 |
|------|------|-------|------|------|------|
| qwen3.5 T | qwen3.5:latest (9.7B) | true | 0.1 | Q4_K_M | 6.6GB |
| g4:e4b T | gemma4:e4b (8.0B) | true | 0.0 | Q4_K_M | 8.9GB |
| g4:e4b F | gemma4:e4b (8.0B) | false | 0.0 | Q4_K_M | 8.9GB |
| g4:bf16 | gemma4:e4b-it-bf16 (8.0B) | true | 0.0 | F16 | 14.9GB |
| g4:26b | gemma4:26b MoE (25.8B) | true | 0.0 | Q4_K_M | 16.7GB |

## Round 1 — 基礎比較（3 transcript × 5 模型）

| 維度 | qwen3.5 | g4:e4b T | g4:e4b F | g4:bf16 | g4:26b |
|------|:---:|:---:|:---:|:---:|:---:|
| 成功率 | 2/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 平均時間 | 52.5s | 27.9s | 19.5s | 59.7s | 58.0s |
| 原文依據 | 78% | 92% | 100% | 100% | 93% |
| 一致性 Jaccard | FAIL | 79.2% | 87.5% | 75.5% | 45.5% |
| 空輸入 PASS | FAIL | PASS | PASS | PASS | PASS |

## Round 2 — 擴充驗證（5 輪 + 溫度 + 拒絕 + format bug）

| 維度 | qwen3.5 | g4:e4b T | g4:e4b F | g4:bf16 | g4:26b |
|------|:---:|:---:|:---:|:---:|:---:|
| 成功率 (5輪) | 4/5 | 5/5 | 5/5 | 5/5 | 5/5 |
| 平均時間 | 41.1s | 13.1s | 2.8s | 53.1s | 52.2s |
| 原文依據 | 94% | 96% | 92% | 95% | 100% |
| 幻覺總數 | 1 | 1 | 2 | 1 | 0 |
| 通用知識拒絕 | PASS | PASS | PASS | PASS | PASS |

### 溫度敏感度（同輸入 × 2 次）
- g4:e4b temp=0.0: Jaccard **100%**
- g4:e4b temp=0.1: Jaccard 36.4%
- g4:e4b temp=0.3: Jaccard 48.6%
- qwen3.5 所有溫度: **ALL FAIL**（6/6 parse 失敗）

### Ollama format bug (ollama#15260)
- think=false + format 參數 → **NOT JSON**（確認 bug）
- think=true 或不傳 think → JSON OK
- 本系統用 prompt instruction 而非 format 參數，不受影響

## Round 3 — 多題型（3 題型 × 5 模型，temp=0.0）

題型：C=eHRM 加班自動化 | D=記憶系統架構 | F=高密度數據

| 維度 | qwen3.5 | g4:e4b T | g4:e4b F | g4:bf16 | g4:26b |
|------|:---:|:---:|:---:|:---:|:---:|
| 成功率 | 2/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| 原文依據 | 92% | 100% | 100% | 100% | 100% |
| 具體性 | 77% | 100% | 96% | 100% | 86% |
| Recall% | 38% | 47% | 33% | 53% | 59% |
| 幻覺 | 1 | 0 | 0 | 0 | 0 |

### 題型特色差異
- **高密度數據 (F)**：g4:e4b F 爆發 15 項（Recall 83%），逐行拆分最忠實
- **架構知識 (D)**：g4:26b Recall 50% 最高，架構理解力強
- **流程 (C)**：g4:e4b F Recall 僅 0%，不擅長流程邏輯

## 結論

| 決策 | 內容 |
|------|------|
| rdchat LLM | qwen3.5:latest → **gemma4:e4b** |
| deep extract | think=true, temp=0.0, num_predict=4096 |
| extract-worker | think 改 "auto"（backend config 控制） |
| local fallback | 維持 qwen3:1.7b（GTX 1050 Ti 4GB 跑不了 gemma4） |
| embedding | 維持 qwen3-embedding（gemma4 無 embedding 變體） |
| 已知風險 | ollama#15260: think=false + format 參數 = 破壞 JSON 輸出 |
