# C# 遊戲開發：可讀性、降低複雜度與優良設計準則全集（正面清單）

> 範圍：回答「怎樣算好、怎麼量得出來」。壞味道的長相與成因不重寫，只在每條後面點名「違反它會長出哪一類壞味道」。
> 分工：Unity 客戶端危險清單、遊戲開發通用危險清單由別處維護；C# Server 危險見同資料夾 `全面CSharpServer危險彙整.md`。
> 既有知識（不重寫，用「既有」欄指節號）：`../Research/code-smells/` 的 `07-readability-metrics.md`（簡稱 07，含度量總表、工具一覽、Bend Count）、`09-local-knowledge.md`（簡稱 09，含使用者原則 B-01～B-30）、`README.md` §1 核心觀念（簡稱 R1）、`01`～`06` 各檔（簡稱 01…06）。
> 本檔的新增價值：每條正面準則的「可數判法＋反例→正例」、輕量與穩健設計、遊戲特有的可讀設計、給 LLM 的 30 行索引。

---

## 0. 讀法與尺

### 0.1 欄位
每條固定五欄：準則一句｜為什麼｜判法｜反→正｜壞味道｜來源與既有。

- 判法標記：【數】可數的數字或個數｜【grep】可用 rg 搜出特徵｜【工具】Roslyn 或分析器能量｜【問】只能人（或帶證據的 LLM）回答一個問句。
- 來源標記：【官】本次檢索直接得到官方或一手頁面內容｜【書】書籍、論文、談話，本次只見二手摘要、未開原文，引述請回查原文｜【經驗】查不到出處，或屬業界慣例與本機慣例。
- 數字一律是「審查線」不是判決（07 §I、R1-2、09 B-02）。要引用外部工具預設值，查 07 總表，不在此重抄。

### 0.2 優先序（抄自使用者的種子規則，本檔不得與之相反）
正確與安全邊界 > 使用者這次的目標 > 真實限制 > 專案現有做法 > 可讀可驗證的簡單 > 最小修改面 > 個人語法偏好。極簡永遠排在正確後面。

### 0.3 三把總尺
1. 使用者的尺：資料能攤成二維表就該直觀；少綁定；讀的人腦中直接浮現資料的長相與流向；一個檔案看完一件事。
2. 人讀預算：跳層超過三層、單一構想拐超過三個彎、巢狀 =3 審查 ≥4 重構（09 B-03/B-04/B-05）。
3. Ousterhout 的三個症狀：改一處要動很多處（變更放大）、讀者要記太多（認知負荷）、不知道自己不知道什麼（未知的未知）。每條準則至少壓住其中一個。【書】

### 0.4 與外部意見衝突時的取捨（先分類再比大小）
| 外部說法 | 本檔取捨 | 理由 |
|---|---|---|
| Clean Code：函式越小越好（2～4 行） | 不採行數導向；採「抽出需 ≥2 處呼叫或能用一個名詞命名且有實質內容」 | 與種子一致；Ousterhout 與 Martin 公開討論的主要爭點即極短函式造成淺介面與糾纏（`github.com/johnousterhout/aposd-vs-clean-code`）【官】 |
| Rule of Three（出現三次再抽） | 取「必須同步變更的知識」第 2 次出現才抽 | 種子寫法；文字相似不算重複 |
| Cyclomatic 當人讀指標 | 人讀用 Cognitive、測試案例數才用 Cyclomatic | 07 A 兩條已比較 |
| 一律 DI／ECS／事件匯流排 | 工具非教條；先直接引用，痛了才加（5.5） | Unity 社群與業界多數輕量派意見，但多屬論壇二手 |
| 註解越少越好 | 註解寫「為什麼」與限制，白話；不逐行翻譯 | 種子「註解白話」、09 B-19 |
| Go／Rust 的明確性 | 只借「明確、扁平、錯誤在呼叫處可見」，不借語法 | C# 有例外機制，語意不同（6.4） |

### 0.5 本檔不涵蓋
效能微調的完整清單（見 05）、Unity 生命週期與 GC 的危險細節（見 03 Unity 節與客戶端危險清單）、安全與反作弊（04）。

---

## 1. 讀者認知負荷：跳層、拐彎、命名、匿名

### 1.1 讀任何一行時，要同時記住的活東西不超過 3 件
- 為什麼：短期記憶中心容量約 4 個意元，3 是留餘裕的線。
- 判法：【問】讀這一行，我必須同時記得哪幾件事（活變數、已成立條件、目前在哪一層）？數 >3 就要整理。
- 反→正：三層 if 各守一個獨立條件，且中途還有兩個暫存變數 → 先踢例外、暫存變數就近宣告並縮短壽命。
- 壞味道：Arrow Code、Bumpy Road、暫存變數蔓延。
- 來源：Cowan 的工作記憶研究【書】｜既有：07 §0、07 A

### 1.2 為了看懂一個行為要打開的定義不超過 3 層（人讀跳層）
- 為什麼：每跳一層，讀者要記住「剛從哪來」；超過三層多數人丟失上下文。
- 判法：【數】從入口出發，用「到定義」或 Call Hierarchy 追到資料真正被讀寫的那一行，數跳數；刻意分層（每層有獨立責任、可只讀一層就停）不算跳。
- 反→正：`Click → Controller → Service → Manager → Handler → Helper` 逐層轉手 → 入口直接呼叫一個有實質內容的函式。
- 壞味道：Middle Man、Pass-Through Method、Indirection Hell、Yo-yo。
- 來源：使用者審查原則；Ousterhout 的 pass-through 方法批評【書】｜既有：07 §B Long Read Path、09 B-03、B-10

### 1.3 單一構想的完成邏輯拐彎不超過 3 個
- 為什麼：一個彎＝讀者多記一件事或視線離開畫面；第四個彎開始忘記從哪來。
- 判法：【數】把資料從輸入到結果寫成形狀鏈 `A→B→C→D`，箭頭 >3 就是壞味道；每個箭頭代表換容器、換單位、換座標、換語意之一。
- 反→正：`string → Dictionary<string,object> → List<Tuple> → Dto → Entity → ViewModel` → 表格列 `readonly struct` 一路讀到底。
- 壞味道：轉換鏈、Primitive Obsession、Feature Envy。
- 來源：使用者審查原則（無業界標準度量）｜既有：07 §B Bend Count、09 B-04、R1-9

### 1.4 名字用使用者世界的名詞
- 為什麼：名字是最便宜的文件；名實不符要讀者自己修正心中模型。
- 判法：【問】企劃或美術看到這個名字，知道它是什麼嗎？【grep】`\b(data|tmp|temp|info|obj|stuff|val)\d*\b`、`Manager|Helper|Util|Handler` 結尾的類別，逐個問「它的名詞是什麼」。
- 反→正：`Process(data2)` → `ApplyDamage(damageRow)`；`ItemManager` → `ItemShop` 或 `Backpack`（能說出名詞才留）。
- 壞味道：Mysterious Name、Linguistic Antipatterns。
- 來源：Code Complete 命名章、Clean Code 命名章可取部分【書】；可讀性模型把識別字一致性與文字連貫納入特徵（Scalabrino 等人的 Readability 研究）【書】｜既有：07 §D、01 B

### 1.5 一個概念一個名字，一個名字一個概念
- 為什麼：同義詞讓讀者懷疑是兩件事；一詞多義讓讀者誤以為是同一件事。
- 判法：【grep】同一概念的候選詞各搜一次（`hp|health|life`、`fetch|get|load|retrieve`），主詞外的殘留應為 0；【數】專案詞彙表（表頭欄名）外的新縮寫數。
- 反→正：`GetItem / FetchItem / LoadItem` 三種並存 → 查表叫 `Get`、讀檔叫 `Load`，各只一種意思。
- 壞味道：Inconsistent Names、Divergent Change 的前兆。
- 來源：經驗｜既有：01 B Inconsistent Names、07 §D

### 1.6 減少匿名：沒名字的數字、型別、函式
- 為什麼：匿名東西讀者要猜；種子明訂「減少匿名」。
- 判法：【grep】邏輯內的字面數字（排除 0、1、-1 與 `const` 宣告行）；`Tuple<`、`(int, int, int)` 出現在公開簽章；`object[]`、`Dictionary<string, object>`；【數】超過 3 行的匿名 lambda。
- 反→正：`if (type == 3)` → `if (type == ItemType.Potion)`；`return (a, b, c)` → `readonly record struct Range(int Min, int Max, int Step)`。
- 壞味道：Magic Number、Primitive Obsession、Data Clumps。
- 來源：種子「減少匿名」｜既有：01 B Magic Number、09 B-15

### 1.7 呼叫處讀得出意思
- 為什麼：呼叫處是最常被讀的地方；`Foo(true, false, 3)` 要跳去簽章才懂。
- 判法：【grep】呼叫處的 `true|false|null` 字面引數；【數】同一簽章連續 ≥2 個 bool 參數。
- 反→正：`Spawn(npc, true, false)` → 命名引數 `Spawn(npc, isBoss: true, isHidden: false)`，或換成 enum／旗標 enum。
- 壞味道：Flag Argument、Mysterious Name。
- 來源：經驗（C# 命名引數語法見官方文件）｜既有：01 A Long Parameter List

### 1.8 註解寫「為什麼」與限制，白話一句一義
- 為什麼：命名與結構承載不了的是理由、限制、陷阱；逐行翻譯程式只會與程式漂移。
- 判法：【問】這個看起來奇怪的寫法旁，有沒有一句原因？【數】與下一行同義的註解 =0；【grep】`TODO|HACK|FIXME` 是否帶原因與對象。
- 反→正：`// 迴圈 i 從 0 到 n` → `// 反向走，因為移除會改動後面的索引`。
- 壞味道：Comments（遮蓋壞碼）、說謊的註解。
- 來源：Ousterhout 主張註解承載設計理由，Martin 主張程式自證；本檔取前者並與種子「註解白話」一致【官】（兩人公開討論 repo）｜既有：09 B-19、06 D

### 1.9 一個函式停在同一個抽象層級
- 為什麼：高階步驟與位元、字串細節混寫，讀者每行都要切換尺度。
- 判法：【問】這個函式的每一行，是否都能用同一種「層級」的詞描述？【數】超過約 60 行時問「它有幾個名詞」，不設行數硬線（種子：能用一個名詞命名才抽）。
- 反→正：`LoadLevel` 裡穿插 `BitConverter` 與路徑拼接 → 高階步驟「讀表、建場景、放怪」各自寫成有名詞的函式；若名詞講不出，就留在原處。
- 壞味道：Long Method、Bumpy Road。
- 來源：Code Complete（一個例程一個層級）【書】｜既有：01 A Long Function、07 A Bumpy Road

### 1.10 一個檔案看完一件事
- 為什麼：跨檔跳轉就是跳層；種子要求跨檔抽取必須換來重用、隔離或責任邊界。
- 判法：【數】理解一個功能要開的檔案數 ≤2（本檔＋一張資料表）；【問】這個檔案裡有沒有兩個互不呼叫的主題？partial 分片先問責任軸、再問同一欄位被幾片寫入，不報片數。
- 反→正：`Player.cs`、`Player.Combat.cs`、`Player.UI.cs`…五片共寫同一欄位 → 欄位寫入點收回單一入口，再依責任軸決定要不要分。
- 壞味道：Shotgun Surgery、Divergent Change、God Class 的症狀。
- 來源：種子「一個檔案看完一件事」｜既有：09 B-01、B-08、07 §C

---

## 2. 控制結構與扁平化

### 2.1 巢狀深度：≤2 免談、=3 審查、≥4 重構（只管本次寫或改的段落）
- 為什麼：三層各守獨立條件，讀者要同時記三件事；既有巢狀不要求順手重構（種子）。
- 判法：【數】縮排粗篩（扣掉 namespace、class、method 的基準層）；【工具】Roslyn 走語法樹算 if／for／foreach／while／switch／try／lambda 的最大包含深度；=3 時問：三層是否各守一個獨立條件？是→壓平，否（同一局部決策仍直線可追）→可留。
- 反→正：`if (a) { if (b) { if (c) {...} } }` → `if (!a) return; if (!b) return; if (!c) return; ...`。
- 壞味道：Arrow Code、Callback Hell。
- 來源：種子；Code Complete 第 19.4 節〈Taming Dangerously Deep Nesting〉【書】；Sonar S134 預設 3（見 07 總表）｜既有：09 B-05、07 A Arrow Code

### 2.2 先踢例外，讓主路徑不縮排（guard clause／迴圈內 continue、break）
- 為什麼：主路徑留在最左邊，讀者一眼看到「正常時發生什麼」；Go 社群稱為 line of sight。
- 判法：【數】函式前段的提早離開數 ≥ 前提條件數；【問】把縮排拿掉，主路徑是不是連續一列？
- 反→正：`foreach (var e in list) { if (e.Alive) { if (e.InRange) { Hit(e); } } }` → `if (!e.Alive) continue; if (!e.InRange) continue; Hit(e);`。
- 壞味道：Arrow Code、Complex Conditional。
- 來源：種子「壓平第一步」；Go 社群 happy path 靠左的寫法【書】｜既有：09 B-05

### 2.3 複雜條件命名；if 鏈變長就查表
- 為什麼：條件是句子，給它主詞；同形的長 if 鏈本質是表。
- 判法：【數】單一條件含 ≥3 個 `&&`／`||`（對照 Sonar S1067 預設）就命名；同一變數連續 ≥4 個同形 if／case 就改表。【grep】`else if` 連續 ≥4。
- 反→正：`if (hp > 0 && !stunned && mp >= cost && cd <= 0)` → `bool canCast = ...` 或 `CanCast(unit, skill)`；`if (t==A) x=1; else if (t==B) x=2;…` → `static readonly Dictionary<Type,int>` 或陣列索引。
- 壞味道：Complex Conditional、Repeated Switches、Conditional Complexity。
- 來源：種子「壓平第二步」｜既有：07 A Complex Conditional、01 C

### 2.4 巢狀來自重複搜尋，就預建索引
- 為什麼：兩層 for 找對應，既深又慢；索引把它降成一次查詢，常順便降複雜度。
- 判法：【數】for／foreach 內再呼叫 `Find`、`FirstOrDefault`、`Contains`（List）的處數；【grep】`foreach .* \{\s*$` 之後的 `.Find(`。
- 反→正：`foreach (var q in quests) foreach (var n in npcs) if (n.Id == q.NpcId) ...` → 先 `var npcById = npcs.ToDictionary(n => n.Id);` 再 `npcById[q.NpcId]`。
- 壞味道：Arrow Code、白做的工（見 05）。
- 來源：種子「壓平第三步」｜既有：09 B-05

### 2.5 同一語義可選時，取「讀者要記的狀態最少」的構件
- 為什麼：構件階梯：直線 > guard／early return > 有界迭代（for-each、map／filter）> 單層分支 > 無界迴圈 > 遞迴 > 高階抽象。
- 判法：【問】這段若改用上一級構件是否等價？是→降級；【grep】`while (true)`、`goto`、泛型約束鏈、反射呼叫的出現處逐個問「為何不是上一級」。
- 反→正：用 `while (true)` 加 `break` 走一個已知長度的陣列 → `for` 或 `foreach`。
- 壞味道：Speculative Generality、metaprogramming 過度。
- 來源：種子「結構」｜既有：09 B-05

### 2.6 遞迴與狀態機只用在天然遞迴、且深度可界定、狀態本身是問題的地方
- 為什麼：遞迴要記呼叫鏈，狀態機要記整張轉移表。
- 判法：【問】遞迴深度的上界能用常數或資料性質說出來嗎？狀態機的每個狀態是不是企劃會講的名詞？兩題答不出就不用。
- 反→正：用遞迴走一個「最多三層」的選單 → 兩層 `foreach`；用狀態機表達「是否顯示紅點」→ 一個 bool。
- 壞味道：Speculative Generality、過度設計。
- 來源：種子｜既有：09 B-05

### 2.7 扁平化不過頭
- 為什麼：為壓層數製造一次性小函式，只是把跳層換成跳函式。
- 判法：【數】抽出的函式呼叫點 ≥2，或能講出一個名詞且內容實質；【grep】只被呼叫一次且名稱是動詞片語加數字或 `Part2` 的私有方法。
- 反→正：`ProcessStep1/2/3` 三個只被呼叫一次的方法 → 原地以空行與一句註解分段。
- 壞味道：Lazy Element、Bumpy Road、Yo-yo。
- 來源：種子；Ousterhout 對極短方法的批評【官】｜既有：09 B-06

### 2.8 LINQ 與鏈式：一條鏈 ≤3 個運算子、無副作用，熱路徑不用
- 為什麼：鏈太長等於把巢狀橫放；LINQ 在逐幀路徑會配置（Unity 手冊明示避免）。
- 判法：【數】單一鏈 `.` 運算子 ≤3、lambda 內不寫入外部狀態；種子：comprehension 只准一層 for 一層 if。【grep】`Update|FixedUpdate|LateUpdate` 方法體內的 `using System.Linq` 呼叫（`.Where(`、`.Select(`、`.ToList(`）應為 0。
- 反→正：`list.Where(a).Select(b).GroupBy(c).OrderBy(d).ToList()` 寫進 Update → 預建清單，迴圈填入、重用。
- 壞味道：Callback Hell 的橫向版、配置熱點（見 05）。
- 來源：Unity 手冊 programming best practices 明列避免在 Update 等熱路徑使用 LINQ【官】｜既有：03 集合與 LINQ

### 2.9 switch expression 與 pattern matching 只用在「值對值」與型別分派
- 為什麼：`switch` 運算式窮舉清楚、無 fallthrough；塞進多語句副作用分支就變成難讀的小程式。
- 判法：【數】每個 arm ≤1 個運算式；巢狀 pattern ≤1 層；【工具】編譯器對非窮舉 switch 運算式發警告（enum 仍可能傳入未定義數值，故保留 discard arm 並丟出明確例外，執行期為 `SwitchExpressionException`）。
- 反→正：`switch (kind) { case A: Foo(); Bar(); state = 2; break; ... }` 十個分支 → 值對值用 `kind switch { A => 10, B => 20, _ => throw new ArgumentOutOfRangeException(nameof(kind)) }`；需要副作用的分支留為普通 `switch` 並各呼叫一個具名方法。
- 壞味道：Complex Conditional、Repeated Switches、靜默 default。
- 來源：Microsoft Learn〈Patterns〉與〈switch expression〉【官】｜既有：03 語言構件濫用

### 2.10 三元運算子與表達式體：只放單一運算式，不巢狀
- 為什麼：運算式體讓「值」一眼是「值」；巢狀三元把控制流藏進運算式。
- 判法：【grep】`\?[^;]*\?[^;]*:`（單行巢狀三元）應為 0；【數】表達式體成員 ≤1 個運算式、無副作用、無需註解解釋即可讀。
- 反→正：`a ? b ? 1 : 2 : 3` → 兩行 if 或 switch 運算式。
- 壞味道：Complex Conditional。
- 來源：經驗｜既有：—

---

## 3. 資料優先與少綁定

### 3.1 資料能攤成二維表（列×欄）就用表的樣子寫，打開就看得懂
- 為什麼：一列一個實體、一欄一個屬性，是最低抽象、最易想像的形狀；此方向優先於任何套件、格式或框架的方便（種子）。
- 判法：【問】能不能把這份資料整份貼進試算表而不需要解釋？【數】欄位名是否與企劃表頭一致；一個「實體」需要的巢狀容器層數 ≤1。
- 反→正：`Dictionary<int, Dictionary<string, List<object>>>` → `ItemRow[]`＋`Dictionary<int, ItemRow>` 索引。
- 壞味道：Primitive Obsession、Message Chains。
- 來源：使用者的尺；與資料導向設計同向但動機不同（Acton：轉換資料才是程式的目的，著眼快取與硬體；本檔著眼人讀）【書】｜既有：09 B-13（輕量）

### 3.2 資料型別不綁序列化格式
- 為什麼：種子「少綁定」：資料不必綁某種序列化格式或大量自動產生的物件。綁了之後，改格式要改所有使用端。
- 判法：【數】資料型別檔案裡框架屬性（`[ProtoMember]`、`[JsonProperty]`、`[MessagePackObject]`）的種類數：核心資料型別應為 0，轉接層才有；【問】把序列化函式庫整個換掉，要動幾個檔？
- 反→正：遊戲邏輯直接吃 `[ProtoContract]` 類別 → 邏輯吃純 `readonly struct`，邊界轉接層負責與 proto 互轉。Unity 的 `[Serializable]` 若是引擎強制的真實限制，寫明代價，不當作理想形狀。
- 壞味道：Indecent Exposure、Shotgun Surgery。
- 來源：種子；Hickey〈Simple Made Easy〉：簡單＝不糾纏（complect 的反面），綁死就是糾纏【書】｜既有：09 B-09（複雜源自兩個本該正交的東西被綁死）

### 3.3 自動產生的程式碼不算優點；若採用，表是正本、生成物不手改且可讀
- 為什麼：產生碼綁了套件，卻失去可讀性與抽象思考空間；取用彈性優先，自動產生只是好讀之後順帶的延伸（種子）。
- 判法：【數】生成碼行數對手寫邏輯行數的比；生成器輸入檔 ≤1 份；【問】刪掉生成器後，生成物是否仍是人能維護的碼？
- 反→正：每張表產一堆 `GetXxxByYyy` 屬性類別 → 一個通用 `Table<TRow>` 加 `TryGet(id, out row)`。
- 壞味道：Speculative Generality、Data Class 爆量。
- 來源：種子｜既有：—

### 3.4 值域小就寫成 enum，別用 byte 或 int 裸值
- 為什麼：只有 5 種值就寫 5 個值的 enum；開成 byte（0～255），讀的人得猜哪些值合法（種子點名反例）。
- 判法：【grep】`const (byte|int) .*= *\d+;` 連續成組的常數；欄位名含 `Type|Kind|State|Mode` 且型別為 `int|byte`；【數】合法值個數 ≤ 約 8 卻用數字。
- 反→正：`byte state; // 0閒置 1移動 2攻擊` → `enum UnitState { Idle, Move, Attack }`。
- 壞味道：Primitive Obsession、Magic Number。
- 來源：種子｜既有：01 A Primitive Obsession

### 3.5 讓非法狀態無法表示
- 為什麼：兩個 bool 構成 4 種狀態卻只有 3 種合法，就讓第 4 種存在，等於埋一個靠註解防守的洞。
- 判法：【數】合法組合數／型別能表示的組合數，應接近 1；【問】建構出一個不合法的物件，編譯器或建構函式會擋嗎？
- 反→正：`bool isOpen; bool isClosed;` → `enum DoorState { Open, Closed, Locked }`；`int? targetId` 配 `bool hasTarget` → 只留 `int? targetId`。
- 壞味道：Temporary Field、Temporal Coupling。
- 來源：「Make illegal states unrepresentable」（Yaron Minsky 的 OCaml 設計口號）【書】｜既有：07 §C Temporal Coupling

### 3.6 資料與行為分離到「資料表列是純資料，規則在處理資料的函式」
- 為什麼：列結構穩定、規則會變；讀者想看「長相」就看列，想看「流向」就看函式。
- 判法：【數】資料列型別含邏輯方法數 ≈ 0（僅 trivial 衍生屬性）；【問】這個方法只用自己的欄位嗎？是→屬於它；用別人欄位更多→Feature Envy，搬走。
- 反→正：`ItemRow.Use(Player p)` 改玩家狀態 → `ItemEffects.Apply(ItemRow row, ref PlayerState p)`。
- 壞味道：Feature Envy（相反方向則為 Data Class，兩邊都要看有無責任軸）。
- 來源：Acton「資料才是問題」【書】；Out of the Tar Pit（區分必要狀態與衍生狀態）【書】｜既有：01 G Feature Envy、F Data Class

### 3.7 取用彈性：要什麼撈什麼，不為每個欄位寫一個取值方法
- 為什麼：查詢照需求寫；欄位 getter 家族隨欄位數成長，各自再包一次轉手層。
- 判法：【數】同一張表的公開取值方法 ≤3（整列 `TryGet`、全表唯讀清單、必要的索引查詢）；【grep】`Get(Item|Skill|Npc)\w+ByID` 同前綴方法數。
- 反→正：`GetItemName(id)`、`GetItemPrice(id)`、`GetItemIcon(id)` → `Items.TryGet(id, out var row)` 後讀 `row.Name`。
- 壞味道：Middle Man、Shotgun Surgery。
- 來源：種子「取用彈性」｜既有：—

### 3.8 單一事實來源；衍生資料明標為衍生、可重建
- 為什麼：同一知識兩處定義，必有一處過時；索引、快取、彙總是衍生品，丟掉能重建才安全。
- 判法：【問】這份資料丟了，能由哪一份重建？答不出就有兩份真相。【grep】同一組常數或表欄位在兩個檔案各抄一次。
- 反→正：客戶端手抄一份伺服器的技能冷卻表 → 兩端讀同一份表，或客戶端只顯示、不裁決。
- 壞味道：Duplicated Code（同步變更的知識）、Solution Sprawl。
- 來源：Out of the Tar Pit【書】；種子「同一段必須同步變更的知識」｜既有：01 F、09 B-07

### 3.9 識別字用 int、enum 或專用小 struct，字串鍵只在邊界
- 為什麼：字串鍵無法被編譯器檢查，拼錯就是靜默 miss；專用型別讓 ID 不被當成數量。
- 判法：【grep】邏輯層 `\["[A-Za-z_]+"\]`、`Find\("`、`SendMessage\("`；【數】同一函式的 ≥2 個 `int` 參數是否都是不同種 ID。
- 反→正：`Give(int a, int b)` → `Give(ItemId item, int count)`（`readonly record struct ItemId(int Value)`）。
- 壞味道：Primitive Obsession、Stringly typed。
- 來源：經驗｜既有：01 A Primitive Obsession

### 3.10 預設不可變，可變狀態集中在少數可指認的地方
- 為什麼：資料在一處被改而另一處沒料到，是最難追的讀路徑。
- 判法：【grep】`public \w+ \w+ \{ get; set; \}` 數；【數】同一欄位的寫入點數 ≤1 個「入口」（外部寫入即報）；結構體優先 `readonly struct`、集合對外 `IReadOnlyList`。
- 反→正：`public List<Buff> Buffs;` 任人增刪 → 對外 `IReadOnlyList<Buff>`，增刪只走 `AddBuff / RemoveBuff`。
- 壞味道：Mutable Data、Scattered State Writes、Global Data。
- 來源：C# 的 readonly struct、init、IReadOnlyList 用法（官方文件有說明，本次未逐頁開啟）【經驗】｜既有：07 §C、09 B-08

---

## 4. 模組與責任邊界

### 4.1 深模組：小介面、實質功能
- 為什麼：介面是成本，功能是收益；呼叫者只需知道介面就能用對。
- 判法：【問】呼叫者要知道內部多少才用得對？【數】公開成員數 ≤約 7，且每個都有實質內容（不是純轉呼）；介面成本（參數＋前置順序）小於它省下的程式量。
- 反→正：`SaveManager` 暴露 `Open/Begin/Write/Flush/Close` 要呼叫者記順序 → `Save(slot, state)` 一個入口，順序藏在內部。
- 壞味道：Shallow Module、Temporal Coupling、Leaky Encapsulation。
- 來源：Ousterhout《A Philosophy of Software Design》（深模組、classitis）【書】｜既有：07 §B Shallow Module

### 4.2 沒有純轉接的方法與類別
- 為什麼：只換名字不加工的一層，只增加跳層。
- 判法：【數】方法體只有一個呼叫、參數原樣轉交、無驗證無轉換的方法數 =0；一個類別大半方法都是轉呼另一個類別（Middle Man）→ 刪該層。
- 反→正：`PlayerService.GetHp() => _player.Hp` → 呼叫端直接讀 `player.Hp`。
- 壞味道：Pass-Through Method、Middle Man、Poltergeist。
- 來源：Ousterhout【書】｜既有：07 §B Pass-Through、Middle Man

### 4.3 介面窄；只有一個實作、無替換計畫的 interface 不建
- 為什麼：每個 interface 都是一份要維護的契約與一次跳轉。
- 判法：【數】interface 成員 ≤約 5；【grep】`interface I\w+` 且全專案只有一個實作、不是測試縫或外部邊界者，列清單逐個問「替換的時機是什麼」。
- 反→正：`IPlayerMover` 只有 `PlayerMover` 一個實作 → 直接用類別；有第二個實作（網路版、回放版）時才抽。
- 壞味道：Speculative Generality、Unnecessary Abstraction。
- 來源：種子「不加沒被要求的抽象」｜既有：02 A1、09 B-12

### 4.4 繼承：每一層都說得出「加了什麼」
- 為什麼：說不出加了什麼的層，是讀者白跳的一層。
- 判法：【數】繼承深度 ≤2（分析器 CA1501 預設較鬆，見 07 總表）；每層補一句「這層多了或覆寫了什麼」；空覆寫或只呼叫 base 的 override 數 =0；【grep】`: \w+Base\b` 鏈、`override` 內只有 `base.X()`。
- 反→正：`Unit → Creature → LivingCreature → Monster → Boss` 中間三層各只多一個欄位 → `Unit` 加 `UnitKind` 欄位，Boss 差異走資料表。
- 壞味道：Deep Hierarchy、Rebellious Hierarchy、Refused Bequest。
- 來源：使用者原則（繼承每一層都要說得出加了什麼）；Ousterhout 對繼承的保留態度【書】｜既有：01 D、02 A4、07 §F DIT

### 4.5 只在「真的是一種」且行為會被替換時繼承，其餘用組合
- 為什麼：繼承把父類別的所有決定一併綁給子類別；組合只綁需要的那一點。
- 判法：【問】把父類別出現的位置全換成子類別，行為還合理嗎？不合理就不是 IS-A；【數】`protected` 欄位數 =0。
- 反→正：`class Boss : Monster` 為了重用 `Move()` → `Boss` 持有 `Mover`。
- 壞味道：Broken Hierarchy、Refused Bequest、Rebellious Hierarchy。
- 來源：Gang of Four 的組合優先原則【書】｜既有：02 A4

### 4.6 每個模組藏一個「可能會變的決定」
- 為什麼：資訊隱藏是深模組的主要手段；決定外洩，就變更放大。
- 判法：【數】改變一個決定（存檔格式、協定欄位、渲染後端）要動的檔案數 ≤1～2；【問】這個模組的介面裡，哪個詞洩漏了內部決定？
- 反→正：呼叫端知道存檔是 JSON 才會呼叫 `JsonConvert` → 呼叫端只知道 `Save/Load`。
- 壞味道：Leaky Encapsulation、Shotgun Surgery、Indecent Exposure。
- 來源：Parnas 資訊隱藏（1972）；Hickey〈Simple Made Easy〉【書】｜既有：01 G Indecent Exposure

### 4.7 責任一句話說得完，且不含「和」
- 為什麼：責任軸清楚，才有資格談拆與不拆；數量不是壞味道，責任軸才是。
- 判法：【問】用一句話講這個類別負責什麼，句中是否有「和／以及」？有→找軸；【數】公開方法依「使用同一批欄位」分群，群數 >1 才考慮拆。
- 反→正：`GameManager` 管場景、計時、存檔、UI → 依欄位群拆；若各群本來就互相不共享欄位，才是真拆。
- 壞味道：God Class、Divergent Change、Multifaceted Abstraction。
- 來源：單一職責原則（Martin）；使用者原則 B-01【書】｜既有：09 B-01、07 §G God Class

### 4.8 依賴單向、不成環
- 為什麼：有環就無法單獨理解任何一端。
- 判法：【工具】asmdef 或 namespace 依賴圖無環（asmdef 在 Unity 是編譯期強制）；【數】型別耦合（CA1506 預設值見 07 總表）。
- 反→正：`Inventory` 與 `Shop` 互相引用 → 抽出被兩邊共用的 `Money` 型別，或讓其中一邊改用事件。
- 壞味道：Cyclically-dependent Modularization、Hub-like Modularization。
- 來源：無環依賴原則（Martin）【書】；Microsoft Learn CA1506【官】｜既有：02 A3、07 §F CBO

### 4.9 模組作者吸收複雜度，不把設定項推給呼叫者
- 為什麼：一個模組被用很多次，把複雜度壓在模組裡，比分散在每個呼叫端划算。
- 判法：【數】建構參數與設定欄位 ≤約 5；有合理預設的選項不要求呼叫者填；【問】呼叫端最常寫的那幾行，是不是每次都一樣？是→預設值或內化。
- 反→正：`new Timer(unit, loop, ignoreScale, tick, ...)` 七個參數 → `Timer.Once(sec)`、`Timer.Repeat(sec)` 兩個入口。
- 壞味道：Long Parameter List、Leaky Encapsulation。
- 來源：Ousterhout「把複雜度往下拉」【書】｜既有：01 A

---

## 5. 輕量：不加沒被要求的東西

### 5.1 不加沒被要求的參數、設定、抽象、預防性分支
- 為什麼：每多一個選項，所有讀者與測試都要多顧一個維度；外部邊界與已知失敗模式仍要處理。
- 判法：【數】一次異動新增的參數、設定項、interface、分支數，逐個能指到需求原句；指不到的刪。【問】這個 `if` 在哪個真實輸入下會成立？
- 反→正：為「將來可能多語言」先加 `ILocalizer` 與設定檔 → 先直接取表格欄位，需要時再抽。
- 壞味道：Speculative Generality、Lazy Element。
- 來源：種子「極簡」；YAGNI（Extreme Programming）【書】｜既有：09 B-12

### 5.2 同一段「必須同步變更的知識」第 2 次出現才抽共用
- 為什麼：文字相似不等於知識相同；太早抽出的共用會被兩邊的差異拉扯。
- 判法：【問】改其中一處，另一處是否「必須」跟著改？是→抽；否→留著。【數】抽出的共用函式的旗標參數數 ≥2，通常表示抽錯了。
- 反→正：兩段各 10 行，長得像但規則不同 → 不抽；兩處都含同一個公式 → 抽成命名函式。
- 壞味道：Duplicated Code（及其反面：過早抽象）。
- 來源：種子；Muratori「語意壓縮」主張先寫直接的碼、重複出現後才壓縮（談話與部落格，本次未能取得原文）、Beck 簡單設計「無重複」【書】｜既有：09 B-07

### 5.3 簡單設計四規則：通過測試、表達意圖、無重複、元素最少
- 為什麼：Beck 的順序檢查表；「元素最少」放最後，與種子「極簡排在正確後面」一致。
- 判法：【問】依序問：(1) 驗證過了嗎？(2) 讀的人看得出意圖嗎？(3) 同步變更的知識只有一處嗎？(4) 還有可刪的類別、方法、參數嗎？前一項不過，不談後一項。
- 反→正：為了少一個方法把兩個意圖併成一個含旗標的方法 → 保留兩個，意圖優先於元素數。
- 壞味道：過度壓縮與過度設計兩端。
- 來源：Kent Beck 簡單設計四規則（規則 2 與 3 的順序，Beck 本人兩種寫法都出現過）【書】｜既有：—

### 5.4 引入框架或套件前，寫三行：換來什麼、多綁了什麼、拆掉要做什麼
- 為什麼：框架先行的代價是綁定與認知；Go 社群「少量複製勝過少量依賴」。
- 判法：【數】專案第三方依賴數與每個依賴的三行說明覆蓋率；【問】這個套件拿掉，要改幾個檔？
- 反→正：為了一個字串格式化引入整個擴充函式庫 → 十行自己寫。
- 壞味道：Solution Sprawl、Speculative Generality。
- 來源：Rob Pike〈Go Proverbs〉「A little copying is better than a little dependency」【書】｜既有：09 B-13

### 5.5 DI、ECS、事件匯流排、ScriptableObject 事件通道都是工具，不是教條
- 為什麼：先用最直接的方式（欄位引用、參數傳入、直接呼叫），有可指認的痛點再引入。
- 判法：【問】引入處是否寫得出一個具體痛點（耦合到無法單獨測、同類實體數成千上萬、熱路徑確實量到）？寫不出就不引入。
- 反→正：不到百個實體的玩法邏輯上整套 ECS 與容器 → 一般 MonoBehaviour＋少量純 C# 類別；上千同類實體且量到瓶頸才談資料導向。
- 壞味道：Speculative Generality、Indirection Hell、框架先行。
- 來源：Unity 官方論壇與社群的輕量派意見（二手，權威性弱）【經驗】；Acton 的資料導向主張在於「理解資料」，不等同採用某個 ECS 框架【書】｜既有：09 B-13

### 5.6 非-pessimization：不寫明顯多餘的工作，但不提前優化
- 為什麼：「不做白工」與「微調到極致」是兩件事；前者幾乎免費，後者要證據。
- 判法：【grep】同一幀內重複查表、每幀 new、逐元素虛擬呼叫處理同質資料；【問】同一個值同一幀被算幾次？
- 反→正：每幀 `GetComponent` 一次 → `Awake` 快取一次；但不為此引入物件池框架。
- 壞味道：白做的工、Speculative Generality（提前優化）。
- 來源：Muratori〈Performance-Aware Programming〉課程用語（本次檢索未能取得原文，標經驗）【經驗】｜既有：05

### 5.7 死碼、暫存、廢話註解當場刪
- 為什麼：死碼是對讀者的假線索。
- 判法：【工具】編譯器與 IDE 警告：未使用的私有成員（IDE0051）、未使用的欄位（CS0169）、未使用的參數、不可達碼 =0；【grep】被註解掉的程式碼區塊。
- 反→正：保留 `// old version` 整段備用 → 刪；歷史交給版控。
- 壞味道：Dead Code、Comments。
- 來源：種子｜既有：01 F Dead Code

### 5.8 新增一筆內容改動的檔案數 ≤2
- 為什麼：內容（道具、技能、關卡）是會一直長的東西，結構要讓它只長在表裡。
- 判法：【數】新增一個道具，要改的 `.cs` 檔數 =0、資料檔 ≤2；【問】要不要重新編譯？
- 反→正：新增道具要在 enum、switch、表、圖示路徑各補一次 → enum 由表產生或乾脆用整數 ID＋表。
- 壞味道：Shotgun Surgery、Combinatorial Explosion。
- 來源：經驗｜既有：01 E

### 5.9 極簡不砍可觀測性、資源釋放、資安檢查
- 為什麼：為了行數少而刪日誌、`Dispose`、驗證，是把成本轉給未來。
- 判法：【數】一個 diff 裡刪除的 `catch`、`log`、`Dispose`、驗證呼叫數，逐個要有理由；【問】這行刪了，出錯時還有誰會說話？
- 反→正：把錯誤記錄「簡化」成吞掉例外 → 保留記錄，必要時降級為 Warning。
- 壞味道：靜默失敗。
- 來源：種子「極簡不砍可觀測性」｜既有：09 B-11、R1-7

---

## 6. 穩健：邊界、fail-fast、可觀測、資源釋放

### 6.1 防禦邊界，信任內部
- 為什麼：驗證分散在每個函式，既冗又難讀；集中在邊界一次做完，內部可以放心。邊界＝輸入、網路、檔案、表、UI、外部 SDK。
- 判法：【數】內部私有方法裡的 null 與範圍檢查數，應遠少於邊界函式的；【問】這個參數的值是誰保證的？答「呼叫端」且呼叫端在內部→不重驗；答不出→它是邊界，要驗。
- 反→正：每個內部方法開頭都 `if (x == null) return;` → 邊界轉成非 null 的型別，內部不再檢查。
- 壞味道：Null Check、Special Case、防禦性過度。
- 來源：Bertrand Meyer 的契約式設計【書】；種子「外部邊界與已知失敗模式仍要處理」｜既有：01 C Null Check

### 6.2 在邊界解析成強型別，下游不再重驗（parse, don't validate）
- 為什麼：驗證只回傳 true／false，資訊被丟掉；解析回傳一個「已驗證」的型別，資訊保留在型別裡。
- 判法：【問】下游收到的是 `string/byte[]/Dictionary`，還是已驗證的 struct？【grep】邏輯層出現 `byte[]`、`JObject`、`Dictionary<string, object>`。
- 反→正：`bool IsValid(string json)` 然後到處傳 `json` → `ParseLevel(json)` 回傳 `LevelData`，失敗在此時丟出。
- 壞味道：Primitive Obsession、Special Case。
- 來源：Alexis King〈Parse, don't validate〉【書】｜既有：—

### 6.3 Fail fast：前提被破壞（程式錯誤）時立即、明確、可見地失敗
- 為什麼：吞掉錯誤繼續跑，故障延後到別處爆，原因更難找。fail fast 不減少錯誤總數，但讓錯誤容易找。
- 判法：【grep】空 `catch {}`、`catch (Exception) { }`、`catch` 後只 `return null` 的數 =0（有理由者要有註解）；【問】前提被破壞時，第一個說話的是哪一行？
- 反→正：`try { Load(); } catch { }` → 只 `catch` 預期的例外型別並記錄；程式錯誤用 `Debug.Assert`、`throw`。
- 壞味道：Swallowed Exception、靜默失敗。
- 來源：Jim Shore〈Fail Fast〉（IEEE Software 設計專欄）【官】｜既有：09 A2、B-11

### 6.4 預期的失敗與程式錯誤分流
- 為什麼：玩家輸入錯誤、檔案不在、網路斷是日常，不該用例外當控制流；bug 才該炸。Go 的「錯誤是值」在呼叫處可見；C# 對應的是 `TryXxx` 與結果型別。
- 判法：【grep】用 `try/catch` 做一般分支（`catch (KeyNotFoundException)`、`catch (FormatException)` 當控制流）=0；【數】預期失敗的 API 提供 `TryXxx` 的比例。
- 反→正：`try { return table[id]; } catch (KeyNotFoundException) { return null; }` → `table.TryGetValue(id, out var row)`。
- 壞味道：Exceptions as flow control、Null 當錯誤碼。
- 來源：Go 社群〈Errors are values〉【書】；.NET 例外使用指引（本次未逐頁開啟）【經驗】｜既有：03 例外

### 6.5 不靜默失敗：每個 fallback 都留下訊號
- 為什麼：降級是合理的，無聲降級是不可觀測；種子與核心規則的鐵律。
- 判法：【grep】`?? default`、`?? new`、`catch` 內 `return`、`continue` 的位置，旁邊必須有 log、計數或 UI 訊號；【問】使用者或維運如何知道剛剛降級過？
- 反→正：表缺了列就回傳 0 → 回傳 0 並記錄「表名-列-欄」且每種只記一次。
- 壞味道：Silent Failure、Fail-open 無告知。
- 來源：種子；核心規則可觀測性鐵律｜既有：09 A2、B-11、B-18

### 6.6 錯誤訊息帶上下文：誰、什麼 ID、期望對實際
- 為什麼：沒有上下文的訊息只能證明「出事了」。
- 判法：【數】每個 log／throw 訊息含至少一個變數；【grep】`Debug.LogError\("[^"]*"\)` 這種純字面字串。
- 反→正：`"load failed"` → `$"load level {levelId} failed: row missing column {col}"`。
- 壞味道：Mysterious Error。
- 來源：經驗｜既有：09 B-18

### 6.7 一個錯誤只在能做決定的那一處記錄與處理
- 為什麼：每層都 `catch → log → throw` 會把同一個錯誤記 N 次，真正的原因被淹沒。
- 判法：【grep】`catch` 區塊內 `log` 後立刻 `throw;` 的處數；【問】這一層有權決定「怎麼辦」嗎？沒有就別記，讓它往上。
- 反→正：三層各自記錄再丟出 → 最上層（能決定重試、提示或結束）記一次；中間層需要補上下文時用內層例外包裝。
- 壞味道：重複日誌、吞例外。
- 來源：經驗｜既有：—

### 6.8 取得與釋放配對，生命週期對稱
- 為什麼：資源（事件訂閱、委派、檔案、計時器、非託管資源）沒對稱釋放就是洩漏。
- 判法：【數】`+=` 與 `-=` 的處數應相等；`OnEnable/OnDisable`、`Awake/OnDestroy` 對稱；【grep】`IDisposable` 實例的建立點是否在 `using` 或明確的 `Dispose` 路徑內。
- 反→正：`Start` 內訂閱事件、無退訂 → `OnEnable` 訂閱、`OnDisable` 退訂。
- 壞味道：資源洩漏、事件殭屍訂閱。
- 來源：種子「資源釋放不刪」｜既有：09 A3、03

### 6.9 關鍵狀態轉移可被查到
- 為什麼：可觀測性是穩健的一部分；狀態消失要出聲。
- 判法：【問】出了問題，事後能不能回答「它是什麼時候、因為什麼進入這個狀態」？【數】移除類 API 帶 reason enum 的比例。
- 反→正：`Remove(id)` 無聲刪除 → `Remove(id, RemoveReason.Expired)` 並以去重日誌記一次。
- 壞味道：狀態消失無聲、Hidden Side Effects。
- 來源：使用者原則 B-18｜既有：09 B-18、07 §C

### 6.10 時序前提顯式表達，不靠「剛好先跑」
- 為什麼：初始化順序、呼叫順序若只存在人腦，換個人或換個機器就破。
- 判法：【問】這個物件在 `Init` 前使用會怎樣？答案若是「靜默錯」→ 該改成型別或參數表達；【grep】Script Execution Order 設定、`Awake` 內依賴別的物件已初始化。
- 反→正：`A.Awake` 依賴 `B.Awake` 先跑 → `A.Init(B b)` 由組裝處依序呼叫，或 `B` 提供 `Ready` 事件。
- 壞味道：Temporal Coupling。
- 來源：經驗｜既有：07 §C Temporal Coupling

---

## 7. 可驗證：驗證案例、等值證明、量尺

### 7.1 驗證只跑異動範圍與確實相關的案例；結尾印哨兵
- 為什麼：整組只在被點名時跑；哨兵讓結果可被機器對帳。
- 判法：【grep】驗證腳本尾行符合 `^[A-Z][A-Z0-9_]*_CHECK (PASS|FAIL)$`，exit 0／1 對應；量測腳本尾行符合 `^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$`，數字是尺不是判決，不印 PASS。
- 反→正：腳本只印一堆綠勾 → 尾行 `MYFEATURE_CHECK PASS`。
- 壞味道：不可對帳的驗證。
- 來源：種子「自檢」｜既有：—

### 7.2 行為保持的重構要有等值證明：預期值與實際值來源必不同
- 為什麼：預期值若由新碼產生，驗的是自己；預期來自舊源碼或舊產物，新產物是實際。
- 判法：【問】預期表是不是由新碼產生？是→無效。【數】order、side_effect、boundary 三類變異各至少一組。
- 反→正：寫完新函式後把它的輸出存成「預期」→ 用 regex 從舊源碼解析出預期表，再比新產物逐值。
- 壞味道：循環論證式測試。
- 來源：使用者技能 `behavior-preservation`｜既有：09 B-20、B-21

### 7.3 特徵測試（characterization／golden master）先於重構
- 為什麼：先把「實際行為」釘住，再動；紅燈代表「行為變了」，要人判斷是否本來就要變，不一定是 bug。
- 判法：【數】改前每個分支至少一組輸入輸出，邊界值（0、1、最大、最大+1、空、null）各一；【問】紅燈出現時，能不能分辨「變了」與「壞了」？
- 反→正：直接重構 → 先寫輸出快照，再重構，再比對。
- 壞味道：無安全網的重構。
- 來源：Michael Feathers《Working Effectively with Legacy Code》；approval tests／golden master 實務【書】｜既有：09 B-22

### 7.4 舊碼解析預期表：機器抽取，不手抄
- 為什麼：手抄的預期表會混入抄寫者的理解。
- 判法：【數】預期表筆數與舊碼的分支或枚舉值個數一致；【問】預期是否可由腳本重現？
- 反→正：手打 87 組 → 用 regex 或反射從舊程式碼抽出 87 組。
- 壞味道：預期失真。
- 來源：使用者技能 `behavior-preservation`；09 B-21｜既有：09 B-21

### 7.5 證據與預期不符時，不替原方案辯護
- 為什麼：先更新假設，再做能區分候選原因的最小檢查。
- 判法：【問】這次失敗後，我寫下的假設有沒有變？【數】每輪檢查排除的候選原因數 ≥1。
- 反→正：失敗後加更多修補 → 回到假設，做一個能區分兩種原因的最小實驗。
- 壞味道：Shotgun debugging。
- 來源：種子「自檢」｜既有：—

### 7.6 以陌生維護者視角順資料流重讀
- 為什麼：能連續解釋，才是真的好讀；無法連續解釋的段落就要整理（但不因此自動拆分重寫）。
- 判法：【問】找一個沒看過的人（或乾淨 context 的 LLM），只給檔案，要他複述資料流；卡住的地方是缺陷。【數】卡住次數、複述中出現的「不知道這是什麼」的名字數。
- 反→正：自己讀覺得清楚就交付 → 先做上面的複述測試。
- 壞味道：作者盲點。
- 來源：種子「自檢」｜既有：09 B-10

### 7.7 驗證要分「真 bug」與「沒 bug 但人讀要跳超過三層」兩組
- 為什麼：只用提交紀錄挑案例，會天然漏掉第二組（提交紀錄只記 bug）。
- 判法：【數】審查案例集兩組皆非空；數跳層要跨檔。
- 反→正：案例全取自 bug 修復提交 → 另挑幾個「從沒出過 bug 但沒人敢改」的檔案。
- 壞味道：驗證只測了一半。
- 來源：使用者原則｜既有：09 B-10

### 7.8 回報分清已驗證事實、推論、未知
- 為什麼：不用自信語氣填補證據缺口。
- 判法：【問】報告每個結論，能指出「我跑了什麼」嗎？
- 反→正：「應該沒問題」→「跑了 X，PASS；Y 未驗，原因 Z」。
- 壞味道：過度保證。
- 來源：種子「自檢」｜既有：—

---

## 8. 遊戲特有的可讀設計

### 8.1 Update 當調度員：只呼叫具名步驟，不寫細節
- 為什麼：Update 是讀者的入口；每幀做哪些事，一眼要列得出來。
- 判法：【數】`Update`／`FixedUpdate`／`LateUpdate` 方法體 ≤約 10 行、巢狀 ≤2；每個 MonoBehaviour 每幀工作 ≤3 項；【問】看 Update 能不能列出本物件每幀做的事？
- 反→正：Update 內 80 行含輸入、移動、動畫、瞄準 → `Update(){ ReadInput(); Move(dt); UpdateAnim(); }`，各步有名詞。
- 壞味道：Long Method、God Class。
- 來源：Robert Nystrom《Game Programming Patterns》Update Method【書】｜既有：09 B-17

### 8.2 常駐每幀回呼只留給真的每幀都有事的系統；事件與輪詢依「變化頻率」選
- 為什麼：狀態稀少變化、訂閱者多→事件；每幀都在變→直接讀。N 條 Update 收成一條 Tick 仍是輪詢，不算解。
- 判法：【問】這份狀態一秒變幾次？【數】事件鏈深度 ≤2（A 發事件、B 聽了再發 C…的跳數，與跳層同尺）。
- 反→正：每幀檢查「血量是否變了」 → 血量變化時發事件；血條每幀插值的顯示則直接讀值。
- 壞味道：每幀輪詢、事件鏈迷宮。
- 來源：使用者原則 B-17；Nystrom Observer／Update Method【書】｜既有：09 B-17

### 8.3 事件具名、可 grep 到誰在聽，訂閱與退訂成對
- 為什麼：字串訊息與匿名委派讓「誰會被觸發」不可搜尋。
- 判法：【grep】`SendMessage\(|BroadcastMessage\(`＝0；事件宣告為具名 `event Action<...>`；`+=`／`-=` 配對（6.8）。
- 反→正：`SendMessage("OnHit")` → `unit.Hit += OnHit`。
- 壞味道：隱藏耦合、Message Chains、事件殭屍。
- 來源：經驗｜既有：09 B-15

### 8.4 數值由表驅動：程式只有規則，內容只在表裡
- 為什麼：企劃調數值不該重新編譯；表是二維資料的最佳形狀（3.1）。
- 判法：【數】新增一筆道具／技能／關卡改 `.cs` 的檔數 =0（5.8）；【grep】程式中的數值字面量是否都能對應到某表欄位或具名常數。
- 反→正：`if (skill == 7) dmg = 120;` → `dmg = skillTable[skill].Damage;`。
- 壞味道：Magic Number、Shotgun Surgery。
- 來源：使用者的尺；經驗｜既有：09 B-15（魔術數字照專案設計表查表）

### 8.5 表載入是邊界：載入時一次驗證，錯誤指到「表-列-欄」
- 為什麼：遊戲邏輯只看強型別，不再處理壞資料；壞資料在載入時就說話。
- 判法：【問】外鍵不存在、數值越界、列重複，載入時誰報？【數】驗證項覆蓋：欄位範圍、外鍵、唯一性。
- 反→正：邏輯內到處 `table.ContainsKey` → 載入階段 `Validate()` 一次，之後直接索引。
- 壞味道：靜默 miss、防禦分散。
- 來源：經驗｜既有：06 資料表

### 8.6 網路邊界：封包解析成命令或事件 struct，邏輯層不碰位元組
- 為什麼：協定細節屬於邊界；邏輯讀的是玩家的動作，不是位元。
- 判法：【grep】邏輯層出現 `byte[]`、`BitConverter`、`BinaryReader`＝0；【數】訊息種類用 enum，協定定義集中一處。
- 反→正：遊戲邏輯內 `buf[3] == 7` → 邊界轉成 `MoveCommand`，邏輯只吃 `MoveCommand`。
- 壞味道：Primitive Obsession、協定外洩。
- 來源：經驗｜既有：04

### 8.7 熱更邊界窄而顯式
- 為什麼：熱更與主程式的接縫越寬，兩邊越容易同時改壞。
- 判法：【數】跨邊界的入口數、型別數；【grep】熱更碼是否引用主程式內部型別或 Unity 物件做跨界傳遞；版本號是否顯式。
- 反→正：熱更程式直接持有主程式的 MonoBehaviour 引用 → 傳純資料 struct 與有限入口，閉包不跨界。
- 壞味道：Indecent Exposure、Hub-like Modularization。
- 來源：經驗（依所選熱更方案而異）｜既有：04

### 8.8 遊戲狀態機只為真狀態：enum＋switch，轉移能列成二維表
- 為什麼：玩家狀態、回合階段本來就有名詞；轉移表是二維資料。
- 判法：【數】狀態數 ≤約 8；轉移可寫成「從 × 到」表；【問】是否每個狀態都對應企劃會講的名詞？
- 反→正：每個狀態一個類別加繼承加工廠 → `enum Phase` 加 `switch`；狀態多到難以維護時才抽類別。
- 壞味道：過度設計、Unnecessary Hierarchy。
- 來源：Nystrom State 模式（含其節制建議）【書】｜既有：02 A4

### 8.9 模擬與表現分離：邏輯算、View 讀
- 為什麼：邏輯不依賴引擎物件，才能在非引擎環境跑驗證，讀路徑也短。
- 判法：【grep】邏輯類別 `using UnityEngine;` 的處數（僅允許純值型別如 `Vector3`）；【問】這段邏輯能否在單元測試裡不載入場景就跑？
- 反→正：血量計算寫在 MonoBehaviour 內讀 `transform` → 純 C# `Combat.Resolve(a, b)`，MonoBehaviour 只負責呼叫與顯示。
- 壞味道：God Component、引擎耦合。
- 來源：Unity 社群架構比較（二手）【經驗】｜既有：—

### 8.10 單位與座標系進名字或型別
- 為什麼：幀、秒、tick，世界座標、格子座標、螢幕座標混用，是最安靜的錯誤。
- 判法：【grep】數值欄位名是否帶單位（`cooldownSec`、`delayFrames`、`posGrid`）；【數】公開數值欄位帶單位的比例。
- 反→正：`float cooldown;` → `float cooldownSec;`。
- 壞味道：Mysterious Name、Primitive Obsession。
- 來源：經驗｜既有：—

### 8.11 一段流程一個函式，由上而下；取消與逾時顯式
- 為什麼：劇情、載入、戰鬥流程用 coroutine 或 async 寫成一條線，比拆成一串回呼好讀。
- 判法：【數】一段流程的 `yield`／`await` 在同一函式內；回呼層數 ≤1；【問】取消與逾時是否寫出來？
- 反→正：`LoadA(() => LoadB(() => LoadC(...)))` → `await LoadA(); await LoadB(); await LoadC();`。
- 壞味道：Callback Hell、Pyramid of Doom。
- 來源：C# async／迭代器用法（官方文件有說明，本次未逐頁開啟）【經驗】｜既有：07 A Callback Hell

---

## 9. 度量與工具（只列既有沒有的；度量總表與工具一覽見 07）

### 9.1 可機器量與只能人判的分界
| 準則 | 可機器量 | 只能人判 |
|---|---|---|
| 巢狀深度（2.1） | Roslyn 語法樹走訪、Sonar S134 | =3 時「三層是否各守獨立條件」 |
| 條件命名（2.3） | 運算子個數（S1067） | 命名是否貼近使用者名詞 |
| 繼承（4.4） | CA1501（預設較鬆）、DIT | 每層「加了什麼」 |
| 純轉接（4.2） | 自寫 Roslyn 查詢：單呼叫、參數原樣轉交 | 刻意分層是否有獨立責任 |
| 跳層／拐彎（1.2、1.3） | 無現成工具（07 §H 明言）；可用呼叫圖近似 | 最終判斷靠人（或帶證據的 LLM） |
| 命名（1.4） | 與表頭詞彙表對照找新縮寫 | 名字是否說實話 |
| 輕量（5.x） | 單實作 interface 清單、未使用成員 | 痛點是否真實 |
| 穩健（6.x） | 空 catch、`+=`／`-=` 配對、回傳 null | fallback 是否有訊號 |
- 來源：07 §H「沒有任何主流工具直接量測」段｜既有：07 §F、§H

### 9.2 人讀指標選 Cognitive，不選 Cyclomatic
- 為什麼：Cognitive Complexity 對巢狀加重、對 switch 與 `??`／`?.` 等語言捷徑不重複計分，較貼近人讀；Cyclomatic 與測試案例數同向。
- 判法：【工具】Sonar S3776 一類規則（預設門檻見 07 總表）；排序用，不設一刀切；數字大→問責任軸。
- 反→正：為壓低分數把一個函式拆成一串只呼叫一次的小函式（分降、讀路徑變長）→ 以 1.2、2.7 檢查是否反而變差。
- 壞味道：Goodhart 效應。
- 來源：G. Ann Campbell，SonarSource Cognitive Complexity 白皮書【書】｜既有：07 §A Cognitive、§I

### 9.3 可直接貼的粗篩指令（只當線索）
```text
空 catch：            rg -n "catch\s*(\([^)]*\))?\s*\{\s*\}" --glob "*.cs"
同步 void 事件配對：  rg -c "\+=\s*\w+;" --glob "*.cs"   與   rg -c "-=\s*\w+;" --glob "*.cs"
魔術數字（粗）：      rg -n "[^\w.\"][2-9]\d*[^\w.\"]" --glob "*.cs"  （人工排除 const、陣列索引）
byte 型 enum：        rg -n "enum \w+\s*:\s*byte" --glob "*.cs"
SendMessage：         rg -n "SendMessage\(|BroadcastMessage\(" --glob "*.cs"
Update 內 LINQ：      rg -n -A15 "void (Update|FixedUpdate|LateUpdate)\(" --glob "*.cs" | rg "\.(Where|Select|ToList|OrderBy|Any|First)\("
單實作 interface：    先 rg "interface I\w+" 列清單，再逐個 rg ": I名稱" 數實作
```
- 注意：命中是線索，不是判決；規則要錨在「現在還痛或會重犯」的清單才開（09 B-25、B-26）。
- 來源：經驗｜既有：09 D

### 9.4 量差不量絕對：只量本次異動範圍的前後
- 為什麼：存量另立 baseline；寫碼當下只對本次觸及範圍負責（種子：既有巢狀不要求順手重構）。
- 判法：【數】本次 diff 前後的最大巢狀、參數數、公開成員數；注意「只看新增行」遇拆分型重構會把搬家的舊碼當新碼（09 B-29）。
- 反→正：對全專案報一堆超標 → 只報本次異動檔中「變差」的指標。
- 壞味道：度量固著、噪音。
- 來源：使用者原則｜既有：09 B-28、B-29

### 9.5 先排熱點再審：變動頻率 × 複雜度
- 為什麼：冷區的高複雜度先記錄不急著修，重構預算投在又難讀又常改處。
- 判法：【工具】版控記錄的每檔變動次數，乘上巢狀或認知複雜度排序。
- 反→正：平均撒預算到所有超標檔 → 前 10 名熱點先處理。
- 壞味道：把力氣花在沒人讀的地方。
- 來源：Adam Tornhill《Your Code as a Crime Scene》【書】｜既有：07 §I Hotspot Analysis

---

## 給 LLM 的 30 行索引

```text
1 [認知] 讀一行要同時記的活東西 ≤3（1.1）；跳層 ≤3（1.2）；單一構想拐彎 ≤3（1.3）。
2 [認知] 名字用使用者世界的名詞、一概念一名字（1.4、1.5），減少匿名：魔術數字、匿名型別、難讀的布林引數（1.6、1.7）。
3 [認知] 註解寫為什麼與限制、白話（1.8）；函式停在同一抽象層級（1.9）。
4 [認知] 一個檔案看完一件事；partial 先問責任軸與寫入點，不報片數（1.10）。
5 [控制] 巢狀 ≤2 免談、=3 審查、≥4 重構，只管本次寫改的段落（2.1）；先踢例外讓主路徑靠左（2.2）。
6 [控制] 複雜條件命名、if 鏈查表、重複搜尋預建索引（2.3、2.4）；構件取階梯最低一級（2.5）；遞迴與狀態機只在天然處用（2.6）。
7 [控制] 扁平化不過頭：抽函式要 ≥2 處呼叫或有名詞（2.7）；LINQ 鏈 ≤3 且熱路徑不用（2.8）；switch 運算式只做值對值，三元不巢狀（2.9、2.10）。
8 [資料] 資料能攤成二維表就用表的樣子（3.1）；資料型別不綁序列化格式、自動產生碼不算優點（3.2、3.3）。
9 [資料] 值域小用 enum 不用 byte（3.4）；讓非法狀態無法表示（3.5）；ID 用專用型別（3.9）。
10 [資料] 資料與行為分離、取用彈性（3.6、3.7）；單一事實來源、預設不可變（3.8、3.10）。
11 [模組] 深模組：小介面、實質功能；沒有純轉接方法（4.1、4.2）。
12 [模組] 繼承每層說得出加了什麼、深度 ≤2（4.4）；只在真的是一種時繼承，否則組合（4.5）。
13 [模組] 責任一句話說完不含「和」、依賴單向無環、複雜度往下拉不推給呼叫者（4.7、4.8、4.9）；每個模組藏一個會變的決定（4.6）。
14 [輕量] 不加沒被要求的參數、設定、抽象、預防性分支（5.1）；第 2 次出現且是同步變更的知識才抽（5.2）；簡單設計四規則依序問（5.3）。
15 [輕量] 單實作無替換計畫的 interface 不建（4.3）；框架引入先寫換來什麼、綁了什麼、怎麼拆（5.4）；DI／ECS 非教條（5.5）。
16 [輕量] 不做明顯白工但不提前優化（5.6）；死碼當場刪（5.7）；新增內容只改資料不改碼（5.8）；極簡不砍可觀測性（5.9）。
17 [穩健] 防禦邊界、信任內部（6.1）；邊界解析成強型別、下游不重驗（6.2）。
18 [穩健] 程式錯誤 fail fast，預期失敗走 TryXxx，兩者分流（6.3、6.4）。
19 [穩健] 每個 fallback 留訊號、錯誤訊息帶上下文、一個錯誤只在能決策處記一次（6.5、6.6、6.7）。
20 [穩健] 取得與釋放對稱（+= 對 -=）；狀態轉移可查；時序前提用型別或參數表達（6.8、6.9、6.10）。
21 [驗證] 只驗異動範圍，結尾印 *_CHECK PASS／FAIL 或 DONE k=v（7.1）。
22 [驗證] 等值證明：預期來自舊源碼或舊產物、實際來自新產物，來源必不同；order、side_effect、boundary 三類各證（7.2、7.4）。
23 [驗證] 重構前先釘特徵測試；證據與預期不符不替原方案辯護；回報分清事實、推論、未知；陌生人複述資料流當讀碼測試（7.3、7.5、7.8、7.6、7.7）。
24 [遊戲] Update 只當調度員，每幀工作具名可列舉（8.1）；事件或輪詢依變化頻率選，事件鏈 ≤2 跳（8.2）。
25 [遊戲] 事件具名、可 grep、訂退成對（8.3）；數值由表驅動，新增內容不改 .cs（8.4）。
26 [遊戲] 表載入與網路封包都是邊界：一次解析驗證成強型別，邏輯層不碰位元組（8.5、8.6）。
27 [遊戲] 熱更邊界窄而顯式、純資料跨界（8.7）；狀態機只為真狀態（8.8）；模擬與表現分離（8.9）。
28 [遊戲] 單位與座標系進名字（8.10）；一段流程一個函式由上而下（8.11）。
29 [度量] 數字是代理指標不是判決：分清可機器量與只能人判（9.1）；人讀選 Cognitive、不拿單一數字當目標（9.2）。
30 [度量] 量差不量絕對、先排熱點（9.4、9.5）；跳層、拐彎、命名、抽象有無名詞，仍要人（或帶證據的 LLM）判（9.1）；粗篩指令只當線索（9.3）。
```

---

## 統計摘要

| 大類 | 條數 |
|---|---|
| 1 讀者認知負荷 | 10 |
| 2 控制結構與扁平化 | 10 |
| 3 資料優先與少綁定 | 10 |
| 4 模組與責任邊界 | 9 |
| 5 輕量 | 9 |
| 6 穩健 | 10 |
| 7 可驗證 | 8 |
| 8 遊戲特有 | 11 |
| 9 度量與工具 | 5 |
| 合計 | 82 |

- 判法型態（80 條有「判法」欄；9.1、9.3 是表與指令清單）：含【數】60、含【grep】35、含【工具】6、含【問】46；至少有一種機器或計數判法 75 條，只能靠【問】5 條。
- 來源型態：含【書】33、含【官】6、標【經驗】19、使用者種子或本機原則 25（少數條同時含書與官）。【書】的內容本次只讀到二手摘要，引述前請回查原文。
- 與既有文件的關係：「既有」欄指到 07／09／01～06 節號 71 條；標「—」的 11 條是本檔新增（2.10、3.3、3.7、5.3、6.2、6.7、7.1、7.5、7.8、8.9、8.10）。
- 查證缺口：Muratori 語意壓縮與 non-pessimization 的原文、Code Complete 的具體數字、Go Proverbs 與 Hickey 講稿原文、Microsoft Learn 的 struct 與例外指引頁，本次檢索未能開啟，相關條目已標【經驗】或附註。

---

## 參考來源一覽

| 來源 | 在本檔的用途 | 查證程度 |
|---|---|---|
| Ousterhout《A Philosophy of Software Design》；與 Martin 的公開討論 repo（`github.com/johnousterhout/aposd-vs-clean-code`） | 深模組、複雜度＝依賴＋晦澀、極短函式與註解的爭議 | 討論 repo 為一手摘要；書為二手摘要 |
| SonarSource Cognitive Complexity 白皮書（G. Ann Campbell） | 9.2 | 二手摘要 |
| Kent Beck 簡單設計四規則（Fowler〈Beck Design Rules〉、Agile Alliance 條目） | 5.3 | 二手摘要 |
| Rich Hickey〈Simple Made Easy〉（Strange Loop） | 「簡單」與「容易」不同：簡單＝不糾纏；用來支持 3.2、4.6 | 二手摘要 |
| Acton〈Data-Oriented Design and C++〉（CppCon） | 3.1、3.6、5.5 | 二手摘要 |
| Muratori 語意壓縮與 Performance-Aware Programming | 5.2、5.6 | 本次未取得原文，標經驗 |
| Jim Shore〈Fail Fast〉（IEEE Software） | 6.3 | 一手頁面與摘要 |
| Moseley & Marks〈Out of the Tar Pit〉 | 3.6、3.8 | 二手摘要 |
| Code Complete（McConnell）第 19 章 | 2.1、1.9 | 章節結構已查，數字未取得原文，不引具體門檻 |
| Rob Pike〈Go Proverbs〉；Dave Cheney〈Clear is better than clever〉 | 2.2、5.4、6.4 | 二手摘要 |
| Microsoft Learn：patterns、switch expression、CA1501／1502／1505／1506 | 2.9、4.4、4.8 | 官方頁面 |
| Unity 手冊 programming best practices | 2.8 | 官方頁面 |
| Scalabrino 等人可讀性模型；Buse & Weimer；後續研究發現單一指標與實際理解度相關性弱 | 1.4、9.2 的限制說明 | 二手摘要 |
| Feathers《Working Effectively with Legacy Code》；approval tests／golden master | 7.3 | 二手摘要 |
| Nystrom《Game Programming Patterns》 | 8.1、8.2、8.8 | 目錄與模式摘要 |
| Cowan（2001）、Parnas（1972）、Meyer 契約式設計、Alexis King、Minsky | 1.1、4.6、6.1、6.2、3.5 | 二手引述 |
| 使用者種子規則、`behavior-preservation` 技能、09 本機原則 | 全檔 | 一手 |
