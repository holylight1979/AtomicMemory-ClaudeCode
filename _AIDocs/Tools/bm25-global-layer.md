# BM25 Global Layer — 全域 Atom 檢索（V5 P5a）

> V5 Wave 3 P5a 引入：全域 atom 檢索（~17 atoms 規模）從 Vector Service @ 3849 改為 in-memory BM25。
> 專案層仍走 Vector（可能上百 atoms 規模），不在本檔範圍。

---

## 為什麼是 BM25

V4 全域檢索走 Vector Service 流程：

```
prompt → wg_atoms._semantic_search → urllib.request → 127.0.0.1:3849/search/ranked
       → LanceDB lookup → Ollama re-rank → top-k atoms
```

每查一次 200–500ms。全域只有 17 atoms，傷不起這延遲，也養不起 LanceDB + Ollama 兩個 daemon 的維運成本。BM25 in-memory（純 Python 字典 + counter）<10ms，零 daemon。

V5 拆三層：

| 層 | 規模 | 機制 | 延遲 |
|---|------|------|------|
| Trigger | 17 atoms | exact match in `_atom_index.json` triggers | <1ms |
| **BM25**（全域） | 17 atoms | in-memory bag-of-words, k1=1.2, b=0.75 | <10ms |
| Vector（專案層 / episodic / cross-session） | 數十–上百 atoms / chunks | LanceDB + Ollama | 200–500ms |

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
2. if trigger hits <= 2:
      bm25_results = bm25_match(prompt, atom_entries)
      filter score >= bm25_min_score (default 1.0)
      take top bm25_top_k (default 3)
3. if (trigger + bm25) hits == 0 AND vector_search.global_layer != "bm25":
      vector_results = _semantic_search(prompt, ...)
4. merge → ACT-R rank → budget cap → inject
```

### Config

```json
"vector_search": {
  "global_layer": "bm25",
  "bm25_min_score": 1.0,
  "bm25_top_k": 3,
  ...
}
```

切回 vector：`global_layer: "vector"`（保留 escape hatch，未實測退化）。

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
| 全域 atom trigger match | ✓ | （fallback） |
| 專案層 atom（>30 個）| | ✓ |
| Episodic past sessions | | ✓ |
| Cross-session dedup / 衝突偵測 | | ✓ |
| Atom section-level 半結構檢索 | | ✓ |

V5 Wave 4 P5b 拆掉 Codex Companion daemon @ 3850，但 Vector daemon @ 3849 仍保留 — 不要混淆兩個 daemon 退役決策。

---

## 維運注意

- BM25 dict 全在 hook process 記憶體，每次 UPS 重建（17 atoms × 幾百 tokens 規模 <5ms）。如全域 atom 規模成長到 100+，可考慮 cache 到 `workflow/bm25_index.json`。
- Stale chunk 清理已加：`tools/memory-vector-service/indexer.py --cleanup-stale`（atom 被 supersede/archive → 自動 evict 對應 chunk）。
- 觀察 log：`Logs/vector-observation.log` 仍記錄 BM25 vs Vector fallback 統計，由 `tools/vector-observation-summary.py` 聚合。

---

## 相關文件

- [`SPEC_ATOM_V5.md §6`](../SPEC_ATOM_V5.md) — V5 BM25 全域檢索層規格
- [`DevHistory/vector-observation.md`](../DevHistory/vector-observation.md) — Vector Service 觀察期決策史
- `hooks/wg_atoms.py` `bm25_match` / `_bm25_score` / `_bm25_tokenize` — 實作
- `hooks/handlers/user_prompt_submit.py` — 三層注入流程
