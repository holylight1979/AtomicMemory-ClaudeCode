# hook-py改動立即生效-每次呼叫起新進程-只有MCP-node進程需重啟

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: hook 生效, 下個 session 才生效, 新 session 才生效, hook 改動, PreToolUse 生效, Stop hook 生效, 重啟生效, MCP 重啟, reload window
- Created-at: 2026-09-04
- Related: 規則縫隙偏移-兩條各自合理的規則疊出第三種行為-syncreminder被local-commit靜音, 背景驗證未收就結束回合-stop閘裁判只看當下事證不看未來承諾

## 知識

- [臨] hooks/*.py（PreToolUse／Stop／SessionStart／UserPromptSubmit handlers）每次事件由 settings.json 指令起一個新 pythonw 進程跑 workflow-guardian.py，改完 .py 下一次事件就讀到新碼——實證 2026-09-04：pre_tool_use.py 補上口令閘後，同 session 下一條 Bash 指令即被新閘擋下。「hooks 改動要新 session 才生效」是錯的。
- [臨] 需要重啟的是常駐進程：MCP server（tools/workflow-guardian-mcp 的 node，改 server.js／lib/*.js／schema 要 reload window 或重啟 MCP）、vector service、statusline 常駐腳本。判準：看它是每事件起新進程還是常駐。
- [臨] 收尾報告不得把「hook 改動下個 session 才生效」當成免驗證的理由——改完 hook 可以當場用真事件驗（如故意下一條會命中閘的指令）。

## 行動

- 改 hooks/*.py 後：當場用會命中的真事件驗一次，不寫「下個 session 生效」
- 改 MCP node lib／schema 後：明寫需重啟 MCP（reload window）才 live
