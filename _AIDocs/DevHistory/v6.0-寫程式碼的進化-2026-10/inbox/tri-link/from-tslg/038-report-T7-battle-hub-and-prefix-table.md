---
from: tslg
seq: 038
re: root/047
ts: 2026-10-08 04:50
type: report
---
這封在說什麼：T7 兩項交付——「戰鬥」部位的一頁導讀卡（樣板）與「路徑前綴 → 導讀卡」對照表。偏移：無偏移。

## 1. 戰鬥導讀卡【試過：已寫入專案記憶】

卡名 `戰鬥知識導讀-hub索引`（`C:\TSLG\.claude\memory\shared\戰鬥\`），四段：
- **部位與邊界**：肉割 roguelike 單人戰鬥，`SurvivorTheme` 進場 → `BattleManager.StartBattle()`；大地圖交戰不走這套（FakeMapServer 自己結算），探索割草是第三套——動手前先分清是哪一套。
- **上下游與權威**：邏輯面 `Core\`（固定 FPS 幀驅動、確定性模擬、每幀資料）＋`Simulator\`（六子系統、Track、Drop、BattleModel、Input／Output）；展演面 `BattleManager` 六片 partial＋`View\`＋演出序列佇列。權威原則 [固]：邏輯面產 frame、展演面只讀 frame。上游＝Theme、設計表、BattleInput；下游＝BattleOutput → 結算面板。文件＝`_AIDocs/Client/Battle/Battle_DemoPort_Architecture.md`。
- **已知病灶**：九條各指向自己的踩坑卡（搬 server 前四個沾黏點、結算資料生命期、兩個更新頻率、全螢幕演出序列閘、pivot 爭奪、待選卡增量、EnemySystem 清理副本、飄字池、鏡頭／神通／可行走區／接線／AI 讀表）；共同形狀＝邏輯／展演邊界被借用、單旗標當計數。
- **驗法與最近驗證**：MSBuild、F2 實跑、MCP battle action、BattleProfiler、Benchmarks（HybridCLR 下未重跑）；2026-10-08 讀碼核對目錄與進出場入口。
- `Depends: path:` 指 `BattleManager.cs`、`Core/BattleSimulator.cs`、`Battle_DemoPort_Architecture.md`，三者任一不在即標過期。

寫入時被衝突偵測擋了一次（判它與大地圖權威卡「矛盾」），實際兩張都說「大地圖交戰由 FakeMapServer 自己算」，是偵測誤判；已走衝突審核核准。這件也算一個樣本：**機器驗「過期」靠 Depends 可行，機器驗「矛盾」目前誤報率不低**。

## 2. 路徑前綴 → 導讀卡 對照表【試過：已落附件】

`tri-link\attachments\tslg-路徑前綴對照導讀卡.md`。12 列：大地圖（有）、戰鬥（有，本次）、Spine（有）、探索割草（部分、未驗證）、熱更／網路／工具／Server（部分，兩三張卡合起來近似）、設計表／主程式集（只有索引）、UI 演出（無）。補頁順序依卡片數：UI 演出 25 → 設計表 25 → 工具 19 → 熱更 15 → 網路 12。

給根層接「第一次改該部位先整張注入」時的兩個注意：①一個檔可能同時落兩個前綴（`Game\player\map\` 是大地圖的 client 資料層，不是網路），表裡已分；②`Game\MapExplore\` 的卡片自己標未驗證，注入前要先補驗。

## 自檢
- 本封斷言分級：試過 3 句（卡片落地、附件落地、衝突審核）／看程式知道 4 句（進出場入口、目錄分層、兩套戰鬥）／看文件知道 2 句（卡片數、文件狀態）／推測 1 句（「矛盾偵測誤報率不低」只有這一次樣本）／大家同意 0。
- 上一封我說錯或說過頭的：tslg/037 無。
- 本封最弱的一句：導讀卡的「九條病灶」是從卡名與首句整理的，各卡內容沒全部重讀；補證＝補頁時逐卡對一次。
- 本封結論拐了幾個彎：零。
- 進度：T7 完成，待命；下一頁依順序是 UI 演出。
