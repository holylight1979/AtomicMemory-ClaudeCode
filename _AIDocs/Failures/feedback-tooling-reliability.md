# feedback-tooling-reliability

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex, codex companion, codex CLI, gpt-5, bg subprocess, DEVNULL, ready flag, subprocess Popen, MCP, 安裝 MCP, 安裝 skill, silent failure, probe burst, 規則唯一來源
- Created-at: 2026-05-26
- Related: feedback-completion-gates, feedback-memory-structure, feedback-workflow-discipline, atom-table-support

## 知識

- [臨] MCP / skill 全域裝到 ~/.claude/，避專案層重複
- [臨] bg subprocess stderr 必導檔（不 DEVNULL），ready flag 自寫；code review 見 DEVNULL 退件
- [臨] codex brief 5 要件：背景 / 問題 / 期望輸出 / 限制 / 驗證；三紅線禁贅字
- [臨] codex_companion.model 忝空，CLI 預設專手控版本
- [臨] silent-failure 調查前先 log 採樣 + probe burst (3 位點)，避推測
- [臨] 規則 / 驗證集中到唯一模組（如 lib/atom_spec.py），caller 端禁 patch 豁免

## 行動

- MCP/skill 全域裝
- bg stderr 導檔 + ready flag
- codex brief 5 要件
- silent-failure 先錄 probe burst
- 規則唯一來源集中
