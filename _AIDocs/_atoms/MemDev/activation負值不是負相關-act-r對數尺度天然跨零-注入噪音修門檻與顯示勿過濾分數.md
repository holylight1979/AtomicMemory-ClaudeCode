# activation負值不是負相關-ACT-R對數尺度天然跨零-注入噪音修門檻與顯示勿過濾分數

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: activation, ACT-R, 負分, 注入噪音, truncated, context budget, 裁切, 寧缺勿截, truncated_pointer_max, budget 750
- Created-at: 2026-08-21
- Related: escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造, decisions-architecture

## 知識

- [臨] 始末：評審 session 觀察到「[Atom:x] (truncated, activation=-2.70)」，直覺判定『相關性為負仍注入＝純噪音、該加 activation<=0 過濾』。查原始碼推翻：activation 是 ACT-R base-level `ln(Σ t_k^-d)`（wg_atoms.compute_activation），對數尺度天然跨零——負值＝近期存取少，不是不相關；相關性由 trigger/BM25/vector 入場閘另行把關。加分數過濾會誤殺低近期性但高相關的策展 atom（workflow-rules 這類核心 atom 正是常客）。
- [臨] 正解是修門檻與顯示設計：(1) 截斷行不印 activation 數值（跨零尺度的負數對讀者是誤導，移 debug log）；(2) 裁切改寧缺勿截——被犧牲者僅 activation 最高前 N 顆留一行指標（injection.truncated_pointer_max），其餘整塊不注入，明細落 log + 尾行附 trim 統計。
- [臨] budget 上限有時 750/1750/2550 非 bug：compute_token_budget 按 prompt 估算 token（CJK-aware，非字元數）分級給 1000/2000/3000 起始額，build_context 逐段扣減（session context −200、JIT −250）後才是尾行分母。

## 行動

- 看到跨零尺度分數（logit/log/z-score）想加『負值過濾』前，先查分數定義：負值語意是『不相關』還是『尺度本來跨零』——修錯方向會砍掉有用注入
- 注入端降噪優先序：整塊不注入 > 一行指標 > 截到殘缺；截到只剩標題的條目佔 budget 零效用
- 降級必留觀測訊號：debug log + in-band 統計行
