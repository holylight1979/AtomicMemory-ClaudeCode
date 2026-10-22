# 改wg_release_rules後verify_release_rules要整支跑-有模組級檢查每條規則名要有案例與禁連續破折號-k篩選會漏

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: wg_release_rules, verify_release_rules, 禁破折號, test_044, -k 篩選
- Created-at: 2026-10-22
- Source: session:7e33fec4 2026-10-22

## 知識

- [臨] hooks/verify/verify_release_rules.py 有兩支模組級檢查：test_044（RULES 每條規則名都要在本檔案例出現）與 test_045_rules_module_has_no_em_dash（wg_release_rules.py 不准有「——」）。新加規則只跑 `-k 006` 之類會全綠，整支跑才紅（閘小修 006 實遇：規則文字寫了 5 處「——」）。改 wg_release_rules 一律整支跑，新規則名同時在 verify_release_rules 補一案。

## 行動

- （依知識內容判斷）
