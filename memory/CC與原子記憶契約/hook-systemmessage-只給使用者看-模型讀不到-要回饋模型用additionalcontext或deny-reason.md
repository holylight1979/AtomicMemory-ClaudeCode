# hook-systemMessage-只給使用者看-模型讀不到-要回饋模型用additionalContext或deny-reason

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: systemMessage, additionalContext, hook 輸出, Stop hook 回饋模型, hook 提醒無效, Stop says
- Created-at: 2026-10-01
- Source: session:97005647#db45aec6 2026-10-01
- Quote: 「改。」

- Related: sessionstart的提示只有模型看得到-要使用者做決定就寫成叫模型用askuserquestion問的指示-問到有答案為止不要只提示一次

## 知識

- [臨] Claude Code hook JSON 的 `systemMessage` 只是「shown to the user」——不進模型 context、不算 token。拿它當「提醒模型」用等於零效果（lang_guard 曾如此誤用：同 session 觸發 15 次、英文回應連續 8 次零校正）。
- [臨] 要讓 hook 文字進模型：Stop/SubagentStop 用 `hookSpecificOutput.additionalContext`（回合結尾注入、對話續跑一回合讓模型行動；input 的 `stop_hook_active=true` 時要自停防迴圈）；PreToolUse 用 `permissionDecision: deny` + `permissionDecisionReason` 或 exit 2 + stderr；UserPromptSubmit/SessionStart 用 additionalContext 或純 stdout。
- [臨] VS Code 擴充套件把 systemMessage / deny reason / stderr 渲染成「<事件> says:」逐行顯示，純顯示層、無關閉設定（2026-10 查文件）。想「靜默但有效」→ 拿掉 systemMessage、只出 additionalContext。

## 行動

- 寫 hook 想讓模型看到文字 → 先確認事件支援的回饋欄位，不用 systemMessage。
- hook 提醒「看起來跳了但模型沒反應」→ 先查輸出欄位是不是 systemMessage。
