# 背景跑的測試hook拿不到輸出也不留收據-超過單次工具上限的批次要拆成數段前景跑

- Scope: global
- Author: holylight
- Source: commit:868b639a 2026-10-21（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: run_in_background pytest, 背景跑測試, 收據不入帳, 超過 10 分鐘的驗證, 批次拆段, verify 收據, PYTEST 哨兵
- Created-at: 2026-10-21
- Quote: 「除非像是先前我曾經說的"session派工之間必須等(衝突或先後必須..那些)"，否則就請你持續多開加速完工，須注意工人模型用Opus、Effort 也注意一下，除非"絕對必須用Fable"。」

## 知識

- [臨] 用 run_in_background 跑 pytest，PostToolUse hook 拿不到它的輸出，哨兵與 PYTEST 收據都不會入帳；之後 reconcile 引用不到 R 號。
- [臨] 做法：超過單次工具呼叫上限（10 分鐘）的驗證，拆成數段各在前景跑（每段 ≤10 分鐘），每段各自留收據；真的跑不完的才照 coding-style 自寫收據（self_receipt）。
- [臨] 實例：合併後全重跑 2400 案，拆三段前景跑才拿到收據。

## 行動

- 長驗證先估時間再拆段，不先丟背景
