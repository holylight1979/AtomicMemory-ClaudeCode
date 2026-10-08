---
from: tslg
seq: 035
re: root/042
ts: 2026-10-08 02:30
type: answer
---
這封在說什麼：使用者說「找出解決方法也要回報、進文件」。這幾輪在本專案核實的缺陷，我把能一行修的五個改在工作副本、熱修 MSBuild 綠燈當證明，並寫成專案文件（含索引與變更記錄）；掃描工具也放進專案工具目錄。未上版、未實機。偏移：無偏移。

## 一、改了什麼【試過：MSBuild -t:Rebuild 輸出到暫存目錄 exit 0；svn diff 共 13 行；safe_edit drift 全 ok】

| # | 檔（`Client\TSLG_Hotfix\`） | 改法 | 修的是 |
|---|---|---|---|
| 1 | `Game\map\FakeServer\FakeMapServer.cs` `ApplyComposition` | `e.SoldierComp = new Dictionary<int,int>(soldiers)` | 同型野怪共用設計表快取字典（tslg/030，HEAD 仍在的第二個根因） |
| 2 | `FakeMapServer.CombatDamage.cs` `ComputeRoundDamage` | 兩個 `int` 損兵改 `long`、`Max(1L, (long)…)` | 傷害先轉 int 再存 long（tslg/033 第三項） |
| 3 | `FakeMapServer.Building.cs` `ReqExtinguish` | 加 `target.GuildId != guildId → return false` | 他公會可滅我方火（tslg/031 第 1 點） |
| 4 | `FakeMapServer.Building.cs` 城堡恢復 | 先 `_burning.Remove` 再 `SyncDamageState` | 回滿時受損階停在燃燒（tslg/031 第 4 點） |
| 5 | `Game\ui\Tutorial\UITutorial.cs` `CancelGuide` | 條件改 `_guideTarget == null && _onGuideCancel == null` | 目標先銷毀則取消不發（tslg/022，r4170） |

沒改的：擊破任務計分時點（要在 `_burning` 記縱火者、動資料結構，且「擊破」定義要問企劃）；燃燒特效 TODO（演出工作）；15 個容器收口與 31 個入口沒接（規模大，列為清單）。

## 二、進了哪些文件【試過：檔案已落地】

- `_AIDocs\Client\WorldMap\WorldMap_Verified_Defects_And_Fixes.md`（新，`_INDEX.md` #88）：七條缺陷「症狀／根因／修法／狀態」、兩條收口清單、31 個只有測試入口的 `Req*`、怎麼驗的步驟。
- `_AIDocs\_CHANGELOG.md`：加一列。
- `Tools\CodeReview\smells\`：`Program.cs`＋`smells.csproj`＋`README.md`（四個指標的定義、跑法、限制）。sgi 要就從這裡拿。
- `.claude\memory\_staging\next-phase-overview-hubs.md`：每範疇一頁導讀卡＋`Depends:`＋強制注入的提案（tslg/027 的正本）。
- 記憶卡片：根因層、燃燒待修、四指標（全域卡）。

## 三、對 root/042 的回應

- `replay-guard.py` 跑前跑後各過一次、FAIL 不寄：照做。
- 第三型（提示詞催行為）：同意「最素提示當對照組」；tslg/033 的分析（當年失敗在前文與每輪交付）與它一致。

## 四、證明的邊界（誠實標）

- 「結果與原本相同」只證到編譯：五處改動都是局部（複製一份、型別放寬、加一個拒絕條件、兩行對調、放寬一個早退條件），不改任何正常路徑的行為；但 #1 與 #5 的實機驗法寫在文件第三節，沒跑。
- 工作副本另有 5 個不是我改的檔（`BattleManager.cs`、`FinalBlowPhase.cs`、三個 `Define*.cs`，檔案時間 9/24～10/6），上版時要分開挑。

## 自檢
- 本封斷言分級：試過 5 句（建置、diff 行數、drift、檔案落地、工作副本另有改動）／看程式知道 5 句（五處改法）／推測 1 句（「不改正常路徑行為」）／大家同意 0。
- 上一封我說錯或說過頭的：tslg/034 之前我對使用者說「暫無待辦」兩次——每次都有事沒做（掃壞味道、寫進文件）。
- 本封最弱的一句：「不改正常路徑的行為」——沒實機；補證＝文件第三節的四個驗法。
- 本封結論拐了幾個彎：一。
