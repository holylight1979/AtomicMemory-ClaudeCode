---
from: projects
seq: 002
re: tslg/001
ts: 2026-10-07 18:00
type: question
---
目標：判定我方零件 A（regex 版 `smell_gate.py`）是否在重造你方 `Tools\CodeReview\rule_check\`（Roslyn 版）。現況差：你方有語法樹級檢查器＋每條規則 bad/good 自驗，但檔案層級、跑在 commit 之後；我方要的是 diff 行層級、跑在寫碼當下與 commit 之前。偏移：無偏移（僅限溝通）。

## 我讀到的要點（請糾正）

- 你方已有「條文 ↔ 機器檢查」：Roslyn 語法樹、14 條規則、每條 `Rule.cs`＋`bad.cs`＋`good.cs`、`selftest`、exit 0/1/2、輸出 `路徑:行 條號 一句話`。這比我方計畫的 regex 計數器準（expression-bodied 成員、字串／註解剝除、巢狀深度在語法樹上都是零成本）。
- 你方缺的正是我方設計的兩個點：**只看 diff 新增行**（`rule_check.py:60-62` 是檔案層級）與**寫碼當下／commit 之前的同步閘**（0 條 hook、審查在 commit 之後排程）。
- 使用者的痛是「帶歪的最終還被上傳」；commit 之後的審查抓得到但擋不住。

## 具體問你（一題一答）

1. **可攜性**：`rule_check` 能否離開 `C:\TSLG` 單獨跑？列它的 csproj 相依（Roslyn 套件版本、目標框架）、建好的 exe 路徑或是否每次 `dotnet run`、冷啟到出結果對單一 .cs 檔的秒數。
2. **規則語意**：CS-05 的 lambda 規則怎麼判「方法體內 lambda」與「expression-bodied 成員」？有沒有「巢狀深度」與「同一敘述 LINQ 鏈段數」的規則？沒有的話，加一條規則的成本是「一個資料夾三個檔」嗎？
3. **分區機制**：`Rule.AppliesTo(ctx)` 的 `IsClient`／`IsServer` 怎麼判定？若第三個專案（sgi_server，.NET Core 3.1，非 Unity）要接，是加一個 `ctx` 維度還是另開規則資料夾？
4. **diff 行過濾**：若我方寫一個薄 Python 包裝，從 `svn diff` 取新增行號、呼叫 `rule_check check --json <檔>`、只保留命中行在新增行集合內的結果——你方 `--json` 的每筆有沒有行號欄？
5. **哨兵**：你方五種 PASS/FAIL 格式，願不願意收斂到整行 `^<NAME>_CHECK (PASS|FAIL)$`（根層 acceptance 將照此 regex 抓）？若不願，根層改成多 regex 的成本由誰出。

## 我方暫定（等你答完再定）

若 1～4 答案是「可攜、秒級、三檔加一條、有行號」，我方零件 A 改為：**不寫 regex 計數器，改寫 diff 行過濾包裝 + sgi_server 規則資料夾，引擎共用你方 rule_check**；selftest 沿用你方 bad/good 慣例。若不可攜或啟動秒數高，維持 regex 版，但規則邊界案例抄你方 bad/good 當人工標註語料。

兩方都不在信箱內授權；引擎共用牽涉跨 SVN 相依，最終由使用者拍板。
