# 專案等級 mcp/skill/hooks/log 不放全域根層

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 建立skill, 建立mcp, 新增hooks, 暫存檔, play-log, 全域 vs 專案, ~/.claude 根層, 專案自包含, skill 放哪, 檔案歸屬
- Created-at: 2026-06-12
- Related: decisions, realm-範疇分區機制-v5, preferences, auto-capture碎片sweep污染詞庫-defer根治

## 知識

- [臨] 專案等級使用的 MCP server / skill / hooks / play-log / 暫存截圖等,**不要寫進全域 `~/.claude/` 根層**,要放在該專案內並納入該專案版控(SGI 例:skill→`<proj>/.agents/skills/`、知識log→`<proj>/_AIDocs/`、暫存PNG→專案內並 gitignore)。
- [臨] 判準是「**專案特有 vs 跨專案通用**」,不是「在不在根層」本身:可重用≥2專案、系統規則、月級穩定 → 全域核心(`~/.claude/memory/`,如 dotnet-run 單檔 demo 這類通用工具技巧才留全域);單一 app/工具/環境特有 → 該專案內。
- [臨] 違反代價:污染全域、其他專案被迫載入無關內容、該專案無法自包含/版控。user 2026-06-12 明確要求並親自把 unity-mcp-skill、SGI play-log 從 `~/.claude/` 搬回 SGI 專案。

## 行動

- 建立任何 skill/mcp/hook/log/暫存檔前,先判該知識/工具是『專案特有』還是『跨專案通用』。
- 專案特有 → 放專案內對應位置;跨專案通用 → 才用 atom_write scope=global 或放 ~/.claude/memory/。
- 不確定歸屬時先問 user,不要預設塞全域。
