# 根層與專案session對齊認知用root-link雙槽與tri-link三槽信箱-落專案inbox

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: root-link, tri-link, 三方討論, 根層專案層溝通, 跨session對齊, 跟根層談, 信箱摩槽, 兩個session討論同題
- Created-at: 2026-10-07
- Related: 並行llm即時通訊-inbox機制
- Source: session:16da96f2#f1e3cffa 2026-10-07
- Quote: 「開一個跨session溝通的 inbox monitor.. 我想讓你與根層 直接溝通 看看，那個session也在討論類似的議題，只是 你的似乎更接地氣 (?)。 好了以後給我 prompt 讓我去在根層的CC貼上；僅限 先溝通。」

## 知識

- [臨]（實跑）根層 ~/.claude session 與專案 session 討論同一題目時，用專案 `.claude/inbox/` 下的信箱對齊：雙槽 `root-link/`（`to-root/` 專案寫、`to-project/` 根層寫），三槽 `tri-link/`（每槽一個出向 `from-<slug>/`，`re: <槽>/<seq>`）。落專案目錄的理由：根層寫專案目錄不受保護閘影響，反向會被 CrossRealmBashBlock 擋。
- [臨] 有效模式：首封「我是誰＋綱要正本路徑＋一句摘要＋四題」，對方一封一題回、每封附已驗證路徑或實測數字；分工定案用一句收束同步寫進雙方綱要；三方約 20 封就收斂到「各自向使用者要拍板」。Monitor 要排除自己的出向目錄，換監控先 TaskStop 舊的免雙報。

## 行動

- 發現別的 session 在討論同題 →開 root-link/tri-link，給使用者一段貼到對方 session 的 prompt，指明槽名、寫哪讀哪、首封要回哪幾題
