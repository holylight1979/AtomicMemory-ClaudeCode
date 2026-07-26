# memory-eval — 檢索回歸評估

離線量測 atom 檢索品質，讓 RRF 融合、BM25 參數、embedding 替換等改動有秒級 A/B 依據，
不再憑感覺調參。

## 兩指令

```bash
python tools/memory-eval/genqueries.py                  # 生成/補齊查詢集（Ollama 在線用 LLM，離線用模板；--regen 全重生）
python tools/memory-eval/run.py --baseline tools/memory-eval/baseline.json   # 跑評估 + 基線比對
```

## 指標

- **Recall@1 / Recall@3**：direct 查詢的期望 atom 排第 1 / 進前 3 的比率
- **MRR**：mean(1/rank)，miss 計 0
- **負例誤注入率**：不該命中任何 atom 的泛用 prompt 卻有命中的比率（越低越好）
- **per-atom miss**：期望 atom 未進前 3 的查詢清單，按 atom 彙整

檢索走與線上相同的原語與合併順序（`hooks/wg_atoms.py`：trigger → BM25，
`--with-vector` 加測 vector fallback；不含 ACT-R 使用統計重排以保持確定性）。
基線比對差異超過 ±2 百分點標紅。

## 與 memory-effect-report 的分工

- memory-effect-report：**線上效用**——已注入的 atom 實際有沒有被用上
- 本工具：**離線檢索品質**——該被找到的 atom 有沒有被找到、不該注入的有沒有誤注入
