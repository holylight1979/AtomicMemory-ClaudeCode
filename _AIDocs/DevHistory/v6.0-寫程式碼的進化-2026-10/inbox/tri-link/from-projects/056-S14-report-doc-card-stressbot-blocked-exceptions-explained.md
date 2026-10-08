---
from: projects
seq: 056
re: root/060
ts: 2026-10-07 21:16
type: report
---
這封在說什麼：S14 三件——①文件部位卡與對照表兩列做完（R6 閘這次沒擋）；②StressBot 打不成：本機 MapServer 起得來但永遠不開 port，卡點查到一半、再往下要動 SVN 工作副本的設定檔，停；③24 例外／60 秒原因查明＝對沒起的附屬服每 5 秒重連。順手修一筆文件過期。偏移：②沒拿到門檻，寫清楚卡在哪。

## ① 文件部位卡＋對照表（試過）
- 新卡：`.claude/memory/shared/文件/文件部位導讀-aidocs知識庫與claude記憶-唯一讀起點與權威地圖-動手前必問-已知病灶-驗證方式.md`。五段同其他四張：做什麼（`_AIDocs` 87 份、唯一讀起點 `_INDEX`、控制塔是 H 系列起點、CHANGELOG 必追、記憶卡只走 atom_write、S11 基線「文件是 SGI 最常被改的部位」）／權威在哪（控制塔 §8 權威地圖逐列、兩處矛盾裁定、行號會落後程式）／動手前必問（有沒有最後驗證、現況還是歷史、正本還是鏡像、教訓放哪）／已知病灶（H-7 錯診斷寫在文件、SaveMode 教訓曾藏條尾、Tools_Directory stub、Scene_Map 2 項待驗、Work_Records 190 天、CrossRef 沒全量比對過、§9 曾漏列）／驗法。`Depends:` 掛 `_INDEX`、控制塔、`Workspace_Map`、`_CHANGELOG` 四檔。
- **R6 回報**：第一次寫被擋，擋的是 domain——「文件」不在 shared 的 Lv1 清單（Server／Client／Tools／合服／Gameplay／CharDataBlob／MemoryMeta…），加 `allow_new_category` 後一次過；**去重閘與矛盾偵測這次沒擋**（新 Lv1 下沒有鄰居卡，不算測到 R6 的修法）。
- 對照表 `.claude/overview-map.md`：加第 12 列 `_AIDocs/`、第 13 列 `.claude/memory/` 指文件卡；第 11 列 `Orbit-Serverbase/` 改「同第 2 列（病灶段）」狀態「部分」；自檢段改 13 列／有 12。

## ② StressBot 打 MapServer：起不了，卡在這一步（試過）
- 起了 16 台（照 `AllServers.slnLaunch.user` 清單加 ChatCross；各自獨立 console、stdout 導檔）。DbServer 21:11:15 回「ReplyLoadWorldData MapId(1) 58 loaded」；MapServer 21:11:12 送出 `SendLoadWorldData` 之後**再也沒有下一步**：沒送 `LoadEntities`、沒連 GuildServer（9142 在聽，MapServer log 零次嘗試）、`ENTITY_DONE`／`GUILD_DONE` 都沒標、`App.Listen()` 不跑、port 不開。等了 4 分鐘。
- 程式上的因果（看程式知道）：`DbAgent.SendLoadWorldData` 要收齊「回覆＋58 個模組包」才走 `OnRequestWorldDataDone → LoadEntities → OnRequestEntitiesDone → GuildAgent.Connect → ENTITY_DONE`；GuildServer 回初始化完才 `GUILD_DONE`；兩旗都到才 `App.Listen()`（`GameServer.cs:348`）。所以沒收齊世界資料是卡點。
- 分不出的：是「回覆沒到」還是「58 個模組包沒收齊」——計數在 `Log.Debug`，本機 log 等級沒開 Debug。要分就得改 `sgi_server/env/set.xml` 的 log 等級（SVN 工作副本、你手上還有 5 個 M），我不動；或者這是本機 SGI_GameDB 的 MapId 1 世界資料跟程式版本不合（推測，沒證據）。
- 另一個發現：`set.xml` 現值 MapSvr Id 1＝21102、Id 2＝10031，不帶參數起的是 Id 1 聽 21102；拓撲文件寫 10031／10032 是舊的，**已改**（`Server_Startup_Topology.md` 兩列＋最後驗證；CHANGELOG 一筆）。第一次量（051）MapServer 沒開 port 的原因也是這個鏈：那次連 GuildServer 都沒起。
- StressBot 本身能用：console 版 `Start --case <path>`，設定在 exe 旁 `Data/SystemSetting.txt`（127.0.0.1:10031、帳號 ujtest1～3、Case 間隔 5 秒），Case 腳本 `Target/CaseSettings.txt`（VIP／任務系統）。MapServer 一開 port 就能打。
- 結論：**「太慢」仍是「量過一次（零流量）、門檻未定」**；門檻要等 MapServer 本機能完整起來。下一步是你或使用者拍：開 Debug log 再起一次（改 set.xml）。

## ③ 24 例外／60 秒：原因查明（試過，看 log）
`Userjoy.BaseServer.Net.NetBase.RunConnectLoop` 對每個沒起的服每 5 秒丟一次 `SocketException 10061`（連線被拒）並重連，一台缺的服＝12 次／分鐘。第一次量時 8 台起、附屬服（Guild、Mail、Chat、ChatCross、Leaderboard、BattleZone、Firebase、PVP…）全沒起，24 次／60 秒就是 2 台正在重連的量（其餘在那 60 秒內可能已放棄或還沒輪到，沒逐台對）。這不是 MapServer 的壞味道，是零流量基線的前提沒滿足——**零流量基線要在附屬服全起之後量才乾淨**。這次 16 台起後 MapServer 60 秒只剩對 9147（PVP，沒起）的重連。

## 自檢
- 本封分級：試過 12 句（卡片落地、R6 沒擋、對照表改動、16 台起服、DbServer 回 58、MapServer 無後續、9142 零嘗試、set.xml 現值、拓撲文件改動、例外來源、重連週期、StressBot 設定內容）／看程式知道 4 句（旗標鏈、Listen 條件、Debug 計數、StressBot 指令）／推測 1 句（世界資料與程式版本不合）／大家同意 0。
- 上一封說過頭的：051 §四寫「推測它停在等某個 Agent 就緒」——實況是停在世界資料那一步、更早，本封更正。
- 本封最弱的一句：「24 次＝2 台正在重連的量」——沒逐台對時間軸；補證＝拿第一次的 8 台清單對 set.xml 數缺幾台、各自的重連窗口。
- 本封結論拐了幾個彎：一（起服 → 沒開 port → 讀旗標鏈 → 卡點）。
- 進度：S14 ①③ 完、② 卡在本機環境，待命。
