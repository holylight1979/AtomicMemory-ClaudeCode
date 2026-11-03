# 從transcript算本機token用量-assistant列以message-id加requestid去重-加權近計費input加5m快取1點25倍1h快取2倍讀0點1倍輸出5倍-專案名取projects下第一層-rglob含子代理

- Scope: global
- Author: holylight
- Source: GitLab ClaudeCode-AtomMemory !14 tools/usage-watch.py scan／weighted／merge_ledger（作者 prog_katana_batch，合併 d09f9640）
- Confidence: [臨]
- Trigger: token 用量, transcript usage, 加權 token, cache_creation, ephemeral_1h_input_tokens, cache_read_input_tokens, requestId, message.id 去重, 哪個專案在燒, 本機用量, projects jsonl
- Created-at: 2026-11-03
- Related: 盤點並行session的context用量-讀projects下各transcript最後一筆assistant-usage三欄相加-名字對應靠worktree資料夾與listagents啟動時間
- Quote: 「收割，我希望是從他們推的MR中，汲取此電腦所用LLM所欠缺的知識、經驗」

## 知識

- [臨] 掃 `~/.claude/projects/**/*.jsonl`（rglob 會把 `subagents/` 一起掃進來）取 `type=assistant` 且 `message.usage` 有值的列；同一則回覆在串流中會寫多列，用 `(message.id, requestId)` 去重，不然 token 會重複算。專案名＝路徑在 projects/ 下的第一層（cwd slug）。
- [臨] 四個原始欄位 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens` 直接相加是「原始量」，不反映費用。貼近計費的加權：input×1 ＋ 5 分鐘快取寫入×1.25 ＋ 1 小時快取寫入×2 ＋ 快取讀取×0.1 ＋ output×5；1 小時快取量在 `usage.cache_creation.ephemeral_1h_input_tokens`，5 分鐘量＝`cache_creation_input_tokens` 減它。
- [臨] 先用檔案 mtime 跳過早於觀察窗的 jsonl，再逐行先用字串 `'"usage"' in line and '"assistant"' in line` 粗篩才 json.loads——transcript 動輒上百 MB，全解析會跑很久。
- [臨] transcript 只留兩三週，要長期看趨勢得把每小時×專案的合計另存帳本（同格取大，重掃不會蓋小），帳本壞掉時印警告不採用、不要靜默清空。

## 行動

- 算本機 token：assistant 列以 (message.id, requestId) 去重後再加總
- 要「花了多少」用加權公式；要「處理了多少」用四欄相加，兩個數字分開報
- 掃 transcript 先 mtime 再字串粗篩再解析
