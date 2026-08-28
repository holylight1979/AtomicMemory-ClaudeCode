# 注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: TURN_BUDGET_LIMIT, compute_token_budget, truncate_context, budget fallback, trim: pointer dropped, Context budget, 注入預算, 預算裁切, 過度砍, 分級, 字元數, native-memory-bridge, atom-index-bridge, 橋接檔, projects slug
- Created-at: 2026-08-28
- Related: 取用端稽核與瘦身規範-atomaudit與3kb預算, activation負值不是負相關-act-r對數尺度天然跨零-注入噪音修門檻與顯示勿過濾分數, feedback-原子記憶核心理念-知識經驗全積累分門別類-高精準零token浪費

## 知識

- [臨] 注入預算有三道閘：per-turn atom 段硬頂 TURN_BUDGET_LIMIT（wg_core）、每輪總額 compute_token_budget（依 prompt 估算 token 分級）、總額超支時的 _truncate_context_by_activation。調任一道前先量「熱 atom 全文率」（Logs/injection-turns.jsonl → memory-effect-report）；只調一道常把瓶頸推到下一道。
- [臨] 裁切演算法的坑：用「降成一行能省多少」估犧牲名單，再把名單裡多數整塊丟——整塊丟省的遠多於估算，預算會被砍到遠低於上限（實測 359/1000 卻丟 5 顆）。正解是由 activation 高到低回填：塞得下全文→全文，否則指標行，再否則丟。
- [臨] 總額分級不能看字元數：中文 37 字≈33 tok 是實質問句、英文 37 字≈9 tok 只是短句；字元分級把中文問句壓到最低額（1 全文/5 丟），改依 _estimate_tokens 分級後 4 全文/0 丟。任何「依 prompt 長度」的門檻都要用 token 口徑。
- [臨] 實機驗證 hook 注入時，假 session 必須先送 SessionStart 再送 UserPromptSubmit；只送 UPS 會被 _ensure_state 認領同 cwd 的兄弟 state（24h 窗），繼承 injected_atoms 而注入變 0，看起來像 bug 其實是設計。探針會在 access sidecar 留曝光計數，事後只能清 state/jsonl。
- [臨] CC 原生 memory 目錄（projects/<slug>/memory）的橋接檔 atom-index-bridge.md 是原子系統與原生記憶唯一接點；它列 atom 路徑，atom 搬進範疇資料夾後即全失效（曾 13/13 壞 7 週）。slug 規則是每個非英數字元各轉一個 '-'（c:\Users\x\.claude → c--Users-x--claude），不可合併。現由 sync-memory-index --write 尾端自動重產（fail-open）。

## 行動

- 動預算常數前先跑 memory-effect-report 看全文率與 trim 統計，改完用真 hook 進程（SessionStart+UPS）餵短/中/長 prompt 各 ≥2 次驗
- 看到 [Context budget: x/y | trim: …] 中 x 遠小於 y 卻有 dropped → 裁切演算法問題，不是預算不夠
- 搬 atom / 改索引後確認 projects/<slug>/memory/atom-index-bridge.md 路徑仍全部存在
