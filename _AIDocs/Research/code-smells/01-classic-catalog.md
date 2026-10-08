# 經典壞味道目錄（程式碼層級）

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 切面 01：Fowler《Refactoring》第 1／2 版、Refactoring Guru、Mäntylä 分類學、Wake《Refactoring Workbook》、Kerievsky《Refactoring to Patterns》。
> 查證日：2026-10-08。條目共 38 個。

---

## 0. 讀前須知

- **壞味道（code smell）**：Fowler 的定義是「表面看得到的跡象，通常對應系統裡更深的問題」（*a surface indication that usually corresponds to a deeper problem in the system*）。這個詞是 Kent Beck 協助 Fowler 寫《Refactoring》時提出的。
  **味道只是提示，不是定罪**。Fowler 自己說「有些長函式完全沒問題」，聞到味道後要看底下的程式碼，才知道是不是真有問題。來源：https://martinfowler.com/bliki/CodeSmell.html
- **重構手法（refactoring）**：外部行為不變、只改內部結構的小步驟，每一步都有名字。例如 Extract Function＝把一段程式碼抽成一個有名字的函式。「常見解法」欄列的就是這些手法名。第 2 版名稱優先，第 1 版的舊名附在後面。§4 有中譯對照表。
- **來源代號**

| 代號 | 指的是 |
|---|---|
| [F2] | Fowler & Beck《Refactoring》第 2 版（2018）第 3 章 |
| [F1] | 第 1 版（1999） |
| [RG] | Refactoring Guru 網站 |
| [M03] / [M06] | Mäntylä 2003 年與 2006 年兩版分類 |
| [W] | Wake《Refactoring Workbook》（2003） |
| [K] | Kerievsky《Refactoring to Patterns》（2004） |
| [IL] | Industrial Logic 的「Smells to Refactorings」速查表（整理 F1 與 K 的內容並附頁碼） |
| [MT] | Marinescu 式的工具偵測規則（Borland Together／inCode 採用），轉引自 Yamashita & Moonen 2012 技術報告附錄 A |

- **門檻值都是經驗法則**：各家數字不同，Fowler 本人刻意不給數字。[MT] 的數字是工具「標出來讓人看」用的，不代表「超過就是錯」。
- **標記**：「（推論）」是本文依通行做法補上、來源沒有明寫的內容；「（未查證）」是找不到可靠來源的內容。
- **中譯**：Fowler 第 2 版的味道名稱採簡中版譯名再轉成繁體，已對照 https://www.cnblogs.com/loveshes/p/17367886.html 。其他譯名是通行說法，標了「譯名未查證」的僅供參考。

---

## 1. 這個切面的分類架構（建議）

Refactoring Guru 與 Mäntylä 2006 的五大類引用最廣，但只收到 Fowler 第 1 版的味道。第 2 版新增的 Global Data、Mutable Data、Loops、Mysterious Name，以及 Wake 的命名類、條件邏輯類味道，都放不進這五類。所以建議用五大類當骨架，另外補三類（B、C、H）：

```
壞味道（程式碼層級）
├─ A. 膨脹 Bloaters ................ 東西長太大，一眼看不完
├─ B. 命名與表達 .................... 讀者猜不到意圖（名字、註解、魔術數字）
├─ C. 條件與流程 .................... 分支、迴圈、null 判斷越疊越亂
├─ D. 物件導向誤用 OO Abusers ....... 繼承、多型、欄位用法不對
├─ E. 變更阻礙 Change Preventers .... 改一件事要動很多地方，或一個地方被很多種變更拉扯
├─ F. 可有可無 Dispensables ......... 拿掉反而更清楚的東西
├─ G. 耦合 Couplers ................. 模組彼此知道太多，或委託過頭
└─ H. 共享狀態 ...................... 資料能被太多地方改（全域、可變）
```

| 類 | 一句說明 | 本文條目 | 依據 |
|---|---|---|---|
| A 膨脹 | 慢慢長大到難以處理；Mäntylä 認為「不太可能有人故意設計出來」 | Long Function, Large Class, Long Parameter List, Primitive Obsession, Data Clumps | RG／M06 Bloaters |
| B 命名與表達 | 程式碼本身說不清在做什麼 | Mysterious Name（含 W 的 Uncommunicative Name）, Type Embedded in Name, Inconsistent Names, Magic Number, Comments | F2 新增＋W「Names」類 |
| C 條件與流程 | 控制流程複雜或重複 | Repeated Switches（＝Switch Statements）, Loops, Conditional Complexity, Complicated Boolean Expression, Null Check, Special Case | F2＋W「Conditional Logic」類＋K |
| D 物件導向誤用 | 沒把物件導向的機制用對 | Temporary Field, Refused Bequest, Alternative Classes with Different Interfaces | RG OO Abusers（Switch 移到 C） |
| E 變更阻礙 | 「類別」與「可能的變更」沒有一對一對應 | Divergent Change, Shotgun Surgery, Parallel Inheritance Hierarchies, Combinatorial Explosion, Solution Sprawl | RG／M06＋W「Accommodating Change」類＋K |
| F 可有可無 | 不必要、該刪的東西 | Duplicated Code, Lazy Element, Speculative Generality, Data Class, Dead Code, Oddball Solution | RG Dispensables＋K |
| G 耦合 | 耦合太高，或為了避免耦合而委託過頭 | Feature Envy, Insider Trading（＝Inappropriate Intimacy）, Message Chains, Middle Man, Incomplete Library Class, Indecent Exposure | RG Couplers＋K |
| H 共享狀態 | 能被任意修改的資料 | Global Data, Mutable Data | F2 新增 |

分類只是方便查找，同一個味道常跨好幾類。例如 Repeated Switches 本質上也是重複程式碼，Magic Number 在 Wake 的分類裡就歸在「Duplication」。

---

## 2. 各家目錄對照

### 2.1 Fowler 第 1 版（22 個）→ 第 2 版（24 個）

| 第 1 版（1999） | 第 2 版（2018） | 變動 |
|---|---|---|
| — | Mysterious Name | 新增 |
| Duplicated Code | Duplicated Code | — |
| Long Method | Long Function | 改名 |
| Long Parameter List | Long Parameter List | — |
| — | Global Data | 新增 |
| — | Mutable Data | 新增 |
| Divergent Change | Divergent Change | — |
| Shotgun Surgery | Shotgun Surgery | — |
| Feature Envy | Feature Envy | — |
| Data Clumps | Data Clumps | — |
| Primitive Obsession | Primitive Obsession | — |
| Switch Statements | Repeated Switches | 改名，且範圍縮小：只算「重複出現」的 switch |
| — | Loops | 新增 |
| Lazy Class | Lazy Element | 改名，範圍擴及函式 |
| Speculative Generality | Speculative Generality | — |
| Temporary Field | Temporary Field | — |
| Message Chains | Message Chains | — |
| Middle Man | Middle Man | — |
| Inappropriate Intimacy | Insider Trading | 改名 |
| Large Class | Large Class | — |
| Alternative Classes with Different Interfaces | 同左 | — |
| Data Class | Data Class | — |
| Refused Bequest | Refused Bequest | — |
| Comments | Comments | — |
| Parallel Inheritance Hierarchies | — | 移除 |
| Incomplete Library Class | — | 移除 |

- 第 2 版的完整清單與順序依原書第 3 章，來源：https://www.informit.com/articles/article.aspx?p=2952392
- 增、刪、改名的整理來自二手來源 https://dev.to/trikitrok/on-code-smells-catalogues-and-taxonomies-3ba6 。Fowler 官方的改版說明只說味道這一章「大約四分之三改寫了」，沒有逐條列出：https://martinfowler.com/articles/refactoring-2nd-changes.html
- **移除兩條的理由：Fowler 沒有公開說明（未查證）。**

### 2.2 Refactoring Guru 五大分類（共 23 個）

| 分類（RG 簡中站譯名） | RG 一句說明 | 成員 |
|---|---|---|
| Bloaters（膨脹類） | 程式碼、方法、類別長到難以處理 | Long Method, Large Class, Primitive Obsession, Long Parameter List, Data Clumps |
| Object-Orientation Abusers（物件導向濫用） | 物件導向原則用得不完整或不正確 | Alternative Classes with Different Interfaces, Refused Bequest, Switch Statements, Temporary Field |
| Change Preventers（變更阻礙） | 改一處就得在很多其他地方跟著改 | Divergent Change, Parallel Inheritance Hierarchies, Shotgun Surgery |
| Dispensables（可消除物） | 沒意義也不需要，拿掉會更乾淨好懂 | Comments, Duplicate Code, Data Class, Dead Code, Lazy Class, Speculative Generality |
| Couplers（耦合物） | 類別間耦合過度，或用過度委託取代耦合 | Feature Envy, Inappropriate Intimacy, Incomplete Library Class, Message Chains, Middle Man |

- 來源：https://refactoring.guru/refactoring/smells ；簡中站 https://refactoringguru.cn/refactoring/smells
- RG 用的是 Fowler 第 1 版名稱，另外加了 Dead Code。

### 2.3 Mäntylä 分類學（taxonomy）

| 組 | 2003 版：7 組（ICSM，Mäntylä、Vanhanen、Lassenius） | 2006 版：5 組（EMSE 11(3)，Mäntylä & Lassenius） |
|---|---|---|
| Bloaters | Long Method, Large Class, Primitive Obsession, Long Parameter List, Data Clumps | 同左 |
| Object-Orientation Abusers | Switch Statements, Temporary Field, Refused Bequest, Alternative Classes with Different Interfaces, **Parallel Inheritance Hierarchies** | Switch Statements, Temporary Field, Refused Bequest, Alternative Classes with Different Interfaces |
| Change Preventers | Divergent Change, Shotgun Surgery | Divergent Change, Shotgun Surgery, **Parallel Inheritance Hierarchies** |
| Dispensables | Lazy Class, Data Class, Duplicate Code, Speculative Generality | 同左＋**Dead Code** |
| Encapsulators | Message Chains, Middle Man | （此組刪除） |
| Couplers | Feature Envy, Inappropriate Intimacy | Feature Envy, Inappropriate Intimacy, **Message Chains, Middle Man** |
| Others | Comments, Incomplete Library Class | （此組刪除） |

Mäntylä 對各組的關鍵見解（2006 網頁原文）：
- Primitive Obsession 與 Data Clumps 與其說是膨脹本身，不如說是**造成膨脹的原因**：沒有小類別來裝小概念（例如電話號碼），功能只好塞進別的類別。
- Parallel Inheritance Hierarchies 原本放在 OO Abusers，後來移到 Change Preventers。它本質上是重複的類別階層，也可以歸到 Dispensables。
- Change Preventers 違反的是 Fowler & Beck 的原則：類別與可能的變更應該一對一。
- Middle Man 是反方向的問題：為了避免高耦合而不斷委託，結果做過頭。
- Temporary Field 是把本該屬於方法範圍的變數放到了類別範圍，違反資訊隱藏（information hiding，對外只露出必要部分）。

來源：
- 2006 版網頁的存檔：https://web.archive.org/web/20201105221533/http://mikamantyla.eu/BadCodeSmellsTaxonomy.html （PDF 副本：https://courses.cs.duke.edu/compsci308/spring23/resources/Code_Smells_Taxonomy.pdf ）
- 2003 版前 5 組的成員：https://arxiv.org/html/2004.10777
- 2003 版 Encapsulators／Others 兩組的成員與 2006 年的搬移：https://dev.to/trikitrok/on-code-smells-catalogues-and-taxonomies-3ba6
- 2003 論文書目：https://research.fi/en/results/publication/0357437703 。**原論文全文沒有取得，2003 版那兩組的成員只靠二手來源。**

### 2.4 Wake《Refactoring Workbook》的 10 個子類

| 大類 | 子類 | 成員（**粗體**＝Wake 新增、Fowler 第 1 版沒有的） |
|---|---|---|
| 類別內（Within Classes） | Measured Smells（能用長度量出來的） | Comments, Long Method, Long Parameter List, Large Class |
| | Names | **Type Embedded in Name, Uncommunicative Name, Inconsistent Names** |
| | Unnecessary Complexity | **Dead Code**, Speculative Generality |
| | Duplication | **Magic Number**, Duplicated Code, Alternative Classes with Different Interfaces |
| | Conditional Logic | **Null Check, Complicated Boolean Expression, Special Case**, Switch Statements（Wake 歸類名 Simulated Inheritance） |
| 類別間（Between Classes） | Data | Primitive Obsession, Data Class, Data Clumps, Temporary Field |
| | Inheritance | Refused Bequest, Inappropriate Intimacy, Lazy Class |
| | Responsibility | Feature Envy, Message Chains, Middle Man |
| | Accommodating Change | Divergent Change, Shotgun Surgery, Parallel Inheritance Hierarchies, **Combinatorial Explosion** |
| | Library Classes | Incomplete Library Class |

- 成員歸屬來源：https://sape.inf.usi.ch/essence/algorithmic/smells.html
- 子類說明與「Wake 新增 9 個味道」：https://dev.to/trikitrok/on-code-smells-catalogues-and-taxonomies-3ba6
- 章節結構：https://xp123.com/articles/refactoring-workbook/
- **Wake 原書對各味道的定義與門檻沒有取得（未查證）。**

### 2.5 Kerievsky《Refactoring to Patterns》的 12 個味道

Duplicated Code, Long Method, Conditional Complexity, Primitive Obsession, Indecent Exposure, Solution Sprawl, Alternative Classes with Different Interfaces, Lazy Class（Kerievsky 稱 Freeloader）, Large Class, Switch Statement, Combinatorial Explosion, Oddball Solution。

- **Kerievsky 新增的**：Conditional Complexity、Indecent Exposure、Solution Sprawl、Oddball Solution。Combinatorial Explosion 在 Wake 與 Kerievsky 兩本書都有。
- **更正任務前提**：Oddball Solution 出自 Kerievsky，不是 Wake 或 Kent Beck。
- 來源：[IL] https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf （原址 industriallogic.com/papers/smellstorefactorings.pdf）

---

## 3. 條目

### A. 膨脹（Bloaters）

### Long Function（過長函式）
- 別名：Long Method（F1、RG、W、K）；工具界稱 God Method
- 定義：一個函式長到要從頭讀完，才知道它在做什麼。
- 辨識訊號：
  - [F2] 不給行數，看「做什麼」與「怎麼做」之間的語意距離（semantic distance）有多大。**想寫註解說明某一段時，那一段就該抽成函式**。條件式與迴圈也都是可以抽出來的訊號。
  - [RG] 超過 10 行就該開始問問題。
  - [MT] God Method：行數在全系統前 20%（且至少 70 行），並且參數超過 4 個或區域變數超過 4 個，並且最大分支數超過 4。
- 為何有害：越長越難懂。小函式的好處（解釋意圖、共用、選擇）都靠好名字撐起來。現代語言的函式呼叫成本已經可以忽略。
- 常見解法：Extract Function（主力）、Replace Temp with Query、Introduce Parameter Object、Preserve Whole Object、Replace Function with Command（F1 名 Replace Method with Method Object）、Decompose Conditional、Replace Conditional with Polymorphism、Split Loop
- 何時不算：Fowler 說「有些長函式完全沒問題」（bliki）。重點是能不能用名字講清楚意圖，而不是行數。[F2] 甚至主張：就算抽出來後的呼叫比原本的程式碼還長，只要名字說清楚目的就值得抽。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=3 ；https://refactoring.guru/smells/long-method ；https://martinfowler.com/bliki/CodeSmell.html ；[MT] https://cms.simula.no/sites/default/files/publications/Simula.simula.1494.pdf

### Large Class（過大的類別）
- 別名：God Class、Blob（上帝類別，見於工具與反模式文獻）
- 定義：一個類別想做太多事。
- 辨識訊號：
  - [F2] 欄位太多，程式碼太多又伴隨重複。看呼叫端分別用了這個類別的哪些子集，每個子集都可能是一個獨立的類別。
  - [MT] God Class：存取外部資料量（AOFD）在全系統前 20% 且超過 4；方法複雜度總和（WMPC1）超過 20；方法之間的緊密內聚度（TCC）低於 33%。
- 為何有害：[F2] 程式碼太多的類別是「重複、混亂與死亡的溫床」。
- 常見解法：Extract Class、Extract Superclass、Replace Type Code with Subclasses；RG 另列 Extract Subclass、Extract Interface、Duplicate Observed Data（GUI 類別混進領域邏輯時用）
- 何時不算：來源沒有列出例外（未查證）。補充一項實證：Yamashita & Moonen 發現，部分大類別的維護問題不是直接來自大小，而是多個味道擠在同一個檔案裡互相放大。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=20 ；https://refactoring.guru/smells/large-class ；[MT] 同上

### Long Parameter List（過長參數列）
- 別名：—
- 定義：函式的參數多到難以理解。
- 辨識訊號：
  - [RG] 超過 3～4 個參數。
  - [F2] 不給數字，訊號有四種：某個參數其實能從另一個參數查到；好幾個參數總是一起出現；用旗標參數（flag argument，傳 true/false 切換行為）；好幾個函式共用同一批參數。
- 為何有害：[F1，經 IL] 難懂，而且容易跟著需求變動。
- 常見解法：Replace Parameter with Query（F1 名 Replace Parameter with Method）、Preserve Whole Object、Introduce Parameter Object、Remove Flag Argument（F1 名 Replace Parameter with Explicit Methods）、Combine Functions into Class
- 何時不算：[RG] 如果拿掉參數會在類別之間造成不想要的依賴，就不要拿掉。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=4 ；https://refactoring.guru/smells/long-parameter-list

### Primitive Obsession（基本型別偏執）
- 別名：stringly typed（[F2] 用語，指什麼都用字串表示）
- 定義：用 int、string、float 這類基本型別，表示有意義的領域概念，例如金額、座標、電話、範圍。
- 辨識訊號：
  - [RG] 三種：用基本型別代替小物件（貨幣、範圍、電話字串）；用常數編碼資訊（例如 `USER_ADMIN_ROLE = 1`）；用字串常數當作資料陣列的欄位名。
  - [F2] 計算時忽略單位；用型別碼（type code）驅動條件式。
- 為何有害：缺驗證、缺單位，顯示邏輯重複散落各處。[IL／K] 一旦建了類別，常會發現系統裡還有別的程式碼也該搬進去。
- 常見解法：Replace Primitive with Object（F1 名 Replace Data Value with Object／Replace Type Code with Class）、Replace Type Code with Subclasses、Replace Conditional with Polymorphism、Extract Class、Introduce Parameter Object（成群出現時用）；RG 另列 Replace Type Code with State/Strategy、Replace Array with Object
- 何時不算：來源沒有列出（未查證）。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=11 ；https://refactoring.guru/smells/primitive-obsession

### Data Clumps（資料泥團）
- 別名：—
- 定義：同一組資料總是一起出現（當欄位、當參數），卻沒有包成一個物件。
- 辨識訊號：同一組 2 個以上的欄位或參數，在多處一起出現，例如資料庫連線參數、RGB 三個整數。
  - [F2] 檢驗法：「刪掉其中一個，其他的還有意義嗎？沒有的話，就有個物件正等著誕生。」
  - [F2] 只要能用新物件取代 2 個以上的欄位就划算，不必在意有些地方只用到其中部分欄位。
- 為何有害：[M06] 讓方法與類別膨脹。也錯過了把行為搬到資料旁邊的機會。
- 常見解法：Extract Class、Introduce Parameter Object、Preserve Whole Object。[F2] 建議做成類別而不是純記錄，方便之後把行為搬進去。
- 何時不算：[RG] 傳整個物件而不是傳幾個值，可能讓兩個類別之間產生不想要的依賴。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=10 ；https://refactoring.guru/smells/data-clumps

### B. 命名與表達

### Mysterious Name（神祕命名）
- 別名：Uncommunicative Name（[W]，詞不達意的命名，意思相近）
- 定義：函式、模組、變數、類別的名字，沒辦法讓人一看就懂它做什麼、怎麼用。
- 辨識訊號：
  - 讀者得去看實作才知道用途。
  - [F2] 想不出好名字，往往代表底下有更深的設計問題。
  - Coding Horror 對 Uncommunicative Name 的檢查句：「方法名稱有沒有簡潔描述這個方法做的事？」
- 為何有害：[F2] 讓程式碼清楚的最重要元素就是好名字；名字不好，每次閱讀都要付出成本。
- 常見解法：Change Function Declaration（F1 名 Rename Method）、Rename Variable、Rename Field
- 何時不算：來源沒有列出。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392 ；https://blog.codinghorror.com/code-smells/

### Type Embedded in Name（名稱內嵌型別）— Wake
- 別名：—
- 定義：把型別寫進名字裡，例如 `nameString`、`strName`、`getUserList`（例子為推論）。
- 辨識訊號：名字含有型別字樣（String、List、Int）或型別前綴（例如 str、i）（推論）。
- 為何有害：Coding Horror：重複了型別資訊，而且型別一改，名字也得跟著改。
- 常見解法：Change Function Declaration、Rename Variable、Rename Field（推論）
- 何時不算：（推論）名字中表示單位或角色的部分不算型別，例如 `timeoutMs`，那是語意。
- 來源：歸類 https://sape.inf.usi.ch/essence/algorithmic/smells.html ；描述 https://blog.codinghorror.com/code-smells/ 。**Wake 原文未查證。**

### Inconsistent Names（命名不一致）— Wake
- 別名：—
- 定義：同一個概念在不同地方用不同的詞，例如 fetch、get、retrieve 混用（例子為推論）。
- 辨識訊號：Coding Horror：「挑一套標準用詞，在所有方法中一貫使用。」做不到這點就是訊號。
- 為何有害：Wake 的 Names 類「造成語意混淆，妨礙讀者建立心智模型」（dev.to 轉述）。讀者會以為用詞不同就代表意思不同（推論）。
- 常見解法：用 Rename 系列手法統一用詞（推論）
- 何時不算：來源沒有列出。
- 來源：https://sape.inf.usi.ch/essence/algorithmic/smells.html ；https://blog.codinghorror.com/code-smells/ ；https://dev.to/trikitrok/on-code-smells-catalogues-and-taxonomies-3ba6 。**Wake 原文未查證。**

### Magic Number（魔術數字）— Wake
- 別名：Magic Literal（F2 的手法名用 literal，也就是程式裡直接寫出的字面值，涵蓋字串）
- 定義：程式碼裡直接出現沒有名字的字面常數，讀者看不出它的含義。
- 辨識訊號：同一個字面值散落多處；條件式裡出現裸數字（推論）。
- 為何有害：意義不明；要修改時得找出每一個出現的地方。Wake 把它歸在 Duplication 類，原因就是它本質上是重複。
- 常見解法：Replace Magic Literal（F1 名 Replace Magic Number with Symbolic Constant）
- 何時不算：（推論）0、1、明顯的數學常數，或只出現一次而且旁邊語意自明的值。
- 來源：歸類 https://sape.inf.usi.ch/essence/algorithmic/smells.html ；手法改名 https://martinfowler.com/articles/refactoring-2nd-changes.html 。**Wake 原文未查證。**

### Comments（註解）
- 別名：Deodorant（除臭劑，[IL] 標註的別名）
- 定義：用註解遮蓋寫得不好的程式碼。註解本身不是壞事，壞的是「要靠註解才看得懂」的程式碼。
- 辨識訊號：[RG] 方法裡塞滿解釋性註解。[F2] 想寫註解時，先試著重構，讓註解變得多餘。
- 為何有害：[F2] 註解常被拿來替爛程式除臭；把底下的味道重構掉之後，註解就多餘了。
- 常見解法：Extract Function、Change Function Declaration、Introduce Assertion；RG 另列 Extract Variable
- 何時不算：
  - 說明「為什麼」這樣做。
  - [F2] 記錄不確定的地方：「不知道該怎麼做時，正是寫註解的好時機。」
  - [RG] 複雜演算法，而且其他簡化方法都試過了。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=24 ；https://refactoring.guru/smells/comments

### C. 條件與流程

### Repeated Switches（重複的 switch）
- 別名：Switch Statements（F1、RG、M）、Switch Statement（K）、Simulated Inheritance（W 的歸類名）
- 定義：同一組按型別或狀態分派的 switch（或 if-else 串），在多處重複出現。
- 辨識訊號：[F2] 新增一個分支時，得找出所有相同的 switch 一起改。
- 為何有害：只要漏改一處就出 bug；本質上是重複。
- 常見解法：Replace Conditional with Polymorphism（F2 只列這一個）；F1／RG 另列 Replace Type Code with Subclasses、Replace Type Code with State/Strategy、Replace Parameter with Explicit Methods（F2 名 Remove Flag Argument）、Introduce Null Object（F2 名 Introduce Special Case）
- 何時不算：
  - [F2] 單一個 switch「已經不是十五年前那種簡單的紅旗」，很多語言有更強大的 switch。這條只針對**重複**。
  - [RG] switch 只做簡單動作時不必改；工廠模式（Factory Method、Abstract Factory）用 switch 決定建立哪個類別是正常的。
- 第 1 版與第 2 版的差別：F1／RG 的 Switch Statements 是「複雜的 switch 或 if 串」就算；F2 縮小成「重複」才算。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=12 ；https://refactoring.guru/smells/switch-statements

### Loops（迴圈）
- 別名：—
- 定義：用傳統 for／while 迴圈處理集合，但語言已經有 pipeline（filter／map／reduce 這類串接操作）可以用。
- 辨識訊號：迴圈裡混著篩選、轉換、累加，要讀完整個迴圈才知道它處理了哪些元素、做了什麼。
- 為何有害：[F2] pipeline 能讓「處理哪些元素、怎麼處理」一眼看出來。
- 常見解法：Replace Loop with Pipeline
- 何時不算：[F2] 沒有列出例外，語氣很強（說迴圈「跟喇叭褲、植絨壁紙一樣過時」）。以下是推論的例外：效能熱點、需要複雜提前跳出的控制流程、語言沒有好用的 pipeline。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=13

### Conditional Complexity（條件複雜度）— Kerievsky
- 別名：—
- 定義：條件邏輯隨著功能增加，變得又大又亂。
- 辨識訊號：
  - [K] 「條件邏輯在嬰兒期很單純……可惜很少老得好看。」
  - Coding Horror：留意大型條件區塊，尤其是會持續變大或常常被改的那些。
- 為何有害：難以推理，也難以擴充。
- 常見解法：[IL／K] Introduce Null Object、Move Embellishment to Decorator、Replace Conditional Logic with Strategy、Replace State-Altering Conditionals with State
- 何時不算：來源沒有列出。
- 來源：https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf ；https://blog.codinghorror.com/code-smells/

### Complicated Boolean Expression（複雜布林運算式）— Wake
- 別名：—
- 定義：一個條件由多個 &&、||、! 組成，很難一眼判斷什麼時候成立（推論，Wake 原文未查證）。
- 辨識訊號：多層否定、&& 與 || 混用（推論）。
- 為何有害：容易判斷錯，修改時容易出錯（推論）。
- 常見解法：Decompose Conditional、Consolidate Conditional Expression，或用 Extract Variable／Extract Function 替子條件命名（對應關係為推論）
- 何時不算：未查證。
- 來源：歸類 https://sape.inf.usi.ch/essence/algorithmic/smells.html ；「Wake 新增」https://dev.to/trikitrok/on-code-smells-catalogues-and-taxonomies-3ba6 。**Wake 原文未查證。**

### Null Check（空值檢查）— Wake
- 別名：Nil Check（搜尋結果中出現的寫法）
- 定義：程式裡到處是 `if (x == null)` 這類判斷（推論，Wake 原文未查證）。
- 辨識訊號：同一個物件的 null 檢查在多處重複（推論）。
- 為何有害：重複，而且漏一處就會出現空參照錯誤（推論）。
- 常見解法：Introduce Special Case（F1 名 Introduce Null Object：方法不回傳 null，改回傳一個具備預設行為的「空物件」，藉此消掉大量 null 檢查）
- 何時不算：未查證。
- 來源：歸類 https://sape.inf.usi.ch/essence/algorithmic/smells.html ；手法改名 https://martinfowler.com/articles/refactoring-2nd-changes.html 。**Wake 原文未查證。**

### Special Case（特殊情況）— Wake
- 別名：—
- 定義：主邏輯前面插入檢查特定值的 if，專門處理例外情況（推論，Wake 原文未查證）。
- 辨識訊號：未查證。
- 為何有害：未查證。
- 常見解法：Replace Nested Conditional with Guard Clauses、Introduce Special Case、Replace Conditional with Polymorphism（推論）
- 何時不算：未查證。
- 來源：歸類 https://sape.inf.usi.ch/essence/algorithmic/smells.html 。**除了名稱與歸類之外都未查證。**

### D. 物件導向誤用（Object-Orientation Abusers）

### Temporary Field（臨時欄位）
- 別名：—
- 定義：類別裡有些欄位只在特定情況下才有值，其他時候都是空的。
- 辨識訊號：
  - [RG／IL] 欄位只在某個演算法執行期間被設定。常見原因是為了避免參數列過長，把參數升格成欄位。
  - [M06] 本該屬於方法範圍的變數，被放到了類別範圍。
- 為何有害：[F2] 讀者會預期物件需要它所有的欄位。
- 常見解法：Extract Class（把這些欄位和相關程式碼搬出去）、Move Function、Introduce Special Case
- 何時不算：來源沒有列出。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=16 ；https://refactoring.guru/smells/temporary-field

### Refused Bequest（被拒絕的遺贈）
- 別名：—
- 定義：子類別繼承了父類別的方法與資料，卻用不到或不想要。
- 辨識訊號：
  - [RG] 子類別只用到部分繼承來的成員；繼承來的方法被覆寫成空的，或改成丟例外。
  - [MT] AIUR（平均繼承使用比率）低於 1。
- 為何有害：代表繼承階層不對。味道強的時候，子類別只想重用實作，卻不想支援父類別的介面，等於破壞了「子類別可以替換父類別」的前提（推論）。
- 常見解法：Push Down Method、Push Down Field、Replace Subclass with Delegate、Replace Superclass with Delegate（F1 名 Replace Inheritance with Delegation）；RG 另列 Extract Superclass
- 何時不算：[F2] 「十次有九次，這個味道淡到不值得清理」。只有在子類別重用了行為、**卻拒絕支援父類別介面**時，味道才強。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=23 ；https://refactoring.guru/smells/refused-bequest

### Alternative Classes with Different Interfaces（異曲同工的類別）
- 別名：—
- 定義：兩個類別做類似的事，但介面（方法名、參數）不同，所以不能互相替換。
- 辨識訊號：[RG] 兩個類別功能相同，方法名稱不同。
- 為何有害：[F2] 類別最大的好處之一是可以替換使用，但前提是介面一致。
- 常見解法：Change Function Declaration（先統一簽章）、Move Function、Extract Superclass（出現重複時）；K 另列 Unify Interfaces with Adapter
- 何時不算：[RG] 合併做不到或代價過高時，例如兩個類別分屬不同的函式庫，各有自己的版本。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=21 ；https://refactoring.guru/smells/alternative-classes-with-different-interfaces

### E. 變更阻礙（Change Preventers）

### Divergent Change（發散式變化）
- 別名：—
- 定義：同一個模組會因為**不同的理由**被修改。
- 辨識訊號：
  - [F2] 換資料庫要改這三個函式，加一種新金融商品要改那四個函式，而它們都在同一個模組裡。
  - [RG] 加一種新產品型別時，得改搜尋、顯示、下單等互不相關的方法。
- 為何有害：改其中一個面向時，得先看懂不相關的另一個面向。[M06] 違反「類別與可能的變更一對一」。
- 常見解法：Split Phase（兩個面向有先後順序時）、Move Function、Extract Function、Extract Class；RG 另列 Extract Superclass、Extract Subclass
- 何時不算：[F2] 程式早期的情境邊界（context boundary，也就是哪些事屬於同一塊）通常不清楚，而且會隨功能變化而移動，常常要加過幾個資料庫或商品之後才看得出來。
- 與 Shotgun Surgery 的關係：方向相反。Divergent Change 是「一處被多種變更拉扯」，Shotgun Surgery 是「一個變更要動多處」。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=7 ；https://refactoring.guru/smells/divergent-change

### Shotgun Surgery（霰彈式修改）
- 別名：—
- 定義：做一個變更，得在很多不同的類別裡各改一點。
- 辨識訊號：
  - 一次需求變更，會碰到大量檔案、每個檔案改一點。
  - [MT] CM（依賴它、因而得跟著改的外部方法數）在全系統前 20% 且超過 10，而且這些方法分屬超過 5 個類別（ChC）。
- 為何有害：[F2] 改動散落各處，很難找齊，容易漏改。
- 常見解法：Move Function、Move Field、Combine Functions into Class、Combine Functions into Transform、Split Phase、Inline Function、Inline Class
- 何時不算／注意：[F2] 可以先把東西內聯成一大塊當中間步驟，再重新切分。「我們雖然偏愛小函式小類別，但不怕在重組過程中先做出大東西。」
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=8 ；https://refactoring.guru/smells/shotgun-surgery

### Parallel Inheritance Hierarchies（平行繼承體系）— F1，F2 已移除
- 別名：—
- 定義：每次替某個類別加子類別，就得替另一個類別也加一個對應的子類別。
- 辨識訊號：[RG] 原句：「每替一個類別建子類別，就發現也得替另一個類別建子類別。」
- 為何有害：[F1，經 IL] 這其實是 Shotgun Surgery 的特例。[M06] 本質上是重複的類別階層。
- 常見解法：[RG／IL] 讓一個階層的實例去參照另一個階層的實例，再用 Move Function／Move Field（F1 名 Move Method）消掉被參照的那個階層
- 何時不算：[RG] 有時保留平行階層，是為了避免更糟架構的務實選擇。如果合併後程式碼反而更醜，就退回原樣。
- F2 移除理由：未查證。
- 來源：https://refactoring.guru/smells/parallel-inheritance-hierarchies ；[IL] 同上

### Combinatorial Explosion（組合爆炸）— Wake、Kerievsky
- 別名：—
- 定義：[K] 一種不明顯的重複：許多段程式碼做同一件事，差別只在資料或行為的組合不同。
- 辨識訊號：
  - Coding Horror：很多程式碼做「幾乎」一樣的事，只有資料或行為上的細微差異。
  - 每多一個維度（例如「格式 × 輸出目標」），就得新增好幾個幾乎一樣的方法或類別（例子為推論）。
- 為何有害：重複的量會隨組合數相乘成長。
- 常見解法：[K] Replace Implicit Language with Interpreter
- 何時不算：來源沒有列出。
- 來源：https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf ；https://sape.inf.usi.ch/essence/algorithmic/smells.html ；https://blog.codinghorror.com/code-smells/

### Solution Sprawl（解法蔓延）— Kerievsky
- 別名：—
- 定義：完成某一項職責所需的程式碼或資料，散落在許多類別裡。
- 辨識訊號：
  - [K] 常見於快速加功能，卻沒花時間把設計簡化、整合。
  - Coding Horror：「如果要五個類別才能做成一件有用的事，可能就是 Solution Sprawl。」
- 為何有害：理解或修改一項職責，都得跨好幾個類別（推論）。
- 常見解法：[K] Move Creation Knowledge to Factory
- 何時不算：來源沒有列出。
- 來源：https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf ；https://blog.codinghorror.com/code-smells/

### F. 可有可無（Dispensables）

### Duplicated Code（重複程式碼）
- 別名：Duplicate Code（RG、M）
- 定義：相同或相似的程式碼結構出現在不只一個地方。
- 辨識訊號：
  - [F2] 三種情形：同一個類別的兩個函式有相同的運算式；程式碼相似但不完全相同；兄弟子類別之間有重複。
  - [IL] 分兩種：明顯重複（程式碼完全相同），以及不明顯的重複（外觀不同、本質相同的結構或步驟）。
- 為何有害：讀者得比對其中的細微差異；改一處要記得改所有地方。[F1／K] 稱它是「最普遍也最刺鼻的味道」。
- 常見解法：Extract Function、Slide Statements（先把相似的部分排在一起）、Pull Up Method；RG 另列 Pull Up Field、Pull Up Constructor Body、Form Template Method、Substitute Algorithm、Extract Superclass、Extract Class、Consolidate Conditional Expression
- 何時不算：
  - [RG] 「極少數情況下」，把兩段相同的程式碼合併，反而讓程式更不直觀。
  - （推論）文字相似、但會因為不同理由各自變動的程式碼，硬合併會製造出 Divergent Change。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=2 ；https://refactoring.guru/smells/duplicate-code

### Lazy Element（冗贅的元素）
- 別名：Lazy Class（F1、RG、M、W）、Freeloader（K）
- 定義：函式或類別存在，卻沒貢獻足夠的價值。
- 辨識訊號：
  - [F2] 函式名稱和它的程式碼讀起來幾乎一樣；類別其實只是一個簡單的函式；當初預期會長大，結果沒有長大。
  - [RG] 重構之後變得太小的類別。
- 為何有害：[RG] 理解和維護每一個類別都要花時間和成本。
- 常見解法：Inline Function、Inline Class、Collapse Hierarchy
- 何時不算：[RG] 有時會刻意建一個小類別，用來標示未來開發的意圖。這時要在清楚與簡單之間取得平衡。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=14 ；https://refactoring.guru/smells/lazy-class

### Speculative Generality（誇誇其談通用性）
- 別名：RG 簡中站譯「冗餘通用化」
- 定義：為了「將來也許用得到」而加的掛鉤、特例、抽象層，現在卻沒有用到。
- 辨識訊號：
  - [F2] 函式或類別唯一的使用者是測試；有沒用到的參數。
  - [RG] 存在沒用到的類別、方法、欄位、參數。
- 為何有害：[F2] 「這些機制如果都有被用到，就值得；沒有，就不值得。」只會讓程式更難懂、更難維護。
- 常見解法：Collapse Hierarchy、Inline Function、Inline Class、Change Function Declaration（拿掉多餘參數）、Remove Dead Code
- 何時不算：
  - [RG] 寫框架時，提供框架本身不用、但使用者會用的功能是合理的。
  - [RG] 刪除前先確認單元測試沒有拿它來存取內部資訊。
  - 兩家看法有差：F2 主張「只有測試在用」就把測試一起刪掉；RG 提醒先確認測試是不是刻意依賴它。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=15 ；https://refactoring.guru/smells/speculative-generality

### Data Class（純資料類別）
- 別名：—
- 定義：只有欄位和 getter／setter、沒有任何行為的類別。
- 辨識訊號：
  - [F2] 它的 getter／setter 被其他類別大量使用，代表行為放錯了地方。
  - [MT] WOC（類別中「提供功能」的公開方法比例）低於 33%，並且公開欄位超過 5 個或存取方法超過 5 個。
- 為何有害：[IL／F1] 幾乎必然被其他類別以過細的方式操弄；行為散落在各個呼叫端。
- 常見解法：Encapsulate Record、Remove Setting Method、Move Function（把呼叫端的行為搬進來）、Extract Function、Split Phase；RG 另列 Encapsulate Field（F2 名 Encapsulate Variable）、Encapsulate Collection、Hide Method
- 何時不算：[F2] 作為一次函式呼叫結果的**不可變**記錄是合理的例外，例如 Split Phase 兩個階段之間傳遞的資料。不可變的欄位不需要封裝。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=22 ；https://refactoring.guru/smells/data-class ；[MT] 同上

### Dead Code（死碼）— Wake、RG、M06
- 別名：—
- 定義：已經不再被使用的變數、參數、欄位、方法或類別。
- 辨識訊號：
  - [RG] 需求變更或修正後，留下了沒用的程式碼。
  - [RG] 複雜條件式中，永遠走不到的分支。
- 為何有害：[M06] Dispensables 這一組的共同點就是：該從原始碼中刪掉。
- 常見解法：直接刪除（F2 手法名 Remove Dead Code）；沒用到的子類別或父類別用 Inline Class／Collapse Hierarchy；沒用到的參數用 Change Function Declaration（F1 名 Remove Parameter）
- 何時不算：
  - Coding Horror：放心刪，版本控制系統裡還有紀錄。
  - （推論）對外公開的 API，或透過反射、設定檔動態呼叫的程式碼，看起來沒人用，其實有人用。
- 來源：https://refactoring.guru/smells/dead-code ；https://blog.codinghorror.com/code-smells/

### Oddball Solution（異類解法）— Kerievsky
- 別名：—
- 定義：[K] 同一個問題，系統裡大多用一種方式解決，卻有一處用了另一種方式；那個少數的就是異類。
- 辨識訊號：Coding Horror：「程式中同一個問題應該只有一種解法。」
- 為何有害：[K] 通常代表背後有不明顯的重複程式碼。
- 常見解法：[K] Unify Interfaces with Adapter（先統一介面，再淘汰異類）
- 何時不算：來源沒有列出。
- 來源：https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf ；https://blog.codinghorror.com/code-smells/

### G. 耦合（Couplers）

### Feature Envy（依戀情結）
- 別名：RG 簡中站譯「特性嫉妒」
- 定義：一個函式跟別的模組的函式或資料互動，比跟自己模組裡的還多。
- 辨識訊號：
  - [RG] 方法存取別的物件的資料，比存取自己的還多。
  - [MT] 存取外部資料（AID）超過 4 且在全系統前 10%；存取自己的資料（ALD）少於 3；外部資料來自少於 3 個類別（NIC）。
- 為何有害：資料和處理它的行為應該放在一起，分開的話，改動就得跨模組進行。
- 常見解法：Move Function（搬到資料所在的地方）、Extract Function（只有一部分在依戀時，先抽出來再搬）。原則是搬到「它用最多資料」的那個模組。
- 何時不算：
  - [F2] Strategy、Visitor、Self Delegation 這些設計模式，會刻意把行為和資料分開，用來對抗 Divergent Change。根本原則是「會一起變動的放在一起」。
  - [RG] 刻意分開是為了能動態切換行為。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=9 ；https://refactoring.guru/smells/feature-envy ；[MT] 同上

### Insider Trading（內幕交易）
- 別名：Inappropriate Intimacy（F1、RG、M、W；RG 簡中站譯「不恰當的親密關係」；F1 繁中版譯「狎暱關係」，譯名未查證）
- 定義：模組之間私下交換大量資料，彼此依賴對方的內部細節。
- 辨識訊號：
  - [RG] 一個類別使用另一個類別內部的欄位和方法。
  - [F2] 子類別對父類別知道得太多。
- 為何有害：耦合太高，改一邊就會牽動另一邊。[F2]：「在咖啡機旁竊竊私語的模組，需要被拆開。」
- 常見解法：Move Function、Move Field、Hide Delegate、Replace Subclass with Delegate、Replace Superclass with Delegate；F1／RG 另列 Change Bidirectional Association to Unidirectional、Extract Class
- 何時不算：[F2] 「某些交流免不了，但要壓到最低。」子類別本來就會比父類別希望的多知道一些。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=19 ；https://refactoring.guru/smells/inappropriate-intimacy

### Message Chains（過長的訊息鏈）
- 別名：—
- 定義：呼叫端向 A 要 B、再向 B 要 C、再向 C 要 D……一路串下去才拿到想要的東西。
- 辨識訊號：`a.getB().getC().getD().getData()` 這種寫法，或一長串暫存變數（[IL]）。
- 為何有害：
  - [F2] 呼叫端被綁死在這條導航結構上，中間任何一層關係改變，呼叫端都得跟著改。
  - [M06] A 只需要 D 的資料，卻和 B、C、D 都耦合在一起。
- 常見解法：Hide Delegate；或 Extract Function＋Move Function：先看最後拿到的物件被拿來做什麼，再把那段程式碼往鏈的下游搬
- 何時不算：
  - [F2] 「有人認為任何方法鏈都很糟，而我們以冷靜、講理、溫和著稱。」如果每個中間物件都套 Hide Delegate，它們會全部變成 Middle Man。RG 也這麼說。
  - （推論）流暢介面（fluent interface，方法回傳自己以便連續呼叫）、builder、對同一型別串接的 pipeline（例如 `stream.filter().map()`），都不是在導航物件結構。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=17 ；https://refactoring.guru/smells/message-chains

### Middle Man（中間人）
- 別名：—
- 定義：一個類別大部分的方法，都只是把呼叫轉給另一個類別。
- 辨識訊號：[F2] 類別介面大約一半的方法都在委託給別的類別。
- 為何有害：封裝做過頭，多了一層間接卻沒有增加價值。[M06] 這是為了避免耦合而過度委託造成的反向問題。
- 常見解法：
  - Remove Middle Man。
  - Inline Function：只有少數方法在純轉手時用。
  - Replace Superclass with Delegate／Replace Subclass with Delegate：中間人另外還有自己的行為時用。
  - F1／IL 另列 Replace Delegation with Inheritance。
- 何時不算：
  - [RG] 刻意加進來，用來避免類別之間互相依賴的中間人。
  - [RG] Proxy、Decorator 等設計模式本來就會刻意製造中間人。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=18 ；https://refactoring.guru/smells/middle-man

### Incomplete Library Class（不完美的程式庫類別）— F1，F2 已移除
- 別名：—
- 定義：需要的功能，函式庫的類別沒有提供，而你又沒辦法或不願意去改函式庫。
- 辨識訊號：
  - [RG] 函式庫遲早會不符需求，而函式庫通常是唯讀的。
  - [IL／F1] 自己的程式碼裡，出現了明顯應該屬於函式庫類別的職責。
- 為何有害：補功能的程式碼散落在各個呼叫端（推論）。
- 常見解法：Introduce Foreign Method、Introduce Local Extension（都是 F1 的手法；F2 是否收錄未查證）
- 何時不算：
  - [RG] 如果擴充函式庫會牽動到程式碼的修改，可能帶來額外工作。
  - （推論）現代語言的 extension method（擴充方法）讓這個問題比較少見。
- 來源：https://refactoring.guru/smells/incomplete-library-class ；[IL] 同上

### Indecent Exposure（不當暴露）— Kerievsky
- 別名：—
- 定義：[K] 不該讓呼叫端看到的方法或類別被公開了，也就是缺少 Parnas 提出的資訊隱藏。
- 辨識訊號：Coding Horror：類別不必要地暴露內部，應該積極縮小它的公開介面。
- 為何有害：[K] 呼叫端會知道一些不重要、或只是間接相關的程式碼，讓設計變複雜。
- 常見解法：[K] Encapsulate Classes with Factory；用 Hide Method 縮小可見性（推論）
- 何時不算：來源沒有列出。
- 來源：https://courses.cs.duke.edu/compsci308/fall19/resources/smellstorefactorings.pdf ；https://blog.codinghorror.com/code-smells/

### H. 共享狀態

### Global Data（全域資料）
- 別名：—
- 定義：程式任何地方都能讀寫的資料，包括全域變數、類別變數（static）、Singleton。
- 辨識訊號：資料可以從任何地方被修改，而且查不出是誰改的。
- 為何有害：[F2] 「毒藥和良藥的差別在劑量」：少量還能控制，量一多，難度就急遽上升，bug 很難追。
- 常見解法：Encapsulate Variable（F1 名 Self Encapsulate Field）：先包起來控制存取，再縮小範圍，搬進類別或模組
- 何時不算：[F2] 程式啟動後就不再改變的資料相對安全，前提是語言能強制保證它不可變。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=5

### Mutable Data（可變資料）
- 別名：—
- 定義：資料在一處被更新後，另一處的程式碼沒料到這件事。
- 辨識訊號：
  - 同一個變數被重新賦值，拿去做不同的用途。
  - 可以從其他資料推導出來的值，卻另外存一份並自行更新（[F2] 說這種「特別刺鼻」）。
  - 變數的作用範圍很大。
- 為何有害：[F2] 資料一變動，常帶來意想不到的後果和難追的 bug。函數式程式設計就是靠不可變性來避開這些問題。
- 常見解法：Encapsulate Variable、Split Variable、Slide Statements、Extract Function、Separate Query from Modifier、Remove Setting Method、Replace Derived Variable with Query、Combine Functions into Class、Combine Functions into Transform、Change Reference to Value
- 何時不算：[F2] 作用範圍只有幾行的可變變數不是什麼大問題，風險隨範圍擴大而升高。
- 來源：https://www.informit.com/articles/article.aspx?p=2952392&seqNum=6

---

## 4. 重構手法中譯對照（第 2 版名稱）

譯名依簡中第 2 版轉成繁體，已對照 https://www.cnblogs.com/loveshes/p/17367886.html 。

| 英文 | 中譯 | 英文 | 中譯 |
|---|---|---|---|
| Change Function Declaration | 改變函式宣告 | Rename Variable／Rename Field | 變數改名／欄位改名 |
| Extract Function | 提煉函式 | Slide Statements | 移動語句 |
| Pull Up Method | 函式上移 | Push Down Method／Field | 函式下移／欄位下移 |
| Replace Temp with Query | 以查詢取代臨時變數 | Replace Parameter with Query | 以查詢取代參數 |
| Introduce Parameter Object | 引入參數物件 | Preserve Whole Object | 保持物件完整 |
| Encapsulate Variable | 封裝變數 | Split Variable | 拆分變數 |
| Split Phase | 拆分階段 | Move Function／Move Field | 搬移函式／搬移欄位 |
| Extract Class | 提煉類別 | Extract Superclass | 提煉超類別 |
| Combine Functions into Class | 函式組合成類別 | Replace Primitive with Object | 以物件取代基本型別 |
| Replace Type Code with Subclasses | 以子類別取代型別碼 | Replace Conditional with Polymorphism | 以多型取代條件式 |
| Replace Loop with Pipeline | 以管道取代迴圈 | Inline Function／Inline Class | 內聯函式／內聯類別 |
| Collapse Hierarchy | 折疊繼承體系 | Introduce Special Case | 引入特例 |
| Hide Delegate | 隱藏委託關係 | Remove Middle Man | 移除中間人 |
| Replace Superclass with Delegate | 以委託取代超類別 | Replace Subclass with Delegate | 以委託取代子類別 |
| Encapsulate Record | 封裝記錄 | Remove Setting Method | 移除設值函式 |
| Introduce Assertion | 引入斷言 | | |

第 1 版 → 第 2 版的手法改名（完整清單見 https://martinfowler.com/articles/refactoring-2nd-changes.html ）：

| 第 1 版 | 第 2 版 |
|---|---|
| Extract Method | Extract Function |
| Inline Method | Inline Function |
| Move Method | Move Function |
| Rename Method／Add Parameter／Remove Parameter | Change Function Declaration |
| Replace Method with Method Object | Replace Function with Command |
| Replace Parameter with Method | Replace Parameter with Query |
| Replace Parameter with Explicit Methods | Remove Flag Argument |
| Introduce Null Object | Introduce Special Case |
| Replace Data Value with Object／Replace Type Code with Class | Replace Primitive with Object |
| Replace Magic Number with Symbolic Constant | Replace Magic Literal |
| Self Encapsulate Field | Encapsulate Variable |
| Split Temporary Variable／Remove Assignments to Parameters | Split Variable |
| Consolidate Duplicate Conditional Fragments | Slide Statements |
| Extract Subclass | Replace Type Code with Subclasses |
| Replace Subclass with Fields | Remove Subclass |
| Replace Record with Data Class | Encapsulate Record |

---

## 5. 查證狀態

**已查證（有一手來源或可靠的二手來源）**
- Fowler 第 2 版 24 個味道：逐條讀過原書第 3 章摘錄（informit，24 頁），包括每條的建議手法與例外說明。
- Refactoring Guru 23 個味道：讀過分類頁，並逐條讀過各頁的徵兆、解法、何時忽略。
- Mäntylä 2006 版 5 組：讀過網頁存檔的原文。
- Kerievsky 的 5 個新味道：讀過 Industrial Logic 速查表的原文。
- [MT] 門檻：讀過 Yamashita & Moonen 2012 附錄 A 的原文。

**僅有二手來源**
- Fowler 第 1 版 → 第 2 版的增刪改名清單（dev.to）。
- Mäntylä 2003 版的 Encapsulators／Others 兩組成員（dev.to＋arXiv 綜述），原論文全文沒有取得。
- Wake 的子類成員歸屬（sape.inf.usi.ch）。

**未查證**
- Wake 原書對 Null Check、Special Case、Complicated Boolean Expression、Magic Number、Type Embedded in Name、Inconsistent Names 的定義、門檻與建議手法。本文這些欄位大多標了推論；**Special Case 除了名稱與歸類之外全部未查證**。
- Parallel Inheritance Hierarchies 與 Incomplete Library Class 在第 2 版被移除的理由。
- Introduce Foreign Method／Introduce Local Extension 是否收錄於第 2 版。
- 第 1 版繁中版的味道譯名（例如「狎暱關係」）。
- 標了「（推論）」的例外與例子。
