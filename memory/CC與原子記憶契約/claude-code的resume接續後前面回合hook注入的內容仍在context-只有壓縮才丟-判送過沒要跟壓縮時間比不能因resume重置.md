# claude-code的resume接續後前面回合hook注入的內容仍在context-只有壓縮才丟-判送過沒要跟壓縮時間比不能因resume重置

- Scope: global
- Author: holylight
- Source: 分支 inject-budget e096049f
- Confidence: [臨]
- Trigger: --resume, resume 接續, resume 後 context, 壓縮才丟, 送過重置, SessionStart resume, 重複注入, post_compact_at, 輸入 token 對帳
- Created-at: 2026-10-27
- Related: 壓縮後根層-claudemd-由磁碟重讀不需自製-constraint-pinning-真正會丟的是對話中的計畫脈絡-用-staging-計畫檔加-sessionstart-resume-指標接續

## 知識

- [臨] Claude Code 用 `--resume` 接續 session 時，前面回合 hook 注入的文字仍在模型 context 裡；只有壓縮（compact）才會真的丟。
- [臨] 實測：resume 後第一次呼叫輸入 95,080 token ≈ 上一回合最後一次 89,950＋輸出 2,334＋新進約 2.8k；兩跑同形。
- [臨] 所以 hook 記「這段送過沒」（避免重送）不能在 SessionStart(source=resume) 就清掉，要跟最近一次壓縮的時間比：送出早於壓縮才算丟了、要重送。本系統的壓縮點記在 state 的 pre_compact_snapshot／post_compact_at。

## 行動

- 寫「送過就不重送」的 hook：重置條件綁壓縮，不綁 resume
- 懷疑 resume 有沒有丟 context：比 transcript 裡 resume 前後兩次呼叫的輸入 token
