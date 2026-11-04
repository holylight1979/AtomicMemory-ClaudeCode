# 子代理預設背景跑時agent工具結果只有async-launched沒有內容-子代理產出改從subagentstop的last-assistant-message回填

- Scope: global
- Author: holylight
- Source: hooks/handlers/stop.py _fill_subagent_result、hooks/handlers/post_tool_use.py（規則 SUBAGENT_RESULT_FROM_SUBAGENT_STOP），2026-11-04
- Confidence: [臨]
- Trigger: async_launched, 背景子代理, 子代理結果歸因, SubagentStop, last_assistant_message, PostToolUse Agent, 子代理效用帳, 子代理沒有輸出
- Created-at: 2026-11-04
- Depends: path:~/.claude/hooks/handlers/stop.py

## 知識

- [臨] 子代理現在預設背景跑：派出時 PostToolUse(Agent) 的 tool_response 只有 status=async_launched、沒有 content，靠它取子代理產出會拿到空的；前景子代理的結果仍在 tool_response.content。
- [臨] 產出改從 SubagentStop 事件的 `last_assistant_message` 取：本系統在 `handlers/stop._fill_subagent_result` 依 agent_id 找注入紀錄最後一筆未結算的，填摘要（截 400 字）、status 改 completed、記收到結果的回合；效用歸因收到結果才結，還沒收尾的標 waiting、不標 no_output。

## 行動

- 要用子代理產出做歸因或稽核：接 SubagentStop 的 last_assistant_message，不靠 PostToolUse(Agent)
- 背景子代理還沒收尾就標 waiting，不判沒輸出
