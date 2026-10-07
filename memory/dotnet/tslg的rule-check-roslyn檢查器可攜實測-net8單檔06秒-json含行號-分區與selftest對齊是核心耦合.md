# tslg的rule-check-roslyn檢查器可攜實測-net8單檔0.6秒-json含行號-分區與selftest對齊是核心耦合

- Scope: global
- Author: holylight
- Source: 專案 .claude/inbox/tri-link/from-tslg/001～004（2026-10-07）
- Confidence: [臨]
- Trigger: rule_check, Roslyn, 異味檢查, C# lint, 寫碼守門, smell_gate, 語法樹規則, bad.cs, good.cs, AnonymousFunction, 引擎共用, TSLG CodeReview
- Created-at: 2026-10-07
- Quote: 「開一個跨session溝通的 inbox monitor.. 我想讓你與根層 直接溝通 看看，那個session也在討論類似的議題，只是 你的似乎更接地氣 (?)。 好了以後給我 prompt 讓我去在根層的CC貼上；僅限 先溝通。」

## 知識

- [臨]（2026-10-07 TSLG session 實測）TSLG 工作區的 `CodeReview\rule_check\`（其工具資料夾下）是 Roslyn 語法樹的 C# 規則檢查器：net8.0、唯一套件 `Microsoft.CodeAnalysis.CSharp 4.1.0`；冷建 15s；單檔 1400～3000 行 0.5～0.6s；`check --root <repo> --json <檔>` 每筆有 `rule_id/severity/file_path/line_number(1-based)/title`，同規則同檔同行去重一筆。規則一資料夾三檔 `Rule.cs`+`bad.cs`+`good.cs`，反射掃 `IRule` 免註冊；CS-05 用 `AnonymousFunctionExpressionSyntax` 抓 lambda 與匿名 delegate，expression-bodied 成員天然不命中。
- [臨] 借引擎到其他 C# 專案的唯一核心耦合：分區是 `Core\RuleContext.cs` 四個路徑前綴常數，`Core\Selftest.cs` 虛擬路徑寫死熱修分區（只認 IsServer 的規則 selftest 會 0 命中判 FAIL），`Core\RepoInfo.Locate` 探 `CLAUDE.md + Client\`（`--root` 繞過）；路徑型規則 CR-020/CR-022/CS-06 讀 TSLG 實體，不需要就刪資料夾。selftest 與 `_AIDocs/Rules/*.md` 雙向對齊把工具健康綁在文件健康上：TSLG 本機 selftest 因 checklist 檔不在 HEAD 而 FAIL。
- [臨]（2026-10-08 另一專案實跑）零改碼套到別的 C# 專案：建 junction 根 `X\Server`→目標 repo、`X\Client\TSLG_Hotfix`→同一 repo，`--root X` 後 RelPath 前綴就命中 `IsServer`／`IsHotfix`（lambda 規則 CS-05 只套熱修分區，要數 lambda 走 hotfix junction）。別機實測：冷建 10s、單檔 2836 行 0.5s、29 檔一次 1.0s；Server 分區只有 CS-44／CS-53 有命中，CS-06 路徑型每檔固定 1 筆要剔。「只看新增行」對拆分型重構會把搬家的舊碼當新碼（H-6 搬移行 79.7%），解耦型則幾乎沒有（H-3 0.4%）。

## 行動

- 要在 C# 專案做程式化異味閘，先借這支引擎加薄包裝（diff 行號過濾），不寫 regex 計數器
- 借用時先把分區前綴與 selftest 虛擬路徑參數化，對齊對象換成自己的條文檔或先關
