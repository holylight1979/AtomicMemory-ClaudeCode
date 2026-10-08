---
from: tslg
seq: 049
re: root/066
ts: 2026-10-09 03:50
type: report
---
這封在說什麼：T14 交付。15 個散落容器收口第一群（攻擊相關 per-troop 暫態三表），副本上做、不上版、熱修 MSBuild 綠、smells 標記 15→12；**R5 正樣本拿到了**：5 筆 edit 全 `located=True`、`located_via=tool_input`（三行放在前一個 Bash 指令開頭的 `#` 註解）。偏移：挑的群不是「交戰結束善後」那三條移除路徑（那群已在 r1895 收成 `RemoveEngagement`／`EndEngagementSideEffects`，smells 沒標它），改挑 smells A 表實際標紅、同一張卡講的「追擊／打不動／未成戰三組暫態」。

## 一、改了什麼（試過；收據 `Client/_Receipts/2026-10/20261007-T14-攻擊暫態清理收口-ClearAttackTracking.md`）
- `FakeMapServer.Pursue.cs`：新增三個具名出口——`ClearUnattackable`（B 組：`_unattackableSince`＋`_unattackableLogged`）、`ClearNoEngageLogged`（C 組）、`ClearAttackTracking`＝`ClearPursueTracking`（A 組，既有）＋B＋C。`ClearAttackIntent` 改呼 `ClearAttackTracking`；`HandleUnattackableTarget` 目標恢復可攻擊分支改呼 `ClearUnattackable`；think 迴圈成戰／配對兩處改呼 `ClearNoEngageLogged`。
- `FakeMapServer.cs` `ClearEntitySideState`：四行收成一行 `ClearAttackTracking(uid)`。
- `ClearCombatTracking`（換圖／離場的整世界 `.Clear()`）不動——它本來就是單一出口。
- 刻意**沒有**把三組併成一張表：卡片說 A 每次 think 進射程即清、B 目標恢復可攻擊才清、C 成戰才清，三組只有「意圖沒了／實體沒了」兩個時機一起清；所以是三個出口的合成，不是合併。

| 容器 | 改動點前（sites／files） | 後 |
|---|---|---|
| `_unattackableSince` | 5／3 | 3／2 |
| `_unattackableLogged` | 5／3 | 3／2 |
| `_noEngageLogged` | 6／3 | 3／2 |
| smells A 標記總數 | 15 | **12** |

## 二、行為等價怎麼驗
- **靜態（試過）**：每個原呼叫點移除的表集合 ＝ 新出口的集合，1:1：`ClearAttackIntent`{A,B,C}、`ClearEntitySideState`{A,B,C}、可攻擊分支{B}、成戰／配對{C}；沒有多一次或少一次 Remove，條件與順序不動。
- **動態（寫法，沒實跑——Unity 已停、再拉一次鏈約 5 分鐘，你要我就跑）**：Play Mode `world_map dispatch` 一支部隊攻擊護盾中目標 → `[Combat] troop # target # cannot be engaged` 只出聲一次（B 去重仍在）→ `world_map stop` 再 `dispatch` 同目標 → 應再出聲一次（`ClearAttackIntent` 清了 B）；成戰後 `ExplainNoEngagement` 告警不再出（C 清在成戰）。對照口：`MapTickPerf.tickReport` 的 `AttackPursue` 列仍有次數＝think 迴圈照跑；`world_map snapshot` 交戰對數不變。

## 三、R5 正樣本（試過）
`_overview-hub.log` 本 session 這五筆：
```
22:01:09 FakeMapServer.Pursue.cs located=True via=tool_input reads=23
22:01:11 FakeMapServer.Pursue.cs located=True via=tool_input reads=23
22:01:14 FakeMapServer.Pursue.cs located=True via=tool_input reads=23
22:01:30 FakeMapServer.Pursue.cs located=True via=tool_input reads=23
22:01:34 FakeMapServer.cs       located=True via=tool_input reads=23
```
做法：Edit 之前那一個 Bash 指令開頭放三行 `# 定位｜部位：…／# 定位｜根因層：…／# 定位｜前例：…`，再執行真的讀檔。對照同 session 21:27 那筆（TickStageNames 修法，三行只在回覆文字）`located=False via=None`——同一個人、同一條管線，差別只在放哪。你 066 說「只在單元測試證過」的 `tool_input` 管道，這是第一筆真實 log。

## 四、順手
- 三行放 Bash 註解這招已 append 進全域 atom（transcript 掉字那張）。
- 本輪沒寫新卡，R6 去重／矛盾閘沒有新樣本。

## 自檢
- 本封分級：試過 9 句（build、smells 數字、三表前後、log 五筆、1:1 對照）／看程式知道 2 句（A/B/C 時機、r1895 已收口）／推測 0／大家同意 0。
- 上一封說過頭的：048 無。
- 本封最弱的一句：「行為等價」只做了靜態 1:1，動態沒跑——補證就是第二段那條鏈。
- 本封結論拐了幾個彎：零。
- 進度：T14 完成，待命。
