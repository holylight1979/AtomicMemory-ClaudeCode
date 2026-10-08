# 07 — 可讀性壞味道與量化度量：「沒有 bug，但人讀起來很累」

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 切面範圍：程式正確、測試會過，但讀者要在腦中同時記住太多東西、要跳很多層才看得到「真正做事的那一行」。
> 涵蓋：認知負荷（單一函式內）、讀路徑長度（跨函式／跨類別）、狀態所有權散落、名實不符（語言學反模式）、可讀性相關註解、量化度量與門檻、偵測工具、度量的誤用。
>
> **查證標記**：✅ 已直接讀到一手或官方來源（含工具原始碼）｜⚠ 只讀到二手摘要或來源本身前後不一｜❓ 未查證（不得當成事實引用）。
> **門檻數字的定位**：本文所有門檻都是「值得看一眼的線索」，不是判決。理由見第 I 節。

---

## 0. 這個切面的分類架構

讀程式累，歸根究底是**讀者工作記憶（working memory，腦中同時能抓住的東西）不夠用**。Cowan（2001）整理的證據指出人類短期記憶的中心容量約 4 個意元（chunk，一個可以整塊記住的單位），範圍 3–5；Miller 的「7±2」原本只是粗估 ✅〔[Cowan 2001](https://memory.psych.missouri.edu/assets/doc/articles/2001/cowan-bbs-2001.pdf)〕。Yourdon（1986）引述的研究也說：很少人能理解超過 3 層的巢狀條件 ✅〔[ifsq.org 整理](https://ifsq.org/finding-sp-2-a.html)；Code Complete 2 第 19.4 節〈Taming Dangerously Deep Nesting〉同引此研究，[O'Reilly 目錄頁](https://oreilly.com/library/view/code-complete-2nd/0735619670/ch19s04.html)〕。

所以本切面的壞味道，依「讀者被迫多記一件事」的來源分成五類，外加度量、工具與誤用三節：

| 類別 | 讀者被迫多記的東西 | 本文條目 |
|---|---|---|
| A. 函式內的控制流負荷 | 目前在第幾層、哪些條件成立 | Cognitive Complexity、Cyclomatic Complexity、NPath、Arrow Code、Complex Conditional、Bumpy Road、Callback Hell |
| B. 跨函式／跨類別的讀路徑 | 剛剛從哪裡跳來、還要跳幾次 | 讀路徑過長（拐彎數）、Middle Man、Pass-Through Method、Shallow Module、Message Chains、Indirection Hell、Yo-yo Problem、Poltergeist |
| C. 狀態所有權散落 | 這個欄位此刻的值是誰、何時寫的 | 狀態寫入點散落、Global Data、Mutable Data、Shotgun Surgery、Temporal Coupling、Hidden Side Effects（違反 CQS） |
| D. 名實不符 | 名字說的和實際做的不一樣，要自己修正 | Linguistic Antipatterns（17 項）、命名壞味道 |
| E. 註解 | 註解與程式哪個才是真的 | 可讀性相關註解壞味道 |
| F. 量化度量 | — | 長度、參數、CK 度量組、內聚度、Fan-in/Fan-out、Halstead、Maintainability Index |
| G. 偵測策略 | — | Lanza & Marinescu 的多度量組合規則 |
| H. 工具一覽 | — | SonarQube、NDepend、VS/.NET 分析器、PMD 等 |
| I. 數字不是判決 | — | Goodhart's law、熱點分析、門檻的經驗性 |

**審查順序建議**（與「數量不是臭味，切分有沒有責任軸才是」的原則一致）：先問責任怎麼分（這段程式為誰負責什麼）→ 再問同一份狀態有幾個寫入點、有沒有單一出入口 → 最後才看數字。數字大只代表「值得看一眼」。

---

## A. 函式內的控制流負荷

### Cognitive Complexity（認知複雜度）
- 定義：SonarSource 提出、專門衡量「人讀懂這段控制流有多難」的分數；與 Cyclomatic 不同，它刻意不管「可測路徑數」，只管「讀者要多費力」✅。
- 辨識訊號（計分規則，取自白皮書 v1.7，2023-08-29，G. Ann Campbell）✅：
  - 三條基本規則：(1) 能讓多個敘述被可讀地「簡寫」的結構不計分；(2) 每個打斷「由上而下、由左而右」線性閱讀的結構 +1；(3) 會打斷線性的結構若被巢狀包住，再依巢狀深度加分。
  - **+1（結構性，且受巢狀加權）**：`if`、三元運算子、`switch`（整個 switch 連同所有 case 只算一次）、`for`/`foreach`、`while`/`do while`、`catch`（每個 catch 一次；`try`、`finally` 不計）。
  - **+1（混合型，不受巢狀加權）**：`else if`、`elif`、`else`——「讀 if 時已付過巢狀成本」。
  - **+1（基本型）**：每一「段」同種二元邏輯運算子序列（`a && b && c` 只 +1；`a && b || c` 是兩段 +2）、`goto LABEL`、`break/continue LABEL`、`break/continue NUMBER`、遞迴循環中的每個方法。
  - **不計分**：提前 `return`、一般 `break`/`continue`、null-coalescing（`??`、`?.`）、方法本身的宣告。
  - **巢狀加權**：上述「結構性」構件每被包在另一層 `if/else if/else/三元/switch/迴圈/catch/lambda/巢狀方法` 裡，就再加「目前巢狀層數」分。lambda 與巢狀方法本身不加分，但會讓裡面的東西巢狀 +1。
  - 範例（C#）：
    ```csharp
    void F(List<Item> items) {
        if (items == null) return;          // +1
        foreach (var it in items) {         // +1
            if (it.Ok && it.Ready) {        // +2（if，巢狀1）+1（&& 一段）
                if (it.X || it.Y && it.Z)   // +3（if，巢狀2）+2（|| 與 && 兩段）
                    Do(it);
            }
        }
    }                                       // Cognitive = 10；Cyclomatic = 8
    ```
  - 預設門檻：SonarQube 規則 S3776 方法層級 **15**（Java 等多數語言；sonar-java 原始碼 `DEFAULT_MAX = 15`）✅；C、C++、Objective-C 預設 **25** ✅；PMD `CognitiveComplexity` 的 `reportLevel` 預設 **15** ✅。
- 為何有害：分數高 = 讀者要同時追蹤多層條件與跳躍。實證研究（427 段程式、約 24,000 筆人工評估，10 份研究彙整）顯示它與「理解所需時間」及「主觀可讀性評分」正相關；但與「理解正確率」和生理量測的相關是混合結果，作者說它只反映「至少部分」可讀性面向 ✅〔Muñoz Barón, Wyrich, Wagner, ESEM 2020〕。
- 解法：guard clause／提前 return 壓平第一層；把內層區塊抽成有名字的函式（名字本身變成一個意元）；把複合條件命名成判斷式；長 if-else if 鏈改 switch 或查表（switch 整體只算 1 分）。
- 何時不算：分數主要來自單一大 `switch` 的狀態分派、且每個 case 都很短；或為了降分而抽出一堆只呼叫一次、名字說不清的小函式（會把負荷轉成 B 類「讀路徑過長」）。Sonar 自己說 15 是「從 10 往上調到雜訊可接受」挑出來的，不是科學推導 ✅。
- 來源：
  - https://www.sonarsource.com/docs/CognitiveComplexity.pdf
  - https://community.sonarsource.com/t/s3776-reason-for-the-current-default-value-of-15/127103
  - https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/CognitiveComplexityMethodCheck.java
  - https://pmd.github.io/pmd/pmd_rules_java_design.html
  - https://arxiv.org/abs/2007.12520

### Cyclomatic Complexity（循環複雜度／McCabe 複雜度）
- 定義：控制流程圖上「線性獨立路徑」的數目，實務上 ≈ 決策點數 + 1；原始設計目的是衡量**可測性**（要幾條測試路徑），不是可讀性 ✅。
- 辨識訊號：
  - **10**：McCabe（1976，IEEE TSE SE-2(4)）原始建議上限；NIST SP 500-235（Watson & McCabe, 1996）第 2.5 節：「10 有大量佐證；15 也有人成功使用，但超過 10 只該保留給具備經驗人員、正式設計、結構化程式、code walkthrough、完整測試計畫等優勢的專案」✅。
  - NIST 建議的最佳政策：「每個模組要嘛 ≤10，要嘛**書面說明為何超過**」✅。
  - McCabe 原本就建議豁免「整個模組只是一個多路分支（switch）」的情況 ✅。
  - 工具預設：SonarQube S1541 方法 **10** ✅；PMD 方法 **10**、類別 **80** ✅；.NET CA1502 **25** ✅；NDepend 文件：>15 難懂、>30 應拆 ✅；SIG／Better Code Hub：McCabe ≤5（即分支點 ≤4）✅。
- 為何有害：值高 = 路徑多 = 測試難以覆蓋、修改易漏分支。
- 解法：同 Cognitive Complexity；另可用多型取代型別分派（Clean Code G23）。
- 何時不算：扁平的 `switch` 分派、扁平的驗證清單——Cyclomatic 會很高但讀起來直線。這正是 Cognitive Complexity 被發明的理由（白皮書範例：同樣 Cyclomatic 的兩個方法，Cognitive 一個 7、一個 1）✅。
- 來源：
  - https://www.mccabe.com/pdf/mccabe-nist235r.pdf
  - https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1502
  - https://www.ndepend.com/docs/code-metrics
  - https://dev.to/brunooliveira/measuring-code-quality-with-bettercodehub-5cde

### NPath Complexity（NPath 複雜度）
- 定義：一個方法從頭到尾的「非循環執行路徑」總數；同一區塊內的結構會**相乘**，所以隨序列分支呈指數成長 ✅。
- 辨識訊號：PMD `NPathComplexity` 預設門檻 **200**，PMD 描述「一般認為 200 是應該動手降複雜度的點」✅。
- 為何有害：反映「互相獨立的分支串在一起」造成的組合爆炸——讀者要考慮的情境數乘起來。
- 解法：把互不相干的分支段落拆成各自命名的函式（相乘變相加）；以資料表取代連續 if。
- 何時不算：一連串互不影響的 guard clause（每個都提前 return），組合數高但讀者其實只需逐條看。
- 來源：https://github.com/pmd/pmd/blob/main/pmd-java/src/main/resources/category/java/design.xml（NPathComplexity 規則描述）

### Arrow Code / Deep Nesting（箭頭型程式碼／過深巢狀）
- 定義：條件層層包住，程式縮排往右推成箭頭形狀 ✅（Jeff Atwood, 2006）。
- 辨識訊號：
  - 巢狀深度：SonarQube S134 預設最大 **3**（第 4 層報警）✅；PMD `AvoidDeeplyNestedIfStmts` `problemDepth` 預設 **3** ✅；NDepend IL 巢狀深度 >4 難懂、>8 應拆 ✅；NDepend 規則 ND1003：IL 巢狀 >2 **且** Cyclomatic >17 ✅。
  - 認知依據：「很少人能理解超過 3 層巢狀條件」（Yourdon 1986 引 Chomsky、Weinberg）✅。
- 為何有害：每一層都是讀者要記住的一個「目前成立的前提」，第 4 層時已超出工作記憶。
- 解法（Atwood 列的四招）✅：guard clause 先處理失敗情況；把條件區塊抽成命名函式；優先用正向條件（避免雙重否定）；提早 return，不堅持單一出口。
- 何時不算：巢狀來自資料本身的層級（例如走訪樹或矩陣的兩層迴圈），且每層只做一件事。
- 來源：
  - https://blog.codinghorror.com/flattening-arrow-code/
  - https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/NestedIfStatementsCheck.java
  - https://www.ndepend.com/docs/code-metrics
  - https://ifsq.org/finding-sp-2-a.html

### Complex Conditional（複雜條件式）
- 定義：單一布林運算式裡塞了太多 `&&`、`||`、`!`，讀者要在腦中解真值表。
- 辨識訊號：SonarQube S1067「運算式不應太複雜」預設最多 **3** 個條件運算子 ✅（sonar-java `ExpressionComplexityCheck` `DEFAULT_MAX = 3`）；Cognitive Complexity 對「混用不同運算子」加更多分 ✅；Clean Code G28「Encapsulate Conditionals」、G29「Avoid Negative Conditionals」⚠（名稱取自二手整理）。
- 為何有害：混用 `&&` 與 `||` 時，讀者必須自己推優先順序。
- 解法：抽成命名的布林變數或判斷函式（`bool isEligible = …`）；拆成多個 guard clause。
- 何時不算：同一種運算子串接的平行條件（`a && b && c && d`），Cognitive Complexity 也只算 1 分。
- 來源：
  - https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/ExpressionComplexityCheck.java
  - https://devstarsj.github.io/study/2018/12/15/study.cleanCode.17

### Bumpy Road（顛簸路）
- 定義：CodeScene 的函式層壞味道——「函式沒把責任封裝好，裡面有好幾塊各自獨立的巢狀邏輯」；像顛簸的路一樣拖慢閱讀 ✅。
- 辨識訊號：一個函式內出現 ≥2 段互不相干的巢狀條件區塊（CodeScene 的確切計算門檻 ❓ 未公開於所讀頁面）。
- 為何有害：一個函式其實在做好幾件事，且「功能糾纏」風險高 ✅。
- 解法：每一段「顛簸」抽成一個命名函式。
- 何時不算：各段共享同一組區域變數、拆開後要傳一長串參數（會變成 Long Parameter List）。
- 來源：https://docs.enterprise.codescene.io/versions/6.0.6/guides/technical/code-health.html

### Callback Hell / Pyramid of Doom（回呼地獄／毀滅金字塔）
- 定義：非同步回呼層層巢狀，程式往右長成金字塔 ✅。
- 辨識訊號：匿名回呼裡再傳匿名回呼；縮排深度隨非同步步驟數線性增加（套用上面的巢狀門檻）。
- 為何有害：作者想讓「執行順序」在視覺上由上而下，結果把非同步順序編碼成巢狀 ✅。
- 解法（callbackhell.com 三招）✅：保持淺層——替函式命名並放到最外層；模組化——小模組各做一件事；每個回呼都處理錯誤。現代語言再加：`async/await`、Promise/Task 串接。
- 何時不算：只有 1–2 層，且回呼很短。
- 來源：http://callbackhell.com/

---

## B. 跨函式／跨類別的讀路徑

### Long Read Path / Bend Count（讀路徑過長／拐彎數）
- 定義：為了弄懂「一個構想從頭到尾怎麼完成」，讀者必須跳轉、記住前提、修正誤解的次數。本條是本文件為「人讀起來累」整理的**審查經驗法則**，不是業界標準度量。
- 辨識訊號（拐一個彎 = 讀者多記一件事或視線離開目前畫面一次）：
  1. **跳轉**：要去另一個函式／檔案／基底類別才知道這行在做什麼；每一層「只轉手、不加工」的呼叫各算一彎。
  2. **巢狀**：每多一層控制結構算一彎（同 Cognitive Complexity 的巢狀加權）。
  3. **隱藏狀態**：要知道「別處誰、何時寫了這個欄位」才能判斷結果（見 C 類）。
  4. **順序前提**：要知道「必須先呼叫 X 才能呼叫 Y」（見 Temporal Coupling）。
  5. **名實不符**：名字誤導，讀者要修正心中模型（見 D 類）。
  - 門檻：**超過 3 彎即視為壞味道** ❓（無業界來源；依據是使用者的審查原則，並與 Cowan 工作記憶 3–5 意元、Yourdon「超過 3 層巢狀很少人懂」、Sonar S134 巢狀上限 3 的數量級一致 ✅）。
  - 主流工具都**不直接量**跨函式的讀路徑；Cognitive Complexity 只看單一函式內 ✅（白皮書：方法結構本身不計分）。可用 NDepend CQLinq 或 Roslyn 自寫查詢近似：找出「本體只有一個呼叫、參數原樣轉交」的方法，沿呼叫圖算連續轉手層數 ❓（方法可行，無現成規則）。
- 為何有害：每一彎都佔一格工作記憶；四彎以上讀者開始忘記自己從哪裡來。
- 解法：刪掉不加工的轉手層（Remove Middle Man、Inline Function）；把狀態寫入收斂到單一出入口；用回傳值表達順序前提；改名讓名字說實話。
- 何時不算：每一層都有清楚、獨立的責任（例如對外 API 層做參數驗證與權限、核心層做運算、資料層做持久化），讀者可以只讀一層就停——這時跳轉是「可以不跳」的，不算彎。
- 來源：https://memory.psych.missouri.edu/assets/doc/articles/2001/cowan-bbs-2001.pdf ；https://ifsq.org/finding-sp-2-a.html ；https://www.sonarsource.com/docs/CognitiveComplexity.pdf

### Middle Man（中間人）
- 定義：一個類別的大部分方法都只是把呼叫轉交給另一個類別 ✅。
- 辨識訊號：類別裡多數方法的本體是單一委派呼叫（refactoring.guru：「若多數方法都委派給另一個類別」）✅；具體比例門檻 ❓。
- 為何有害：多一層要讀、卻沒有增加任何資訊；常見成因是過度消除 Message Chains，或功能逐漸搬走後只剩空殼 ✅。
- 解法：Remove Middle Man（讓呼叫端直接呼叫真正做事的物件）；若只有少數方法轉交，用 Inline Function 合併 ✅。
- 何時不算：刻意設計的中介——為降低類別間相依而加的、Proxy／Decorator 等設計模式產生的 ✅。
- 來源：https://refactoring.guru/smells/middle-man ；Fowler《Refactoring》2nd ed. 第 3 章壞味道清單（二手整理 https://github.com/ittus/Refactoring-summary-2nd-javascript）

### Pass-Through Method（純轉接方法）
- 定義：方法除了把參數原樣傳給另一個（通常簽章相同的）方法之外什麼都不做 ✅（Ousterhout《A Philosophy of Software Design》紅旗之一）。
- 辨識訊號：方法本體 = 一行呼叫，參數原樣傳遞；相鄰兩層抽象相似（Ousterhout：「相鄰層有相似抽象」是類別分解有問題的紅旗）⚠。相關：**pass-through variable**（只為了往下傳而穿過中間各層的參數）⚠。
- 為何有害：代表類別間責任劃分不清 ⚠；讀者跳一層卻沒學到新東西。
- 解法：把功能合併到其中一層；或讓呼叫端直接用下層；或改用 context 物件取代穿層參數。
- 何時不算：介面實作、跨模組邊界的 facade、為了讓上層不依賴下層型別而做的轉換——只要它真的隱藏了某個決策。
- 來源：https://dev.to/sportebois/software-design-red-flags-wisdom-nuggets-from-john-ousterhout-43i2 （二手整理）

### Shallow Module（淺模組）
- 定義：介面的複雜度跟它提供的功能差不多，甚至更多——用它的成本幾乎等於自己寫 ⚠（Ousterhout）。
- 辨識訊號：類別／函式的公開成員數多、但每個都很薄；Ousterhout 舉 Java I/O 要串 FileInputStream、BufferedInputStream、ObjectInputStream 為例，對比 Unix 五個 I/O 系統呼叫的「深模組」⚠。
- 為何有害：讀者要學的介面跟實作一樣多，抽象沒有省下任何認知成本。
- 解法：合併成「介面簡單、實作豐富」的深模組；把常見用法設為預設。
- 何時不算：刻意的組合式 API（讓進階使用者自由組裝），且有提供簡單的常用入口。
- 來源：https://dev.to/sportebois/software-design-red-flags-wisdom-nuggets-from-john-ousterhout-43i2 ；https://henrikwarne.com/2021/07/12/book-review-a-philosophy-of-software-design/

### Message Chains（訊息鏈）
- 定義：`a.b().c().d()`——呼叫端沿著物件結構一路導航 ✅。
- 辨識訊號：連續的 `.` 取得另一個物件再呼叫；PMD `LawOfDemeter` 規則 `trustRadius` 預設 **1** ✅；Clean Code G36「Avoid Transitive Navigation」⚠。
- 為何有害：呼叫端依賴整條導航結構，中間任何關係改變都要改呼叫端 ✅。
- 解法：Hide Delegate；或 Extract Method + Move Method 把功能搬到鏈的起點 ✅。
- 何時不算：fluent API／builder／LINQ 這類每一步回傳同一抽象的串接；以及「過度隱藏委派會讓人看不出功能實際在哪裡發生」——會反過來變成 Middle Man ✅。
- 來源：https://refactoring.guru/smells/message-chains ；https://pmd.github.io/pmd/pmd_rules_java_design.html

### Indirection Hell（間接層過多）
- 定義：為了「彈性」疊了太多層介面、工廠、轉接，每層都很薄。
- 辨識訊號：「軟體工程基本定理」：「電腦科學的任何問題都能再加一層間接解決」（Butler Lampson 歸功於 David Wheeler，也有人歸給 Roger Needham），後接補句「……除了間接層太多這個問題」✅。可觀察徵兆：只有一個實作的介面、只被呼叫一次的工廠、跳到定義後還要再跳；Fowler 2nd ed 的 **Speculative Generality（臆測的通用性）**與 **Lazy Element（冗贅元素）**是同一家族 ⚠。數字門檻 ❓（無業界標準）。
- 為何有害：每層都是讀路徑上的一彎；而且各層常互相重複功能 ✅（Wikipedia 以網路協定分層的功能重複為例）。
- 解法：Inline Class／Inline Function／Collapse Hierarchy；等第二個實作真的出現再抽介面。
- 何時不算：間接層換來明確的隔離（測試替身、跨程序邊界、外掛點），且有實際的第二個使用者。
- 來源：https://en.wikipedia.org/wiki/Fundamental_theorem_of_software_engineering ；https://github.com/ittus/Refactoring-summary-2nd-javascript

### Yo-yo Problem（溜溜球問題）
- 定義：要理解一個方法的行為，必須在繼承階層裡上上下下來回看（super 呼叫、override、template method 交錯）✅。最早由 Taenzer、Ganti、Podar（1989）描述：「試著理解這些訊息樹時，常有在玩溜溜球的感覺」✅。
- 辨識訊號：繼承深度 DIT（Depth of Inheritance Tree）——.NET CA1501 預設 **5**（第 5 層以上報警）✅；SonarQube S110 預設 **5** ✅；NDepend 文件：≥6 可能難以維護 ✅；Aivosto：建議 ≤5，有些來源允許到 8 ✅。
- 為何有害：讀者要同時在腦中拼合多個類別定義 ✅。
- 解法：繼承階層保持淺；組合優於繼承；把必要的分層資訊集中文件化 ✅。
- 何時不算：框架規定的基底類別（不算進自己的閱讀負擔，CA1501 預設就排除 `System.*`）✅；各層沒有交錯 override、讀者只需看最底層。
- 來源：https://en.wikipedia.org/wiki/Yo-yo_problem ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1501 ；https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/DepthOfInheritanceTreeCheck.java

### Poltergeist（騷靈類別）
- 定義：短命、通常沒有狀態的物件，只負責初始化或呼叫另一個類別的方法，本身不添加有意義的功能 ✅（Brown 等《AntiPatterns》1998）。
- 辨識訊號：類別名含 Manager、Controller、Supervisor、StartProcess；物件出現又消失不保留狀態；為「預期中但從未到來的複雜度」而建 ✅。
- 為何有害：多一層無意義抽象，讀者追呼叫時多跳一次 ✅。
- 解法：刪掉這個類別，把功能併入它所呼叫的類別 ✅。
- 何時不算：命令物件（Command）、Unit of Work 等短命但真的封裝了一次操作語意的物件。
- 來源：https://en.wikipedia.org/wiki/Poltergeist_(computer_programming)

---

## C. 狀態所有權散落

### Scattered State Writes（狀態寫入點散落）
- 定義：同一個欄位、容器或共享狀態，被許多檔案、許多方法直接寫入，沒有單一出入口。讀者要知道某一刻的值，得把所有寫入點都看過。
- 辨識訊號：
  - 數「寫入點」：一個欄位被幾個方法、幾個類別賦值。NDepend 提供 `MethodsAssigningMe` 等查詢屬性可直接數 ✅。
  - NDepend ND1905「欄位不得從其所屬繼承階層之外被賦值」：任何 public/internal 可變欄位從外部被寫入就報 ✅——規則說明：「非 private 欄位出問題時，元兇可能在任何地方……private 欄位通常只需看一個檔案」✅。
  - 寫入點數的門檻 ❓（無業界標準；審查時以「是否有單一出入口」判斷，而非數字）。
- 為何有害：值的來源散在各處 → 除錯要全域搜尋；改規則要改很多地方（同時觸發 Shotgun Surgery）。
- 解法：Encapsulate Variable（封裝變數：改成只能經由一組函式讀寫）⚠；把寫入集中到擁有該狀態的類別；把可變欄位改為唯讀，以回傳新值取代就地修改。
- 何時不算：寫入點雖多，但全部經過同一個方法（單一出入口）——那是「呼叫點多」，不是「寫入點散」。
- 來源：https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html （ND1905）；https://github.com/ittus/Refactoring-summary-2nd-javascript

### Global Data（全域資料）
- 定義：任何地方都能讀寫的資料（全域變數、類別靜態可變欄位、單例中的可變狀態）✅（Fowler 2nd ed 壞味道）。
- 辨識訊號：可變的 static 欄位；NDepend「Avoid non-readonly static fields」「Avoid static fields with a mutable field type」等規則 ✅（規則名稱存在於 NDepend 規則清單）。
- 為何有害：全域變數難以追蹤與除錯 ⚠——任何一行都可能是改它的人。
- 解法：Encapsulate Variable，先讓所有存取都經過函式，再縮小可見範圍 ⚠。
- 何時不算：真正不可變的全域常數或設定（唯讀）；量很少、可見範圍很小。
- 來源：https://github.com/ittus/Refactoring-summary-2nd-javascript ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html

### Mutable Data（可變資料）
- 定義：資料在一處被改，另一處以為它沒變，導致意外結果 ✅（Fowler 2nd ed 壞味道）。
- 辨識訊號：同一物件被多個呼叫者就地修改；getter 回傳內部可變集合；NDepend「Do not declare read only fields with mutable reference types」「Public read only array fields can be modified」等規則 ✅（名稱）。
- 為何有害：「資料的改變常導致意外後果與棘手 bug」⚠。
- 解法：Encapsulate Variable、Split Variable、Slide Statements、Extract Function；不可變資料結構；回傳複本 ⚠。
- 何時不算：可變範圍限於單一函式的區域變數；效能熱點中有明確擁有者的緩衝區。
- 來源：https://github.com/ittus/Refactoring-summary-2nd-javascript

### Shotgun Surgery（散彈式修改）
- 定義：每次做一個改動，都得到許多類別各改一小處 ✅。與 Divergent Change（發散式變化：一個類別因許多不同理由被改）相反 ✅。
- 辨識訊號：
  - 版本歷史：同一個需求的 commit 總是動到同一群檔案（CodeScene 稱 change coupling，變動耦合）。
  - Lanza & Marinescu 偵測策略：**CM（Changing Methods，會受影響的呼叫方法數）> Many AND CC（Changing Classes，受影響的類別數）> Many** ✅。
- 為何有害：單一責任被拆散到很多類別 ✅；漏改一處就是 bug。
- 解法：Move Method、Move Field 把行為集中到一個類別；搬完後 Inline Class 刪掉變空的類別 ✅。
- 何時不算：真正橫切的關注點（日誌、權限）已由框架或 AOP 集中處理。
- 來源：https://refactoring.guru/smells/shotgun-surgery ；https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/lectures/detection-strategy_v01.pdf

### Temporal Coupling（時序耦合）
- 定義：類別的兩個以上成員之間有隱含的時間關係，呼叫端必須先呼叫其中一個再呼叫另一個 ✅（Mark Seemann, 2011）。典型是 `Initialize()` 方法 ✅。
- 辨識訊號：`Initialize()`／`Setup()` 類方法；在建構子之外才被賦值的欄位；散在各處的「是否已初始化」防禦檢查；測試準備步驟固定照某順序 ✅〔DevIQ〕；Clean Code G31「Hidden Temporal Couplings」⚠。
- 為何有害：API 沒有任何結構提示順序，順序錯了要到執行期才爆，而且錯誤不一定立即浮現 ✅。
- 解法：建構子注入（物件建好就處於有效狀態）；用工廠回傳已初始化的實例；讓前一步回傳下一步需要的參數，由編譯器強制順序 ✅。
- 何時不算：順序已被型別系統強制（builder 每步回傳不同型別）；明確的狀態機且非法轉移會立即丟例外。
- 來源：https://blog.ploeh.dk/2011/05/24/DesignSmellTemporalCoupling/ ；https://www.deviq.com/code-smells/hidden-temporal-coupling/ ；https://devstarsj.github.io/study/2018/12/15/study.cleanCode.17

### Hidden Side Effects / CQS Violation（隱藏副作用／違反命令查詢分離）
- 定義：名字看起來是查詢（只讀），實際上會寫入狀態。Command-Query Separation（命令查詢分離，Bertrand Meyer 提出）：方法要嘛是**查詢**（回傳結果、不改狀態），要嘛是**命令**（改狀態、不回傳值）✅。
- 辨識訊號：
  - `Get…`／`Is…`／`Has…`／屬性 getter 內有欄位賦值、I/O、事件觸發。
  - NDepend ND1904「Property Getters should be pure」：getter 指派欄位就報；但排除「只有 getter 與對應 setter 會寫的欄位」（延遲初始化）✅。
  - Clean Code N7「Names Should Describe Side-Effects」⚠；語言學反模式 A.1（見 D 類）✅。
- 為何有害：查詢可以被放心地隨處呼叫、重複呼叫；一旦查詢會改狀態，讀者看到每個 getter 都得點進去確認 ✅（Fowler：「能清楚分開改狀態與不改狀態的方法，非常好用」）。
- 解法：Separate Query from Modifier（把「回傳值又有副作用」的函式拆成一個查詢、一個修改）⚠；若副作用必要，就把它寫進名字（`GetOrCreate…`、`LoadAndCache…`）。
- 何時不算：Fowler 舉的例外——堆疊 `pop()` 同時回傳與修改，是有用的慣用法 ✅；對呼叫者不可見的延遲初始化／快取 ✅（NDepend ND1904 的排除條件）。
- 來源：https://martinfowler.com/bliki/CommandQuerySeparation.html ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html （ND1904）；https://refactoring.com/catalog/separateQueryFromModifier.html

---

## D. 名實不符

### Linguistic Antipatterns（語言學反模式，LA）
- 定義：一個程式實體的**名字、文件（註解）與實作**之間不一致的重複型態；Arnaoudova、Di Penta、Antoniol 首先在 CSMR 2013 提出，2016 年於 Empirical Software Engineering（21(1):104–158）擴充為 17 項並調查開發者觀感 ✅。
- 辨識訊號：分成六大家族、17 項（下表的「偵測規則」取自 IDEAL 工具論文 Table I，A–F 為 Arnaoudova 原始定義）✅：

| ID | 名稱（中譯） | 偵測規則（摘要） |
|---|---|---|
| **A. 做的比說的多**（方法） | | |
| A.1 | "Get" more than an accessor（Get 不只是存取子） | 名稱以 `get` 開頭、public/protected、名稱含某屬性名、回傳型別同該屬性，但本體有條件判斷 |
| A.2 | "Is" returns more than a Boolean（Is 回傳的不只是布林） | 名稱以述語／肯定語（is/has/can…）開頭，回傳型別不是 bool |
| A.3 | "Set" method returns（Set 方法有回傳值） | 名稱以 `set` 開頭，回傳型別不是 void |
| A.4 | Expecting but not getting a single instance（期待單一卻拿到多個） | 名稱最後一詞是單數、不含集合字眼，回傳型別卻是集合 |
| **B. 說的比做的多**（方法） | | |
| B.1 | Not implemented condition（條件沒實作） | 名稱或註解含條件語意，本體卻沒有條件敘述 |
| B.2 | Validation method does not confirm（驗證方法不回報結果） | 名稱以驗證詞（validate/check…）開頭，無回傳值也不丟例外 |
| B.3 | "Get" method does not return（Get 方法不回傳） | 名稱以 get 類詞開頭，回傳 void |
| B.4 | Not answered question（問了卻不回答） | 名稱以述語（is/has…）開頭，回傳 void |
| B.5 | Transform method does not return（轉換方法不回傳） | 名稱以轉換詞（to/convert…）開頭或含之，回傳 void |
| B.6 | Expecting but not getting a collection（期待集合卻拿到單一） | 名稱以 get 類詞開頭、含複數或集合字眼，回傳不是集合 |
| **C. 做的與說的相反**（方法） | | |
| C.1 | Method name and return type are opposite（方法名與回傳型別相反） | 名稱詞與回傳型別詞為反義詞 |
| C.2 | Method signature and comment are opposite（簽章與註解相反） | 名稱或型別與註解間有反義詞 |
| **D. 裝的比說的多**（屬性／變數／參數） | | |
| D.1 | Says one but contains many（說一個卻裝很多） | 名稱最後一詞是單數，型別是集合 |
| D.2 | Name suggests Boolean but type does not（名字像布林，型別不是） | 名稱以述語開頭，型別不是 bool |
| **E. 說的比裝的多**（屬性／變數／參數） | | |
| E.1 | Says many but contains one（說很多卻只裝一個） | 名稱最後一詞是複數，型別不是集合 |
| **F. 裝的與說的相反**（屬性／變數／參數） | | |
| F.1 | Attribute name and type are opposite（屬性名與型別相反） | 名稱詞與型別詞為反義詞 |
| F.2 | Attribute signature and comment are opposite（屬性簽章與註解相反） | 名稱或型別與註解間有反義詞 |

  - IDEAL 另加兩項（非 Arnaoudova 原始）：G.1 名稱只含特殊字元；G.2 測試方法名多餘地以 `test` 開頭 ✅。
  - 使用者常說的「名字說 get 實際做 set」對應最接近的是 **A.1**＋上節的 **ND1904 getter 應為純函式**；「名稱複數、回傳單數」是 **B.6**（方法）或 **E.1**（變數）；「is 開頭回傳非 bool」是 **A.2**（方法）或 **D.2**（變數）。
- 為何有害：讀者靠名字建立心智模型，名字說謊就得重讀實作來修正——每個 LA 都是讀路徑上的一彎。Arnaoudova 等的調查：多數開發者認為 LA 是不良實務；指出後約 10% 的案例被開發者移除 ✅。
- 解法：改名讓名字說實話（最便宜）；或改實作讓它符合名字（例如 `Validate` 改成回傳結果或丟例外）。
- 何時不算：偵測器誤報很多——IDEAL 平均精確率 75.27%、LAPD 72% ✅；常見誤報：自訂集合型別（如 `EnvVars`）被當成非集合、命名慣例產生的「反義詞」（`GetCompletionResult` 回傳 `CompletionResult`，Get 與 Result 被判為反義）、條件詞與轉換詞的語境 ✅。所以 LA 偵測結果要人工或 LLM 再判讀語境。
- 來源：
  - https://arxiv.org/abs/2107.08344 （IDEAL，Table I）
  - https://doi.org/10.1007/s10664-014-9350-8 （ESE 2016 論文 DOI）
  - https://crihn.openum.ca/s/519 （CSMR 2013〈A New Family of Software Anti-Patterns: Linguistic Anti-Patterns〉）

### Naming Smells（命名壞味道：Mysterious / Vague / Hard-to-Pick Name）
- 定義：名字沒有清楚傳達「這是什麼、做什麼、怎麼用」。
- 辨識訊號：
  - Fowler 2nd ed 把 **Mysterious Name（神秘的名字）**列為第一個壞味道 ⚠。
  - Ousterhout 紅旗：**Vague Name**（名字太廣，傳達不了明確意義）、**Hard to Pick Name**（想不出好名字 → 底層設計可能有問題）、**Hard to Describe**（寫不出簡單完整的說明 → 設計有問題）⚠。
  - Clean Code 命名啟發：N1 描述性名稱、N2 名稱抽象層級要對、N3 用標準術語、N4 清楚、N5 範圍越大名字越長、N6 避免編碼（匈牙利命名等）、N7 名字要說出副作用 ⚠。
  - 泛用詞：IDEAL 作者觀察 `data`、`result` 這類詞無法看出是單一還是集合；C# `var` 與 `object` 也不表達資料性質 ✅。
  - Butler 等（2009／2010）以一組命名風格準則檢查 8 個大型 Java 專案，發現命名違規與 FindBugs 回報的品質問題相關，2010 年把結論延伸到方法層級 ⚠（各準則的數字門檻 ❓ 未讀到原文）。
- 為何有害：名字是讀者最主要的壓縮工具；名字不準，整段就得展開讀。
- 解法：Rename；想不出名字時先懷疑職責切分。
- 何時不算：慣例性的短名（迴圈的 `i`、lambda 的 `x`）在極小範圍內使用。
- 來源：https://github.com/ittus/Refactoring-summary-2nd-javascript ；https://dev.to/sportebois/software-design-red-flags-wisdom-nuggets-from-john-ousterhout-43i2 ；https://devstarsj.github.io/study/2018/12/15/study.cleanCode.17 ；https://arxiv.org/abs/2107.08344 ；https://oro.open.ac.uk/view/person/sjb792.html

---

## E. 註解（只寫與可讀性有關的部分；完整註解壞味道見 [06-test-data-config.md](06-test-data-config.md) D 節）

### Comment Smells affecting readability（影響可讀性的註解壞味道）
- 定義：註解與程式不一致、重複程式、或把本該寫進程式結構的資訊塞進註解。
- 辨識訊號：
  - Clean Code：C1 不恰當的資訊、C2 過時註解、C3 多餘註解、C4 寫得差的註解、C5 被註解掉的程式碼 ⚠。
  - Ousterhout 紅旗：Comment Repeats Code（註解只是換句話說）、Implementation Documentation Contaminates Interface（介面文件寫了不必要的內部細節）⚠。
  - LA 的 C.2、F.2：註解與簽章語意相反 ✅。
  - NDepend ND1006「可能註解不足的方法」：註解比例 ≤5% **且** 程式 ≥30 行 **且** Cyclomatic ≥3 ✅。
- 為何有害：讀者不知道該信註解還是信程式；過時註解比沒註解更糟（是一個「名實不符」的彎）。
- 解法：能用命名、抽函式表達的就不用註解；註解寫「為什麼」與「不明顯的約束」，不寫「做什麼」。
- 何時不算：公開 API 的文件註解、解釋非顯而易見的演算法或外部限制。
- 來源：https://devstarsj.github.io/study/2018/12/15/study.cleanCode.17 ；https://dev.to/sportebois/software-design-red-flags-wisdom-nuggets-from-john-ousterhout-43i2 ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html

---

## F. 量化度量

### Long Method / LOC（過長方法／程式行數）
- 定義：方法或檔案的行數過多。LOC（Lines of Code）的計法各工具不同（實體行、邏輯行 NCSS、IL 指令推估）✅。
- 辨識訊號（方法層級）：SonarQube S138 預設 **75** 行（Java，sonar-java 原始碼）✅；PMD `NcssCount` 方法 **60**、類別 **1500** ✅；NDepend 文件：>20 難懂、>40 應拆 ✅；NIST：「60 行是常見上限，理由是一個模組要能印在一頁上——有點過時」✅；SIG／Better Code Hub：≤**15** 行 ✅。檔案層級：SonarQube S104 **750** 行（Java）✅；NDepend ND1000 型別 >**200** LOC ✅。
- 為何有害：越長越可能混了多個責任、需要捲動、讀者要記的區域變數越多（NDepend：區域變數 >8 難懂、>15 應拆 ✅）。
- 解法：Extract Function；依「一個函式只做一件事」（Clean Code G30）、「只往下一個抽象層級」（G34）切 ⚠。
- 何時不算：NIST 明講「行數與複雜度沒有一致關係」——很多 Cyclomatic=1 的模組遠超 60 行，也有很多 >10 的不到 60 行 ✅。純資料表、產生的程式、線性的設定步驟，長而不難。
- 來源：https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/MethodTooBigCheck.java ；https://pmd.github.io/pmd/pmd_rules_java_design.html ；https://www.ndepend.com/docs/code-metrics ；https://www.mccabe.com/pdf/mccabe-nist235r.pdf

### Long Parameter List（過長參數列）
- 定義：方法參數太多，呼叫端要記住順序與意義。
- 辨識訊號（**各家差距極大，本身就是「數字不是判決」的證據**）：SonarQube S107 **7** ✅；NDepend 規則 ND1004 **≥8**（文件另說 >5 呼叫起來可能很痛苦）✅；PMD `ExcessiveParameterList` **10** ✅；Better Code Hub **≤2**（依該部落格轉述）⚠；Clean Code F1「Too Many Arguments」⚠（書中具體數字 ❓ 本次未查證）；旗標參數 Clean Code F3 ⚠。
- 為何有害：每個參數都是讀者要對位的一格；同型別相鄰參數容易傳反。
- 解法：Introduce Parameter Object；Preserve Whole Object；拆出需要較少參數的子函式（Better Code Hub 建議）✅。
- 何時不算：NDepend 排除「覆寫第三方方法」與「建構子把參數轉給有同樣多參數的基底建構子」✅；依賴注入建構子參數多常是類別職責過多的訊號，而非參數列本身的問題。
- 來源：https://github.com/SonarSource/sonar-java/blob/master/java-checks/src/main/java/org/sonar/java/checks/TooManyParametersCheck.java ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html ；https://pmd.github.io/pmd/pmd_rules_java_design.html ；https://dev.to/brunooliveira/measuring-code-quality-with-bettercodehub-5cde

### WMC — Weighted Methods per Class（類別加權方法數，CK 度量）
- 定義：類別中所有方法複雜度的總和；權重可用 Cyclomatic，或每個方法都算 1（此時等於方法數）✅（Chidamber & Kemerer 1994，CK 度量組共 6 項：WMC、DIT、NOC、CBO、RFC、LCOM）✅。
- 辨識訊號：Lanza & Marinescu 的 Very High = **47**（PMD GodClass 實作，引書 p.16–18、p.80）✅；Aivosto 引用的經驗限制：每類別方法數 20 或 50，或「最多 10% 的類別超過 24 個方法」✅；PMD `TooManyMethods` **10** ✅；NDepend ND1001 方法數 >**20**（且至少有一個非常數欄位——全是無狀態方法的類別可接受）✅。
- 為何有害：類別包太多行為，常是 God Class 的一個面向。
- 解法：Extract Class，依欄位使用群組切分。
- 何時不算：NDepend 明確排除只有無狀態靜態方法的類別 ✅；Cognitive Complexity 白皮書指出，用不收「方法入場費」的度量加總時，滿是簡單 getter/setter 的領域類別不會被誤判 ✅。
- 來源：https://github.com/pmd/pmd/blob/main/pmd-java/src/main/java/net/sourceforge/pmd/lang/java/rule/design/GodClassRule.java ；https://www.aivosto.com/project/help/pm-oo-ck.html ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html

### DIT / NOC — Depth of Inheritance Tree / Number of Children（繼承深度／直接子類別數，CK 度量）
- 定義：DIT = 類別到根類別的最長繼承路徑；NOC = 直接子類別數 ✅。
- 辨識訊號：DIT 門檻見 Yo-yo Problem（CA1501 5、Sonar S110 5、NDepend ≥6、Aivosto ≤5）✅。NOC 無公認門檻；Aivosto：高 NOC 被發現與**較少**缺陷相關（可能因為重用），但「高 NOC 加高 WMC」代表複雜度集中在階層頂端 ✅。
- 為何有害：DIT 高 → 基底類別修改的波及面大、讀者要上下跳（Visual Studio 文件）✅。
- 解法：組合取代繼承；壓平中間層。
- 何時不算：框架基底類別；NOC 高通常不是壞事 ✅。
- 來源：https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-values ；https://www.aivosto.com/project/help/pm-oo-ck.html

### CBO / RFC / Class Coupling（物件間耦合／類別回應集合／類別耦合）
- 定義：CBO = 與本類別耦合的其他類別數；RFC = 本類別方法數 + 其直接呼叫的外部方法數（RFC' 為遞迴全呼叫版）✅。Visual Studio 的 Class Coupling 計算透過參數、區域變數、回傳型別、方法呼叫、泛型實例化、基底類別、介面實作、外部型別欄位、屬性標註等引用到的唯一類別數 ✅。
- 辨識訊號：CBO：Aivosto「>14 太高」✅；PMD `CouplingBetweenObjects` **20** ✅；.NET CA1506 型別 **95**、其他符號 **40** ✅；NDepend：TypeCe（efferent coupling，往外依賴數）>**50** 表示依賴太多、責任不只一個 ✅。RFC：Aivosto 說「大 RFC 與較多缺陷相關」，但沒給數字 ✅；常見的「RFC>50」說法 ❓ 未查證。
- 為何有害：依賴越多，理解本類別時要載入的外部概念越多；修改波及面越大。
- 解法：Move Method、Extract Class、引入較窄的介面。
- 何時不算：組裝根（composition root）、應用程式進入點、DTO 對映層——本來就該知道很多型別。
- 來源：https://www.aivosto.com/project/help/pm-oo-ck.html ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1506 ；https://pmd.github.io/pmd/pmd_rules_java_design.html ；https://www.ndepend.com/docs/code-metrics

### LCOM family / TCC / LCC（方法內聚缺乏度各版本／緊密與鬆散類別內聚度）
- 定義：衡量類別中的方法是否共用同一批欄位；共用越少 = 越不內聚 = 越像好幾個類別硬湊在一起。
- 辨識訊號（各版本）✅（Aivosto 頁面）：
  - **LCOM1**（CK 原版）：P = 不共用欄位的方法對數、Q = 共用的對數；LCOM1 = P−Q（P>Q 時），否則 0。0 = 內聚；>0 = 可拆。缺點：很多差異很大的類別都得 0。
  - **LCOM2** = 1 − Σ(mA)/(m×a)；**LCOM3**（Henderson-Sellers 的 LCOM*）= (m − Σ(mA)/a)/(m−1)。⚠ Aivosto 同一頁對兩者值域前後說法不一（一處說 LCOM3 在 [0,1]、LCOM2 在 [0,2]；另一處說 LCOM3 介於 0–2、1–2 為警訊）。
  - **LCOM4**（Hitz & Montazeri，Aivosto 推薦）：方法之間（經共用欄位或互相呼叫）連通的元件數。=1 內聚；≥2 應拆成那麼多個類別；=0 表示沒有方法 ✅。CodeScene 的 Low Cohesion 也用 LCOM4 ✅。
  - **TCC** = 直接相連的方法對 / 所有可能方法對，值域 0–1；Aivosto：<0.5 視為不內聚；Lanza & Marinescu 的 God Class 用 **TCC < 1/3** ✅。**LCC** 另含間接連結，TCC ≤ LCC；LCC=0.8 算「相當內聚」✅。
  - **NDepend**：LCOM = 1 − Σ(MF)/(M×F)、LCOM HS = (M − Σ(MF)/F)/(M−1)；文件建議 LCOM >0.8 且欄位 >10 且方法 >10「可能有問題」、LCOM HS >1.0（同條件）「應避免」✅。⚠ NDepend 規則 ND1007 的說明文字寫「LCOM 高於 0.84」，實際 CQLinq 寫 `t.LCOM > 0.91`——同一工具文件與實作不一致。
- 為何有害：低內聚 = 一個類別裝了好幾個責任，讀者要分辨哪些方法跟哪些欄位是一組。
- 解法：依 LCOM4 的連通元件 Extract Class。
- 何時不算：欄位少、方法少的小類別（NDepend 規則都加了「欄位 >10、方法 >10」前提）✅；只有 getter/setter 的資料類別、以介面方法為主的 facade。
- 來源：https://www.aivosto.com/project/help/pm-oo-cohesion.html ；https://www.ndepend.com/docs/code-metrics ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html

### Fan-in / Fan-out（扇入／扇出）
- 定義：Fan-in = 有多少其他元件呼叫或傳資訊給本元件；Fan-out = 本元件呼叫或傳資訊給多少元件 ✅。Henry & Kafura（1981，IEEE TSE SE-7(5)）資訊流複雜度 = 長度 × (fan-in × fan-out)² ⚠。
- 辨識訊號：Henry-Kafura 無公認門檻 ❓；Better Code Hub：模組被呼叫（incoming calls）≤**10** ✅。
- 為何有害：高 fan-out = 讀懂本元件要先懂很多別的；高 fan-in = 改它會波及很多呼叫者（與 Shotgun Surgery 的 CM/CC 同一概念）。
- 解法：高 fan-out → 拆責任；高 fan-in 而且常改 → 穩定其介面或拆分。
- 何時不算：高 fan-in 的穩定工具函式（字串處理、日誌）是好的重用，不是壞味道。
- 來源：https://www.aivosto.com/project/help/pm-proc-infoflow.html ；https://dev.to/brunooliveira/measuring-code-quality-with-bettercodehub-5cde

### Halstead Metrics（Halstead 度量）
- 定義：以運算子與運算元的種類數與出現次數推算「程式量」✅。n1、n2 = 相異運算子、運算元數；N1、N2 = 總出現次數。詞彙量 n = n1+n2；長度 N = N1+N2；**Volume V = N × log2(n)**；**Difficulty D = (n1/2) × (N2/n2)**；Effort E = D × V；時間 T = E/18 秒；預估缺陷數 B = V/3000 ✅。
- 辨識訊號：無公認門檻 ❓；主要用途是作為 Maintainability Index 的輸入。
- 為何有害：D 高代表用了很多種運算子、同一批運算元被反覆使用——讀起來要追很多東西。
- 解法：拆函式、引入解釋變數。
- 何時不算：T、B 這類推估值不該當成真實工時或缺陷數。
- 來源：https://en.wikipedia.org/wiki/Halstead_complexity_measures

### Maintainability Index（可維護性指數，MI）
- 定義：由 Halstead Volume、Cyclomatic Complexity、行數合成的單一分數 ✅。
- 辨識訊號：
  - 原始公式：`MI = 171 − 5.2·ln(Halstead Volume) − 0.23·(Cyclomatic) − 16.2·ln(LOC)`；Visual Studio 改為 `MAX(0, 原式 × 100 / 171)`，值域 0–100 ✅。
  - Visual Studio 門檻：**0–9 紅**（低）、**10–19 黃**（中）、**20–100 綠**（良）✅。微軟自述：門檻刻意保守，「80-20 切分以壓低雜訊，只標示可疑程式」，紅色時要能高度確信真有問題 ✅。
  - .NET CA1505 預設 MI **<10** 報警 ✅；NDepend ND1009：LOC ≥30 **且** MI ≤35 **且** Cyclomatic ≥20 ✅。
- 為何有害：分數低通常同時代表長、複雜、運算量大。
- 解法：看是哪個輸入拉低分數，再對症處理。
- 何時不算：MI 是三個度量的合成值，大部分變化其實來自行數（公式中 ln(LOC) 係數最大）——單看 MI 無法知道問題在哪；不要把 MI 當目標值優化。
- 來源：https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-maintainability-index-range-and-meaning ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1505 ；https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html

---

## G. 偵測策略（Detection Strategies：多度量組合）

Lanza & Marinescu《Object-Oriented Metrics in Practice》（Springer, 2006）的核心主張：**單一度量回答不了設計問題，要用多個度量以 AND/OR 組合成「偵測策略」**（概念 2002 年提出）✅。門檻分兩種來源 ✅：

- **統計門檻**：取參考系統的平均（AVG）與標準差（STDEV）——Low = AVG−STDEV、High = AVG+STDEV、Very High = High × 1.5。書中依 45 個 Java 與 37 個 C++ 系統得出 ✅：

  | 度量 | Java Low / Avg / High / Very High | C++ Low / Avg / High / Very High |
  |---|---|---|
  | CYCLO / LOC | 0.16 / 0.20 / 0.24 / 0.36 | 0.20 / 0.25 / 0.30 / 0.45 |
  | LOC / 方法 | 7 / 10 / 13 / 19.5 | 5 / 10 / 16 / 24 |
  | NOM（方法數）/ 類別 | 4 / 7 / 10 / 15 | 4 / 9 / 15 / 22.5 |

- **語意門檻**：常用分數（1/4、1/3、1/2、2/3、3/4）與共識數量詞（NONE=0、FEW、SEVERAL、MANY、SHORT MEMORY CAP）✅。⚠ FEW 的數值各處不同：UFMG 講義以 ATFD 舉例 FEW=3；PMD 的 GodClass 實作用 ATFD **>5**。SEVERAL、MANY、SHORT MEMORY CAP 的確切數值 ❓ 未查證。

### God Class（上帝類別）偵測策略
- 定義：集中系統智慧、什麼都做、還大量取用小資料類別資料的類別 ✅。
- 辨識訊號：**ATFD（Access To Foreign Data，存取外部類別屬性數）> FEW AND WMC ≥ VERY HIGH AND TCC < 1/3** ✅。PMD 實作：WMC ≥ **47**、ATFD > **5**、TCC < **1/3** ✅。
- 為何有害：高複雜、低內聚、依賴外部資料——三者同時成立才報，避免單一數字誤判。
- 解法：依 TCC/LCOM4 的方法群組 Extract Class；把用到外部資料的邏輯搬回資料所在處。
- 何時不算：協調者（orchestrator）類別刻意集中流程控制，但本身不持有業務規則；責任軸清楚的 partial 類別切片（數量多不等於壞，先問切分軸）。
- 來源：https://github.com/pmd/pmd/blob/main/pmd-java/src/main/java/net/sourceforge/pmd/lang/java/rule/design/GodClassRule.java ；https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/lectures/detection-strategy_v01.pdf

### Feature Envy（依戀情結）偵測策略
- 定義：方法用別的類別的資料比用自己類別的還多 ✅。
- 辨識訊號：**ATFD > FEW AND LAA（Locality of Attribute Accesses，本類別屬性存取占比）< 1/3 AND FDP（Foreign Data Providers，外部資料提供者類別數）≤ FEW** ✅。
- 為何有害：行為與資料分居，讀者要在兩個類別間來回。
- 解法：Move Method 到資料所在的類別（JDeodorant 自動提出此重構）✅。
- 何時不算：Strategy、Visitor 等刻意把行為與資料分離的模式。
- 來源：https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/lectures/detection-strategy_v01.pdf

### God Method / Brain Method（上帝方法／腦方法）偵測策略
- 定義：過長、分支多、用到大量變數的方法 ✅。
- 辨識訊號：**LOC > High(class)/2 AND CYCLO ≥ High AND NOAV（Number of Accessed Variables，存取的屬性＋區域變數＋參數數）> MANY** ✅（UFMG 講義版本）。書中 Brain Method 另含最大巢狀深度條件 ❓ 未查證確切形式。CodeScene 的 Brain Method：「單一函式集中太多行為，變成區域熱點」✅。
- 為何有害：同時具備長、彎多、要記的變數多三種負荷。
- 解法：Extract Function；把區域變數變成新類別的欄位（Replace Function with Command）。
- 何時不算：產生的程式、解析器的大型 switch 分派。
- 來源：https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/lectures/detection-strategy_v01.pdf ；https://docs.enterprise.codescene.io/versions/6.0.6/guides/technical/code-health.html

### Refused Parent Bequest（拒絕父類遺贈）偵測策略
- 定義：子類別幾乎不用父類別給的東西，卻又不是小類別 ✅。
- 辨識訊號：**（NProtM > FEW AND (BUR < 1/3 OR BOvR < 1/3)）AND（(AMW > AVG OR WMC ≥ AVG) AND NOM > AVG）**；NProtM = 父類 protected 成員數、BUR = 基底類別使用率、BOvR = 基底類別覆寫率、AMW = 平均方法權重 ✅。
- 為何有害：繼承關係是假的，讀者以為子類別是父類別的一種，其實不是（也是 Yo-yo 的來源之一）。
- 解法：Replace Subclass with Delegate；Push Down 不需要的成員。
- 何時不算：父類別提供的是可選的掛勾（hook）方法。
- 來源：https://homepages.dcc.ufmg.br/~figueiredo/disciplinas/lectures/detection-strategy_v01.pdf

（Shotgun Surgery 的偵測策略見 C 類同名條目。）

---

## H. 偵測工具一覽

| 工具 | 性質 | 與本切面相關的能力與預設門檻 | 查證 | 來源 |
|---|---|---|---|---|
| **SonarQube / SonarLint** | 商用＋社群版靜態分析 | S3776 Cognitive 15（C/C++/ObjC 25）；S1541 Cyclomatic 10；S134 巢狀 3；S1067 運算式運算子 3；S107 參數 7；S138 方法 75 行；S104 檔案 750 行；S110 繼承深度 5（以上為 sonar-java 原始碼預設值，其他語言可能不同）；規則標籤 `brain-overload` | ✅ | https://github.com/SonarSource/sonar-java/tree/master/java-checks/src/main/java/org/sonar/java/checks |
| **NDepend** | .NET 商用分析器，CQLinq（以 LINQ 寫規則） | ND1000 型別 >200 LOC；ND1001 >20 方法；ND1002 >15 欄位（Unity 專案 30）；ND1003 IL 巢狀 >2 且 CC >17；ND1004 參數 ≥8；ND1005 多載 ≥7；ND1006 註解 ≤5% 且 ≥30 行且 CC ≥3；ND1007 LCOM >0.91 且欄位 >10 且方法 >10；ND1008 區域變數 >15；ND1009 LOC ≥30 且 MI ≤35 且 CC ≥20；ND1904 getter 應為純函式；ND1905 欄位不得從外部寫入；可用 `MethodsAssigningMe` 等自寫狀態所有權查詢 | ✅ | https://www.ndepend.com/default-rules/NDepend-Rules-Explorer.html ；https://www.ndepend.com/docs/code-metrics |
| **Visual Studio Code Metrics** | IDE 內建 | MI（0–9 紅、10–19 黃、20–100 綠）、Cyclomatic、DIT、Class Coupling、原始碼行數、可執行行數；忽略多數產生的程式碼（WinForms 產生碼除外） | ✅ | https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-values |
| **.NET 程式碼分析器（Microsoft.CodeAnalysis.NetAnalyzers）** | Roslyn 分析器，預設不啟用以下規則 | CA1501 繼承深度 5；CA1502 Cyclomatic 25；CA1505 MI <10；CA1506 耦合 型別 95／其他 40；以 `CodeMetricsConfig.txt`（AdditionalFiles）調整 | ✅ | https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1502 |
| **Roslynator** | 開源 C# 分析器＋重構集合（RCS 規則） | 以風格、簡化、去冗餘為主；依搜尋結果未見內建 Cognitive/Cyclomatic 規則 | ⚠ | https://github.com/dotnet/Roslynator |
| **ReSharper / Rider** | JetBrains IDE | 第三方外掛「Cognitive Complexity」（Matthias Koch）依 Sonar 白皮書即時計分，門檻可依語言設定、以 Code Vision 呈現；預設數值 ❓ | ⚠ | https://github.com/matkoch/resharper-cognitivecomplexity |
| **PMD** | 開源 Java 等靜態分析 | CognitiveComplexity 15；CyclomaticComplexity 方法 10／類別 80；NPath 200；ExcessiveParameterList 10；NcssCount 方法 60／類別 1500；CouplingBetweenObjects 20；ExcessivePublicCount 45；TooManyFields 15；TooManyMethods 10；AvoidDeeplyNestedIfStmts 3；LawOfDemeter trustRadius 1；GodClass（WMC 47、ATFD 5、TCC 1/3）；DataClass | ✅ | https://pmd.github.io/pmd/pmd_rules_java_design.html |
| **DECOR / DETEX** | 學術（Moha 等，IEEE TSE 2010） | 以規格化語言描述並自動產生偵測演算法；涵蓋 Blob、Functional Decomposition、Spaghetti Code、Swiss Army Knife 四個反模式及其底下 15 個 code smell | ✅ | https://hal.univ-grenoble-alpes.fr/INRIA-RENNES/inria-00538476v1 |
| **JDeodorant** | 學術 Eclipse 外掛（Tsantalis 等） | 偵測 Feature Envy、Type Checking、Long Method、God Class、Duplicated Code，並自動套用 Move Method、Replace Conditional with Polymorphism、Extract Method、Extract Class、Extract Clone | ✅ | https://2011.icse-conferences.org/content/jdeodorant-identification-and-application-extract-class-refactorings.html |
| **iPlasma / inCode** | 學術（Marinescu 團隊） | iPlasma：物件導向設計品質評估整合平台（C++、Java），實作偵測策略；inCode：Eclipse 外掛，邊打字邊偵測設計問題 | ✅ | https://staff.cs.upt.ro/~radum/projects.html |
| **CodeScene** | 商用行為式程式分析 | Code Health 1–10（≥9 健康、4–9 警告、<4 警報），彙整 25+ 因子：Brain Method、Bumpy Road、Nested Complexity、Complex Conditional、Low Cohesion（LCOM4）、Large Method、Primitive Obsession、DRY 違反等；Hotspot（變動頻率 × 健康度）與 change coupling（變動耦合） | ✅ | https://en.wikipedia.org/wiki/CodeScene ；https://codescene.io/docs/guides/technical/hotspots.html |
| **IDEAL / LAPD** | 學術，語言學反模式偵測 | IDEAL 支援 Java、C#（基於 srcML），平均精確率 75.27%；LAPD 72% | ✅ | https://arxiv.org/abs/2107.08344 |

**沒有任何主流工具直接量測**：跨函式的讀路徑長度（轉手層數）、同一欄位的寫入點數門檻、時序耦合。這三項需用 NDepend CQLinq／Roslyn 自寫查詢，或交給 LLM 語意審查。

---

## I. 數字不是判決

### Metric Fixation / Goodhart's Law（度量固著／古德哈特定律）
- 定義：把度量當目標後，度量就失效。Goodhart（1975）原文：「任何觀察到的統計規律，一旦被施壓用於控制，就會傾向崩潰」；Strathern（1997）的通行說法：「當一個量測變成目標，它就不再是好的量測」✅。
- 辨識訊號：為了壓低 Cognitive Complexity 把邏輯拆成一串只呼叫一次的小函式（分數降、讀路徑變長）；為了 MI 變綠而縮行；把門檻寫進 CI 當硬閘後出現大量 suppress。NIST 記錄過一個真實案例：有人自創「修正版複雜度」把 Cyclomatic 除以 switch 分支數，結果能把 90 的模組「降」成 10 ✅。
- 為何有害：門檻本身就是經驗值、且各工具互相矛盾——
  - Sonar 的 15 是「從 10 往上調到雜訊可接受」✅；VS 的 MI 門檻是「80-20 切分壓低雜訊」✅。
  - 參數上限：Sonar 7、NDepend 8、PMD 10、Better Code Hub 2；方法長度：BCH 15、NDepend 20/40、PMD 60、Sonar 75；Cyclomatic：BCH 5、McCabe 10、NDepend 15/30、CA1502 25 ✅。
  - 同一工具文件與實作不一致（NDepend ND1007 說明 0.84、程式 0.91）；同一參考網頁前後矛盾（Aivosto 的 LCOM2/LCOM3 值域）⚠。
  - Cognitive Complexity 的實證只證明它與理解時間、主觀評分相關，與理解正確率是混合結果 ✅。
  - Fowler：壞味道是「通常對應更深層問題的表面跡象」，但「不一定代表有問題」，看到後要深入檢查而不是自動修正 ✅。
- 解法：
  - 採 NIST 的政策形式：「要嘛低於門檻，要嘛**書面說明為何超過**」✅。
  - 度量只當排序與提問的線索：數字大 → 問「責任軸是否清楚？同一狀態有幾個寫入點？讀者要拐幾個彎？」。
  - 以基準資料推門檻而不是抄數字：Alves、Ypma、Visser（SIG, 2010）從 100 個系統的量測資料彙整分佈推導門檻（論文例示以 70% 分位為「正常」上界）⚠。
- 何時不算：安全、正確性類規則（不是可讀性度量）可以當硬閘。
- 來源：https://en.wikipedia.org/wiki/Goodhart%27s_law ；https://www.mccabe.com/pdf/mccabe-nist235r.pdf ；https://martinfowler.com/bliki/CodeSmell.html ；https://community.sonarsource.com/t/s3776-reason-for-the-current-default-value-of-15/127103 ；https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-maintainability-index-range-and-meaning

### Hotspot Analysis（熱點分析：變動頻率 × 複雜度）
- 定義：只看複雜度會找到一堆「很複雜但沒人碰」的程式；把版本控制的**變動頻率**和**複雜度（或大小、健康度）**相乘，才找到「又難讀、又常被改」真正花成本的地方 ✅（Adam Tornhill《Your Code as a Crime Scene》, 2015；概念借自犯罪學的地理側寫）。
- 辨識訊號：
  - Tornhill：單看變動頻率或單看行數都是弱預測因子，兩者合併才是程式開始腐化的好指標 ⚠。
  - InfoQ 報導的案例：400 KLOC、89 位開發者、18,000+ commits，**4% 的程式造成 72% 的缺陷** ✅。
  - CodeScene 文件：優先熱點只占程式庫 1.2%，卻吃掉 12.5% 開發投入，且包含 45% 被修的 bug ✅。
  - Tornhill & Borg〈Code Red〉（TechDebt 2022，39 個商業程式庫）：低品質程式缺陷多 **15 倍**、解 issue 的開發時間平均多 **124%**、最長週期時間長 **9 倍** ✅。
  - Change coupling（變動耦合）：總是一起被改的檔案 = Shotgun Surgery 的歷史證據。
- 為何有害：（指「不用熱點」的害處）把重構預算平均撒在所有超標程式上，大部分投在沒人會再讀的地方。
- 解法：先排熱點，再在熱點內用本文 A–E 類條目做語意審查；冷區的高複雜度先記錄不急著修。
- 何時不算：新專案沒有足夠歷史；安全或正確性關鍵的冷區程式仍需審。
- 來源：https://www.infoq.com/news/2015/03/code-as-a-crime-scene ；https://codescene.io/docs/guides/technical/hotspots.html ；https://arxiv.org/abs/2203.04374 ；https://en.wikipedia.org/wiki/CodeScene

---

## 總表：度量—門檻—出處

> 「預設值」= 工具出廠設定或文獻建議，不是品質判決。✅ 已查證｜⚠ 二手或來源矛盾｜❓ 未查證。

| 度量 | 層級 | 門檻 | 出處 | 查證 |
|---|---|---|---|---|
| Cognitive Complexity | 方法 | 15 | SonarQube S3776（多數語言）、PMD | ✅ |
| Cognitive Complexity | 方法 | 25 | SonarQube S3776（C/C++/ObjC） | ✅ |
| Cyclomatic Complexity | 模組 | 10（條件嚴格時可到 15，或書面說明） | McCabe 1976；NIST SP 500-235 §2.5 | ✅ |
| Cyclomatic Complexity | 方法 | 10 | SonarQube S1541；PMD | ✅ |
| Cyclomatic Complexity | 類別 | 80 | PMD | ✅ |
| Cyclomatic Complexity | 方法 | 25 | .NET CA1502 | ✅ |
| Cyclomatic Complexity | 方法 | >15 難懂／>30 應拆 | NDepend 文件 | ✅ |
| Cyclomatic Complexity | 方法 | ≤5（分支點 ≤4） | SIG／Better Code Hub | ✅ |
| NPath | 方法 | 200 | PMD | ✅ |
| 巢狀深度 | 方法 | 3 | SonarQube S134；PMD AvoidDeeplyNestedIfStmts | ✅ |
| 巢狀深度（IL） | 方法 | >4 難懂／>8 應拆；規則 ND1003：>2 且 CC >17 | NDepend | ✅ |
| 巢狀深度（認知） | — | 超過 3 層很少人能理解 | Yourdon 1986（Code Complete 19.4 引） | ✅ |
| 布林運算式運算子數 | 運算式 | 3 | SonarQube S1067 | ✅ |
| 方法長度 | 方法 | 75 行 | SonarQube S138（Java） | ✅ |
| 方法長度 | 方法 | 60 NCSS | PMD NcssCount | ✅ |
| 方法長度 | 方法 | >20 難懂／>40 應拆 | NDepend 文件 | ✅ |
| 方法長度 | 方法 | 60 行（「印得進一頁」的舊理由） | NIST SP 500-235 §3.1 | ✅ |
| 方法長度 | 方法 | 15 行 | SIG／Better Code Hub | ✅ |
| 檔案／類別長度 | 檔案 | 750 行 | SonarQube S104（Java） | ✅ |
| 檔案／類別長度 | 型別 | 200 LOC | NDepend ND1000 | ✅ |
| 檔案／類別長度 | 類別 | 1500 NCSS | PMD NcssCount | ✅ |
| 參數數 | 方法 | 7 | SonarQube S107 | ✅ |
| 參數數 | 方法 | ≥8（文件：>5 呼叫痛苦） | NDepend ND1004 | ✅ |
| 參數數 | 方法 | 10 | PMD ExcessiveParameterList | ✅ |
| 參數數 | 方法 | ≤2 | Better Code Hub（部落格轉述） | ⚠ |
| 區域變數數 | 方法 | >8 難懂／>15 應拆 | NDepend 文件、ND1008 | ✅ |
| 多載數 | 方法 | ≥7（文件：>6） | NDepend ND1005 | ✅ |
| 方法數 | 類別 | 10 | PMD TooManyMethods | ✅ |
| 方法數 | 類別 | >20（且有非常數欄位） | NDepend ND1001 | ✅ |
| 方法數 | 類別 | 20 或 50；或 ≤10% 類別超過 24 | Aivosto 引用 | ✅ |
| 欄位數 | 類別 | 15 | PMD TooManyFields；NDepend ND1002（Unity 30） | ✅ |
| 公開成員數 | 類別 | 45 | PMD ExcessivePublicCount | ✅ |
| WMC | 類別 | VERY HIGH = 47 | Lanza & Marinescu（PMD GodClass） | ✅ |
| DIT | 類別 | 5 | .NET CA1501；SonarQube S110 | ✅ |
| DIT | 類別 | ≥6 可能難維護 | NDepend 文件 | ✅ |
| DIT | 類別 | ≤5（有人允許 8） | Aivosto | ✅ |
| NOC | 類別 | 無公認門檻（高 NOC 與較少缺陷相關） | Aivosto | ✅ |
| CBO | 類別 | >14 太高 | Aivosto | ✅ |
| CBO | 類別 | 20 | PMD CouplingBetweenObjects | ✅ |
| Class Coupling | 型別／成員 | 95／40 | .NET CA1506 | ✅ |
| Efferent Coupling（TypeCe） | 型別 | >50 | NDepend 文件 | ✅ |
| RFC | 類別 | 無查得門檻（常見「50」之說未查證） | Aivosto | ❓ |
| LCOM（NDepend 定義） | 類別 | >0.8 且欄位 >10 且方法 >10；規則 ND1007 實作 >0.91（說明寫 0.84） | NDepend | ⚠ |
| LCOM HS | 類別 | >1.0 且欄位 >10 且方法 >10 | NDepend 文件 | ✅ |
| LCOM4 | 類別 | =1 內聚；≥2 應拆 | Aivosto；CodeScene 採用 | ✅ |
| TCC | 類別 | <1/3（God Class）；<0.5 不內聚 | Lanza & Marinescu；Aivosto | ✅ |
| ATFD | 類別／方法 | > FEW（PMD 實作 5；UFMG 講義例示 3） | Lanza & Marinescu | ⚠ |
| LAA | 方法 | <1/3（Feature Envy） | Lanza & Marinescu | ✅ |
| CYCLO/LOC、LOC/方法、NOM/類別 | 統計 | 見 G 節表（Java High：0.24／13／10） | Lanza & Marinescu（45 個 Java 系統） | ✅ |
| Fan-in（incoming calls） | 模組 | ≤10 | Better Code Hub | ✅ |
| Henry-Kafura 資訊流 | 程序 | 無公認門檻 | Henry & Kafura 1981 | ❓ |
| Halstead | 程序 | 無公認門檻；B = V/3000 為推估 | Halstead | ✅ |
| Maintainability Index | 方法／型別 | 0–9 紅、10–19 黃、20–100 綠 | Visual Studio | ✅ |
| Maintainability Index | 符號 | <10 | .NET CA1505 | ✅ |
| Maintainability Index | 方法 | ≤35 且 LOC ≥30 且 CC ≥20 | NDepend ND1009 | ✅ |
| 註解比例 | 方法 | ≤5% 且 ≥30 行且 CC ≥3 | NDepend ND1006 | ✅ |
| Code Health | 檔案 | ≥9 健康、4–9 警告、<4 警報 | CodeScene | ✅ |
| 熱點 | 檔案 | 無固定門檻；以變動頻率 × 複雜度排序 | Tornhill；CodeScene | ✅ |
| 讀路徑拐彎數 | 一個構想 | >3 彎為壞味道 | 使用者審查原則；佐證 Cowan 3–5 意元 | ❓ |
| 同欄位寫入點 | 欄位 | 無數字門檻；外部寫入即報 | NDepend ND1905 | ✅（規則）／❓（數字） |
| LA 偵測精確率 | — | IDEAL 75.27%、LAPD 72% | IDEAL 論文 | ✅ |

---

## 未查證與待補清單

- ❓ 讀路徑「>3 彎」門檻：無業界來源，是審查原則；工作記憶數據只是數量級佐證。
- ❓ 同一欄位寫入點的數字門檻：查無業界標準。
- ❓ Lanza & Marinescu 的 SEVERAL、MANY、SHORT MEMORY CAP 確切數值；Brain Method 的巢狀條件確切形式。
- ❓ RFC 的常見門檻（如 50）。
- ❓ Clean Code F1 參數數的書中原文數字。
- ❓ Butler 等命名準則的各項數字門檻。
- ❓ CodeScene Bumpy Road 等各壞味道的內部計算門檻；ReSharper Cognitive Complexity 外掛的預設數值。
- ⚠ Ousterhout 紅旗、Fowler 2nd ed 壞味道定義、Clean Code 啟發編號：只讀到二手整理，未讀原書。
- ⚠ Better Code Hub「參數 ≤2」只見部落格轉述（SIG 原書數字未查證）。
- ⚠ Alves 等 2010 的分位數方法只讀到搜尋摘要。
- ⚠ Roslynator 無複雜度規則的判斷來自搜尋摘要，未逐條比對其 500+ 規則。
- 查證過程備註：rules.sonarsource.com 被抓取限制擋下，Sonar 門檻改由 GitHub 上 sonar-java 原始碼確認（master 分支，C# 版 sonar-dotnet 數值可能不同）。
