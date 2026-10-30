# claude-p無頭跑會被hook判成無法互動-問人類流程驗不到-預設CLAUDE_CODE_ENTRYPOINT=claude-vscode可保留但-p沒有AskUserQuestion

- Scope: global
- Author: holylight
- Source: session 26d36367（2026-10-21，入口 smoke 40/40、22/22 筆 entrypoint）
- Confidence: [臨]
- Trigger: claude -p, 無頭, headless, CLAUDE_CODE_ENTRYPOINT, sdk-cli, non_interactive_reason, 無頭驗收, AskUserQuestion 不存在
- Created-at: 2026-10-30
- Related: 驗收用乾淨資料根三坑-缺memory-meta詞表g6靜默退回舊詞表-索引0筆與健檢警告帶偏ai-試跑資料根放在系統repo內會被背景同步commit
- Supersedes: claude-p無頭跑會被hook判成無法互動-g9第二意見整條不觸發-預設claude-code-entrypointclaude-vscode可保留但-p沒有askuserquestion

## 知識

- [臨] `claude -p` 會把行程的 CLAUDE_CODE_ENTRYPOINT 設成 sdk-cli；hooks/wg_release.non_interactive_reason 看到 sdk* 就判「無法互動」：閘擋滿改「擋到底」不叫 AI 問人，規則寫明 headless 不觸發的閘整條不跑。用無頭代打做驗收時，這些流程根本驗不到。
- [臨] 實測 claude.exe 2.1.304：claude 只在環境變數未設、或值等於 cli 時才在 -p 改成 sdk-cli；先預設 CLAUDE_CODE_ENTRYPOINT=claude-vscode 再跑 -p，工具環境與 transcript 每筆 entrypoint 都是 claude-vscode，hook 當成 VS Code 互動 session。
- [臨] 代價：-p 底下沒有 AskUserQuestion 工具（ToolSearch 找不到），閘擋滿要 AI 問使用者時它只能用文字問；stop.py 不看 stop_hook_active，要用 --max-turns 封頂防 Stop 反覆擋燒額度。
- [臨] 無頭實跑要驗「誤警報不再讓 AI 停手」，入口得設成會停手的那種（CLAUDE_CODE_ENTRYPOINT=claude-vscode）：sdk-cli 入口本來就判成無頭、不停手，跑出「沒有 halted」什麼也證明不了；設成 claude-vscode，誤警報才會真的停手，結果才有意義。
- [臨] 入口設 claude-vscode 時，寫碼查核擋滿要人放行會一直擋（實測連擋 11 次）：無頭題目要讓 AI 在同一回合改到能覆蓋改動的測試，避開「改了程式欠驗證案例」這條；或這條路改用 sdk 入口驗。

## 行動

- 無頭驗收要蓋到擋滿問人流程：該題預設 CLAUDE_CODE_ENTRYPOINT=claude-vscode，並加 --max-turns
- 判分時先看 index／transcript 的 entrypoint，sdk 入口下互動類流程判「沒發生（跑法）」不判沒過
