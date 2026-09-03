# 禁語 hook 不開引用豁免（誤報噪音 vs 契約破洞不對稱）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 禁語, 退避語, evasion hook, wg_evasion, 誤報, false positive, 引用豁免, detect_evasion, forbidden-phrases
- Created-at: 2026-07-29
- Related: feedback-workflow-discipline, feedback-rigor-standards

## 知識

- [臨] `wg_evasion.py` 的 `detect_evasion()` **不加引用豁免**（不跳過「」/『』/`code`/行首 > 區間的命中）。使用者 2026-07-29 明確否決此補丁。
- [臨] 否決理由：引用豁免＝退避方只要把話包進引號就能過關，可自造引號洗白。誤報代價僅收尾報告多幾行噪音，漏報代價是契約破洞——兩者不對稱，須往保守側靠。
- [臨] 誤報的真實來源不是 hook 邏輯，是 AI 反覆複述被抓的禁語來檢討。降噪正解＝認錯一次就停，不每輪重貼那個詞，而非放寬偵測。
- [臨] 實例：某 session 因同一個禁語被攔 5 次，第 1 次為正確攔截（確實在推卸），其餘 4 次全是引述自己前一輪的檢討文字所致。
- [臨] 跨 realm 護欄：外部專案 session 改不了 `~/.claude/hooks/`（CrossRealmWriteBlock），此拦截為預期行為，勿繞。

## 行動

- 未來若再想放寬 detect_evasion 的偵測面（引用豁免/白名單/情境判斷）→ 先讀本 atom，此案已否決，勿重提
- 被禁語 hook 攔到時：認錯並修正一次即可，後續回合不再複述該詞，避免自我觸發迴圈
- 誤報若確實困擾，正解方向是減少複述，不是降低偵測靈敏度
