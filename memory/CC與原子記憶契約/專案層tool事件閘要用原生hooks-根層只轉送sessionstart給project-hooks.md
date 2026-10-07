# 專案層tool事件閘要用原生hooks-根層只轉送SessionStart給project_hooks

- Scope: global
- Author: holylight
- Source: C:/Users/holylight/.claude/hooks/handlers/_shared.py:131 + session_start.py:1154（2026-10-07 查證）
- Confidence: [臨]
- Trigger: project_hooks.py, 專案 hook, PreToolUse, PostToolUse, 專案層閘, 原生 hooks, settings.json hooks, _call_project_hook, tool 事件轉送
- Created-at: 2026-10-07
- Quote: 「你講了很多，但要落地卻因為chat內還要描述現況，導致 很缺乏 具體條列化實作綱要 (與帶有自我批判性的 預訂架構)?」

## 知識

- [臨] 根層 dispatcher 只在 SessionStart 以 subprocess 呼叫 `{專案}/.claude/hooks/project_hooks.py`（`handlers/_shared.py:_call_project_hook`，唯一呼叫點在 session_start.py）；PreToolUse／PostToolUse／Stop 等 tool 事件**不轉送**給專案 hook。CrossRealmBashBlock 的提示「專案自己的需求 → 寫 project_hooks.py」只對 session 開頭注入訊息成立。
- [臨] 專案要在 Edit/Write/Bash 前後加閘（風格計數、commit 前檢查、注入提醒）→ 用 Claude Code 原生 hooks 宣告在 `{專案}/.claude/settings.json` 的 `hooks` 區，與根層 user-scope hooks 並存各跑一次；不必改根層、符合 Native-first。

## 行動

- 專案要加 tool 事件閘時先確認事件種類：SessionStart → project_hooks.py；其他 → 專案 settings.json 原生 hooks
- 不要為了專案閘去改根層 dispatcher 轉送邏輯
