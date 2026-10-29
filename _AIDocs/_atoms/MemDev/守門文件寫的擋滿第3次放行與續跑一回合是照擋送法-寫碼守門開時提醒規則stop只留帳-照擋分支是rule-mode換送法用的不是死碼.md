# 守門文件寫的擋滿第3次放行與續跑一回合是照擋送法-寫碼守門開時提醒規則Stop只留帳-照擋分支是RULE_MODE換送法用的不是死碼

- Scope: global
- Author: holylight
- Source: TECH 待裁 F 讀碼（hooks/handlers/stop.py PickOne 段與 ReconcileGate 段、hooks/wg_release_rules.py RULE_MODE），commit bd0ab7aa
- Confidence: [臨]
- Trigger: RULE_MODE, gate_mode, 照擋, 提醒, 第 3 次放行, 續跑一回合, STOP_REMIND_LEDGER_ONLY, PickOne, reconcile_overflow, 死碼, 守門文件矛盾, 擋或提醒
- Created-at: 2026-10-29
- Depends: path:~/.claude/hooks/wg_release_rules.py, path:~/.claude/hooks/handlers/stop.py
- Quote: 「上SESSION給的prompt： 接續 TECH.md 重整的收尾工作（repo：C:/Users/holylight/.claude，分支 main）。 先讀 memory/_staging/next-phase-TECH-重整待裁.md： 1. 「待驗收」：我已在 GitHub／GitLab 網頁看過 TECH.md 與 TECH/ 四份文件的結果是：＿＿（照我的回饋修）。 2. 「待裁」…」

## 知識

- [臨] 讀守門文件看到「擋滿第 3 次放行」「Stop 回 additionalContext 讓對話續跑一回合」，先查那條規則在 `hooks/wg_release_rules.RULE_MODE` 是 block 還是 remind：寫碼守門開時 remind 的規則在 Stop 只走 `_remind_logged` 留帳，那些句子描述的是照擋時的送法，不是現況。
- [臨] 例：PickOne 與寫碼查核 (e) 只在寫碼守門開時跑，開時一律 remind；`hooks/handlers/stop.py` 裡續跑與 reconcile_overflow 那兩條分支實際走不到，但它們是 `RULE_MODE` 改表換送法用的（verify_stop_reconcile／verify_need_goal 用 monkeypatch 把 `_gate_mode` 釘成 block 驗判定內容），不是死碼，別提議刪。
- [臨] 判法：分支條件含 `_gate_mode(...) == _REMIND` 的 else 支＝照擋送法；外層又要求寫碼守門開（v6）時，只有改 RULE_CLASS 才走得到。

## 行動

- 讀守門文件的擋滿／續跑描述前，先看規則在 RULE_MODE 是 block 還是 remind
- 看到只在照擋時走得到的 Stop 分支，先查測試有沒有把 gate_mode 釘成 block，不當死碼刪
