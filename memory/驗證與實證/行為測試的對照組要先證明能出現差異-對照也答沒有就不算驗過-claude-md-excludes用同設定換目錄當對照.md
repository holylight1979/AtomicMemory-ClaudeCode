# 行為測試的對照組要先證明能出現差異-對照也答沒有就不算驗過-claude-md-excludes用同設定換目錄當對照

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 對照組, claudeMdExcludes, AGENTS.md, 無頭測試, setting-sources, 排除規則驗證
- Created-at: 2026-11-05
- Source: session:d164c54c#73e15770 2026-11-05
- Quote: 「收割後，可以關session囉?」

## 知識

- [臨] 驗 claudeMdExcludes 時，對照組用 --setting-sources project 連專案層 AGENTS.md 都不載入，實驗組和對照組都答沒有，分不出規則有無生效。改成設定相同、把帶記號的假目錄移出 Users/ 底下：上層 AGENTS.md 讀得到，才證明前一次沒讀到是規則造成。

## 行動

- 行為測試先看對照組有沒有出現預期差異，沒有就換對照，不報驗過
