# BM25 Global Layer — 全域 Atom 檢索

> 出廠 `vector_search.global_layer: "vector"`：每句先問向量，向量這次沒結果（服務沒起來、逾時、沒命中）才跑 BM25。
> `global_layer: "bm25"` 時才是 BM25 先跑、向量只補專案層。

---

## 為什麼留著 BM25

BM25 in-memory（純 Python 字典 + counter）<10ms、零 daemon；向量服務掛了，全域層靠它撐住，不會只剩 trigger。

| 層 | 機制 | 延遲 |
|---|------|------|
| Trigger | exact match in `_atom_index.json` triggers | <1ms |
| **BM25**（全域） | in-memory bag-of-words, k1=1.2, b=0.75 | <10ms |
| Vector（全域層與專案層） | LanceDB + Ollama | 單次中位數約 0.6 秒 |

---

## 實作

### 程式碼

`hooks/wg_atoms.py`（V5 P5a 手刻 ~80 行）：

```python
def _bm25_tokenize(text: str) -> list[str]:
    """ASCII word boundaries + 中文 char-bigram tokenization."""
    ...

def _bm25_score(query_tokens, doc_tokens, idf, avgdl, k1=1.2, b=0.75) -> float:
    ...

def bm25_match(prompt: str, atom_entries) -> list[tuple[name, score]]:
    """Score all atom_entries against prompt, return sorted top_k."""
    ...
```

### 注入流程

`hooks/handlers/user_prompt_submit.py`：

```
1. trigger match in _atom_index.json
2. global_layer=vector（出廠）：
      vector_results = _semantic_search(prompt, ...)
      這次沒結果 → bm25_results = bm25_match(prompt, global_atoms)，分數 >= bm25_min_score，取前 bm25_top_k
   global_layer=bm25：
      bm25_results 先跑；trigger + bm25 全空，或有專案層卡且 trigger 命中 < 3，才問向量
3. merge → RRF → budget cap → inject
```

### Config

```json
"vector_search": {
  "global_layer": "vector",
  "bm25_min_score": 7.0,
  "bm25_top_k": 3,
  ...
}
```

全域層只走 BM25：`global_layer: "bm25"`。

---

## Tokenization 細節

中英混合 prompt 用 char-bigram + ASCII word boundary 兩種策略並行：

| 範例 prompt | tokens |
|------------|--------|
| `ollama 嵌入失敗` | `ollama`, `嵌入`, `入失`, `失敗`, `嵌入失敗`(bigrams) |
| `codex silent failure` | `codex`, `silent`, `failure` |
| `V5 進度` | `V5`, `進度` |

優點：
- 中文不依賴外部 segmenter（jieba 等）
- 英文 keyword 完整保留
- Bigram 容忍語序變化（「載入失敗」 vs 「失敗載入」皆能匹配「失敗」atom）

缺點：
- 同義詞無法捕捉（「報錯」≠「失敗」）— 這層由 trigger / Vector 兜
- 短查詢（≤2 字）BM25 score 不穩 — 用 `bm25_min_score=1.0` 過濾

---

## 實測樣本（Wave 3 驗證，2026-05-27）

| Prompt | top-1 atom | 命中正確 |
|--------|-----------|---------|
| ollama 嵌入失敗 | toolchain-ollama | ✓ |
| codex silent failure | feedback-tooling-reliability | ✓ |
| V5 進度 | v5-overhaul-audit-2026-05 | ✓ |
| 衝突偵測 | conflict-* atom | ✓ |
| atom 晉升規則 | preferences | ✓ |
| 角色機制 | （無命中）→ fallback trigger | ✓ |

6 / 6 命中（含 1 個 fallback 路徑驗證）。

---

## 與 Vector 退役決策

Vector Service @ 3849 **不退役**，仍是專案層/episodic/cross-session 的主要檢索機制：

| 場景 | 用 BM25 | 用 Vector |
|------|---------|-----------|
| 全域 atom | 向量這次沒結果才跑 | ✓ |
| 專案層 atom（>30 個）| | ✓ |
| Episodic past sessions | | ✓ |
| Cross-session dedup / 衝突偵測 | | ✓ |
| Atom section-level 半結構檢索 | | ✓ |

V5 Wave 4 P5b 拆掉 Codex Companion daemon @ 3850，但 Vector daemon @ 3849 仍保留 — 不要混淆兩個 daemon 退役決策。

---

## 維運注意

- BM25 dict 全在 hook process 記憶體，每次 UPS 重建（17 atoms × 幾百 tokens 規模 <5ms）。如全域 atom 規模成長到 100+，可考慮 cache 到 `workflow/bm25_index.json`。
- Stale chunk 清理已加：`tools/memory-vector-service/indexer.py --cleanup-stale`（atom 被 supersede/archive → 自動 evict 對應 chunk）。
- 觀察 log：`Logs/vector-observation.log` 仍記錄 BM25 vs Vector fallback 統計（JSONL，schema 見 `Failures/vectordb-silent-failure-2026-04.md` §Wave 3a）。聚合工具 `vector-observation-summary.py` 已於 `d76bba1`（Wave 5 汰舊）移除 → 改 ad-hoc 讀 log 聚合；最新複測（2026-07-01 P1 後，命中率 87–89% → daemon KEEP）見同文件 §2026-07-01。

---

## 相關文件

- [`SPEC_ATOM_V5.md §6`](../SPEC_ATOM_V5.md) — V5 BM25 全域檢索層規格
- [`DevHistory/vector-observation.md`](../DevHistory/vector-observation.md) — Vector Service 觀察期決策史
- `hooks/wg_atoms.py` `bm25_match` / `_bm25_score` / `_bm25_tokenize` — 實作
- `hooks/handlers/user_prompt_submit.py` — 三層注入流程
