# memory-eval — 檢索回歸評估

離線量測 atom 檢索品質，讓 RRF 融合、BM25 參數、embedding 替換等改動有秒級 A/B 依據，
不再憑感覺調參。

## 指令

```bash
python tools/memory-eval/genqueries.py                  # 生成/補齊查詢集（Ollama 在線用 LLM，離線用模板；--regen 全重生）
python tools/memory-eval/run.py --online --baseline tools/memory-eval/baseline_online.json   # 線上管線對齊評估（主用）
python tools/memory-eval/run.py --baseline tools/memory-eval/baseline.json                   # 診斷欄：只驗 trigger/BM25 層
```

## --online：走線上同一條管線（主用）

`online_replay.Replayer` 直接呼叫 hooks 的 `collect_matched_atoms → assemble_injection → _truncate_context_by_activation
→ reconcile_injection_after_trim`，所以 RRF×activation、Supersedes、Related 擴散、預算三態、最終裁切全部量得到；
凍結時鐘（`--frozen-time`）、vector 替身、其他專案不掃、曝光不寫，零副作用。三層指標：

- **候選**：Recall@1／@3／MRR（排序後名單）
- **送達**：期望 atom 最後是 full（全文／印象／節錄）、pointer（一行路標／cold／被裁成指標）還是 missing（dropped／整塊裁掉／沒進候選）
- **額外送出**：正例題除期望 atom 外還送了幾顆（誤送的代理指標，無相關性標註前只看趨勢）
- 負例：有沒有候選／有沒有實際送出內容

排序實驗用 `--set`（dotted key，值為 JSON）覆寫 config，同一批比較請給同一個 `--frozen-time`：

```bash
T=$(python -c "import time;print(int(time.time()))")
python tools/memory-eval/run.py --online --frozen-time $T                                             # 現行 config
python tools/memory-eval/run.py --online --frozen-time $T --set vector_search.rrf_activation_gain=0.25  # 對照
python tools/memory-eval/run.py --online --frozen-time $T --set injection.related_depth=0 --dump /tmp/rel0.json
```

`--baseline` 有基線就比對（±2pp 標退步、母體不同會提醒），退步回 exit 2；沒有就建立。
注意：`--frozen-time` 只凍結時鐘，**不凍結 sidecar／atom 輸入**——線上 hook 持續更新 access.json，隔一段時間重跑同一設定
會有 ±1pp 的漂移（實測舊設定 R@1 45.1% vs 44.6%）；要嚴格 A/B 請在同一分鐘內連跑各組。送達欄只量 atom 段，
Guardian／JIT／episodic 共用總額的擠壓不在其中。
`[skip] archived=N` 是被 selective forget 封存的 expect（屬預期）；relocated／renamed?／missing 才要修題目。

2026-09-21 調參結論（175 正例／22 負例，同凍結時鐘）：activation 增益 0.25→0 讓 R@1 45.1%→81.1%、MRR 0.639→0.870、
全文送達 78.9%→88.0%；BM25 每輪跑再 +1.2pp R@1；請求框架 bigram（幫我／我想／請你…）剔出 BM25 後負例誤注入 31.8%→4.5%。

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

## eval_usage_v2.py — 判用 v1 vs v2 對照（Phase 2 定案依據）

```bash
python -X utf8 tools/memory-eval/eval_usage_v2.py --detail
```
同一標註集上比 v1（詞彙重疊 rare≥2 or cont≥0.18）與 v2（`wg_atoms.detect_atom_use_v2`：否定線索→rejected、
rescue 特異 token→used、引用線索→cited、路標／cold 未 Read→不算、去路徑噪音後共享 ≥6）。
2026-09-21 結果（正類＝adopted＋corrected，即「有沒有用到」）：v1 P 0.35／R 1.00 → **v2 P 0.67／R 0.84**；
rejected 判 used 9/9→1/9、cited 9/9→3/9、unknown 18/20→4/20。線上 Stop 已切 v2（config `usefulness.attribution_policy`，
`v1` 可回滾）。

## eval_usage.py — 效用歸因「判用」標註集評估

`detect_atom_use`（Stop 判「這輪有沒有用到這顆 atom」，Wilson 晉升的輸入）的離線校準：

```bash
python -X utf8 tools/memory-eval/eval_usage.py                                  # 現行參數 + 候選網格，寫 usage_eval_report.md
python -X utf8 tools/memory-eval/eval_usage.py --rare-token-min 2,3 --overlap-min 0.18,0.3 --df-ratio none,0.5,0.1
python -X utf8 tools/memory-eval/eval_usage.py --atom-source file               # 比對整檔（鏡像現行 Stop），預設比對實際送出形式
python -X utf8 tools/memory-eval/eval_usage.py --positive-include-corrected     # corrected 也算正類
```

- 標註集 `usage_labels.jsonl`：五類 adopted／cited／rejected／corrected／unknown，每筆帶 `origin: real|synthetic`、實際送出形式、回合文字窗、理由；檔頭 `_meta` 寫判準與分布。**標籤由 AI 判定未人工複核**，`review_flag` 是標註者自認最該挑錯的案例。
- 正類 = adopted（可選含 corrected），其餘負類；輸出混淆矩陣、precision／recall、FP／FN 明細與共享 token。
- 唯讀：透過 `PYTEST_CURRENT_TEST` 把 hook log 導向暫存，不寫 sidecar／state／Logs；embedding tiebreak 固定關閉。
