# decisions

- Scope: global
- Author: holylight
- Source: commit:7deb043 2026-03-02（原對話已逾保留期）
- Confidence: [固]
- Trigger: 決策, 記憶系統, 原子記憶, 架構細節, context budget
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的工作 session track-a6，總控台是 claude-9f（調度；對人總控台是 claude-91）。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-a6（分支 v6/track-a6，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\…」
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

## 行動

- 記憶寫入走 write-gate 品質閘門
- 向量搜尋 fallback：Ollama → sentence-transformers → keyword
- Guardian 一般閘（退避、AEC、AtomAudit、同步）每回合最多擋 2 次，第 3 次放行並記帳；寫碼查核（對帳 (a)～(d)＋量尺）擋滿不准自行放行，只能照【收尾放行確認】用 AskUserQuestion 問使用者，使用者在最後一次擋之後放行才放這一回合（記 user_release，健檢列 red）；子代理、裁判、headless 沒人能回答，擋到底
