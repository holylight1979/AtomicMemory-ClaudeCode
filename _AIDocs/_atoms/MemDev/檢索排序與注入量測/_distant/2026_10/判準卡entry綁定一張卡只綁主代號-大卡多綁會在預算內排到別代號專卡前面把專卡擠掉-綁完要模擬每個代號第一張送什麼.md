# 判準卡Entry綁定一張卡只綁主代號-大卡多綁會在預算內排到別代號專卡前面把專卡擠掉-綁完要模擬每個代號第一張送什麼

- Scope: global
- Author: holylight
- Source: track-wave2-kit 006（entry-bind 副本試跑＋重建索引後模擬 ENTRY_BIND_TRIAL_CHECK PASS）
- Confidence: [臨]
- Trigger: Entry 綁定, 判準卡, entry-bind, cards_for_entry, judgment_cards, inject_budget_tokens, 專卡被擠掉, 切入點卡
- Created-at: 2026-10-21
- Related: 切入點帳guard-entry原始response永遠是none-逐筆回應型要呼叫resolve-responses-entry-stats只給計數且預設只看7天

## 知識

- [臨] 同一個代號綁了好幾張卡時，送卡順序是卡池（索引）順序、不是主次；一張大卡（約 1000 bytes）多綁別的代號，在 400 token 預算下會排在那些代號自己的專卡前面，把專卡擠掉（實測：綁 E10＋E07＋E11 的那張讓 E07、E11 的專卡都送不到）。
- [臨] 所以一張卡只綁它的主代號；「也用得上」的代號等預算放寬再加。G 規格卡（評分規格）綁上去多半排第二、被截斷或送不到，沒擠掉專卡。
- [臨] 綁完的驗法：在記憶副本上套用，照建受測環境的做法重建索引，再對每個有接線的代號跑 judgment_cards，看第一張是不是它的專卡、哪些綁了沒送到。


## 行動

- 綁 Entry 前先分主代號與順帶代號，只綁主代號
- 綁完在副本上模擬每個代號送什麼，專卡不在第一張就改綁法


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（判準卡在切入點送卡的排序與預算 cards_for_entry／judgment_cards）已從寫碼守門拔除 | memory-audit --delete |
