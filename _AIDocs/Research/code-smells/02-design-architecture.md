# 02 設計層與架構層壞味道（Design & Architecture Smells）

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 切面範圍：比單一函式大的尺度——類別之間的設計關係、套件／元件（package／component，一組一起發布的類別）、分層、整個系統、微服務。
> 查證日：2026-10-08。所有定義與門檻都對過下方列出的來源。

## 0. 讀前須知

**標記規則**
- 「辨識訊號」裡的數字門檻，一律註明是**哪個工具或哪篇論文**的預設值。不同工具的門檻差很多，請把它們當成「起點」，不要當成「標準」。
- 「常見解法」和「何時不算」如果來源沒有寫，而是本文根據一般工程知識推出來的，會標 **〔推論〕**。
- **未查證** = 找不到可靠來源；照實標出，不補來源。

**常用術語白話**
- **fan-in／fan-out**：有多少別的型別依賴我／我依賴多少別的型別。
- **Ca（afferent coupling，傳入耦合）**：套件外有多少類別依賴本套件。**Ce（efferent coupling，傳出耦合）**：本套件依賴多少套件外的類別。
- **I（Instability，不穩定度）**= Ce / (Ca + Ce)，範圍 0–1。0 = 只被別人依賴、自己不依賴別人（最穩定，很難改）；1 = 只依賴別人（最容易改）。
- **A（Abstractness，抽象度）**= Na / Nc（抽象類別數 / 類別總數），範圍 0–1。
- **D（Distance from Main Sequence，與主序列的距離）**= |A + I − 1|，範圍 0–1。0 = 剛好落在理想線上（Wikipedia 的寫法；Martin 2000 原文另有一個除以 √2 的版本 D，範圍 0–約 0.707，正規化後的 D′ 範圍 0–1）。
- **DIT（Depth of Inheritance Tree，繼承深度）**、**NOC（Number of Children，直接子類別數）**、**WMC（Weighted Methods per Class，類別內各方法複雜度的總和）**、**LCOM（Lack of Cohesion of Methods，方法間缺乏內聚的程度）**。
- **強連通分量（strongly connected component，SCC）**：依賴圖裡彼此都能走到對方的一群節點。SCC 大小 > 1 就表示有循環依賴。
- **co-change（共同變更）**：從版控歷史看，兩個檔案常在同一個 commit 一起被改。

---

## 1. 這個切面的分類架構（建議的分類樹）

```
設計與架構壞味道
├─ A. 設計原則違反（PHAME 四類，類別之間的設計）—— 每個味道都對到一條被違反的原則，順著原則就找得到解法
│   ├─ A1 抽象（Abstraction）：概念沒抽出來、抽錯、抽太多、抽了沒用
│   ├─ A2 封裝（Encapsulation）：該藏的沒藏、藏了卻沒用
│   ├─ A3 模組化（Modularization）：責任切得太大、太散、互相纏繞、變成依賴樞紐
│   └─ A4 階層（Hierarchy）：繼承該有沒有、多餘、太寬太深、IS-A 關係不成立、循環
├─ B. 設計腐化徵兆（Martin 七味）—— 從「改起來的感覺」看症狀，不指出位置，是 A／D／E 的「病徵層」
├─ C. SOLID 違反 —— 五條原則被違反時，各自長出哪些 A 類味道（交叉索引）
├─ D. 套件／元件原則違反（ADP／SDP／SAP）—— 用 Ca／Ce／I／A／D 量化套件之間的依賴方向
├─ E. 架構壞味道（研究文獻與工具）—— 元件、連接器、分層、子系統尺度；可用 Arcan／Designite 等工具偵測
│   ├─ E1 依賴結構類：Cyclic Dependency、Hub-Like、Unstable Dependency、Dense Structure、Unstable Interface、Implicit Cross-module Dependency、Abstraction without Decoupling
│   ├─ E2 關注點類：God Component、Feature Concentration、Scattered Parasitic Functionality
│   ├─ E3 介面與連接器類：Ambiguous Interface、Connector Envy、Extraneous Adjacent Connector
│   └─ E4 分層與子系統類：Layer Violation、Subsystem-API Bypassed、套件結構失衡
├─ F. 經典架構反模式（anti-pattern：常見、看起來合理、但結果有害的做法）—— 整個系統或團隊實踐尺度
└─ G. 微服務壞味道 —— 服務切分、資料所有權、服務間通訊、部署獨立性
    ├─ G1 技術—內部：Megaservice、Hardcoded Endpoints、Inappropriate Service Intimacy、API Versioning、Local Logging
    ├─ G2 技術—通訊：Cyclic Dependency、ESB Usage、No API Gateway、Shared Libraries、Wobbly Service Interactions
    ├─ G3 技術—其他：Shared Persistence、Wrong Cuts、Lack of Monitoring、Distributed Monolith
    └─ G4 組織：Legacy Organization、Common Ownership、Microservice Greedy、Too Many Technologies 等
```

分類依據：
- A 類沿用 Suryanarayana、Samarthyam、Sharma《Refactoring for Software Design Smells》（2014）的 **PHAME**（Principles of Hierarchy, Abstraction, Modularization, Encapsulation，階層、抽象、模組化、封裝四條原則）。這四條原則源自 Booch 的物件模型。書中收錄 25 個結構性設計味道，命名規則是「形容詞 + 原則名」，名字本身就說明了哪條原則被怎麼違反。
- E 類依 Azadi & Arcelli Fontana〈Architectural Smells Detected by Tools: a Catalogue Proposal〉的歸納，再加上 Garcia 等人（2009）和 Mo 等人（2015 Hotspot Patterns）的味道。
- G 類沿用 Taibi、Lenarduzzi、Pahl〈Microservices Anti-Patterns: A Taxonomy〉的「技術／組織」二分法，再補上 Neri 等人的多聲道文獻回顧（multivocal review）和 Newman 的 Distributed Monolith。

### 1.1 與「函式／類別層經典味道」的對應（避免重複）

下表左欄的味道，主條目在 `01-classic-catalog.md`。本檔只補上**設計層的觀點**（違反哪條原則）和**工具門檻**，害處與重構步驟不重寫。

| 本切面味道 | 對應的經典味道（01） | 本檔角色 |
|---|---|---|
| Missing Abstraction | Primitive Obsession、Data Clumps | 補原則觀點 |
| Multifaceted Abstraction | Divergent Change（Brown：Swiss Army Knife） | 補 DesigniteJava 門檻 |
| Unnecessary Abstraction | Lazy Element（F1：Lazy Class） | 補門檻 |
| Unutilized Abstraction | Speculative Generality、Dead Code | 補門檻、命名衝突 |
| Duplicate Abstraction | Duplicated Code、Alternative Classes with Different Interfaces | 補 clone 分型 |
| Incomplete Abstraction | Incomplete Library Class | 補互補方法訊號 |
| Deficient Encapsulation | Indecent Exposure（Kerievsky） | 補門檻 |
| Unexploited Encapsulation、Missing Hierarchy | Repeated Switches（F1：Switch Statements） | 區分兩者 |
| Broken Modularization | Data Class（常與 Feature Envy 並存） | 補門檻 |
| Insufficient Modularization | Large Class（God Class、The Blob） | **只補門檻**，主條目在 01 |
| Rebellious Hierarchy | Refused Bequest | **只補門檻**，主條目在 01 |
| Speculative Hierarchy | Speculative Generality | 補階層版本 |
| Scattered Parasitic Functionality | Shotgun Surgery | Garcia 明說兩者不同（見 E 條目） |
| Connector Envy | Feature Envy（名稱類比） | 元件／連接器尺度 |
| Singleton Abuse | Global Data、Mutable Data | 補架構觀點 |
| Anemic Domain Model | Data Class + Feature Envy 的領域層版本 | 架構層主條目 |

**一般規則**：類別層味道放大到套件／元件／服務尺度，會換一個名字再出現一次。例如 Large Class → God Component → Megaservice；Feature Envy → Connector Envy → Inappropriate Service Intimacy；循環依賴則從類別、套件一路到服務都有。本檔每個尺度各寫一條，並互相標註。

### 1.2 工具預設門檻速查（DesigniteJava 原始碼 `ThresholdsDTO.java`）

| 味道 | 規則（實際程式碼邏輯） |
|---|---|
| Imperative Abstraction | 公開方法數 == 1，且該方法 > 50 行 |
| Multifaceted Abstraction | LCOM ≥ 0.8 **且** 欄位 ≥ 7 **且** 方法 ≥ 7 |
| Unnecessary Abstraction | 方法數 == 0 且欄位 ≤ 5 |
| Unutilized Abstraction | 無 fan-in（有父型別時：父型別也無 fan-in，或自身無 fan-in） |
| Deficient Encapsulation | 公開欄位數 > 0 |
| Unexploited Encapsulation | 同一方法對同一階層中 ≥ 2 個不同型別做 instanceof |
| Broken Modularization | 方法數 == 0 且欄位 ≥ 5 |
| Insufficient Modularization | 公開方法 ≥ 20 **或** 方法 ≥ 30 **或** WMC ≥ 100 |
| Hub-like Modularization | fan-in ≥ 20 **且** fan-out ≥ 20 |
| Cyclically-dependent Modularization | 所在 SCC 大小 > 1 |
| Missing Hierarchy | 方法中 instanceof 的型別有 ≥ 2 個不在自己的祖先鏈中 |
| Deep Hierarchy | DIT > 6 |
| Wide Hierarchy | NOC > 10 |
| Rebellious Hierarchy | 覆寫父類別方法，且實作為空或只有一行 throw |
| Broken Hierarchy | 有父型別、有公開方法，卻沒覆寫任何父型別方法 |

來源：https://github.com/tushartushar/DesigniteJava/blob/master/src/Designite/smells/ThresholdsDTO.java 、https://github.com/tushartushar/DesigniteJava/tree/master/src/Designite/smells/designSmells

---

## 2. 條目

## A. 設計原則違反（PHAME）

### A1 抽象類（Abstraction smells）

### Missing Abstraction（缺失抽象）
- 別名：Primitive Obsession、Data Clumps（Fowler）
- 定義：該有自己的類別或介面的概念，卻用一團資料或編碼過的字串代替。
- 辨識訊號：同一組欄位或參數反覆一起出現在多個方法簽章；把結構化資訊編成字串或整數，再到處 split／parse。DesigniteJava 不偵測這個味道。
- 為何有害：驗證和相關行為散落在各個呼叫點；型別系統幫不上忙；改格式就得改所有呼叫點。
- 常見解法：Extract Class、Introduce Parameter Object、Replace Primitive with Object（值物件）。
- 何時不算：跨程序邊界的序列化格式或 DTO 本來就是扁平的〔推論〕；效能熱點刻意用原生型別〔推論〕。
- 來源：https://www.tusharma.in/smells/MA.html

### Imperative Abstraction（命令式抽象）
- 別名：Poltergeist（Riel 的「Operation classes」型態）
- 定義：把一個「操作」做成一個類別。
- 辨識訊號：DesigniteJava：類別只有 1 個公開方法，且該方法 > 50 行。類別名稱是動詞（`CalculateTax`、`ProcessOrder`）〔推論〕。
- 為何有害：資料和操作資料的行為被拆到不同地方；類別數膨脹；相關操作散在多個「動作類別」。
- 常見解法：把操作搬回它所操作的資料所在的類別（Move Method、Inline Class）；或把多個相關動作合成一個有內聚的抽象〔推論〕。
- 何時不算：刻意把動作物件化的 Command、Strategy 模式（需要排隊、復原、注入）〔推論〕；框架規定一個 handler 一個類別〔推論〕。
- 來源：https://www.tusharma.in/smells/IA.html 、DesigniteJava `AbstractionSmellDetector.java`

### Incomplete Abstraction（不完整抽象）
- 別名：Incomplete Library Class（Fowler）
- 定義：抽象沒有完整提供一個責任所需的方法，特別是缺了成對或互補的方法。
- 辨識訊號：缺少對稱的方法：有 open 沒 close、有 add 沒 remove、有 min 沒 max、有 create 沒 destroy、有 read 沒 write；呼叫端自己寫補丁。
- 為何有害：呼叫端被迫繞路，行為分散。公開 API 發布後很難再補（ICSE 2014 教程原話：對公開 API 往往「為時已晚」）。
- 常見解法：補齊互補方法。第三方類別改不動時，用 Introduce Foreign Method 或 Introduce Local Extension（Fowler 針對 Incomplete Library Class 的手法）。
- 何時不算：刻意設計成不可變（immutable）所以沒有 setter；刻意只允許附加（append-only）〔推論〕。
- 來源：https://www.tusharma.in/smells/IA2.html 、https://www.slideshare.net/slideshow/refactoring-for-software-design-smells-icse-2014-tutorial/35564821

### Multifaceted Abstraction（多面向抽象）
- 別名：Divergent Change（Fowler）、Swiss Army Knife（Brown）；即 SRP 違反
- 定義：一個抽象被指派了不只一個責任。
- 辨識訊號：DesigniteJava：LCOM ≥ 0.8 且欄位 ≥ 7 且方法 ≥ 7。版控歷史裡，同一個類別因為不同理由、應不同需求方被修改〔推論〕。
- 為何有害：改一個責任可能弄壞另一個；理解成本高；無法單獨重用其中一個責任。
- 常見解法：Extract Class，依責任拆分。
- 何時不算：只負責轉發、本身不含邏輯的 Facade〔推論〕；LCOM 對大量 getter／setter 的類別容易誤報〔推論〕。
- 來源：https://www.tusharma.in/smells/MA2.html

### Unnecessary Abstraction（多餘抽象）
- 別名：Lazy Class（Fowler）、Poltergeist
- 定義：設計裡引入了實際上不需要（本來可以避免）的抽象。
- 辨識訊號：DesigniteJava：方法數 == 0 且欄位 ≤ 5（例如只放幾個常數的類別）。
- 為何有害：每個類別都有理解和維護成本（Fowler：沒做足夠的事來支付自身成本的類別應該被消除）。
- 常見解法：Inline Class、Collapse Hierarchy；常數移到使用它的類別或 enum〔推論〕。
- 何時不算：序列化邊界的純資料 record／DTO；為了型別安全而設的 marker 型別〔推論〕。
- 來源：https://www.tusharma.in/smells/UA.html

### Unutilized Abstraction（未使用抽象）
- 別名：Speculative Generality（Fowler）、Obsolete Classes、Unused Packages（Lippert）
- 定義：抽象沒有被使用（沒有被直接使用，或從入口走不到）。
- 辨識訊號：DesigniteJava：沒有 fan-in；有父型別時，父型別也沒有 fan-in 或自身沒有 fan-in。
- 為何有害：死碼增加認知負擔，也常是 Lava Flow 的成分。
- 常見解法：刪除（版控裡還留得到）。
- 何時不算：透過反射、DI 容器、序列化框架、外掛機制或公開函式庫 API 被外部使用的類別，靜態分析看不到 fan-in〔推論〕。
- **命名衝突**：Azadi & Fontana 目錄裡的「Unutilized Abstraction」意思不同，是指「直接引用具體類別，而不是引用它的父型別」。
- 來源：https://www.tusharma.in/smells/UA2.html 、http://www.taibi.it/sites/default/files/Architectural%20Smells%20Detected%20by%20Tools%20a%20Catalogue%20Proposal.pdf

### Duplicate Abstraction（重複抽象）
- 別名：Duplicate Code、Cut-and-Paste Programming（Brown）、Alternative Classes with Different Interfaces（Fowler）、Unfactored Hierarchy
- 定義：兩個以上的抽象名稱相同、實作相同，或兩者都相同。
- 辨識訊號：不同命名空間裡有同名類別。複製碼（clone）分四型：Type 1 只差空白排版；Type 2 只差識別字名稱；Type 3 有增刪改語句；Type 4 語意相同但語法不同。
- 為何有害：修一處忘了另一處；呼叫端不知道該用哪一個。
- 常見解法：合併成一個；同名但不同義就改名〔推論〕。
- 何時不算：刻意隔離的 bounded context（限界上下文：一個模型適用的明確邊界）各自有同名概念（兩個子系統各有自己的 `Customer`）〔推論〕；自動生成的程式碼〔推論〕。
- 來源：https://www.tusharma.in/smells/DA.html 、ICSE 2014 教程（同上）

### A2 封裝類（Encapsulation smells）

### Deficient Encapsulation（封裝不足）
- 別名：Indecent Exposure（Kerievsky，近義）
- 定義：抽象中一或多個成員宣告的可見度，比實際需要的更寬。
- 辨識訊號：DesigniteJava：公開欄位數 > 0。宣告成 public 卻只在類別內使用的方法〔推論〕。
- 為何有害：外部能直接改內部狀態，不變量（invariant，任何時候都必須成立的條件）可能被破壞；一旦變成公開契約，之後就改不動了。
- 常見解法：降低可見度；Encapsulate Field。
- 何時不算：常數；語言慣例本來就沒有強制私有（如 Python）〔推論〕。DesigniteJava 是否排除 `static final` 常數：**未查證**。
- 來源：https://www.tusharma.in/smells/DE.html 、DesigniteJava `EncapsulationSmellDetector.java`

### Leaky Encapsulation（洩漏式封裝）
- 別名：Visibility of Dependency Graphs、Subsystem-API Bypassed（Lippert，近義）
- 定義：抽象透過公開介面「洩漏」了實作細節。
- 辨識訊號：公開方法回傳內部可變集合的參考；方法名或參數暴露了資料結構或演算法；把 ORM 實體或資料庫例外往上層丟〔以上皆推論〕。
- 為何有害：呼叫端依賴實作細節，換實作就得改呼叫端；內部狀態可以繞過不變量被修改〔推論〕。
- 常見解法：回傳不可變視圖或複本；用意圖命名介面；把實作型別藏到介面後面〔推論〕。
- 何時不算：為了效能刻意暴露（例如 zero-copy buffer），並寫進文件〔推論〕。
- 來源：https://www.tusharma.in/smells/LE.html

### Missing Encapsulation（缺失封裝）
- 定義：實作上的變化點（variation）沒有被包進一個抽象或階層裡。
- 辨識訊號：同一個「會變的東西」（演算法、格式、供應商）在多處用條件判斷處理；每多一種組合就多一個類別（類別爆炸）〔推論〕。
- 為何有害：變化擴散到各處，新增一種變體的成本高〔推論〕。
- 常見解法：封裝會變的部分（Strategy、Bridge 等）〔推論〕。
- 何時不算：只有一種實作、也看不到會變的跡象——這時硬抽就變成 Speculative Hierarchy〔推論〕。
- 來源：https://www.tusharma.in/smells/ME.html

### Unexploited Encapsulation（未善用封裝）
- 別名：Switch Statements（Fowler）、Type Queries（Lippert）
- 定義：繼承階層裡已經封裝好型別差異，呼叫端卻還用明確的型別檢查（if-else 鏈或 switch 判斷物件型別）自己分派。
- 辨識訊號：DesigniteJava：同一方法內，對同一階層中兩個以上不同型別做 instanceof。
- 為何有害：違反 OCP，每多一個子型別就要改所有檢查點；Lippert 認為型別查詢也違反 DRY。
- 常見解法：Replace Conditional with Polymorphism，把行為搬進階層。
- 與 Missing Hierarchy 的差別：這裡**階層已經存在**但沒被用到；Missing Hierarchy 是**階層根本沒建**。
- 何時不算：對封閉型別（sealed／代數資料型別）做模式比對，而且編譯器會檢查是否窮舉〔推論〕；`equals()` 裡慣用的 instanceof〔推論〕。
- 來源：https://www.tusharma.in/smells/UE.html 、DesigniteJava `EncapsulationSmellDetector.java`

### A3 模組化類（Modularization smells）

### Broken Modularization（破碎模組化）
- 別名：Data Class（Fowler）；常與 Feature Envy 一起出現
- 定義：本該集中在同一個抽象裡的資料和／或方法，被拆散到多個抽象中。
- 辨識訊號：DesigniteJava：方法數 == 0 且欄位 ≥ 5。另一個類別大量操作這些資料〔推論〕。
- 為何有害：資料和行為分開，不變量沒有守門人，邏輯在多處重複〔推論〕。
- 常見解法：Move Method，把操作資料的行為搬到資料所在的類別。
- 何時不算：DTO、序列化邊界、CQRS（讀寫分離架構）的讀模型、刻意讓資料與函式分離的函式式設計〔推論〕。
- 來源：https://www.tusharma.in/smells/BM.html

### Insufficient Modularization（模組化不足）
- 別名：Large Class、God Class、The Blob、Too Large Packages/Subsystems
- 定義：抽象還沒有被充分分解；再分解可以縮小介面、降低實作複雜度，或兩者都降。
- 辨識訊號：DesigniteJava：公開方法 ≥ 20，或方法 ≥ 30，或 WMC ≥ 100（三者任一）。書中的實例：`java.awt.Component` 有 332 個方法（259 個公開）、107 個欄位、10,102 行。
- 為何有害／常見解法：**主條目見 01 的 Large Class**。
- 何時不算：自動生成的類別〔推論〕。
- 來源：https://www.tusharma.in/smells/IM.html 、ICSE 2014 教程

### Cyclically-dependent Modularization（循環依賴模組化）
- 別名：cyclic dependencies、Static Cycles in Dependency Graphs（Lippert）；也就是類別層的 ADP 違反
- 定義：兩個以上的抽象直接或間接互相依賴。
- 辨識訊號：DesigniteJava：型別所在的強連通分量大小 > 1，例如 A→B→C→A。
- 為何有害：環裡的類別必須一起理解、一起測試、一起發布；改一個可能波及整個環。Lippert：環一多，系統就會「結塊」。
- 常見解法：引入介面來反轉其中一條依賴（DIP）；把雙方共用的部分抽到第三個抽象；本來就是一體的兩者乾脆合併；把回呼改成事件〔後兩項推論〕。
- 何時不算：套件內部的循環，一般被認為比跨套件的循環輕微（Azadi）。
- 套件層版本見 E1「Cyclic Dependency」，服務層版本見 G2。
- 來源：https://www.tusharma.in/smells/CM.html 、Azadi & Fontana（同上）

### Hub-like Modularization（樞紐式模組化）
- 定義：抽象同時有大量的傳入與傳出依賴。
- 辨識訊號：DesigniteJava：fan-in ≥ 20 **且** fan-out ≥ 20（類別層）。
- 為何有害：它一變，依賴它的全部受影響；它依賴的任何東西一變，它也受影響——漣漪效應的中心。
- 常見解法：拆分責任（通常它同時也是 Multifaceted Abstraction）；把不屬於它的東西搬走；用介面切斷其中一個方向〔推論〕。
- 何時不算：只有 fan-in 高的穩定核心型別（值物件、基礎型別）是正常的，問題在「同時」fan-out 也高〔推論〕；刻意集中組裝的 Composition Root 或 Mediator〔推論〕。
- 套件層版本見 E1「Hub-Like Dependency」。
- 來源：https://www.tusharma.in/smells/HM.html

### A4 階層類（Hierarchy smells）

### Missing Hierarchy（缺失階層）
- 別名：Switch Statements
- 定義：用條件邏輯明確管理行為上的變化，而這些變化本來可以建一個階層來封裝。
- 辨識訊號：DesigniteJava：方法中 instanceof 的型別，有 ≥ 2 個不在本類別的祖先鏈中。型別碼（type code）欄位加 switch〔推論〕。
- 為何有害：違反 OCP，新增一種變體要改所有分支。
- 常見解法：Replace Type Code with Subclasses／Strategy、Replace Conditional with Polymorphism〔推論〕。
- 何時不算：只有兩三種變化，而且只在一處分派〔推論〕。
- 來源：https://www.tusharma.in/smells/MH.html

### Unnecessary Hierarchy（多餘階層）
- 定義：整個繼承階層都不需要——在這個情境下用繼承是多此一舉。ICSE 教程列了三種情況：所有子型別都不必要（繼承用錯）、父型別只有一個子型別（臆測式一般化）、中間型別不必要。
- 辨識訊號：子類別之間只差資料值、沒有行為差異，其實應該是同一類別的不同實例（Riel 的「Object classes」）。
- 常見解法：Collapse Hierarchy、Replace Subclass with Fields〔推論〕。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/UH.html 、ICSE 2014 教程

### Unfactored Hierarchy（未提煉階層）
- 別名：Duplicate Abstraction、Cut-and-Paste Programming
- 定義：階層內的型別之間有不必要的重複，分兩種：兄弟型別之間、父子型別之間。
- 辨識訊號：兄弟類別有相同的方法實作；子類別覆寫成和父類別一樣的內容。
- 常見解法：Pull Up Method／Field、Extract Superclass、Form Template Method〔推論〕。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/UH2.html

### Wide Hierarchy（過寬階層）
- 定義：繼承階層「太寬」，暗示中間型別可能缺了。
- 辨識訊號：DesigniteJava：直接子類別數 NOC > 10。
- 常見解法：引入中間抽象，把子類別分組〔推論〕。
- 何時不算：擴充點型別本來就有大量平行實作（各種例外類別、各種編解碼器）〔推論〕。
- 來源：https://www.tusharma.in/smells/WH.html

### Speculative Hierarchy（臆測式階層）
- 別名：Speculative Generality；List-like Inheritance Hierarchy（Lippert：每個類別最多只有一個子類別）
- 定義：階層中有一或多個型別，是根據想像的需求而不是真實的需求加上去的。
- 辨識訊號：抽象類別或介面只有一個實作；繼承階層裡沒有任何多型賦值（Lippert：Inheritance Hierarchies Without Polymorphic Assignments）。
- 為何有害：多出來的層級讓設計更難懂、更難維護。
- 常見解法：Collapse Hierarchy；等第二個實作真的出現再抽（YAGNI）〔推論〕。
- 何時不算：為了放測試替身而設的介面（一個正式實作加測試替身）〔推論〕；跨模組邊界、用來反轉依賴的介面〔推論〕。
- 來源：https://www.tusharma.in/smells/SH.html 、https://www.tusharma.in/smells/LIH.html

### Deep Hierarchy（過深階層）
- 別名：Too Deep Inheritance Hierarchy（Lippert）
- 定義：繼承階層「過度」地深。
- 辨識訊號：DesigniteJava：DIT > 6。Lippert：繼承到 10 層時，光讀程式碼幾乎無法判斷呼叫到的是哪一個實作。
- 為何有害：可理解性和階層的可調整性都變差。
- 常見解法：Collapse Hierarchy；改用組合（Replace Superclass with Delegate）〔推論〕。
- 何時不算：繼承的是框架本身提供的深階層，你只在最末端加一層〔推論〕。DIT 有沒有算進框架類別，各工具不同〔推論〕。
- 來源：https://www.tusharma.in/smells/DH.html 、https://www.tusharma.in/smells/TDIH.html

### Rebellious Hierarchy（叛逆階層）
- 別名：Refused Bequest（Fowler）；LSP 違反
- 定義：子型別拒絕父型別提供的方法。
- 辨識訊號：DesigniteJava：子類別覆寫父類別的方法，而覆寫的實作是空的，或只有一行 throw（例如丟 `UnsupportedOperationException`）。
- 為何有害／常見解法：**主條目見 01 的 Refused Bequest**。
- 何時不算：父型別的文件明訂某些操作是「可選操作」（例如 Java Collections 的 optional operations）〔推論〕；Null Object 模式裡刻意的空實作〔推論〕。
- 來源：https://www.tusharma.in/smells/RH.html 、DesigniteJava `HierarchySmellDetector.java`

### Broken Hierarchy（斷裂階層）
- 別名：Subclasses Do Not Redefine Methods（Lippert）
- 定義：父型別和子型別在概念上不是 IS-A（「是一種」）關係，可替換性因此被破壞；通常是該用組合的地方用了繼承。
- 辨識訊號：DesigniteJava：有父型別、有公開方法，卻一個父型別方法都沒覆寫。Lippert：子類別不重新定義父類別的方法，代表繼承沒有表達任何抽象，只是在繼承實作。
- 為何有害：呼叫端拿到子型別時，行為不符合父型別的預期（LSP 違反）。
- 常見解法：Replace Inheritance with Delegation（Lippert：改用「使用」關係通常更有效）。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/BH.html 、https://www.tusharma.in/smells/SDRM.html 、ICSE 2014 教程

### Multipath Hierarchy（多路徑階層）
- 別名：Degenerated Inheritance（Azadi 引用 Massey Architecture Explorer）
- 定義：子型別同時直接和間接繼承同一個父型別，在階層中多出不必要的繼承路徑。
- 辨識訊號：`class C extends B implements I`，而 B 本身已經 `implements I`；把階層畫成圖，結果不是一棵樹。
- 為何有害：階層變雜亂，更難理解和維護。Azadi：各工具都說這個味道每次出現都該重構，因為多半是錯誤或疏忽。
- 常見解法：移除多餘的直接繼承〔推論〕。
- 何時不算：有些函式庫為了讓文件更好讀，刻意重複宣告 implements〔推論〕。
- 來源：https://www.tusharma.in/smells/MH2.html 、Azadi & Fontana

### Cyclic Hierarchy（循環階層）
- 別名：Subtype Knowledge（Massey）、Unhealthy Inheritance Hierarchy（Mo 等人，其中一種情況）
- 定義：階層中的父型別依賴自己的任何一個子型別。
- 辨識訊號：父類別程式碼裡出現子類別名稱（new 子類別、對子類別做 instanceof、回傳子類別型別）。
- 為何有害：父型別無法獨立理解；子型別不穩定會拖累父型別；父子分屬不同套件時，會形成套件循環（Azadi）。各工具都說每次出現都該重構。
- 常見解法：把需要子型別知識的邏輯下放到子型別（多型）；工廠方法移到階層外〔推論〕。
- 何時不算：sealed 階層由語言要求父型別列出子型別（例如 `permits`）〔推論〕。
- 來源：https://www.tusharma.in/smells/CH.html 、Azadi & Fontana

---

## B. 設計腐化徵兆（Robert C. Martin）

> Martin 在〈Design Principles and Design Patterns〉（2000）提出四個「設計正在腐爛」的徵兆：Rigidity、Fragility、Immobility、Viscosity。後來在《Agile Software Development》（2002）擴充為七個「設計味道」，稱它們是「腐爛軟體的氣味」。這七個描述的是**改程式時的感受**，不直接指出位置；要找根因，就往 A／D／E 類對應。原文沒給數字門檻，下面的「可數訊號」都是〔推論〕的代理指標。

### Rigidity（僵化）
- 定義：系統很難改，因為每改一處都會逼出許多其他改動（Martin 2000：每個改動都在依賴模組間引發一連串後續修改）。
- 辨識訊號：Martin 的描述：原本兩天的改動變成好幾週的馬拉松，工程師得在一個又一個模組間追著改。管理者因此不敢讓人修非關鍵問題。可數代理〔推論〕：一個小需求的 commit 平均碰到幾個模組；估時與實際落差。
- 為何有害：設計缺陷最後變成管理政策——Martin 稱之為「official rigidity」（官方僵化：管理層乾脆禁止改動）。
- 常見解法：找出漣漪中心（Hub、Cyclic Dependency、Unstable Dependency），用 DIP 和 OCP 隔離變化點〔推論〕。
- 何時不算：需求本身就是橫切的（例如法規變動牽動所有報表），影響面大是正常的〔推論〕。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf 、https://www.cs.hmc.edu/courses/2009/spring/cs121/13OODprinciples.pdf

### Fragility（脆弱）
- 定義：每次修改都會在許多地方壞掉，而且常壞在和修改處沒有概念關係的區域。
- 辨識訊號：Martin：越來越脆弱時，破損機率隨時間逼近 1，每次修補帶來的問題比解決的還多。可數代理〔推論〕：回歸 bug 數、bug 出現在沒被改的模組；Mo 等人的 Implicit Cross-module Dependency（沒有靜態依賴卻常一起改）是可量化的線索。
- 為何有害：管理者和客戶開始懷疑開發者已經控制不住軟體，信任流失。
- 常見解法：消除隱性耦合（共享的全域狀態、重複的知識）；補測試安全網〔推論〕。
- 何時不算：未查證。
- 來源：同上兩個

### Immobility（不可移植性；難以重用）
- 定義：很難把系統拆成能在其他系統（或同系統的新版本）重用的元件。Martin：需要的模組常拖著太多依賴的「包袱」，拆出來的工作和風險太大，最後只好重寫，而不是重用。
- 辨識訊號：〔推論〕要抽出一個模組時，得一起帶走的傳遞依賴數；同一功能被重寫的次數（Brown 的 Reinvent the Wheel）。
- 為何有害：重用失敗，造成重複開發。
- 常見解法：讓依賴指向抽象（DIP）；把可重用的邏輯和應用專屬的部分分開〔推論〕。
- 何時不算：未查證。
- 來源：同上兩個

### Viscosity（黏滯）
- 定義：做對的事比做錯的事更難。分兩種：
  - **設計的黏滯**：保持設計的改法比 hack 難。
  - **環境的黏滯**：開發環境又慢又沒效率。例如編譯很久，工程師就傾向選不會觸發大量重編的改法；版控 check-in 要好幾小時，就傾向少 check-in，設計好不好都顧不上了。
- 辨識訊號：〔推論〕HACK／workaround 類註解數量、建置與 CI 時間、一個「正確」修改需要動到的層數。
- 為何有害：抄捷徑一再累積，設計就持續腐化。
- 常見解法：讓正確的路徑變成最短的路徑——改善抽象、加速建置與 CI〔推論〕。
- 何時不算：未查證。
- 來源：同上兩個

### Needless Complexity（不必要的複雜）
- 定義：設計中含有不帶來直接效益的基礎設施。
- 辨識訊號：只有一個實作的擴充點；沒人用的設定參數；只負責轉呼叫的層（Lippert 的 Too Many Layers）〔推論對應〕。
- 對應：Speculative Hierarchy、Unnecessary Abstraction、F 類的 Speculative Architecture。
- 常見解法：YAGNI；刪掉或 Inline〔推論〕。
- 何時不算：見 F 類 Speculative Architecture 的例外（Fowler）。
- 來源：https://www.cs.hmc.edu/courses/2009/spring/cs121/13OODprinciples.pdf

### Needless Repetition（不必要的重複）
- 定義：設計中有可以統一在單一抽象下的重複結構。
- 對應：Duplicate Abstraction、Unfactored Hierarchy、Duplicated Code。
- 何時不算：微服務之間刻意接受重複，換取彼此獨立（Taibi 對 Shared Libraries 提的解法之一就是「接受冗餘」），這是有意識的取捨。
- 來源：同上；https://arxiv.org/abs/1908.04101

### Opacity（晦澀）
- 定義：程式碼很難讀、很難懂，沒有好好表達意圖。
- 對應：命名類味道（01 的 Mysterious Name 等）、Ambiguous Interface；**主條目屬於程式碼層切面**。
- 來源：https://www.cs.hmc.edu/courses/2009/spring/cs121/13OODprinciples.pdf

---

## C. SOLID 違反

### SRP Violation（違反單一職責原則）
- 定義：Martin 的表述是「把因相同理由而變的東西放在一起，把因不同理由而變的東西分開」，這裡的「理由」指**人**，也就是不同的角色或需求方（actor）。違反 = 一個模組同時服務多個需求方。
- 辨識訊號：Martin 的例子：`Employee` 類別同時有 `calculatePay()`（財務長關心）、`reportHours()`（營運長關心）、`save()`（技術長關心）。可數代理〔推論〕：同一檔案常被不同團隊、不同需求來源修改；LCOM 高。
- 對應味道：Multifaceted Abstraction、Divergent Change、God Class；元件層是 Feature Concentration。
- 為何有害：改其中一個需求方要的東西，可能弄壞另一個需求方在用的功能。
- 常見解法：依需求方拆分；需要單一入口時，用 Facade 保留〔推論〕。
- 何時不算：方法多，但都只服務同一個需求方〔推論〕。
- 來源：https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html

### OCP Violation（違反開放封閉原則）
- 定義：OCP =「模組應該對擴充開放、對修改封閉」。違反 = 每加一種新變體，都得修改既有模組的原始碼。
- 辨識訊號：Martin 的 `LogOn` 例子：每多一種數據機，`LogOn` 就得改；而且所有數據機都依賴 `Modem::Type` 列舉，每加一種就要全部重編。依型別碼寫的 switch 散在多處。
- 對應味道：Missing Hierarchy、Unexploited Encapsulation、Missing Encapsulation、Repeated Switches。
- 常見解法：Martin：達成 OCP 的各種技巧都建立在抽象上，例如動態多型。
- 何時不算：變化的方向還不知道就先抽象化，會變成 Speculative Hierarchy；OCP 只能對「預期得到的變化」封閉〔推論〕。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf

### LSP Violation（違反里氏替換原則）
- 定義：LSP =「子類別應該能替換它的基底類別」：接受 Base 的函式，傳入 Derived 也要正常運作。
- 辨識訊號：Martin 舉的經典例子是 Circle／Ellipse 兩難。實務訊號：子類別把覆寫寫成空的或丟例外（Rebellious Hierarchy）；呼叫端用 instanceof 檢查子型別；子類別加嚴前置條件或放寬後置條件（Design by Contract 的觀點，LSP 源自 Meyer 的 DbC）。
- 對應味道：Rebellious Hierarchy、Broken Hierarchy、Refused Bequest。
- 常見解法：改用組合；重新劃分階層，讓 IS-A 在「行為」上也成立〔推論〕。
- 何時不算：未查證。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf

### ISP Violation（違反介面隔離原則）
- 定義：ISP =「多個客戶端專屬的介面，勝過一個通用介面」。違反 = 胖介面（fat interface）：一個類別有多種客戶端，卻只給一個大介面。
- 辨識訊號：Martin：ClientA 用到的方法一改，ClientB、ClientC 也得重編、重新部署。實作類別裡有一堆空方法或 throw NotSupported；客戶端只用到介面中一小部分方法〔後兩項推論〕。
- 對應味道：Rebellious Hierarchy；Azadi 版本的 Ambiguous Interface（過度一般化的介面）。
- 常見解法：依客戶端類別切出專屬介面，由服務類別同時實作多個介面。
- 何時不算：Martin 明說 ISP **不是**要每個使用者一個介面——那樣服務反而會依賴每一個客戶端。應該依客戶端的「類別」分組。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf

### DIP Violation（違反依賴反轉原則）
- 定義：DIP =「依賴抽象，不要依賴具體」。違反 = 高階的政策模組直接依賴低階的實作模組，依賴箭頭從上往下指向細節（Martin 說這是程序式架構的依賴結構）。
- 辨識訊號：高階模組直接 import 或 new 具體的低階類別（資料庫驅動、HTTP client）〔推論例〕。套件層：穩定的套件依賴不穩定的套件（Unstable Dependency）；同時依賴抽象和它的具體子型別（Abstraction without Decoupling）。
- 對應味道：Unstable Dependency、Abstraction without Decoupling、Zone of Pain。
- 常見解法：由高階這一側定義介面，低階去實作；介面放在**使用它的那一側**套件（Martin 的範例做法）。
- 何時不算：Martin 的「緩和因素」（mitigating forces）：DIP 假設具體的東西都容易變，但有例外。具體卻不易變的模組（例如 C 的 `string.h`、久經考驗的成熟模組），依賴它們並無大害。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf

---

## D. 套件／元件原則違反（ADP／SDP／SAP）

> 三條原則（Martin 2000）：
> - **ADP**（Acyclic Dependencies Principle，無環依賴原則）：套件之間的依賴不能形成環。違反 → 見 E1 Cyclic Dependency。
> - **SDP**（Stable Dependencies Principle，穩定依賴原則）：往穩定的方向依賴，也就是「依賴 I 值比自己低的套件」。違反 → 見 E1 Unstable Dependency。
> - **SAP**（Stable Abstractions Principle，穩定抽象原則）：穩定的套件應該是抽象的套件，也就是 I 下降時 A 要上升。Martin 說 SAP 其實是 DIP 的另一種說法。違反 → 落在下面兩個區域。
>
> 度量：I = Ce/(Ca+Ce)，A = Na/Nc，D = |A+I−1|（見第 0 節）。Martin 提醒：這些度量並不完美，把它們當成架構好壞的唯一指標是愚蠢的。Martin 沒有給 D 的警戒門檻（**未查證**有權威門檻）。

### Zone of Pain（痛苦區）
- 定義：套件又具體（A≈0）又穩定（I≈0，被大量依賴）。具體的東西沒辦法靠擴充來改變，而依賴者又多，改起來非常痛苦。Martin 說這是一個套件最糟的位置。
- 辨識訊號：A 接近 0、I 接近 0、D 接近 1。
- 為何有害：只要它變，所有依賴者都要跟著處理。
- 常見解法：抽出介面，讓依賴者改依賴抽象（提高 A）；或拆分以減少依賴者〔推論〕。
- 何時不算：具體但不易變的套件（標準函式庫、成熟工具類），理由同 DIP 的緩和因素；資料庫 schema 這類東西天生落在這區〔推論〕。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf 、https://en.wikipedia.org/wiki/Software_package_metrics

### Zone of Uselessness（無用區）
- 定義：套件高度抽象（A≈1），卻沒有人依賴它（I≈1）。
- 辨識訊號：A 接近 1、I 接近 1。例如只放介面的套件，卻沒有實作者也沒有使用者〔推論例〕。
- 對應：Unutilized Abstraction、Speculative Hierarchy 的套件層版本〔推論〕。
- 常見解法：刪除，或併入真正使用它的套件〔推論〕。
- 何時不算：剛發布、還沒有使用者的公開 API 套件〔推論〕。
- 來源：同上

---

## E. 架構壞味道（研究文獻與工具）

### E1 依賴結構類

### Cyclic Dependency（循環依賴；套件／元件層）
- 別名：Tangle（Structure101、STAN 兩個工具的叫法）、Cross-Module Cycle、Cross-Package Cycle（Mo 等人）、Dependency Cycles between Packages/Subsystems（Lippert）；類別層版本是 Cyclically-dependent Modularization；即 ADP 違反
- 定義：兩個以上的架構元件直接或間接互相依賴。
- 辨識訊號：套件依賴圖中有環。套件層依賴通常由類別層推上來：A 套件裡的類別 a 依賴 B 套件裡的類別 b，就算 A 依賴 B。Arcan 會標出環的形狀：circle（環狀）、clique（全連通）、tiny（最小的兩點環）、chain（鏈狀）、star（星狀）。
- 為何有害：Martin 的例子：`CommError` 為了在畫面上顯示訊息去依賴 `GUI`，結果 `Protocol` 的團隊要發布時，測試得連 `CommError`、`GUI`、`Comm`、`ModemControl`、`Analysis`、`Database` 一起建置。不及時打斷，傳遞依賴最終會讓每個模組都依賴每個模組。Azadi：參與循環的類別與套件無法分開部署和維護。
- 常見解法（Martin 2000 的兩種做法）：
  1. 新增一個套件，把雙方都需要的類別搬進去，讓原本的兩個套件都依賴它；
  2. 用 DIP 加 ISP：在被依賴的一方加一個介面，放在**使用者那一側**的套件，藉此反轉一條依賴邊。
- 何時不算：套件內部的循環，一般被認為比跨套件的循環輕微（Azadi）。
- 工具：Azadi 提到幾乎所有架構工具都偵測這個味道（JDepend、NDepend、Sonargraph、Structure101、Lattix、Arcan、Designite 等）。
- 來源：https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf 、https://arxiv.org/abs/2203.08702 、http://www.taibi.it/sites/default/files/Architectural%20Smells%20Detected%20by%20Tools%20a%20Catalogue%20Proposal.pdf 、https://www.tusharma.in/smells/DCP.html

### Hub-Like Dependency（樞紐依賴；套件／元件層）
- 別名：Hub-like Modularization（類別層版本）、Link Overload（Garcia 等人／ARCADE 工具）；變體：Overreliant Class（只看傳出依賴）、Dense Structure（Azadi 視為更一般的形式）
- 定義：元件同時和大量其他元件有傳入與傳出的依賴。
- 辨識訊號（**各工具差異很大**）：
  - Arcan：傳入和傳出依賴都高於系統中位數，而且 |傳入 − 傳出| < 總依賴數的 1/4（要求兩邊平衡）；套件層和類別層都偵測。
  - Designite：fan-in ≥ 20 且 fan-out ≥ 20。
  - ARCADE：依賴數 > 全系統平均 + 1.5 × 標準差。
  - AI Reviewer：引用超過 7 個具體（非抽象）類別。
- 為何有害：Azadi：hub 一改，所有依賴者都要調整；hub 依賴的類別一改，hub 也受影響。系統裡再小的調整，都會在相關類別間產生漣漪。Sas 等人（產業案例）：hub 會隨時間變得更複雜、連結更多。
- 常見解法：拆分責任；把只有少數使用者需要的部分搬走；用介面切斷其中一個方向〔推論〕。
- 何時不算：Arcan 要求兩邊平衡，就是為了排除「只是被大量依賴的穩定核心」和「只負責協調的組裝者」〔推論解讀〕。
- 來源：https://arxiv.org/abs/2203.08702 、Azadi & Fontana（同上）、https://www.tusharma.in/smells/HM.html

### Unstable Dependency（不穩定依賴）
- 別名：變體 Unstable Interface（Mo 等人，見下）；即 SDP 違反
- 定義：元件依賴了比自己更不穩定的元件。
- 辨識訊號：Arcan：一個套件所依賴的套件中，I 值比自己高的占「顯著比例」，Arcan 的門檻是 30%；只偵測套件層級。Designite 也用 Martin 的 I 值偵測，門檻**未查證**。
- 為何有害：比較穩定的一方被迫跟著不穩定的一方一起改。Martin 的例子：有人在 `Stable` 套件掛上對 `Flexible` 套件的依賴之後，`Flexible` 就不再容易改了，改它就得處理 `Stable` 和 `Stable` 的所有依賴者。
- 常見解法：在穩定的一側定義介面（DIP）；把被依賴的部分抽成更抽象、更穩定的套件〔推論〕。
- 何時不算：I 只看結構，不看實際變更頻率。被依賴的套件 I 值雖高，實際上可能很少改。Hotspot Detector 改用版控的共同變更頻率衡量，結果會和 Arcan／Designite 不同（Azadi）。
- 來源：https://arxiv.org/abs/2203.08702 、https://www.tusharma.in/smells/AUD.html 、https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf

### Dense Structure（稠密結構）
- 定義：元件之間的依賴過多、過密，而且看不出任何結構。
- 辨識訊號：原始出處是 Sharma 等人 MSR 2016（研究對象是 Puppet 設定碼）：把模組當節點、模組間引用當邊，算平均度數 AvgDegree = 2|E| / |V|，大於 0.5 就判定有這個味道。這是**整個專案層級**的味道，一個專案最多一個實例。Designite 把它移植到程式碼架構層，該層的門檻**未查證**。
- 為何有害：整體沒有可辨認的分層或模組結構，可以當作 Big Ball of Mud 的量化代理〔推論〕。
- 常見解法：建立分層與模組邊界；移除不必要的依賴〔推論〕。
- 何時不算：未查證。
- 來源：https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf 、Azadi & Fontana

### Unstable Interface（不穩定介面）
- 定義（Mo 等人 2015，Hotspot Patterns）：一個檔案被許多檔案依賴（扮演「介面」的角色），卻經常和其他檔案一起變動。
- 辨識訊號：高 fan-in，加上版控歷史裡高 co-change 頻率。Hotspot Detector 的門檻**未查證**。Azadi 說它聚焦在「設計規則空間」（Design Rule Spaces），也就是系統中影響力最大的那些檔案。
- 為何有害：它每變一次，大量依賴者跟著變，形成變更與缺陷的熱點〔推論〕。
- 常見解法：把介面中易變的部分拆出去，讓介面本身穩定下來〔推論〕。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/UINT.html 、Azadi & Fontana

### Implicit Cross-module Dependency（隱性跨模組依賴）
- 定義（Mo 等人 2015）：兩個在結構上（靜態依賴上）互相獨立的模組，在版控歷史裡卻有共同變更的關係。
- 辨識訊號：co-change 分析：彼此沒有 import，卻常在同一個 commit 一起被改。門檻**未查證**。
- 為何有害：這是 Fragility 的直接來源——看不見的耦合，例如共享的假設、重複的知識、私下約定的協定〔推論〕。
- 常見解法：把共享的知識變成明確的共用模組或契約〔推論〕。
- 何時不算：同一個功能需求本來就同時牽動 UI 和後端，一起改是正常的〔推論〕。
- 來源：https://www.tusharma.in/smells/CROSSM.html

### Abstraction without Decoupling（有抽象卻沒解耦）
- 別名：Unhealthy Inheritance Hierarchy（Mo 等人，其中一種情況：客戶端同時依賴父型別和子型別）
- 定義：客戶端用抽象型別來使用一個服務，卻**同時**直接依賴這個抽象型別的具體子型別。
- 辨識訊號：Hotspot Detector 要求客戶端依賴階層中**所有**子型別；Massey Architecture Explorer 只要依賴**至少一個**子型別就算。
- 為何有害：服務的實作很難替換，也很難動態重新設定或升級；客戶端把「服務描述」和「服務實作」綁在一起了。
- 常見解法：把具體型別的建立移到工廠或組裝根（composition root），讓客戶端只看得到抽象〔推論〕。
- 何時不算：未查證。
- 來源：Azadi & Fontana（同上）、https://www.tusharma.in/smells/UNINHERIT.html

### E2 關注點類

### God Component（上帝元件）
- 別名：God Class（類別層版本）、Concern Overload（ARCADE）、Too Large Packages/Subsystems（Lippert）
- 定義：元件過大。有兩派定義：
  - **尺寸派**（Lippert、Arcan）：元件的程式碼行數（LOC）明顯大於系統中其他元件。
  - **關注點派**（Azadi 目錄、ARCADE）：元件實作了過多關注點，累積了過多控制權。
- 辨識訊號：
  - Arcan：不用固定門檻，而是依系統中其他套件的 LOC 分佈訂出浮動門檻。
  - Designite（Azadi 轉述）：LOC > 27,000，或套件內類別數 > 30。
  - ARCADE：每個元件的關注點數比例超過 0.10。
  - AI Reviewer：直接或透過 setter 修改至少 3 個不相關類別的資料成員。
- 為何有害：違反關注點分離。Azadi：通常伴隨許多不提供功能的「衛星類別」，元件和衛星類別之間耦合嚴重，元件內部內聚很差。Sas 等人的產業案例：God Component 的尺寸 53% 的情況會隨時間增加（40% 持平、6% 減少），越長越大。
- 常見解法：依關注點拆分元件〔推論〕。注意 Azadi 的觀察：God Component 拆出一個關注點後，剩下的部分可能變成 Hub-Like，要一起看。
- 何時不算：自動生成的程式碼、vendored（直接複製進專案的）第三方程式碼〔推論〕。
- 來源：https://arxiv.org/abs/2203.08702 、Azadi & Fontana、https://www.tusharma.in/smells/TLP.html

### Feature Concentration（功能集中）
- 定義：一個架構元件實現了不只一個架構關注點。
- 辨識訊號：元件內部可以分出多群互不相關的功能（元件層的低內聚）〔推論〕。Designite 會偵測，門檻**未查證**。
- 對應：Multifaceted Abstraction／SRP 違反的元件層版本〔推論對應〕。
- 為何有害：改一個關注點可能影響其他關注點〔推論〕。
- 常見解法：依關注點拆分元件〔推論〕。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/AFC.html （Andrade、Almeida、Crnkovic，WICSA 2014）

### Scattered Parasitic Functionality（分散寄生功能）
- 別名：Scattered Functionality（Azadi／Designite）
- 定義（Garcia 等人 2009）：多個元件負責實現同一個高階關注點，而其中一些元件**還同時**負責其他正交（不相干）的關注點。這違反關注點分離兩次：一個關注點被分散到多個元件；至少一個元件同時處理多個正交關注點，像寄生蟲一樣「感染」了那個元件。
- 辨識訊號：同一個關注點（例如權限檢查、狀態回報）的程式碼散在多個元件，而這些元件各自還做別的事。Garcia 的實例：Linux 的行程狀態回報其實分散實作在整個核心裡。Designite（Azadi 轉述）：以存取外部元件的次數衡量，預設門檻 1；ARCADE：用資訊檢索和機器學習把處理相似關注點的實體分群。
- 為何有害：可修改性、可理解性、可測試性、可重用性都下降——要改那個共同關注點，得去好幾個地方改、好幾個地方測。
- 與 Shotgun Surgery 的差別：Garcia 明說，兩者表面相似，但 Shotgun Surgery 不管「正交關注點」這一層。
- 常見解法：把該關注點收攏到一個元件；橫切關注點用中介層或 AOP（剖面導向程式設計）處理〔推論〕。
- 何時不算：Garcia：共同關注點必須由多個內部無法修改的現成元件（off-the-shelf，OTS）提供時，可以接受。
- 來源：https://jgarcia.ics.uci.edu/wp-content/uploads/10.1.1.183.9958.pdf 、https://www.tusharma.in/smells/SPF.html

### E3 介面與連接器類

> 「連接器」（connector）：負責元件之間互動的架構元素，例如程序呼叫、事件匯流排、訊息佇列。

### Ambiguous Interface（模糊介面）
- 定義（Garcia 等人 2009）：介面只提供單一、一般化的進入點（例如 `process(GeneralType p)`），元件在內部再依型別分派。常見於透過共享事件匯流排交換訊息的 publish-subscribe 系統，以及用字串或整數做動態分派的系統。
- 辨識訊號：Garcia 的兩個條件：(1) 介面只有一個公開服務或方法，元件實際上卻提供並處理多種服務；(2) 因為只有一個進入點，接受的參數型別必然過度一般化。
- 為何有害：介面看不出元件提供哪些服務，使用者得去讀實作才會用。靜態分析會高估依賴：事件匯流排上有 n 個元件時，改一個發佈者看起來會影響 n−1 個元件。如果各元件明列自己的訂閱，就能縮小到實際受影響的 m 個（m ≤ n）。
- 常見解法：把各項服務拆成明確的方法或訊息型別；把訂閱關係寫清楚。
- 何時不算：事件驅動架構刻意的鬆耦合〔推論〕——但仍應把訂閱關係文件化。
- **命名衝突**：Azadi 目錄裡的「Ambiguous Interface」（又名 Underused Interface）指的是「為了可能的未來需求而過度設計的抽象介面」，和 Garcia 的定義不同。引用時要說明用的是哪一版。
- 來源：https://jgarcia.ics.uci.edu/wp-content/uploads/10.1.1.183.9958.pdf 、https://www.tusharma.in/smells/AAI.html 、Azadi & Fontana

### Connector Envy（連接器嫉妒）
- 定義（Garcia 等人 2009）：元件裡含有大量本該委派給連接器的互動功能。連接器提供四類服務：communication（傳遞資料）、coordination（傳遞控制）、conversion（轉換資料格式、型別、協定）、facilitation（負載平衡、監控、容錯）。
- 辨識訊號：業務元件裡混著序列化、協定轉換、重試、座標轉換等程式碼。Garcia 的例子：負責畫機器人路線的 `MapDisplay`，在內部把直角座標轉成螢幕座標。
- 為何有害：可重用性下降（互動服務和應用服務綁在一起，很難只取其一）；可理解性下降（不相干的關注點混在一起）；可測試性下降（測試失敗時，分不出是應用邏輯還是互動機制出錯）。
- 常見解法：把互動功能抽成獨立的連接器或 adapter（轉接層）。
- 何時不算：Garcia：效能優先於可維護性時可以接受——把互動機制分出去會多一層間接，有時還要額外的執行緒或行程。資源極受限、互動機制又簡單的應用，留著反而有利。
- 來源：https://jgarcia.ics.uci.edu/wp-content/uploads/10.1.1.183.9958.pdf 、https://www.tusharma.in/smells/ACE.html

### Extraneous Adjacent Connector（多餘的並存連接器）
- 定義（Garcia 等人 2009）：同一對元件之間，同時用兩種不同類型的連接器連接（例如事件匯流排加上直接方法呼叫）。
- 辨識訊號：A 與 B 之間既透過 event bus 溝通，又有直接的方法呼叫。
- 為何有害：兩種連接器的好處互相抵銷。直接呼叫讓控制流程清楚可追，但多了事件連接器，就看不出 A 和 B 之間還有沒有別的溝通；事件連接器讓元件可替換，卻被直接呼叫破壞了。此外，事件連接器保證的順序（例如 FIFO）可能被直接呼叫繞過。
- 常見解法：統一成一種連接器〔推論〕。
- 何時不算：Garcia：獨立的桌面應用程式常同時用兩種連接器處理 GUI 輸入，這裡的事件連接器是為了非同步處理 GUI 事件，而不是為了可替換性，可以接受。
- 來源：https://jgarcia.ics.uci.edu/wp-content/uploads/10.1.1.183.9958.pdf 、https://www.tusharma.in/smells/EAC.html

### E4 分層與子系統類

### Layer Violation（分層違規：反向依賴與跳層）
- 別名：Upward References between Layers（往上層的引用）、Strict Layers Violated（違反嚴格分層，即跳層 layer skipping）（Lippert & Roock）
- 定義：下層使用上層（反向依賴）；或在嚴格分層中，跳過正下方那一層，直接存取更下面的層。
- 辨識訊號：用依賴規則檢查（例如 ArchUnit）找出領域層 import UI 層、controller 跳過 service 直接呼叫 repository 這類情況〔推論例〕。
- 為何有害：Lippert：下層使用上層違反了分層的基本原則，一層的修改不只影響上層，還會影響更下面的層。跳層讓一層的潛在客戶端變多、層與層之間的依賴增加，可修改性受損。
- 常見解法：反轉依賴（由下層定義介面，上層實作或回呼）；補上中間層的 API〔推論〕。
- 何時不算：鬆散分層（relaxed layering）本來就允許跳層。Lippert 的原文只針對「原本是嚴格的分層」被違反的情況。
- 相關：No Layers（完全沒有分層，少了指引修改方向的地圖）；Too Many Layers（層太多，間接層過多，徵兆是大量只轉呼叫、自己不做事的「笨委派」）；References between Vertically Separated Layers（垂直分隔的層之間有引用，產品線就無法發揮作用）。
- 來源：https://www.tusharma.in/smells/URL.html 、https://www.tusharma.in/smells/SLV.html 、https://www.tusharma.in/smells/TML.html 、https://www.tusharma.in/smells/NL.html 、https://www.tusharma.in/smells/RVSL.html

### Subsystem-API Bypassed（繞過子系統 API）
- 別名：Leaky Encapsulation、Visibility of Dependency Graphs（近義）
- 定義（Lippert & Roock）：客戶端繞過子系統的對外 API，直接存取元件的內部實作——等於擅自擴大了子系統的 API。
- 辨識訊號：跨子系統引用到非 API 套件（internal、impl）裡的類別〔推論〕。
- 為何有害：Lippert：這種做法不只常見，還可能是致命的；之後內部就沒辦法自由修改了。
- 常見解法：用語言或模組系統強制邊界（Java module 的 exports、internal 可見度、架構規則測試）〔推論〕。
- 相關：**Subsystem-API Too Large**（子系統 API 過大）：API 相對實作太大，系統大部分內容都對所有子系統可見，沒有達到降低複雜度的目的。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/SAB.html 、https://www.tusharma.in/smells/SATL.html

### Package Structure Imbalance（套件結構失衡）
- 別名：Lippert & Roock 的一組味道
- 定義與辨識訊號（數字都是 Lippert 的原文）：
  - **Too Large Packages/Subsystems**：套件裡類別或子套件很多，代表它承擔了不只一個責任。
  - **Too Small Packages/Subsystems**：只有一、兩個類別的套件，通常不值得設立——它帶來的複雜度抵不過它提供的結構化效益。
  - **No Subsystems**：只用套件組織系統，超過約 100 個套件時，套件之間的結構就極難辨認和維護。
  - **Too Many Subsystems**：子系統遠多於 30 個又沒有再分組時，可理解性嚴重受損。
  - **Package Hierarchies Unbalanced**：套件階層不平衡，可理解性受損。
  - **Packages Not Clearly Named**：`util`、`base`、`framework`、`toolkit` 這類名稱的套件並列在同一層，開發者找不到想要的類別。
- 為何有害：找不到東西、看不出結構。
- 常見解法：依責任重新分組；加一層子系統〔推論〕。
- 何時不算：未查證。
- 來源：https://www.tusharma.in/smells/TLP.html 、https://www.tusharma.in/smells/TSP.html 、https://www.tusharma.in/smells/NS.html 、https://www.tusharma.in/smells/TMS.html 、https://www.tusharma.in/smells/PHU.html 、https://www.tusharma.in/smells/PNCN.html

---

## F. 經典架構反模式

### Big Ball of Mud（大泥球）
- 定義（Foote & Yoder）：一個隨意、甚至雜亂無章拼湊起來的系統，它的組織方式（如果還稱得上有組織）是由權宜而不是設計決定的。
- 辨識訊號：原文描述是「haphazardly structured, sprawling, sloppy, duct-tape and bailing wire, spaghetti code jungle」（結構隨意、四處蔓延、草率、靠膠帶和鐵絲勉強撐著的義大利麵程式叢林）。資訊在系統中相距很遠的元素之間濫交共享，重要資訊幾乎都變成全域的或重複的；處處是不受管控的成長與反覆權宜修補的痕跡；資料結構隨意拼湊，甚至幾乎不存在。可量化代理〔推論〕：Dense Structure 的平均度數高、大量循環依賴、看不出分層。
- 成因（原文列出的力量）：時間、成本、經驗、技能、可見性（架構從外面看不到）、複雜度、變化、規模。
- 常見解法（同一篇論文的相關模式）：
  - Keep It Working：邊修邊讓系統持續運作。
  - Piecemeal Growth：受控的漸進成長。
  - Shearing Layers：「把變化速率相近的東西放在一起」。
  - Sweeping It Under the Rug：「清不掉，至少把它圍起來」，把混亂限制在固定範圍，為後續重構鋪路。
  - Reconstruction：整個重寫。
- 何時不算：原文：在原型和擴張階段、大家還在學習這個領域時，系統一開始看起來像泥球沒關係，前提是之後要清理。
- 來源：http://www.laputan.org/mud/

### Lava Flow（熔岩流）
- 別名：Dead Code（程式碼層）、Unutilized Abstraction（部分）
- 定義：在次佳條件下寫的程式碼被部署到生產環境，之後又在仍處於開發狀態時被繼續擴充（Wikipedia）。Brown 等人 1998 的描述：一段沒人記得用途和用法、而且大多沒被使用的程式碼。
- 辨識訊號：沒人說得出用途的程式碼區塊；缺文件、缺測試；大量被註解掉的程式碼和不知道還有沒有人用的類別〔後者推論〕。
- 成因：時程壓力讓臨時方案變成永久方案；文件不足；缺自動化測試，重構有風險；人員流動造成知識流失。
- 為何有害：向後相容的要求阻礙創新；技術債累積推高維護成本；怕弄壞依賴而不敢改進。
- 常見解法：文件標準、定期 code review、把重構當日常工作、建立完整的自動化測試。刪除前先用測試或執行期觀察確認真的沒人在用〔推論〕。
- 何時不算：未查證。
- 來源：https://en.wikipedia.org/wiki/Lava_flow_(programming) 、https://www.tusharma.in/smells/LF.html

### Golden Hammer（黃金錘）
- 定義（Brown 等人 1998）：誤用偏愛的工具、函式庫、語言、框架或概念。開發者和管理者習慣既有做法，不願意學習並採用更合適的做法。
- 辨識訊號：〔推論〕什麼問題都用同一種技術解；技術選型文件裡沒有任何替代方案的比較。
- 為何有害：用錯工具，帶來不必要的複雜度與限制〔推論〕。
- 常見解法：〔推論〕技術選型時強制列出替代方案和取捨；擴展團隊的技能廣度。
- 何時不算：〔推論〕團隊把技術棧標準化本身是合理的取捨（也能避免 G4 的 Too Many Technologies），問題在於「明明不合適還硬要用」。
- 來源：https://www.tusharma.in/smells/GH.html

### Anemic Domain Model（貧血領域模型）
- 定義（Fowler）：表面上有領域物件，仔細一看卻幾乎沒有行為，只是一包 getter／setter；領域邏輯全被推到服務物件裡。
- 辨識訊號：領域類別只有屬性和存取方法；大量 `*Service` 類別在操作這些物件的資料（可以看成 Broken Modularization 加 Feature Envy 的領域層版本）〔推論對應〕。
- 為何有害：Fowler：付出了 Domain Model 的全部成本（例如 O/R 映射，物件與關聯式資料庫之間的轉換），卻沒拿到任何好處，本質上退回程序式設計。
- 常見解法：把業務規則搬回領域物件。Evans：Service 層要薄，只負責協調和委派，關鍵邏輯都在領域層。
- 何時不算：Fowler 承認 Domain Model 不一定是最好的工具。邏輯簡單時用 Transaction Script（交易腳本：每個業務操作寫成一支程序）是合理的選擇，這時資料物件沒有行為不算病。
- 來源：https://martinfowler.com/bliki/AnemicDomainModel.html

### Service Locator Abuse（服務定位器濫用）
- 定義（Seemann）：類別在內部向一個全域註冊表要依賴，而不是在建構子上宣告依賴。
- 辨識訊號：程式各處散落 `Locator.Get<T>()`、`container.Resolve<T>()`；類別的建構子是空的，執行時卻需要某些服務事先註冊好。
- 為何有害：依賴被隱藏起來；錯誤從編譯期延後到執行期（例如 `KeyNotFoundException`）；新增一個依賴算不算破壞性變更，無從判斷。
- 常見解法：Constructor Injection（建構子注入）；需要動態建立物件時，注入一個 Abstract Factory。
- 何時不算：Seemann：在 Composition Root（組裝根）可以接受——例如框架控制實例化的進入點（ASP.NET Page、WCF 服務），在那裡解析依賴沒問題，但不能把 container 再往深處傳。
- 來源：https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/

### Singleton Abuse（單例濫用）
- 別名：Global Data（程式碼層）
- 定義：用 Singleton 模式（靜態的全域存取點）當作取得協作者的手段。Hevery：Singleton 本質上就是全域狀態，讓物件偷偷取得 API 沒有宣告的東西，所以稱它們是「病態的說謊者」（pathological liars）。
- 辨識訊號：類別的 API 沒宣告，內部卻呼叫 `X.getInstance()`；測試要重設全域狀態，或測試結果和執行順序有關〔推論〕。
- 為何有害：API 說謊（依賴被隱藏）；難以單元測試；全域狀態讓同樣的操作重複執行時結果不一定相同。
- 常見解法：用 DI 讓容器只建立一個實例（小寫 s 的 singleton），再透過建構子傳入。
- 何時不算：「整個應用只有一個實例」本身沒問題，只要它是由組裝根建立並注入的。問題在「靜態全域存取」（Hevery 文章和留言都討論了這個區分）。
- 來源：https://testing.googleblog.com/2008/08/by-miko-hevery-so-you-join-new-project.html

### Speculative Architecture（臆測式架構；過度工程 over-engineering）
- 別名：Speculative Generality（類別層）、Overgeneralization（Lippert）、Needless Complexity（Martin）；服務層的對應見 G4 Microservice Greedy
- 定義：為了「想像中」而不是真實的需求，預先建立架構基礎設施（擴充點、抽象層、外掛機制、可設定性）。
- 辨識訊號：
  - Fowler 的 presumptive feature（推定功能）：支援一個「還沒開放使用」的功能的程式碼。
  - 只有一個實作的抽象層；沒人用的設定參數；只轉呼叫的層（Too Many Layers）〔推論〕。
  - Lippert 的 Overgeneralization：子系統為了追求最大可重用性而過度一般化。
- 為何有害：Fowler 列出四種成本：
  - cost of build：建了用不到的東西；
  - cost of delay：把資源從能帶來收益的功能挪走；
  - cost of carry：多出來的複雜度讓後續修改更難；
  - cost of repair：等真的要用時，假設已經過時，得重做。
- 常見解法：YAGNI；需求出現時再抽象；同時保持程式碼可塑（重構加測試）。
- 何時不算：Fowler：為了讓軟體更容易修改的投入（重構、自我測試的程式碼、持續交付）**不算**違反 YAGNI；不增加複雜度的預先設計也不算。YAGNI 的前提是程式碼可塑。
- 來源：https://martinfowler.com/bliki/Yagni.html 、https://www.tusharma.in/smells/OG.html

### Functional Decomposition（功能分解）
- 別名：Tree-like Dependency Graph（Lippert）
- 定義（Brown）：程序式背景的開發者在物件導向語言裡寫程序式程式碼：一個 main 呼叫一堆子程序，再把每個子程序變成一個類別，完全不用類別階層。
- 辨識訊號：Lippert：依賴圖呈樹狀，每個類別恰好只被另一個類別使用。
- 為何有害：失去物件導向的封裝與多型〔推論〕。
- 常見解法：依資料和責任重新組成物件〔推論〕。
- 何時不算：本來就是程序式或函式式的設計，而且語言也鼓勵這樣寫〔推論〕。
- 來源：https://www.tusharma.in/smells/FD.html 、https://www.tusharma.in/smells/TDG.html

### Brown《AntiPatterns》其他架構級反模式（速查）

| 名稱 | 一句話（依 catalog 摘錄 Brown 1998） | 來源 |
|---|---|---|
| Stovepipe System（煙囪系統） | 子系統之間用多種整合策略和機制臨時拼接 | https://www.tusharma.in/smells/SS1.html |
| Stovepipe Enterprise（煙囪企業） | 多個系統之間缺乏協調與規劃，結構阻礙變更 | https://www.tusharma.in/smells/SE.html |
| Autogenerated Stovepipe | 既有系統被轉成分散式架構，卻沒有重新考慮設計 | https://www.tusharma.in/smells/AS.html |
| Jumble（大雜燴） | 水平與垂直設計元素混在一起，架構不穩定 | https://www.tusharma.in/smells/JU.html |
| Vendor Lock-In（供應商綁定） | 系統高度依賴專有架構 | https://www.tusharma.in/smells/VLI.html |
| Reinvent the Wheel（重造輪子） | 專案之間缺乏技術轉移，大量重新發明 | https://www.tusharma.in/smells/RW.html |
| Design by Committee（委員會設計） | 由委員會設計架構，產出過度複雜、缺乏一致性的架構 | https://www.tusharma.in/smells/DBC.html |
| Architecture by Implication（隱含式架構） | 因為過度自信和過去的成功，忽略新系統的風險管理 | https://www.tusharma.in/smells/AI.html |

---

## G. 微服務壞味道

> 主要來源 Taibi、Lenarduzzi、Pahl〈Microservices Anti-Patterns: A Taxonomy〉訪談了 27 位有經驗的從業者，請他們給每個反模式的危害打分（0–10 分，0 = 無害、10 = 極度有害），並記錄提及人數。下文「危害中位數」就是指這個分數。
> 補充來源：Neri 等人多聲道文獻回顧（https://arxiv.org/abs/1906.01553，從「違反哪條微服務原則」切入）。

### G1 技術—內部

### Megaservice（巨型服務）
- 別名：God Component 的服務層版本
- 定義：一個服務做了很多事——其實就是一個單體（monolith）。
- 辨識訊號：同一個服務實作了好幾個業務流程；由好幾個模組組成，由好幾位開發者甚至好幾個團隊開發。危害中位數 6（5 人提及，19%）。
- 為何有害：單體系統的所有問題它都有。
- 常見解法：拆成較小的微服務。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101

### Hardcoded Endpoints（寫死端點）
- 別名：Hardcoded IPs and Ports（Saleh）；Neri 的 Endpoint-based Service Interactions（只呼叫另一個服務的特定實例）
- 定義：服務之間把對方的 IP 位址和埠號寫死。
- 辨識訊號：設定檔或程式碼裡出現對方服務的固定 host:port。危害中位數 **8**（10 人，37%），與 Wrong Cuts 並列最有害。
- 為何有害：服務位置一變就出問題。Neri：違反水平擴展——呼叫端綁死在單一實例上。
- 常見解法：採用服務發現（service discovery）；Neri 另外建議加訊息路由器（負載平衡器）或訊息代理（message broker）。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101 、https://arxiv.org/abs/1906.01553

### Inappropriate Service Intimacy（不當的服務親密）
- 別名：Inappropriate Intimacy（類別層，近義）
- 定義：服務不處理自己的資料，而是一直去連其他服務的私有資料。
- 辨識訊號：向其他服務要它的私有資料；直接連線到其他服務的資料庫。危害中位數 5（5 人，19%）。
- 為何有害：服務之間的耦合升高。這個問題可能源於資料建模時犯的錯。
- 常見解法：Taibi 的受訪者建議考慮合併這幾個服務。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101

### API Versioning（缺少 API 版本化）
- 別名：Static Contract Pitfall（Richards、Saleh）
- 定義：API 沒有使用語意化版本（semantic versioning）。
- 辨識訊號：API 上沒有語意化版本號（例如 v1.1、v1.2）。危害中位數 6.05（6 人，22%）。
- 為何有害：沒有版本的 API 推出新版時，消費端可能連線出錯——回傳的資料不同，或呼叫方式變了。
- 常見解法：API 採用語意化版本，讓服務知道自己是否在和正確版本溝通，或需要調整以符合新契約。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101

### Local Logging（本地日誌）／Lack of Monitoring（缺乏監控）
- 定義：日誌只存在各個服務本地，沒有用分散式日誌系統；或沒有監控系統（服務是否存活、回應是否正確）。
- 辨識訊號：危害中位數：Local Logging 6（17 人，63%，提及率最高）；Lack of Monitoring 5（3 人，11%）。
- 為何有害：錯誤與服務資訊被藏在各自的容器裡；服務掛掉了，不持續人工檢查就不會發現。
- 常見解法：分散式日誌系統；監控系統。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101

### G2 技術—通訊

### Cyclic Dependency（循環依賴；服務層）
- 別名：類別層 Cyclically-dependent Modularization、套件層 Cyclic Dependency
- 定義：服務之間形成循環的呼叫鏈。
- 辨識訊號：服務間的呼叫存在環，例如 A 呼叫 B、B 呼叫 C、C 又回頭呼叫 A。危害中位數 7（5 人，19%）。Taibi 2019 的結論：Wrong Cuts、Cyclic Dependency、Hardcoded Endpoints、Shared Persistence 仍被認為是最有害的四項。
- 為何有害：參與循環的服務很難單獨維護或重用。
- 常見解法：依環的形狀逐一處理；套用 API Gateway 模式。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101

### No API Gateway（缺少 API 閘道）
- 定義：服務之間彼此直接溝通；最糟的情況下，服務的消費端也直接和每個服務溝通。
- 辨識訊號：服務之間直接通訊。危害中位數 5（4 人，15%）。受訪者說：50 個互連的服務還應付得來，再多就開始出現通訊和維護問題。
- 為何有害：系統複雜度上升、可維護性下降。Neri：違反水平擴展，沒有集中的進入點就很難有效擴展。
- 常見解法：套用 API Gateway 模式，降低服務間通訊的複雜度。
- 何時不算：服務數量少的系統〔推論，依上述「約 50 個」的受訪說法〕。
- 來源：https://arxiv.org/abs/1908.04101 、https://arxiv.org/abs/1906.01553

### Shared Libraries（共用函式庫）
- 別名：「I was taught to share」（Richards）
- 定義：不同的微服務共用同一個函式庫。
- 辨識訊號：危害中位數 4（8 人，30%）。
- 為何有害：服務被綁在一起，失去彼此的獨立性；改共用函式庫時，團隊之間必須協調。
- 常見解法：兩種：(1) 接受冗餘，降低團隊之間的相依；(2) 把函式庫抽成一個可以獨立開發和部署的共用服務。
- 何時不算：〔推論〕穩定、不常改的基礎工具函式庫（參照 DIP 的緩和因素：具體但不易變）。
- 來源：https://arxiv.org/abs/1908.04101

### ESB Usage（使用企業服務匯流排）
- 別名：Neri 的 ESB Misuse
- 定義：微服務之間透過企業服務匯流排（Enterprise Service Bus，ESB）溝通。
- 辨識訊號：用 ESB 連接微服務。危害中位數 6（2 人，7%）。
- 為何有害：在 ESB 上註冊和註銷服務增加了複雜度。Neri：ESB 被當成中央樞紐，業務邏輯集中在它身上，成為架構瓶頸，違反去中心化原則。
- 常見解法：改用輕量的訊息匯流排；Neri 建議改成「dumb pipes」（只傳遞、不處理邏輯的管道），用佇列做非同步訊息傳遞。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101 、https://arxiv.org/abs/1906.01553

### Wobbly Service Interactions（不穩的服務互動）
- 定義（Neri）：一個服務失敗，會連帶觸發依賴它的服務也失敗（連鎖失效）。
- 辨識訊號：同步呼叫鏈上沒有逾時、斷路器或隔艙設計〔推論〕。
- 為何有害：違反故障隔離原則。
- 常見解法：斷路器（circuit breaker）、用訊息代理解耦、逾時、隔艙（bulkhead，把資源分艙，讓故障局限在一處）。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1906.01553

### G3 技術—其他

### Shared Persistence（共用持久層／共用資料庫）
- 別名：「data ownership」問題（Bogard）、Shared Database
- 定義：不同的微服務存取同一個關聯式資料庫；最糟的情況是存取同一個資料庫裡的同一批實體。
- 辨識訊號：多個服務的連線字串指向同一個資料庫或 schema。危害中位數 6.05（10 人，37%）。
- 為何有害：連到同一份資料的服務被高度耦合，團隊和服務的獨立性都降低。Neri：違反去中心化。
- 常見解法（Taibi 列出的三種）：(1) 每個服務有自己獨立的資料庫；(2) 共用資料庫，但每個服務有一組只有自己能存取的私有表；(3) 每個服務有自己的私有 schema。Neri 另外提出：把資料庫拆開、引入專門管理資料的服務，或把共用資料庫的服務合併。
- 何時不算：未查證。
- 來源：https://arxiv.org/abs/1908.04101 、https://arxiv.org/abs/1906.01553

### Wrong Cuts（錯誤切分）
- 定義：服務應該依**業務能力**切分，卻依**技術層**（展示層、業務層、資料層）切分。
- 辨識訊號：出現 `frontend-service`、`business-service`、`data-service` 這類以技術層命名的服務〔推論例〕。危害中位數 **8**，提及人數最多（15 人，56%）。
- 為何有害：關注點分離錯誤，資料拆分的複雜度上升。
- 常見解法：清楚分析業務流程和資源需求。
- 何時不算：未查證。
- 組織層的對應：Neri 的 Single-layer Teams（依技術層而不是依服務組團隊）。
- 來源：https://arxiv.org/abs/1908.04101

### Distributed Monolith（分散式單體）
- 定義（Newman）：系統拆成了多個程序，卻必須整個系統一起部署，也就是「鎖步發布」（lockstep release）。
- 辨識訊號：Newman：如果你有一位全職的發布協調經理，你很可能就有一個分散式單體。〔推論〕常見同時徵兆：多個服務必須同版本一起上線；長串的同步呼叫鏈；Shared Persistence。
- 為何有害：承擔了微服務的部署複雜度，卻沒有它的主要好處——獨立部署。
- 常見解法：Newman：以「能獨立部署」為最重要的目標。
- 何時不算：未查證。
- 來源：https://www.theregister.com/2020/03/04/microservices_last_resort/

### Multiple Services in One Container（一個容器放多個服務）
- 定義（Neri）：把多個服務放進同一個容器。
- 辨識訊號：同一個容器映像裡啟動了多個服務程序〔推論〕。
- 為何有害：違反服務可獨立部署的原則。
- 常見解法：每個服務各自封裝成一個容器映像。
- 何時不算：sidecar（附掛在主服務旁、提供輔助功能的容器）這類刻意的輔助程序〔推論〕。
- 來源：https://arxiv.org/abs/1906.01553

### G4 組織（非程式碼，但會反映在架構上；速查）

| 名稱 | 定義／問題（Taibi 2019；Single-layer Teams 為 Neri） | 危害中位數 |
|---|---|---|
| Legacy Organization（舊式組織） | 流程和政策沒改：Dev 與 Ops 分開、人工測試、排定共同發布日 → 享受不到微服務的好處 | 6 |
| Microservice Greedy（微服務貪食） | 每個功能都開一個新服務，即使根本不需要（例如只提供一兩個靜態 HTML 頁面的服務）→ 服務數量爆炸，系統大到難以維護 | 3 |
| Too Many Technologies（技術過多） | 用了太多不同的語言、協定、框架，又沒有共同政策；人員流動時特別麻煩。Bryant 稱為「Lust」「Gluttony」；Taibi 2018 的 IEEE Software 版本是否稱為「Too many standards」**未查證** | 4 |
| Lack of Microservice Skeleton（缺少服務骨架） | 每個團隊從零寫服務，沒有共用骨架（例如連 API Gateway 的樣板）→ 重工、出錯風險高；解法：共用樣板 | 3.05 |
| Common Ownership（共同擁有） | 一個團隊擁有所有服務 → 實際上是循序開發，沒有發揮開發獨立性 | 2 |
| Non-homogeneous Adoption（不一致的導入） | 只有少數團隊遷移，要不要遷移交給團隊自行決定 → 基礎設施、部署管線重複建置 | 2 |
| Focus on Latest Technologies（追新技術） | 遷移是為了採用最新技術，而不是解決實際問題 | 2.05 |
| No DevOps Tools（無 DevOps 工具） | 沒有 CI/CD，人工測試和部署 → 生產力低、部署出錯 | 2 |
| Single-layer Teams（單層團隊） | 依技術層而不是依服務組團隊 → 無法自主決策；解法：組成全端團隊，各自完整負責一個服務 | —（Neri，無評分） |

來源：https://arxiv.org/abs/1908.04101 、https://arxiv.org/abs/1906.01553

---

## H. 命名衝突與易混淆對照（查閱時必看）

| 名稱 | 版本一 | 版本二 | 建議 |
|---|---|---|---|
| Ambiguous Interface | Garcia 2009：單一、一般化的進入點，內部再分派 | Azadi 目錄／AI Reviewer：為未來需求過度設計的介面（Underused Interface） | 引用時註明出處 |
| Unutilized Abstraction | Suryanarayana 2014：沒人用的抽象 | Azadi 目錄：直接引用具體類別而非父型別（Policy Detail Dependency） | 同上 |
| God Component | 尺寸派（Lippert、Arcan：LOC 相對過大） | 關注點派（Azadi、ARCADE：關注點過多） | 兩者常一起出現，偵測規則不同 |
| Cyclic Dependency | 類別層（Cyclically-dependent Modularization） | 套件層（ADP）／服務層（Taibi） | 依尺度選解法 |
| Hub-like | 類別層（Designite 20/20） | 套件層（Arcan：中位數 + 平衡條件） | 同一程式碼兩工具結果可能差很多 |
| Unstable Dependency vs Unstable Interface | 結構上的 I 值（Arcan、Designite） | 版控歷史的共同變更（Mo 等人 Hotspot） | 兩種偵測結果「可能不同」（Azadi） |
| Unexploited Encapsulation vs Missing Hierarchy | 階層已存在，卻用型別檢查 | 階層根本沒建，用型別碼加條件 | 解法分別是「用上它」和「建出來」 |
| Scattered Parasitic Functionality vs Shotgun Surgery | 一個關注點分散，而且宿主元件同時還有正交關注點 | 一個改動要改很多類別，不管關注點 | Garcia 明確區分 |

---

## 3. 來源清單

| 代號 | 來源 | URL |
|---|---|---|
| S1 | Tushar Sharma, A Taxonomy of Software Smells（線上目錄；各味道頁 `/smells/<ID>.html`；資料檔在 GitHub） | https://www.tusharma.in/smells/ ；https://github.com/tushartushar/smells |
| S2 | Suryanarayana, Samarthyam, Sharma,《Refactoring for Software Design Smells》, Morgan Kaufmann 2014 | https://shop.elsevier.com/books/refactoring-for-software-design-smells/suryanarayana/978-0-12-801397-7 |
| S3 | 同作者 ICSE 2014 教程投影片 | https://www.slideshare.net/slideshow/refactoring-for-software-design-smells-icse-2014-tutorial/35564821 |
| S4 | DesigniteJava 原始碼（門檻與偵測規則） | https://github.com/tushartushar/DesigniteJava/blob/master/src/Designite/smells/ThresholdsDTO.java |
| S5 | R. C. Martin, Design Principles and Design Patterns（2000） | https://eli.sdsu.edu/courses/fall19/cs635/Principles_and_Patterns.pdf |
| S6 | HMC CS121 講義（引 Martin《Agile Software Development》七個設計味道） | https://www.cs.hmc.edu/courses/2009/spring/cs121/13OODprinciples.pdf |
| S7 | R. C. Martin, The Single Responsibility Principle（2014） | https://blog.cleancoder.com/uncle-bob/2014/05/08/SingleReponsibilityPrinciple.html |
| S8 | Wikipedia, Software package metrics | https://en.wikipedia.org/wiki/Software_package_metrics |
| S9 | Sas, Avgeriou 等, On the evolution and impact of Architectural Smells — an industrial case study（Arcan 定義與門檻） | https://arxiv.org/abs/2203.08702 |
| S10 | Arcan 工具頁 | https://essere.disco.unimib.it/wiki/arcan/ |
| S11 | Azadi & Arcelli Fontana, Architectural Smells Detected by Tools: a Catalogue Proposal | http://www.taibi.it/sites/default/files/Architectural%20Smells%20Detected%20by%20Tools%20a%20Catalogue%20Proposal.pdf |
| S12 | Garcia, Popescu, Edwards, Medvidovic, Toward a Catalogue of Architectural Bad Smells（QoSA 2009） | https://jgarcia.ics.uci.edu/wp-content/uploads/10.1.1.183.9958.pdf |
| S13 | Sharma, Fragkoulis, Spinellis, Does Your Configuration Code Smell?（MSR 2016；Dense Structure 原始定義） | https://www.spinellis.gr/pubs/conf/2016-MSR-conf-smells/html/MSR-2016%20configuration%20smells.pdf |
| S14 | Taibi, Lenarduzzi, Pahl, Microservices Anti-Patterns: A Taxonomy | https://arxiv.org/abs/1908.04101 |
| S15 | Neri 等, Design principles, architectural smells and refactorings for microservices: A multivocal review | https://arxiv.org/abs/1906.01553 |
| S16 | Sam Newman 談 Distributed Monolith（The Register 2020） | https://www.theregister.com/2020/03/04/microservices_last_resort/ |
| S17 | Foote & Yoder, Big Ball of Mud | http://www.laputan.org/mud/ |
| S18 | Fowler, AnemicDomainModel | https://martinfowler.com/bliki/AnemicDomainModel.html |
| S19 | Seemann, Service Locator is an Anti-Pattern | https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/ |
| S20 | Hevery, Singletons are Pathological Liars（Google Testing Blog 2008） | https://testing.googleblog.com/2008/08/by-miko-hevery-so-you-join-new-project.html |
| S21 | Fowler, Yagni | https://martinfowler.com/bliki/Yagni.html |
| S22 | Wikipedia, Lava flow (programming) | https://en.wikipedia.org/wiki/Lava_flow_(programming) |
| S23 | Wikipedia, Design smell | https://en.wikipedia.org/wiki/Design_smell |

Mo 等人〈Hotspot Patterns〉（WICSA 2015）、Lippert & Roock《Refactoring in Large Software Projects》（2006）、Brown 等人《AntiPatterns》（1998）、Riel《Object-Oriented Design Heuristics》（1996）、Andrade 等人（WICSA 2014）的內容，都是透過 S1 目錄的逐條摘錄取得，**沒有直接讀原書或原論文**。

## 4. 查證狀態

- **未查證**：
  - Designite 在程式碼架構層的 Dense Structure、Feature Concentration、Unstable Dependency 門檻；
  - Mo 等人 Hotspot Detector 的數字門檻；
  - Martin 的 D 值警戒門檻（原文沒給）；
  - Taibi 2018 IEEE Software 版本的完整 11 項名單，以及是否有「Too many standards」這個名稱；
  - DesigniteJava 的 Deficient Encapsulation 是否排除常數；
  - 多數階層類味道的「何時不算」（原始資料沒有寫，已標「未查證」或〔推論〕）。
- **間接取得**：Lippert、Brown、Riel、Mo、Andrade 的內容來自 S1 目錄的摘錄（見上）。
- **已對原始碼或原文驗證**：DesigniteJava 全部門檻（讀原始碼）；Martin 2000 原文（ADP／SDP／SAP、四個腐化徵兆、DIP 緩和因素、ISP 分組說明、破環兩法）；Garcia 2009 四個味道和它們的可接受情境；Taibi 2019 全部表格與危害分數；Azadi 目錄中各工具的門檻；MSR 2016 的 Dense Structure 公式。
