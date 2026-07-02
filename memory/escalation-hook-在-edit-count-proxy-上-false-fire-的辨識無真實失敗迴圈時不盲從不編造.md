# escalation-hook 在 edit-count-proxy 上 false-fire 的辨識（無真實失敗迴圈時不盲從不編造）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: fix-escalation, DeepPostMortem, deep-post-mortem, 反覆重試, retry, 同檔多次修改, proxy, false positive, 偵測到高effort失敗, post-mortem 要求, 偵測到重複修正, escalation hook
- Created-at: 2026-06-25
- Related: cognitive-patterns, feedback-rigor-standards, 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證, post-mortem-write-raw靜默拒寫invalid-source-未檢回傳值誤報成功-代理訊號非真副作用

## 知識

- [臨] 核心紀律（跨專案 core）：FixEscalation / DeepPostMortem Stop hook 以 retry / fix-escalation 當「失敗中反覆」的 effort 訊號。retry 已 error-gate（僅在真測試/lint 失敗未解 failing_tests 期間、同檔反覆編輯才計）；DeepPostMortem 另需疊一個 real_failure 訊號（failing_tests ∨ evasion ∨ 未宣告完成）才 fire。故單純多次迭代式開發 / API 探索不進 retry、也不觸 postmortem。**殘留誤觸面**：「未宣告完成」這個 real_failure 分支不需 failing_tests——正常重度迭代若在未宣告完成時結束、又疊上 retry，仍可能觸發，此時未必真卡住。此為 [[cognitive-patterns]] proxy-metric 誤用類。**這些 hook 在每個專案（含 ~/.claude 本體）都會 fire，故此辨識紀律屬跨專案 core，非單一專案知識。**
- [臨] 辨識判準 = 「同一錯誤是否重複出現 ≥ 2-3 次仍未解」。是 → 真迴圈，走 /fix-escalation 深層分析。否（每次錯誤不同、一修即過、最終結果全綠/驗證 PASS）→ false positive。
- [臨] 錯誤行為（若盲從 false positive）：把「正常迭代式開發」誤當「修不好的迴圈」去跑 escalation，或為满足 hook 而 fabricate 一份戲劇化的 post-mortem（虛構根因 / 設計原理）→ 污染失敗記憶、降信任。違反 [[feedback-rigor-standards]]（不為满足 hook 編造規則 / 根因）。
- [臨] 正確做法：辨識為 false positive 時據實標註並簡短說明理由（同錯未重複 ≥ 2-3 次），不盲從、不 fabricate。真有可重用技術 lesson 才寫，且寫在主題對應的原子（工具踩坑等），不為满足 hook 而重複戲劇化。
- [臨] 實例（工具開發）：單檔約 6 次編輯撞 2 輪「不同」編譯錯（先 ctor、後 cast），每次「診斷→修→建置」一次過、最終 build 0 錯 + verify-roundtrip 全 PASS。session 末 FixEscalation + DeepPostMortem 觸發；正確處置＝辨識為 false positive，而非編造 post-mortem。

## 行動

- 收到 escalation / post-mortem hook 觸發 → 先判「同錯是否重複 ≥ 2-3 次未解」；否則據實標 false positive、不 fabricate post-mortem
- 真實技術 lesson 寫在主題對應的原子（工具踩坑等），不為满足 hook 而重複戲劇化
