# 04 Client/Server 架構與網路通訊的壞味道

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 視角：多人線上遊戲，C# 伺服器 + Unity 用戶端。也適用一般有「用戶端 ↔ 伺服器 ↔ 資料庫」的連線服務。
> 讀法：每條固定六欄（定義／辨識訊號／為何有害／解法／何時不算／來源）。「來源」只列實際打開或檢索驗證過的網址；標「業界經驗」表示沒找到能直接引用的權威專文，內容來自通行實務，引用時請降低權重。
> 名詞白話：
> - authoritative（權威）＝「最後說了算的那一方」。
> - tick＝伺服器固定頻率跑一次的遊戲更新，例如每秒 20 次。
> - RTT＝一來一回的網路延遲。
> - idempotent（冪等）＝做一次跟做很多次結果一樣。
> - race condition（競態條件）＝結果取決於誰先跑到的錯誤。
> - dupe（刷物）＝利用漏洞複製道具或金錢。

---

## 這個切面的分類架構

```
Client/Server 壞味道
├─ A. 信任邊界（Trust Boundary）……… 用戶端講的話有沒有被當成事實？（外掛、刷物的頭號來源）
├─ B. 協定設計（Protocol Design）……… 訊息怎麼切、怎麼編碼、怎麼演進而不互相弄壞
├─ C. 狀態同步（State Synchronization）… 兩端看到的世界怎麼對齊、誰為準、時間怎麼算
├─ D. 可靠性（Reliability）…………… 網路一定會慢、會斷、會重送；程式有沒有預設這件事
├─ E. 伺服器並行與資源隔離（Server Concurrency）… tick、執行緒、鎖、actor、單一熱點拖垮全服
├─ F. 資料存取（Data Access / Persistence）…… DB、快取、存檔的寫法造成的卡頓與回檔
├─ G. 用戶端結構（Unity Client）……… 主執行緒、UI 與網路耦合、全域管理器、事件亂飛
└─ H. 可觀測性（Observability）………… 出事時查不查得到、能不能重現
```

各類的事故型態（排查優先序由高到低）：

| 類別 | 典型事故 | 處理優先序 |
|---|---|---|
| A 信任邊界、E9 先查後改、D4 非冪等重試 | 外掛、刷物、重複扣款，經濟崩壞後往往只能全服回檔 | 最高：直接造成金錢損失 |
| C 狀態同步、D 可靠性 | 拉回（rubber-banding）、斷線即輸、資料對不上 | 高 |
| E 並行、F 資料存取 | 全服卡頓、死結、存檔遺失或回檔 | 高：通常要等負載上來才爆 |
| B 協定設計 | 版本錯配崩潰、頻寬爆、維護成本高 | 中：屬於技術債 |
| G 用戶端結構 | 掉幀、改不動、重連後殘留舊狀態 | 中 |
| H 可觀測性 | 上述事故都查不出原因 | 中，但會放大其他類的代價 |

### 條目索引

| 代號 | 名稱 | 代號 | 名稱 |
|---|---|---|---|
| A1 | Client-Authoritative State 信任用戶端數值 | E1 | Shared Mutable State 跨執行緒共享可變狀態 |
| A2 | Missing Server-Side Validation 伺服器不驗證輸入 | E2 | Game Logic on I/O Thread 邏輯跑在 I/O 執行緒 |
| A3 | Business Logic in Client 商業邏輯放用戶端 | E3 | Global Lock 全域大鎖 |
| A4 | Client-Side Permission Filtering 靠用戶端過濾權限 | E4 | Inconsistent Lock Ordering 鎖順序不一致 |
| A5 | Client-Enforced Limits 冷卻/次數只在用戶端擋 | E5 | Blocking I/O in Tick tick 內做阻塞 I/O |
| B1 | Chatty Interface 聊天式介面 | E6 | Sync-over-Async 同步等待非同步 |
| B2 | Chunky Packet / Extraneous Fetching 過胖封包 | E7 | Per-Tick Allocation tick 內大量配置 |
| B3 | N+1 Requests N+1 請求 | E8 | Actor Model Bypass 繞過 actor 模型 |
| B4 | Unversioned Protocol 協定無版本號 | E9 | Non-Atomic Check-Then-Act 先查後改非原子 |
| B5 | Backward-Incompatible Serialization 序列化不相容 | E10 | Busy Front End 前端忙碌 |
| B6 | Ordinal Leakage enum/序號直接上線 | E11 | Noisy Neighbor 吵鬧鄰居 |
| B7 | Handler Boilerplate Hell 封包處理樣板地獄 | F1 | SQL in Game Logic 邏輯中直接寫 SQL |
| B8 | Giant Opcode Switch opcode 大 switch | F2 | Whole-Blob Save 整包 blob 存檔 |
| B9 | Duplicated Message Definitions 訊息多處定義 | F3 | Sync DB Write Blocking Player 同步寫 DB |
| C1 | Dual Source of Truth 雙存 | F4 | Cache-DB Inconsistency 快取與 DB 不一致 |
| C2 | No Authoritative Source 沒有權威來源 | F5 | Shared Persistence 多服務共用 DB |
| C3 | Drift Without Reconciliation 漂移且不和解 | F6 | ORM N+1 Query |
| C4 | Full-State Sync 全量代替差量 | F7 | Monolithic Persistence 單一儲存放所有資料 |
| C5 | No Sequence/Ack 沒有序號與確認 | F8 | No Caching 不快取 |
| C6 | Arrival-Order Dependence 依賴到達順序 | F9 | Busy Database 忙碌資料庫 |
| C7 | Client Clock as Time Source 用用戶端時鐘 | F10 | Improper Instantiation 不當實例化 |
| D1 | Missing Timeout 沒有逾時 | G1 | Network Callback Mutates UI 網路回呼直接改 UI |
| D2 | Unbounded Retry 無上限重試 | G2 | Network/Parsing on Main Thread 主執行緒做網路與解析 |
| D3 | Retry Storm / Reconnect Herd 重試風暴/重連雪崩 | G3 | Business Rules in UI UI 層含業務規則 |
| D4 | Non-Idempotent Retry 非冪等操作被重試 | G4 | Manager Spider Web 全域管理器蛛網 |
| D5 | No Reconnect/Resume 沒有斷線重連 | G5 | Event Bus Abuse 事件總線濫用 |
| D6 | Undetected Half-Open Connection 半開連線 | H1 | Silent Failure 失敗靜默 |
| D7 | Session Bound to Connection session 綁連線 | H2 | No Correlation ID 沒有關聯 ID |
|  |  | H3 | Unreproducible Packet Flow 無法重現的封包流 |

---

## A. 信任邊界（Trust Boundary）

### Client-Authoritative State（信任用戶端數值／用戶端權威）〔A1〕
- 定義：伺服器直接採用用戶端回報的「結果」，例如位置、血量、傷害、冷卻是否結束、掉了什麼寶，而不是自己算。
- 辨識訊號：
  - 封包欄位寫的是結果而不是意圖，例如 `ReportDamage(dmg)`、`MoveTo(x,y,z)`、`PickLoot(itemId, count)`、`SkillReady = true`。
  - 伺服器 handler 只做 `player.X = msg.X` 這類賦值，找不到對應的重算、上限或距離檢查。
  - 可數指標：handler 中「把 msg 欄位直接寫進權威狀態」的行數，大於 0 就要逐條檢視。
- 為何有害：改過的用戶端（記憶體修改器、封包重放、改 DLL）可以宣稱任何結果。Gambetta 舉的例子是被改的用戶端宣稱自己有 10000% 血量，或從 (10,10) 直接跳到 (20,10)。Fiedler 也說，如果玩家能直接告訴伺服器自己的位置，就 "trivially easy to hack"。落到遊戲裡就是瞬移、穿牆、無敵、秒殺、無冷卻、自訂掉落，然後外掛橫行、經濟崩潰。
- 解法：用戶端只送「意圖／輸入」（我要往右走、我要對目標 X 放技能 Y），伺服器依自己的狀態模擬、裁決，再回傳結果。手感靠用戶端預測（client-side prediction），但結果以伺服器為準（見 C3）。
  ```csharp
  // 壞：相信用戶端算好的傷害
  void OnAttack(AttackMsg m) => target.Hp -= m.Damage;

  // 好：用戶端只說「打誰、用哪招」，冷卻／資源／距離／傷害都由伺服器判
  void OnAttack(AttackIntent m) {
      if (!skills.TryGet(m.SkillId, out var skill) || !caster.CanCast(skill, serverNow)) return;
      if (!world.TryGet(m.TargetId, out var target) || !InRange(caster, target, skill.Range)) return;
      target.Hp -= DamageFormula.Calc(caster, target, skill);
  }
  ```
- 何時不算：
  - 純表現層、不影響他人與經濟的狀態，例如鏡頭、本地特效、UI 排序。
  - 單機或合作遊戲，沒有排行榜也沒有交易，作弊只影響自己，刻意拿這點換伺服器成本。
  - 有完整的伺服器端事後驗證（例如重播驗證），這時伺服器實質上仍是權威。
- 來源：https://www.gabrielgambetta.com/client-server-game-architecture.html ；https://gafferongames.com/post/what_every_programmer_needs_to_know_about_game_networking/ ；CWE-602 https://cwe.mitre.org/data/definitions/602.html

### Missing Server-Side Input Validation（伺服器不驗證輸入／封包沒做邊界檢查）〔A2〕
- 定義：伺服器把收到的位元組直接當合法資料用，不檢查長度、範圍、索引、數量正負、字串長度。
- 辨識訊號：
  - 反序列化後直接寫 `array[msg.Index]`、`for (i < msg.Count)`、`new byte[msg.Len]`。
  - 用 `MemoryMarshal.Read<T>` 或 memcpy 把封包直接蓋到 struct 上。
  - 數量欄位用 `int` 卻沒擋負數。
  - 沒有單包大小上限。
- 為何有害：
  - Fiedler 原話："It's a massive security risk to take data coming in over the network and trust it."
  - 若陣列只有 32 格，攻擊者送 33～63（6 bit 內合法）就會越界；沒檢查的 count 會造成緩衝區溢位或無窮迴圈。
  - 在遊戲裡：一個人送畸形封包就能打掛整個服；負數數量讓商店或交易反向加錢（刷錢）；超長字串耗盡記憶體與頻寬。
- 解法：
  - 在序列化層「自動」做範圍檢查：每個欄位宣告 [min, max]，超出就整包丟棄並記錄。Fiedler 強調這不該是手動步驟。
  - 限制單包大小與單連線速率。
  - 業務層再做語意檢查：數量大於 0 且不超過背包上限、目標存在且在視野內。
  - 對應 Azure 的 Gatekeeper pattern：在信任邊界前集中驗證、清洗請求。
- 何時不算：同一信任域內、雙方都由你部署的內部 RPC 可以只做 schema 驗證，但仍要防版本不一致造成的錯資料（B4）。
- 來源：https://gafferongames.com/post/reading_and_writing_packets/ ；https://gafferongames.com/post/serialization_strategies/ ；https://cwe.mitre.org/data/definitions/602.html ；https://learn.microsoft.com/en-us/azure/architecture/patterns/gatekeeper

### Business Logic in Client（商業邏輯放在用戶端）〔A3〕
- 定義：掉落機率、合成成功率、商店價格與折扣、任務完成判定、獎勵數量由用戶端計算，伺服器只負責記帳。
- 辨識訊號：
  - Unity 端用 `Random.Range` 決定掉落，再送 `ClaimReward(itemId)`。
  - 價格表只存在用戶端的 ScriptableObject，伺服器收的是 `Buy(itemId, price)`。
  - `CompleteQuest(questId)` 在伺服器端沒有條件檢查。
- 為何有害：
  - OWASP WSTG-BUSL-02 直接拿遊戲當例子：攻擊者利用隱藏或開發用欄位，"quickly get to the highest levels... accumulate unearned points"。
  - CWE-602 收錄的實例 CVE-2024-50653：電商只在前端限制折價券，伺服器沒檢查。
  - 在遊戲裡：自訂掉落、0 元購、跳關刷獎勵。規則改版還得發新版用戶端，熱修困難。
- 解法：規則與機率表放伺服器。用戶端只拿顯示用副本，可由伺服器下發。請求只帶識別碼，價格與結果由伺服器查表決定。
- 何時不算：純顯示的預估（例如「預計獲得」）且伺服器不採信；離線單機模式。
- 來源：https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/02-Test_Ability_to_Forge_Requests ；https://cwe.mitre.org/data/definitions/602.html

### Client-Side Permission Filtering（靠用戶端過濾權限）〔A4〕
- 定義：權限只靠介面隱藏，例如 GM 按鈕不顯示、debug 封包只是用戶端不送、公會管理只有會長看得到，但伺服器 handler 對任何人都開放。
- 辨識訊號：
  - 伺服器 handler 沒有 `if (!session.HasRole(...))`。
  - 權限判斷只出現在 Unity UI 的 `SetActive(isAdmin)`。
  - 正式版伺服器仍註冊 debug 或 cheat 用的 opcode。
- 為何有害：
  - CWE-602 的示範：用戶端先驗證身分再送指令，伺服器之後不再驗證，攻擊者拿掉驗證步驟就能直接執行特權指令。
  - WSTG-BUSL-02 提到 debug 功能洩漏其他玩家與寶藏的位置。
  - 在遊戲裡：一般玩家能發 GM 指令刷物、踢人、改公告。
- 解法：每個 handler 都在伺服器端授權，最好集中在 dispatcher 或 filter（見 B7）。正式版不註冊 debug opcode。權限資料只信伺服器 session。
- 何時不算：UI 隱藏本身沒錯，可以減少誤操作，前提是伺服器也有檢查。
- 來源：https://cwe.mitre.org/data/definitions/602.html （相關：CWE-603 Use of Client-Side Authentication）；https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/02-Test_Ability_to_Forge_Requests

### Client-Enforced Limits（冷卻、次數、頻率只在用戶端擋）〔A5〕
- 定義：技能冷卻、每日次數、獎勵只能領一次、聊天頻率等限制只寫在用戶端。
- 辨識訊號：伺服器沒有每個玩家的冷卻時間戳或計數器；`lastCastTime` 只在 Unity 端；伺服器沒有任何 rate limiter。
- 為何有害：WSTG-BUSL-05 指出，有次數上限的功能必須由應用程式硬性控制，因為使用者每用一次就拿一次好處。在遊戲裡就是無冷卻連發、每日獎勵重複領，聊天或交易請求灌爆伺服器（同時也是 DoS，阻斷服務攻擊）。
- 解法：伺服器以伺服器時間記錄每次使用並檢查。次數類用 DB 唯一約束或原子遞增（見 E9）。連線層加 rate limit（Azure Rate Limiting／Throttling pattern）。
- 何時不算：用戶端的冷卻 UI 仍需要（顧手感），只要伺服器重複檢查。
- 來源：https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/05-Test_Number_of_Times_a_Function_Can_Be_Used_Limits ；https://learn.microsoft.com/en-us/azure/architecture/patterns/rate-limiting-pattern ；https://learn.microsoft.com/en-us/azure/architecture/patterns/throttling

---

## B. 協定設計（Protocol Design）

### Chatty Interface / Chatty I/O（聊天式介面：多次小往返）〔B1〕
- 定義：一個邏輯操作被拆成很多次小請求來回。
- 辨識訊號：
  - 開一個畫面要發 5 個以上請求，而且後一個等前一個回應（串行 await）。
  - 每個屬性一個 opcode，例如 `GetName`、`GetLevel`、`GetGold`。
  - Azure 列的症狀：同一應用對同一服務或資料庫發出大量小請求；服務變成卡在 I/O 等待（I/O-bound）。
- 為何有害：
  - 每次往返都付一次 RTT，串行 N 次就是 N 倍的開畫面延遲；伺服器處理每包的固定成本（解包、驗證、排程）也乘上 N。
  - Fowler：跨行程呼叫比行程內呼叫貴 "orders of magnitude"。
  - Azure 的實測：一個操作打 45 次 SELECT，改成單一查詢後吞吐從 410 提升到 3,970 req/min。
- 解法：
  - Remote Facade（遠端外觀），也就是粗粒度（coarse-grained）API：一個畫面一個請求，或伺服器主動推送整理好的狀態。
  - 批次請求；Gateway Aggregation。
- 何時不算：
  - 本來就該小而頻繁的獨立訊息，例如每 tick 一包移動輸入。
  - Azure 也提醒：若用戶端常常只需要某個欄位，拆開提供是合理的。別矯枉過正成 B2。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/ ；https://martinfowler.com/eaaCatalog/remoteFacade.html ；https://learn.microsoft.com/en-us/azure/architecture/patterns/gateway-aggregation

### Chunky / Bloated Packet & Extraneous Fetching（過胖封包／多撈資料）〔B2〕
- 定義：矯正 B1 過頭，每次都送一整包，例如整個背包、整個角色、整個公會成員表，或單包大到會被 IP 分片。
- 辨識訊號：
  - UDP 單包超過約 1200 bytes。
  - 只改一個欄位也送整個物件。
  - 登入時一次下發所有系統的資料。
  - 從 DB 撈出的資料量遠大於回給用戶端的量（Azure 範例：80,503 bytes 對 19,855 bytes）。
- 為何有害：
  - UDP 封包被 IP 分片時，任何一片遺失就整包遺失。Fiedler 的算例：1% 丟包率、256 片，整包遺失率高達 92.4%。
  - 浪費頻寬、行動流量與伺服器序列化 CPU。
  - 在 TCP 上，大包會造成 head-of-line blocking（前面的包沒到，後面的全部排隊等），延遲敏感的訊息跟著卡。
- 解法：
  - 只送有變動的部分（delta，見 C4）、分頁、依畫面需要才載入。
  - UDP 包維持在 1200 bytes 以內；大資料走專門的可靠傳輸。
  - DB 端用投影（Select）只取需要的欄位。
- 何時不算：低頻、需要原子一致的快照可以是大包，但要走可靠通道。例如進場初始化、重連後的一次全量同步。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/extraneous-fetching/ ；https://gafferongames.com/post/packet_fragmentation_and_reassembly/ ；https://gafferongames.com/post/client_server_connection/

### N+1 Requests（N+1 請求）〔B3〕
- 定義：先拿一份清單（1 次），再對清單每一項各發一次請求（N 次）。
- 辨識訊號：
  - `foreach (id in friendIds) await GetProfile(id)`。
  - 拿到排行榜 ID 後逐個查名字與頭像。
  - 伺服器 log 中，同一連線在 1 秒內打同一 opcode N 次。
- 為何有害：請求數隨資料量線性成長。測試帳號 5 個好友沒事，上線後 500 個好友就卡死。如果伺服器每次又打 DB，就和 F6（ORM N+1）疊加。
- 解法：提供批次 API，例如 `GetProfiles(ids[])`；清單回應直接附上顯示需要的欄位；伺服器端用 IN 查詢或快取。
- 何時不算：N 有硬性小上限（例如隊伍最多 4 人），而且不在熱路徑上。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/ （N+1 段）；https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying

### Unversioned Protocol（協定沒有版本號）〔B4〕
- 定義：連線握手時不交換協定識別與版本，兩端只是「剛好一致」才能運作。
- 辨識訊號：
  - 握手封包沒有 version 或 protocolId 欄位。
  - 改封包格式時必須所有端同時更新。
  - 舊用戶端連上新伺服器時出現亂碼、崩潰或錯值，而不是清楚的「請更新」。
- 為何有害：灰度發布、熱更、商店審核延遲，都會讓新舊用戶端一定並存。沒有版本號時，錯配只會在解析失敗或資料錯亂時才浮現，變成難診斷的崩潰，錯資料甚至寫進 DB。Azure 把「Component versioning is simple」列為分散式系統的錯誤假設之一。
- 解法：
  - 握手第一包帶 protocol id 與版本。Fiedler 的做法是 protocol id 加 CRC32 校驗，並在封包中段與結尾放 serialize check 抓錯位與截斷。
  - 伺服器明確拒絕不支援的版本，回傳可讀的錯誤。
  - 訂出支援的版本範圍。
- 何時不算：兩端綁同一 build 發布且強制更新的情況。但握手檢查成本極低，仍建議做。
- 來源：https://gafferongames.com/post/serialization_strategies/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/

### Backward-Incompatible Serialization（序列化格式不向後相容）〔B5〕
- 定義：改訊息結構的方式，讓舊資料或舊版對端無法正確解讀。常見做法：改欄位型別、重用已刪欄位的編號、改預設值、把 repeated 改成單值、新增 required 欄位。
- 辨識訊號：
  - `.proto` 或 MessagePack 定義的 diff 裡，同一個 tag 換了名字或型別。
  - 刪欄位時沒有 `reserved`。
  - `[Key(3)]` 被挪給新欄位。
- 為何有害：Protobuf 官方："Never re-use a tag number. It messes up deserialization." 舊用戶端、舊存檔、log 裡的舊封包會被解成錯的值，結果是數值錯亂、存檔損毀、回檔。
- 解法：
  - 只增不改。刪欄位就 reserve 編號。新欄位設為 optional 並給合理預設。
  - MessagePack-CSharp 的 IntKey 不重用 index；官方建議保留過時成員（標 Obsolete），直到所有用戶端都更新。
  - CI 加 schema 相容性檢查。
- 何時不算：只活在單一行程記憶體裡、不落地也不跨版本的訊息。
- 來源：https://protobuf.dev/best-practices/dos-donts/ ；https://github.com/MessagePack-CSharp/MessagePack-CSharp

### Ordinal Leakage（enum／欄位序號直接上線）〔B6〕
- 定義：把語言內部的「位置」當成線上格式，例如 C# enum 的整數值、欄位宣告順序、陣列索引、IntKey 序號，而且沒有明確固定它們。
- 辨識訊號：
  - enum 沒有顯式給值（`enum ItemType { Sword, Shield, Potion }`），卻被序列化成 int。
  - 有人在 enum 中間插入新成員。
  - 依宣告順序寫欄位的序列化器。
  - enum 的 0 是有業務意義的值。
- 為何有害：在 enum 中間插一個值，後面所有值都位移，舊用戶端或舊存檔會把「藥水」讀成「盾」。0 有語意時，「沒設定」與「設為 0」分不出來，未初始化的封包可能被當成合法指令。
- 解法：enum 顯式給值、只增不改。第一個值保留為 `Unspecified = 0`（protobuf 建議）。刪掉的值要 reserve。長期存放或跨語言的資料，考慮用字串鍵或正式 schema。
  ```csharp
  public enum ItemType : int { Unspecified = 0, Sword = 1, Shield = 2, Potion = 3 } // 顯式給值，新值只往後加
  ```
- 何時不算：只在行程內使用、從不序列化的 enum。
- 來源：https://protobuf.dev/best-practices/dos-donts/ （Include an Unspecified Value；Reserve Numbers for Deleted Enum Values）；https://github.com/MessagePack-CSharp/MessagePack-CSharp

### Packet Handler Boilerplate Hell（封包處理器樣板地獄）〔B7〕
- 定義：每個 handler 各自重複「解包 → 驗證 session 與權限 → 驗證欄位 → try/catch → 記 log → 組回應」，這些橫切關注點（cross-cutting concerns，指每個功能都需要的共通處理）散落在數百個 handler 裡。
- 辨識訊號：
  - 各 handler 的前 10 行幾乎一模一樣。
  - 新 handler 是複製舊的改出來的。
  - 某些 handler 漏了權限檢查或 try/catch，是 A4 與 H1 的溫床。
  - 改一條驗證規則要動 N 個檔。
- 為何有害：漏一個就多一個漏洞（權限、速率、錯誤處理）；各 handler 行為不一致讓事故難查；新人會複製到過時的樣板。
- 解法：
  - 把共通流程收進 dispatcher pipeline、middleware 或 filter。ASP.NET Core SignalR 的 hub filter 就是這個概念：在 hub 方法前後執行共同邏輯，例如 logging、驗證、授權。
  - handler 只寫業務邏輯；權限與速率用屬性宣告。
- 何時不算：只有少數幾個 handler 的小專案；或某個 handler 的流程確實不同。
- 來源：https://learn.microsoft.com/en-us/aspnet/core/signalr/hub-filters ；業界經驗（遊戲自製封包框架）

### Giant Opcode Switch（opcode 大 switch）〔B8〕
- 定義：所有訊息分派寫在一個巨大的 `switch (opcode)`，每個 case 裡直接放業務程式碼。
- 辨識訊號：單一方法數百到上千行；新增訊息都要改這個檔，成為合併衝突熱點；case 裡直接寫邏輯，而不是呼叫 handler。
- 為何有害：refactoring.guru 指出 switch 邏輯會分散，新增條件要改多處。在遊戲裡，所有系統耦合在同一檔，改動風險高，也無法依 opcode 套用共通 pipeline（又回到 B7）。
- 解法：用 dispatch table，例如 `Dictionary<opcode, handler>` 或 source generator 產生的表；handler 自己註冊；opcode 與訊息型別一對一。
  ```csharp
  static readonly Dictionary<ushort, Func<Session, ReadOnlyMemory<byte>, ValueTask>> Handlers = new() {
      [Op.Move]   = MoveHandler.Handle,
      [Op.Attack] = AttackHandler.Handle,
  };
  if (!Handlers.TryGetValue(op, out var h)) { log.LogWarning("unknown op {Op} from {Player}", op, s.PlayerId); s.Kick(); return; }
  await h(s, payload);
  ```
- 何時不算：switch 每個 case 只有一行「opcode → handler」分派，而且由產生器維護。refactoring.guru 也說 switch 只做簡單動作時不必處理。
- 來源：https://refactoring.guru/smells/switch-statements ；業界經驗

### Duplicated Message Definitions（同一訊息多處定義）〔B9〕
- 定義：同一個封包格式在用戶端（Unity）與伺服器（C#）各手寫一份；或同一端的 Read 與 Write 各寫一份。
- 辨識訊號：
  - `Assets/Scripts/Net/Packets.cs` 與 `Server/Protocol/Packets.cs` 內容相似但不同步。
  - bug 史裡有「兩邊欄位順序不一致」。
  - `Write()` 與 `Read()` 分開手寫。
- 為何有害：兩份一定會漂移，一邊加了欄位另一邊沒加，結果是解析錯位、數值錯亂、只在某些版本組合才崩潰。讀寫不對稱也一樣。Fiedler 用單一 serialize 函式同時產生讀寫，就是為了消除兩條路徑不同步的風險。
- 解法：
  - schema 只有單一來源（single source of truth），由產生器或共用組件提供兩端程式碼。可以是 `.proto`，也可以是共用的 C# 專案或介面；MagicOnion 就是把 C# interface 當 schema，在 Unity 與伺服器間共用，不需要 `.proto`。
  - 讀寫用同一個函式。
- 何時不算：刻意的防腐層（anti-corruption layer），例如用戶端的 view model 與網路 DTO 分開。前提是網路 DTO 本身只有單一來源。
- 來源：https://gafferongames.com/post/serialization_strategies/ ；https://github.com/Cysharp/MagicOnion

---

## C. 狀態同步（State Synchronization）

### Dual Source of Truth（雙存：同一份資料兩個可寫來源）〔C1〕
- 定義：同一個事實存在兩處，而且兩處都會被寫入。例如：
  - 金幣同時在遊戲服記憶體與 DB，兩邊都會被改。
  - 背包被用戶端本地快取與伺服器同時修改。
  - 兩個服務各自保存玩家等級。
- 辨識訊號：
  - 同一欄位有兩條以上寫入路徑。
  - 出現「同步」「校正」「以哪邊為準」的排程或註解。
  - 客服常收到「數值對不起來」。
- 為何有害：兩份必然分歧，何時分歧取決於時序，所以問題間歇出現又難重現。修復時常以一份覆蓋另一份，結果不是回檔就是刷物。
- 解法：每份資料指定唯一的權威擁有者（owner），其他地方只能是可失效的快取。快取用 cache-aside：寫入權威來源後讓快取失效。跨服務的資料走 API，不直接共用。
- 何時不算：明確標成唯讀快取、有失效策略、可容忍過期的資料，例如排行榜顯示、商城列表。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside ；https://microservices.io/patterns/data/shared-database.html ；業界經驗

### No Authoritative Source（沒有權威來源）〔C2〕
- 定義：多個參與者都能宣告狀態，沒有任何一方的裁決是最終的。典型例子是 P2P 沒有主機裁決，或用戶端互相廣播狀態、伺服器只負責轉發。
- 辨識訊號：伺服器只做 relay（轉發），自己不持有遊戲狀態；兩人同時撿同一件裝備時沒有固定的裁決者；不同用戶端看到不同結果。
- 為何有害：Fiedler 指出，讓玩家自己告訴伺服器位置就 "trivially easy to hack"，而且衝突無從裁決：兩人都撿到（刷物），或雙方都認為自己贏。
- 解法：伺服器權威。Fiedler 引用 Tim Sweeney 的話："The Server Is The Man"。用戶端是 Gambetta 說的 "privileged spectators"（有特權的觀眾），再加上預測。
- 何時不算：確定性鎖步（deterministic lockstep）的 RTS。各端從同一初始狀態套用同一串輸入，得到相同結果，權威是「輸入序列」本身；但作弊與不同步偵測要另外處理。
- 來源：https://gafferongames.com/post/what_every_programmer_needs_to_know_about_game_networking/ ；https://www.gabrielgambetta.com/client-server-game-architecture.html

### State Drift Without Reconciliation（狀態漂移且沒有和解機制）〔C3〕
- 定義：用戶端做了預測或本地模擬，但收到伺服器的權威狀態時沒有正確和解（reconciliation）。結果是兩端長期不一致，或修正時畫面劇烈跳動。
- 辨識訊號：
  - 輸入封包沒有序號。
  - 收到伺服器位置時直接覆蓋，造成拉回（rubber-banding）；或完全忽略，造成漂移。
  - 兩端對浮點數的量化方式不一致。
- 為何有害：Gambetta 描述沒有和解時，角色會先往左跳一格再往右跳一格。長期漂移會造成命中判定爭議，或用戶端以為有的道具伺服器沒有。
- 解法：
  - 輸入帶序號；伺服器回傳「最後處理到的輸入序號」加權威狀態；用戶端以權威狀態為基準，重播還沒被確認的輸入。
  - 兩端都對量化後的同一個值做模擬，Fiedler 稱為 bilateral quantization。
- 何時不算：不做預測的回合制或慢節奏遊戲，直接顯示伺服器結果即可。
- 來源：https://www.gabrielgambetta.com/client-side-prediction-server-reconciliation.html ；https://gafferongames.com/post/state_synchronization/

### Full-State Sync Instead of Delta（以全量同步代替差量）〔C4〕
- 定義：每次更新都送整個世界或整個物件的完整狀態。
- 辨識訊號：同步頻寬隨實體數成長且恆定，就算世界靜止也一樣；每 tick 序列化所有實體；協定裡沒有 baseline 或 ack 概念。
- 為何有害：Fiedler 的例子：901 個方塊、60Hz 未壓縮快照需要 17.37 Mbps，經差量壓縮等技巧降到約 256 kbps。全量同步會讓頻寬爆掉、行動網路卡頓、伺服器 CPU 被序列化吃光，可承載人數下降。
- 解法：
  - 以對方「已確認收到」的快照為基準（baseline）送差量。Source 引擎只在開局或嚴重丟包時才送全量。
  - 搭配優先級：Fiedler 的 priority accumulator 每次只送最重要的物件。
  - 只送玩家附近的物件：興趣管理（AOI，area of interest），屬業界經驗。
- 何時不算：狀態本身很小或更新很低頻（例如回合制每回合一次）；重連時送一次全量是正確做法。
- 來源：https://gafferongames.com/post/snapshot_compression/ ；https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking （原頁回 403，內容經搜尋摘要確認）；https://gafferongames.com/post/state_synchronization/

### No Sequence / Ack（沒有序號與確認機制）〔C5〕
- 定義：訊息沒有序號，接收端無法判斷遺失、重複、亂序；傳送端也不知道對方收到了哪些。
- 辨識訊號：
  - UDP 協定的封包頭沒有 sequence 或 ack 欄位。
  - 應用層請求沒有 request id，回應對不上請求。
  - 序號比較只寫 `a > b`，沒處理回繞（wrap-around）。
- 為何有害：
  - 不知道 baseline 就做不了差量；過期訊息丟不掉。
  - 重複封包會被重複執行（D4）。
  - 回繞處理錯，長時間連線後協定會「突然壞掉」。
- 解法：每包帶遞增序號、ack 與 ack bitfield（Fiedler 的設計一包可以確認 33 包）；比較序號時處理回繞；請求與回應帶 request id。
  ```csharp
  // Fiedler 的 16-bit 序號比較：處理回繞
  static bool SeqGreater(ushort s1, ushort s2) =>
      (s1 > s2 && s1 - s2 <= 32768) || (s1 < s2 && s2 - s1 > 32768);
  ```
- 何時不算：
  - 純請求-回應，而且 RPC 框架已處理對應（例如 SignalR 的 invocation id）。
  - 單一 TCP 連線保證順序且不重複；但跨重連不保證。
- 來源：https://gafferongames.com/post/reliability_ordering_and_congestion_avoidance_over_udp/ ；https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking （每包附 ack 號，經搜尋摘要確認）

### Arrival-Order Dependence（依賴到達順序）〔C6〕
- 定義：程式假設訊息會照送出順序到達並被處理，但底層並不保證。不保證順序的情況包括 UDP、多條連線、多台伺服器、多個 consumer、async handler 併行。
- 辨識訊號：
  - 隱含「先收到 A 才會收到 B」的假設，例如先 `EquipItem` 再 `UseSkill`。
  - 同一玩家的請求被丟進 thread pool 併行處理。
  - 跨服訊息經 MQ 由多個 consumer 處理。
  - 重連後，舊連線遲到的封包仍被處理。
- 為何有害：偶爾發生的順序顛倒會造成間歇性錯誤狀態，例如裝備沒生效、扣款晚於發貨才失敗，這是最難重現的一類 bug。Azure Service Bus 在多個 consumer 競爭消費時不保證處理順序。
- 解法：
  - 需要順序的訊息帶序號或版本，接收端拒收過期（stale）訊息。
  - 同一實體（玩家、房間）的訊息串行處理：actor 或單執行緒佇列；Azure 的 Sequential Convoy pattern 或 Service Bus sessions。
  - 把狀態轉移設計成冪等：訊息攜帶絕對值，而不是增量。
- 何時不算：
  - 順序無關的訊息。
  - 底層真的保證順序（單一 TCP 連線、單執行緒處理），而且你沒有在後段破壞它。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/patterns/sequential-convoy ；https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer （Account for message ordering）；https://gafferongames.com/post/reliability_ordering_and_congestion_avoidance_over_udp/

### Client Clock as Time Source（用用戶端時鐘當時間來源）〔C7〕
- 定義：冷卻、buff 到期、移動距離（速度 × 時間）、每日重置、拍賣截止等，用用戶端送來的時間戳或用戶端本機時間計算。
- 辨識訊號：
  - 封包帶 `clientTime`，伺服器直接拿來計算。
  - Unity 端用 `DateTime.Now` 判斷每日重置。
  - 伺服器沒有檢查用戶端時間與伺服器時間的累計差。
- 為何有害：加速器（speed hack）或改系統時間，就能移動超速、縮短冷卻、重複領每日獎勵。Unreal 的 CharacterMovementComponent 專門內建「時間差異偵測」：比較 ServerMove 回報的時間差與伺服器實際經過的時間，用來抓 speed hack，並讓用戶端「還債」（之後的移動幾乎不給時間）。
- 解法：
  - 伺服器時間是唯一權威。
  - 用戶端時間只用於排序與插值，而且伺服器要設累計誤差上限。
  - 每日重置等以伺服器時間計算。
- 何時不算：
  - 純表現用途，例如動畫插值、本地 UI 倒數（倒數以伺服器下發的到期時間為準）。
  - 延遲補償（lag compensation）：伺服器會回溯到用戶端開槍時看到的時間點（Gambetta），屬合理參考用戶端時間；但伺服器必須限制可回溯的範圍（業界經驗）。
- 來源：https://docs.unrealengine.com/4.26/en-US/API/Runtime/Engine/GameFramework/UCharacterMovementComponent/OnTimeDiscrepanc-/index.html ；https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FNetworkPredictionData_Server_Ch- ；https://www.gabrielgambetta.com/lag-compensation.html

---

## D. 可靠性（Reliability）

### Missing Timeout（沒有逾時）〔D1〕
- 定義：網路呼叫、DB 查詢、跨服 RPC、等待對方回應，都沒有時間上限。
- 辨識訊號：
  - `await SendAsync(...)` 沒傳 CancellationToken。
  - `HttpClient.Timeout = Infinite`。
  - 交易的雙方確認流程沒有期限。
  - 可能死結的地方用 `Monitor.Enter`，而不是 `TryEnter(timeout)`。
- 為何有害：AWS 指出，等待中的呼叫一直佔著資源。下游一慢，上游的執行緒、連線、記憶體都被拖住，進而連鎖崩潰。在遊戲裡就是交易視窗卡住、玩家停在「處理中」、連線槽被佔滿。WSTG-BUSL-04 也建議交易在指定時間後取消或重置（以票券保留為例）。
- 解法：
  - 所有外部呼叫都設逾時。AWS 的建議：先決定可接受的誤判率（例如 0.1%），再取下游延遲的對應百分位數當逾時值。
  - CancellationToken 沿呼叫鏈一路傳下去。
  - 業務流程（交易、組隊確認）也要有期限。
- 何時不算：刻意保持的長連線（例如 server push 用的 WebSocket）沒有「請求逾時」，但要有心跳與閒置逾時（D6）。
- 來源：https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ ；https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/04-Test_for_Process_Timing

### Unbounded Retry（無上限重試）〔D2〕
- 定義：失敗就立刻重試，而且永遠重試（`while (true)`）。
- 辨識訊號：重試迴圈沒有次數或總時長上限，也沒有延遲；連 4xx 或驗證失敗這類重試也不會成功的錯誤都重試。
- 為何有害：Azure 指出，請求通常只在有限時間內有意義，無限重試既無效又拖垮服務；「你的請求本身不合法」的錯誤（例如 400）重試毫無意義。
- 解法：限制次數與總時長；分清可重試（暫時性）與不可重試的錯誤；最終失敗要回報給使用者或呼叫端；用 Polly 這類成熟函式庫，不要自己手寫。
- 何時不算：背景的最終一致修復任務（例如補發郵件佇列），只要有退避、超限告警與死信佇列。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/retry-storm/

### Retry Storm / Reconnect Thundering Herd（重試風暴／重連雪崩）〔D3〕
- 定義：大量用戶端或多層服務在同一時間重試，把剛恢復的服務再次打掛。
- 辨識訊號：
  - 伺服器重啟後幾秒內，連線數暴衝到平常的數倍。
  - 重連間隔固定（例如固定 5 秒）、沒有隨機抖動（jitter）。
  - client → gateway → game → DB 每一層都各自重試。
  - Azure 列的症狀：單一用戶端短時間大量請求；服務修好後立刻又連鎖失敗。
- 為何有害：AWS 的算例：若每層各自重試、一路疊加，DB 負載可放大 243 倍。在遊戲裡，維護後開服那一刻、或某台 gateway 掛掉時，全服同時重連，打爆登入服或 DB，然後再掛一次，形成惡性循環。
- 解法：
  - 指數退避（exponential backoff，每次失敗後等待時間加倍）加 jitter。
  - 只在一層重試。
  - 用 Circuit Breaker（熔斷器）。
  - 伺服器端節流，並回傳 retry-after。
  - 登入排隊：Queue-Based Load Leveling。
  ```csharp
  // 指數退避 + full jitter，含上限（上限 30 秒）
  var capMs = Math.Min(30_000, 500 * Math.Pow(2, attempt));
  await Task.Delay(Random.Shared.Next(0, (int)capMs), ct);
  ```
- 何時不算：單一使用者手動按的重試按鈕通常不構成風暴，但仍要防連點。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/retry-storm/ ；https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker ；https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling

### Non-Idempotent Retry（非冪等操作被重試：重複扣款／重複發獎）〔D4〕
- 定義：有副作用的操作（扣款、發獎、扣材料、寄信）被重送時，會再執行一次。
- 辨識訊號：
  - 購買或領獎請求沒有 request id／idempotency key（冪等鍵）。
  - 用戶端逾時後自動重送。
  - 伺服器用增量（`gold += 100`）處理，既不寫絕對值，也不用 key 去重。
  - DB 上沒有 `(playerId, requestId)` 唯一約束。
- 為何有害：AWS 原話："APIs with side effects aren't safe to retry unless they provide idempotency"。Azure 舉的後果是重複處理會 "double-charge a customer"。在遊戲裡，網路抖一下，儲值就被扣兩次（客訴），或獎勵領兩次（刷物）。「逾時但其實成功」是常態，不是例外。
- 解法：
  - 用戶端為每個邏輯操作產生唯一 key，重試時沿用同一個 key。
  - 伺服器把「記錄 key」與「業務變更」放在同一個 ACID 交易。
  - 用唯一約束讓資料庫當最終仲裁。
  - 重複請求回傳與第一次語意相同的結果。
  ```csharp
  // 同一交易：寫入去重紀錄 + 發獎；UNIQUE(PlayerId, RequestId) 擋掉重複
  await using var tx = await db.Database.BeginTransactionAsync(ct);
  db.RewardClaims.Add(new RewardClaim { PlayerId = pid, RequestId = req.RequestId, Result = reward });
  player.Gold += reward.Gold;
  try { await db.SaveChangesAsync(ct); await tx.CommitAsync(ct); return reward; }
  catch (DbUpdateException ex) when (IsUniqueViolation(ex)) {          // IsUniqueViolation 依 DB provider 判斷
      return await LoadPreviousResult(pid, req.RequestId);             // 回傳第一次的結果，不再發一次
  }
  ```
- 何時不算：天然冪等的操作，例如讀取、寫入絕對值、以 key upsert。
- 來源：https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer ；https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/

### No Reconnect / Session Resume（沒有斷線重連處理）〔D5〕
- 定義：連線一斷就等同登出，戰鬥、交易、組隊狀態全丟；或用戶端只會跳回登入畫面。
- 辨識訊號：
  - `OnDisconnected` 直接銷毀玩家物件。
  - 用戶端沒有「重連中」的狀態與 UI。
  - 斷線期間送出的請求不知道成功還是失敗，也沒有查詢機制。
- 為何有害：行動網路切換（Wi-Fi 與 4G 互換）、電梯、隧道造成的短暫斷線是日常。直接踢出會讓戰鬥被判輸、副本進度遺失、交易卡在一半。用戶端不知道請求結果就重送，又回到 D4。
- 解法：
  - 伺服器保留 session 一段寬限期。參考值：SignalR 2 的 DisconnectTimeout 預設 30 秒。
  - 以 session token 恢復身分，而不是靠連線。
  - 重連後做一次全量狀態同步。
  - 訊息層用 ack 加重送緩衝。ASP.NET Core SignalR 的 stateful reconnect 就是兩端暫存、互相 ACK、重連後重播。
  - 重連本身要退避（D3）。
- 何時不算：極短局、刻意設計成「斷線即判負」的競技模式。但這應是明確的設計決策。
- 來源：https://learn.microsoft.com/en-us/aspnet/signalr/overview/guide-to-the-api/handling-connection-lifetime-events ；https://learn.microsoft.com/en-us/aspnet/core/signalr/configuration （Configure stateful reconnect）

### Undetected Half-Open Connection（半開連線未偵測）〔D6〕
- 定義：一端已經斷了（拔線、手機休眠、NAT 逾時、中間設備重啟），另一端卻以為連線還活著。
- 辨識訊號：
  - 伺服器的在線人數比實際多（殭屍連線）。
  - 只讀不寫的 socket 永遠等不到錯誤。
  - 沒有應用層心跳，只依賴作業系統的 TCP keepalive 預設值（預設常以小時計，業界經驗）。
- 為何有害：Cleary 原話："a socket that only reads cannot detect a dropped connection"。殭屍連線會佔住角色（玩家重新登入時看到「帳號已在線」）、佔資源、浪費廣播頻寬，房間也會一直等一個不存在的玩家。
- 解法：
  - 雙向的應用層心跳。Cleary 最推薦在協定的 framing（封包分框）裡加空的 keepalive 訊息，而且兩端都要做。
  - 閒置逾時。Fiedler 的 UDP 協定以 5 秒沒收到封包判定逾時。
  - SignalR 預設每 10 秒 keepalive、20 秒逾時。
  - 新登入要踢掉舊 session。
- 何時不算：短連線的請求-回應（例如每個請求一條 HTTP 連線）。
- 來源：https://blog.stephencleary.com/2009/05/detection-of-half-open-dropped.html ；https://gafferongames.com/post/client_server_connection/ ；https://learn.microsoft.com/en-us/aspnet/signalr/overview/guide-to-the-api/handling-connection-lifetime-events

### Session State Bound to Connection Object（session 狀態綁在單一連線物件上）〔D7〕
- 定義：玩家的遊戲狀態（角色、背包、所在房間）以連線物件或連線 ID 為 key 存放，連線一消失狀態就跟著消失。
- 辨識訊號：
  - `Dictionary<ConnectionId, Player>`。
  - 玩家物件是 `Connection` 的欄位。
  - 狀態存在 SignalR Hub 實例的屬性裡。
  - 以 ConnectionId 當作玩家身分來送訊息。
- 為何有害：
  - 重連會拿到新連線，狀態就找不到了，D5 也做不出來。
  - SignalR 文件說明：重連逾時後重新呼叫 Start，會建立新的 connection ID。
  - ASP.NET Core SignalR 文件明說：每次 hub 方法呼叫都是新的 hub 實例，不要把狀態存在 hub 屬性。
  - 多機部署時，重連可能落到不同節點。
- 解法：用玩家或帳號 ID 當 key 建立 session 物件；連線只是「目前綁定的傳輸通道」，可以替換。送訊息用 UserIdentifier 或群組，不用 ConnectionId。
- 何時不算：純傳輸層的資料本來就屬於連線，例如該連線的加密 key、壓縮狀態、流量控制視窗。
- 來源：https://learn.microsoft.com/en-us/aspnet/signalr/overview/guide-to-the-api/handling-connection-lifetime-events ；https://learn.microsoft.com/en-us/aspnet/core/signalr/hubs

---

## E. 伺服器並行與資源隔離（Server Concurrency）

### Shared Mutable State Across Threads（跨執行緒共享可變狀態）〔E1〕
- 定義：遊戲狀態（玩家、房間、地圖物件）可以被多條執行緒同時讀寫，保護它的只有散落各處的 lock，甚至完全沒有保護。
- 辨識訊號：
  - 可修改的 `static Dictionary` 或 `List`。
  - handler 在 thread pool 上直接改 `room.Players`。
  - 偶發 `InvalidOperationException: Collection was modified`。
  - `count++` 這類非原子遞增。
- 為何有害：競態條件的結果不可預測、無法重現。在遊戲裡就是道具數量錯亂、玩家同時出現在兩個房間、偶發崩潰。Microsoft 提醒：伺服器情境下，static 狀態是所有請求共用的，多條執行緒會同時執行同一段程式碼。
- 解法：
  - 首選「狀態只屬於一條執行緒或一個 actor」：每個房間或地圖一條單執行緒佇列，其他執行緒用訊息溝通。
  - 必要的共享改用不可變資料、`Interlocked`、Concurrent 集合。
  - 避免可修改的 static 狀態。
- 何時不算：啟動後就不再修改的唯讀設定資料。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://gameprogrammingpatterns.com/singleton.html

### Game Logic on I/O Thread（遊戲邏輯跑在 I/O 執行緒上）〔E2〕
- 定義：在網路收包的回呼（socket receive callback、event loop）裡直接執行遊戲邏輯、DB 存取或重計算。
- 辨識訊號：
  - `OnReceive` 裡直接呼叫 `HandleAttack()` 或查 DB。
  - 網路執行緒 CPU 偏高，tick 執行緒卻閒著。
  - 一個慢 handler 讓所有連線的收包都延遲。
- 為何有害：Vert.x 的「黃金規則」是別阻塞 event loop：一旦阻塞，那個 loop 什麼都做不了；全部阻塞，應用就停擺。在遊戲裡，一個重 handler 會讓同一 I/O 執行緒上所有玩家延遲飆高；邏輯又分散在多條 I/O 執行緒上併行，等於 E1。
- 解法：I/O 執行緒只做解框（framing）、解碼與基本驗證，再把訊息投遞到所屬房間或 actor 的佇列；邏輯在 tick 或 actor 執行緒處理。
- 何時不算：極輕量、不碰共享狀態的處理，例如心跳回覆、協定層的 ping/pong。
- 來源：https://vertx.io/docs/vertx-core/java/ （The Golden Rule - Don't Block the Event Loop）；https://learn.microsoft.com/en-us/dotnet/orleans/grains/external-tasks-and-grains ；業界經驗

### Global Lock（全域鎖／鎖粒度過粗）〔E3〕
- 定義：用一把大鎖保護整個世界或整台伺服器的狀態，任何操作都要先拿到這把鎖。
- 辨識訊號：
  - 大多數 handler 都有 `lock (World.SyncRoot)`。
  - 核心很多，忙的只有一核。
  - 在線人數上升時，延遲非線性惡化。
  - profiler 顯示大量時間花在等鎖。
- 為何有害：所有操作被串行化，等於單執行緒，還額外付出鎖的成本。鎖內若做 I/O（E5），整服一起卡。Microsoft 指出，加鎖會降低效能、增加鎖競爭，還引入死結的可能。
- 解法：
  - 依資料的自然邊界分區：每房間、每地圖、每公會一條執行緒或一個 actor。
  - 跨分區的操作用訊息，不要巢狀鎖。
  - 只鎖最小必要範圍，鎖內不做 I/O。
- 何時不算：低併發的管理功能（GM 工具、啟動初始化）；或刻意設計的單執行緒主迴圈。後者不是鎖，而是單一擁有者（見 E8）。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices （Recommendations for class libraries）；業界經驗

### Inconsistent Lock Ordering（鎖順序不一致）〔E4〕
- 定義：不同程式路徑以不同順序取得多把鎖。
- 辨識訊號：交易功能寫 `lock(a){ lock(b){…} }`，反向操作卻寫 `lock(b){ lock(a){…} }`；程式裡有巢狀 lock；偶發「整台伺服器卡住但 CPU 不高」。
- 為何有害：Microsoft 的定義：兩條執行緒各自鎖住對方需要的資源，誰都無法前進，這就是死結。遊戲的典型場景是 A 與 B 同時互相發起交易，兩個玩家（甚至整台伺服器）一起卡死。CERT LCK07-J 以銀行轉帳為例說明。
- 解法：
  - 全域統一的取鎖順序，例如依實體 ID 排序後再取鎖。
  - 更好的做法是避免多鎖：交易交給單一協調者（例如交易 actor）處理。
  - 用 `Monitor.TryEnter(timeout)` 偵測死結。
  ```csharp
  var (first, second) = a.Id < b.Id ? (a, b) : (b, a);   // 依 ID 決定固定順序
  lock (first.Gate) lock (second.Gate) { Transfer(a, b, item); }
  ```
- 何時不算：只有一把鎖，或每段程式只取一把鎖且不巢狀。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices （Deadlocks）；https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck07-j

### Blocking I/O in Tick（在 tick 主迴圈中做阻塞 I/O 或 DB 呼叫）〔E5〕
- 定義：在固定頻率的遊戲主迴圈裡，同步等待 DB、檔案、HTTP 或跨服 RPC。
- 辨識訊號：
  - `Tick()` 或 `Update()` 裡出現 `SaveChanges()`、`File.WriteAllText`、`.Result`。
  - tick 耗時分佈有長尾：大多 2ms，偶爾 300ms。
  - 存檔時全場景卡一下。
- 為何有害：Game Loop 的前提是 "processes user input, but doesn't wait for it"。一次慢查詢，就是整個房間或地圖的所有玩家同時卡頓（拉回、技能延遲）。Azure 也指出，同步 I/O 讓執行緒在等待時無法做事，負載一高佇列就堆積到逾時。Orleans 文件直說：在 grain 的執行脈絡裡做阻塞呼叫 "should never be done"。
- 解法：
  - tick 內只發出非同步請求就繼續往下跑，結果以訊息形式在後續 tick 套用。
  - 存檔走背景佇列（write-behind，先寫記憶體、背景再寫 DB）。
  - 處理「寫入期間狀態又變了」的版本問題。
- 何時不算：啟動與關閉流程，或明確不在即時路徑上的工具程式。
- 來源：https://gameprogrammingpatterns.com/game-loop.html ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/synchronous-io/ ；https://learn.microsoft.com/en-us/dotnet/orleans/grains/external-tasks-and-grains

### Sync-over-Async（以 .Result／.Wait() 同步等待非同步工作）〔E6〕
- 定義：C# 中用 `.Result`、`.Wait()`、`GetAwaiter().GetResult()` 阻塞等待 Task 完成。
- 辨識訊號：
  - grep 得到 `.Result`、`.Wait()`、`.GetAwaiter().GetResult()`、`async void`。
  - thread pool 執行緒數持續上升。
  - 負載一高延遲突然惡化。
  - 有 SynchronizationContext 的環境下偶發死結。
- 為何有害：
  - Fowler 說這 "MUCH worse than calling a truly synchronous API"：一個操作佔兩條執行緒，導致執行緒池飢餓（thread pool starvation），服務中斷。
  - Orleans 說明它會讓 grain 死結。
  - EF Core 警告混用同步與非同步很容易觸發執行緒池飢餓。
  - Unity 主執行緒有自己的 SynchronizationContext，在主執行緒上 `.Result` 等一個需要回主執行緒才能完成的 Task，會讓遊戲凍結。這是 Fowler 所述死結機制在 Unity 的對應，屬業界經驗。
- 解法：
  - async 一路到底。
  - 真的避不開，就把同步等待隔離到專用執行緒（Orleans 示範 `await Task.Run(() => task.Wait())`）。
  - 禁用 `async void`，Fowler 與 Orleans 都明言禁止。
- 何時不算：極少數框架限制只能同步的進入點，而且確定不在熱路徑上。
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://learn.microsoft.com/en-us/dotnet/orleans/grains/external-tasks-and-grains ；https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying

### Per-Tick Allocation Churn（在 tick 中大量配置記憶體）〔E7〕
- 定義：每個 tick 或每個封包都 new 一堆短命物件，例如訊息物件、LINQ、閉包、字串串接、boxing、`byte[]`。
- 辨識訊號：
  - GC 次數隨在線人數成長。
  - tick 耗時的週期性尖峰與 GC 對得上。
  - Unity Profiler 的 GC Alloc 欄每幀都不是 0。
- 為何有害：Unity 文件的算例：每幀配置 1KB、60fps，每分鐘就是 3.6MB 的垃圾，GC 回收時要清理數千個小物件。GC 停頓會讓伺服器 tick 抖動（所有玩家一起卡）、讓用戶端掉幀。.NET 伺服器同理，屬業界經驗。
- 解法：
  - 目標是 Unity 建議的「理想 0 bytes per frame」。
  - 物件池（pooling）、`ArrayPool<byte>`、`Span<T>`。
  - 熱路徑上避免 LINQ、閉包與字串格式化；重用封包緩衝。
- 何時不算：非熱路徑（登入、讀設定）；或量測證明 GC 不是瓶頸。
- 來源：https://docs.unity3d.com/2022.3/Documentation/Manual/performance-garbage-collection-best-practices.html

### Actor / Single-Thread Model Bypass（繞過 actor／單執行緒模型）〔E8〕
- 定義：系統用「每個 actor 或房間由單執行緒處理」來免除鎖，但程式碼偷偷從其他執行緒去碰 actor 的內部狀態。
- 辨識訊號：
  - Orleans grain 裡用 `Task.Run(() => this.state…)`，或在 `ConfigureAwait(false)` 之後存取 grain 狀態。
  - Akka 等 actor 在 Future 或 Task 的回呼裡改自己的欄位。
  - 把 actor 內部的可變集合當成訊息送出去。
  - 從外部直接呼叫房間物件的方法，而不是送訊息。
- 為何有害：模型的安全保證只在「所有存取都經過 actor 自己的排程器」時才成立。一旦繞過，就是 E1 的競態，而且大家以為這裡不需要鎖，更難發現。
  - Orleans：`Task.Run` 與 `ConfigureAwait(false)` 會跳出 grain 的單執行緒排程，文件明言 "never use ConfigureAwait(false) directly in grain code"。
  - Akka：不得把 actor 內部狀態洩漏到回呼裡；訊息應該不可變。
- 解法：
  - 結果用訊息送回自己：Akka 用 pipeToSelf；Orleans 只要正常 `await`，之後就會回到 grain 排程器。
  - 訊息一律不可變。
  - 用 analyzer 或 code review 禁止 actor 程式碼出現 `ConfigureAwait(false)`，以及 `Task.Run` 內存取狀態。
- 何時不算：在 actor 外做純計算、不碰 actor 狀態，再把結果以 await 或訊息帶回。Orleans 允許 `await Task.Run(blocking)` 這種用法。
- 來源：https://learn.microsoft.com/en-us/dotnet/orleans/grains/external-tasks-and-grains ；https://doc.akka.io/docs/akka/current/general/jmm.html （Actors and shared mutable state）

### Non-Atomic Check-Then-Act（先查後改非原子：刷物溫床）〔E9〕
- 定義：「檢查條件」與「執行變更」分成兩步，中間有時間窗（race window），併發請求可以同時通過檢查。又稱 TOCTOU（time-of-check to time-of-use，檢查時與使用時狀態不同）。
- 辨識訊號：
  - `if (!HasClaimed(x)) { await Give(x); await MarkClaimed(x); }`。
  - `if (gold >= price) { await …; gold -= price; }`，檢查與扣款之間有 await。
  - 交易在「雙方確認」之後才各自扣物品。
  - 快速連點偶爾會成功兩次。
- 為何有害：PortSwigger 把這類問題稱為 limit overrun（突破限制），例子包括同一張禮物卡兌換多次、提款超過餘額。在遊戲裡，同時送出多個領獎、販售、拆解、收郵件附件的請求，就能複製物品或金錢（dupe）。經濟一旦崩壞，常常只能全服回檔。
- 解法：
  - 把檢查與變更變成單一原子操作。
  - DB 交易加唯一約束，或用條件式更新：`UPDATE … SET gold = gold - @p WHERE id = @id AND gold >= @p`，影響 0 列就代表失敗。
  - 或保證同一玩家的請求在同一個 actor 上串行處理，且檢查與變更之間不 await 外部。
  - Azure 的做法：用唯一約束讓資料庫當仲裁者；cache 也要用 set-if-absent 這類原子寫入。
- 何時不算：單執行緒處理，且檢查與變更之間不讓出執行權（沒有 await、沒有釋放鎖）。
- 來源：https://portswigger.net/web-security/race-conditions ；https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer （Guard against concurrent duplicates）；https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/05-Test_Number_of_Times_a_Function_Can_Be_Used_Limits

### Busy Front End（前端忙碌：在服務行程內無節制地開背景工作）〔E10〕
- 定義：Azure 的定義是，把 CPU 密集工作丟到大量背景執行緒，看似讓回應變快，實際上和處理請求的執行緒搶資源。遊戲版本：在遊戲服行程內為尋路、AI 批次、排行榜重算、配對、報表無上限地 `new Thread` 或 `Task.Run`。
- 辨識訊號：
  - CPU 衝到 100% 時，tick 延遲跟著飆高。
  - handler 裡出現 `new Thread(...)` 或大量 `Task.Run`。
  - 依賴的服務回 429，或佇列長度持續增加。
- 為何有害：tick 執行緒搶不到 CPU，全服一起卡。Azure 也提到，伺服器能跑的執行緒有上限，超過就可能在建立執行緒時拋例外。
- 解法：
  - Queue-Based Load Leveling：重工作丟進佇列，由獨立的 worker 或服務處理。
  - 限制併發（SemaphoreSlim、專用 scheduler）。
  - 加上 Throttling 與 Priority Queue。
- 何時不算：await 網路 I/O 不算。Azure 明說 "Performing an asynchronous await on a network call is a recommended practice"，那是 E5 的正解。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/busy-front-end/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling

### Noisy Neighbor（吵鬧鄰居：單一房間或公會吃光共用資源）〔E11〕
- 定義：多個房間、公會、分線（或租戶）共用同一個行程、DB 或快取，其中一方的突發負載拖垮其他人。
- 辨識訊號：
  - 「某公會攻城時全伺服器都卡」。
  - 同一個請求有時快、有時隨機失敗。
  - 沒有每個房間或每個玩家的資源用量指標。
- 為何有害：Azure 指出，只要資源共享就無法完全避免；一方用掉不成比例的資源，其他人的請求就失敗或變慢。部分來源可能是惡意的，例如刻意觸發昂貴操作。
- 解法：
  - 監控每個房間或玩家的資源用量並設告警。
  - 配額與節流：Throttling、Rate Limiting。
  - Bulkhead（艙壁隔離）：大型活動獨立行程或分線。
  - 限制單一方能觸發的昂貴操作，例如查詢筆數上限、改成非同步排程。
- 何時不算：資源充足且負載互補；或已經隔離（每個房間獨立行程）。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/noisy-neighbor/noisy-neighbor ；https://learn.microsoft.com/en-us/azure/architecture/patterns/bulkhead

---

## F. 資料存取（Data Access / Persistence）

### SQL Embedded in Game Logic（遊戲邏輯中直接寫 SQL）〔F1〕
- 定義：戰鬥、任務、商店等業務邏輯裡直接組 SQL 字串，或直接操作 DB 連線。
- 辨識訊號：
  - `SkillSystem.cs` 裡出現 `new SqlCommand("UPDATE …")`。
  - 同一張表的寫入散落在十幾個系統。
  - 用字串拼接組 SQL（附帶 SQL injection 風險）。
  - 單元測試非連 DB 不可。
- 為何有害：何時寫、寫什麼、要不要批次與快取，這些持久化策略無法集中控制，很容易在 tick 裡同步寫（E5），或每個小改動都寫一次（對 DB 的 Chatty I/O）。schema 改動的影響面也無從得知。
- 解法：
  - 用 Repository 或資料存取層集中查詢邏輯。Fowler 說這樣能減少重複的查詢邏輯。
  - 遊戲邏輯只改記憶體中的領域物件；何時、如何寫入由持久化層決定（dirty tracking 加批次）。
- 何時不算：極小工具或一次性管理腳本；或把 stored procedure 當成明確的資料 API（但要留意 F9）。
- 來源：https://martinfowler.com/eaaCatalog/repository.html ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/ ；業界經驗

### Whole-Blob Save（每次存檔寫整包 blob）〔F2〕
- 定義：把整個角色（屬性、背包、任務、好友……）序列化成一個大 blob，任何變動都整包寫回。
- 辨識訊號：
  - `characters` 表只有 `id` 與 `data varbinary(max)`。
  - 改 1 金幣也寫 50KB。
  - 為了壓住 DB 負載只好降低存檔頻率。
  - 兩個系統同時改同一角色時，出現「後寫覆蓋前寫」的回檔客訴。
- 為何有害：
  - 寫入放大：頻寬、DB I/O、交易 log 都暴增。
  - 整包採「最後寫入者勝」（last-write-wins），一個系統的舊快照會蓋掉另一個系統的新變更，等於回檔或道具消失。
  - 無法對單一欄位查詢或稽核，客服查不到「誰在何時拿到這把劍」。
  - 格式演進受 B5 影響。
  - Azure 的 Monolithic Persistence 把「關聯式 DB 裡存大 blob」列為儲存與資料不匹配的例子；Chatty I/O 也建議把資料分成常用與不常用兩塊。
- 解法：
  - 依變動頻率與存取模式拆分，例如常變的貨幣與背包，和很少變的外觀設定分開。
  - 用 dirty flag 只寫有變動的部分。
  - 經濟相關變動另外寫 append-only 稽核記錄（Event Sourcing 的思路）。
  - 加 version 欄位做樂觀並行控制，防止互相覆蓋。
- 何時不算：資料小、變動低頻、只有單一寫入者（單機雲存檔、設定檔）；或 blob 搭配版本號與單一寫入 actor，覆蓋問題已經消除。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/monolithic-persistence/ ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing ；回檔情境為業界經驗

### Synchronous DB Write Blocking Player（同步寫 DB 阻塞玩家操作）〔F3〕
- 定義：玩家每個動作都等 DB 寫完才回應或繼續。
- 辨識訊號：
  - 撿道具、換裝的回應延遲約等於 DB 寫入延遲。
  - DB 一慢，所有玩家的操作都慢。
  - 出現連線池耗盡錯誤。
- 為何有害：DB 延遲直接變成手感延遲，DB 一抖全服卡；和 E5 疊加時，整個房間一起凍結。
- 解法：
  - 分清兩類操作：
    - 必須先落地才能確認的：儲值、交易、稀有掉落。用非同步寫入並等待結果，但不阻塞 tick。
    - 可以延後持久化的：位置、一般經驗值。用 write-behind 批次寫入。
  - 搭配 Queue-Based Load Leveling。
  - Azure 提醒：記憶體緩衝在行程當機時會遺失，要在耐久佇列與縮短 flush 週期之間取捨。
- 何時不算：經濟關鍵操作確實要等落地才回成功，等待本身是對的，但要用非同步等待，而不是阻塞執行緒。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/synchronous-io/ ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/ （Considerations：buffer vulnerable if process crashes）；https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying （Asynchronous programming）；https://learn.microsoft.com/en-us/azure/architecture/patterns/queue-based-load-leveling

### Cache-DB Inconsistency（快取與 DB 不一致）〔F4〕
- 定義：快取（Redis 或記憶體）與 DB 的資料不一致，而且沒有明確策略。常見原因：寫入順序錯、沒有失效、多個本地快取各自過期。
- 辨識訊號：
  - 先刪快取再寫 DB。
  - 寫完 DB 忘了讓快取失效。
  - 多台伺服器各自在記憶體快取同一份可變資料。
  - 沒有 TTL。
  - 數值偶爾「退回舊值」。
- 為何有害：Azure Cache-Aside 說明：如果先刪快取再更新 DB，中間有個時間窗會讓舊資料被重新載入快取，快取因此長期陳舊。在遊戲裡，玩家看到舊數值，系統又拿舊值計算再寫回，就變成回檔。
- 解法：
  - Cache-Aside：先更新資料儲存，再讓快取失效。
  - 設定合適的過期時間；跨實例用分散式快取。
  - 需要「寫完立刻讀到新值」時改用 write-through。
  - 權威的遊戲狀態不要同時存在可寫的快取與 DB（見 C1）。
- 何時不算：可容忍過期的展示資料，例如每分鐘刷新的排行榜。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/no-caching/

### Shared Persistence（多服務共用同一個資料庫）〔F5〕
- 定義：多個服務（登入服、遊戲服、商城服、GM 後台、營運報表）直接讀寫同一組表。
- 辨識訊號：
  - GM 工具直接 `UPDATE characters`。
  - 報表查詢直接打正式 DB。
  - 改一個欄位要通知四個團隊。
  - 某服務的長交易把表鎖住，其他服務跟著卡。
- 為何有害：
  - microservices.io 列出兩種耦合：
    - 開發期耦合：schema 改動要多團隊協調。
    - 執行期耦合：一個服務的長交易鎖表，另一個服務被擋住。
  - 在遊戲裡：GM 後台在玩家在線時改 DB，又被遊戲服記憶體裡的舊狀態蓋回去（C1）；營運報表的大查詢拖慢遊戲。
- 解法：每份資料只有一個擁有者服務，其他服務透過 API 存取；報表走唯讀副本或資料倉儲；GM 操作透過遊戲服的 API，由權威擁有者執行。
- 何時不算：單體架構初期，在同一個部署單元內共用 DB 是合理起點。問題出在「多個獨立部署的服務直接改同一張表」。
- 來源：https://microservices.io/patterns/data/shared-database.html ；「Shared Persistence」一詞出自 Taibi & Lenarduzzi 的微服務壞味道目錄（IEEE Software 2018）https://www.computer.org/publications/tech-news/research/defining-bad-smells-specifically-for-cloud-native-applications-based-on-microservices （該頁未展開條目內文）

### ORM N+1 Query（ORM 的 N+1 查詢）〔F6〕
- 定義：先查出 N 筆主資料，再在迴圈中觸發 N 次關聯查詢，常由 lazy loading（延遲載入：存取到關聯屬性時才自動查 DB）在背後產生。
- 辨識訊號：
  - 打開 EF Core 的 SQL log，看到同一形狀的查詢重複 N 次。
  - `foreach (var g in guilds) foreach (var m in g.Members)`。
  - 專案啟用了 lazy loading proxies。
- 為何有害：EF Core 文件說 lazy loading 特別容易產生多餘往返，"can cause very significant performance issues"。在遊戲裡，載入公會、好友、郵件清單的往返數隨資料量成長，登入尖峰時 DB 被打爆。
- 解法：eager loading（Include）、投影（Select）、split query。EF Core 建議避免 lazy loading，因為 eager 或 explicit loading 讓「這裡會打一次 DB」在原始碼中一目了然。
- 何時不算：N 很小且確定有上限；或在條件分支中刻意用 explicit loading 只載入少數。
- 來源：https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/

### Monolithic Persistence（單一資料儲存放所有類型資料）〔F7〕
- 定義：業務資料、log、遙測、聊天紀錄、佇列訊息全部塞在同一個資料庫。
- 辨識訊號：
  - 遊戲 DB 裡的 `game_log`、`chat_log` 寫入量遠大於業務表。
  - log 寫入尖峰時，玩家操作變慢。
  - 備份與還原時間被 log 拖長。
- 為何有害：Azure 指出，不相關的大量資料爭用同一個儲存，會造成回應變慢與連線失敗；而且不同資料適合不同儲存（log 是循序寫入，業務資料是隨機存取）。
- 解法：依用途分離儲存：log 與遙測走專用管線，聊天紀錄放獨立的庫，暫存資料放 Redis。
- 何時不算：極小規模或單機開發環境。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/monolithic-persistence/

### No Caching（不快取）〔F8〕
- 定義：每次請求都重新讀取相同而且很少變的資料，例如道具表、技能表、玩家公開資料。
- 辨識訊號：
  - DB 統計裡同一個查詢被執行數十萬次（Azure 範例超過 25 萬次）。
  - 每個請求都讀一次設定表。
- 為何有害：Azure 指出，反覆抓取昂貴資源會增加資料儲存的爭用、降低擴展性；若對方有配額，還可能被節流。
- 解法：
  - 靜態設定資料在啟動時就載入記憶體（priming）。
  - 動態但少變的資料用 cache-aside 加過期時間。
  - 量測快取命中與未命中（hit/miss）。
- 何時不算：
  - 敏感或與安全相關的資料：Azure 建議一律從主要來源取。
  - 大部分請求都不會命中快取。
  - 需要強一致的經濟資料（見 F4、C1）。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/no-caching/ ；https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside

### Busy Database（忙碌資料庫：把運算塞進 DB）〔F9〕
- 定義：用 stored procedure、trigger 或複雜 SQL 做格式化、字串處理、業務規則計算。
- 辨識訊號：
  - DB CPU 很高，資料傳輸量卻很低。
  - 掉落、獎勵公式寫在 stored procedure 裡。
  - trigger 連鎖更新。
- 為何有害：Azure 指出，DB 是共享資源而且難以水平擴展，花時間跑程式就沒空服務請求。在遊戲裡，活動結算或排行榜計算會拖垮所有玩家的存取。
- 解法：把運算搬到可水平擴展的應用層；DB 只做它擅長的事，例如索引查詢與彙總。
- 何時不算：資料庫擅長的彙總計算，Azure 明說別搬出來；或搬出來會造成大量資料傳輸（Extraneous Fetching）。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/busy-database/

### Improper Instantiation（不當實例化：反覆建立應共享的連線物件）〔F10〕
- 定義：每個請求都 new 一個本該共享的重量級物件，例如 HttpClient、Redis 的 ConnectionMultiplexer、ServiceBusClient、gRPC channel。
- 辨識訊號：
  - handler 裡有 `using var http = new HttpClient()`。
  - 每次存取都呼叫 `ConnectionMultiplexer.Connect`。
  - 出現 SocketException（埠耗盡）。
  - 連線數隨請求數暴增。
- 為何有害：Azure 的實測：高負載下 socket 耗盡、拋 SocketException；或光是建立物件的成本就讓吞吐卡住。在遊戲裡，登入尖峰時對平台 API（儲值驗證、第三方登入）的請求開始失敗。
- 解法：
  - 可共享且執行緒安全的物件用單例，或用 IHttpClientFactory。
  - 不可共享的物件用物件池。
  - EF Core 的 DbContext 不是執行緒安全的（ASP.NET Core SignalR 文件特別提醒），應短生命週期使用；資料庫連線是稀缺資源，不該長期佔用。
- 何時不算：物件本身非執行緒安全、不可共享時，Azure 明說此反模式不適用，例如 DbContext。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/improper-instantiation/ ；https://learn.microsoft.com/en-us/aspnet/core/signalr/hubs

---

## G. 用戶端結構（Unity Client）

### Network Callback Mutates UI Directly（網路回呼直接改 UI）〔G1〕
- 定義：收到封包的回呼裡直接操作 UI 元件或 GameObject。
- 辨識訊號：
  - socket 執行緒上寫 `OnPacket(m) { goldText.text = m.Gold.ToString(); }`。
  - 開發版報錯 "... can only be called from the main thread"。
  - 網路模組引用了 UI 命名空間。
  - 同一份資料被多個回呼各自寫到不同的 UI。
- 為何有害：
  - Unity 文件："Most of the Unity API isn't thread-safe and therefore, you should only use Unity APIs from the main thread"。
  - 而且 "Unity doesn't perform checks for multithreaded behavior in non-development builds"：正式版不會報錯，只會出現不可預期的行為或崩潰。
  - 就算在主執行緒上，網路層與 UI 直接耦合，換 UI 就得改網路程式碼，資料流也追不到（G5）。
- 解法：網路層只把訊息解碼成資料，再切回主執行緒（例如 `await Awaitable.MainThreadAsync()`）更新 Model；UI 由 Presenter 或 ViewModel 觀察 Model 的變化。
  ```csharp
  async Awaitable OnGoldChangedAsync(GoldChanged m) {
      await Awaitable.MainThreadAsync();   // 回到主執行緒
      playerModel.SetGold(m.Gold);         // 只改 Model；UI 由 Presenter 訂閱 Model 的變更
  }
  ```
- 何時不算：極簡原型；或網路框架保證回呼已在主執行緒執行（但耦合問題仍在）。
- 來源：https://docs.unity.cn/Manual/AwaitSupport.html ；https://docs.unity3d.com/6000.0/Documentation/Manual/async-awaitable-continuations.html ；https://learn.unity.com/course/design-patterns-unity-6/tutorial/build-a-modular-codebase-with-mvc-and-mvp-programming-patterns

### Network I/O and Parsing on Main Thread（在主執行緒做網路收送與解析）〔G2〕
- 定義：在 Unity 主執行緒上同步收送 socket、解壓縮、反序列化大封包（JSON、大型 protobuf）。
- 辨識訊號：
  - Profiler 的主執行緒出現 `Socket.Receive` 或 `JsonConvert.DeserializeObject` 的大尖峰。
  - 進大廳、開背包時掉幀。
  - 使用同步的網路請求。
- 為何有害：主執行緒同時負責邏輯與渲染，60fps 下每幀只有約 16.7ms。解析一個大封包花 50ms，就掉了約 3 幀；同步等網路則是畫面直接凍結。解析過程大量配置記憶體，還會帶出 GC 尖峰（E7）。
- 解法：
  - socket 收送用非同步 API。
  - 大封包解析丟到背景（`await Awaitable.BackgroundThreadAsync()`），只把結果帶回主執行緒套用。
  - 資料量大時分幀套用，並減少配置。
- 何時不算：小而頻繁的封包，解析成本可忽略（以量測為準）；WebGL 等不支援多執行緒的平台（業界經驗）。
- 來源：https://docs.unity3d.com/6000.0/Documentation/Manual/async-awaitable-continuations.html ；https://docs.unity3d.com/2022.3/Documentation/Manual/performance-garbage-collection-best-practices.html

### Business Rules in UI Layer（UI 層含業務規則）〔G3〕
- 定義：MonoBehaviour 的 UI 腳本裡含有遊戲規則，例如在按鈕事件裡算價格、判斷能否強化、決定要顯示的掉落、驗證輸入。
- 辨識訊號：
  - `ShopPanel.cs` 長達 2000 行，裡面有折扣公式。
  - 同一條規則在多個 UI 面板重複。
  - 規則改版要改 UI prefab 的腳本。
  - 不開 Unity 場景就無法測試規則。
- 為何有害：Unity 官方教學指出，資料與 UI 混在一起 "wouldn't scale well"，擴充、測試與重構成本都高。網遊還多兩個風險：規則放在用戶端等於可被竄改（A3）；又和伺服器規則各寫一份，必然漂移（B9、C1）。
- 解法：
  - 採 MVP（Model-View-Presenter）或 MVVM：View 被動、Presenter 協調、Model 只存資料。
  - 真正的規則以伺服器為準；用戶端只保留「預覽」用的規則程式庫，最好與伺服器共用同一份程式碼。
- 何時不算：純顯示邏輯（數字格式化、排序、動畫）本來就屬於 UI。
- 來源：https://learn.unity.com/course/design-patterns-unity-6/tutorial/build-a-modular-codebase-with-mvc-and-mvp-programming-patterns ；https://cwe.mitre.org/data/definitions/602.html

### Manager Spider Web（全域管理器蛛網）〔G4〕
- 定義：大量 `XxxManager.Instance` 單例互相直接呼叫，形成網狀依賴。
- 辨識訊號：
  - `NetworkManager.Instance` 被 100 個以上的檔案引用。
  - 各 Manager 之間互相呼叫 Instance。
  - 有初始化順序問題：某個 Manager 在 Awake 時，另一個還是 null。
  - 無法單獨測試或替換，例如換成假的網路層。
- 為何有害：
  - Nystrom 指出：singleton 本質上是全域狀態，會鼓勵耦合、不利併行；「Manager」類別常是設計不完整的徵兆。
  - Unity 官方建議用明確參考取代 singleton，才容易換成測試版或教學版。
  - 網遊的特有風險：斷線重連時需要「重置所有狀態」，散在各單例裡的狀態清不乾淨，重連後殘留舊資料（C1、D5）。
- 解法：依賴注入或明確參考（ScriptableObject 參考、建構子注入）；把連線期間的狀態集中在一個可以整體重建的 session 或 context 物件；Manager 只留真正全域的服務。
- 何時不算：少數真正全域、且不帶可變遊戲狀態的服務，例如 Log、時間來源。
- 來源：https://gameprogrammingpatterns.com/singleton.html ；https://unity.com/how-to/architect-game-code-scriptable-objects

### Event Bus Abuse（事件總線濫用導致追不到資料流）〔G5〕
- 定義：所有模組都透過全域事件總線（EventBus、Messenger）溝通，事件被拿來傳命令與資料，而不只是通知「某件事已經發生」。
- 辨識訊號：
  - 想知道誰會處理某個事件，只能全域搜尋字串。
  - handler 又發出事件，形成連鎖。
  - 事件名稱是命令式的，例如 `DoBuyItem`。
  - 偶發無限迴圈或重複觸發。
  - payload 只帶 ID，handler 再去查「現在」的狀態。
- 為何有害：
  - Fowler：跨多個事件的流程 "not explicit in any program text"，往往只能監看正在執行的系統才看得懂。
  - Nystrom：中央事件佇列本質上是全域變數；事件被處理時世界可能已經變了；而且可能形成回饋迴圈。
  - 網遊的情況：封包觸發事件，事件連鎖觸發 UI 與邏輯，產生難以重現的錯誤狀態。
- 解法：
  - 事件只用來通知「已發生的事」，命令改用直接呼叫。
  - payload 帶齊發生當下所需的資料。
  - 處理事件時不再發事件（Nystrom 的建議）。
  - 事件系統加上除錯 log。
  - 縮小事件範圍：模組內事件優先於全域事件。
- 何時不算：真正一對多、雙方不需要互相知道的通知，例如成就系統監聽擊殺事件，這正是事件的正當用途。
- 來源：https://martinfowler.com/articles/201701-event-driven.html ；https://gameprogrammingpatterns.com/event-queue.html

---

## H. 可觀測性（Observability）

### Silent Failure（失敗靜默：錯誤被吞或只記 debug）〔H1〕
- 定義：錯誤被吞掉、只記成 debug 等級的 log，或回傳預設值後若無其事地繼續執行。
- 辨識訊號：
  - `catch { }`、`catch (Exception) { return null; }`。
  - handler 失敗時不回應用戶端，對方只能等到逾時。
  - 正式環境的 log 等級是 Warn，錯誤卻用 Debug 記。
  - 解析失敗的封包被默默丟棄，也沒有計數。
- 為何有害：
  - CWE-390：偵測到錯誤卻不處理，系統會進入非預期狀態。
  - OWASP A09：登入失敗、高價值交易等事件沒記錄，攻擊就無從偵測。
  - 網遊的情況：外掛送的畸形封包、刷物嘗試全被吞掉，營運要等到經濟異常才發現；用戶端的請求「沒反應」，玩家又重送，引發 D4。
- 解法：每個失敗都要有明確的結局：
  - 回錯誤碼給用戶端。
  - 記 Warn 或 Error，附玩家 ID、opcode、關聯 ID。
  - 計數指標並設告警。
  - 高價值操作（交易、儲值、稀有掉落）寫稽核 log。
- 何時不算：預期中且已計數的雜訊，例如被去重的重複請求記成指標而不是錯誤。
- 來源：https://cwe.mitre.org/data/definitions/390.html ；https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/

### No Correlation ID（沒有關聯 ID）〔H2〕
- 定義：一個玩家操作會經過 client → gateway → game server → DB 或其他服務，但各處的 log 沒有共同的識別碼。
- 辨識訊號：
  - 查客訴時只能用「時間 + 玩家 ID」到各台機器 grep、人工比對。
  - 請求封包沒有 request id。
  - 跨服 RPC 不傳遞 trace context。
- 為何有害：無法串起一次操作的完整路徑。玩家說「付了錢沒拿到東西」時，查不出卡在哪一層；也分不出重複請求與重試（D4）。
- 解法：
  - 用戶端請求帶 request id，同一個值兼當冪等鍵（D4）。
  - 伺服器建立 trace：.NET 的 `Activity`，搭配 W3C TraceContext 的 trace-id，並跨行程傳遞。
  - 所有 log 結構化，附上 trace-id 與 player-id。
  - Azure Idempotent Consumer 也建議在 log 中同時輸出去重鍵與關聯 ID。
- 何時不算：單一行程、單一步驟的操作；但仍建議至少帶 request id。
- 來源：https://learn.microsoft.com/en-us/dotnet/core/diagnostics/distributed-tracing-concepts ；https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer

### Unreproducible Packet Flow（無法重現的封包流）〔H3〕
- 定義：線上發生的錯誤無法在本地重現，因為沒有保留足夠資訊，例如輸入序列、封包內容、伺服器 tick 編號、隨機種子。
- 辨識訊號：
  - bug 單上常見「無法重現」。
  - 沒有封包錄製與重播工具。
  - 伺服器邏輯依賴沒有記錄下來的非確定性來源：系統時間、未固定種子的亂數、執行緒排程。
- 為何有害：網遊的 bug 多半跟時序、丟包、併發有關（C5、C6、E1、E9）；不能重現就只能猜，結果不是修錯就是不修。
- 解法：
  - 可開關的封包錄製，記下時間戳、方向、序號；敏感欄位要遮罩。
  - 伺服器邏輯盡量確定性：時間與亂數由可注入的來源提供，並記錄種子。確定性模擬的原理是「同一初始狀態加同一串輸入，得到同一結果」，正是 lockstep 模型的基礎。
  - 重播工具餵入錄製的輸入；用 H2 的 trace-id 定位。
- 何時不算：成本取捨問題；至少經濟與戰鬥的核心路徑要保留可重現性。
- 來源：業界經驗（未找到直接以此為題的權威專文）；確定性原理參考 https://gafferongames.com/post/what_every_programmer_needs_to_know_about_game_networking/

---

## 附錄 1：Microsoft Azure「Performance antipatterns」對照

Azure Architecture Center 列出 10 個效能反模式，原始目錄：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/

| Azure 反模式 | Azure 一句話定義 | 本文條目 | 遊戲情境 |
|---|---|---|---|
| Busy Database | 把太多處理丟給資料儲存 | F9 | 活動結算或公式寫在 stored procedure |
| Busy Front End | 把耗資源的工作丟到背景執行緒 | E10 | 遊戲服內無上限地 `Task.Run` 尋路、配對 |
| Chatty I/O | 持續發送大量小網路請求 | B1、B3、F6 | 一個畫面 N 個請求；ORM N+1 |
| Extraneous Fetching | 撈的比需要的多 | B2 | 整包下發背包、SELECT * |
| Improper Instantiation | 反覆建立應共享重用的物件 | F10 | 每請求 new HttpClient 或 Redis 連線 |
| Monolithic Persistence | 用法差異很大的資料共用同一儲存 | F7（F2 相關） | log、聊天、業務資料同庫 |
| No Caching | 不快取 | F8 | 每次請求都讀道具表 |
| Noisy Neighbor | 單一租戶用掉不成比例的資源 | E11 | 攻城公會拖垮整服 |
| Retry Storm | 對伺服器重試太頻繁 | D2、D3 | 開服瞬間全服重連 |
| Synchronous I/O | I/O 完成前阻塞呼叫執行緒 | E5、E6、F3 | tick 內同步寫 DB、`.Result` |

## 附錄 2：Cloud Design Patterns 與它們對治的壞味道

完整目錄：https://learn.microsoft.com/en-us/azure/architecture/patterns/

| Pattern（解法） | 對治的壞味道 |
|---|---|
| Gatekeeper | A2、A4（在信任邊界前集中驗證與清洗） |
| Rate Limiting／Throttling | A5、E11、D3（伺服器端節流） |
| Retry（有上限加退避）＋ Circuit Breaker | D2、D3 |
| Idempotent Consumer | D4、E9（唯一約束、去重鍵與副作用同交易） |
| Sequential Convoy | C6（同組訊息依序、不同組平行） |
| Queue-Based Load Leveling | E10、F3、D3（登入排隊、重工作排隊） |
| Bulkhead | E11（隔離艙，一個爆了不拖累其他） |
| Cache-Aside | F4、F8、C1（先寫來源再讓快取失效） |
| Event Sourcing | F2（經濟變動的 append-only 稽核） |
| Gateway Aggregation | B1、B3 |
| Compensating Transaction／Saga | 跨服務流程失敗時的回補（如跨服交易），避免半套狀態 |

反過來看，Azure 在模式目錄開頭列的「分散式運算的錯誤假設」(fallacies of distributed computing)，本切面幾乎每一條都能對上：

| 錯誤假設 | 對應條目 |
|---|---|
| network is reliable | D 類 |
| latency is zero | B1、E5 |
| bandwidth is infinite | B2、C4 |
| network is secure | A 類 |
| component versioning is simple | B4、B5 |
| observability can be delayed | H 類 |

## 附錄 3：快速 grep 線索（給程式碼審查用）

| 搜尋字樣 | 可能的壞味道 |
|---|---|
| `.Result`、`.Wait()`、`GetAwaiter().GetResult()`、`async void` | E6 |
| `catch { }`、`catch (Exception) { }`、`catch (...) { return null; }` | H1 |
| handler 內 `new HttpClient(`、`ConnectionMultiplexer.Connect(` | F10 |
| 網路呼叫外圍的 `while (true)`，且沒有 delay 與上限 | D2、D3 |
| actor 或 grain 程式碼中的 `ConfigureAwait(false)`、`Task.Run(` | E8 |
| 巢狀 `lock (`；`lock (this)`、`lock (typeof(` | E4、E3 |
| `Tick`／`Update` 內的 `SaveChanges()`、`File.Write`、`Thread.Sleep` | E5 |
| handler 內 `player.X = msg.X`、欄位名含 `Damage`／`Price`／`Count` 的上行封包 | A1、A3 |
| 用戶端遊戲規則中的 `DateTime.Now`；封包中的 `clientTime` | C7 |
| 被序列化、卻沒有顯式數值的 `enum` | B6 |
| `.Instance.` 出現次數（Unity 專案） | G4 |
| socket 執行緒回呼中的 `.text =`、`SetActive(` | G1 |
| `if (...) { await ...; ... -= ... }` 這類「檢查後 await 再改」 | E9 |
| `Dictionary<string /*connectionId*/, Player>` | D7 |
| 啟用 `UseLazyLoadingProxies` | F6 |

---

## 主要來源清單

- Gabriel Gambetta, Fast-Paced Multiplayer：
  - https://www.gabrielgambetta.com/client-server-game-architecture.html
  - https://www.gabrielgambetta.com/client-side-prediction-server-reconciliation.html
  - https://www.gabrielgambetta.com/lag-compensation.html
- Glenn Fiedler, Gaffer On Games：
  - https://gafferongames.com/post/what_every_programmer_needs_to_know_about_game_networking/
  - https://gafferongames.com/post/reading_and_writing_packets/
  - https://gafferongames.com/post/serialization_strategies/
  - https://gafferongames.com/post/reliability_ordering_and_congestion_avoidance_over_udp/
  - https://gafferongames.com/post/snapshot_compression/
  - https://gafferongames.com/post/state_synchronization/
  - https://gafferongames.com/post/client_server_connection/
  - https://gafferongames.com/post/packet_fragmentation_and_reassembly/
- Valve Source Multiplayer Networking：https://developer.valvesoftware.com/wiki/Source_Multiplayer_Networking （原頁 403，經搜尋摘要確認 delta／全量／ack 敘述）
- Unreal CharacterMovementComponent 時間差異偵測：https://docs.unrealengine.com/4.26/en-US/API/Runtime/Engine/GameFramework/UCharacterMovementComponent/OnTimeDiscrepanc-/index.html
- GDC 參考（未逐字引用內容）：
  - Overwatch Gameplay Architecture and Netcode, Tim Ford, GDC 2017：https://gdcvault.com/play/1024001/-Overwatch-Gameplay-Architecture-and
  - I Shot You First: Networking the Gameplay of Halo: Reach, David Aldridge, GDC 2011：https://www.gdcvault.com/play/1014345/I-Shot-You-First-Networking
- OWASP：
  - WSTG-BUSL-02：https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/02-Test_Ability_to_Forge_Requests
  - WSTG-BUSL-04：https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/04-Test_for_Process_Timing
  - WSTG-BUSL-05：https://wstg.owasp.org/v4.2/4-Web_Application_Security_Testing/10-Business_Logic_Testing/05-Test_Number_of_Times_a_Function_Can_Be_Used_Limits
  - A09:2021：https://owasp.org/Top10/A09_2021-Security_Logging_and_Monitoring_Failures/
- MITRE CWE：
  - CWE-602：https://cwe.mitre.org/data/definitions/602.html
  - CWE-390：https://cwe.mitre.org/data/definitions/390.html
- PortSwigger Race conditions：https://portswigger.net/web-security/race-conditions
- Microsoft Azure Architecture Center：
  - Antipatterns 目錄：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/ （各子頁見上文）
  - Patterns 目錄：https://learn.microsoft.com/en-us/azure/architecture/patterns/
  - Cache-Aside、Idempotent Consumer、Gatekeeper、Sequential Convoy、Circuit Breaker、Bulkhead、Queue-Based Load Leveling 等子頁見上文
- AWS Builders' Library：
  - https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/
  - https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/
- .NET 與 C#：
  - Managed threading best practices：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices
  - David Fowler AsyncGuidance：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md
  - Orleans：https://learn.microsoft.com/en-us/dotnet/orleans/grains/external-tasks-and-grains
  - EF Core：https://learn.microsoft.com/en-us/ef/core/performance/efficient-querying
  - ASP.NET Core SignalR：hubs、hub-filters、configuration
  - SignalR 2 connection lifetime：https://learn.microsoft.com/en-us/aspnet/signalr/overview/guide-to-the-api/handling-connection-lifetime-events
  - Distributed tracing：https://learn.microsoft.com/en-us/dotnet/core/diagnostics/distributed-tracing-concepts
- Unity：
  - Awaitable continuations：https://docs.unity3d.com/6000.0/Documentation/Manual/async-awaitable-continuations.html
  - AwaitSupport：https://docs.unity.cn/Manual/AwaitSupport.html
  - GC best practices：https://docs.unity3d.com/2022.3/Documentation/Manual/performance-garbage-collection-best-practices.html
  - MVC/MVP：https://learn.unity.com/course/design-patterns-unity-6/tutorial/build-a-modular-codebase-with-mvc-and-mvp-programming-patterns
  - ScriptableObject architecture：https://unity.com/how-to/architect-game-code-scriptable-objects
- 一般設計：
  - Martin Fowler：https://martinfowler.com/eaaCatalog/remoteFacade.html ；https://martinfowler.com/eaaCatalog/repository.html ；https://martinfowler.com/articles/201701-event-driven.html
  - Robert Nystrom, Game Programming Patterns：https://gameprogrammingpatterns.com/singleton.html ；https://gameprogrammingpatterns.com/event-queue.html ；https://gameprogrammingpatterns.com/game-loop.html
  - refactoring.guru：https://refactoring.guru/smells/switch-statements
  - microservices.io：https://microservices.io/patterns/data/shared-database.html
- 序列化：
  - Protobuf：https://protobuf.dev/best-practices/dos-donts/
  - MessagePack-CSharp：https://github.com/MessagePack-CSharp/MessagePack-CSharp
  - MagicOnion：https://github.com/Cysharp/MagicOnion
- 並行與 actor：
  - Akka：https://doc.akka.io/docs/akka/current/general/jmm.html
  - SEI CERT LCK07-J：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck07-j
  - Vert.x：https://vertx.io/docs/vertx-core/java/
- 連線：Stephen Cleary 半開連線：https://blog.stephencleary.com/2009/05/detection-of-half-open-dropped.html

## 未查證／僅部分查證的內容

- **整條標「業界經驗」**：
  - H3（無法重現的封包流）：沒有直接專文，只引用確定性原理。
  - B7、B8 的遊戲封包框架細節：只引用通用來源（hub filter、switch smell）。
- **條目內的業界經驗補充**：
  - C1「雙存」：遊戲情境的描述。
  - C4：AOI（興趣管理）。
  - C7：延遲補償要限制回溯上限。
  - D6：TCP keepalive 預設以小時計。
  - E2、E3：遊戲情境推論。
  - E6：Unity 主執行緒上用 `.Result` 會凍結（由 Fowler 的 SynchronizationContext 死結機制推論）。
  - E7：.NET 伺服器的 GC 停頓。
  - F1：遊戲情境。
  - F2：回檔情境。
  - G2：WebGL 沒有多執行緒。
- **只經搜尋摘要確認、原頁無法直接開啟**：
  - Valve Source Multiplayer Networking（回 HTTP 403）。
  - Unreal API 頁的時間差異偵測描述。
  - Vert.x 黃金規則原文。
  - CERT LCK07-J（只確認網址存在與標題）。
- **只引用名稱或存在、未逐字引用內容**：
  - Taibi & Lenarduzzi 的「Shared Persistence」：只確認名稱出處，該頁未展開條目內文。
  - 兩場 GDC 演講（Overwatch、Halo: Reach）：只作延伸閱讀。
