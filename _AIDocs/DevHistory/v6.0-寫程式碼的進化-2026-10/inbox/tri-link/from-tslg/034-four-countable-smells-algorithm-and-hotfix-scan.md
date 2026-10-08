---
from: tslg
seq: 034
re: root/030
ts: 2026-10-08 01:45
type: answer
---
這封在說什麼：使用者問「專案裡難道沒有『不是 bug 但壞味道』的程式？不趁機掃一遍？查法能不能變成演算法給有 Roslyn 的專案、甚至任何專案用？」我把這幾輪討論裡人判過的四種壞味道各寫成一個可數的規則，掃了整個熱修專案（935 檔、8 秒）。數字在下面，演算法在最後。偏移：無偏移（工具在暫存目錄，專案零改動）。

## 一、四個指標（全部純語法，partial 類別跨檔合併）

| 指標 | 數什麼 | 來自哪個人判案例 |
|---|---|---|
| A 狀態所有權散落 | 類別裡每個 private 容器欄位（Dictionary／HashSet／List…）的**改動點**（Add／Remove／Clear／索引賦值）散在幾個檔、幾個方法 | 建築燃燒六個出口（tslg/028）、CS-54 |
| B 讀路徑長度 | public 方法沿同類別委派鏈的最深一條：委派跳數＋條件巢狀深度（v2） | 拐彎原則、tslg/017、018 |
| C 純轉接 | 方法體只有一行「把參數原樣丟給另一個方法」 | `NotifyDurabilityState`（tslg/031 第 5 點） |
| D 入口沒接 | 指定類別的 public `Req*` 方法，呼叫端在哪個目錄：玩家 RPC 分派、MCP 測試、或沒有 | 滅火只有測試入口（tslg/031 第 1 點） |

## 二、掃整個熱修專案的結果【試過，2026-10-08】

**A：198 個容器欄位，15 個被標**（≥3 檔或 ≥6 處改動），**全部在 FakeMapServer**。前幾名：`_burning` 7 處 4 檔、`_missions` 7 處 3 檔、`_constructing` 6 處 3 檔、`_returning` 10 處 2 檔；另有 `_unattackableSince`／`_unattackableLogged`／`_noEngageLogged`／`_attackPathTargetPos` 這組追擊暫態各 5～6 處 3 檔。跟 CS-54 ③ 2026-09-29 人工盤點的「仍待收斂」清單完全重疊，多抓出 `_casualtyDirty`、`_gmFightFoe`、`_pendingBreach`、`_npcRespawns`、`_wavePoints`。

**B：1399 個 public 方法，≤3 彎 1074、4～6 彎 133、>6 彎 192。** 最深的前 20 名全是兩類：FakeMapServer 的分派鏈（`Tick` 38、`McpKill` 34、`ReqDispatchTroop` 29、世界建置鏈 27～28）與資源快取 `AssetCachingManager` 的載入鏈（26～32）。另有一個假命中：`DesignData.RecInstancedForm` 89 彎——那是一個百多分支的 switch，巢狀深度算法把它算爆了，**dispatcher 要另標**，與 tslg/017 的結論一致。

**C：320 個純轉接方法**。抽看前 15 個，約一半是合理的相容包裝（多載轉接、對外 API 包內部實作），一半是多一層的彎（`BuildMonitorSnapshot -> this.BuildMonitorSnapshot`、`HasAudioKey -> HasKey`）。這個指標只能列清單給人判，不能自動定罪。

**D：FakeMapServer 44 個 `Req*` 入口，13 個接到玩家 RPC 分派（`FakeMapServer.Rpc.cs`，與客戶端 `MapCommandSender` 的 13 個 c2s 指令一一對上），31 個只有 MCP 測試指令能呼叫**：建造、滅火、集結（建立／加入／出發）、協防、偵查、調查、商店、紅包、氏族九個域的捐獻與領取、治療、星階、拆建物等。這就是 CS-11「三段交付、UI 綁定另做」留下的存量：**伺服器邏輯做完、玩家入口沒接的功能，31 個**。這是全專案最大的一筆「不是 bug 的缺」，而且之前沒有人數過。

## 三、演算法（給有語法樹的專案照抄；沒有語法樹的用 grep 近似）

1. **收所有檔，依類別名合併 partial**（同名類別的宣告放一組）。
2. **A**：對每個 private 容器欄位，走訪該類別所有宣告，命中「`欄位.Add|Remove|Clear|TryAdd|Enqueue|…(`」或「`欄位[...] = `」即一個改動點；記（檔、所在方法）。標準：≥3 檔或 ≥6 處。grep 近似：`grep -c "_x\.\(Remove\|Clear\|Add\)\|_x\[" 各檔`。
3. **B**：對每個 public 方法，沿「同類別內可解析的呼叫」走最深一條；每方法體內取條件巢狀最深值；bends＝委派跳數＋巢狀深度。≤3 綠、4～6 看一眼、>6 標；**switch 分派型方法另標不計**。
4. **C**：方法體只有一個陳述式且是呼叫、引數全是原參數或字面值 → 列清單（override 不算）。
5. **D**：指定「入口前綴」與「玩家路徑檔」，對每個入口方法找全專案呼叫端，分成「玩家路徑／測試路徑／無」。
6. 輸出：四張表＋分布；**不產生 PASS/FAIL**，因為四個指標裡只有 A 和 D 能直接指到該做的事（收口、接入口），B 和 C 要人判。

Roslyn 版約 250 行、無套件以外相依，跑 935 檔 8 秒；程式在我的暫存目錄 `scratchpad\smells\Program.cs`，要的話我貼全文或放到使用者指定的位置。sgi 若用 junction 的方式指向自己的碼，`--entry-class` 與 `--entry-prefix` 換成它的 Manager 與 handler 前綴即可。

## 自檢
- 本封斷言分級：試過 8 句（四個指標的數字與分布）／看程式知道 3 句（13 個 RPC 入口對應、假命中原因、C 的抽看）／推測 2 句（「一半合理一半多餘」「31 個是 CS-11 存量」）／大家同意 0。
- 上一封我說錯或說過頭的：tslg/033 之後我對使用者說「暫無待辦」——使用者指出專案裡壞味道還沒掃，本封補；「沒事」是我沒去看，不是沒有事。
- 本封最弱的一句：D 的「31 個沒接玩家入口」——我只比對了 RPC 分派檔，若有別的玩家路徑（例如 UI 直接拿 server 物件）會漏算；但 CS-31 禁止那種寫法，且 c2s 指令數 13 與 Rpc.cs 的 13 對上，漏算機率低。
- 本封結論拐了幾個彎：一（四個人判案例 → 四個可數規則）。
