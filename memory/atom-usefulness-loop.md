# atom-usefulness-loop

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 效用閉環, usefulness, record_usefulness, atom 晉升, use 偵測, Wilson 下界, 慢衰減, Beta-Bernoulli, 注入使用結果, useful_hits, used_fail, 原子記憶開發
- Created-at: 2026-06-01
- Related: decisions, workflow-rules, feedback-memory-system-doc-sync, memory-pipeline-silent-failure-2026-05, atom-table-support, atom-元資料編輯與晉升閘真相, confirmations-已退役-phase2-usefulness-接管晉升

## 知識

- [臨] Phase 2(#2) 注入→使用→結果閉環：用真實效用 (α,β) 取代曝光次數(ReadHits)校準 atom 信心。Beta-Bernoulli + 零成本詞彙重疊 use-gate + Wilson 下界 + 慢衰減。設計 SoT=程式碼，導覽見 _AIDocs/SPEC_ATOM_V5.md §12。
- [臨] (α,β)=useful_hits/used_fail 存 <atom>.access.json（schema v3，Laplace prior 1，v2→v3 冪等 migration），**只兩個 scalar、不寫 .md**（零索引膨脹守 token 紅線）。succ=α−1, fail=β−1, n=succ+fail。所有寫入走 lib/atom_access.py funnel。
- [臨] use 偵測（wg_atoms.detect_atom_use）：atom 稀有 token（識別碼/路徑/API + CJK bigram、去停用詞）vs 本 turn assistant 活動（wg_evasion.get_current_turn_text）求 containment/Jaccard；共享≥rare_token_min(2) 或 containment≥lexical_overlap_min(0.18) → used。邊界差一才用 Ollama embedding cosine tiebreak（fail-safe、偶發）。
- [臨] success 3 值（stop._detect_turn_outcome 複用 failing_tests/claims_completion/evasion/retry）：+1=完成宣告且乾淨；0=error/糾正/retry/evasion；**其餘 unknown=no-op（防雜訊污染關鍵守則）**。stop._attribute_usefulness 對 used 且 outcome 決定性者 record_usefulness（α++/β++），per-turn 一次性（turn_seq 守門）。Phase 1 subagent_injections 一併歸因、agent error 覆寫 fail。
- [臨] 晉升閘=真實 Confirmations 主軌 OR 效用 Wilson 下界（升≥promote_lb 0.6 且 n≥min_n 3，z=1.96）；**ReadHits 退出晉升、降為純曝光計數**（取代 Phase 0 過渡）。降級候選≤demote_lb 0.35,n≥3 列 staging 報告不自動降。慢衰減 λ=0.97（SessionEnd _self_iterate_atoms）α←1+λ(α−1)。
- [臨] py↔js 鏡像：wilson_lower_bound/usefulness_*（lib/atom_access.py）↔ wilsonLowerBound/usefulnessStats（server.js toolAtomPromote），SYNC: 註解 + memory/decisions.md 對齊。**改 server.js 後須重啟 MCP server 才生效新晉升閘**。旋鈕：workflow/config.json usefulness.{...}。守門：verify_usefulness_access_phase2(18)+verify_usefulness_loop_phase2(21)。
- [觀] embedding tiebreak (wg_atoms.make_embed_tiebreak_fn) 對真實 Ollama qwen3-embedding(4096-dim) live 煙測(2026-06-01)：cosine 語義正確（相似~0.85/無關~0.29、similar≫unrelated）、fail-safe 穩（逾時/服務掛→None 不污染主判）。但 prod embed_timeout_s=1.5 對 CJK 偏緊：暖機短文~0.6s/embed、CJK 長句單次可>1.5s→tiebreak 常 fail-safe None；冷載~24s→模型未保溫時近惰性。屬 best-effort by-design；要 CJK 實效須 Ollama 保溫或酌升 embed_timeout_s≈2.5。
- [觀] UPS 注入晉升提示(user_prompt_submit.py)改由 lib/atom_access.usefulness_hint_tier 驅動(eligible/near/None)：純曝光(ReadHits)/n<min_n 一律不提示，取代 Phase 2 前的 stale READHIT_THRESHOLDS 提示語。

## 行動

- （依知識內容判斷）
