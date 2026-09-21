# Claude 審查者 D：遙測實證雞肋審查 — 摘要（23 次工具呼叫，149K tokens；腳本 scratchpad/telemetry_audit*.py）

母體：近 30 天 99 個 session、183 個 transcript（80 個 subagent）。

## 三個量測事實
1. sidecar useful_hits/used_fail 含 Laplace prior +1（atom_access.py:549），直接讀會得「每顆都有效用、useful 率全擠 0.5」假象。
2. `_promotion_audit.jsonl` 的 `hint` 列（90 天 1286 筆，94%）不是晉升事件，是 UPS 注入時的稽核列（ups_inject.py:477-486）。真晉升：auto_observe 55、manual 27、**降級 0**。
3. pytest 直接寫進正式 Logs/：guard-aec_pending.jsonl 11/11 session_id="sid"；atom-debug evasion 81 筆全 pytest 路徑；recall_miss 336 筆中 79 個爆發秒是測試。

## 精簡候選（有數字）
- **hint 稽核列**：8 顆 atom 貢獻 793 列（feedback-completion-gates 192 列，n=84、lb 0.596 永遠卡門下）；無讀者 → 停寫。
- **效用降級路徑**：90 天 0 筆；live 227 顆 n≥3 且成功 0 只 1 顆；useful 率（去 prior）0:13 / <.25:10 / <.5:22 / <.75:68 / ≤1:51 → 歸因太寬幾乎掉不到 0.35。砍前先決定是否收緊歸因。
- **AEC-Pending 閘**：30 天真實觸發 0（11 筆全測試）；DeferralGate（18 筆/17 session）已涵蓋。
- **AEC HUD 決策 API**：全期用 1 次。
- **Codex 裁判無綁定佔位列**：30 天 203 列中 181 列（89%）「案卷未組」；真裁判 30 天 22 次／全期 34 次：fail 21 / uncertain 13 / **pass 0**；human_label 2/438 → 無法算精度 → **需拍板，不砍**（先 20 筆人工標註）。
- **17 個 60 天零使用 skill**：Skill 呼叫只有 handoff 6、memory 4(+3)、vector 2、continue 2；0 次：atom-debug, browse-sprites, changelog-debug, codex-companion, conflict, consciousness-stream, extract, fix-escalation, generate-episodic, harvest, heal-review, journal, karpathy-guidelines, read-project, refile, skill-creator, upgrade；其中連 hook 也沒引用 10 個。描述合計 ~940 tok/prompt，零使用者 ~730 tok。（注意：9 個已 disable-model-invocation，其描述不進模型路由——Codex #1/#3；多機需確認）
- **cross_session confirmations 軌**：config 仍 enabled、90 天 3 筆 → 關。
- **recall-miss**：全期 19 筆／30 天 8 筆；`kq.get` 對字串 knowledge_queue 拋 AttributeError，08-26～09-18 真實 session 16 個時刻 crash → 修一行。
- **rescue-log**：30 天 417 筆／75 session／86 顆 atom，全系統精度最高的「真被用到」證據，只被報表讀 → 接進 α/β。
- **health-weekly episodic 判定**：只看 memory/episodic/；C:\Projects\.claude\memory\episodic 113 檔（最後 09-16）、TSLG 09-18；09-18 三個 ~/.claude session 確實 0 產出（一個改 11 檔跑 2 小時），跳過路徑無 log。
- **測試污染 Logs + SessionStart 三個 advisory 08-26 起每次啟動 crash（unpushed 89、health 84、personal_sync 30），09-18 commit 後無再現——health dead-man switch 靜默死 3 週**，訊號只進 debug log。

## 數據顯示有效、不要動
- 每輪注入 30 天 509 輪：ok 1163、skip 767（**39.7% 候選被 1200 tok 預算砍掉**）、cold 1008；平均 857/1200，**155 輪（30%）撞頂** → 不砍注入端。
- live 227 顆：近 30 天注入 191（84%）；從未注入 22（9.7%，local realm 舊 atom）。
- PAN warn 模式：30 天 1262 事件；pass 率 W32 29% → W38 56%，有學習效果。
- 退避偵測 71 筆/40 session；aec-report 23 份；DeferralGate 18 筆真擋；auto_observe 15 筆/30 天；lang guard 212 筆（無法量矯正效果）；vector `_semantic_search` 696 次 59% 回 0；episodic search 233 次 31% 回 0（有被消費）。

## 前五
1. 修 recall-miss 一行 + rescue-log 接進 α/β。
2. 停寫 hint 列、Codex 佔位列改計數、關 cross_session。
3. 測試 Logs 隔離 + SessionStart 錯誤浮出 statusline。
4. 17 個零使用 skill 搬 _archived/（多機先確認）。
5. episodic 跳過原因落 log + health 掃專案層。

## 不建議
砍注入端；砍 PAN；現在砍 Codex 裁判；批次清 [臨] >60 天 31 顆（17 顆 n<3 但 read_hits 3–39 是低流量非無用）。

## 未查到
失敗關鍵字萃取 30 天產出數（35 顆 Failures 無 source；26 顆 S3 遷移、9 顆手動）；使用者決策萃取產出數；selective forget 09-03 後 0 搬入；**always-load 以 1.5 tok/字算 ~5,800 tok（IDENTITY 1919 + coding-style 1542 + core 1206 + USER 803 + MEMORY 322），簡報寫 1,500–2,000 偏低 2–3 倍**（實際 CJK ~1–1.3 tok/字 → ~4,500）；`skills/synced/` 207 檔 3.6MB 不在 _skill_index.json。
