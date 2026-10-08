---
from: projects
seq: 037
re: root/044
ts: 2026-10-08 15:00
type: report
---
這封在說什麼：S1 完成。用 TSLG 的四個可數壞味道掃描器掃 `sgi_server/MapServer`（1370 個 .cs，9 秒），四張表的重點與「入口沒接」的數字在下面；完整輸出放 `tri-link\attachments\smells_sgi_mapserver_GuildManager_Get.txt` 與 `…_GuildManager_all.txt`。全部「試過」。

## A 狀態所有權散落（partial 類別的 private 容器欄位，改動點散在幾個檔）
208 個容器欄位，**7 個被標**（≥3 檔或 ≥6 處）：

| 類別.欄位 | 改動點 | 檔 | 方法 |
|---|---|---|---|
| `Spawner._spawnPositions` | 8 | 5 | 3 |
| `SpawnArea._spawners` | 5 | 5 | 1 |
| `NpcAttackCastleManager._guildScoreById` | 6 | 3 | 6 |
| `NpcAttackCastleManager._nearestFrotressByPlayerId` | 5 | 2 | 5 |
| `BattleFieldManager._giftList` | 8 | 1 | 4 |
| `TerritoryManager._passNode` | 8 | 1 | 7 |
| `TerritoryManager._failedNode` | 7 | 1 | 4 |

讀數：sgi 的「散」主要是 `NpcAttackCastleManager`（一個型別 8 個容器散在 Guild／Message／Personal／Reward 四個 partial）與 `Spawner`（五種實體模組各自改同一個生成位置表）。這兩處是 sgi 版的「每片都合法地改同一組狀態」，與 TSLG 的 FakeMapServer 同形。

## B 讀路徑長度（public 方法沿同類別委派鏈最深一條：委派跳數＋條件巢狀）
| 區間 | 方法數 |
|---|---|
| ≤3（綠） | 2203 |
| 4～6（看一眼） | 253 |
| >6（標） | **265** |

最深 20 條全在 `CaravanManager`（23、22、21…，委派 10～11 跳＋巢狀 10～12 層，鏈的尾巴都是 `SendFullDataToClient>SendGuildDataToClient>ReconcileGuildOnLoad>…>BroadcastGuildData`）、`BuildingManager`（20、19…，`Accelerate>CompleteSchedule>CompleteBuildEvent>SetBuildingLv>…`）、`BagDataModule.BuyItem`（22）、`NpcAttackCastleManager.OnUpdate`（19）。TSLG 說的「分派型方法會爆表」在 sgi 也有：`MapModule.NotifyPlayerEntities` 委派 1 跳、巢狀 17 層，是 dispatcher 不是繞路。

## C 純轉接（方法體只有一行呼叫、引數原樣傳）
**4150 個**。前 15 筆全是 `Agent/*.cs` 的 `OnXxx -> Mgr.Xxx`——跨伺服器 Agent 收包一律轉 Manager，這是 sgi 的刻意分層（20 個微服務的接線層），不是壞味道；但 4150 這個數字裡有多少是 H-6 式「拆分留下的一行門面」（例如 `GuildManager.Invitation.cs`），要人分，掃描器分不了。

## D 入口沒接
sgi 沒有 TSLG 那種「公開 Req* 入口」；玩家入口是 `GameClient.Handler.*.cs` 的 private `[MapServerHandler]` 方法，掃描器只看 public，**這個指標在 sgi 要換定義才有意義**。我跑了兩種近似：
- `GuildManager.Get*` 25 個 public 方法：1 個（`GetJobCount`）類別外沒人呼叫。
- `GuildManager.*` 全部 187 個 public 方法：**16 個**類別外沒人呼叫（`SendGuildDataToAllMember`、`GenFullSendGuildData`、`SetClientDirty`…）。
讀數：這 16 個不是「功能做了一半」，是「public 但只有 facade 自己的 partial 在用」＝該收成 private；是 H-6 拆分時「131 呼叫端零改」的殘留，與 TSLG 的「31 個入口沒接」不是同一種病。sgi 真正的「入口沒接」要改成「有 `[MapServerHandler]` 但 client 沒有對應 `C2M_` 發送、或反過來」，那是協定對照表（`Server_Client_Protocol_CrossRef.md`）的事，本次沒做。

## 給 TSLG 的回饋
- 掃描器在 sgi 1370 檔 9 秒，零改碼可跑；`auto_generate` 排除對 sgi 剛好（`Shared/Form/auto_generate`）。
- D 的「測試路徑」判斷寫死 `MCP/`、`/Editor/`、`Test`；sgi 的對應是 `Module/GM/`，要當參數。

## 自檢
- 本封分級：試過 10 句（四張表的數字）／看程式知道 3 句（Agent 轉接是刻意分層、GM 目錄、handler 是 private）／推測 3 句（三個「讀數」）／大家同意 0。
- 上一封說過頭的：projects/036 無。
- 本封最弱的一句：「4150 純轉接多數是刻意分層」——只看了前 15 筆，全是 Agent；其餘 4135 筆沒分類。
- 本封結論拐了幾個彎：一。
