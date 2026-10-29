# 解除Entry綁定的卡下次SessionEnd會被範疇自動搬移搬走-驗收資料根帶了會在跑中搬並在下一回合開場印卡名-建環境先預判不帶

- Scope: global
- Author: holylight
- Source: track-wave2-kit 011 2026-10-22（A3 transcript 開場提示＋資料根稽核帳 realm_move 01:17:39Z；verify_realm_probe REALM_PROBE_CHECK PASS）
- Confidence: [臨]
- Trigger: 解除綁定, 解綁 Entry, 範疇自動搬移, 已自動歸 local, realm_move, 驗收資料根, 建環境, 卡集比對 刪掉, _sweep_realm_auto_migrate, ENTRY_BOUND_STAYS_CORE
- Created-at: 2026-10-22
- Depends: path:~/.claude/hooks/wg_atoms.py
- Related: 驗收用乾淨資料根三坑-缺memory-meta詞表g6靜默退回舊詞表-索引0筆與健檢警告帶偏ai-試跑資料根放在系統repo內會被背景同步commit, 綁了entry的判準卡是量尺-非總控台session要改得先宣告改判準卡哪張理由留帳-不唯讀以保留判錯當天落卡的迴路

## 知識

- [臨] 綁 Entry 的卡不會被範疇自動搬移搬走（ENTRY_BOUND_STAYS_CORE）。一解綁，下一次 SessionEnd 的 _sweep_realm_auto_migrate 就照詞庫把它搬去 _AIDocs/_atoms（本地範疇），下一個 SessionStart 會印「[Realm] 已自動歸 local：<卡名>」。
- [臨] 驗收資料根照建的那一刻的 live 帶卡：live 解綁之後、還沒跑到 SessionEnd 就建，資料根會帶著這張卡。受測第一回合收尾就被搬走，第二回合開場把卡名（就是那張卡教的做法）送到受測 AI 眼前。卡集比對還會把它記成「刪掉」，看起來像受測 AI 刪的，要看資料根稽核帳 op=realm_move 才分得出來。
- [臨] 預判做法：跑真的 _sweep_realm_auto_migrate，把 _load_tool_module("atom-set-realm.py") 換成只記卡名、回 noop 的假搬移器，lib.atom_io._audit_log 換成什麼都不做，再數 classify_realm 被呼叫幾次，證明真的逐張判過。對 live 跑也不會寫任何東西。

## 行動

- 解綁判準卡或新寫卡之後要建驗收資料根：先預判哪些卡會被搬，這些卡不帶進資料根
- 卡集比對看到「刪掉」：先查資料根稽核帳有沒有 op=realm_move
