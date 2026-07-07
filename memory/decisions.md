# 全域決策

- Scope: global
- Confidence: [固]
- Trigger: 決策, 記憶系統, 原子記憶, 架構細節, context budget
- Related: decisions-architecture, toolchain, toolchain-ollama

## 知識

> 架構細節（核心架構 / V3 管線 / SessionStart 風暴修復）已移至 `decisions-architecture.md`

### 跨 Session 鞏固（效用驅動）
- [固] 晉升門檻（SYNC: server.js toolAtomPromote / wg_atoms._self_iterate_atoms / lib.atom_access）：
  - 效用 Wilson 軌為**唯一自動晉升路徑**：效用 Wilson 下界（Beta-Bernoulli α=useful_hits/β=used_fail；succ=α−1,fail=β−1,n=succ+fail）≥ promote_lb(0.6) 且 n ≥ min_n(3)，z=1.96；降級候選 ≤ demote_lb(0.35) 且 n≥3（不自動降，列裁決）；慢衰減 λ=0.97（SessionEnd）
  - Confirmations 軌已除役（唯一資料源 per-turn extraction 停產，全庫 confirmation_events=0）
  - ReadHits（注入讀取）：純曝光計數、不參與晉升（防純注入頻率晉升劣化品質，Xiong 2505.16067）
  - 旋鈕：workflow/config.json usefulness.{promote_lb,demote_lb,min_n,wilson_z,decay_lambda,rare_token_min,lexical_overlap_min}

### 品質機制
- [固] 自我迭代精簡為 3 條：品質函數（Hook）、證據門檻（Claude）、震盪偵測（Hook）

### Fix Escalation
- [固] 同一問題修正第 2 次起 → 6 Agent 精確修正會議
- [固] Guardian 自動偵測 retry_count ≥ 2 → 注入信號

## 行動

- 記憶寫入走 write-gate 品質閘門
- 向量搜尋 fallback：Ollama → sentence-transformers → keyword
- Guardian 閘門最多阻止 2 次，第 3 次強制放行
