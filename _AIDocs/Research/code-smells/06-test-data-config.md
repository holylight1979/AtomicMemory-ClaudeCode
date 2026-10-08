# 06 測試、資料與 SQL、設定與建置、文件與註解的壞味道

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 用途：給 LLM 隨時查「這算不算壞味道、怎麼認、怎麼修、何時其實沒事」。
> 壞味道（smell）＝「看起來可疑、值得停下來檢查」的訊號，不等於 bug；每條都有「何時不算」。
> 查證標記：每條「來源」都是實際開過的網址。標 **〔部分查證〕** 的條目，名稱與核心主張有來源，但細節是依主旨整理的通行做法，沒有逐字對過原書；標 **〔未查證〕** 的句子沒找到可靠來源。
> 門檻數字若標「（經驗值）」＝沒有文獻出處，只是常見判斷線；其餘數字都出自來源。

---

## 0. 這個切面的分類架構

```
06 測試／資料／設定／註解
├─ A 測試壞味道（test smells）
│  ├─ A1 看不懂：讀測試要花力氣，看不出在驗什麼
│  ├─ A2 會騙人：綠燈不代表真的有測，紅燈不代表產品有錯
│  ├─ A3 不穩定：同一份程式碼，時過時不過（flaky，俗稱「看心情的測試」）
│  ├─ A4 太黏實作：產品碼做了不影響行為的修改，測試卻壞了
│  ├─ A5 太貴：慢、要人手介入、每次失敗都要開除錯器
│  ├─ A6 測試邏輯滲進產品碼
│  ├─ A7 專案層：根本沒測、難測，bug 照樣漏到正式環境
│  └─ A8 測試框架用法小味道
├─ B 資料與 SQL 壞味道
│  ├─ B1 邏輯設計：資料表怎麼切、欄位怎麼放
│  ├─ B2 實體設計：型別、索引、大型檔案放哪
│  ├─ B3 查詢寫法
│  └─ B4 應用程式和資料庫的接縫：密碼、注入、錯誤處理、ORM
├─ C 設定與建置壞味道
│  ├─ C1 值放錯地方：寫死的設定、密鑰、魔術數字
│  ├─ C2 多個來源：設定分岔、伺服器設定漂移
│  ├─ C3 環境差異寫進程式：if (isDev)、功能旗標債
│  ├─ C4 建置與 CI（持續整合）腳本
│  ├─ C5 依賴宣告與版本鎖
│  └─ C6 IaC（Infrastructure as Code，用程式碼描述伺服器設定）
└─ D 文件與註解壞味道
```

| 類別 | 一句話說明 |
|---|---|
| A1 看不懂 | 測試本該兼當規格文件；讀不懂的測試沒辦法當文件，藏在裡面的錯也沒人看得到 |
| A2 會騙人 | 測試結果和真相不一致：沒驗東西卻綠燈，或產品沒錯卻紅燈 |
| A3 不穩定 | 結果取決於執行順序、時間、環境、誰在跑；大家就學會無視紅燈 |
| A4 太黏實作 | 測試綁死「怎麼做」而不是「做出什麼」，每次重構都要改一堆測試 |
| A5 太貴 | 跑一次的成本（時間、人力、除錯）高到大家不想跑 |
| A6 滲入產品碼 | 為了測試在產品碼加分支或後門，正式環境的行為和測試時不同 |
| A7 專案層 | 從專案管理看得到的症狀：沒人寫測試、改不動、bug 量偏高 |
| A8 框架小味道 | 違反特定測試框架慣例的寫法（偵測工具的規則） |
| B1 邏輯設計 | 違反正規化或關聯模型的表結構，讓資料一致性要靠應用程式碼補救 |
| B2 實體設計 | 型別、約束、索引、檔案存放選錯，造成精度、維護或效能問題 |
| B3 查詢 | SQL 寫法本身有陷阱：NULL 邏輯、分組歧義、全表掃描、笛卡兒積 |
| B4 接縫 | 應用程式用資料庫的方式出問題：安全、錯誤處理、ORM 的隱性查詢 |
| C1 值放錯地方 | 會隨部署環境改變的值、或機密資料，被寫死在程式碼裡 |
| C2 多個來源 | 同一份設定存在多處，誰為準不清楚，遲早不一致 |
| C3 環境分支 | 程式碼依「現在是哪個環境」走不同路徑，正式環境的路徑沒被測到 |
| C4 建置與 CI | 建置腳本複製貼上、CI 設定誤用（例如跳過安全檢查） |
| C5 依賴 | 依賴版本宣告太死、太鬆、沒鎖、沒宣告或沒在用 |
| C6 IaC | 把一般程式碼的壞味道（重複、過長、低內聚、寫死密碼）套到設定碼上 |
| D 註解 | 註解在重述程式碼、已經過期、堆積 TODO、寫版本歷史，而不是解釋「為什麼」 |

### 原始分類對照（查原文用）

- **Meszaros《xUnit Test Patterns》（2007）三層**：Code Smells（讀程式碼就看得到）、Behavior Smells（跑測試時才出現）、Project Smells（從專案層級觀察到）。
  - Code：Obscure Test → A1、Conditional Test Logic → A1、Hard-to-Test Code → A7、Test Code Duplication → A1、Test Logic in Production → A6
  - Behavior：Assertion Roulette → A1、Erratic Test → A3、Fragile Test → A4、Frequent Debugging → A5、Manual Intervention → A5、Slow Tests → A5
  - Project：Buggy Tests → A2、Developers Not Writing Tests → A7、High Test Maintenance Cost → A5、Production Bugs → A7
  - 來源：http://xunitpatterns.com/Test%20Smells.html
- **van Deursen、Moonen、van den Bergh、Kok〈Refactoring Test Code〉（XP2001）原始 11 種**：Mystery Guest、Resource Optimism、Test Run War、General Fixture、Eager Test、Lazy Test、Assertion Roulette、Indirect Testing、For Testers Only、Sensitive Equality、Test Code Duplication。
  - 來源：https://ir.cwi.nl/pub/4324/04324D.pdf
- **testsmells.org（tsDetect 偵測工具的目錄，RIT）列 19 種**：Assertion Roulette、Conditional Test Logic、Constructor Initialization、Default Test、Duplicate Assert、Eager Test、Empty Test、Exception Handling、General Fixture、Ignored Test、Lazy Test、Magic Number Test、Mystery Guest、Redundant Print、Redundant Assertion、Resource Optimism、Sensitive Equality、Sleepy Test、Unknown Test。
  - 來源：https://testsmells.org/pages/testsmells.html
- **Karwin《SQL Antipatterns》**：2010 年版共 24 章，分四部分：Logical Database Design、Physical Database Design、Query、Application Development。2022 年版《SQL Antipatterns, Volume 1》在第四部分以 Standard Operating Procedures 取代 Magic Beans，另增兩章外鍵錯誤，以及穿插在各章之間的 mini-antipatterns（小型反模式）。
  - 來源：https://pragprog.com/titles/bksqla/sql-antipatterns/ 、 http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://pragprog.com/titles/bksap1/sql-antipatterns-volume-1/
- **Sharma 等〈Smelly Relations〉（ICSE-SEIP 2018）13 種 schema smells**（資料表結構壞味道）：Compound attribute、Adjacency list、Superfluous key、Missing constraints、Metadata as data、Polymorphic association、Multicolumn attribute、Clone tables、Values in attribute definition、Index abuse、God table、Meaningless name、Overloaded attribute names。前 11 種幾乎和 Karwin 一一對應（見 B1 開頭的對照表）。
  - 來源：https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf
- **Sharma、Fragkoulis、Spinellis〈Does Your Configuration Code Smell?〉（MSR 2016）**：Puppet 設定碼，13 種 implementation 與 11 種 design configuration smells。
  - 來源：https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf

---

## A. 測試壞味道

名詞先講白：
- **SUT**（system under test，受測系統）＝被測的那段產品碼。
- **fixture**（測試前置資料）＝跑測試前要先準備好的物件或資料。
- **mock**（模擬物件）＝替代真實依賴、可以記錄「被怎麼呼叫」的假物件。
- **斷言**（assertion）＝測試裡「結果應該是 X」的那一行檢查。

### A1 看不懂

### Obscure Test（晦澀測試）
- 定義：讀者一眼看不出這個測試在驗證什麼行為。
- 辨識訊號：準備、執行、驗證三段交錯在一起；測試名稱說不出預期結果；要打開別的檔案（共用 setUp、資料檔）才知道輸入是什麼。Meszaros 列的成因：Eager Test、Mystery Guest、General Fixture、Irrelevant Information（無關細節淹沒重點）、Hard-Coded Test Data（字面值散落）、Indirect Testing。
- 為何有害：測試沒辦法當文件用，維護成本跟著升高；測試本身的 bug 藏在雜訊裡（會變成 Buggy Tests）；一個斷言失敗後，後面的斷言不再執行，除錯資訊就丟了。
- 解法：一個測試只驗一個條件；只留下影響結果的值，其他用 test data builder（測試資料建構器）或具名 helper 帶預設值；用 Arrange-Act-Assert（準備、執行、驗證）三段排版；名稱寫出行為和預期結果。
- 何時不算：端對端或驗收測試天生比較長，只要每一步都用具名 helper 表達、讀得出流程，就不算。
- 來源：http://xunitpatterns.com/Obscure%20Test.html

### Eager Test（貪心測試）
- 定義：一個測試方法同時驗證受測物件的好幾個方法或行為。
- 辨識訊號：一個測試呼叫 ≥2 個不同的產品方法，而且各自斷言（tsDetect 的判斷規則）；名稱含 "And" 或是 testAll、testEverything 這類泛稱。
- 為何有害：難讀，也難當文件；前面的斷言失敗會遮住後面的錯；測試之間更互相依賴，更難維護。
- 解法：用 Extract Method（抽出方法）拆成「一個行為一個測試」，名稱點出目的。
- 何時不算：一個行為本來就要好幾步呼叫才看得到（例如 push 之後 pop，驗證堆疊的先進後出）。van Deursen 也提醒：拆太細會增加 setup／teardown 的開銷。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://testsmells.org/pages/testsmells.html

### Mystery Guest（神秘客）
- 定義：測試依賴外部資源（檔案、資料庫裡的列、環境變數），但光讀測試本身看不到那份資料的內容。
- 辨識訊號：測試裡出現檔案路徑、資料庫查詢、固定 ID，而且預期值取決於這些外部資料；改一個 fixture 檔，好幾個測試一起變紅。
- 為何有害：測試不自足，沒辦法當文件；依賴是隱藏的，別人改了或刪了資源，測試就壞；共用同一資源的測試越多，越容易出事。
- 解法：Inline Resource（把資料搬回測試裡）；一定要用外部資源時，用 Setup External Resource（由測試自己建立、自己清理）。
- 何時不算：刻意寫的整合測試，而且資源由測試自己建立；或資料量大，但用具名 builder 把關鍵欄位明確寫在測試裡。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 http://xunitpatterns.com/Obscure%20Test.html 、 https://testsmells.org/pages/testsmells.html

### General Fixture（過度泛用的前置資料）
- 定義：setUp 建好一大包資料，但每個測試只用到其中一部分。
- 辨識訊號：setUp 初始化的欄位裡，有些在某些測試從來沒被讀過（tsDetect 就是用這條規則偵測）；setUp 比測試本體還長。
- 為何有害：看不出哪些資料和這個測試有關；做多餘的工作，測試變慢，開發者就不跑了（van Deursen）；很多測試共用同一份 fixture，改一處牽動一片（Meszaros 稱為 Fragile Fixture）。
- 解法：setUp 只放所有測試真正共用的部分，其餘移回各測試或抽成具名 helper；需要不同 fixture 的測試群，拆成不同的測試類別。
- 何時不算：所有測試確實都用到同一組前置資料，例如同一個 SUT 實例。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://testsmells.org/pages/testsmells.html 、 http://xunitpatterns.com/Slow%20Tests.html

### Assertion Roulette（斷言輪盤）
- 定義：一個測試裡有多個沒附說明的斷言，失敗時看不出是哪一個。
- 辨識訊號：同一測試有 ≥2 個沒帶 message 參數的斷言（tsDetect 規則）；CI 紀錄只寫 "expected true but was false"。
- 為何有害：在 CI 上失敗、本機又重現不了（例如環境問題）時，修起來慢又貴（Meszaros）。
- 解法：拆成單一條件的測試；補上斷言說明；改用會印出具體差異的斷言庫（例如 Truth、AssertJ 的物件比對）。
- 何時不算：多個斷言共同描述同一個結果，而且斷言庫失敗時會指出哪一個（例如 assertAll、soft assertions、整個物件比對）。
- 來源：http://xunitpatterns.com/Assertion%20Roulette.html 、 https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://abseil.io/resources/swe-book/html/ch12.html

### Conditional Test Logic（測試中的條件邏輯）
- 定義：測試裡有 if、switch、for、while，每次跑可能走不同路徑。
- 辨識訊號：測試方法裡的控制結構數 > 0（tsDetect 直接計數）。Meszaros 細分的成因：Flexible Test、Conditional Verification Logic、Production Logic in Test、Complex Teardown、Multiple Test Conditions。
- 為何有害：沒有人替測試寫測試；分支裡的斷言可能根本沒執行到；難以確定它到底驗了什麼；路徑不固定，除錯困難。
- 解法：拆成幾個直線式測試；用 Guard Assertion 或自訂斷言取代 if；用參數化測試取代手寫迴圈。Google 的原則是「straight-line code over clever logic」（寧可寫直線式程式，不要寫聰明的邏輯）。
- 何時不算：測試框架提供的參數化測試或表格驅動測試（框架負責展開，每一案各自回報結果）。
- 來源：http://xunitpatterns.com/Conditional%20Test%20Logic.html 、 https://abseil.io/resources/swe-book/html/ch12.html 、 https://testsmells.org/pages/testsmells.html

### Magic Number Test（魔術數字測試）
- 定義：斷言裡出現沒說明意義的數字。
- 辨識訊號：斷言參數裡有數字字面值（tsDetect 規則）。Meszaros 把它歸在 Hard-Coded Test Data，是 Obscure Test 的成因之一。
- 為何有害：讀者不知道 1810 是怎麼來的；規則改變時，不知道哪些數字要跟著改。
- 解法：用具名常數，或在名稱裡交代來源（例如 KM_FOR_1122_MILES）。不要在測試裡重算一遍產品邏輯，那樣測試會跟著產品一起錯。
- 何時不算：0、1、空字串這類一看就懂的值；或規格本身就是這個數字（例如 HTTP 404）。
- 來源：https://testsmells.org/pages/testsmells.html 、 http://xunitpatterns.com/Obscure%20Test.html 、 https://abseil.io/resources/swe-book/html/ch12.html

### Lazy Test（懶惰測試）
- 定義：好幾個測試用同一份 fixture 驗同一個產品方法，只是各看不同的欄位。
- 辨識訊號：≥2 個測試呼叫同一個產品方法，fixture 也相同（tsDetect 規則）。
- 為何有害：這些測試只有放在一起看才有意義，分散開來就讀不出完整規格。
- 解法：用 Inline Method（內聯合併）把它們合成一個。
- 何時不算：每個測試驗的是不同輸入條件下的不同行為，那分開是對的。Lazy Test 專指「同條件、同 fixture」被拆碎；和 Eager Test 是互相拉扯的兩端。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://testsmells.org/pages/testsmells.html

### Test Code Duplication（測試碼重複）
- 定義：同一段準備或驗證程式碼，在多個測試裡（或同一測試裡）一再出現。
- 辨識訊號：複製貼上的 setup 區塊。Meszaros 列的成因：Cut-and-Paste Code Reuse（複製貼上重用），以及 Reinventing the Wheel（不知道已經有 helper）。van Deursen 另舉 test implication（測試蘊含）：A 失敗若且唯若 B 失敗，兩者其實測同一段碼。
- 為何有害：產品介面一改，要改 N 個地方，會變成 High Test Maintenance Cost。
- 解法：抽成 Creation Method（建立物件的 helper）或自訂斷言；跨類別抽共用 helper 時，留意會引入測試之間的依賴（van Deursen 的警告）。
- 何時不算：Google 主張測試要「DAMP, not DRY」（DAMP＝描述性、有意義的語句；DRY＝不重複）：少量重複如果讓每個測試自成一體、更好讀，是可以接受的。不要為了去重，把關鍵輸入藏進 helper，那樣就變成 Mystery Guest。
- 來源：http://xunitpatterns.com/Test%20Code%20Duplication.html 、 https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://abseil.io/resources/swe-book/html/ch12.html

### Readability-Blind Testing（只看抓不抓得到 bug、不看可讀性）〔部分查證：非文獻固定名稱，是依來源整理的合成條目〕
- 定義：評價測試只問「能不能抓到 bug、有沒有綠」，不檢查測試是否清楚到可以當規格讀。
- 辨識訊號：code review 只看產品碼，測試檔整批略過；測試名稱是 test1、testFoo；失敗訊息只有 true／false；新人要問人才知道某個測試在保護什麼。
- 為何有害：Meszaros 指出 Obscure Test 會讓測試沒辦法當文件，進而墊高維護成本，也讓測試自身的 bug 溜過。Google 要求測試同時「complete」（該有的資訊都在）和「concise」（沒有分散注意力的資訊），測試名稱要能讓人不看程式碼就判斷失敗原因。
- 解法：把測試納入 review 範圍；用「名稱寫行為、本體三段式、失敗訊息寫出預期與實際」當檢查清單；以行為來組織測試，而不是以方法（given／when／then）。
- 何時不算：一次性的探索性 spike（技術驗證原型）測試，用完即丟。
- 來源：https://abseil.io/resources/swe-book/html/ch12.html 、 http://xunitpatterns.com/Obscure%20Test.html

### A2 會騙人

### Unknown Test（不明測試）
- 定義：測試方法裡沒有任何斷言，也沒宣告預期的例外。
- 辨識訊號：斷言數 = 0，而且沒有 @Test(expected) 或 assertThrows（tsDetect 規則）。
- 為何有害：只要不丟例外就綠燈，實際上什麼都沒驗；看不出預期結果。
- 解法：補斷言；如果本意就是「不丟例外」，明寫 assertDoesNotThrow 或等價寫法。
- 何時不算：刻意只驗「跑得完」的 smoke test（冒煙測試），但要在名稱和寫法上明示。
- 來源：https://testsmells.org/pages/testsmells.html

### Empty Test（空測試）
- 定義：測試方法裡沒有可執行的敘述（常見是整段被註解掉），卻回報通過。
- 辨識訊號：方法本體只有註解或空白（tsDetect 規則）。
- 為何有害：綠燈是假的，誤以為有覆蓋。
- 解法：補完或刪除；暫停一個測試應該用框架的 skip 機制並附原因，不要把內容掏空。
- 何時不算：幾乎沒有。框架產生的佔位測試也該在提交前處理掉。
- 來源：https://testsmells.org/pages/testsmells.html

### Redundant Assertion（多餘斷言）
- 定義：斷言的預期值和實際值是同一個東西，永遠成立（或永遠不成立）。
- 辨識訊號：assertEquals(true, true)、assertEquals(x, x) 這類寫法（tsDetect 規則）。
- 為何有害：看起來有驗，其實沒驗；常是除錯時留下的殘骸。
- 解法：刪掉，或改成真正比對產品輸出。
- 何時不算：無。
- 來源：https://testsmells.org/pages/testsmells.html

### Ignored Test（被忽略的測試）
- 定義：被 @Ignore、@Disabled、skip 標記而不執行的測試。
- 辨識訊號：skip 標記數量；被跳過的時間長度（用 git blame 看）；有沒有附原因。
- 為何有害：增加編譯負擔和程式碼複雜度（testsmells.org）；長期跳過等於 Meszaros 說的 Lost Test（測試遺失），bug 會從這裡漏到正式環境。
- 解法：修好或刪除；暫時跳過要寫明原因、追蹤單號和期限；Fowler 建議把不穩定測試「隔離」，但要設上限（例如最多 8 個或最多一週）。
- 何時不算：有條件的跳過，例如只在特定平台跑，而且條件寫在程式碼裡。
- 來源：https://testsmells.org/pages/testsmells.html 、 http://xunitpatterns.com/Production%20Bugs.html 、 https://martinfowler.com/articles/nonDeterminism.html

### Exception Handling（測試自己處理例外）
- 定義：測試用自寫的 try／catch 或 throw 處理例外，而不是用框架內建的例外斷言。
- 辨識訊號：測試方法裡有 try／catch 或 throw 敘述（tsDetect 規則）。
- 為何有害：catch 很容易把失敗吞掉，測試因此誤綠；意圖也比框架寫法難讀。
- 解法：改用 assertThrows、pytest.raises 這類框架寫法。
- 何時不算：要驗證例外物件的多個屬性，而框架寫法表達不了（新框架通常可以，例如 assertThrows 會回傳例外物件）。
- 來源：https://testsmells.org/pages/testsmells.html

### Duplicate Assert（重複斷言）
- 定義：同一個測試裡對同一個條件斷言好幾次。
- 辨識訊號：同一測試內出現參數完全相同的斷言（tsDetect 規則）。
- 為何有害：雜訊；常代表這個測試其實在驗好幾個情境，應該拆開。
- 解法：刪掉重複的；如果是不同情境，拆成不同測試。
- 何時不算：同一個屬性在狀態改變前、後各驗一次（時間點不同，意義也不同）。
- 來源：https://testsmells.org/pages/testsmells.html

### Redundant Print（多餘輸出）
- 定義：測試裡留著 print 或 console 輸出。
- 辨識訊號：測試碼裡的 print、System.out、console.log 呼叫數。
- 為何有害：自動化執行時沒人看；拖慢速度、製造雜訊；是除錯完忘記清掉的殘留。
- 解法：刪掉；需要診斷資訊就放進斷言的失敗訊息裡。
- 何時不算：框架會擷取輸出、只在失敗時顯示的寫法（例如 pytest 預設擷取 stdout），而且內容有診斷價值。
- 來源：https://testsmells.org/pages/testsmells.html

### Buggy Tests（有 bug 的測試）
- 定義：測試本身有錯，產品沒壞它說壞，或產品壞了它說沒壞。
- 辨識訊號：建置因測試失敗，但查下去產品碼是對的；正式環境出了 bug，明明有測試涵蓋那個情境卻沒抓到。
- 為何有害：Meszaros：該紅不紅（false negative）給人虛假的安全感；不該紅卻紅（false positive）讓測試失去公信力，像放羊的孩子喊「狼來了」，幾次之後大家就不理了。
- 解法：處理它的成因：Fragile Test、Obscure Test、Hard-to-Test Code；測試寫完先看它紅一次（先失敗再修好），確認它真的會抓到錯。
- 何時不算：無。
- 來源：http://xunitpatterns.com/Buggy%20Tests.html

### A3 不穩定

### Erratic Test（不穩定測試；flaky test）
- 定義：同一個測試，有時過、有時不過，或換個人、換個環境就不同結果。
- 辨識訊號：重跑就綠；只在 CI 失敗；只在全套一起跑時失敗；結果和執行順序、時間有關。Meszaros 列的成因：Interacting Tests（測試互相影響）、Interacting Test Suites、Lonely Test（單獨跑才會壞或才會過）、Resource Leakage（資源洩漏）、Resource Optimism、Unrepeatable Test（第一次跑和之後跑結果不同）、Test Run War、Nondeterministic Test（用了隨機或時間）。
- 為何有害：大家會想把它移出測試集來「保持綠燈」，結果變成 Lost Test；留著的話，已知的失敗又會遮住新的失敗。
- 解法：Fowler 的五大成因對策：測試彼此隔離、非同步改用 callback 或輪詢（不要用 sleep）、遠端服務用測試替身取代、把系統時鐘包起來好讓測試替換、找出資源洩漏（測試時把連線池設成 1，問題會立刻浮現）；暫時隔離時要設數量和時間上限。
- 何時不算：無。即使是外部依賴造成的，也該改成可控的。
- 來源：http://xunitpatterns.com/Erratic%20Test.html 、 https://martinfowler.com/articles/nonDeterminism.html

### Interacting Tests（互相干擾的測試）
- 定義：一個測試的結果，取決於別的測試先跑過沒有、留下了什麼。
- 辨識訊號：改變執行順序（例如隨機排序）或單獨執行，結果就變；共用 static 變數、單例或同一張資料表。
- 為何有害：是 Erratic Test 最常見的成因；拿掉或新增一個測試，另一個就壞。
- 解法：每個測試自己建立並清理需要的狀態（Fresh Fixture，每次新建的前置資料）；避免共用可變狀態；資料庫測試用交易回滾或唯一前綴。
- 何時不算：刻意設計成有序的情境流程測試，而且框架明確保證執行順序。
- 來源：http://xunitpatterns.com/Erratic%20Test.html 、 https://martinfowler.com/articles/nonDeterminism.html

### Resource Optimism（資源樂觀）
- 定義：測試樂觀假設外部資源（目錄、檔案、資料表）一定存在或一定不存在，狀態也剛好對。
- 辨識訊號：使用檔案前不檢查是否存在（tsDetect 規則：用 File 卻沒呼叫 exists()、isFile()）；某台機器上才失敗。
- 為何有害：結果不確定，有時跑得好好的，有時一敗塗地（van Deursen）。
- 解法：Setup External Resource，由測試自己配置、初始化所有用到的資源。
- 何時不算：資源由框架保證存在，例如框架提供的暫存目錄。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://testsmells.org/pages/testsmells.html 、 http://xunitpatterns.com/Erratic%20Test.html

### Test Run War（測試執行戰爭）
- 定義：只有一個人跑時都正常，多人或多個 CI 工作同時跑就互相打架。
- 辨識訊號：並行執行時才失敗；測試使用固定名稱的暫存檔、固定 port、共用資料庫。
- 為何有害：失敗看似隨機，很難重現。
- 解法：Make Resource Unique（每次執行用唯一的資源名稱或路徑）；每個執行者用獨立的資料庫或 schema。
- 何時不算：無。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 http://xunitpatterns.com/Erratic%20Test.html

### Sleepy Test（嗜睡測試）
- 定義：用 sleep 等待非同步結果。
- 辨識訊號：測試裡呼叫 Thread.sleep、time.sleep、setTimeout 等待（tsDetect 規則）。
- 為何有害：在不同機器上，同樣的等待時間可能不夠或太長，結果不可預測；Fowler：光用 sleep 既浪費時間，又照樣會隨機失敗。
- 解法：Fowler：「Never use bare sleeps to wait for asynchronous responses: use a callback or polling.」優先用 callback，其次是附逾時的輪詢；或把時鐘、排程器換成可控的測試替身。
- 何時不算：受測行為本身就是「等待 N 秒」，例如節流或逾時，而且時鐘已經可控。
- 來源：https://testsmells.org/pages/testsmells.html 、 https://martinfowler.com/articles/nonDeterminism.html

### A4 太黏實作

### Fragile Test（脆弱測試）
- 定義：產品碼做了不影響受測部分的修改，測試卻編譯失敗或執行失敗。
- 辨識訊號：一個不改行為的重構讓 N 個測試變紅；壞掉的測試有共同點（同一個介面、同一份 fixture、同一筆資料）。Meszaros 的「四種敏感」：Interface Sensitivity（介面敏感）、Behavior Sensitivity（行為敏感）、Data Sensitivity（資料敏感）、Context Sensitivity（環境敏感，例如時間或主機）；其他成因：Overspecified Software（又稱 Overcoupled Test，過度指定）、Sensitive Equality、Fragile Fixture。
- 為何有害：每次修改都得回頭修很多測試，維護成本暴增，對頻繁小步交付的專案特別致命；Google 的定義是「在不相關的修改下失敗、卻沒有引入真 bug」，會持續耗掉工程師的生產力。
- 解法：只透過公開 API 測試；驗狀態而不是驗互動；用 helper 隔開建構細節（介面一改只動一處）；把時間、亂數等環境因素注入。
- 何時不算：產品的行為規格真的改了，測試跟著改是應該的。
- 來源：http://xunitpatterns.com/Fragile%20Test.html 、 https://abseil.io/resources/swe-book/html/ch12.html

### Over-mocking / Overspecified Software（過度 mock、過度指定）
- 定義：大量用 mock 取代依賴，並斷言「哪個方法被用什麼參數呼叫了幾次」，而不是驗證結果。
- 辨識訊號：一個測試裡 mock 數 ≥ 被測物件的依賴數；verify(...)、assert_called_with 的數量多於檢查結果的斷言；替不是自己擁有的型別（第三方函式庫）建 mock。
- 為何有害：Google 的經驗：這類測試寫起來容易，但「required constant effort to maintain while rarely finding bugs」（得一直花力氣維護，卻很少抓到 bug）；互動測試只能證明某些函式被呼叫了，不能證明系統正確。
- 解法：Google 的優先順序：真實實作 > fake（輕量但能用的替代實作）> stub／mock；預設驗狀態；互動測試只驗必要的最小行為；不要 mock 你不擁有的型別，改成包一層自己的 wrapper 再 mock 那層。
- 何時不算：真實實作和 fake 都不可用時；或「呼叫次數」本身就是規格（例如驗證快取確實減少了資料庫存取）。
- 來源：https://abseil.io/resources/swe-book/html/ch13.html 、 http://xunitpatterns.com/Fragile%20Test.html 、 https://testing.googleblog.com/2020/07/testing-on-toilet-dont-mock-types-you.html（最後這篇只看過搜尋摘要）

### Testing Implementation, Not Behavior／Change-Detector Test（測實作不測行為／變更偵測器測試）
- 定義：測試驗證的是程式碼「怎麼做」（內部呼叫順序、私有方法、資料結構），而不是對使用者「做出什麼」。
- 辨識訊號：測試直接呼叫私有方法或透過反射取私有欄位；mock 掉所有依賴，然後逐一驗證呼叫；每次重構都要同步改測試，而產品行為沒變。
- 為何有害：Google：這種測試不增加任何清晰度、讓你無法安全重構，而且因為什麼都 mock 掉了，真正的邏輯改壞了它照樣通過。
- 解法：只透過公開 API，以使用者的方式呼叫；「如果使用者可見的行為沒變，測試本身通常不該需要修改」；以行為來組織測試。
- 何時不算：底層演算法模組的公開介面本身就是「實作細節」（例如排序函式庫，其行為就是排序結果）。
- 來源：https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html 、 https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html 、 https://abseil.io/resources/swe-book/html/ch12.html

### Sensitive Equality（敏感的相等比較）
- 定義：用 toString() 之類的字串輸出來判斷物件是否相等。
- 辨識訊號：斷言裡出現 toString()（tsDetect 規則）；整串比對序列化後的 JSON 字串。
- 為何有害：逗號、引號、空白、欄位順序這些無關細節一改，測試就紅，是 Fragile Test 的成因之一。
- 解法：Introduce Equality Method（定義真正的相等比較）或逐欄位比對；JSON 先解析再比對結構。
- 何時不算：受測行為本身就是字串格式（formatter、序列化器），這時字串就是規格；刻意比對完整輸出的 golden file（標準答案檔）或 snapshot 測試。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 https://testsmells.org/pages/testsmells.html 、 http://xunitpatterns.com/Fragile%20Test.html

### Indirect Testing（間接測試）
- 定義：A 的測試類別，其實在透過 A 測 B 的功能。
- 辨識訊號：測試類別名稱對應 A，斷言卻針對 A 參考到的其他物件。
- 為何有害：從高層去測很難照顧到低層每個可能壞的地方，理解和除錯都更難；也透露產品碼的資訊隱藏可能有問題（van Deursen）。
- 解法：把那部分抽出來，移到 B 自己的測試類別。
- 何時不算：van Deursen 也承認這點見仁見智：有人刻意從高層測，以免低層類別一改測試就壞。如果團隊選擇只透過公開 API 測（呼應 Google 的建議），經由上層驗證下層行為是合理的。
- 來源：https://ir.cwi.nl/pub/4324/04324D.pdf 、 http://xunitpatterns.com/Obscure%20Test.html

### A5 太貴

### Slow Tests（慢測試）
- 定義：測試慢到開發者不會每次改完就跑。
- 辨識訊號：大家等休息時間才跑測試；單元測試套件的牆鐘時間超過一杯咖啡（Meszaros 的描述，沒給數字）；有人在 CI 上跳過測試。成因：Slow Component Usage（用到慢元件，例如真實資料庫）、General Fixture、Asynchronous Test（非同步等待）、Too Many Tests。
- 為何有害：直接成本是等待；間接成本是回饋變慢，從引入錯誤到發現錯誤的時間拉長，除錯更難。
- 解法：慢元件（例如資料庫）換成 Fake Object；縮小 fixture；把非同步邏輯拆成可同步測試的部分（Humble Object 模式，把難測的外殼做到最薄）；把測試分層，快的每次跑、慢的在 CI 跑。注意：常見反應是改用 Shared Fixture（共用前置資料），但 Meszaros 指出這幾乎總會換來 Erratic Test。
- 何時不算：刻意分出的端對端測試層，本來就預期慢，而且不在開發迴圈裡跑。
- 來源：http://xunitpatterns.com/Slow%20Tests.html

### Manual Intervention（需要人手介入）
- 定義：跑測試前或跑到一半要有人手動操作，或要人用眼睛確認結果。
- 辨識訊號：測試說明寫著「先手動啟動 X」「看一下輸出對不對」。成因：Manual Fixture Setup（手動準備前置資料）、Manual Result Verification（手動驗證結果）、Manual Event Injection（手動觸發事件）。
- 為何有害：回饋成本太高，大家就不常跑；也沒辦法做全自動的整合建置。
- 解法：自動化準備步驟；把肉眼確認改成斷言；用程式注入事件。
- 何時不算：刻意的探索式測試或 UX 驗收，那不屬於自動化測試的範疇。
- 來源：http://xunitpatterns.com/Manual%20Intervention.html

### Frequent Debugging（經常需要除錯）
- 定義：大多數測試失敗時，光看輸出判斷不出問題，必須開除錯器或到處加 print。
- 辨識訊號：「每次紅燈都要開 debugger」是常態，不是例外。
- 為何有害：抵消了自動化測試快速定位問題的價值。
- 解法：測試要小、要只驗一個條件；失敗訊息要寫出預期與實際；更常跑測試，讓每次失敗只對應少量變動。
- 何時不算：偶發的情況（Meszaros：如果只是例外，不必擔心）。
- 來源：http://xunitpatterns.com/Frequent%20Debugging.html

### High Test Maintenance Cost（測試維護成本過高）
- 定義：每加一個新功能，就得大改既有測試，新功能開發因此變慢。
- 辨識訊號：分開記帳的話，花在修改舊測試的時間多於寫新程式碼的時間；團隊要求排一個「測試整理迭代」；伴隨 Fragile Test、Fragile Fixture、Erratic Test 等症狀。
- 為何有害：生產力下降；大家開始主張刪測試，因為寫產品碼是必須的，維護測試卻被誤當成可有可無。
- 解法：處理底下的成因（Fragile Test、Obscure Test、Hard-to-Test Code）。
- 何時不算：需求本身大改，測試跟著大改是正當的。
- 來源：http://xunitpatterns.com/High%20Test%20Maintenance%20Cost.html

### A6 測試滲入產品碼

### Test Logic in Production（產品碼裡的測試邏輯；van Deursen 稱 For Testers Only）
- 定義：產品碼裡有只為了測試才存在的邏輯，或偵測到「正在被測試」就改變行為。
- 辨識訊號：`if (testing) { return hardCodedCannedData; }` 這類分支；只被測試呼叫的方法，名稱或註解寫著「僅供測試」。Meszaros 列的成因：Test Hook（測試掛鉤）、For Tests Only、Test Dependency in Production（產品碼依賴測試模組）、Equality Pollution（為了測試在產品類別加 equals）。
- 為何有害：正式環境和測試環境行為不同，等於災難的配方。如果設定錯了，測試路徑可能在正式環境被執行（Meszaros 以 Ariane 5 火箭失事為例：只該在地面跑的程式碼在飛行中繼續執行）。
- 解法：用依賴注入或測試替身取代 if (testing)；把僅供測試的方法移到測試碼裡的子類別（van Deursen：Extract Subclass）；相等比較放在測試端的自訂斷言。
- 何時不算：為了可測性做的正當設計（依賴注入的建構子、可替換的時鐘介面），它在正式環境也有用途，不是「只為測試」。
- 來源：http://xunitpatterns.com/Test%20Logic%20in%20Production.html 、 https://ir.cwi.nl/pub/4324/04324D.pdf

### A7 專案層

### Hard-to-Test Code（難測的程式碼）
- 定義：程式碼結構讓它很難寫自動化測試。
- 辨識訊號：要測一個類別，得連帶建好幾個其他類別；建構子是 private，或參數一大堆；邏輯和執行緒、行程、GUI 綁死，測試得啟動整個程式再等它就緒。成因：Highly Coupled Code（高耦合，又稱 Hard-Coded Dependency）、Asynchronous Code（非同步程式碼）、Untestable Test Code。
- 為何有害：品質沒辦法自動驗證，只能靠人工，而人工驗證不能規模化，改一次就要重做。
- 解法：解開耦合（用測試替身）；把邏輯和非同步外殼分開（Humble Object：外殼做到最薄、邏輯可同步測）；舊系統參考 Feathers《Working Effectively with Legacy Code》的技巧。
- 何時不算：極薄的整合層（只轉接到外部系統），交給整合測試涵蓋。
- 來源：http://xunitpatterns.com/Hard%20to%20Test%20Code.html

### Developers Not Writing Tests（開發者不寫測試）
- 定義：團隊沒有為會出錯的程式碼寫自動化測試。
- 辨識訊號：bug 漏到後段時，被告知「那部分沒有測試」；新程式碼的 PR 不附測試。成因：Not Enough Time（沒時間）、Hard to Test Code、Wrong Test Automation Strategy（自動化策略錯誤）。
- 為何有害：累積「測試債」，加功能越來越慢；重構變得危險，最後沒人敢重構。
- 解法：處理成因：用 TDD（測試驅動開發）把測試成本攤進開發；先處理難測的結構；選對自動化層級。
- 何時不算：一次性腳本、確定丟棄的原型。
- 來源：http://xunitpatterns.com/Developers%20Not%20Writing%20Tests.html

### No Test Suite（無測試專案）
- 定義：整個專案沒有可自動執行的測試，或測試早已不能執行。
- 辨識訊號：測試目錄不存在或是空的；CI 沒有測試步驟；測試指令跑不起來；Feathers 的定義：沒有測試的程式碼就是 legacy code（遺留程式碼）。
- 為何有害：Feathers 一書的前提是，沒有測試覆蓋就無法有效修改程式碼，每次修改都是賭博。
- 解法：先在要改的地方補 characterization test（特性測試：先記錄現在的行為，不判斷對錯），再改；從最常改、最常出 bug 的區塊開始；把測試步驟放進 CI，紅燈就擋。
- 何時不算：確定不再修改的封存程式碼；生命週期很短的一次性工具。
- 來源：https://www.spinellis.gr/pubs/Breview/2005-CR-Legacy/html/review.html 、 http://xunitpatterns.com/Developers%20Not%20Writing%20Tests.html

### Production Bugs（正式環境 bug 過多）
- 定義：投入了自動化測試，系統測試或正式環境的 bug 數量還是太高。
- 辨識訊號：逃逸缺陷率（正式環境 bug 數／總 bug 數）偏高或上升。Meszaros 列的成因：Infrequently Run Tests（不常跑）、Lost Test（測試遺失或被跳過）、Missing Unit Test、Untested Code、Untested Requirement（沒測到的需求）、Neverfail Test（永遠不會失敗的測試）。
- 為何有害：越晚發現的 bug 越貴，可能延誤出貨、損及信譽。
- 解法：依成因處理：把測試掛進 CI 每次跑；清點被 skip 的測試；補需求層級的驗收測試；檢查是否有永遠不會失敗的測試（可以用 mutation testing，故意改壞產品碼看測試會不會紅）〔mutation testing 這部分未查證〕。
- 何時不算：無。
- 來源：http://xunitpatterns.com/Production%20Bugs.html

### A8 測試框架用法小味道（tsDetect 規則）

### Constructor Initialization（用建構子初始化測試）
- 定義：測試類別用建構子而不是 setUp 方法準備狀態。
- 辨識訊號：測試類別有自訂建構子（tsDetect 規則）。
- 為何有害：違反框架的生命週期慣例；部分框架的建構時機和 setUp 不同，可能造成狀態共用或錯誤難以追蹤。
- 解法：搬到 setUp／@BeforeEach。
- 何時不算：框架本身就以建構子作為每個測試的初始化點（例如 xUnit.net 每個測試都新建一個測試類別實例）〔這個框架例外未查證〕。
- 來源：https://testsmells.org/pages/testsmells.html

### Default Test（預設範本測試）
- 定義：工具自動產生的範例測試類別（例如 Android 的 ExampleUnitTest）沒刪也沒改名。
- 辨識訊號：存在框架範本的類別名稱和範例斷言（tsDetect 規則）。
- 為何有害：容易變成什麼都往裡丟的雜物箱。
- 解法：刪除，或改名成有意義的測試類別。
- 何時不算：無。
- 來源：https://testsmells.org/pages/testsmells.html

---

## B. 資料與 SQL 壞味道

名詞先講白：
- **外鍵**（foreign key）＝資料庫層強制「這個欄位的值必須存在於另一張表」的約束。
- **正規化**（normalization）＝把資料拆表，讓每個事實只存一次。
- **ORM**（Object-Relational Mapping，物件關聯對映）＝把資料表當成程式物件來操作的函式庫，例如 Hibernate、Django ORM、Rails Active Record。

> Karwin 條目的查證說明：每章的「Objective（目標）／Antipattern（反模式）／Solution（解法）」三個名稱，逐字取自 2010 年版目錄（http://media.pragprog.com/titles/bksqla/toc.pdf，已查證）。辨識訊號裡標 ★ 的句子，取自出版社公開的試讀章節原文；其餘辨識訊號與「何時不算」是依章節主旨整理的通行做法，**沒有逐字核對原書**，屬〔部分查證〕。

Sharma 2018 schema smells 與 Karwin 的對照：
- Compound attribute ≈ Jaywalking
- Adjacency list ≈ Naive Trees
- Superfluous key ≈ ID Required
- Missing constraints ≈ Keyless Entry
- Metadata as data ≈ EAV
- Polymorphic association ＝ Polymorphic Associations
- Multicolumn attribute ＝ Multicolumn Attributes
- Clone tables ≈ Metadata Tribbles
- Values in attribute definition ≈ 31 Flavors
- Index abuse ≈ Index Shotgun
- Sharma 獨有：God table、Meaningless name、Overloaded attribute names

### B1 邏輯設計

### Jaywalking（亂穿馬路：逗號分隔清單）
- 定義：把多個值用逗號串成一個字串，塞進同一個欄位。目標「Store Multivalue Attributes」／反模式「Format Comma-Separated Lists」／解法「Create an Intersection Table」。
- 辨識訊號：VARCHAR 欄位存 '10,14,18' 這類 ID 清單；查詢用 LIKE '%,14,%' 或 REGEXP 比對。★ 團隊裡出現這些問題就是線索：「這個清單最多要支援幾筆？」「SQL 怎麼比對單字邊界？」「哪個字元絕對不會出現在清單項目裡？」
- 為何有害：沒辦法用外鍵保證 ID 有效；查詢沒辦法用索引；加總、計數、更新都要解析字串；欄位長度限制了清單長度；分隔字元可能出現在值裡。
- 解法：建立交叉表（intersection table，又稱關聯表），一列一個關聯。
- 何時不算：清單只是整體存取、從不個別查詢或約束的不透明資料（例如原樣保存的外部輸入）；為了效能刻意反正規化，而且有同步機制。
- 來源：https://media.pragprog.com/titles/bksap1/jaywalking.pdf 、 http://media.pragprog.com/titles/bksqla/toc.pdf

### Naive Trees（天真樹：只存父節點）
- 定義：階層資料只在每一列存 parent_id（Adjacency List，鄰接串列），卻需要查整棵子樹或所有祖先。目標「Store and Query Hierarchies」／反模式「Always Depend on One's Parent」／解法「Use Alternative Tree Models」。
- 辨識訊號：★「樹要支援幾層？」（只能固定層數 JOIN）；★「我很怕碰管理樹狀結構的那段程式碼」；★「得定期跑腳本清掉樹裡的孤兒節點」。
- 為何有害：沒有遞迴查詢時，查任意深度要多次往返；刪除非葉節點會留下孤兒節點。
- 解法：依用途選樹模型：Path Enumeration（路徑列舉）、Nested Sets（巢狀集合）、Closure Table（閉包表）；或使用 SQL-99 的遞迴 CTE（WITH RECURSIVE）。
- 何時不算：★ 只需要取直接的父或子節點、插入容易就好時，Adjacency List 完全夠用；Karwin 也自述曾為了「理論上任意深度」花了好幾週，實際上從來只用到一層。
- 來源：http://media.pragprog.com/titles/bksqla/trees.pdf

### ID Required（一律要 id 主鍵）〔部分查證〕
- 定義：不管合不合適，每張表都放一個名叫 id 的自動遞增代理鍵（surrogate key，沒有業務意義的流水號主鍵）。目標「Establish Primary Key Conventions」／反模式「One Size Fits All」／解法「Tailored to Fit」。
- 辨識訊號：交叉表也有 id，而 (a_id, b_id) 沒有唯一約束，結果允許重複關聯；表裡已有天然唯一欄位（例如 ISO 代碼）卻沒宣告成鍵；每張表的主鍵都叫 id，JOIN 時欄位名稱撞名。Sharma 2018 稱為 Superfluous key（多餘的鍵）。
- 為何有害：多餘的鍵讓重複資料溜進來；欄位名稱沒有語意，JOIN 容易接錯。
- 解法：依表選鍵：天然鍵、複合鍵或代理鍵；代理鍵命名要有語意（bug_id）；交叉表用複合主鍵或加唯一約束。
- 何時不算：ORM 慣例要求單一代理鍵，而且天然鍵可能改變時，用代理鍵很合理，但仍要對天然唯一欄位加 UNIQUE。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Keyless Entry（無鑰匙進入：不宣告外鍵）〔部分查證〕
- 定義：為了「簡化」或擔心效能，不宣告外鍵約束，把參照完整性交給應用程式碼。目標「Simplify Database Architecture」／反模式「Leave Out the Constraints」／解法「Declare Constraints」。
- 辨識訊號：schema 裡外鍵約束數 = 0，或明顯少於 *_id 欄位數；有定期清理孤兒資料的腳本；Sharma 2018 稱為 Missing constraints，在問卷中 77% 的受訪者認為這是壞味道。
- 為何有害：每個寫入路徑都得自己檢查，任何一條漏掉就留下壞資料；修復要寫品質檢查腳本，永遠在追趕。
- 解法：宣告外鍵，善用 ON DELETE／ON UPDATE CASCADE 等動作。
- 何時不算：資料庫引擎不支援外鍵（例如部分 MySQL 儲存引擎）；跨資料庫或分片後確實無法宣告，這時要有替代的一致性機制。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Entity-Attribute-Value（實體-屬性-值，EAV）〔部分查證〕
- 定義：用一張通用表 (entity_id, attr_name, attr_value) 存所有可變屬性。目標「Support Variable Attributes」／反模式「Use a Generic Attribute Table」／解法「Model the Subtypes」。
- 辨識訊號：表只有大約三個欄位，其中兩個是 VARCHAR（Sharma 2018 對 Metadata as data 的偵測規則）；查一個實體要 pivot（把多列轉成多欄）或多次自我 JOIN；attr_value 一律存字串。
- 為何有害：沒辦法對個別屬性設 NOT NULL、型別、外鍵；屬性名稱拼錯也不會被擋；重組一筆資料的查詢又長又慢。
- 解法：建模子型別：Single Table Inheritance（單表繼承）、Concrete Table Inheritance（具體表繼承）、Class Table Inheritance（類別表繼承）；或用半結構化欄位（見下方 Opaque Blob 條目）。
- 何時不算：屬性在執行期才由使用者定義，而且很少需要約束或查詢（例如設定項、使用者自訂標籤）；也可以考慮改用文件型資料庫。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Polymorphic Associations（多型關聯）〔部分查證〕
- 定義：一個外鍵欄位依另一個「型別」欄位的值，指向不同的父表。目標「Reference Multiple Parents」／反模式「Use Dual-Purpose Foreign Key」／解法「Simplify the Relationship」。
- 辨識訊號：(commentable_type, commentable_id) 這種欄位組合，型別欄位存的是表名字串。
- 為何有害：沒辦法宣告外鍵，參照完整性全靠應用程式；JOIN 要依型別分支。
- 解法：每種父表各一張交叉表；或建一個共同的上層父表（super-table），讓各父表繼承它的主鍵。
- 何時不算：ORM 框架原生支援，而且團隊接受由應用程式維持完整性（例如 Rails 的 polymorphic），但要清楚這個取捨。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Multicolumn Attributes（多欄位屬性）〔部分查證〕
- 定義：用 tag1、tag2、tag3 這類編號欄位存同一種屬性的多個值。目標「Store Multivalue Attributes」／反模式「Create Multiple Columns」／解法「Create Dependent Table」。
- 辨識訊號：同一張表有 ≥2 個「名稱＋數字」的欄位（Sharma 2018 的偵測規則）。
- 為何有害：查詢要對每個欄位都寫 OR；去重和唯一性難保證；超過欄位數就要改 schema。
- 解法：建一張從屬表，一個值一列。
- 何時不算：欄位雖然編號，但語意各不相同（例如地址第 1 行、第 2 行）。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Metadata Tribbles（元資料分裂：複製表或欄）〔部分查證〕
- 定義：把資料值編進表名或欄名，例如 sales_2023、sales_2024，或 revenue_2023 欄位。目標「Support Scalability」／反模式「Clone Tables or Columns」／解法「Partition and Normalize」。
- 辨識訊號：資料庫裡有 ≥2 張「表名＋數字」的表（Sharma 2018 的偵測規則）；每年或每個客戶都要手動建新表；跨期查詢要 UNION 一長串。
- 為何有害：schema 隨資料成長；跨表的唯一性和完整性難保證；查詢要動態組表名。Sharma 發現，工業專案只要出現 clone table，通常也伴隨其他壞味道。
- 解法：用資料庫的分割功能（水平分割，依列切）或垂直分割（依欄切）；把年份等值放回欄位。
- 何時不算：刻意的封存表（把舊資料移出、平常不查）；或有明確的多租戶隔離需求，而且用自動化管理。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### God Table（上帝表）
- 定義：一張表塞了過多欄位，承載好幾種概念。
- 辨識訊號：欄位數超過門檻；Sharma 的 DbDeo 工具以 10 個欄位為門檻，作者自承這只是目前採用的值。
- 為何有害：容易違反正規化，引入更新異常；難以維護。
- 解法：依概念拆表（一對一或一對多從屬表）。
- 何時不算：刻意反正規化的報表或寬表（資料倉儲的事實表或扁平化視圖）；或欄位確實都依賴同一個鍵、語意單一。
- 來源：https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Overloaded Attribute Names（同名不同型的欄位）
- 定義：不同表裡有同名欄位，型別卻不同。
- 辨識訊號：同一個欄位名稱在 ≥2 張表中定義成不同的資料型別（Sharma 的偵測規則）。
- 為何有害：造成混淆，查詢中可能出現隱性型別轉換的細微 bug。
- 解法：統一型別，或改名以區分語意。
- 何時不算：語意本來就不同、只是剛好同名（例如 status），但最好還是改名。
- 來源：https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Meaningless Name（無意義的名稱）
- 定義：表名或欄位名稱晦澀、沒有意義（例如 t1、col_a、flag2）。
- 辨識訊號：名稱是縮寫或編號，要查文件或問人才懂；Sharma 問卷中 83% 的受訪者認為這是壞味道，是比例最高的一項。
- 為何有害：schema 難讀，查詢容易寫錯。
- 解法：改成描述內容的名稱，必要時用 view 過渡。
- 何時不算：業界通行的縮寫（例如 sku、iso_code）。
- 來源：https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf

### Opaque Blob for Structured Data（把結構化資料塞成單一 blob 或 JSON）〔部分查證：非 Karwin 或 Sharma 的命名，是依 PostgreSQL 官方文件整理的合成條目〕
- 定義：把需要查詢、約束或個別更新的結構化資料，整包存成 JSON、XML 或序列化物件，放進一個欄位。
- 辨識訊號：查詢要解析 JSON 才能篩選；用 LIKE 搜 JSON 文字；各列的 key 結構不一致；只改一個巢狀欄位也要整包讀寫；存的是特定語言的序列化格式（例如 pickle），其他語言讀不了。
- 為何有害：PostgreSQL 官方建議：即使追求彈性，JSON 也應有「somewhat fixed structure」（大致固定的結構），否則難以做彙總查詢；任何更新都會鎖住整列，大文件會增加鎖競爭；理想上每份 JSON 應是業務上不能再細分、不會被獨立修改的單位。另外，型別、外鍵、NOT NULL 都無法套用。
- 解法：常查詢、常約束、常單獨更新的欄位升級成正式欄位，其餘留在 JSON；JSON 保持固定結構；控制文件大小；必要時加 JSON schema 檢查或對特定 key 建索引。
- 何時不算：真正不透明的負載（原樣保存的 webhook 內容、稽核快照）；稀疏、不查詢的可變屬性。PostgreSQL 文件也說兩種模型可以在同一個應用中並存互補。
- 來源：https://www.postgresql.org/docs/current/datatype-json.html

### B2 實體設計

### Rounding Errors（捨入誤差）〔部分查證〕
- 定義：用 FLOAT 或 DOUBLE 存需要精確的小數，例如金額。目標「Use Fractional Numbers Instead of Integers」／反模式「Use FLOAT Data Type」／解法「Use NUMERIC Data Type」。
- 辨識訊號：金額、匯率、數量欄位是 FLOAT／REAL／DOUBLE；用 = 比對浮點數時找不到預期的列；加總後出現 0.30000000000000004 這種尾數。
- 為何有害：二進位浮點數無法精確表示多數十進位小數，誤差會在累加和比較時浮現。
- 解法：用 NUMERIC 或 DECIMAL，指定精度；或以最小單位存整數（例如以「分」為單位）。
- 何時不算：科學量測、統計等本來就容許近似值、需要很大動態範圍的資料。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### 31 Flavors（31 種口味：把可選值寫死在欄位定義）
- 定義：用 ENUM、CHECK 約束或觸發器，把允許的值清單寫在欄位定義裡。目標「Restrict a Column to Specific Values」／反模式「Specify Values in the Column Definition」／解法「Specify Values in Data」。
- 辨識訊號：★「要停機才能在選單加一個選項，順利的話不超過三十分鐘」；★「status 欄位只能是下列值，應該不需要再改」（「應該不需要」是推託之詞，意思和「不可能改」完全不同）；★「應用程式碼裡的值清單又和資料庫的業務規則不同步了」。
- 為何有害：改清單要改 schema；★ 淘汰舊值時，歷史資料怎麼處理很麻煩；★ ENUM、CHECK、網域型別在不同資料庫之間支援不一，難以移植；清單在應用程式和資料庫兩邊各存一份，容易不同步。
- 解法：建查找表（lookup table），以外鍵參照；用 active 欄位標記淘汰的值。
- 何時不算：★ 值集合確定不變時，ENUM 的問題較少（例如左／右、開／關）。
- 來源：https://media.pragprog.com/titles/bksap1/31flavors.pdf

### Phantom Files（幽靈檔案）〔部分查證〕
- 定義：認定圖片等大型媒體「一定要」存成外部檔案，資料庫只存路徑。目標「Store Images or Other Bulky Media」／反模式「Assume You Must Use Files」／解法「Use BLOB Data Types As Needed」。
- 辨識訊號：資料庫刪了列，對應的檔案還在（或反過來）；備份和還原時，資料庫和檔案不一致；交易回滾不會回滾檔案；檔案權限不受資料庫權限控管。
- 為何有害：檔案不在交易、備份、權限、刪除的管理範圍內，一致性只能靠應用程式。
- 解法：需要交易一致性、權限一致時，改用 BLOB 欄位；續用外部檔案的話，要有對帳和清理機制。
- 何時不算：檔案很大、要經 CDN 或網頁伺服器直接提供、要控制資料庫大小。Karwin 的重點是「不要預設一定用檔案」，而不是「一定要用 BLOB」。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Index Shotgun（索引亂槍）〔部分查證〕
- 定義：沒有計畫地加索引：沒加、加太多，或加了用不到的。目標「Optimize Performance」／反模式「Using Indexes Without a Plan」／解法「MENTOR Your Indexes」（Measure 量測、Explain 看執行計畫、Nominate 提名候選、Test 測試、Optimize 最佳化、Rebuild 重建）。
- 辨識訊號：Sharma 2018 的三種變體：有表卻完全沒有索引（Missing indexes）；外鍵欄位沒有索引（Insufficient indexes）；被索引的欄位從沒出現在任何查詢裡（Unused indexes）。這是 Sharma 研究中出現最頻繁的 schema smell。另外，每個欄位各建一個單欄索引也算。
- 為何有害：缺索引讓查詢全表掃描；多餘的索引拖慢寫入、浪費空間。
- 解法：先量測慢查詢，用 EXPLAIN 看執行計畫，針對實際查詢設計（複合）索引，加完再量測，定期重建。
- 何時不算：小表全表掃描比走索引還快；新系統還沒有查詢模式時，先只加主鍵和外鍵的索引。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### B3 查詢寫法

### Fear of the Unknown（害怕未知：NULL 誤用）〔部分查證〕
- 定義：把 NULL 當普通值用，或反過來用普通值（-1、空字串、'1900-01-01'）假裝 NULL。目標「Distinguish Missing Values」／反模式「Use Null as an Ordinary Value, or Vice Versa」／解法「Use Null as a Unique Value」。
- 辨識訊號：寫 `= NULL` 或 `<> NULL`；用特殊值代表「未知」；字串串接遇到 NULL 整串變 NULL。★ mini-antipattern「NOT IN (NULL)」：`WHERE status NOT IN (NULL, 'NEW')` 一列都不會回傳，因為和 NULL 比較的結果是「未知」，不是真也不是假。
- 為何有害：三值邏輯（真、假、未知）讓查詢靜默漏資料；特殊值會污染加總和平均。
- 解法：用 IS NULL、IS NOT NULL、COALESCE（★ 書中示範）；有意義的欄位宣告 NOT NULL；NOT IN 子查詢改用 NOT EXISTS。
- 何時不算：NULL 本來就該表示「未知或不適用」，問題出在誤用，不在 NULL 本身。
- 來源：https://media.pragprog.com/titles/bksap1/null.pdf 、 http://media.pragprog.com/titles/bksqla/toc.pdf

### Ambiguous Groups（模稜兩可的分組）〔部分查證〕
- 定義：SELECT 裡放了既沒分組、也沒聚合的欄位，期望資料庫「自動挑對的那一列」。目標「Get Row with Greatest Value per Group」／反模式「Reference Nongrouped Columns」／解法「Use Columns Unambiguously」。
- 辨識訊號：`SELECT product_id, MAX(date), bug_id FROM ... GROUP BY product_id`，其中 bug_id 不在 GROUP BY 裡；在 MySQL 關掉 ONLY_FULL_GROUP_BY、或在 SQLite 上能跑，換到其他資料庫就報錯。
- 為何有害：回傳的值是不確定的，不保證和 MAX 出自同一列。
- 解法：只選函數相依於分組鍵的欄位；用相關子查詢、衍生表 JOIN、視窗函數（ROW_NUMBER）取每組最大的那一列。
- 何時不算：額外欄位在函數上相依於分組鍵（例如以主鍵分組時，選同一表的其他欄位），結果是確定的。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Random Selection（隨機選取）
- 定義：用 `ORDER BY RAND() LIMIT 1` 取隨機樣本。目標「Fetch a Sample Row」／反模式「Sort Data Randomly」／解法「In No Particular Order...」。
- 辨識訊號：查詢含 ORDER BY RAND()、RANDOM() 或 NEWID()；隨資料量成長越來越慢。
- 為何有害：★ 依隨機值排序用不到索引，必須全表掃描並排序（常需要暫存表）；★ 排完整張表卻只取一列，其餘的工作全浪費。
- 解法：在鍵值範圍內隨機挑鍵；先算筆數，再用隨機 OFFSET；或在應用程式端選取。
- 何時不算：★ 資料量小時察覺不到問題，例如資料筆數固定且很少的小表。
- 來源：http://media.pragprog.com/titles/bksqla/random.pdf

### Poor Man's Search Engine（窮人的搜尋引擎）〔部分查證〕
- 定義：用 LIKE '%關鍵字%' 或正規表示式做全文搜尋。目標「Full-Text Search」／反模式「Pattern Matching Predicates」／解法「Use the Right Tool for the Job」。
- 辨識訊號：搜尋功能的 SQL 是開頭帶 % 的 LIKE 或 REGEXP；搜「one」會比對到「money」；資料一多搜尋就慢。
- 為何有害：開頭帶萬用字元，索引就用不上，每次都全表掃描；比對不到詞的邊界，結果不準。
- 解法：用資料庫的全文索引（MySQL FULLTEXT、PostgreSQL tsvector、SQLite FTS）或外部搜尋引擎；或自建倒排索引表。
- 何時不算：資料量小、查詢不頻繁、只是後台的簡單過濾。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Spaghetti Query（義大利麵查詢）〔部分查證〕
- 定義：想用一條 SQL 一次解決複雜的多步驟問題。目標「Decrease SQL Queries」／反模式「Solve a Complex Problem in One Step」／解法「Divide and Conquer」。
- 辨識訊號：多個一對多 JOIN 加上聚合，數字莫名偏大（意外的笛卡兒積，也就是兩邊每一列互相配對）；用 DISTINCT「修」重複資料；一條查詢長到沒人敢改。
- 為何有害：結果錯了不容易察覺；難以理解和維護；效能也不一定比較好。
- 解法：拆成多條查詢；用 UNION 合併同形的結果；必要時由程式動態產生 SQL。
- 何時不算：報表工具或介面只接受單一查詢；或單一查詢確實更簡單也更快，而且結果已經驗證過。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Implicit Columns（隱式欄位）〔部分查證〕
- 定義：在程式碼裡用 SELECT * 或省略欄位清單的 INSERT。目標「Reduce Typing」／反模式「a Shortcut That Gets You Lost」／解法「Name Columns Explicitly」。
- 辨識訊號：應用程式碼裡的 SELECT * 次數；INSERT INTO t VALUES (...) 沒寫欄位清單；依欄位位置（索引）取值。
- 為何有害：schema 一加欄位、改欄位順序，程式就壞或靜默讀錯欄；抓了不需要的大欄位，浪費頻寬。
- 解法：明確列出欄位。
- 何時不算：互動式的臨時查詢；快速探索用的一次性腳本。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### B4 應用程式和資料庫的接縫

### Readable Passwords（可讀密碼）
- 定義：明文或可逆地存密碼。目標「Recover or Reset Passwords」／反模式「Store Password in Plain Text」／解法「Store a Salted Hash of the Password」。
- 辨識訊號：「忘記密碼」寄出的是原密碼；password 欄位可以直接讀懂；密碼出現在 SQL 紀錄或備份裡；用沒加鹽、或很快的雜湊（MD5、SHA-1、單次 SHA-256）。
- 為何有害：資料庫、備份或紀錄一外洩，所有帳號（和使用者在其他網站重複使用的密碼）一起淪陷。
- 解法：書中解法是加鹽雜湊。目前 OWASP 的建議更進一步：用刻意很慢的演算法，首選 Argon2id（至少 19 MiB 記憶體、2 次迭代、平行度 1），其次 scrypt；舊系統用 bcrypt（work factor ≥ 10）；需要 FIPS 合規時用 PBKDF2-HMAC-SHA-256（≥ 600,000 次）。OWASP 指出 SHA-256 這類快速雜湊不適合密碼。忘記密碼改成重設流程。
- 何時不算：應用程式必須拿這個憑證去登入第三方服務（這時它是外送憑證，不是使用者密碼），改用加密存放或密鑰管理服務，見 C1 的 Hard-coded Secrets。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

### SQL Injection（SQL 注入）
- 定義：把未經驗證的輸入直接串進 SQL，當成程式碼執行。目標「Write Dynamic SQL Queries」／反模式「Execute Unverified Input As Code」／解法「Trust No One」。
- 辨識訊號：★ 只要 SQL 的任何部分是靠字串串接或變數內插組出來的，就可能有注入風險；★ 除非剛做完專門的審查，否則應該假設應用程式裡已經有這種漏洞；★ 間接形式：用參數安全寫入的資料，日後被讀出來再串進另一條動態 SQL。
- 為何有害：攻擊者可以讀取、修改、刪除資料，甚至執行系統指令。
- 解法：OWASP 的主要防線：Prepared Statements（參數化查詢）、安全寫法的 Stored Procedures（預存程序）、Allow-list Input Validation（白名單驗證，例如表名或欄名從固定對照表取值）；跳脫使用者輸入（escaping）被列為最後手段，強烈不建議。附加防線：最小權限。
- 何時不算：★ 沒有例外。Karwin 明言這一章不像其他章，沒有任何正當用途。
- 來源：http://media.pragprog.com/titles/bksqla/injection.pdf 、 https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

### Pseudokey Neat-Freak（偽鍵潔癖）〔部分查證〕
- 定義：刪除資料後，想重新編號主鍵來填補空號。目標「Tidy Up the Data」／反模式「Filling in the Corners」／解法「Get Over It」。
- 辨識訊號：有重新編號 ID 的腳本；重用已刪除的 ID；拿 MAX(id) 或 id 是否連續來當筆數或檢查。
- 為何有害：外部系統、快取、網址、紀錄裡引用的舊 ID 會指到錯的資料；改主鍵要連帶更新所有外鍵。
- 解法：接受空號，代理鍵只要唯一就好，不需要連續。
- 何時不算：業務上要求連號（例如統一發票號碼），這時要另設一個業務編號欄位，不要動主鍵。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### See No Evil（視而不見：忽略資料庫錯誤）〔部分查證〕
- 定義：不檢查資料庫 API 的回傳值或例外，也不看實際執行的 SQL。目標「Write Less Code」／反模式「Making Bricks Without Straw」／解法「Recover from Errors Gracefully」。
- 辨識訊號：execute 的回傳值沒被使用；空的 catch；除錯時只盯著組 SQL 的程式碼，從沒印出最後實際送出的 SQL。
- 為何有害：錯誤靜默發生，壞資料或空結果一路往下傳，最後在遠處才爆。
- 解法：每次都檢查錯誤並記錄；除錯時看實際的 SQL 字串和參數。
- 何時不算：框架已統一處理並記錄錯誤（但仍要確認錯誤沒被吞掉）。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Diplomatic Immunity（外交豁免：SQL 不守工程規範）〔部分查證〕
- 定義：認為 SQL 和資料庫是二等公民，不適用版本控制、測試、文件、審查這些工程實務。目標「Employ Best Practices」／反模式「Make SQL a Second-Class Citizen」／解法「Establish a Big-Tent Culture of Quality」。
- 辨識訊號：schema 變更是在正式環境手動下的，沒有遷移腳本進版控；資料庫程式碼（預存程序、觸發器、約束）沒有測試；沒有 ERD（實體關係圖）或資料字典；SQL 不經 code review。
- 為何有害：環境之間的 schema 會漂移，沒辦法重現或回溯。
- 解法：遷移腳本納入版控；為 schema 和資料庫邏輯寫測試；維護文件；SQL 一樣要審查。
- 何時不算：無。
- 來源：http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Magic Beans（魔豆：Model 就是 Active Record）〔部分查證；2010 年版的章節，2022 年版已換成 Standard Operating Procedures〕
- 定義：MVC 的 Model 直接繼承資料存取類別（Active Record，一個物件對應資料表一列），讓資料表結構等於領域模型。目標「Simplify Models in MVC」／反模式「The Model Is an Active Record」／解法「The Model Has an Active Record」。
- 辨識訊號：Controller 到處直接呼叫 ORM 的查詢方法；業務規則散在 Controller；Model 和資料表一對一；Model 的單元測試必須連資料庫。
- 為何有害：領域邏輯和 schema 綁死；查詢和規則分散；沒辦法脫離資料庫測試。
- 解法：Model 改成「擁有」資料存取物件（組合，而不是繼承），把查詢封裝在 Model 或服務層內；Controller 只呼叫領域方法。
- 何時不算：單純的 CRUD 應用，Active Record 簡單直接，反而合適。
- 來源：https://pragprog.com/titles/bksqla/sql-antipatterns/ 、 http://media.pragprog.com/titles/bksqla/toc.pdf 、 https://hackernoon.com/an-overview-of-sql-antipatterns

### Standard Operating Procedures（標準作業程序：因循使用預存程序）〔部分查證：章名經出版社頁面確認；內文只看過搜尋摘要〕
- 定義：2022 年版第四部分新增的章節。真正的反模式（節名「Follow the Leader」，跟著前人走）不是預存程序本身，而是「因為以前都這樣做」就沿用某項技術；預存程序只是最典型的例子，而且它有隱藏成本。
- 辨識訊號：選擇預存程序的理由只有「公司慣例」或「上個專案這樣做」；無法說明它在這個專案帶來什麼好處。〔辨識訊號未查證原文〕
- 為何有害：沿用前案的技術選擇，卻承擔不適合本案的隱藏成本（例如部署、測試、版本控制、可攜性）。〔具體成本清單未查證〕
- 解法：依本案需求重新評估技術選擇。〔未查證原書解法名稱〕
- 何時不算：評估後確實適合，例如需要在資料庫端集中執行權限或交易邏輯。
- 來源：https://pragprog.com/titles/bksap1/sql-antipatterns-volume-1/ （O'Reilly 的「Antipattern: Follow the Leader」頁面回應 403，只取得搜尋摘要）

### N+1 Queries（N+1 查詢）
- 定義：先用 1 條查詢取回 N 筆資料，接著在迴圈裡逐筆存取關聯資料，又觸發 N 條查詢。
- 辨識訊號：每個請求送出的 SQL 數量隨結果筆數線性成長；紀錄裡大量相同的 SELECT，只差 id；在迴圈或模板裡存取 book.author 這類關聯。Rails 文件的例子：取 10 本書再逐本取作者，共 1+10＝11 條查詢。
- 為何有害：Hibernate 文件稱它「毫無疑問是 Java 程式資料存取效能差的最常見原因」；這不是 ORM 的 bug，手寫的 JDBC 一樣會犯，只有開發者知道一個工作單元需要哪些資料。
- 解法：Rails 用 includes、preload、eager_load（includes 把 11 條降成 2 條），並可開 strict_loading，讓任何延遲載入直接拋錯；Django 用 select_related（外鍵、一對一，以 JOIN 取）和 prefetch_related（多對多、反向外鍵，分開查再組合）；Hibernate 首選 outer join fetch（HQL 的 join fetch 或 EntityGraph），batch fetching 只能減輕、不能根治。
- 何時不算：N 很小而且有上限；或只有少數項目在條件成立時才需要關聯資料（這時延遲載入反而省）。前提是量測過。
- 來源：https://guides.rubyonrails.org/active_record_querying.html#n-1-queries-problem 、 https://docs.djangoproject.com/en/stable/topics/db/optimization/ 、 https://docs.hibernate.org/orm/6.4/introduction/html_single/Hibernate_Introduction.html

### Lazy Loading Traps（延遲載入陷阱）
- 定義：依賴 ORM 的 proxy（代理物件：看起來像資料，存取時才去資料庫抓）在任意位置隱性查詢；或反過來，把關聯全設成預設立即載入。
- 辨識訊號：出現 LazyInitializationException（session 結束後才存取 proxy）；在 view、序列化或日誌裡觸發查詢；JPA 的 @ManyToOne 沒明確設成 LAZY（Hibernate 指出它預設不是 LAZY）；全域 EAGER 讓一個簡單操作抓回半個資料庫。
- 為何有害：Hibernate：一次往返只抓一個實體，幾乎是最沒效率的資料存取方式，必然導向 N+1；全域 EAGER 又是另一個極端，會變成「a terrible idea」（糟糕透頂的主意）。
- 解法：Hibernate 的建議：所有關聯預設映射為 LAZY，但避免寫出會觸發延遲載入的程式碼；在工作單元一開始，用 join fetch 或 EntityGraph 明確抓齊這次需要的資料。也就是「在需要的時間和地點，明確指定立即載入」。
- 何時不算：互動式工具或管理後台，資料量小、效能不是重點。
- 來源：https://docs.hibernate.org/orm/6.4/introduction/html_single/Hibernate_Introduction.html 、 https://guides.rubyonrails.org/active_record_querying.html#strict-loading

---

## C. 設定與建置壞味道

名詞先講白：
- **設定**（config）＝12-Factor 的定義：「每次部署之間可能不同的一切」，例如資料庫憑證、外部服務位址、每個環境各自的值。
- **lockfile**（鎖檔）＝記錄實際安裝的確切版本、讓每次安裝結果一致的檔案，例如 package-lock.json、poetry.lock。

### C1 值放錯地方

### Hard-coded Configuration（寫死的設定）
- 定義：會隨部署環境改變的值（主機、port、路徑、逾時、外部服務網址），用常數寫在程式碼裡。
- 辨識訊號：程式碼裡有 URL、IP、主機名稱、絕對路徑的字面值；換環境必須改程式碼或重新建置；12-Factor 的試金石：這個程式碼庫能不能隨時開源，而不洩漏任何憑證。
- 為何有害：違反程式碼和設定的嚴格分離；部署綁死在建置上；不同環境的值混在程式碼歷史裡。
- 解法：12-Factor 建議用環境變數注入；或由設定服務、設定檔注入，程式只讀一個入口。
- 何時不算：不隨部署改變的內部應用設定（例如路由表、模組之間的接線），12-Factor 明說這類放在程式碼裡最好〔這句出自 12factor.net/config 原頁，本次抓取摘要沒有逐字列出〕。
- 來源：https://12factor.net/config

### Hard-coded Secrets（寫死的密鑰與憑證）
- 定義：密碼、API key、私鑰、token 直接寫在程式碼或進版控的設定檔裡。CWE-798（Use of Hard-coded Credentials）。
- 辨識訊號：名為 password、secret、token、apikey 的變數被指定為字面值；符合金鑰格式的字串（例如以 `-----BEGIN PRIVATE KEY-----` 開頭）；.env 進了版控；secret scanner（例如 Yelp detect-secrets）有命中。Rahman 等人 2019 年在 Puppet 腳本中找到 1,326 個寫死的密碼〔數字取自搜尋摘要〕。
- 為何有害：CWE-798 分兩種：Inbound（產品內建一組所有安裝都相同、改不掉的預設管理密碼）和 Outbound（產品連線外部系統用的憑證寫在程式裡），兩者都很容易被找到和利用；能讀程式碼的人就拿得到；輪替（定期更換）必須改程式碼。
- 解法：OWASP：集中化、標準化的密鑰管理方案；在開發端就偵測（IDE 或 pre-commit hook，提交前自動檢查），防止密鑰被提交；定期並自動化輪替；已外洩的密鑰立刻作廢更換（只從 git 歷史刪除不夠）。
- 何時不算：明顯是假值的測試資料；公開金鑰；設計上就要公開的識別碼（例如前端用的 publishable key）。注意：偵測工具會誤報，例如把函式呼叫或 undef 當成密碼（TaintPup 論文對 SLIC 工具的批評）。
- 來源：https://cwe.mitre.org/data/definitions/798.html 、 https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html 、 https://par.nsf.gov/servlets/purl/10424781

### Scattered Magic Literals（魔術數字散落）
- 定義：沒有名字、意義不明的數字或字串，直接寫在程式碼各處。
- 辨識訊號：同一個字面值在 ≥2 處出現，而且代表同一件事；數字的意義要靠註解解釋；逾時、上限、門檻值散落在呼叫點。
- 為何有害：讀者不懂它的意思；要改時找不齊所有出現的地方，只改到一半。
- 解法：Fowler 的重構 Replace Magic Literal（又稱 Replace Magic Number with Symbolic Constant）：抽成具名常數；如果值會隨部署改變，就升級成設定（見 Hard-coded Configuration）。
- 何時不算：0、1、-1 這類在上下文中自明的值；只用一次而且旁邊名稱已經說清楚的值；測試中直接對應規格的預期值。
- 來源：https://refactoring.com/catalog/replaceMagicLiteral.html

### C2 多個來源

### Config Sprawl / Multiple Sources of Truth（設定散落、多個來源不同步）〔部分查證：名稱是整理用語〕
- 定義：同一個設定值在多個檔案或系統裡各存一份，誰為準不清楚，日久就不一致。
- 辨識訊號：同一個 key 出現在 ≥2 處（例如 appsettings.json、.env、docker-compose.yml、Kubernetes ConfigMap、程式內預設值），而且值不同；說不出覆蓋的優先順序；12-Factor 描述的症狀：設定檔散在各處、格式不一。Karwin 在 31 Flavors 也記錄了同類症狀：「應用程式碼裡的值清單又和資料庫的業務規則不同步了」，這是同一份資訊存在兩處的風險。
- 為何有害：改了一處忘了另一處，不同環境的行為就分岔；問題常在正式環境才現形。
- 解法：指定單一來源，其他地方由它產生；把覆蓋的優先順序寫成文件；程式啟動時驗證設定，缺值或衝突就直接失敗，不要默默用預設值。
- 何時不算：刻意的分層覆蓋（基礎設定加上環境層覆蓋），而且優先順序明確、有文件，這是模式，不是壞味道。
- 來源：https://12factor.net/config 、 https://media.pragprog.com/titles/bksap1/31flavors.pdf

### Snowflake Server / Configuration Drift（雪花伺服器、設定漂移）
- 定義：伺服器靠人手一次次調整，變成獨一無二、無法重現的狀態（像雪花，世上沒有兩片一樣）。
- 辨識訊號：「那台不要動」；沒辦法從零重建出一台一樣的；正式環境的實際設定和設定碼或文件不一致；登入正式機手動修改是常態。
- 為何有害：Fowler：雪花伺服器很快變得難以理解和修改，升級一個元件就產生不可預測的連鎖效應。
- 解法：把完整的作業設定寫成自動化配方（Puppet、Chef、Ansible、Terraform 等）並納入版控；必要時定期從配方重建伺服器。
- 何時不算：用完即丟的實驗機器。
- 來源：https://martinfowler.com/bliki/SnowflakeServer.html

### C3 環境差異寫進程式

### Environment Branching in Code（環境判斷寫進程式：if (isDev)）〔部分查證：名稱是整理用語〕
- 定義：業務邏輯依「目前是哪個環境」走不同的程式路徑。
- 辨識訊號：`if (env == "prod")`、`#if DEBUG`、`if (testing)` 包住的是業務邏輯（不是紀錄詳細程度）；某條路徑只在某一個環境執行；設定依 development、staging、production 這類具名環境分組，環境數一多就組合爆炸（12-Factor 的說法）。
- 為何有害：正式環境的路徑在開發和測試時沒被執行過；Meszaros：設定錯誤就可能讓測試路徑在正式環境執行（Test Logic in Production 的 Ariane 5 例子）；12-Factor 的「開發和正式環境一致」原則提醒：環境之間的差異，會讓本機測過的程式碼在正式環境失敗。
- 解法：環境差異只透過設定值或依賴注入（在程式啟動、組裝元件時選擇實作）表達，業務邏輯保持一致；每個設定項獨立管理，不靠具名環境分組。
- 何時不算：只影響紀錄等級、除錯工具（例如熱重載）、在組裝元件的入口一次性選擇的實作；不碰業務邏輯。
- 來源：http://xunitpatterns.com/Test%20Logic%20in%20Production.html 、 https://12factor.net/dev-prod-parity 、 https://12factor.net/config

### Feature Toggle Debt（功能旗標債）
- 定義：功能旗標（feature toggle，用設定開關新功能的機制）用完不刪，越積越多。
- 辨識訊號：旗標總數持續上升；旗標存在的時間已超過預定的發布時間；旗標沒有負責人或到期日；旗標互相巢狀。
- 為何有害：Fowler／Hodgson：成熟的團隊把程式碼裡的旗標視為「有持有成本的庫存」；每個旗標都增加條件分支和要測的組合；文中以 Knight Capital 損失 4.6 億美元的事件作為旗標管理不當的警示。
- 解法：新增 release toggle（發布用旗標）時，同時在待辦清單加一張「移除旗標」的工作；設到期日；設 time bomb（旗標過期就讓測試失敗，甚至拒絕啟動）；限制旗標總數上限。
- 何時不算：設計上就是長期存在的旗標，例如維運開關（kill switch，緊急關閉功能用）、權限或方案開關；文章依類型區分旗標的壽命，長壽的旗標仍要定期盤點。
- 來源：https://martinfowler.com/articles/feature-toggles.html

### C4 建置與 CI 腳本

### Copy-Pasted Build / CI Scripts（建置與 CI 腳本複製貼上）
- 定義：同樣的建置步驟、CI 工作流程、專案設定，在多個檔案或 repo 裡複製貼上。
- 辨識訊號：N 個 workflow 檔有幾乎相同的步驟區塊；修一個建置問題要改好幾處，而且常漏改；Sharma 2016 的 Duplicate Block 設定壞味道，用 PMD-CPD 工具偵測，超過 150 個 token 的重複區塊即算。
- 為何有害：和一般程式碼重複一樣：修一處漏一處，各份版本慢慢分岔。
- 解法：GitHub Actions 用 reusable workflows（可重用工作流程，官方說明的目的就是避免複製貼上）或 composite actions；其他系統用範本、共用腳本、共用建置屬性檔。
- 何時不算：兩份預期會各自演化的流程；很短的少量重複（抽出來反而更難讀）。
- 來源：https://docs.github.com/en/actions/sharing-automations/reusing-workflows 、 https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf

### CI Specification Misuse（CI 設定誤用）
- 定義：Gallaba 和 McIntosh 研究 9,312 個使用 Travis CI 的專案，歸納出四種 CI 設定反模式。
- 辨識訊號：(1) Redirecting scripts into interpreters：把下載的腳本直接導進直譯器執行（例如 `curl ... | bash`）；(2) Bypassing security checks：繞過安全檢查；(3) Using irrelevant properties：使用和當前建置無關的屬性；(4) Commands unrelated to the phase：把指令放在不對應的階段。他們的工具 Hansel 在 894 個專案（9.60%）中偵測到這些反模式。
- 為何有害：(1)(2) 是供應鏈安全風險，下載內容被竄改也照樣執行；(3)(4) 讓設定難懂，也讓階段語意失準。
- 解法：先下載、驗證雜湊或簽章，再執行；保留安全檢查；指令放到對的階段。他們的工具 Gretel 能自動修正第 4 類。
- 何時不算：無。
- 來源：https://github.com/software-rebels/hansel_and_gretel 、 https://www.swag.uwaterloo.ca/www/publications/use-and-misuse-of-continuous-integration-features-an-empirical-study-of-projects-that-mis-use-travis-ci.html

### C5 依賴宣告與版本鎖

### Missing or Inconsistent Lockfile（版本鎖缺漏或不一致）
- 定義：沒有提交 lockfile，或 lockfile 和依賴宣告檔不同步，或同一個 repo 裡不同模組鎖了同一套件的不同版本。
- 辨識訊號：lockfile 在 .gitignore 裡或根本不存在；CI 的嚴格安裝（npm ci、--frozen-lockfile）失敗；「在我機器上會過」；同一個依賴在不同服務版本不同。Jafari 等人把「No package-lock」列為 7 種依賴壞味道之一。
- 為何有害：npm 官方說明：lockfile 描述實際產生的完整依賴樹，讓後續安裝不受中間版本更新影響，產生相同的結果；它應該提交到版控，以保證隊友、部署和 CI 安裝到完全相同的依賴，也讓依賴變更在 diff 裡看得見。
- 解法：提交 lockfile；CI 用嚴格安裝模式；monorepo（多個專案放在同一 repo）集中管理版本。
- 何時不算：發布出去給別人用的函式庫，它的 lockfile 不會約束下游使用者，下游看的是 manifest 宣告的版本範圍；但仍建議提交，好讓自家 CI 可重現〔「函式庫的 lockfile 不約束下游」這句未在本次抓取的 npm 頁面中查證〕。
- 來源：https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json 、 https://arxiv.org/abs/2010.14573

### Dependency Smells（依賴宣告壞味道）
- 定義：Jafari 等人（TSE 期刊，ICSE 2022 journal-first）研究 1,146 個 JavaScript 專案，整理出 7 種依賴壞味道：Pinned Dependency（釘死在確切版本）、URL Dependency（直接用 git 或網址當依賴）、Restrictive Constraint（範圍過窄，例如只允許修補版）、Permissive Constraint（範圍過寬，例如 * 或 >=）、No package-lock、Unused Dependency（宣告了沒用）、Missing Dependency（用了沒宣告）。
- 辨識訊號：直接讀 package.json（或其他語言的依賴宣告檔）的版本範圍語法；用工具比對 import 和宣告。研究數據：80% 的專案有 ≥2 種不同的依賴壞味道；Unused 出現在 79% 的專案，Missing 出現在 63%；而且壞味道會隨時間累積，新增的速度比修掉的快。
- 為何有害：實務工作者認為會帶來安全威脅、bug、依賴斷裂、執行期錯誤和維護問題；範圍太死會錯過安全修補，太鬆會吃到破壞性更新。
- 解法：用 SemVer（語意化版本）相容範圍（例如 ^）搭配 lockfile；移除沒用的依賴；把用到的依賴全部宣告。研究中的工具 DependencySniffer 可以放進 CI 擋關。
- 何時不算：研究記錄了開發者的正當理由：遇過破壞性更新、不信任上游會遵守 SemVer、需要的修正還沒發布到 npm（這時暫時用 URL 依賴）。理由要寫在旁邊，並設定回收時點。
- 來源：https://arxiv.org/abs/2010.14573

### C6 IaC（用程式碼描述基礎設施）

### Implementation Configuration Smells（設定碼實作層壞味道）
- 定義：Sharma 等人 2016 年從 Puppet 風格指南和 Puppet-Lint 規則整理出 13 種實作層壞味道：Missing Default Case（case 沒有 default）、Inconsistent Naming Convention（命名不一致）、Complex Expression（運算式太複雜）、Duplicate Entity（重複的 hash key 或參數）、Misplaced Attribute（屬性順序不對）、Improper Alignment（對齊不當或用 tab）、Invalid Property Value（屬性值無效，例如檔案權限只寫 3 位八進位）、Incomplete Tasks（留著 fixme、todo）、Deprecated Statement Usage（用了已淘汰的語法）、Improper Quote Usage（引號誤用，例如布林值加了引號）、Long Statement（敘述過長）、Incomplete Conditional（if…elsif 沒有 else）、Unguarded Variable（字串內插的變數沒加大括號）。
- 辨識訊號：大多可用 linter（程式碼風格與錯誤檢查工具）自動偵測（Puppet-Lint 加自訂規則）。研究分析了 4,621 個 repo、約 890 萬行 Puppet 程式碼。
- 為何有害：和一般程式碼的實作壞味道一樣，降低可讀性，也是潛在的錯誤來源。
- 解法：在 CI 跑 linter；照語言的官方風格指南寫。
- 何時不算：僅屬風格類（對齊、引號），而團隊有自己一致的格式規範時。
- 來源：https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf

### Design Configuration Smells（設定碼設計層壞味道）
- 定義：同一篇研究的 11 種設計層壞味道：Multifaceted Abstraction（一個抽象管多件事）、Unnecessary Abstraction（空的類別或模組）、Imperative Abstraction（宣告式語言裡塞滿命令式的 exec）、Missing Abstraction（資源沒封裝成類別）、Insufficient Modularization（模組化不足）、Duplicate Block（重複區塊）、Broken Hierarchy（跨模組繼承）、Unstructured Module（模組目錄結構不標準）、Dense Structure（模組之間依賴過密）、Deficient Encapsulation（節點定義宣告全域變數給類別撿用）、Weakened Modularity（高耦合低內聚）。
- 辨識訊號（論文中工具 Puppeteer 的門檻）：Imperative Abstraction＝exec 超過 2 個，而且占該抽象元素 20% 以上；Insufficient Modularization＝一個檔案有超過 1 個類別或 define、類別超過 40 行、或巢狀深度超過 3；Duplicate Block＝超過 150 token 的重複區塊；Missing Abstraction＝模組內有超過 2 個沒封裝的元素；Dense Structure＝模組依賴圖的平均度數超過 0.5；Unnecessary Abstraction＝抽象的本體大小為 0。
- 為何有害：設計層的壞味道之間共同出現的比例，比實作層高 9%；設計壞味道的密度和設定專案的規模呈負相關（論文發現）。
- 解法：依單一職責拆分；把命令式步驟改成宣告式資源；抽出重複；依官方建議的模組目錄結構組織。
- 何時不算：門檻是論文工具的取捨，不是普世標準；小型一次性設定可以放寬。
- 來源：https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf

### IaC Security Smells（IaC 安全壞味道）〔部分查證：前六項經後續論文逐字確認，第七項 Suspicious comment 只見於搜尋摘要〕
- 定義：Rahman、Parnin、Williams（ICSE 2019 傑出論文〈The Seven Sins〉）從 Puppet 腳本歸納出 7 種安全壞味道：Admin by default（預設管理員帳號）、Empty password（空密碼）、Hard-coded secret（寫死的密鑰）、Invalid IP address binding（綁定 0.0.0.0 這類不受限的位址）、Suspicious comment（可疑註解，例如註解裡寫著 TODO 或已知的安全缺陷）、Use of HTTP without TLS（未加密的 HTTP）、Use of weak cryptography algorithms（弱加密演算法，例如 MD5、SHA-1）。
- 辨識訊號：可用他們的靜態分析工具 SLIC 掃描；後續的 TaintPup 研究指出 SLIC 有誤報（例如把函式呼叫或 undef 當成寫死的密碼），並追蹤到單一弱點最多會傳播到 35 個資源。
- 為何有害：設定碼的權限通常很高，一個弱點就影響整片基礎設施；論文引用的事件包括寫死的密碼導致 Uber 5,700 萬名用戶資料外洩。
- 解法：密鑰改由密鑰管理服務注入；禁止空密碼和預設管理員帳號；綁定明確的位址；全面改用 TLS；換成強演算法；在 CI 加安全掃描。
- 何時不算：明確標示的本機開發或測試設定，而且不可能部署出去。
- 來源：https://archive.cps-vo.org/node/65681 、 https://par.nsf.gov/servlets/purl/10424781

---

## D. 文件與註解壞味道

### Comments That Explain What, Not Why / Deodorant Comments（解釋 what 不解釋 why 的註解；除臭劑註解）
- 定義：註解在重述程式碼做了什麼，用來掩蓋程式碼本身不清楚（Fowler《Refactoring》把它比喻成除臭劑，蓋住臭味而不是除掉臭源）。
- 辨識訊號：註解和下一行程式碼說的是同一件事；一段程式碼上方有標題式註解（其實該抽成一個有名字的方法）；單位或意義寫在註解裡而不是名稱裡（Google 的例子：與其加註解說明單位，不如把變數命名為 timeoutMillis）。
- 為何有害：註解和程式碼是兩份必須同步的資訊，遲早不同步；真正重要的「為什麼」反而沒寫。
- 解法：refactoring.guru 列的處方：Extract Variable（把複雜運算式抽成具名變數）、Extract Method（把有註解的區段抽成方法）、Rename Method、Introduce Assertion（把註解裡的前提改成斷言）；註解只留給「為什麼」。
- 何時不算：解釋「為什麼這樣實作」；說明複雜演算法（在其他簡化手段都試過之後）；公開 API 的文件註解。
- 來源：https://refactoring.guru/smells/comments 、 https://testing.googleblog.com/2017/07/code-health-to-comment-or-not-to-comment.html

### Outdated / Misleading Comments（過期或誤導的註解）
- 定義：程式碼改了，旁邊的註解沒改，現在描述的是不存在的行為。
- 辨識訊號：註解提到已經不存在的參數或變數名稱；註解說「回傳 null」而程式碼其實丟例外；某次提交改了一段程式碼，緊鄰的註解卻沒動。
- 為何有害：讀者會相信註解而被誤導。Wen、Nagy、Bavota、Lanza（ICPC 2019）分析了 1,500 個 Java 專案的完整變更歷史，研究程式碼和註解的不一致；他們引述 Ibrahim 等人的研究：異常的註解更新行為（例如在一向會更新註解的子系統裡漏改註解），和引入 bug 的機率較高有關。
- 解法：改程式碼的同一個提交裡一併更新或刪除註解；review 時把「註解還成立嗎」列入檢查；能用型別、斷言、測試表達的約束，就不要只寫在註解裡。
- 何時不算：無。
- 來源：https://www.inf.usi.ch/faculty/lanza/PUBS/P/Wen2019a.pdf

### TODO / FIXME Accumulation（TODO 與 FIXME 堆積；Self-Admitted Technical Debt，自認的技術債）
- 定義：TODO、FIXME、HACK、XXX 這類「之後再處理」的註解一直留著，數量只增不減。
- 辨識訊號：TODO 類標記總數隨時間上升；沒有負責人或追蹤單號；用 git blame 看，存在超過數個月（經驗值）。Sharma 2016 把設定碼裡的 fixme、todo 列為 Incomplete Tasks 壞味道。
- 為何有害：債務只被記錄、沒被償還；讀者分不清哪些是仍然有效的警告、哪些是早已過時的殘骸。Potdar 和 Shihab（ICSME 2014）提出「self-admitted technical debt」這個詞，並統計其普遍程度〔具體比例只經二手摘要，原文未查證〕。
- 解法：Google 風格指南的格式：TODO 後面接追蹤單號、設計文件連結或負責人，例如 `// TODO(bug 12345): ...`，目的是讓人可以搜尋並找到詳情；連到追蹤系統；定期清掃；可以在 CI 擋下沒有負責人的 TODO。
- 何時不算：開發分支裡短暫存在、合併前就會處理掉的 TODO；有追蹤單號、還在處理中的 TODO。
- 來源：https://google.github.io/styleguide/cppguide.html#TODO_Comments 、 https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf

### Journal Comments / Version Narrative in Code（日誌式註解：把版本敘事寫進程式碼）〔部分查證：Clean Code 的分類只經二手摘要取得〕
- 定義：在程式碼註解裡記錄修改歷程、版本、日期、作者，例如「2024-03-01 改為…」「v2 新增」「原本是 X，後來改成 Y」「Bob 修了 #123」。
- 辨識訊號：註解裡有日期戳、版本號、「原本、後來、改為、新增於」這類時間敘事；檔頭有一長串變更紀錄；Clean Code 第 4 章稱為 Journal Comments 和 Attributions and Bylines（署名註解）。
- 為何有害：版控已經記錄了這些資訊，重複又會過期；讀者要先在腦中跑一遍歷史，才知道現在的狀態；註解描述的「原本」早已不存在，只會干擾。
- 解法：歷程寫進 commit message、CHANGELOG 或 ADR（架構決策紀錄）；程式碼註解只描述現況和「為什麼」。
- 何時不算：法律要求的授權或版權檔頭；「為什麼」類的註解附上 issue 連結（例如「上游套件 bug，見連結，修好後移除」），這是在解釋現在的設計，不是在講歷史。
- 來源：https://dev.to/vndlovu/clean-code-chapter-4-summary-comments-3id9 （二手摘要）、 https://refactoring.guru/smells/comments

### Commented-Out Code（被註解掉的程式碼）〔部分查證：Clean Code 原書未直接查閱〕
- 定義：整段程式碼被註解掉，但沒刪除。
- 辨識訊號：註解區塊裡是語法完整的程式碼；用工具可以計數（例如很多 linter 有「commented-out code」規則）。
- 為何有害：Clean Code 的觀察：讀者會以為留著一定有原因、不敢刪，於是越積越多，最後只有原作者知道它是做什麼的。
- 解法：直接刪除，版控保有歷史；如果是暫時停用的功能，改用功能旗標。
- 何時不算：本機除錯當下暫時註解、沒有提交。
- 來源：https://dev.to/vndlovu/clean-code-chapter-4-summary-comments-3id9 （二手摘要）

---

## 附：本檔主要來源

測試
- Meszaros, xUnit Test Patterns 線上版：http://xunitpatterns.com/Test%20Smells.html （各條目頁：`http://xunitpatterns.com/<名稱>.html`；Hard-to-Test Code 的頁面是 `Hard%20to%20Test%20Code.html`）
- van Deursen et al. 2001, Refactoring Test Code：https://ir.cwi.nl/pub/4324/04324D.pdf
- testsmells.org 目錄：https://testsmells.org/pages/testsmells.html
- Software Engineering at Google，第 12 章 Unit Testing：https://abseil.io/resources/swe-book/html/ch12.html ；第 13 章 Test Doubles：https://abseil.io/resources/swe-book/html/ch13.html
- Google Testing Blog：https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html 、 https://testing.googleblog.com/2015/01/testing-on-toilet-change-detector-tests.html
- Fowler, Eradicating Non-Determinism in Tests：https://martinfowler.com/articles/nonDeterminism.html
- Feathers 書評（legacy code 的定義）：https://www.spinellis.gr/pubs/Breview/2005-CR-Legacy/html/review.html

資料與 SQL
- Karwin 2010 目錄：http://media.pragprog.com/titles/bksqla/toc.pdf ；書頁：https://pragprog.com/titles/bksqla/sql-antipatterns/ ；2022 年版：https://pragprog.com/titles/bksap1/sql-antipatterns-volume-1/
- 試讀章節：jaywalking / 31flavors / null（2022）、trees / random / injection（2010），網址見各條目
- Sharma et al. 2018, Smelly Relations：https://www.cc.gatech.edu/~jarulraj/courses/8803-f18/papers/smelly_relations.pdf
- PostgreSQL JSON：https://www.postgresql.org/docs/current/datatype-json.html
- Rails、Django、Hibernate 的 N+1 與延遲載入：網址見各條目
- OWASP Password Storage 與 SQL Injection Prevention：網址見各條目

設定與建置
- 12-Factor：https://12factor.net/config 、 https://12factor.net/dev-prod-parity
- CWE-798：https://cwe.mitre.org/data/definitions/798.html ；OWASP Secrets Management：https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- Fowler：https://martinfowler.com/bliki/SnowflakeServer.html 、 https://martinfowler.com/articles/feature-toggles.html 、 https://refactoring.com/catalog/replaceMagicLiteral.html
- Sharma et al. 2016（MSR）：https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf
- Rahman et al. 2019：https://archive.cps-vo.org/node/65681 ；TaintPup：https://par.nsf.gov/servlets/purl/10424781
- Gallaba & McIntosh：https://github.com/software-rebels/hansel_and_gretel
- Jafari et al.：https://arxiv.org/abs/2010.14573 ；npm lockfile：https://docs.npmjs.com/cli/v10/configuring-npm/package-lock-json
- GitHub reusable workflows：https://docs.github.com/en/actions/sharing-automations/reusing-workflows

註解
- https://refactoring.guru/smells/comments 、 https://testing.googleblog.com/2017/07/code-health-to-comment-or-not-to-comment.html 、 https://www.inf.usi.ch/faculty/lanza/PUBS/P/Wen2019a.pdf 、 https://google.github.io/styleguide/cppguide.html#TODO_Comments
