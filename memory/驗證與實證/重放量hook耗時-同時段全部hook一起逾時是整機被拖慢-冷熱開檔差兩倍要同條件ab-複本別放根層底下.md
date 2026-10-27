# 重放量hook耗時-同時段全部hook一起逾時是整機被拖慢-冷熱開檔差兩倍要同條件AB-複本別放根層底下

- Scope: global
- Author: holylight
- Source: 2026-10-21 hook 耗時重放
- Confidence: [臨]
- Trigger: hook 逾時, hook 耗時, hook_cancelled, timedOut, SessionStart 太慢, 重放, cProfile, A/B 量測, 複本路徑
- Created-at: 2026-10-21

## 知識

- [臨] 判 hook 逾時是程式慢還是整機被拖慢：先看 transcript 的 hook_cancelled 附件（durationMs／timeoutMs）——同一時段連 ensure-mcp、codex_companion、plan_bash_guard 這種瑣碎 hook 都超過上限 2～3 倍，就是整機資源被搶，不是單一段程式；同材料孤立重放只要 1.5～4 秒（實例：B-2 開場 22.8 秒，孤立暖 1.5 秒）。
- [臨] Windows 冷熱開檔差很多：剛複製或同步過的檔第一次開，每個 open 約 5 毫秒（防毒掃描），第二次開快取命中；逐張讀幾百張卡的段落冷時 1.6 秒、暖時幾十毫秒。新舊版 A/B 要同樣先暖一次、交替跑，否則把快取差當成改善。
- [臨] 重放 hook 時複本不能放在資料根（~/.claude）底下，會被當成核心環境、行為不同；追蹤帳本等以 cwd 推 slug 的資料，複本換了路徑就要照新 cwd 的 slug 改名，否則重放看不到該送的提示。
- [臨] 分段打點（Logs/guard-hook_timing.jsonl 的 segments）比 cProfile 更適合找忙機時被放大的段；cProfile 在有背景計時執行緒時累計時間會錯掛到別的函式。

## 行動

- hook 逾時先翻 transcript 看同時段其他 hook 是否一起逾時，再決定查程式或查機器
- A/B 量測先各暖一次、交替跑多輪取中位數
- 重放複本放 %TEMP% 這類非資料根路徑，並照新 cwd 改 slug 類資料檔名
