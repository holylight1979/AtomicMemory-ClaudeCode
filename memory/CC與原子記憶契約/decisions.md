# 全域決策

- Scope: global
- Author: holylight
- Source: commit:7deb043 2026-03-02（原對話已逾保留期）
- Confidence: [固]
- Trigger: 決策, 記憶系統, 原子記憶, 架構細節, context budget
- Related: decisions-architecture, toolchain, toolchain-ollama

## 知識

- > 架構細節（核心架構 / V3 管線 / SessionStart 風暴修復）已移至 `decisions-architecture.md`
- ### 跨 Session 鞏固（效用驅動）
- [固] 晉升門檻（SYNC: server.js toolAtomPromote / wg_atoms._self_iterate_atoms / lib.atom_access）：效用 Wilson 軌為**唯一自動晉升路徑**：效用 Wilson 下界（Beta-Bernoulli α=useful_hits/β=used_fail；succ=α−1,fail=β−1,n=succ+fail）≥ promote_lb(0.6) 且 n ≥ min_n(3)，z=wilson_z(1.28)；降級候選 ≤ demote_lb(0.35) 且 n ≥ demote_min_n(5)（不自動降，列裁決）；旋鈕值以 workflow/config.json usefulness 段為準；慢衰減 λ=0.97（SessionEnd）。Confirmations 軌已除役（唯一資料源 per-turn extraction 停產，全庫 confirmation_events=0）。ReadHits（注入讀取）：純曝光計數、不參與晉升（防純注入頻率晉升劣化品質，Xiong 2505.16067）。旋鈕：workflow/config.json usefulness.{promote_lb,demote_lb,min_n,wilson_z,decay_lambda,rare_token_min,lexical_overlap_min}
- ### 品質機制
- [固] 自我迭代精簡為 3 條：品質函數（Hook）、證據門檻（Claude）、震盪偵測（Hook）
- ### Fix Escalation
- [固] 同一問題修正第 2 次起 → 6 Agent 精確修正會議
- [固] Guardian 自動偵測 retry_count ≥ 2 → 注入信號
- [臨] 放行／欠帳判定契約（SYNC: hooks/wg_release_rules.py）：所有「這回合算不算改碼／欠不欠案例／算不算開回合／要不要擋」的判定集中在一支純函式模組，每個情境一條有名字的規則（RULES 表）＋至少一個會紅的案例＋一個反例；呼叫端（stop／post_tool_use／pre_tool_use／wg_core／wg_overview／wisdom_engine／ups_gates／wg_evasion／wg_harvest）只蒐集事實交給模組判、不自己判；擋訊息固定格式 `✗ (<字母>) <規則名>：<一句現象>｜證據：<一行一證據>`，擋次預算每條規則各自計次、擋滿訊息列全部條目。閘誤判的修法是在這支模組加規則與紅案例，不加例外清單、不放寬、不整輪不擋（原設計者 2026-10-13 裁定，044／045 落地）。

## 行動

- 記憶寫入走 write-gate 品質閘門
- 向量搜尋 fallback：Ollama → sentence-transformers → keyword
- Guardian 一般閘（退避、AEC、AtomAudit、同步）每回合最多擋 2 次，第 3 次放行並記帳；寫碼查核（對帳 (a)～(d)＋量尺）擋滿不准自行放行，只能照【收尾放行確認】用 AskUserQuestion 問使用者，使用者在最後一次擋之後放行才放這一回合（記 user_release，健檢列 red）；子代理、裁判、headless 沒人能回答，擋到底
