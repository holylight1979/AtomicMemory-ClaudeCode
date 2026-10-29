# 量hook注入改前改後-同一串事件重播兩棵樹-包記號切出要量的文字

- Scope: global
- Author: holylight
- Source: 2026-10-22 pull-goal-locate 001 實測
- Confidence: [臨]
- Trigger: 注入量測, 事件重播, 改前改後 token, 目標樹注入, goal_inject_replay, 注入瘦身
- Created-at: 2026-10-22

## 知識

- [臨] 量 hook 注入改前改後：用 git archive 解出舊樹，同一串事件直接呼叫兩棵樹的入口函式（on_read、on_edit、batch_lines、on_prompt…），把 render、_header、brief 這類產生器包一層記號，從注入裡切出那段數 token；事件組成照真實 transcript 數次數。腳本：_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-實測/goal_inject_replay.py。
- [臨] 實測結論：每則提示固定附兩行就是下限，小樹（5 節點）只降到 44%；同一使用者回合內容沒變只附一次之後才到 19%。

## 行動

- （依知識內容判斷）
