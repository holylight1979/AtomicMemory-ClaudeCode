# cross-encoder rerank 與 sentence-transformers 要不要進原子記憶系統——實測評估（2026-10-07）

> 讀者：holylight（決策者）。結論先行，數字全部可重現（§6）。
> 三路來源：本機回歸集對照實驗（Claude）、外部文獻與模型調查（Claude 代理，附 URL）、Codex gpt-6-astra 獨立開 repo 審查；三方不一致處在 §5 寫明裁決。

## 0. 結論

**不建議把 cross-encoder 放進每句話的注入鏈；建議做的是「按需」用法。** 理由三句：

1. 排序不是現在的痛。回歸集 175 題：期望卡片已在前三名 92.6%、送達全文 92%。rerank 只動「前三名內的順序」，而且 13 題期望卡根本不在候選池、13 題池內只有一顆，這 26 題（15%）rerank 碰不到。
2. 實測收益小、代價可感。最好的可商用模型（bge-reranker-base，ONNX）把 R@1 從 81.7% 拉到 85.1%（+3.4 點，約 6 題），但 R@3 反而 92.6% → 92.0%，每句話在這台 CPU 多 1.2 秒（p95 2.4 秒）。使用者看得到的是「每句話慢一秒」，看不到的是「第 2 名變第 1 名」——因為兩者都已送達。
3. 更便宜的手段還沒用完：期望卡不在池內的 13 題是 trigger／BM25 召回問題，不是排序問題；每回合 38% 候選被 1200 token 硬頂砍掉，是預算與去冗問題。

**按需用法**（值得做、低風險）：`memory_search`／`atom_source` 這類「使用者主動查」的讀取端與離線回歸評估加一個可選 reranker（fastembed ONNX，bge-reranker-base），不進 hook。

## 1. 本機現況（實證）

| 項目 | 值 | 來源 |
|------|-----|------|
| 線上檢索鏈 | trigger → BM25（每輪）→ vector（專案層補位／零命中 fallback）→ RRF k=60，activation 增益 0 | `hooks/handlers/ups_search.py collect_matched_atoms`、`hooks/wg_atoms.py rrf_fuse` |
| 每回合預算 | atom 段硬頂 1200 tok；近 7 天 190 回合平均用 891、61% 回合 ≥1100；候選 38% 被砍（dropped） | `Logs/injection-turns.jsonl` |
| 回歸集（含向量路，凍結時鐘 1789981315） | R@1 81.7%、R@3 92.6%、MRR 0.870；期望卡全文送達 92.0%、missing 6.9%；負例誤注入 1/22 | `tools/memory-eval/run.py --online --with-vector` |
| 候選池大小 | 175 題：1 顆 13 題、2 顆 20、3 顆 57、4 顆 48、5 顆 21、≥6 顆 16；期望卡不在池內 13 題 | step1 腳本（§6） |
| 既有 rerank | `tools/memory-vector-service/reranker.py`：Ollama 逐條 0–10 打分，檔頭明寫離線路徑；全 repo 只有 `tools/rag-engine.py --rerank` 呼叫，hook 不用 | grep |
| sentence-transformers | **hook 直譯器（`%LOCALAPPDATA%\Python\bin\python.exe` → pythoncore-3.14）已裝 5.2.3 ＋ torch 2.10 CPU**；預設 `python`（3.11）與 hermes venv 沒裝。TECH §2.2 原寫「本機無 sentence-transformers」為誤，本次已改 | 實測 import |
| Ollama | 本機與遠端都沒有 reranker 模型；Ollama 無原生 rerank 端點 | `/api/tags`、外查 |
| 既有量測 | 近 30 天「高曝光零使用」1 顆、失念 4 筆 | `tools/memory-effect-report.py`、`Logs/recall-miss.jsonl` |

## 2. 對照實驗（本機 CPU，175 題，候選 ≤10）

重排對象＝線上 RRF 的候選清單（名次已含向量路）；文本＝卡片標題＋知識段前 700 字；分數相同保留 RRF 原序。

| 排序 | R@1 | R@3 | MRR | p50 | p95 | 升／降題數 | 備註 |
|------|-----|-----|-----|-----|-----|-----------|------|
| RRF 原序 | 81.7% | 92.6% | 0.870 | — | — | — | 現況 |
| bge-reranker-base（278M，ONNX／fastembed） | 85.1% | 92.0% | 0.883 | 1.18 s | 2.36 s | 升 16／降 11 | 可商用（MIT） |
| jina-reranker-v2-base-multilingual（278M，ONNX） | 88.6% | 92.0% | 0.903 | 1.35 s | 2.55 s | 升 18／降 6 | **CC-BY-NC，公司不能用** |
| ms-marco-MiniLM-L-6（22M，ONNX） | 54.9% | 87.4% | 0.703 | 0.25 s | 0.52 s | — | 英文模型，中文卡片變差 |
| bge-reranker-base（torch，sentence-transformers） | 77.7% | — | — | 1.45 s | 2.69 s | — | 載入 56 s；比 ONNX 慢且分數不同（未深究） |
| 理想上界（期望卡置首） | 92.6% | 92.6% | — | — | — | — | 13 題不在池內 |

讀法：
- 可商用的 bge-base 淨改善約 6 題（升 16 降 11），R@3 還倒退 1 題；跨語多語的 jina 明顯更好但授權不可用。
- 延遲 1.2–1.4 秒落在 8 秒 hook 預算內，但目前整條 UPS 鏈含向量路 timeout 3.5 秒，再加 1.2 秒會讓「每句話」都慢一拍。
- torch 路徑冷啟動 56 秒，不能放在每次都新起進程的 hook 裡；只能常駐在 vector service。

## 3. 外部證據摘錄（代理調查，含 URL）

- 收益形狀：cross-encoder 主要抬 hit@1／MRR，對 hit@10 幾乎無效；只重排 top-10 時 Recall@10 定義上不變（ConvMemory v2，arXiv 2606.10842）；小而整理良好的語料、延遲預算 <200 ms 時不划算（atlan.com）。
- 本地可跑的成本：bge-reranker-v2-m3（0.6B）CPU 約 3.6 s／15 候選（Wyrm BENCHMARKS 2026-06）；278M 級 30 pairs 約 130–190 ms（Qdrant 2026-09，Apple M4）——本機 i5 級 CPU 實測是它的 6–8 倍。
- 用 LLM 當 reranker 是最差組合：慢 8–17 倍、分數不穩（ZeroEntropy 2025-09；Rank-DistiLLM）。本系統既有 `reranker.py` 正是這種做法。
- 業界 agent memory（Mem0、Zep、Letta、LangMem、claude-mem）全部把 rerank 做成可選插件、無人預設開；Hindsight（2026-08）警告「分數全同時退化成純時近排序」。
- 更便宜的替代：query 改寫在 SemEval-2026 T8 的 nDCG@5 增益（+0.043）大於 bge-v2-m3 rerank（+0.023）；hybrid 融合本身 recall@10 +4 點。

來源 URL 清單見本檔末 §7。

## 4. 使用者長期協作體驗：有 vs 沒有

| 面向 | 沒 rerank（現況） | 加 rerank 進 hook | 使用者感覺得到嗎 |
|------|------|------|------|
| 錯卡片出現 | 近 30 天高曝光零使用 1 顆；負例誤注入 1/22 | 排序改變不會「拒收」錯卡（純排序不設門檻），要另做拒收閾值 | 幾乎不會 |
| 該想起沒想起 | 13/175 題期望卡不在池內；失念 4 筆 | 不變，rerank 不撈池外的卡 | 不會改善 |
| 前三名順序 | 19 題期望卡在第 2–3 名 | 約 6 題升到第 1 | 看不到：第 2 名也已全文送達 |
| 每句話延遲 | vector 路最多 3.5 s | 每句 +1.2 s（p95 +2.4 s） | **會**，每一句 |
| 安裝與維護 | hook 直譯器已有 ST＋torch（CPU）；fastembed 另裝 | 多一個 ONNX 模型檔（約 1.1 GB）與版本；多機都要裝 | 會，裝機與升級時 |
| 冷啟動 | — | ONNX 2.6 s／torch 56 s，必須常駐在 vector service | 第一句 |

一句話：加進 hook 的代價每天每句都在付，收益落在使用者本來就看不到的「第 2 名變第 1 名」。

## 5. 三方裁決

| 爭點 | Claude 代理 | Codex | 裁決（親自重現） |
|------|------|------|------|
| 本機有無 sentence-transformers | 無（測的是 3.11 與 hermes venv） | 有（`requirements.txt`） | **Codex 對**：hook 直譯器 3.14 有 ST 5.2.3＋torch 2.10 CPU；TECH 已改 |
| 痛在召回還是精度 | 送達是瓶頸（38% dropped） | 缺口偏召回；精度未知（標籤單一 expect） | 兩者都對：13 題池外＝召回；dropped 38%＝預算；精度無證據說有問題 |
| 每回合 ≤6 條是硬限制 | 無明確條數上限 | 不是（log 有送 7–8 顆） | 對，TECH 不寫「≤6」為硬限 |
| LLM 當 reranker | 最差組合（外查） | 舊審查把通用 LLM 當專用 reranker、200–500 ms 無實測 | 一致：`reranker.py` 不作為線上方案 |
| 值不值得上 | 先做零成本項 | 門檻：錯卡減 ≥20%、召回不降、p95 新增 ≤300 ms | 採 Codex 門檻；本次 bge-base 的 p95 +2.36 s 未達，R@3 還降 |

## 6. 重現

```powershell
# 含向量路的線上回放（凍結時鐘同 baseline_online.json）
python tools/memory-eval/run.py --online --with-vector --frozen-time 1789981315 --dump %TEMP%\eval_dump_vec.json
# 對照實驗：候選落檔 → 隔離 venv（fastembed，不裝 torch）重排
python %TEMP%\rerank_step1.py            # 用 tools/memory-eval/online_replay.Replayer 取候選＋文本
python -m venv %TEMP%\rerank-venv && %TEMP%\rerank-venv\Scripts\pip install fastembed
%TEMP%\rerank-venv\Scripts\python %TEMP%\rerank_step2.py BAAI/bge-reranker-base jinaai/jina-reranker-v2-base-multilingual Xenova/ms-marco-MiniLM-L-6-v2
```
step1／step2／step3 三支腳本本次只放 scratchpad（一次性實驗，不進 repo）；要重做時照上面兩段 20 行內可重寫：step1 取 `Replayer.run(q)["candidates"][:10]` 與卡片知識段前 700 字，step2 用 `fastembed.rerank.cross_encoder.TextCrossEncoder.rerank(q, docs)` 排序後算 R@1／R@3／MRR。

## 7. 外部來源

- tianpan.co 2026-04-19 cross-encoder vs cosine：https://tianpan.co/blog/2026/04/19/cross-encoder-reranking-cosine-similarity
- Wyrm BENCHMARKS 2026-06-27（bge-v2-m3 CPU 3.6 s／15 候選）：https://cdn.jsdelivr.net/npm/wyrm-mcp@8.5.8/BENCHMARKS.md
- ConvMemory v2，arXiv 2606.10842（只重排 top-10）：https://arxiv.org/abs/2606.10842
- Elastic semantic reranker part 3（深度曲線飽和）：https://www.elastic.co/search-labs/blog/elastic-semantic-reranker-part-3
- Qdrant oxidizing cross-encoders 2026-09-25（CPU 延遲）：https://qdrant.tech/blog/oxidizing-cross-encoders/
- Qwen3-Embedding／Reranker 2025-06-05：https://qwenlm.github.io/blog/qwen3-embedding/
- ZeroEntropy 2025-09-05 LLM vs cross-encoder rerank：https://www.zeroentropy.dev/articles/should-you-use-llms-for-reranking-a-deep-dive-into-pointwise-listwise-and-cross-encoders/
- Mem0 rerankers overview：https://docs.mem0.ai/components/rerankers/overview
- Zep 搜尋策略 2025-02-21：https://www.getzep.com/blog/how-do-you-search-a-knowledge-graph/
- Hindsight 2026-08-28 passthrough trap：https://hindsight.vectorize.io/blog/2026/08/28/cross-encoder-reranking-agent-memory
- fastembed rerankers（ONNX，無 torch）：https://qdrant.tech/documentation/fastembed/fastembed-rerankers/
- SemEval-2026 T8（query 改寫 > rerank）：https://arxiv.org/pdf/2606.28352
- atlan reranking in RAG（何時不划算）：https://atlan.com/know/ai-agent/reranking-in-rag/
