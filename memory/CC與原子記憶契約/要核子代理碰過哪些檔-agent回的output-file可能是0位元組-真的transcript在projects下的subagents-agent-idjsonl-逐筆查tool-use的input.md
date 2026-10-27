# 要核子代理碰過哪些檔-agent回的output_file可能是0位元組-真的transcript在projects下的subagents-agent-id.jsonl-逐筆查tool_use的input

- Scope: global
- Author: holylight
- Source: track-rejudge 2026-10-23：核 Opus 判分子代理沒讀 Codex 判分表
- Confidence: [臨]
- Trigger: 子代理 transcript, subagent transcript, output_file 空, agent-<id>.jsonl, 核子代理讀了哪些檔, 判分者互相看不到
- Created-at: 2026-10-23

## 知識

- [臨] 要事後核實子代理做過什麼（例：兩位判分者互相看不到、子代理只寫了指定那一個檔）：Agent 工具回的 output_file 在 Windows 實測是 0 位元組，讀不到東西。真正的 transcript 在 ~/.claude/projects/<工作目錄 slug>/<主 session id>/subagents/agent-<agentId>.jsonl（旁邊有 .meta.json）。
- [臨] 查法：逐行 json.loads，取 message.content 裡 type=tool_use 的 name 與 input；搜 input 有沒有出現不准碰的檔名、列出 Write／Edit 的 file_path、message.model 看實際模型。只看 grep 命中的行，不要整檔讀進 context（檔可能幾 MB）。
- [臨] 判讀：命中不等於讀了——要看那筆是讀檔，還是在搜尋指令裡把檔排除（例 grep -v 判分-codex.md）。

## 行動

- 核子代理行為時，到 projects/<slug>/<session>/subagents/ 找 agent-<id>.jsonl，用腳本抽 tool_use 的 input，不要讀 output_file
