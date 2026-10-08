---
from: tslg
seq: 062
re: root/074
ts: 2026-10-09 11:40
type: report
---
這封在說什麼：T18 ①② 交付。①`C:\TSLG\.claude\overview-map.md` 已直接擴五欄（表頭＋全部 13 列補空欄，大地圖、戰鬥兩列填滿），每個路徑欄指到的檔都核過存在；②七張導讀卡（＋三張同部位相關卡）的 `Part:` 對照表在第二段。③Codex 審計畫第 2 版正在跑，另寄 063。偏移：表的路徑欄沿用表頭約定「相對 `Client\TSLG_Hotfix\`」，工具與文件用專案根相對路徑——兩種基準混在一列裡，根層 OverviewHub 若要機器核存在性得認這兩種（我在備註標了）。

## 一、擴欄後的兩列（試過；原表前四欄不動）
**大地圖**
- 病灶清單：`_AIDocs\Client\WorldMap\WorldMap_Verified_Defects_And_Fixes.md`（10 列：位置／症狀／根因／修法／狀態）
- 量尺：`MapTickPerf`（量法：Play Mode `GET /monitor/state` 的 `sources.MapTickPerf`，每幀 avg/P90/max＋allocKBPerSec＋tick 報表｜指令：`curl http://localhost:7898/monitor/state`｜門檻：P90>21.7ms 黃、>33ms 紅；單 stage>1.67ms/s；alloc>1MB/s（Editor 只當上限，實機再量）；程式 `Game\map\FakeServer\FakeMapServer.TickProfiler.cs`）
- 檢查器清單：`rule_check.exe selftest --root C:/TSLG`；smells v2（`dotnet run … Tools\CodeReview\smells`，entry FakeMapServer/Req）；熱修 MSBuild `-t:Rebuild -p:OutputPath=<暫存>\`
- 讀路徑樣本：`_AIDocs\Client\WorldMap\WorldMap_Knowledge_Map.md`（資料流圖＋燃燒狀態 13 步 8 檔）
- 第四問：「定位｜存法與訊號：這個數值有幾份存法（衍生 vs 直寫）？這個失敗有沒有原因訊號？」（根因層卡兩案同形）

**戰鬥**
- 病灶清單：（無固定格式表；候補 `.claude\memory\shared\戰鬥\battle-spec-backlog.md`，導讀卡病灶段 5 條各指子卡）——**這是戰鬥部位的缺口**：下一波「病灶正本在文件」第一個要補的就是戰鬥的缺陷表。
- 量尺：`BattleProfiler`（`Game\Battle\Profiler\BattleProfiler.cs`＋`BattleProfilerConfig.cs`，進 SurvivorTheme 後讀｜指令：MCP `do_action battle`（`MCP\McpManager.Battle.cs`）｜門檻：未定；`Benchmarks\` 九支 HybridCLR 下尚未重跑）
- 檢查器清單：同大地圖
- 讀路徑樣本：`_AIDocs\Client\Battle\Battle_DemoPort_Architecture.md`（三套戰鬥各走哪條、frame 通道）
- 第四問：「定位｜幀通道：改的是邏輯幀還是 render frame？展演面只讀 frame 沒回寫？」（arch-battle-frame通道原則）

驗收：10 個路徑欄引用的檔逐一 `test -f`：全在（TickProfiler.cs／BattleProfiler.cs／BattleProfilerConfig.cs／McpManager.Battle.cs／兩份 _AIDocs／battle-spec-backlog.md／rule_check.exe／smells.csproj／HotfixProj.csproj）。其餘 11 列五欄留空（表頭與分隔列已補，markdown 仍是合法表）。

## 二、`Part:` 對照（先不改卡，等根層欄位上了批次標）
| 卡 | Part（＝表「部位」欄文字） |
|---|---|
| 大地圖知識導讀-hub索引 | 大地圖 |
| 大地圖已知病灶根因層-野怪不掉血…兩案同形 | 大地圖 |
| mapexplore-gameplay-guide | 探索割草（另一玩法層） |
| 戰鬥知識導讀-hub索引 | 戰鬥 |
| ui演出知識導讀-hub索引 | UI 演出 |
| 設計表知識導讀-hub索引 | 設計表 |
| 工具mcp知識導讀-hub索引 | 工具 MCP |
| 熱更知識導讀-hub索引 | 熱更 |
| 網路登入知識導讀-hub索引 | 網路登入 |
| spine區導讀-單張圖到肢體式拍翅spine資產的知識地圖與閱讀序 | Spine |
- 一個要定的小事：表的第 2 列「部位」欄寫的是「大地圖（client 資料層與面板）」——若 `Part:` 值要跟「部位」欄逐字相等，這列會變成第二個部位名。建議該列「部位」改成「大地圖」、括號文字移到備註，讓一個部位一個值（表是專案的，你點頭我就改）。
- 其餘 ~280 張 shared 卡的 `Part:` 可由路徑前綴＋trigger 自動推（大地圖 80、戰鬥 22、UI 24、設計表 26…的範疇資料夾本身就是部位），人工只核推不出的。

## 自檢
- 本封分級：試過 4 句（擴欄、兩列、路徑逐一 test -f、表仍合法）／看程式知道 2 句（BattleProfiler／McpManager.Battle 位置）／推測 1 句（Part 可由資料夾自動推）／大家同意 0。
- 上一封說過頭的：061 無。
- 本封最弱的一句：「門檻：未定」那格——戰鬥量尺我沒跑過 BattleProfiler，只知道它在。
- 本封結論拐了幾個彎：零。
