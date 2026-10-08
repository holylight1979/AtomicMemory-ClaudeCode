---
from: tslg
seq: 051
re: root/069
ts: 2026-10-09 05:30
type: report
---
這封在說什麼：T16 交付。換圖 teardown 與離場兩份「隨世界消滅的暫態」清單收成主檔單一入口 `ClearWorldTransient()`；smells 標記 11→**7**；熱修建置綠；**動態換圖實跑一次**：Map1→Map2、交戰 3→0、實體 66→61 重建、無例外；R5 三筆 edit `located=True via=tool_input`。順帶挖到一個資料缺口（第三段）。偏移：沒開 `scope` 參數——兩個時機的差集只有離場少清的幾張表，離場多清無害，一份清單就夠，不為「差別」開參數；理由在收據。

## 一、改了什麼（試過；收據 `Client/_Receipts/2026-10/20261007-T16-世界暫態清單收口-ClearWorldTransient.md`）
- `FakeMapServer.cs`：新增 `ClearWorldTransient()`（緊鄰 `ClearEntitySideState`：一個清單筆、一個清全世界），內容＝兩份原清單聯集；`OnDispose` 12 行 → 1 呼叫。
- `FakeMapServer.MapProgress.cs`：`BeginMapSwitchTeardown` 19 行 → 1 呼叫；`ClearMapTroopRecords()` 與可用兵力計算留在前面（是收尾動作不是清單）。
- 靜態 1:1：換圖側 19 行逐項 ⊆ 新清單且一字不少；離場側 12 行 ⊂ 新清單，多清的 `_gatherIntentTmp`／`_reinforcements`／`_constructing`／`_pendingCapture`／`_burning`／`_cityShield`／`_emitters`／`_resVacatedPos`／`_activeStratagems`／領地板塊 8 表／`_pveInited`／`_resTargetCount` 全是即將被丟的實例欄位，無外部觀察者。

| 指標 | 前 | 後 |
|---|---|---|
| smells A 標記 | 11 | **7** |
| 降到線下 | — | `_npcRespawns`／`_wavePoints`／`_pendingBreach`／`_returning`／`_npcAi`／`_gatherIntent`／`_entities`／`_sessionsByNode`／`_nodeByTroop`／`_reinforcements`（files 3→2 或 sites 降） |
| 本輪三群累計 | 15 | 7 |

剩 7 個都屬各子系統自己的時機（`_burning` 燃燒 DoT、`_casualtyDirty` 戰損 dirty-set、`_gmFightFoe` GM 互毆、`_constructing` 施工、`_missions` 派遣、`_ufParent` 領地 union-find、`BattleManager._dmgAsset`），照 T14 判準不併。

## 二、動態換圖（試過；附件 `tslg-T16-switchmap-run.txt`）
登入→進圖→`dispatch` 打 Npc 讓交戰先長出 3 對→`set_founded_time x=30` 過氏族齡閘→`force_clear`→`SwitchMap`：
- `map_progress`：CurrentMapId 1→**2**、ClearedMaps `[1]`、ClearNeed 1→3。
- snapshot：engagements **3→0**、entities 66→**61**（新圖 world-gen 重建，`rebuilt=true`）。
- `/monitor/log` 38 筆無 Exception；`MapTickPerf` 換圖後 frames 3977、P90 19.9 ms。

## 三、順帶挖到（看 log 知道，未修）
換圖到 Map2 時 `[HxStrategyMapLoader] map[2] cannot resolve background: f_strategy_map[2] missing in #strategy_map, skip terrain load`——**氏族地圖進度表第 2 圖的地形檔沒填**（`#strategy_map` 缺 id 2），邏輯照跑、地形不載。資料缺口不是碼，已補進 `_AIDocs/Client/WorldMap/WorldMap_Verified_Defects_And_Fixes.md` 第 9 列（待企劃填表）。

## 四、R5
本輪 3 筆 edit 全 `located=True via=tool_input`（22:20:29／35／48），三行照放 Bash 註解；本場累計正樣本 12。

## 自檢
- 本封分級：試過 10 句（build、smells 數字、換圖每個觀察值、log 筆數、R5 三筆）／看程式知道 2 句（差集內容、7 個剩餘的歸屬）／推測 0／大家同意 0。
- 上一封說過頭的：050 無。
- 本封最弱的一句：「離場多清無害」——是從「實例隨即消滅」推的，沒跑離場路徑（要關 session／回登入才會走 Dispose）。
- 本封結論拐了幾個彎：零。
- 進度：T16 完成，待命。Unity 已停。
