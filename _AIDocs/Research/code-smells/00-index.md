# 全條目速查索引

> 由各分支檔自動抽出「條目名＋一句定義」。查法：Ctrl+F／grep 英文名或中文名 → 到該檔搜同一個標題讀全文（辨識訊號、何時不算、解法、來源都在那裡）。
> 同一個味道可能在多個分支各有一條，各自從不同尺度或語言切入；主條目歸屬見 README「重疊對照」。
> 共 513 條。

## [經典程式碼層](01-classic-catalog.md)（38 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Long Function（過長函式） | 一個函式長到要從頭讀完，才知道它在做什麼。 | A. 膨脹（Bloaters） |
| Large Class（過大的類別） | 一個類別想做太多事。 | A. 膨脹（Bloaters） |
| Long Parameter List（過長參數列） | 函式的參數多到難以理解。 | A. 膨脹（Bloaters） |
| Primitive Obsession（基本型別偏執） | 用 int、string、float 這類基本型別，表示有意義的領域概念，例如金額、座標、電話、範圍。 | A. 膨脹（Bloaters） |
| Data Clumps（資料泥團） | 同一組資料總是一起出現（當欄位、當參數），卻沒有包成一個物件。 | A. 膨脹（Bloaters） |
| Mysterious Name（神祕命名） | 函式、模組、變數、類別的名字，沒辦法讓人一看就懂它做什麼、怎麼用。 | B. 命名與表達 |
| Type Embedded in Name（名稱內嵌型別）— Wake | 把型別寫進名字裡，例如 `nameString`、`strName`、`getUserList`（例子為推論）。 | B. 命名與表達 |
| Inconsistent Names（命名不一致）— Wake | 同一個概念在不同地方用不同的詞，例如 fetch、get、retrieve 混用（例子為推論）。 | B. 命名與表達 |
| Magic Number（魔術數字）— Wake | 程式碼裡直接出現沒有名字的字面常數，讀者看不出它的含義。 | B. 命名與表達 |
| Comments（註解） | 用註解遮蓋寫得不好的程式碼。註解本身不是壞事，壞的是「要靠註解才看得懂」的程式碼。 | B. 命名與表達 |
| Repeated Switches（重複的 switch） | 同一組按型別或狀態分派的 switch（或 if-else 串），在多處重複出現。 | C. 條件與流程 |
| Loops（迴圈） | 用傳統 for／while 迴圈處理集合，但語言已經有 pipeline（filter／map／reduce 這類串接操作）可以用。 | C. 條件與流程 |
| Conditional Complexity（條件複雜度）— Kerievsky | 條件邏輯隨著功能增加，變得又大又亂。 | C. 條件與流程 |
| Complicated Boolean Expression（複雜布林運算式）— Wake | 一個條件由多個 &&、／／、! 組成，很難一眼判斷什麼時候成立（推論，Wake 原文未查證）。 | C. 條件與流程 |
| Null Check（空值檢查）— Wake | 程式裡到處是 `if (x == null)` 這類判斷（推論，Wake 原文未查證）。 | C. 條件與流程 |
| Special Case（特殊情況）— Wake | 主邏輯前面插入檢查特定值的 if，專門處理例外情況（推論，Wake 原文未查證）。 | C. 條件與流程 |
| Temporary Field（臨時欄位） | 類別裡有些欄位只在特定情況下才有值，其他時候都是空的。 | D. 物件導向誤用（Object-Orientation … |
| Refused Bequest（被拒絕的遺贈） | 子類別繼承了父類別的方法與資料，卻用不到或不想要。 | D. 物件導向誤用（Object-Orientation … |
| Alternative Classes with Different Interfaces（異曲同工的類別） | 兩個類別做類似的事，但介面（方法名、參數）不同，所以不能互相替換。 | D. 物件導向誤用（Object-Orientation … |
| Divergent Change（發散式變化） | 同一個模組會因為**不同的理由**被修改。 | E. 變更阻礙（Change Preventers） |
| Shotgun Surgery（霰彈式修改） | 做一個變更，得在很多不同的類別裡各改一點。 | E. 變更阻礙（Change Preventers） |
| Parallel Inheritance Hierarchies（平行繼承體系）— F1，F2 已移除 | 每次替某個類別加子類別，就得替另一個類別也加一個對應的子類別。 | E. 變更阻礙（Change Preventers） |
| Combinatorial Explosion（組合爆炸）— Wake、Kerievsky | [K] 一種不明顯的重複：許多段程式碼做同一件事，差別只在資料或行為的組合不同。 | E. 變更阻礙（Change Preventers） |
| Solution Sprawl（解法蔓延）— Kerievsky | 完成某一項職責所需的程式碼或資料，散落在許多類別裡。 | E. 變更阻礙（Change Preventers） |
| Duplicated Code（重複程式碼） | 相同或相似的程式碼結構出現在不只一個地方。 | F. 可有可無（Dispensables） |
| Lazy Element（冗贅的元素） | 函式或類別存在，卻沒貢獻足夠的價值。 | F. 可有可無（Dispensables） |
| Speculative Generality（誇誇其談通用性） | 為了「將來也許用得到」而加的掛鉤、特例、抽象層，現在卻沒有用到。 | F. 可有可無（Dispensables） |
| Data Class（純資料類別） | 只有欄位和 getter／setter、沒有任何行為的類別。 | F. 可有可無（Dispensables） |
| Dead Code（死碼）— Wake、RG、M06 | 已經不再被使用的變數、參數、欄位、方法或類別。 | F. 可有可無（Dispensables） |
| Oddball Solution（異類解法）— Kerievsky | [K] 同一個問題，系統裡大多用一種方式解決，卻有一處用了另一種方式；那個少數的就是異類。 | F. 可有可無（Dispensables） |
| Feature Envy（依戀情結） | 一個函式跟別的模組的函式或資料互動，比跟自己模組裡的還多。 | G. 耦合（Couplers） |
| Insider Trading（內幕交易） | 模組之間私下交換大量資料，彼此依賴對方的內部細節。 | G. 耦合（Couplers） |
| Message Chains（過長的訊息鏈） | 呼叫端向 A 要 B、再向 B 要 C、再向 C 要 D……一路串下去才拿到想要的東西。 | G. 耦合（Couplers） |
| Middle Man（中間人） | 一個類別大部分的方法，都只是把呼叫轉給另一個類別。 | G. 耦合（Couplers） |
| Incomplete Library Class（不完美的程式庫類別）— F1，F2 已移除 | 需要的功能，函式庫的類別沒有提供，而你又沒辦法或不願意去改函式庫。 | G. 耦合（Couplers） |
| Indecent Exposure（不當暴露）— Kerievsky | [K] 不該讓呼叫端看到的方法或類別被公開了，也就是缺少 Parnas 提出的資訊隱藏。 | G. 耦合（Couplers） |
| Global Data（全域資料） | 程式任何地方都能讀寫的資料，包括全域變數、類別變數（static）、Singleton。 | H. 共享狀態 |
| Mutable Data（可變資料） | 資料在一處被更新後，另一處的程式碼沒料到這件事。 | H. 共享狀態 |

## [設計與架構層](02-design-architecture.md)（77 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Missing Abstraction（缺失抽象） | 該有自己的類別或介面的概念，卻用一團資料或編碼過的字串代替。 | A1 抽象類（Abstraction smells） |
| Imperative Abstraction（命令式抽象） | 把一個「操作」做成一個類別。 | A1 抽象類（Abstraction smells） |
| Incomplete Abstraction（不完整抽象） | 抽象沒有完整提供一個責任所需的方法，特別是缺了成對或互補的方法。 | A1 抽象類（Abstraction smells） |
| Multifaceted Abstraction（多面向抽象） | 一個抽象被指派了不只一個責任。 | A1 抽象類（Abstraction smells） |
| Unnecessary Abstraction（多餘抽象） | 設計裡引入了實際上不需要（本來可以避免）的抽象。 | A1 抽象類（Abstraction smells） |
| Unutilized Abstraction（未使用抽象） | 抽象沒有被使用（沒有被直接使用，或從入口走不到）。 | A1 抽象類（Abstraction smells） |
| Duplicate Abstraction（重複抽象） | 兩個以上的抽象名稱相同、實作相同，或兩者都相同。 | A1 抽象類（Abstraction smells） |
| Deficient Encapsulation（封裝不足） | 抽象中一或多個成員宣告的可見度，比實際需要的更寬。 | A2 封裝類（Encapsulation smells） |
| Leaky Encapsulation（洩漏式封裝） | 抽象透過公開介面「洩漏」了實作細節。 | A2 封裝類（Encapsulation smells） |
| Missing Encapsulation（缺失封裝） | 實作上的變化點（variation）沒有被包進一個抽象或階層裡。 | A2 封裝類（Encapsulation smells） |
| Unexploited Encapsulation（未善用封裝） | 繼承階層裡已經封裝好型別差異，呼叫端卻還用明確的型別檢查（if-else 鏈或 switch 判斷物件型別）自己分派。 | A2 封裝類（Encapsulation smells） |
| Broken Modularization（破碎模組化） | 本該集中在同一個抽象裡的資料和／或方法，被拆散到多個抽象中。 | A3 模組化類（Modularization smells） |
| Insufficient Modularization（模組化不足） | 抽象還沒有被充分分解；再分解可以縮小介面、降低實作複雜度，或兩者都降。 | A3 模組化類（Modularization smells） |
| Cyclically-dependent Modularization（循環依賴模組化） | 兩個以上的抽象直接或間接互相依賴。 | A3 模組化類（Modularization smells） |
| Hub-like Modularization（樞紐式模組化） | 抽象同時有大量的傳入與傳出依賴。 | A3 模組化類（Modularization smells） |
| Missing Hierarchy（缺失階層） | 用條件邏輯明確管理行為上的變化，而這些變化本來可以建一個階層來封裝。 | A4 階層類（Hierarchy smells） |
| Unnecessary Hierarchy（多餘階層） | 整個繼承階層都不需要——在這個情境下用繼承是多此一舉。ICSE 教程列了三種情況：所有子型別都不必要（繼承用錯）、父型別只有一個子型別（臆測式一般化）、中間型別不必要。 | A4 階層類（Hierarchy smells） |
| Unfactored Hierarchy（未提煉階層） | 階層內的型別之間有不必要的重複，分兩種：兄弟型別之間、父子型別之間。 | A4 階層類（Hierarchy smells） |
| Wide Hierarchy（過寬階層） | 繼承階層「太寬」，暗示中間型別可能缺了。 | A4 階層類（Hierarchy smells） |
| Speculative Hierarchy（臆測式階層） | 階層中有一或多個型別，是根據想像的需求而不是真實的需求加上去的。 | A4 階層類（Hierarchy smells） |
| Deep Hierarchy（過深階層） | 繼承階層「過度」地深。 | A4 階層類（Hierarchy smells） |
| Rebellious Hierarchy（叛逆階層） | 子型別拒絕父型別提供的方法。 | A4 階層類（Hierarchy smells） |
| Broken Hierarchy（斷裂階層） | 父型別和子型別在概念上不是 IS-A（「是一種」）關係，可替換性因此被破壞；通常是該用組合的地方用了繼承。 | A4 階層類（Hierarchy smells） |
| Multipath Hierarchy（多路徑階層） | 子型別同時直接和間接繼承同一個父型別，在階層中多出不必要的繼承路徑。 | A4 階層類（Hierarchy smells） |
| Cyclic Hierarchy（循環階層） | 階層中的父型別依賴自己的任何一個子型別。 | A4 階層類（Hierarchy smells） |
| Rigidity（僵化） | 系統很難改，因為每改一處都會逼出許多其他改動（Martin 2000：每個改動都在依賴模組間引發一連串後續修改）。 | B. 設計腐化徵兆（Robert C. Martin） |
| Fragility（脆弱） | 每次修改都會在許多地方壞掉，而且常壞在和修改處沒有概念關係的區域。 | B. 設計腐化徵兆（Robert C. Martin） |
| Immobility（不可移植性；難以重用） | 很難把系統拆成能在其他系統（或同系統的新版本）重用的元件。Martin：需要的模組常拖著太多依賴的「包袱」，拆出來的工作和風險太大，最後只好重寫，而不是重用。 | B. 設計腐化徵兆（Robert C. Martin） |
| Viscosity（黏滯） | 做對的事比做錯的事更難。分兩種： | B. 設計腐化徵兆（Robert C. Martin） |
| Needless Complexity（不必要的複雜） | 設計中含有不帶來直接效益的基礎設施。 | B. 設計腐化徵兆（Robert C. Martin） |
| Needless Repetition（不必要的重複） | 設計中有可以統一在單一抽象下的重複結構。 | B. 設計腐化徵兆（Robert C. Martin） |
| Opacity（晦澀） | 程式碼很難讀、很難懂，沒有好好表達意圖。 | B. 設計腐化徵兆（Robert C. Martin） |
| SRP Violation（違反單一職責原則） | Martin 的表述是「把因相同理由而變的東西放在一起，把因不同理由而變的東西分開」，這裡的「理由」指**人**，也就是不同的角色或需求方（actor）。違反 = 一個模組同時服… | C. SOLID 違反 |
| OCP Violation（違反開放封閉原則） | OCP =「模組應該對擴充開放、對修改封閉」。違反 = 每加一種新變體，都得修改既有模組的原始碼。 | C. SOLID 違反 |
| LSP Violation（違反里氏替換原則） | LSP =「子類別應該能替換它的基底類別」：接受 Base 的函式，傳入 Derived 也要正常運作。 | C. SOLID 違反 |
| ISP Violation（違反介面隔離原則） | ISP =「多個客戶端專屬的介面，勝過一個通用介面」。違反 = 胖介面（fat interface）：一個類別有多種客戶端，卻只給一個大介面。 | C. SOLID 違反 |
| DIP Violation（違反依賴反轉原則） | DIP =「依賴抽象，不要依賴具體」。違反 = 高階的政策模組直接依賴低階的實作模組，依賴箭頭從上往下指向細節（Martin 說這是程序式架構的依賴結構）。 | C. SOLID 違反 |
| Zone of Pain（痛苦區） | 套件又具體（A≈0）又穩定（I≈0，被大量依賴）。具體的東西沒辦法靠擴充來改變，而依賴者又多，改起來非常痛苦。Martin 說這是一個套件最糟的位置。 | D. 套件／元件原則違反（ADP／SDP／SAP） |
| Zone of Uselessness（無用區） | 套件高度抽象（A≈1），卻沒有人依賴它（I≈1）。 | D. 套件／元件原則違反（ADP／SDP／SAP） |
| Cyclic Dependency（循環依賴；套件／元件層） | 兩個以上的架構元件直接或間接互相依賴。 | E1 依賴結構類 |
| Hub-Like Dependency（樞紐依賴；套件／元件層） | 元件同時和大量其他元件有傳入與傳出的依賴。 | E1 依賴結構類 |
| Unstable Dependency（不穩定依賴） | 元件依賴了比自己更不穩定的元件。 | E1 依賴結構類 |
| Dense Structure（稠密結構） | 元件之間的依賴過多、過密，而且看不出任何結構。 | E1 依賴結構類 |
| Unstable Interface（不穩定介面） | 一個檔案被許多檔案依賴（扮演「介面」的角色），卻經常和其他檔案一起變動。 | E1 依賴結構類 |
| Implicit Cross-module Dependency（隱性跨模組依賴） | 兩個在結構上（靜態依賴上）互相獨立的模組，在版控歷史裡卻有共同變更的關係。 | E1 依賴結構類 |
| Abstraction without Decoupling（有抽象卻沒解耦） | 客戶端用抽象型別來使用一個服務，卻**同時**直接依賴這個抽象型別的具體子型別。 | E1 依賴結構類 |
| God Component（上帝元件） | 元件過大。有兩派定義： | E2 關注點類 |
| Feature Concentration（功能集中） | 一個架構元件實現了不只一個架構關注點。 | E2 關注點類 |
| Scattered Parasitic Functionality（分散寄生功能） | 多個元件負責實現同一個高階關注點，而其中一些元件**還同時**負責其他正交（不相干）的關注點。這違反關注點分離兩次：一個關注點被分散到多個元件；至少一個元件同時處理多個正交關注點… | E2 關注點類 |
| Ambiguous Interface（模糊介面） | 介面只提供單一、一般化的進入點（例如 `process(GeneralType p)`），元件在內部再依型別分派。常見於透過共享事件匯流排交換訊息的 publish-subscr… | E3 介面與連接器類 |
| Connector Envy（連接器嫉妒） | 元件裡含有大量本該委派給連接器的互動功能。連接器提供四類服務：communication（傳遞資料）、coordination（傳遞控制）、conversion（轉換資料格式、型… | E3 介面與連接器類 |
| Extraneous Adjacent Connector（多餘的並存連接器） | 同一對元件之間，同時用兩種不同類型的連接器連接（例如事件匯流排加上直接方法呼叫）。 | E3 介面與連接器類 |
| Layer Violation（分層違規：反向依賴與跳層） | 下層使用上層（反向依賴）；或在嚴格分層中，跳過正下方那一層，直接存取更下面的層。 | E4 分層與子系統類 |
| Subsystem-API Bypassed（繞過子系統 API） | 客戶端繞過子系統的對外 API，直接存取元件的內部實作——等於擅自擴大了子系統的 API。 | E4 分層與子系統類 |
| Package Structure Imbalance（套件結構失衡） | **Too Large Packages/Subsystems**：套件裡類別或子套件很多，代表它承擔了不只一個責任。 | E4 分層與子系統類 |
| Big Ball of Mud（大泥球） | 一個隨意、甚至雜亂無章拼湊起來的系統，它的組織方式（如果還稱得上有組織）是由權宜而不是設計決定的。 | F. 經典架構反模式 |
| Lava Flow（熔岩流） | 在次佳條件下寫的程式碼被部署到生產環境，之後又在仍處於開發狀態時被繼續擴充（Wikipedia）。Brown 等人 1998 的描述：一段沒人記得用途和用法、而且大多沒被使用的程… | F. 經典架構反模式 |
| Golden Hammer（黃金錘） | 誤用偏愛的工具、函式庫、語言、框架或概念。開發者和管理者習慣既有做法，不願意學習並採用更合適的做法。 | F. 經典架構反模式 |
| Anemic Domain Model（貧血領域模型） | 表面上有領域物件，仔細一看卻幾乎沒有行為，只是一包 getter／setter；領域邏輯全被推到服務物件裡。 | F. 經典架構反模式 |
| Service Locator Abuse（服務定位器濫用） | 類別在內部向一個全域註冊表要依賴，而不是在建構子上宣告依賴。 | F. 經典架構反模式 |
| Singleton Abuse（單例濫用） | 用 Singleton 模式（靜態的全域存取點）當作取得協作者的手段。Hevery：Singleton 本質上就是全域狀態，讓物件偷偷取得 API 沒有宣告的東西，所以稱它們是「… | F. 經典架構反模式 |
| Speculative Architecture（臆測式架構；過度工程 over-engineering） | 為了「想像中」而不是真實的需求，預先建立架構基礎設施（擴充點、抽象層、外掛機制、可設定性）。 | F. 經典架構反模式 |
| Functional Decomposition（功能分解） | 程序式背景的開發者在物件導向語言裡寫程序式程式碼：一個 main 呼叫一堆子程序，再把每個子程序變成一個類別，完全不用類別階層。 | F. 經典架構反模式 |
| Megaservice（巨型服務） | 一個服務做了很多事——其實就是一個單體（monolith）。 | G1 技術—內部 |
| Hardcoded Endpoints（寫死端點） | 服務之間把對方的 IP 位址和埠號寫死。 | G1 技術—內部 |
| Inappropriate Service Intimacy（不當的服務親密） | 服務不處理自己的資料，而是一直去連其他服務的私有資料。 | G1 技術—內部 |
| API Versioning（缺少 API 版本化） | API 沒有使用語意化版本（semantic versioning）。 | G1 技術—內部 |
| Local Logging（本地日誌）／Lack of Monitoring（缺乏監控） | 日誌只存在各個服務本地，沒有用分散式日誌系統；或沒有監控系統（服務是否存活、回應是否正確）。 | G1 技術—內部 |
| Cyclic Dependency（循環依賴；服務層） | 服務之間形成循環的呼叫鏈。 | G2 技術—通訊 |
| No API Gateway（缺少 API 閘道） | 服務之間彼此直接溝通；最糟的情況下，服務的消費端也直接和每個服務溝通。 | G2 技術—通訊 |
| Shared Libraries（共用函式庫） | 不同的微服務共用同一個函式庫。 | G2 技術—通訊 |
| ESB Usage（使用企業服務匯流排） | 微服務之間透過企業服務匯流排（Enterprise Service Bus，ESB）溝通。 | G2 技術—通訊 |
| Wobbly Service Interactions（不穩的服務互動） | 一個服務失敗，會連帶觸發依賴它的服務也失敗（連鎖失效）。 | G2 技術—通訊 |
| Shared Persistence（共用持久層／共用資料庫） | 不同的微服務存取同一個關聯式資料庫；最糟的情況是存取同一個資料庫裡的同一批實體。 | G3 技術—其他 |
| Wrong Cuts（錯誤切分） | 服務應該依**業務能力**切分，卻依**技術層**（展示層、業務層、資料層）切分。 | G3 技術—其他 |
| Distributed Monolith（分散式單體） | 系統拆成了多個程序，卻必須整個系統一起部署，也就是「鎖步發布」（lockstep release）。 | G3 技術—其他 |
| Multiple Services in One Container（一個容器放多個服務） | 把多個服務放進同一個容器。 | G3 技術—其他 |

## [C# / .NET](03-csharp-dotnet.md)（82 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| A01 Async Void Method（async void 方法） | 不是事件處理器的 async 方法，卻宣告成回傳 `void`。 | A. 非同步與 Task |
| A02 Async Lambda Passed as Void Delegate（async lambda 被轉成 async void … | 把 async lambda 傳給參數型別是 `Action`、`Action<T>`、`TimerCallback` 這類回傳 void 的委派，結果等於寫了一個看不見的 as… | A. 非同步與 Task |
| A03 Sync-over-Async（同步阻塞等待非同步：.Result / .Wait() / GetAwaiter().GetRes… | 在同步程式碼裡用 `.Result`、`.Wait()`、`.GetAwaiter().GetResult()`、`Task.WaitAll/WaitAny` 卡住等 Task … | A. 非同步與 Task |
| A04 Blocking Call Inside Async Method（async 方法裡呼叫阻塞 API） | async 方法裡呼叫 `Thread.Sleep`、同步 I/O（`File.ReadAllText`、`Stream.Read`），或任何已有 Async 版本卻呼叫同步版本… | A. 非同步與 Task |
| A05 Async-over-Sync（用 Task.Run 包同步方法，假裝非同步） | 對外提供 `XxxAsync() => Task.Run(() => Xxx())`；在 ASP.NET Core 裡 `await Task.Run(...)` 後立刻等待；或… | A. 非同步與 Task |
| A06 Long-Running Blocking Loop on Thread Pool（長時間阻塞迴圈占住執行緒池） | 把永遠不結束、會阻塞的處理迴圈丟給 `Task.Run`，例如佇列消費或同步收封包的迴圈。 | A. 非同步與 Task |
| A07 Unobserved Fire-and-Forget Task（射後不理、沒人觀察的 Task） | 呼叫回傳 Task 的方法後，不 await、不保存，也不處理它的結果或例外。 | A. 非同步與 Task |
| A08 Missing or Unforwarded CancellationToken（沒有或沒往下傳 CancellationToke… | async API 不接受 CancellationToken；或接受了卻沒傳給下游的 async 呼叫；或 `CancellationTokenSource` 用完沒 Disp… | A. 非同步與 Task |
| A09 ConfigureAwait Misuse（ConfigureAwait 用錯場合） | 兩個方向都算壞味道：(a) 通用函式庫沒用 `ConfigureAwait(false)`；(b) 應用層程式（UI 事件、需要回主執行緒的遊戲邏輯）用了 `ConfigureA… | A. 非同步與 Task |
| A10 ValueTask / Awaitable Consumed More Than Once（ValueTask／Awaitable… | 對同一個 `ValueTask` await 兩次以上；還沒完成就取 `.Result`；存進欄位稍後再用；或多處同時 await。Unity 的 `Awaitable` 屬於同… | A. 非同步與 Task |
| A11 Returning Task Without Await Inside using/try（在 using／try 裡直接 ret… | 沒有 async 修飾的 Task 方法，在 `using` 或 `try` 區塊內直接 `return SomethingAsync();`。 | A. 非同步與 Task |
| A12 Returning Null from Task-Returning Method（Task 方法回傳 null） | 回傳 `Task`／`Task<T>` 的「非 async」方法 `return null;`。 | A. 非同步與 Task |
| A13 Blocking Async Initialization in Constructor（建構子裡同步等待非同步初始化） | 建構子或 DI 工廠 lambda 用 `.Result`／`.Wait()` 等待非同步初始化。 | A. 非同步與 Task |
| A14 TaskCompletionSource Without RunContinuationsAsynchronously（TCS 沒… | `new TaskCompletionSource<T>()` 沒帶 `TaskCreationOptions.RunContinuationsAsynchronously`。 | A. 非同步與 Task |
| A15 Lock Around Await / Unsynchronized Async State（用 lock 保護非同步臨界區／非同… | 在 async 程式碼裡用 `lock` 或 `Monitor` 保護跨越 await 的臨界區。`lock` 裡不能 await（編譯不過），所以有人改寫手動 Monitor，… | A. 非同步與 Task |
| A16 Deferred Argument Validation in Async Method（async 方法的參數檢查延後才拋出） | async 方法開頭的參數檢查（例如 ArgumentNullException）位在 async 狀態機裡面，例外會被存進 Task，等到 await 才出現。 | A. 非同步與 Task |
| B01 Undisposed IDisposable（IDisposable 沒有釋放） | 建立了 IDisposable 物件（檔案、socket、DB 連線、CancellationTokenSource、Timer…），卻沒有在每一條路徑上 Dispose。 | B. 資源與生命週期 |
| B02 Disposable Field Owner Not Disposable（擁有 disposable 欄位卻不實作或不傳遞 Di… | 類別持有 IDisposable 欄位，自己卻不實作 IDisposable；或實作了，但 Dispose 漏掉某個欄位，或沒呼叫基底類別的 Dispose。 | B. 資源與生命週期 |
| B03 Broken Dispose Pattern（Dispose 模式寫錯） | IDisposable 的實作不符合模式：Dispose 重複呼叫會拋例外（不是冪等）；finalizer 路徑（`disposing == false`）去碰受控物件；沒呼叫 … | B. 資源與生命週期 |
| B04 Unnecessary Finalizer（不必要的 finalizer／解構子） | 類別宣告了 `~ClassName()`，但沒有直接持有非受控資源，finalizer 裡只是計數、清欄位、寫 log、呼叫其他受控物件的 Dispose；或 finalizer… | B. 資源與生命週期 |
| B05 Event Subscription Leak（事件訂閱了沒退訂：有 += 沒有 -=，含 static 事件） | 用 `+=` 訂閱事件後，沒在對應時機 `-=` 退訂，而事件來源比訂閱者活得久。常見的長壽來源：static 事件、單例管理器、全域事件匯流排、長壽的連線物件。 | B. 資源與生命週期 |
| B06 HttpClient Per Request（每次請求都 new 一個 HttpClient） | 每次發請求都 `new HttpClient()`，通常還包在 using 裡。 | B. 資源與生命週期 |
| B07 Closure-Extended Lifetime（閉包捕捉延長物件壽命） | lambda 或匿名方法捕捉了 `this` 或大型區域變數，又被交給更長壽的東西（static 快取、事件、計時器、背景工作），被捕捉的物件因此無法回收。 | B. 資源與生命週期 |
| B08 Captive Dependency / Container-Captured Transient（DI 生命週期錯配） | DI 生命週期配錯。singleton 依賴 scoped 或 transient 服務，短命服務被「俘虜」成單例；transient 的 IDisposable 從根容器解析，… | B. 資源與生命週期 |
| B09 Explicit GC.Collect（手動呼叫 GC.Collect） | 程式裡主動呼叫 `GC.Collect()`，或 `GC.GetTotalMemory(true)`（它內部會呼叫 GC.Collect）。 | B. 資源與生命週期 |
| C01 Catch-All Exception（catch (Exception) 一網打盡） | 在一般流程裡用 `catch (Exception)`、`catch (SystemException)` 或不帶型別的 `catch` 處理例外。 | C. 例外處理 |
| C02 Swallowed Exception / Empty Catch（空 catch、吞掉例外） | catch 區塊是空的，或只有註解或 `return`，不記錄、不處理、也不重拋。 | C. 例外處理 |
| C03 throw ex Resets Stack Trace（throw ex 毀掉堆疊追蹤） | 在 catch 裡用 `throw ex;` 重拋原本的例外。 | C. 例外處理 |
| C04 Useless Rethrow Catch（只做重拋的 catch） | catch 區塊裡只有 `throw;`，其他什麼都沒做。 | C. 例外處理 |
| C05 Exceptions as Control Flow（把例外當流程控制） | 用 try/catch 處理「平常就會發生」的情況，例如用 `int.Parse` 加 catch 判斷輸入是不是數字，或用 KeyNotFoundException 判斷字典裡… | C. 例外處理 |
| C06 Throwing from finally / Dispose / Unexpected Members（在 finally、Di… | 在不預期會拋例外的位置拋例外：finally、例外篩選、Dispose、ToString、Equals、GetHashCode、靜態建構子、事件存取子、隱式轉型運算子。 | C. 例外處理 |
| C07 Catching NullReferenceException / Throwing Reserved Types（抓 NullR… | 用 `catch (NullReferenceException)` 來處理 null；或自己 `throw new Exception()`，或拋 `NullReference… | C. 例外處理 |
| D01 Multiple Enumeration of IEnumerable（同一個 IEnumerable 被列舉多次） | 同一個 `IEnumerable<T>` 被列舉好幾次，尤其是延遲執行的 LINQ 或 DB 查詢。例如先 `Count()` 再 `foreach`，或先 `Any()` 再 … | D. 集合與 LINQ |
| D02 Count() for Emptiness / LINQ on Sized Collections（用 Count() 判空、對有… | 用 `Count() > 0` 判斷 IEnumerable 是不是空的；或對本來就有 `Count`／`Length` 屬性的集合呼叫 LINQ 的 `Count()`、`An… | D. 集合與 LINQ |
| D03 LINQ in Hot Path（熱路徑上用 LINQ） | 在每幀、每封包、每個伺服器 tick 都會執行的熱路徑上，使用 Where、Select、OrderBy、ToList 這類 LINQ 鏈。 | D. 集合與 LINQ |
| D04 ToList/ToArray Abuse（ToList()／ToArray() 濫用） | 在查詢鏈中間呼叫 ToList() 或 ToArray()；只為了 foreach 就先物化；或寫出 `.ToList().Count()`、`.ToList().ForEach… | D. 集合與 LINQ |
| D05 Linear Lookup in Loop（迴圈裡做線性搜尋，變成 O(n²)） | 在迴圈裡對 List 或陣列呼叫 `Contains`、`IndexOf`、`Find`，總成本變成 O(n×m)，甚至 O(n²)。 | D. 集合與 LINQ |
| D06 Double Dictionary Lookup（ContainsKey 加索引子，查兩次） | `if (d.ContainsKey(k)) v = d[k];`、`if (!d.ContainsKey(k)) d.Add(k, v);`、`d.Keys.Contains(… | D. 集合與 LINQ |
| D07 Modifying Collection During Enumeration（走訪集合時修改它） | 用 foreach 走訪集合的同時，對同一個集合 Add 或 Remove。 | D. 集合與 LINQ |
| D08 Exposing Mutable Collections（對外公開可變集合） | 公開 API 回傳或接收 `List<T>`；屬性回傳陣列；集合屬性有公開的 setter。 | D. 集合與 LINQ |
| E01 Boxing（裝箱） | 值型別被轉成 object 或介面型別時，會在堆積上配置一份副本。 | E. 型別與記憶體配置 |
| E02 String Concatenation in Loop（迴圈裡串接字串） | 在迴圈裡用 `+` 或 `+=` 累加字串。 | E. 型別與記憶體配置 |
| E03 Large or Mutable Struct（過大或可變的 struct） | struct 大於約 16 bytes、可變、或常常被裝箱；或者沒有覆寫 Equals。 | E. 型別與記憶體配置 |
| E04 Closure Allocation in Hot Path（熱路徑上的閉包配置） | 熱路徑上的 lambda 或匿名方法捕捉了外部變數，每執行一次就配置一次閉包物件與委派。 | E. 型別與記憶體配置 |
| E05 Params Array Allocation（params 陣列配置） | 在熱路徑上呼叫 `params T[]` 方法，例如多參數的 `string.Format`、自訂的 `Log(params object[])`，每次呼叫都配置一個陣列；值型別… | E. 型別與記憶體配置 |
| E06 Repeated Empty/Constant Array Allocation（重複配置空陣列或常數陣列） | 寫 `new T[0]`；或每次呼叫都傳一個新的常數陣列，例如 `new[] { ',', ';' }`。 | E. 型別與記憶體配置 |
| E07 Reflection in Hot Path（熱路徑上用反射） | 執行期反覆用 `GetType().GetMethod/GetField`、`Activator.CreateInstance`、`Assembly.GetTypes()` 來做… | E. 型別與記憶體配置 |
| E08 Dynamic Abuse（濫用 dynamic） | 明明型別已知，卻用 `dynamic` 取代介面、泛型或模式比對。 | E. 型別與記憶體配置 |
| E09 ToLower/ToUpper Comparison & Culture-Sensitive Compare（用 ToLower／… | 用 `a.ToLower() == b.ToLower()` 做不分大小寫的比較；或字串比較、搜尋時沒有指定 StringComparison，結果套用目前的文化設定。 | E. 型別與記憶體配置 |
| F01 Partial Class as Giant-Class Hider（用 partial class 切開巨型類別） | 一個職責過多的巨型類別，用 `partial` 拆成很多個檔案（例如 `GameClient.Network.cs`、`GameClient.UI.cs`…共 37 檔），而不是… | F. 語言構件與設計濫用 |
| F02 Region Hiding Code（用 #region 遮住程式碼） | 用 `#region` 把巨型類別或巨型方法折疊起來，或在方法本體裡用 region 分段。 | F. 語言構件與設計濫用 |
| F03 Extension Method Abuse（濫用擴充方法） | 自己有原始碼的型別，用擴充方法代替成員；對 object 或極廣泛的型別（string、int）加入領域邏輯的擴充；所有擴充方法都丟進一個叫 `Extensions` 的命名空間。 | F. 語言構件與設計濫用 |
| F04 Mutable Static State（可變的 static 狀態） | public 或 protected 的非 readonly static 欄位；實例方法寫入 static 欄位；用全域可變的 static 變數當共享狀態。 | F. 語言構件與設計濫用 |
| F05 Singleton / Service Locator / Static Service Access（Singleton、Ser… | 用 `XxxManager.Instance` 這種全域單例存取一切；在類別內部呼叫 `GetService<T>()` 或 `Locator.Get<T>()` 取得依賴；把 … | F. 語言構件與設計濫用 |
| F06 Public or Protected Fields（public 或 protected 欄位） | 不是 const、也不是 static readonly 的 public 或 protected 實例欄位。 | F. 語言構件與設計濫用 |
| F07 Deep Inheritance（繼承太深） | 類別的繼承層級太深。CA1501 的門檻是 5 層以上；預設排除 `System.*` 命名空間的型別，也可以設定排除其他命名空間。 | F. 語言構件與設計濫用 |
| F08 Out/Ref Parameter Overuse & Long Parameter List（out／ref 參數太多、參數清單… | 方法用好幾個 out 或 ref 參數回傳多個結果，或參數數量太多。 | F. 語言構件與設計濫用 |
| F09 Boolean Flag Argument（用 bool 參數切換行為） | 用 bool 參數切換方法的行為，例如 `Save(true)`、`Spawn(pos, false, true)`。 | F. 語言構件與設計濫用 |
| F10 Null Return Without Nullable Annotations（用 null 表示「沒有」，卻沒啟用 NRT） | 方法用 null 表示「空集合」或「沒有結果」，型別上卻看不出來；專案沒啟用 nullable reference types（NRT），哪些東西可能是 null 全靠註解或猜。 | F. 語言構件與設計濫用 |
| F11 Magic Strings（魔術字串） | 程式裡散落著有特定意義的字串常值（事件名、設定鍵、場景名、tag、參數名），同一個字串在多處重複出現。 | F. 語言構件與設計濫用 |
| F12 Virtual Call in Constructor（建構子裡呼叫可覆寫的成員） | 建構子呼叫 virtual 或 abstract 成員。 | F. 語言構件與設計濫用 |
| F13 Member Could Be Static（不需要實例卻不是 static） | 成員完全沒用到實例資料，卻沒宣告成 static。 | F. 語言構件與設計濫用 |
| F14 Ignored Return Value（忽略回傳值） | 呼叫沒有副作用、會回傳新值的方法，卻把結果丟掉；或忽略 Try 方法的成功旗標。 | F. 語言構件與設計濫用 |
| G01 Locking on Public or Weak-Identity Objects（鎖在公開或身分不穩的物件上：lock(thi… | 用 `this`、`typeof(X)`、字串（包括字串常值）或其他外部也拿得到的物件當鎖。 | G. 執行緒與同步 |
| G02 Hand-Rolled Double-Checked Locking（自己寫雙重檢查鎖定） | 自己寫 `if (x == null) lock (...) if (x == null) x = new ...;` 來做延遲初始化。 | G. 執行緒與同步 |
| G03 Unsynchronized Shared Collection（多執行緒共寫非執行緒安全的集合） | 多條執行緒同時寫入（或一條寫、多條讀）Dictionary、List、HashSet 這類非執行緒安全的集合，卻沒有任何同步。 | G. 執行緒與同步 |
| G04 Assuming GetOrAdd Factory Runs Once（以為 ConcurrentDictionary.GetOr… | 以為 `ConcurrentDictionary.GetOrAdd(key, factory)` 的工廠只會執行一次，就在工廠裡做昂貴或有副作用的事（建連線、扣資源），甚至在工廠… | G. 執行緒與同步 |
| G05 Thread.Sleep for Waiting or Polling（用 Thread.Sleep 等待或輪詢） | 用 Thread.Sleep 等某個條件成立（輪詢），或在 async 方法裡延遲。 | G. 執行緒與同步 |
| G06 Timer Leak or Reentrancy（Timer 沒停、沒保留參考，或回呼會重入） | 建立 `System.Threading.Timer` 後沒保留參考、也沒 Dispose；或回呼的執行時間可能比週期長，卻沒有防止重入。 | G. 執行緒與同步 |
| G07 Coarse or Hot-Path Locking（熱路徑上鎖、鎖的範圍太大） | 在熱路徑上取鎖；在鎖裡做 I/O 或長時間計算；用一把全域鎖保護互不相關的資源；簡單的計數也用 lock。 | G. 執行緒與同步 |
| H01 Per-Frame Lookups（每幀做 GetComponent／Find 查找） | 在 Update、FixedUpdate、LateUpdate 裡呼叫 `GetComponent`、`GameObject.Find`、`FindObjectOfType`、`… | H. Unity C# 特有 |
| H02 Camera.main in Update（每幀存取 Camera.main） | 每幀甚至一幀內多次存取 `Camera.main`。 | H. Unity C# 特有 |
| H03 Tag String Comparison（用 == 比較 tag 字串） | 用 `gameObject.tag == "Enemy"` 比較 tag。 | H. Unity C# 特有 |
| H04 Empty Unity Messages（空的 Update 等 Unity 訊息方法） | 留著空的 `Update()`、`FixedUpdate()`、`Start()` 等 Unity 訊息方法；或 Update 裡只是在等某個少見的條件成立。 | H. Unity C# 特有 |
| H05 Per-Frame GC Allocation（每幀產生 GC 配置） | 每幀執行的程式碼在堆積上配置：new 參考型別、字串串接或格式化、閉包、LINQ、裝箱、params、會回傳陣列的 Unity API、Debug.Log。 | H. Unity C# 特有 |
| H06 Repeated Array-Returning API Access（迴圈裡重複存取會回傳陣列的 Unity API） | 在迴圈裡反覆存取每次都會回傳新陣列的 Unity API，例如 `mesh.vertices`、`Input.touches`、`Physics.RaycastAll`、`ren… | H. Unity C# 特有 |
| H07 foreach Allocation on Old Unity or via Interface（舊版 Unity 的 forea… | 在 Unity 5.5 之前的編譯器上，對 `List<T>` foreach 會配置；而在任何版本，透過介面型別（`IEnumerable<T>` 等）foreach 都會把 … | H. Unity C# 特有 |
| H08 Coroutine Leak & Yield Allocation（協程洩漏與 yield 配置） | 協程沒有結束條件，也沒有停止機制；以為把腳本 `enabled = false` 就會停止協程；每一輪都 `yield return new WaitForSeconds(x)`… | H. Unity C# 特有 |
| H09 C# Null Operators on UnityEngine.Object（對 Unity 物件用 ?.、??、is null） | 對 UnityEngine.Object（GameObject、Component、ScriptableObject 等）用 `?.`、`??`、`??=`、`is null` … | H. Unity C# 特有 |
| H10 String-Based Animator/Shader Property Access（用字串名稱存取 Animator／Sha… | 每次都用字串名稱呼叫 `animator.SetFloat("Speed", v)`、`material.SetColor("_Color", c)`。 | H. Unity C# 特有 |
| H11 Instantiate/Destroy Churn（頻繁 Instantiate／Destroy，不用物件池） | 頻繁 Instantiate 與 Destroy 短命的物件，例如子彈、特效、傷害數字。 | H. Unity C# 特有 |
| H12 God MonoBehaviour（巨型 MonoBehaviour） | 一個 MonoBehaviour 同時負責輸入、移動、戰鬥、UI、網路、存檔等多種職責，長達數千行，Update 裡塞滿 if 分支。 | H. Unity C# 特有 |

## [Client/Server](04-client-server.md)（57 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Client-Authoritative State（信任用戶端數值／用戶端權威）〔A1〕 | 伺服器直接採用用戶端回報的「結果」，例如位置、血量、傷害、冷卻是否結束、掉了什麼寶，而不是自己算。 | A. 信任邊界（Trust Boundary） |
| Missing Server-Side Input Validation（伺服器不驗證輸入／封包沒做邊界檢查）〔A2〕 | 伺服器把收到的位元組直接當合法資料用，不檢查長度、範圍、索引、數量正負、字串長度。 | A. 信任邊界（Trust Boundary） |
| Business Logic in Client（商業邏輯放在用戶端）〔A3〕 | 掉落機率、合成成功率、商店價格與折扣、任務完成判定、獎勵數量由用戶端計算，伺服器只負責記帳。 | A. 信任邊界（Trust Boundary） |
| Client-Side Permission Filtering（靠用戶端過濾權限）〔A4〕 | 權限只靠介面隱藏，例如 GM 按鈕不顯示、debug 封包只是用戶端不送、公會管理只有會長看得到，但伺服器 handler 對任何人都開放。 | A. 信任邊界（Trust Boundary） |
| Client-Enforced Limits（冷卻、次數、頻率只在用戶端擋）〔A5〕 | 技能冷卻、每日次數、獎勵只能領一次、聊天頻率等限制只寫在用戶端。 | A. 信任邊界（Trust Boundary） |
| Chatty Interface / Chatty I/O（聊天式介面：多次小往返）〔B1〕 | 一個邏輯操作被拆成很多次小請求來回。 | B. 協定設計（Protocol Design） |
| Chunky / Bloated Packet & Extraneous Fetching（過胖封包／多撈資料）〔B2〕 | 矯正 B1 過頭，每次都送一整包，例如整個背包、整個角色、整個公會成員表，或單包大到會被 IP 分片。 | B. 協定設計（Protocol Design） |
| N+1 Requests（N+1 請求）〔B3〕 | 先拿一份清單（1 次），再對清單每一項各發一次請求（N 次）。 | B. 協定設計（Protocol Design） |
| Unversioned Protocol（協定沒有版本號）〔B4〕 | 連線握手時不交換協定識別與版本，兩端只是「剛好一致」才能運作。 | B. 協定設計（Protocol Design） |
| Backward-Incompatible Serialization（序列化格式不向後相容）〔B5〕 | 改訊息結構的方式，讓舊資料或舊版對端無法正確解讀。常見做法：改欄位型別、重用已刪欄位的編號、改預設值、把 repeated 改成單值、新增 required 欄位。 | B. 協定設計（Protocol Design） |
| Ordinal Leakage（enum／欄位序號直接上線）〔B6〕 | 把語言內部的「位置」當成線上格式，例如 C# enum 的整數值、欄位宣告順序、陣列索引、IntKey 序號，而且沒有明確固定它們。 | B. 協定設計（Protocol Design） |
| Packet Handler Boilerplate Hell（封包處理器樣板地獄）〔B7〕 | 每個 handler 各自重複「解包 → 驗證 session 與權限 → 驗證欄位 → try/catch → 記 log → 組回應」，這些橫切關注點（cross-cutti… | B. 協定設計（Protocol Design） |
| Giant Opcode Switch（opcode 大 switch）〔B8〕 | 所有訊息分派寫在一個巨大的 `switch (opcode)`，每個 case 裡直接放業務程式碼。 | B. 協定設計（Protocol Design） |
| Duplicated Message Definitions（同一訊息多處定義）〔B9〕 | 同一個封包格式在用戶端（Unity）與伺服器（C#）各手寫一份；或同一端的 Read 與 Write 各寫一份。 | B. 協定設計（Protocol Design） |
| Dual Source of Truth（雙存：同一份資料兩個可寫來源）〔C1〕 | 同一個事實存在兩處，而且兩處都會被寫入。例如： | C. 狀態同步（State Synchronization） |
| No Authoritative Source（沒有權威來源）〔C2〕 | 多個參與者都能宣告狀態，沒有任何一方的裁決是最終的。典型例子是 P2P 沒有主機裁決，或用戶端互相廣播狀態、伺服器只負責轉發。 | C. 狀態同步（State Synchronization） |
| State Drift Without Reconciliation（狀態漂移且沒有和解機制）〔C3〕 | 用戶端做了預測或本地模擬，但收到伺服器的權威狀態時沒有正確和解（reconciliation）。結果是兩端長期不一致，或修正時畫面劇烈跳動。 | C. 狀態同步（State Synchronization） |
| Full-State Sync Instead of Delta（以全量同步代替差量）〔C4〕 | 每次更新都送整個世界或整個物件的完整狀態。 | C. 狀態同步（State Synchronization） |
| No Sequence / Ack（沒有序號與確認機制）〔C5〕 | 訊息沒有序號，接收端無法判斷遺失、重複、亂序；傳送端也不知道對方收到了哪些。 | C. 狀態同步（State Synchronization） |
| Arrival-Order Dependence（依賴到達順序）〔C6〕 | 程式假設訊息會照送出順序到達並被處理，但底層並不保證。不保證順序的情況包括 UDP、多條連線、多台伺服器、多個 consumer、async handler 併行。 | C. 狀態同步（State Synchronization） |
| Client Clock as Time Source（用用戶端時鐘當時間來源）〔C7〕 | 冷卻、buff 到期、移動距離（速度 × 時間）、每日重置、拍賣截止等，用用戶端送來的時間戳或用戶端本機時間計算。 | C. 狀態同步（State Synchronization） |
| Missing Timeout（沒有逾時）〔D1〕 | 網路呼叫、DB 查詢、跨服 RPC、等待對方回應，都沒有時間上限。 | D. 可靠性（Reliability） |
| Unbounded Retry（無上限重試）〔D2〕 | 失敗就立刻重試，而且永遠重試（`while (true)`）。 | D. 可靠性（Reliability） |
| Retry Storm / Reconnect Thundering Herd（重試風暴／重連雪崩）〔D3〕 | 大量用戶端或多層服務在同一時間重試，把剛恢復的服務再次打掛。 | D. 可靠性（Reliability） |
| Non-Idempotent Retry（非冪等操作被重試：重複扣款／重複發獎）〔D4〕 | 有副作用的操作（扣款、發獎、扣材料、寄信）被重送時，會再執行一次。 | D. 可靠性（Reliability） |
| No Reconnect / Session Resume（沒有斷線重連處理）〔D5〕 | 連線一斷就等同登出，戰鬥、交易、組隊狀態全丟；或用戶端只會跳回登入畫面。 | D. 可靠性（Reliability） |
| Undetected Half-Open Connection（半開連線未偵測）〔D6〕 | 一端已經斷了（拔線、手機休眠、NAT 逾時、中間設備重啟），另一端卻以為連線還活著。 | D. 可靠性（Reliability） |
| Session State Bound to Connection Object（session 狀態綁在單一連線物件上）〔D7〕 | 玩家的遊戲狀態（角色、背包、所在房間）以連線物件或連線 ID 為 key 存放，連線一消失狀態就跟著消失。 | D. 可靠性（Reliability） |
| Shared Mutable State Across Threads（跨執行緒共享可變狀態）〔E1〕 | 遊戲狀態（玩家、房間、地圖物件）可以被多條執行緒同時讀寫，保護它的只有散落各處的 lock，甚至完全沒有保護。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Game Logic on I/O Thread（遊戲邏輯跑在 I/O 執行緒上）〔E2〕 | 在網路收包的回呼（socket receive callback、event loop）裡直接執行遊戲邏輯、DB 存取或重計算。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Global Lock（全域鎖／鎖粒度過粗）〔E3〕 | 用一把大鎖保護整個世界或整台伺服器的狀態，任何操作都要先拿到這把鎖。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Inconsistent Lock Ordering（鎖順序不一致）〔E4〕 | 不同程式路徑以不同順序取得多把鎖。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Blocking I/O in Tick（在 tick 主迴圈中做阻塞 I/O 或 DB 呼叫）〔E5〕 | 在固定頻率的遊戲主迴圈裡，同步等待 DB、檔案、HTTP 或跨服 RPC。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Sync-over-Async（以 .Result／.Wait() 同步等待非同步工作）〔E6〕 | C# 中用 `.Result`、`.Wait()`、`GetAwaiter().GetResult()` 阻塞等待 Task 完成。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Per-Tick Allocation Churn（在 tick 中大量配置記憶體）〔E7〕 | 每個 tick 或每個封包都 new 一堆短命物件，例如訊息物件、LINQ、閉包、字串串接、boxing、`byte[]`。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Actor / Single-Thread Model Bypass（繞過 actor／單執行緒模型）〔E8〕 | 系統用「每個 actor 或房間由單執行緒處理」來免除鎖，但程式碼偷偷從其他執行緒去碰 actor 的內部狀態。 | E. 伺服器並行與資源隔離（Server Concurre… |
| Non-Atomic Check-Then-Act（先查後改非原子：刷物溫床）〔E9〕 | 「檢查條件」與「執行變更」分成兩步，中間有時間窗（race window），併發請求可以同時通過檢查。又稱 TOCTOU（time-of-check to time-of-use… | E. 伺服器並行與資源隔離（Server Concurre… |
| Busy Front End（前端忙碌：在服務行程內無節制地開背景工作）〔E10〕 | Azure 的定義是，把 CPU 密集工作丟到大量背景執行緒，看似讓回應變快，實際上和處理請求的執行緒搶資源。遊戲版本：在遊戲服行程內為尋路、AI 批次、排行榜重算、配對、報表無… | E. 伺服器並行與資源隔離（Server Concurre… |
| Noisy Neighbor（吵鬧鄰居：單一房間或公會吃光共用資源）〔E11〕 | 多個房間、公會、分線（或租戶）共用同一個行程、DB 或快取，其中一方的突發負載拖垮其他人。 | E. 伺服器並行與資源隔離（Server Concurre… |
| SQL Embedded in Game Logic（遊戲邏輯中直接寫 SQL）〔F1〕 | 戰鬥、任務、商店等業務邏輯裡直接組 SQL 字串，或直接操作 DB 連線。 | F. 資料存取（Data Access / Persist… |
| Whole-Blob Save（每次存檔寫整包 blob）〔F2〕 | 把整個角色（屬性、背包、任務、好友……）序列化成一個大 blob，任何變動都整包寫回。 | F. 資料存取（Data Access / Persist… |
| Synchronous DB Write Blocking Player（同步寫 DB 阻塞玩家操作）〔F3〕 | 玩家每個動作都等 DB 寫完才回應或繼續。 | F. 資料存取（Data Access / Persist… |
| Cache-DB Inconsistency（快取與 DB 不一致）〔F4〕 | 快取（Redis 或記憶體）與 DB 的資料不一致，而且沒有明確策略。常見原因：寫入順序錯、沒有失效、多個本地快取各自過期。 | F. 資料存取（Data Access / Persist… |
| Shared Persistence（多服務共用同一個資料庫）〔F5〕 | 多個服務（登入服、遊戲服、商城服、GM 後台、營運報表）直接讀寫同一組表。 | F. 資料存取（Data Access / Persist… |
| ORM N+1 Query（ORM 的 N+1 查詢）〔F6〕 | 先查出 N 筆主資料，再在迴圈中觸發 N 次關聯查詢，常由 lazy loading（延遲載入：存取到關聯屬性時才自動查 DB）在背後產生。 | F. 資料存取（Data Access / Persist… |
| Monolithic Persistence（單一資料儲存放所有類型資料）〔F7〕 | 業務資料、log、遙測、聊天紀錄、佇列訊息全部塞在同一個資料庫。 | F. 資料存取（Data Access / Persist… |
| No Caching（不快取）〔F8〕 | 每次請求都重新讀取相同而且很少變的資料，例如道具表、技能表、玩家公開資料。 | F. 資料存取（Data Access / Persist… |
| Busy Database（忙碌資料庫：把運算塞進 DB）〔F9〕 | 用 stored procedure、trigger 或複雜 SQL 做格式化、字串處理、業務規則計算。 | F. 資料存取（Data Access / Persist… |
| Improper Instantiation（不當實例化：反覆建立應共享的連線物件）〔F10〕 | 每個請求都 new 一個本該共享的重量級物件，例如 HttpClient、Redis 的 ConnectionMultiplexer、ServiceBusClient、gRPC … | F. 資料存取（Data Access / Persist… |
| Network Callback Mutates UI Directly（網路回呼直接改 UI）〔G1〕 | 收到封包的回呼裡直接操作 UI 元件或 GameObject。 | G. 用戶端結構（Unity Client） |
| Network I/O and Parsing on Main Thread（在主執行緒做網路收送與解析）〔G2〕 | 在 Unity 主執行緒上同步收送 socket、解壓縮、反序列化大封包（JSON、大型 protobuf）。 | G. 用戶端結構（Unity Client） |
| Business Rules in UI Layer（UI 層含業務規則）〔G3〕 | MonoBehaviour 的 UI 腳本裡含有遊戲規則，例如在按鈕事件裡算價格、判斷能否強化、決定要顯示的掉落、驗證輸入。 | G. 用戶端結構（Unity Client） |
| Manager Spider Web（全域管理器蛛網）〔G4〕 | 大量 `XxxManager.Instance` 單例互相直接呼叫，形成網狀依賴。 | G. 用戶端結構（Unity Client） |
| Event Bus Abuse（事件總線濫用導致追不到資料流）〔G5〕 | 所有模組都透過全域事件總線（EventBus、Messenger）溝通，事件被拿來傳命令與資料，而不只是通知「某件事已經發生」。 | G. 用戶端結構（Unity Client） |
| Silent Failure（失敗靜默：錯誤被吞或只記 debug）〔H1〕 | 錯誤被吞掉、只記成 debug 等級的 log，或回傳預設值後若無其事地繼續執行。 | H. 可觀測性（Observability） |
| No Correlation ID（沒有關聯 ID）〔H2〕 | 一個玩家操作會經過 client → gateway → game server → DB 或其他服務，但各處的 log 沒有共同的識別碼。 | H. 可觀測性（Observability） |
| Unreproducible Packet Flow（無法重現的封包流）〔H3〕 | 線上發生的錯誤無法在本地重現，因為沒有保留足夠資訊，例如輸入序列、封包內容、伺服器 tick 編號、隨機種子。 | H. 可觀測性（Observability） |

## [並行·效能·資源](05-concurrency-perf-resource.md)（60 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Unsynchronized Shared Mutable State（未同步的共享可變狀態） | 兩條以上執行緒讀寫同一個可變變數，卻沒有任何同步保護。 | A1 共享狀態與原子性 |
| Non-atomic Read-Modify-Write（非原子的讀-改-寫） | `x++`、`x += n`、`flag ^= true` 看起來是一行，實際上是「讀出→修改→寫回」三步，中間可以被別的執行緒插隊。 | A1 共享狀態與原子性 |
| Check-Then-Act（先檢查再行動） | 先檢查一個條件，再依結果行動；但兩步之間，狀態可能已被別的執行緒改掉。 | A1 共享狀態與原子性 |
| Composing Independently Atomic Calls（把多個各自原子的呼叫當成整體原子） | 以為每個方法各自是執行緒安全的，連續呼叫幾個也就安全。 | A1 共享狀態與原子性 |
| Order Violation（順序違反：假設的執行順序沒有被保證） | 程式默默假設「A 一定比 B 先發生」，例如先初始化再使用、先設好欄位再觸發回呼，但沒有任何同步機制保證這個順序。 | A1 共享狀態與原子性 |
| Invariant Split Across Locks（同一個不變量被拆給不同鎖保護） | 兩個變數之間有必須一起成立的關係，也就是不變量（invariant），例如 `lower <= upper`、總數等於各項加總；但這兩個變數分別由不同的鎖保護。 | A1 共享狀態與原子性 |
| Volatile as Synchronization（把 volatile 當同步工具） | 以為欄位加上 `volatile` 就執行緒安全了。 | A1 共享狀態與原子性 |
| Broken Double-Checked Locking（錯誤的雙重檢查鎖定） | 雙重檢查鎖定（double-checked locking, DCL）是為了省掉鎖的成本，先不加鎖檢查一次 null，再加鎖檢查一次，然後建立物件；錯在欄位沒有正確的記憶體可見性… | A1 共享狀態與原子性 |
| Unsafe Publication（不安全發佈：物件還沒建好就被別的執行緒看到） | 物件還沒建構完成，參考就被別的執行緒拿到。 | A1 共享狀態與原子性 |
| Mutable Static State in Server Code（伺服器程式裡會被修改的 static 狀態） | 伺服器程式用 static 欄位存放會被修改的狀態。 | A1 共享狀態與原子性 |
| Coarse-Grained Lock / One-Lane Bridge（鎖粒度過粗／單線橋） | 一把大鎖把所有呼叫者排成單線，而且持鎖期間還做大量工作。 | A2 鎖的設計 |
| Over-Synchronization（過度同步／鎖切得過細） | 不需要同步的地方也加鎖，或把鎖切得很碎，一個操作要拿好幾把鎖。 | A2 鎖的設計 |
| Inconsistent Lock Ordering（巢狀鎖的取得順序不一致） | 兩段程式以不同順序取得同一組鎖，結果互相等對方放手。 | A2 鎖的設計 |
| Calling Alien Methods While Holding a Lock（持鎖時呼叫外部程式碼） | 持鎖期間呼叫自己掌控不了行為的程式碼，也就是外來方法（alien method），例如事件、回呼、委派、虛擬方法、介面實作、插件。 | A2 鎖的設計 |
| Blocking While Holding a Lock（持鎖時做阻塞操作） | 持著鎖去做 I/O、睡眠或等待其他事件。 | A2 鎖的設計 |
| Locking on Publicly Accessible Objects（拿外部也拿得到的物件當鎖） | 用 `this`、`typeof(X)`、字串常值、公開欄位這類外部程式碼也能拿到的物件當鎖。 | A2 鎖的設計 |
| Lock Not Released on Exception（例外路徑沒有釋放鎖） | 手動取得與釋放鎖時，發生例外就沒走到釋放那一步。 | A2 鎖的設計 |
| Busy Waiting / Sleep Polling（忙等／睡眠輪詢） | 用迴圈反覆檢查條件來等某件事發生，而不是讓執行緒睡著、等別人通知。 | A3 等待與通知 |
| Condition Wait Without Loop / Lost Notification（條件等待不在迴圈內／通知遺失） | 等待條件時只檢查一次（用 `if` 而不是 `while`），或通知在對方開始等待之前就發出而遺失。 | A3 等待與通知 |
| Thread-per-Request（每個請求開一條執行緒） | 每來一個請求就 new 一條執行緒處理，沒有上限。 | A4 執行緒數量與生命週期 |
| More Is Less（越多越慢：執行緒或池資源配置過量） | 某種資源配置過多，例如執行緒、行程、池中的連線，反而拖慢整體。 | A4 執行緒數量與生命週期 |
| Thread Leak（執行緒洩漏） | 持續啟動新執行緒或建立新的執行緒池，卻從不停止。 | A4 執行緒數量與生命週期 |
| Interdependent Tasks in a Bounded Pool（有上限的池中放了互相等待的任務） | 在固定大小的執行緒池裡，任務同步等待另一個也排在同一個池的任務，造成執行緒飢餓死結（thread starvation deadlock）。 | A4 執行緒數量與生命週期 |
| Forcible Thread Termination（從外部強制終止執行緒） | 從外部硬殺或硬停另一條執行緒。 | A4 執行緒數量與生命週期 |
| Stale ThreadLocal in Pooled Threads（池化執行緒中殘留的 ThreadLocal） | 在執行緒池裡使用執行緒區域變數（ThreadLocal／`[ThreadStatic]`），任務結束時沒清掉，下一個任務就拿到上一個任務的值。 | A4 執行緒數量與生命週期 |
| Unnecessary Processing（不必要的處理） | 在關鍵路徑上做了此刻不需要、或根本不需要的工作。 | B1 白做的工 |
| Repeated Computation / "How Many Times Do I Have to Tell You?"（重複計算） | 同樣的結果在迴圈內、或在多條呼叫路徑上被重算很多次。 | B1 白做的工 |
| Tower of Babel / Repeated Serialization（巴別塔：反覆轉換格式與序列化） | 資料在元件之間傳遞時一再轉換格式，例如物件→JSON→物件→XML，大量時間花在轉換上。 | B1 白做的工 |
| Unnecessary Deep Copy（不必要的深拷貝） | 為了「安全」把整個物件圖複製一份，但呼叫端其實不會修改，或根本不需要獨立的副本。 | B1 白做的工 |
| Hidden Quadratic（隱藏的 O(n²)） | 看起來是線性的程式碼，因為在迴圈內呼叫了本身就是 O(n) 的操作，整體變成 O(n²)。 | B2 演算法與成長 |
| The Ramp（斜坡：隨使用時間與資料量越來越慢） | 處理時間隨系統使用時間或資料量增長而持續上升。 | B2 演算法與成長 |
| Circuitous Treasure Hunt / N+1 Query（迂迴尋寶／N+1 查詢） | 為了湊齊一份資料，查完一筆再根據結果查下一筆，層層往下，造成大量往返。 | B3 I/O 往返 |
| Empty Semi Trucks / Chatty I/O（空車半掛：請求太多、每次只運一點） | 完成一件事需要過多次請求，每次只搬一點點資料。 | B3 I/O 往返 |
| Sisyphus Database Retrieval / Extraneous Fetching（撈回比需要多得多的資料） | 查回遠多於需要的資料，再在應用程式內丟掉大部分。 | B3 I/O 往返 |
| Excessive Dynamic Allocation（過度動態配置：熱路徑大量建立短命物件） | 在熱路徑上大量建立、又立刻丟棄短命物件。 | B4 配置與實例化 |
| Improper Instantiation（不當實例化：該共用的物件每次都重建） | 設計成「建立一次、到處共用」的物件，例如連線或客戶端類別，卻在每個請求中重新建立。 | B4 配置與實例化 |
| Blob / God Class — performance view（團塊／上帝類別：效能視角） | 單一元件做了系統大部分的工作，或握有大部分的資料，所有請求都要經過它。 | B5 負載與排隊 |
| Unbalanced Processing / Pipe and Filter（處理不平衡／最慢的一段卡住整條管線） | 處理沒有用到可用的處理器，或某一個慢階段限制了整體吞吐量。 | B5 負載與排隊 |
| Traffic Jam（塞車：一次暫時問題造成長時間積壓） | 一個暫時性的問題造成工作積壓，問題消失後，回應時間仍長時間偏高，而且波動很大。 | B5 負載與排隊 |
| Falling Dominoes / Retry Storm（骨牌效應／重試風暴） | 一個元件失敗，連帶引發其他元件的效能失敗。常見機制是大量、立即、沒有上限的重試。 | B5 負載與排隊 |
| Are We There Yet? / Is Everything OK?（到了沒？：過度輪詢與狀態檢查） | 檢查事件或平台狀態（電量、磁碟空間等）的頻率遠高於它實際變化的頻率；也包括過度頻繁地寫狀態 log。 | B5 負載與排隊 |
| Premature Optimization（過早最佳化） | 還沒量測證明是瓶頸，就為了速度犧牲可讀性或正確性。 | B6 最佳化判斷本身出錯 |
| Over-Caching（過度快取） | 快取了不值得快取的東西，或快取層疊得太多。 | B6 最佳化判斷本身出錯 |
| Cache Without Invalidation（沒有失效策略的快取） | 快取了資料，卻沒定義資料何時過期，或來源改變時怎麼讓快取失效。 | B6 最佳化判斷本身出錯 |
| Event Subscription Leak（事件訂閱沒有解除） | 訂閱者向生命週期比自己長的事件來源註冊了處理器，卻從不解除。 | C1 記憶體洩漏 |
| Ever-Growing Static Collection（只加不刪的 static 或單例集合） | static 或單例的集合只會加入、從不移除。 | C1 記憶體洩漏 |
| Unbounded Cache（沒有上限的快取） | 快取既沒有大小上限，也沒有淘汰策略。 | C1 記憶體洩漏 |
| Closure Capture Leak（閉包捕獲造成的洩漏） | 長壽的委派、lambda 或回呼意外抓住了大物件或 `this`，讓它們跟著活很久。 | C1 記憶體洩漏 |
| Resource Not Released（資源沒有釋放） | 檔案、連線、socket、handle 等資源在不再需要時沒有釋放。 | C2 作業系統資源與配置策略 |
| Object Pool Misuse（物件池誤用） | 在不該用物件池的地方用了池，或使用池的方式錯誤。 | C2 作業系統資源與配置策略 |
| Temporary Large Objects / LOH Fragmentation（暫存大物件／大物件堆碎片） | 反覆配置短命的大物件。在 .NET 中，85,000 bytes 以上的物件會放進大物件堆（Large Object Heap, LOH）。 | C2 作業系統資源與配置策略 |
| Duplicated State（同一份資料兩份存法） | 同一個事實在記憶體裡存了兩份以上，靠程式記得同步。例如清單中的物件之外，又另存一份「目前選取的物件」副本；或資料庫、記憶體快取、UI 各自一份。 | D. 狀態一致性（State Consistency） |
| Redundant or Contradictory State（可推導卻另存的狀態／會互相矛盾的狀態） | 另外存了可以從其他狀態算出來的值，例如 fullName、總數、isEmpty；或用多個旗標描述同一件事，旗標之間可能互相矛盾，例如 isSending 與 isSent 同時為… | D. 狀態一致性（State Consistency） |
| Swallowed Exception（吞掉例外／空 catch） | catch 住例外之後什麼都不做，或只做沒有意義的事。 | E. 可觀測性（Observability） |
| Ignored Return Value / Error Code（忽略回傳值或錯誤碼） | 呼叫一個會回報成功與否或錯誤碼的函式，卻不檢查結果。 | E. 可觀測性（Observability） |
| Silent Fallback / Failing Slowly（靜默降級：默默改用預設值繼續跑） | 遇到錯誤或缺漏時，默默改用預設值、空集合或舊資料繼續執行，卻不通知任何人。 | E. 可觀測性（Observability） |
| Silent Failure in Background Tasks（背景任務靜默失敗） | 丟到執行緒池或背景執行的任務拋了例外，卻沒有人察覺。 | E. 可觀測性（Observability） |
| Excessive Logging / Logging in Hot Path（log 過多／在熱路徑寫 log） | log 量多到影響效能，或把有用的訊息淹沒。 | E. 可觀測性（Observability） |
| Insufficient Logging（log 過少或缺少關鍵細節） | 重要事件沒有記錄，或記錄了卻缺少能定位問題的細節。 | E. 可觀測性（Observability） |
| No Metrics（沒有度量） | 系統沒有量化的健康指標，只能靠使用者回報或翻 log 才知道出了問題。 | E. 可觀測性（Observability） |

## [測試·資料·設定·註解](06-test-data-config.md)（89 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Obscure Test（晦澀測試） | 讀者一眼看不出這個測試在驗證什麼行為。 | A1 看不懂 |
| Eager Test（貪心測試） | 一個測試方法同時驗證受測物件的好幾個方法或行為。 | A1 看不懂 |
| Mystery Guest（神秘客） | 測試依賴外部資源（檔案、資料庫裡的列、環境變數），但光讀測試本身看不到那份資料的內容。 | A1 看不懂 |
| General Fixture（過度泛用的前置資料） | setUp 建好一大包資料，但每個測試只用到其中一部分。 | A1 看不懂 |
| Assertion Roulette（斷言輪盤） | 一個測試裡有多個沒附說明的斷言，失敗時看不出是哪一個。 | A1 看不懂 |
| Conditional Test Logic（測試中的條件邏輯） | 測試裡有 if、switch、for、while，每次跑可能走不同路徑。 | A1 看不懂 |
| Magic Number Test（魔術數字測試） | 斷言裡出現沒說明意義的數字。 | A1 看不懂 |
| Lazy Test（懶惰測試） | 好幾個測試用同一份 fixture 驗同一個產品方法，只是各看不同的欄位。 | A1 看不懂 |
| Test Code Duplication（測試碼重複） | 同一段準備或驗證程式碼，在多個測試裡（或同一測試裡）一再出現。 | A1 看不懂 |
| Readability-Blind Testing（只看抓不抓得到 bug、不看可讀性）〔部分查證：非文獻固定名稱，是依來源整理的合成條目〕 | 評價測試只問「能不能抓到 bug、有沒有綠」，不檢查測試是否清楚到可以當規格讀。 | A1 看不懂 |
| Unknown Test（不明測試） | 測試方法裡沒有任何斷言，也沒宣告預期的例外。 | A2 會騙人 |
| Empty Test（空測試） | 測試方法裡沒有可執行的敘述（常見是整段被註解掉），卻回報通過。 | A2 會騙人 |
| Redundant Assertion（多餘斷言） | 斷言的預期值和實際值是同一個東西，永遠成立（或永遠不成立）。 | A2 會騙人 |
| Ignored Test（被忽略的測試） | 被 @Ignore、@Disabled、skip 標記而不執行的測試。 | A2 會騙人 |
| Exception Handling（測試自己處理例外） | 測試用自寫的 try／catch 或 throw 處理例外，而不是用框架內建的例外斷言。 | A2 會騙人 |
| Duplicate Assert（重複斷言） | 同一個測試裡對同一個條件斷言好幾次。 | A2 會騙人 |
| Redundant Print（多餘輸出） | 測試裡留著 print 或 console 輸出。 | A2 會騙人 |
| Buggy Tests（有 bug 的測試） | 測試本身有錯，產品沒壞它說壞，或產品壞了它說沒壞。 | A2 會騙人 |
| Erratic Test（不穩定測試；flaky test） | 同一個測試，有時過、有時不過，或換個人、換個環境就不同結果。 | A3 不穩定 |
| Interacting Tests（互相干擾的測試） | 一個測試的結果，取決於別的測試先跑過沒有、留下了什麼。 | A3 不穩定 |
| Resource Optimism（資源樂觀） | 測試樂觀假設外部資源（目錄、檔案、資料表）一定存在或一定不存在，狀態也剛好對。 | A3 不穩定 |
| Test Run War（測試執行戰爭） | 只有一個人跑時都正常，多人或多個 CI 工作同時跑就互相打架。 | A3 不穩定 |
| Sleepy Test（嗜睡測試） | 用 sleep 等待非同步結果。 | A3 不穩定 |
| Fragile Test（脆弱測試） | 產品碼做了不影響受測部分的修改，測試卻編譯失敗或執行失敗。 | A4 太黏實作 |
| Over-mocking / Overspecified Software（過度 mock、過度指定） | 大量用 mock 取代依賴，並斷言「哪個方法被用什麼參數呼叫了幾次」，而不是驗證結果。 | A4 太黏實作 |
| Testing Implementation, Not Behavior／Change-Detector Test（測實作不測行為／變更偵… | 測試驗證的是程式碼「怎麼做」（內部呼叫順序、私有方法、資料結構），而不是對使用者「做出什麼」。 | A4 太黏實作 |
| Sensitive Equality（敏感的相等比較） | 用 toString() 之類的字串輸出來判斷物件是否相等。 | A4 太黏實作 |
| Indirect Testing（間接測試） | A 的測試類別，其實在透過 A 測 B 的功能。 | A4 太黏實作 |
| Slow Tests（慢測試） | 測試慢到開發者不會每次改完就跑。 | A5 太貴 |
| Manual Intervention（需要人手介入） | 跑測試前或跑到一半要有人手動操作，或要人用眼睛確認結果。 | A5 太貴 |
| Frequent Debugging（經常需要除錯） | 大多數測試失敗時，光看輸出判斷不出問題，必須開除錯器或到處加 print。 | A5 太貴 |
| High Test Maintenance Cost（測試維護成本過高） | 每加一個新功能，就得大改既有測試，新功能開發因此變慢。 | A5 太貴 |
| Test Logic in Production（產品碼裡的測試邏輯；van Deursen 稱 For Testers Only） | 產品碼裡有只為了測試才存在的邏輯，或偵測到「正在被測試」就改變行為。 | A6 測試滲入產品碼 |
| Hard-to-Test Code（難測的程式碼） | 程式碼結構讓它很難寫自動化測試。 | A7 專案層 |
| Developers Not Writing Tests（開發者不寫測試） | 團隊沒有為會出錯的程式碼寫自動化測試。 | A7 專案層 |
| No Test Suite（無測試專案） | 整個專案沒有可自動執行的測試，或測試早已不能執行。 | A7 專案層 |
| Production Bugs（正式環境 bug 過多） | 投入了自動化測試，系統測試或正式環境的 bug 數量還是太高。 | A7 專案層 |
| Constructor Initialization（用建構子初始化測試） | 測試類別用建構子而不是 setUp 方法準備狀態。 | A8 測試框架用法小味道（tsDetect 規則） |
| Default Test（預設範本測試） | 工具自動產生的範例測試類別（例如 Android 的 ExampleUnitTest）沒刪也沒改名。 | A8 測試框架用法小味道（tsDetect 規則） |
| Jaywalking（亂穿馬路：逗號分隔清單） | 把多個值用逗號串成一個字串，塞進同一個欄位。目標「Store Multivalue Attributes」／反模式「Format Comma-Separated Lists」／解… | B1 邏輯設計 |
| Naive Trees（天真樹：只存父節點） | 階層資料只在每一列存 parent_id（Adjacency List，鄰接串列），卻需要查整棵子樹或所有祖先。目標「Store and Query Hierarchies」／反… | B1 邏輯設計 |
| ID Required（一律要 id 主鍵）〔部分查證〕 | 不管合不合適，每張表都放一個名叫 id 的自動遞增代理鍵（surrogate key，沒有業務意義的流水號主鍵）。目標「Establish Primary Key Convent… | B1 邏輯設計 |
| Keyless Entry（無鑰匙進入：不宣告外鍵）〔部分查證〕 | 為了「簡化」或擔心效能，不宣告外鍵約束，把參照完整性交給應用程式碼。目標「Simplify Database Architecture」／反模式「Leave Out the Co… | B1 邏輯設計 |
| Entity-Attribute-Value（實體-屬性-值，EAV）〔部分查證〕 | 用一張通用表 (entity_id, attr_name, attr_value) 存所有可變屬性。目標「Support Variable Attributes」／反模式「Use… | B1 邏輯設計 |
| Polymorphic Associations（多型關聯）〔部分查證〕 | 一個外鍵欄位依另一個「型別」欄位的值，指向不同的父表。目標「Reference Multiple Parents」／反模式「Use Dual-Purpose Foreign Ke… | B1 邏輯設計 |
| Multicolumn Attributes（多欄位屬性）〔部分查證〕 | 用 tag1、tag2、tag3 這類編號欄位存同一種屬性的多個值。目標「Store Multivalue Attributes」／反模式「Create Multiple Col… | B1 邏輯設計 |
| Metadata Tribbles（元資料分裂：複製表或欄）〔部分查證〕 | 把資料值編進表名或欄名，例如 sales_2023、sales_2024，或 revenue_2023 欄位。目標「Support Scalability」／反模式「Clone … | B1 邏輯設計 |
| God Table（上帝表） | 一張表塞了過多欄位，承載好幾種概念。 | B1 邏輯設計 |
| Overloaded Attribute Names（同名不同型的欄位） | 不同表裡有同名欄位，型別卻不同。 | B1 邏輯設計 |
| Meaningless Name（無意義的名稱） | 表名或欄位名稱晦澀、沒有意義（例如 t1、col_a、flag2）。 | B1 邏輯設計 |
| Opaque Blob for Structured Data（把結構化資料塞成單一 blob 或 JSON）〔部分查證：非 Karwin… | 把需要查詢、約束或個別更新的結構化資料，整包存成 JSON、XML 或序列化物件，放進一個欄位。 | B1 邏輯設計 |
| Rounding Errors（捨入誤差）〔部分查證〕 | 用 FLOAT 或 DOUBLE 存需要精確的小數，例如金額。目標「Use Fractional Numbers Instead of Integers」／反模式「Use FLO… | B2 實體設計 |
| 31 Flavors（31 種口味：把可選值寫死在欄位定義） | 用 ENUM、CHECK 約束或觸發器，把允許的值清單寫在欄位定義裡。目標「Restrict a Column to Specific Values」／反模式「Specify V… | B2 實體設計 |
| Phantom Files（幽靈檔案）〔部分查證〕 | 認定圖片等大型媒體「一定要」存成外部檔案，資料庫只存路徑。目標「Store Images or Other Bulky Media」／反模式「Assume You Must Us… | B2 實體設計 |
| Index Shotgun（索引亂槍）〔部分查證〕 | 沒有計畫地加索引：沒加、加太多，或加了用不到的。目標「Optimize Performance」／反模式「Using Indexes Without a Plan」／解法「MEN… | B2 實體設計 |
| Fear of the Unknown（害怕未知：NULL 誤用）〔部分查證〕 | 把 NULL 當普通值用，或反過來用普通值（-1、空字串、'1900-01-01'）假裝 NULL。目標「Distinguish Missing Values」／反模式「Use … | B3 查詢寫法 |
| Ambiguous Groups（模稜兩可的分組）〔部分查證〕 | SELECT 裡放了既沒分組、也沒聚合的欄位，期望資料庫「自動挑對的那一列」。目標「Get Row with Greatest Value per Group」／反模式「Refe… | B3 查詢寫法 |
| Random Selection（隨機選取） | 用 `ORDER BY RAND() LIMIT 1` 取隨機樣本。目標「Fetch a Sample Row」／反模式「Sort Data Randomly」／解法「In No… | B3 查詢寫法 |
| Poor Man's Search Engine（窮人的搜尋引擎）〔部分查證〕 | 用 LIKE '%關鍵字%' 或正規表示式做全文搜尋。目標「Full-Text Search」／反模式「Pattern Matching Predicates」／解法「Use t… | B3 查詢寫法 |
| Spaghetti Query（義大利麵查詢）〔部分查證〕 | 想用一條 SQL 一次解決複雜的多步驟問題。目標「Decrease SQL Queries」／反模式「Solve a Complex Problem in One Step」／解… | B3 查詢寫法 |
| Implicit Columns（隱式欄位）〔部分查證〕 | 在程式碼裡用 SELECT * 或省略欄位清單的 INSERT。目標「Reduce Typing」／反模式「a Shortcut That Gets You Lost」／解法「N… | B3 查詢寫法 |
| Readable Passwords（可讀密碼） | 明文或可逆地存密碼。目標「Recover or Reset Passwords」／反模式「Store Password in Plain Text」／解法「Store a Sal… | B4 應用程式和資料庫的接縫 |
| SQL Injection（SQL 注入） | 把未經驗證的輸入直接串進 SQL，當成程式碼執行。目標「Write Dynamic SQL Queries」／反模式「Execute Unverified Input As Co… | B4 應用程式和資料庫的接縫 |
| Pseudokey Neat-Freak（偽鍵潔癖）〔部分查證〕 | 刪除資料後，想重新編號主鍵來填補空號。目標「Tidy Up the Data」／反模式「Filling in the Corners」／解法「Get Over It」。 | B4 應用程式和資料庫的接縫 |
| See No Evil（視而不見：忽略資料庫錯誤）〔部分查證〕 | 不檢查資料庫 API 的回傳值或例外，也不看實際執行的 SQL。目標「Write Less Code」／反模式「Making Bricks Without Straw」／解法「R… | B4 應用程式和資料庫的接縫 |
| Diplomatic Immunity（外交豁免：SQL 不守工程規範）〔部分查證〕 | 認為 SQL 和資料庫是二等公民，不適用版本控制、測試、文件、審查這些工程實務。目標「Employ Best Practices」／反模式「Make SQL a Second-C… | B4 應用程式和資料庫的接縫 |
| Magic Beans（魔豆：Model 就是 Active Record）〔部分查證；2010 年版的章節，2022 年版已換成 Sta… | MVC 的 Model 直接繼承資料存取類別（Active Record，一個物件對應資料表一列），讓資料表結構等於領域模型。目標「Simplify Models in MVC」… | B4 應用程式和資料庫的接縫 |
| Standard Operating Procedures（標準作業程序：因循使用預存程序）〔部分查證：章名經出版社頁面確認；內文只看過搜… | 2022 年版第四部分新增的章節。真正的反模式（節名「Follow the Leader」，跟著前人走）不是預存程序本身，而是「因為以前都這樣做」就沿用某項技術；預存程序只是最典… | B4 應用程式和資料庫的接縫 |
| N+1 Queries（N+1 查詢） | 先用 1 條查詢取回 N 筆資料，接著在迴圈裡逐筆存取關聯資料，又觸發 N 條查詢。 | B4 應用程式和資料庫的接縫 |
| Lazy Loading Traps（延遲載入陷阱） | 依賴 ORM 的 proxy（代理物件：看起來像資料，存取時才去資料庫抓）在任意位置隱性查詢；或反過來，把關聯全設成預設立即載入。 | B4 應用程式和資料庫的接縫 |
| Hard-coded Configuration（寫死的設定） | 會隨部署環境改變的值（主機、port、路徑、逾時、外部服務網址），用常數寫在程式碼裡。 | C1 值放錯地方 |
| Hard-coded Secrets（寫死的密鑰與憑證） | 密碼、API key、私鑰、token 直接寫在程式碼或進版控的設定檔裡。CWE-798（Use of Hard-coded Credentials）。 | C1 值放錯地方 |
| Scattered Magic Literals（魔術數字散落） | 沒有名字、意義不明的數字或字串，直接寫在程式碼各處。 | C1 值放錯地方 |
| Config Sprawl / Multiple Sources of Truth（設定散落、多個來源不同步）〔部分查證：名稱是整理用語〕 | 同一個設定值在多個檔案或系統裡各存一份，誰為準不清楚，日久就不一致。 | C2 多個來源 |
| Snowflake Server / Configuration Drift（雪花伺服器、設定漂移） | 伺服器靠人手一次次調整，變成獨一無二、無法重現的狀態（像雪花，世上沒有兩片一樣）。 | C2 多個來源 |
| Environment Branching in Code（環境判斷寫進程式：if (isDev)）〔部分查證：名稱是整理用語〕 | 業務邏輯依「目前是哪個環境」走不同的程式路徑。 | C3 環境差異寫進程式 |
| Feature Toggle Debt（功能旗標債） | 功能旗標（feature toggle，用設定開關新功能的機制）用完不刪，越積越多。 | C3 環境差異寫進程式 |
| Copy-Pasted Build / CI Scripts（建置與 CI 腳本複製貼上） | 同樣的建置步驟、CI 工作流程、專案設定，在多個檔案或 repo 裡複製貼上。 | C4 建置與 CI 腳本 |
| CI Specification Misuse（CI 設定誤用） | Gallaba 和 McIntosh 研究 9,312 個使用 Travis CI 的專案，歸納出四種 CI 設定反模式。 | C4 建置與 CI 腳本 |
| Missing or Inconsistent Lockfile（版本鎖缺漏或不一致） | 沒有提交 lockfile，或 lockfile 和依賴宣告檔不同步，或同一個 repo 裡不同模組鎖了同一套件的不同版本。 | C5 依賴宣告與版本鎖 |
| Dependency Smells（依賴宣告壞味道） | Jafari 等人（TSE 期刊，ICSE 2022 journal-first）研究 1,146 個 JavaScript 專案，整理出 7 種依賴壞味道：Pinned Dep… | C5 依賴宣告與版本鎖 |
| Implementation Configuration Smells（設定碼實作層壞味道） | Sharma 等人 2016 年從 Puppet 風格指南和 Puppet-Lint 規則整理出 13 種實作層壞味道：Missing Default Case（case 沒有 … | C6 IaC（用程式碼描述基礎設施） |
| Design Configuration Smells（設定碼設計層壞味道） | 同一篇研究的 11 種設計層壞味道：Multifaceted Abstraction（一個抽象管多件事）、Unnecessary Abstraction（空的類別或模組）、Imp… | C6 IaC（用程式碼描述基礎設施） |
| IaC Security Smells（IaC 安全壞味道）〔部分查證：前六項經後續論文逐字確認，第七項 Suspicious comme… | Rahman、Parnin、Williams（ICSE 2019 傑出論文〈The Seven Sins〉）從 Puppet 腳本歸納出 7 種安全壞味道：Admin by de… | C6 IaC（用程式碼描述基礎設施） |
| Comments That Explain What, Not Why / Deodorant Comments（解釋 what 不解釋 … | 註解在重述程式碼做了什麼，用來掩蓋程式碼本身不清楚（Fowler《Refactoring》把它比喻成除臭劑，蓋住臭味而不是除掉臭源）。 | D. 文件與註解壞味道 |
| Outdated / Misleading Comments（過期或誤導的註解） | 程式碼改了，旁邊的註解沒改，現在描述的是不存在的行為。 | D. 文件與註解壞味道 |
| TODO / FIXME Accumulation（TODO 與 FIXME 堆積；Self-Admitted Technical Deb… | TODO、FIXME、HACK、XXX 這類「之後再處理」的註解一直留著，數量只增不減。 | D. 文件與註解壞味道 |
| Journal Comments / Version Narrative in Code（日誌式註解：把版本敘事寫進程式碼）〔部分查證：C… | 在程式碼註解裡記錄修改歷程、版本、日期、作者，例如「2024-03-01 改為…」「v2 新增」「原本是 X，後來改成 Y」「Bob 修了 #123」。 | D. 文件與註解壞味道 |
| Commented-Out Code（被註解掉的程式碼）〔部分查證：Clean Code 原書未直接查閱〕 | 整段程式碼被註解掉，但沒刪除。 | D. 文件與註解壞味道 |

## [可讀性與度量](07-readability-metrics.md)（39 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Cognitive Complexity（認知複雜度） | SonarSource 提出、專門衡量「人讀懂這段控制流有多難」的分數；與 Cyclomatic 不同，它刻意不管「可測路徑數」，只管「讀者要多費力」。 | A. 函式內的控制流負荷 |
| Cyclomatic Complexity（循環複雜度／McCabe 複雜度） | 控制流程圖上「線性獨立路徑」的數目，實務上 ≈ 決策點數 + 1；原始設計目的是衡量**可測性**（要幾條測試路徑），不是可讀性 。 | A. 函式內的控制流負荷 |
| NPath Complexity（NPath 複雜度） | 一個方法從頭到尾的「非循環執行路徑」總數；同一區塊內的結構會**相乘**，所以隨序列分支呈指數成長 。 | A. 函式內的控制流負荷 |
| Arrow Code / Deep Nesting（箭頭型程式碼／過深巢狀） | 條件層層包住，程式縮排往右推成箭頭形狀 （Jeff Atwood, 2006）。 | A. 函式內的控制流負荷 |
| Complex Conditional（複雜條件式） | 單一布林運算式裡塞了太多 `&&`、`／／`、`!`，讀者要在腦中解真值表。 | A. 函式內的控制流負荷 |
| Bumpy Road（顛簸路） | CodeScene 的函式層壞味道——「函式沒把責任封裝好，裡面有好幾塊各自獨立的巢狀邏輯」；像顛簸的路一樣拖慢閱讀 。 | A. 函式內的控制流負荷 |
| Callback Hell / Pyramid of Doom（回呼地獄／毀滅金字塔） | 非同步回呼層層巢狀，程式往右長成金字塔 。 | A. 函式內的控制流負荷 |
| Long Read Path / Bend Count（讀路徑過長／拐彎數） | 為了弄懂「一個構想從頭到尾怎麼完成」，讀者必須跳轉、記住前提、修正誤解的次數。本條是本文件為「人讀起來累」整理的**審查經驗法則**，不是業界標準度量。 | B. 跨函式／跨類別的讀路徑 |
| Middle Man（中間人） | 一個類別的大部分方法都只是把呼叫轉交給另一個類別 。 | B. 跨函式／跨類別的讀路徑 |
| Pass-Through Method（純轉接方法） | 方法除了把參數原樣傳給另一個（通常簽章相同的）方法之外什麼都不做 （Ousterhout《A Philosophy of Software Design》紅旗之一）。 | B. 跨函式／跨類別的讀路徑 |
| Shallow Module（淺模組） | 介面的複雜度跟它提供的功能差不多，甚至更多——用它的成本幾乎等於自己寫 （Ousterhout）。 | B. 跨函式／跨類別的讀路徑 |
| Message Chains（訊息鏈） | `a.b().c().d()`——呼叫端沿著物件結構一路導航 。 | B. 跨函式／跨類別的讀路徑 |
| Indirection Hell（間接層過多） | 為了「彈性」疊了太多層介面、工廠、轉接，每層都很薄。 | B. 跨函式／跨類別的讀路徑 |
| Yo-yo Problem（溜溜球問題） | 要理解一個方法的行為，必須在繼承階層裡上上下下來回看（super 呼叫、override、template method 交錯）。最早由 Taenzer、Ganti、Podar（… | B. 跨函式／跨類別的讀路徑 |
| Poltergeist（騷靈類別） | 短命、通常沒有狀態的物件，只負責初始化或呼叫另一個類別的方法，本身不添加有意義的功能 （Brown 等《AntiPatterns》1998）。 | B. 跨函式／跨類別的讀路徑 |
| Scattered State Writes（狀態寫入點散落） | 同一個欄位、容器或共享狀態，被許多檔案、許多方法直接寫入，沒有單一出入口。讀者要知道某一刻的值，得把所有寫入點都看過。 | C. 狀態所有權散落 |
| Global Data（全域資料） | 任何地方都能讀寫的資料（全域變數、類別靜態可變欄位、單例中的可變狀態）（Fowler 2nd ed 壞味道）。 | C. 狀態所有權散落 |
| Mutable Data（可變資料） | 資料在一處被改，另一處以為它沒變，導致意外結果 （Fowler 2nd ed 壞味道）。 | C. 狀態所有權散落 |
| Shotgun Surgery（散彈式修改） | 每次做一個改動，都得到許多類別各改一小處 。與 Divergent Change（發散式變化：一個類別因許多不同理由被改）相反 。 | C. 狀態所有權散落 |
| Temporal Coupling（時序耦合） | 類別的兩個以上成員之間有隱含的時間關係，呼叫端必須先呼叫其中一個再呼叫另一個 （Mark Seemann, 2011）。典型是 `Initialize()` 方法 。 | C. 狀態所有權散落 |
| Hidden Side Effects / CQS Violation（隱藏副作用／違反命令查詢分離） | 名字看起來是查詢（只讀），實際上會寫入狀態。Command-Query Separation（命令查詢分離，Bertrand Meyer 提出）：方法要嘛是**查詢**（回傳結果… | C. 狀態所有權散落 |
| Linguistic Antipatterns（語言學反模式，LA） | 一個程式實體的**名字、文件（註解）與實作**之間不一致的重複型態；Arnaoudova、Di Penta、Antoniol 首先在 CSMR 2013 提出，2016 年於 E… | D. 名實不符 |
| Naming Smells（命名壞味道：Mysterious / Vague / Hard-to-Pick Name） | 名字沒有清楚傳達「這是什麼、做什麼、怎麼用」。 | D. 名實不符 |
| Comment Smells affecting readability（影響可讀性的註解壞味道） | 註解與程式不一致、重複程式、或把本該寫進程式結構的資訊塞進註解。 | E. 註解（只寫與可讀性有關的部分；完整註解壞味道見 [0… |
| Long Method / LOC（過長方法／程式行數） | 方法或檔案的行數過多。LOC（Lines of Code）的計法各工具不同（實體行、邏輯行 NCSS、IL 指令推估）。 | F. 量化度量 |
| Long Parameter List（過長參數列） | 方法參數太多，呼叫端要記住順序與意義。 | F. 量化度量 |
| WMC — Weighted Methods per Class（類別加權方法數，CK 度量） | 類別中所有方法複雜度的總和；權重可用 Cyclomatic，或每個方法都算 1（此時等於方法數）（Chidamber & Kemerer 1994，CK 度量組共 6 項：WMC… | F. 量化度量 |
| DIT / NOC — Depth of Inheritance Tree / Number of Children（繼承深度／直接子類別… | DIT = 類別到根類別的最長繼承路徑；NOC = 直接子類別數 。 | F. 量化度量 |
| CBO / RFC / Class Coupling（物件間耦合／類別回應集合／類別耦合） | CBO = 與本類別耦合的其他類別數；RFC = 本類別方法數 + 其直接呼叫的外部方法數（RFC' 為遞迴全呼叫版）。Visual Studio 的 Class Couplin… | F. 量化度量 |
| LCOM family / TCC / LCC（方法內聚缺乏度各版本／緊密與鬆散類別內聚度） | 衡量類別中的方法是否共用同一批欄位；共用越少 = 越不內聚 = 越像好幾個類別硬湊在一起。 | F. 量化度量 |
| Fan-in / Fan-out（扇入／扇出） | Fan-in = 有多少其他元件呼叫或傳資訊給本元件；Fan-out = 本元件呼叫或傳資訊給多少元件 。Henry & Kafura（1981，IEEE TSE SE-7(5)… | F. 量化度量 |
| Halstead Metrics（Halstead 度量） | 以運算子與運算元的種類數與出現次數推算「程式量」。n1、n2 = 相異運算子、運算元數；N1、N2 = 總出現次數。詞彙量 n = n1+n2；長度 N = N1+N2；**Vo… | F. 量化度量 |
| Maintainability Index（可維護性指數，MI） | 由 Halstead Volume、Cyclomatic Complexity、行數合成的單一分數 。 | F. 量化度量 |
| God Class（上帝類別）偵測策略 | 集中系統智慧、什麼都做、還大量取用小資料類別資料的類別 。 | G. 偵測策略（Detection Strategies：… |
| Feature Envy（依戀情結）偵測策略 | 方法用別的類別的資料比用自己類別的還多 。 | G. 偵測策略（Detection Strategies：… |
| God Method / Brain Method（上帝方法／腦方法）偵測策略 | 過長、分支多、用到大量變數的方法 。 | G. 偵測策略（Detection Strategies：… |
| Refused Parent Bequest（拒絕父類遺贈）偵測策略 | 子類別幾乎不用父類別給的東西，卻又不是小類別 。 | G. 偵測策略（Detection Strategies：… |
| Metric Fixation / Goodhart's Law（度量固著／古德哈特定律） | 把度量當目標後，度量就失效。Goodhart（1975）原文：「任何觀察到的統計規律，一旦被施壓用於控制，就會傾向崩潰」；Strathern（1997）的通行說法：「當一個量測變… | I. 數字不是判決 |
| Hotspot Analysis（熱點分析：變動頻率 × 複雜度） | 只看複雜度會找到一堆「很複雜但沒人碰」的程式；把版本控制的**變動頻率**和**複雜度（或大小、健康度）**相乘，才找到「又難讀、又常被改」真正花成本的地方 （Adam Torn… | I. 數字不是判決 |

## [AI 寫碼與演化](08-ai-and-evolution.md)（23 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| Reinvented Helper（重複造輪子） | 專案裡已經有能用的函式，模型沒去找，自己又寫一個差不多的。 | A. 看不到全貌（context-blind） |
| Copy-Paste Instead of Refactor（複製取代重構） | 需要相似邏輯時，複製一段改幾個字，而不是把共同部分抽出來或搬到共用處。 | A. 看不到全貌（context-blind） |
| Hallucinated API / Package（幻覺 API／幻覺套件） | 呼叫不存在的函式、參數、設定鍵，或 import、安裝根本不存在的套件。 | A. 看不到全貌（context-blind） |
| Stale API（過時 API） | 用了已棄用（deprecated）或舊版的 API，因為訓練資料裡舊寫法比較多。 | A. 看不到全貌（context-blind） |
| Architecture Bypass（繞過既有架構） | 直接在當下檔案裡把需求做完，跳過專案既定的分層、介面或服務。例如 domain（業務邏輯）層直接 import 資料庫。 | A. 看不到全貌（context-blind） |
| Convention Drift（慣例漂移：命名與錯誤處理風格） | 同一專案裡，同一種東西有好幾種命名，同一層函式有好幾種錯誤處理方式（有的丟例外、有的回 None、有的回 `{"error": ...}`）。 | A. 看不到全貌（context-blind） |
| Multiple Sources of Truth（同一事實多份來源） | 同一個常數、設定、規則、列舉值或 schema 在好幾處各寫一份。 | A. 看不到全貌（context-blind） |
| Speculative Abstraction & Unused Parameters（預防性抽象與無用參數） | 為了「將來也許用得到」加介面、工廠、設定選項、參數，但目前只有一個用法，或根本沒人用。 | B. 做太多（overeager） |
| One-off Helper Proliferation（一次性小函式泛濫） | 把只用一次的兩三行邏輯包成獨立函式，函式名只是把內容再說一遍。 | B. 做太多（overeager） |
| Defensive Overdose（過度防禦） | 對內部保證不會發生的情況，加 null 檢查、型別檢查、try/catch、fallback（備援路徑）。 | B. 做太多（overeager） |
| Narrative Comments（敘事型註解） | 註解在講「這裡做了什麼」「這次改了什麼」「原本是 X、現在改成 Y」，而不是「為什麼這樣做」。 | B. 做太多（overeager） |
| Leftover Debug & Dead Code（殘留除錯碼與死碼） | 除錯用的 print／console.log、寫死的測試值、註解掉的舊碼、臨時腳本，跟著提交進去。 | B. 做太多（overeager） |
| Swallowed Errors & Silent Fallback（吞錯與靜默降級） | catch 所有例外後什麼都不做、只印一行、或回傳預設值，讓呼叫端以為成功了。 | C. 遮住問題（masking） |
| Symptom Patch（只修症狀） | 在錯誤冒出來的位置加判斷或 try/catch 讓它不再報錯，卻不追壞值是從哪來的。 | C. 遮住問題（masking） |
| Test Tampering（竄改或刪除測試求綠燈） | 測試失敗時去改測試、刪測試、加 skip，或 monkey-patch（執行期替換）評分程式，而不是修被測的程式。 | C. 遮住問題（masking） |
| Test Special-Casing / Hardcoded Expected Values（為測試特判／寫死期望值） | 程式偵測到測試輸入就直接回傳期望值，或把測試的期望值直接寫進產品碼。 | C. 遮住問題（masking） |
| Bug-Enshrining Tests（把現況當正確答案的測試） | 先跑實作，再把當下的輸出抄進斷言，於是測試驗的是「程式現在做什麼」，不是「規格要求什麼」。 | C. 遮住問題（masking） |
| Short-Term Churn & Hotspots（短期重改與熱點） | 剛寫好的程式碼兩三週內又被改或刪（churn）；長期來看，一個又大又常被改的檔案（hotspot，熱點）。 | D. 演化壞味道（change smells） |
| Change Coupling（變更耦合） | 兩個以上的檔案總在同一個 commit 一起改，但程式碼上看不出它們有依賴關係。 | D. 演化壞味道（change smells） |
| Shotgun Fix（散彈式修改） | 一個邏輯上單一的修正，卻得在很多檔案各改一小處。 | D. 演化壞味道（change smells） |
| Fix-the-Fix / Incomplete Fix（修補的修補） | 同一個 bug 被修了不只一次，因為第一次修得不完整或修錯。 | D. 演化壞味道（change smells） |
| Whack-a-Mole Regression（修一個冒一個） | 修好 A 弄壞 B，修 B 又弄壞 C，一直循環。 | D. 演化壞味道（change smells） |
| Big-Batch Change（巨型變更批次） | 一次提交或一個 PR 改很多檔、很多行，還混了多種目的（修 bug＋重構＋格式化＋新功能）。 | D. 演化壞味道（change smells） |

## [本機實戰](09-local-knowledge.md)（48 條）

| 條目 | 一句定義 | 所在節 |
|---|---|---|
| A-01 狀態所有權散落（同一組狀態多處改，沒有單一出入口） | 一個 private 容器（Dictionary／HashSet／List）的增刪改點散在多個檔、多個方法；每處都「合法地」改同一組狀態，漏改一側不報錯、不出訊號，只在下游長出無… | A1 狀態與資料所有權 |
| A-02 同一事實存兩份（衍生值另存／雙存） | 同一份資料、或可由別的資料算出的值，被另外存一份；某條更新路徑只改其中一份。 | A1 狀態與資料所有權 |
| A-03 共用可變參考被當成私有狀態改 | （案例）遊戲專案乙野怪案第二根因：同種野怪共用設計表快取的那本字典，打 A 隻、B 隻跟著掉血【試過：回放實驗找到，遊戲專案乙核真】。 | A1 狀態與資料所有權 |
| A-04 內部可變集合直接外漏 | 回傳內部集合的直接引用，呼叫方可以增刪；對方迭代時被改會丟例外。 | A1 狀態與資料所有權 |
| A-05 static 狀態跨生命週期殘留 | （案例）遊戲專案甲用戶端某個補給快捷使用資料類別的兩個 static Dictionary 在登出／換角時不清（實例 `Clear()` 不碰 static），舊 session… | A1 狀態與資料所有權 |
| A-06 多份手列「全清清單」 | 同一組容器的清空在兩處以上各自逐個 `Clear()`，新增容器要每處都記得。 | A1 狀態與資料所有權 |
| A-07 同一欄位粗細兩來源互相覆寫 | 一個精確但偶發、一個粗略但高頻的來源都無條件寫同一欄位，粗略的把精確的洗掉；值都合法，所以不報錯。 | A1 狀態與資料所有權 |
| A-08 兩份「同源」定義靠人工同步（鏡像檔、手工翻譯、生成碼手改） | （案例）遊戲專案甲用戶端的共用腳本 16 檔在 Main 與 IL 兩側靠手動＋檔頭 10 行驚嘆號警告維持同步；報告原話：「10 行驚嘆號警告本身就是壞味道的信號」【文件】。後… | A1 狀態與資料所有權 |
| A-09 手寫逐欄映射漏接新欄位 | （案例）某專案給一個傳輸用的摘要資料物件加 `content` 欄，接收端解析器手寫逐欄重建、漏接這一欄；單元／整合測試全綠（測的是物件層），真線路上欄位全空，靠真 server… | A1 狀態與資料所有權 |
| A-10 靜默失敗／空 catch 吞例外 | （案例）遊戲專案甲用戶端空 catch 6 項 P0，含網路連線基底類別 6 處（網路層錯誤完全靜默）、程式進入點檔裡一處空 catch 旁註解「// 應該不需處理啥..?」【文… | A2 失敗沒有訊號 |
| A-11 把正常中間狀態當失敗，而且全部靜默 | （案例）遊戲專案乙「部隊停死在半路」五個誤判逐個修、修一個冒一個；病根一個：把正常的中間狀態當失敗，且全部靜默【讀碼】。三方歸納遊戲專案乙兩案共同形狀：「狀態所有權散在多處、失敗… | A2 失敗沒有訊號 |
| A-12 狀態消失不出聲，或原因用字串 | Remove／Cancel／End／Clear 類 API 不帶原因、不留紀錄；或原因用字串，錯字靜默分裂成不同去重 key。 | A2 失敗沒有訊號 |
| A-13 安全機制被註解掉 | （案例）遊戲專案甲用戶端網路系統類別的 `Update()` 外層 try-catch 被整段註解，每幀入口（網路執行與模組管理器更新兩個呼叫）完全裸露，任何網路例外即整個 cl… | A2 失敗沒有訊號 |
| A-14 async void | （案例）遊戲專案甲用戶端 35 項 P0，含熱修、UI、地圖、建築管理等核心系統（例外無法被 await 捕捉 → 靜默崩潰）【文件】。遊戲專案乙規則 CR-003：async … | A2 失敗沒有訊號 |
| A-15 事件訂閱不退訂 | （指標）`+=` 與 `-=` 配對數；Unity MonoBehaviour 要有 OnDestroy 保底退訂。 | A3 生命週期與資源 |
| A-16 隱性初始化時序耦合 | 初始化有先後順序，但順序沒寫在讀者會經過的地方；或 Refresh 類方法被某個 Init 提早呼叫，讀到還沒建好的欄位。 | A3 生命週期與資源 |
| A-17 常駐每幀回呼（用輪詢代替事件） | 物件大多時間閒著、只在短段「過渡」有事，卻註冊常駐 Update／Tick。把 N 條常駐收成 1 條 Tick 仍是輪詢，使用者不算解。 | A3 生命週期與資源 |
| A-18 巨型類別（God Class） | （指標）遊戲專案甲報告用「>1,000 行」與 public 方法數；但使用者原則：行數／方法數只當「值得看一眼」的線索，不進計數規則（見 B-01）。 | A4 結構膨脹 |
| A-19 近乎複製的平行類別 | （案例）某個全服對戰活動管理類別（1,503 行）與它的跨服版本（1,304 行）「幾乎複製」，差異僅資料來源，合計 2,807 行；整改優先提取共用基類【文件】。 | A4 結構膨脹 |
| A-20 樣板地獄（Handler／PackHandler） | （案例）遊戲專案甲伺服器 500+ 個地圖伺服器 handler（以 attribute 標記）中 98.8% 同一結構（反序列化 → 呼叫 Manager → 判錯誤碼回覆），… | A4 結構膨脹 |
| A-21 參數爆炸＋資料泥團 | （案例）遊戲專案甲伺服器 28+ 個方法 ≥6 參數；武將強化屬性計算方法 11 參數、道具管理類別的發獎方法 9 參數；同一組審計參數（原因、角色、來源 ID、備註）在發獎、扣… | A4 結構膨脹 |
| A-22 原始型別執念 | （案例）遊戲專案甲伺服器型別安全 ID 0 個，characterId／guildId／itemId／playerId 全是 `uint`，三個 uint 參數傳錯順序編譯不報；… | A4 結構膨脹 |
| A-23 Manager 蛛網耦合 | （案例）A-19 那對活動管理類別，跨服版透過 `Server.XxxMgr` 依賴 27 個 Manager、本服版 26 個；修改一個 Manager 介面可能影響 26 個… | A4 結構膨脹 |
| A-24 過度泛型／被迫寫空殼 | （案例）遊戲專案甲伺服器每個 DataModule 繼承 5 型態參數泛型基類，前 3 個在全部 Module 完全一樣；306 個 DataModule 檔中 43+ 個為了符… | A4 結構膨脹 |
| A-25 只改一欄卻整包推送 | （案例）遊戲專案甲武將資料模組的「子資料變髒」回呼，每次組 20+ 欄位的武將子資料封包整包推給 client，只改等級一欄也一樣；VIP、玩家快取、背包模組同模式；根因是框架一… | A4 結構膨脹 |
| A-26 單一構想拐超過三個彎 | 從「這個構想要做什麼」到「做到了」之間，讀者必須換脈絡才能續追的點（間接層、條件分支、跨檔跳轉）。使用者原話：「單一構想的實際完成邏輯，如果腳本內必須先拐三個彎，這種設計必定有貓… | A5 讀路徑與可讀性 |
| A-27 讀路徑過長（委派鏈＋巢狀；沒 bug 但人讀要跳很多層） | 程式沒錯、測試會過，但讀者要開四五個檔、穿過介面／工廠／基類才懂。使用者原話：「你們只針對了實際發生的 BUG 寫出測試，但是沒有寫出『人讀的時候就要跳超過 3 層、以及腦袋必須… | A5 讀路徑與可讀性 |
| A-28 巢狀過深 | （案例）見 A-27 的巢狀分量（背包購買道具方法巢狀 15、地圖模組通知玩家實體方法 17）。掃碼重構 SOP 用「縮排深度＋方法行數」量化挑重災區。 | A5 讀路徑與可讀性 |
| A-29 純轉接（一行原樣轉呼叫） | 方法體只有一行呼叫、引數原樣傳過去（override 不算）。 | A5 讀路徑與可讀性 |
| A-30 partial 切分軸混雜 | 同一型別切成多片，但切法混了功能、機制、生命週期等多種軸；或每片都改同一組可變狀態。 | A5 讀路徑與可讀性 |
| A-31 方法名藏副作用 | （案例）遊戲專案甲商隊管理類別的同步鏈（送完整資料給 client → 送軍團資料給 client → 載入時對帳軍團 → 對帳軍團貨車 → 清掉過期軍團貨車 → 廣播軍團資料，… | A5 讀路徑與可讀性 |
| A-32 public 但只有自己用 | （案例）遊戲專案甲軍團管理類別 187 個 public 入口中 16 個類別外無人呼叫（例：檢查團長到期、標記 client 資料待同步）【試過】；[全貌] 歸在「分太細」。 | A5 讀路徑與可讀性 |
| A-33 註解污染 | 註解埋版本／階段標記、日期戳、事件敘事；生造詞、一句塞三層轉折；逐行把程式照翻一遍（使用者指為 AI 生硬感的來源）。 | A5 讀路徑與可讀性 |
| A-34 命名不一致與拼錯傳播 | （案例）查歷史排行榜的方法名把 History 拼成 Histroy，同一拼錯出現在兩個檔（複製貼上傳播）；另一個 handler 名稱把 Chest 拼成 Ches；handl… | A5 讀路徑與可讀性 |
| A-35 魔術數字 | （案例）遊戲專案甲伺服器 150+ 處（送包警告門檻常數直接 `= 4096` 無註解、建構區域物件時直接傳 `10`、戰報容量常數寫成「收藏容量 `+ 20`」）；client… | A5 讀路徑與可讀性 |
| A-36 死碼與註解碼累積 | （案例）遊戲專案甲伺服器註解碼 1,051 處／176 檔、`#if false` 41 處／32 檔、TODO／FIXME／HACK／XXX 等約 219 處，合計約 1,27… | A6 死碼與半成品 |
| A-37 入口沒接（功能做了一半） | 伺服器端入口寫好了，但只有測試指令（或沒人）能呼叫，玩家按不到。 | A6 死碼與半成品 |
| A-38 協定兩端沒對上 | （案例）遊戲專案甲地圖伺服器（C2M＝用戶端送往地圖伺服器：server handler 494、client 發送 492）——server 有 handler 但 clien… | A6 死碼與半成品 |
| A-39 字串型反射橋接 | （案例）遊戲專案甲用戶端的模組查詢轉接類別 165 個方法全用字串方法名反射呼叫 IL 側；熱修系統的 `Invoke(string, string, …)` 估計 42+ 個呼… | A7 跨邊界與效能 |
| A-40 熱路徑反射零快取 | （案例）模組查詢轉接類別每次呼叫都完整走 `GetMethod` 反射鏈，沒有任何快取；報告估 0.5–1 ms/幀（估計值，未見實測）【文件】。 | A7 跨邊界與效能 |
| A-41 跨界過度交互（chatty 查詢） | （案例）CharacterID（session 內不變）、CharacterName（只在改名時變）與 Gold 共用同一條無快取的反射路徑，每幀多次跨 Main → IL；修法… | A7 跨邊界與效能 |
| A-42 手動推棧呼叫 | （案例）遊戲專案甲用戶端的建築管理類別 6 個方法用 `BeginInvoke`＋`PushObject／PushInteger／PushReference` 呼叫 IL 方法，… | A7 跨邊界與效能 |
| A-43 熱路徑線性搜尋／每幀多餘工作 | （案例）聊天好友列表面板 10 處 `List.Find／FindIndex`，每次聊天更新都線性掃好友列表【文件】；`Debug.Log` 未條件編譯 2,182 處（[RA]… | A7 跨邊界與效能 |
| A-44 第三方框架肥大 | （案例）遊戲專案甲用戶端的第三方套件資料夾 942 檔，佔 Main 工程 40%；違反使用者「框架層應薄」的偏好【文件】。判定：成本不對稱，不修（見 A-附）。 | A7 跨邊界與效能 |
| A-45 沒有自動化測試 | （案例）遊戲專案甲 server、client 都是 0 個測試專案；唯一「測試」是一支黑盒壓測機器人。報告把它列為核心根因：「缺乏自動化測試 → 不敢重構 → 技術債越堆越高」… | A8 專案層 |
| A-46 跨工程沒有一致性驗證 | （案例）遊戲專案甲的協定編號、錯誤碼、通用定義三組常數要在 Server＋Main＋IL 三方同步，全靠手動；出錯時是 enum 值偏移 → 封包路由到錯的 handler → … | A8 專案層 |
| A-47 條件編譯裡混遊戲邏輯 | （案例）聊天可編輯文字元件 7 處 `#if UNITY_EDITOR ／／ UNITY_STANDALONE`、聊天網路管理類別的 `#if UNITY_EDITOR` 內有邏… | A8 專案層 |
| A-48 修了又修的熱點檔 | （指標）同一程式檔 14 天內被兩筆以上 fix 提交改到＝可能在修症狀。 | A8 專案層 |

