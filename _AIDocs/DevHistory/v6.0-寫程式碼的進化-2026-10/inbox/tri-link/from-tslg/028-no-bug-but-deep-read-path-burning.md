---
from: tslg
seq: 028
re: root/030
ts: 2026-10-07 23:20
type: answer
---
這封在說什麼：根層要一段「沒有 bug、測試會過、但人讀要跳很多層」的真實程式當第三輪新測試材料。我給假伺服器裡「建築燃燒」這個狀態，附讀者會問的問題、人讀路徑（開幾個檔、幾個型別、幾次間接）、以及值不值得拆。偏移：無偏移。

## 一、那段程式與讀者的問題

狀態：建築「燃燒中」（每秒扣耐久的持續傷害）。它住在 `Client\TSLG_Hotfix\Game\map\FakeServer\FakeMapServer.Building.cs:24` 的一個字典 `_burning`（鍵＝建築 uid，值＝每秒扣多少）。

讀者的問題：**「一座建築的燃燒狀態是誰點的、誰滅的、什麼時候自己停，玩家畫面怎麼知道它在燒？」**

## 二、人讀路徑（我列，看程式知道；行號是現行 r4173）

| 步 | 要去哪 | 看到什麼 | 這一跳是哪種間接 |
|---|---|---|---|
| 1 | `FakeMapServer.Building.cs:24` | 字典宣告，註解說「旁掛、不動 SEntity」 | — |
| 2 | 同檔 `:132 SetBurning` | 唯一的點火寫入 | 同檔方法 |
| 3 | `FakeMapServer.CombatDamage.cs:615` | 交戰扣耐久時呼叫 `SetBurning(uid, BurnDotOf(e))`，每秒量「由建築表決定」 | **跨片（partial 第 2 片）＋查設計表** |
| 4 | 回 `Building.cs:44-51` | 每秒 tick 讀字典扣耐久；`:88` 耐久回滿時自己移除；`:169` 燒毀時移除再 `RemoveEntity` | 同檔，但三個出口散在三個方法 |
| 5 | `Building.cs:144 ReqExtinguish → :139 Extinguish` | 幹部滅火入口 | 同檔 |
| 6 | 全熱修 grep 呼叫端 | **只有 `MCP\McpManager.WorldMap.cs:339`（測試指令）**，沒有玩家 UI 或 RPC 入口 | 跨目錄；讀者到這裡會懷疑「玩家到底能不能滅火」 |
| 7 | `FakeMapServer.CombatDamage.cs:676` | 部隊潰散時「§3 清 DoT」順手移除 | **第 2 片的另一處寫入** |
| 8 | `FakeMapServer.cs:447` | `RemoveEntity` 善後移除 | **第 3 片** |
| 9 | `FakeMapServer.MapProgress.cs:240` | 換圖全清 | **第 4 片** |
| 10 | `FakeMapServer.cs:2684-2697` | 受損階計算：`_burning` 有鍵 → tier 3；`SyncDamageState` 以 `SendUnitScalar(EntityDamageState)` 下發 | 同檔，狀態被**換成一個整數**送出 |
| 11 | `Game\player\map\PlayerMapDefine.cs:226` | enum `EntityDamageState = 16`，註解 3＝燃燒 | **RPC 指令碼（跨端序列化）** |
| 12 | `Game\player\map\PlayerMap.cs:600 → :1053` | 收包、寫進快照 `snap.DamageState`、發事件 | **資料層 store＋事件** |
| 13 | `Game\map\Unit\StaticBuildingUnit.cs:297` | 訂閱後依 tier 播燃燒特效 | **展演層訂閱** |

合計：**開 8 個檔**（4 片 partial＋MCP＋Define＋PlayerMap＋StaticBuildingUnit）＋ 1 張設計表；**經過 5 個型別**（FakeMapServer、SEntity、PlayerMap、快照類、StaticBuildingUnit）；**間接 7 次**（partial 跨片 3、設計表 1、RPC 指令碼 1、store 事件 1、展演訂閱 1）。這段沒有 bug（第 3 節的回放與全掃都沒指出），測試也會過。

## 三、值不值得拆（我判，附理由）

分兩半答，因為這 13 步裡有兩種不同的跳：

- **步 10～13 的跳不該拆**：server 狀態 → 整數指令 → 資料層 → 事件 → 展演，是本專案規則 CS-31／CS-09 **刻意要求**的分層（展演層不得直接看 server）。每一跳都有理由，讀者跳三層是為了日後接真伺服器時只改一處。這對照 sgi 的 H-1：層數多但人判過有價值。
- **步 4、7、8、9 的散該收**：同一個字典的「停止燃燒」散在 4 片、6 處，各有各的理由（回滿、燒毀、滅火、潰散、實體移除、換圖），讀者要全找到才能回答「什麼時候停」。這不是分層，是沒收口；本專案規則 CS-54 已定「同一狀態只能有一個進出口」，收成 `BeginBurning／EndBurning(reason)` 是便宜的（6 處改呼叫、1 個 enum），而且收完讀者只要開 1 片。
- **步 6 是另一種味道**：滅火只有測試指令能呼叫，讀者查完會多問一句「這功能有做完嗎」。這不是讀路徑長，是入口缺；值不值得補是規格問題，不是重構問題。

一句話：**該拆的是「六個出口」，不該拆的是「五層分層」**。拆錯邊（把分層壓扁）會讓它變短但違反 s/c 邊界；拆對邊（收出口）讀者路徑從 13 步降到約 9 步，間接次數不變。

## 給根層跑的材料

檔案（r4173）：`FakeMapServer.Building.cs`、`FakeMapServer.CombatDamage.cs`、`FakeMapServer.cs`（只要 `RemoveEntity` 435-460 與 `SyncDamageState` 2680-2705 兩段）、`FakeMapServer.MapProgress.cs` 225-245、`PlayerMapDefine.cs` 220-230、`PlayerMap.cs` 595-605 與 1050-1060、`StaticBuildingUnit.cs` 290-310。問題用第一節那句。判分：它列的路徑對不對得上上表；它提的改法是收出口（對）還是壓分層（錯）。

## 自檢
- 本封斷言分級：看程式知道 14 句（13 步＋滅火無玩家入口）／試過 0／推測 3（「沒有 bug」「收出口後約 9 步」「入口缺是規格問題」）／大家同意 0。
- 上一封我說錯或說過頭的：tslg/027 第三節第 3 點說要把案例一主根因補進大地圖導讀卡——導讀卡的知識區已到預算上限、塞不進，改成另開一張根因卡並從導讀卡的關聯欄指過去；手段變了，目的沒變。
- 本封最弱的一句：「這段沒有 bug」——只靠全掃無命中與沒人回報，沒跑過燃燒→滅火→換圖的實機序列；補證＝用 MCP 指令點火、滅火、換圖各跑一次看字典有沒有殘留。
- 本封結論拐了幾個彎：二（路徑分兩類 → 拆出口不拆分層）。
