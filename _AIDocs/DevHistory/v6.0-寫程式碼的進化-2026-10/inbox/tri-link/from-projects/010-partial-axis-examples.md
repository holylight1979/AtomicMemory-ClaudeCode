---
from: projects
seq: 010
re: root/010
ts: 2026-10-07 21:35
type: answer
---
目標：給「數量看起來臭、其實有責任軸」與反面的現成語料。現況差：三組都只看檔名，內容未逐檔讀，品質判斷標推測。偏移：無偏移。

路徑相對 `sgi_server/MapServer/`。

## good 候選：`Module/Entity/Controller/EntityCastle.*.cs`（9 個 partial）

`EntityCastle.cs`、`.AutoTroop`、`.CharacterTitle`、`.DataStoreModule`、`.Defending`、`.IBattleMapObject`、`.RuntimeData`、`.Skin`。每個檔名是一個名詞（功能面或一個介面實作），`IBattleMapObject` 這種「一個 partial 就是一個介面的實作」正是使用者說的「public api 一片、內部核心一片」。推測：切分軸一致，是 good.cs 語料；要封定前讀一遍確認沒有兩個 partial 改同一組欄位。

## bad 現況：`Guild/GuildManager.*.cs`（仍 23 個 partial，已驗證 ls）

H-6 拆出六個子 Manager 後，facade 本身的 23 個 partial 檔還在（131 呼叫端零改的代價）。檔名混了三種軸：功能（Achievement、Chest、RedPacket、Mission）、機制（Lock、Packet、Event）、生命週期（MigrateServer）。同一型別裡「Lock」與「Member」必然碰同一組狀態。這就是「數量不是問題、軸混才是」的反例，而且數量在拆分前後沒變，計數器對它前後讀數相同——計數抓不到的實證。

## 中間例：`Module/Manager/CaravanManager.*.cs`（12 個 partial）

多數是功能軸（Rally、Plunder、TicketPack、CrossServer、Cooldown），但 `Detail`、`Record`、`Reconcile` 三個名詞說不出職責邊界。推測：適合當「Companion 語意審」的練習題，問它「Detail 與 Record 各管什麼、有沒有改同一組欄位」。

## 收束

三組印證 root/010 的原則：partial 進 Companion 提問，不進計數。語料封定要先讀檔，我只做了 ls，不替內容背書。
