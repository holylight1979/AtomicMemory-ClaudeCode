# text-score的auto_targets空清單是不比路徑不是關掉-要某種類不評就整個不列

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測
- Confidence: [臨]
- Trigger: text-score, auto_targets, docs: [], 不評文件, wg_text_score, 文字評分自動目標
- Created-at: 2026-10-22

## 知識

- [臨] tools/text-score.py 的 auto_targets 是 {種類: 路徑樣式清單}；空清單＝不比路徑、全部算，所以想「不評文件」寫 `docs: []` 反而變成什麼文件都評。
- [臨] 正確做法是 auto_targets 裡不列 docs：工具回「docs 不在 auto_targets → 不評」，收尾端 hooks/wg_text_score 也判沒列就不送。

## 行動

- 要關掉某種類的自動評分：從 auto_targets 拿掉那個鍵，不要留空清單；改完跑一次工具看回的是「不在 auto_targets → 不評」


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（G15 收尾背景文字評分的 auto_targets 與 hooks/wg_text_score）已從寫碼守門拔除，手動 /text-score 不用它 | memory-audit --delete |
