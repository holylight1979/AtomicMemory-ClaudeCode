# 修剪必載檔前先對always-load-contracts的must_contain-章節標題字樣也算契約句

- Scope: global
- Author: holylight
- Source: session 050c2387 2026-10-28；commit d0ee6300（2026-10-27 精簡 IDENTITY 時中招）
- Confidence: [臨]
- Trigger: IDENTITY.md 修剪, USER.md 修剪, core.md 修剪, 必載檔, Guardian:Contract, always-load-contracts, 缺硬契約
- Created-at: 2026-10-28
- Depends: path:C:/Users/holylight/.claude/memory/_meta/always-load-contracts.json

## 知識

- [臨] 精簡 IDENTITY.md／USER.md／rules/core.md 前，先 grep memory/_meta/always-load-contracts.json 的 must_contain：哨兵只做字面比對，章節標題（例「收尾誠實」「反退避契約」）也算契約句，內容留著但標題改字就會在 SessionStart 報「缺硬契約」、run_verify 紅。
- [臨] 中招的修法是標題補回字樣（例「## 收尾誠實 ＋ 反退避契約」），不必搬內容；改 live 檔要同步 templates/ 同名模板，驗 hooks/verify/verify_always_load_contracts.py 一支即可。

## 行動

- 精簡必載檔前：grep must_contain → 每句在新稿裡都找得到才交
- 改 live 與 templates/ 同步 → 跑 verify_always_load_contracts.py
