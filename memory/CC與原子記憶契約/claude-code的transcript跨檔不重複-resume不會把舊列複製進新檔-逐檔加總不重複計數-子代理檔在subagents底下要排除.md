# claude-code的transcript跨檔不重複-resume不會把舊列複製進新檔-逐檔加總不重複計數-子代理檔在subagents底下要排除

- Scope: global
- Author: holylight
- Source: merge 4f3dc85a（注入噪音減量）2026-10-27
- Confidence: [臨]
- Trigger: transcript 加總, transcript 跨檔, resume 新檔, 重複計數, jsonl 統計, subagents 目錄, 對話紀錄統計, token 統計, 掃 projects 目錄
- Created-at: 2026-10-27
- Related: 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔

## 知識

- [臨]（實查本機）Claude Code 的 transcript 跨檔不重複：resume 不會把舊列複製進新檔（2,824 列跨檔重複 0），所以逐檔加總 token 或事件不會重複計數。
- [臨] 主 session 檔是 `~/.claude/projects/<專案>/<session>.jsonl`，子代理在 `<專案>/<session>/subagents/` 底下；從 projects/ 只取 `*/*.jsonl` 就不會混進子代理。

## 行動

- 統計多個 session 的 transcript：直接逐檔加總，不必去重 resume 接續的檔
- 只算主 session 就排除 subagents/ 底下的檔
