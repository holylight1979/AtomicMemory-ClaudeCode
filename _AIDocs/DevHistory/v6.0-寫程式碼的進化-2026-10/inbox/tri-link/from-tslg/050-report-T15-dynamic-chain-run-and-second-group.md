---
from: tslg
seq: 050
re: root/068
ts: 2026-10-09 04:40
type: report
---
這封在說什麼：T15 交付。①動態鏈實跑了兩輪（附件 `tslg-T15-dynamic-run1.txt`／`run2.txt`）：A 組（追擊／重導向／stop／再 attack）與 C 組（成戰後不再出未成戰告警）走通、無例外；**B 組「cannot be engaged」在這個 build 觸發不了**（原因在第二段，不是碼的問題，是 demo 旗標與地圖內容）。②第二群收口完成：`_attackPathTargetPos` 三個寫入點收成 `SetAttackPathTarget`，smells 標記 15→**11**。偏移：①的 B 路徑沒拿到「出聲一次→再出聲一次」的實測，只到靜態 1:1；寫清楚為什麼。

## 一、動態鏈實跑（試過；Unity 由我 GUI 點 Play 起、跑完點停；bin DLL 含 T14＋T15）
**run1**：登入→進圖→snapshot 65 實體（Castle 55／Npc 10／Troop 1）→ `dispatch` 5000 兵攻 BMCity_101（troop#1066）→ 25 秒 `cannot be engaged` 0 筆 → `stop` → 同隊 `attack` 再下 → 0 筆 → `return`；`dispatch` 攻 Npc#1056（troop#1067）→ 60 秒內 snapshot `engagements` 出現 `[1058,1067]`、1067 `engaged=true`，`ExplainNoEngagement` 告警 **0 筆**（C 組：成戰路徑乾淨）。
**run2**（換「返城中部隊」當打不動目標）：troop#1068 派出 12 秒後 `return`；troop#1069 攻 #1068 → 20 秒 0 筆；`stop`→`attack` 再下 → log：`目標實體不存在（已被移除？）` —— P 已返抵主城被移除；Q 在城下被守軍 #1056～1058 三支攔截成戰（`engagements` 三對）。
**對照口**：`MapTickPerf.tickReport` `AttackPursue 19.44ms x10578`（think 迴圈照跑）；兩輪 log 無 Exception；P90 22.1 ms、alloc 1.7 MB/s（與 T12 同量級）。

## 二、B 組為什麼觸發不了（看程式知道）
`Fightable()`＝可戰型別 ∧ 有戰力 ∧ ¬護巢無敵 ∧ ¬護盾 ∧ ¬返城中。這張圖：①`DemoDefine.DEMO_FORCE_ENABLE = true` → `ForceAttackable` 把**護盾與城池保護罩兩條全部短路**（`IsShielded`／`IsCityShielded` 恆 false）；②地圖 55 座城沒有一座是 `CityRole.BeastPrison`（名稱全 BMCity_1xx），本來就沒盾；③返城中部隊 12 秒就回到主城被 `RemoveEntity`，追擊方還沒進射程目標就沒了；④護巢無敵要等野怪被打到脫戰返點，攔截時序不可控。所以 B 組只能靠靜態 1:1（`HandleUnattackableTarget` 可攻擊分支{B}、`ClearAttackIntent`{A,B,C}、`ClearEntitySideState`{A,B,C} 集合不變）。要實測得關 `DEMO_FORCE_ENABLE` 或放一座 BeastPrison 進測試圖——兩者都動到 demo 旗標／地圖資料，我不擅自改。

## 三、②第二群：`_attackPathTargetPos`（試過；收據 `Client/_Receipts/2026-10/20261007-T15-攻擊路徑目標位置寫入收口-SetAttackPathTarget.md`）
- 同一張卡的 A 組、同清除時機（`ClearPursueTracking`）；差別是**寫入**散在三處（`Pursue.cs` 進射程重算與行軍中重導向、主檔 `SetAttackTarget`）。收成 `Pursue.cs` 內 `SetAttackPathTarget(troopId, targetPos)`，主檔改呼它。純搬移，值與時機不變（仍在 `SendPath` 成功後）。
- 改動點 5 處 3 檔 → 3 處 2 檔；smells A 標記 **15→11**（T14 12 → T15 11）；熱修 MSBuild 綠。
- 三行照放 Bash 註解；log 應有 4 筆 `located=True via=tool_input`（我沒再去數，你那邊看得到）。

## 四、剩下的 11 個標記怎麼分（給下一群挑）
同卡同時機可再收的：`_gmFightFoe`（GM 互毆配對，GmFight.cs 設／主檔 ClearEntitySideState 清／Combat 重置）。其餘屬別的卡：`_burning`／`_constructing`／`_pendingBreach`（建築／城池）、`_missions`／`_returning`／`_npcAi`／`_npcRespawns`／`_wavePoints`／`_gatherIntent`（各自子系統，MapProgress 換圖重置是共同散落源）、`_casualtyDirty`（戰損 dirty-set，4 個 Add 點）、`_ufParent`（領地 union-find）。共同形狀：**換圖重置（MapProgress.cs）＋離場清理（主檔）各抄一份**——下一群若要一次降最多，收的是「換圖重置清單」本身，不是單一容器。

## 自檢
- 本封分級：試過 12 句（兩輪每步、數字、smells、build）／看程式知道 4 句（Fightable 五條件、DEMO_FORCE_ENABLE、BeastPrison 來源、換圖重置形狀）／推測 1 句（「收換圖重置清單降最多」）／大家同意 0。
- 上一封說過頭的：049 寫「動態鏈你要我就跑」——應該直接跑，本封跑了。
- 本封最弱的一句：B 組「觸發不了」——四個原因都是讀碼推的，沒有一個是改旗標後反證過的。
- 本封結論拐了幾個彎：一（兩輪 0 筆 → 讀 Fightable 找原因）。
- 進度：T15 完成，待命。Unity 已停。
