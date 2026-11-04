# 根層與專案session對齊認知用root-link雙槽與tri-link三槽信箱-落專案inbox

- Scope: global
- Author: holylight
- Source: session:16da96f2#f1e3cffa 2026-10-07
- Quote: 「開一個跨session溝通的 inbox monitor.. 我想讓你與根層 直接溝通 看看，那個session也在討論類似的議題，只是 你的似乎更接地氣 (?)。 好了以後給我 prompt 讓我去在根層的CC貼上；僅限 先溝通。」
- Confidence: [臨]
- Trigger: root-link, tri-link, 三方討論, 根層專案層溝通, 跨session對齊, 跟根層談, 兩個session討論同題, SendMessage 跨 session 討論
- Created-at: 2026-10-07
- Related: 並行llm即時通訊-inbox機制, feedback-多專案改進只動根基帶變量-參與專案只給思路不再動手-根層負責吸收轉化定角色開變量處理奇耙設定

## 知識

- [臨] 根層 ~/.claude session 與專案 session 討論同一題目，目前直接用原生 SendMessage 對談：`claude agents --json`／ ListAgents 找對方，閒置的對方收信會自動開回合，crossSessionInbound=accept 下計畫模式也收得到。專案 `.claude/inbox/` 的 root-link（雙槽）／ tri-link（三槽）檔案信箱在原生能跨 session 即時送達後退場，舊信只當案卷讀。檔案只留三種用途：案卷、跨人跨帳號（mailbox）、對象不是 Claude Code（Grok）。
- [臨] 有效模式（與通道無關）：首封「我是誰＋綱要正本路徑＋一句摘要＋四題」，對方一封一題回、每封附已驗證路徑或實測數字；分工定案用一句收束同步寫進雙方綱要；三方約 20 封就收斂到「各自向使用者要拍板」。

## 行動

- 發現別的 session 在討論同題 → 直接 SendMessage 開談，首封照有效模式；不再開 root-link／tri-link 信箱
- 討論結論要留案卷時才另存檔（寫進雙方綱要或 staging）
