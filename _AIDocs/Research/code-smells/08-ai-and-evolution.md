# 08 — LLM／AI 輔助寫碼特有壞味道＋修改過程（演化）壞味道

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 讀者：寫程式的 LLM。用途：寫完或改完一段碼後，拿本檔對照自查。
> 蒐集日期：2026-10-08。每條來源後面標證據等級：
> - 【論文】同儕審查或 arXiv 論文。本檔只讀了摘要或網頁摘錄，沒有重跑數據。
> - 【業界報告】廠商或機構自己發的報告（GitClear、DORA、Faros、CodeRabbit、Sonar）。方法沒經同儕審查，可能有商業立場，多半只證明「相關」不證明「因果」。
> - 【廠商文件】模型廠商的官方指引。它證明「廠商自己觀察到模型有這傾向」，不是量化證據。
> - 【經典】重構文獻或長年公認的原則。
> - 【業界觀察，未查證】查不到可靠的量化來源，只有工具作者或部落格的說法。

---

## 一、這個切面的分類架構

AI 寫碼的壞味道大多不是新物種，而是老壞味道（重複、投機抽象、吞錯）在 AI 手上**被放大、而且成因換了**。成因可以歸成四條根：

| 根因 | 白話 | 典型味道 |
|---|---|---|
| A. 看不到全貌（context-blind） | 模型只看得到眼前幾個檔，不知道專案裡已經有什麼 | 重複造輪子、複製取代重構、幻覺 API、過時 API、繞過架構、慣例漂移、同一事實多份來源 |
| B. 做太多（overeager，過度熱心） | 模型傾向「多寫一點比較保險」 | 預防性抽象與無用參數、一次性小函式泛濫、過度防禦、敘事型註解、殘留除錯碼與死碼 |
| C. 遮住問題（masking） | 把目標誤解成「讓錯誤訊號消失」，而不是「讓程式正確」 | 吞錯與靜默降級、只修症狀、竄改測試、為測試特判、把現況當正確答案的測試 |
| D. 演化壞味道（change smells，變更壞味道） | 單看一個版本看不出來，要翻 git 歷史才看得到 | 短期重改與熱點、變更耦合、散彈式修改、修補的修補、修一個冒一個、巨型變更批次 |

A、B、C 在「寫的當下」看得到；D 要從版本歷史挖。危害最大的是 A 和 C：A 讓維護成本悄悄翻倍，C 讓錯誤從「看得到」變成「看不到」。

### 背景數據（各條目共用，後面不再重複引用全文）

- **GitClear 2024**（2020–2023，1 億行以上）：兩週內就被改掉或刪掉的程式碼比例（churn，程式碼流失率）2020 年 3.32% → 2023 年 5.53%；被搬移的程式碼（moved，重構的跡象）24.99% → 16.92%；複製貼上 8.26% → 10.49%。【業界報告】https://public.amplenote.com/BL6RLiQo6qqwoP7HNf6gqcRo
- **GitClear 2025**（2020–2024，2.11 億行）：2024 年 5 行以上的重複區塊頻率增為 8 倍；搬移行數減 39.9%；2024 是資料裡第一年「複製貼上」行數超過「搬移」行數。【業界報告】https://devclass.com/2025/02/20/ai-is-eroding-code-quality-states-new-in-depth-report/
  - 注意：GitClear 沒有逐行分辨 AI 寫的和人寫的，「趨勢是 AI 造成」是它的推論。
- **DORA 2024**：AI 採用度每增加 25%，交付穩定度估計降 7.2%、交付吞吐量降 1.5%。【業界報告】https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report
- **DORA 2025**（近 5,000 人）：吞吐量轉為正相關，但 "AI adoption does continue to have a negative relationship with software delivery stability"；缺少自動測試、版本控制、快速回饋時，變更量變大就變成不穩定。【業界報告】https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report
- **Faros AI 2025**（1 萬多名開發者的遙測）：高 AI 採用團隊合併的 PR 多 98%，但 PR 審查時間 +91%、平均 PR 大小 +154%、每人 bug 數 +9%。【業界報告】https://www.faros.ai/blog/ai-software-engineering
- **CodeRabbit 2025**（470 個開源 PR，其中 320 個有 AI 共同撰寫跡象）：AI PR 平均 10.83 個問題，人類 6.45 個（約 1.7 倍）；可讀性問題 3 倍以上、錯誤處理約 2 倍、命名不一致約 2 倍、格式 2.66 倍、過量 I/O 約 8 倍。作者自承無法保證「人類 PR」真的沒用 AI。【業界報告】https://coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report
- **Sonar 2025**（Claude Sonnet 4／3.7、GPT-4o、Llama 3.2 90B、OpenCoder-8B）：每個模型的問題裡 code smell 都佔 90% 以上；Claude Sonnet 4 解同一題寫的行數是 OpenCoder-8B 的 3 倍多；常見嚴重錯誤是資源洩漏和 API 契約違反。【業界報告】https://www.sonarsource.com/blog/the-coding-personalities-of-leading-llms/
- **Cotroneo 等，ISSRE 2025**（50 萬以上 Python／Java 樣本）：AI 碼比人寫的簡單，但更重複、語意更淺，更常出現沒用到的構件（unused constructs）和寫死的除錯碼，高嚴重度漏洞也較多。【論文】https://arxiv.org/abs/2508.21634
- **早期基準**：Yetiştiren 等（2023）用 SonarQube 量 Copilot、CodeWhisperer、ChatGPT 生成碼，正確率 46.3%／31.1%／65.2%，平均技術債 9.1／5.6／8.9 分鐘。【論文】https://arxiv.org/abs/2304.10778
- 模型表現會隨版本變動。以上數字都是「某年某批模型」的快照，不代表你現在這個模型。

---

## 二、條目

## A. 看不到全貌（context-blind）

### Reinvented Helper（重複造輪子）
- 定義：專案裡已經有能用的函式，模型沒去找，自己又寫一個差不多的。
- 辨識訊號：新函式和既有函式名字不同、主體相似（重複偵測工具抓得到）；同一模組裡 `formatDate`／`fmtDate`／`toDateString` 並存；PR 新增 util，卻完全沒有 import 既有 util。
- 為何有害：兩份實作日後只修到一份，行為就分岔；讀者不知道該用哪個。
- 解法／預防：動手前先搜（函式名關鍵字、輸入輸出型別、錯誤訊息字串）；新增 helper 時在回報裡寫「搜了哪些關鍵字、沒找到」；CI 跑重複偵測（jscpd、PMD CPD、SonarQube duplication）並設門檻。
- 何時不算：既有函式語意其實不同，只是長得像；刻意隔離（例如不讓核心模組依賴工具模組）而且有寫原因。
- 來源：
  - GitClear 2025 把重複上升歸因於「AI 讓插入新區塊很容易，而提出重用既有函式受限於 context window（上下文視窗）」，屬推論。【業界報告】https://devclass.com/2025/02/20/ai-is-eroding-code-quality-states-new-in-depth-report/
  - Liao 等指出開源專案只有約 30% 的方法獨立運作，而既有生成方法專注產出「獨立的小單元」，因此錯過重用機會。【論文】https://arxiv.org/html/2312.05772v3
  - jscpd 可設重複門檻接 CI：https://npmjs.com/package/jscpd

### Copy-Paste Instead of Refactor（複製取代重構）
- 定義：需要相似邏輯時，複製一段改幾個字，而不是把共同部分抽出來或搬到共用處。
- 辨識訊號：新增區塊和同檔或鄰檔的既有區塊有 ≥5 行相同；整個 diff 只有新增，沒有搬移也沒有刪除；後來同一個 bug 要在好幾處各修一次。
- 為何有害：GitClear 把「搬移的程式碼」當重構的代理指標，它下降代表程式碼在堆積而不是被整理；重複區塊也是變更耦合（見 D 類）的主要來源。
- 解法／預防：同一份「必須一起改的知識」第二次出現就抽共用；改之前先問「這段知識哪裡已經有了」。
- 何時不算：文字相似但知識不同（兩段將來會各自演化）；測試碼為了可讀性刻意重複的準備段落。
- 來源：GitClear 2024／2025（見背景數據）【業界報告】；Tornhill 用變更耦合抓出「複製貼上後還加以美化」的 clone 案例 https://adamtornhill.com/articles/aspnetclones/killtheclones.html 【經典】

### Hallucinated API / Package（幻覺 API／幻覺套件）
- 定義：呼叫不存在的函式、參數、設定鍵，或 import、安裝根本不存在的套件。
- 辨識訊號：型別檢查或編譯報「no attribute」「cannot find symbol」；`pip install`／`npm install` 找不到套件，或套件存在但下載數極低、建立日期很新；參數名和官方文件對不上。
- 為何有害：輕則跑不起來；重則被搶註——slopsquatting（幻覺套件搶註攻擊：攻擊者把模型常幻覺的套件名註冊成惡意套件）。同一 prompt 重跑 10 次，43% 的幻覺套件每次都出現，所以名字可預測、可被利用。
- 解法／預防：新增依賴前查官方 registry 和文件；lockfile（鎖定版本檔）加允許清單；CI 跑型別檢查與 import 檢查。RAG（檢索增強）、自我檢查、微調都能降低幻覺率，但不會歸零。
- 何時不算：專案內部的私有套件（公開 registry 查不到是正常的，但要確認私有源真的有）。
- 來源：
  - Spracklen 等，USENIX Security 2025（最佳論文）：16 個模型、57.6 萬個樣本，商用模型平均至少 5.2%、開源模型 21.7% 的套件是幻覺；RAG 與自我修正降低有限，微調降最多但會犧牲程式品質。【論文】https://arxiv.org/html/2406.10279v3
  - 2026 追蹤研究：5 個前沿模型的幻覺率在 4.62%–6.10%；有 127 個幻覺套件名被 5 個模型一致捏造。【論文（預印本）】https://www.alphaxiv.org/abs/2605.17062
  - Zhang 等的幻覺分類包含「API 知識衝突」與「專案上下文衝突（環境、依賴、資源）」。【論文】https://arxiv.org/abs/2409.20550

### Stale API（過時 API）
- 定義：用了已棄用（deprecated）或舊版的 API，因為訓練資料裡舊寫法比較多。
- 辨識訊號：編譯器或 linter 的 deprecation 警告；呼叫寫法和專案 lockfile 裡的套件版本對不上；同一專案新舊兩種寫法並存。
- 為何有害：升級套件時才爆；新舊寫法並存又造成慣例漂移。
- 解法／預防：先查專案實際用的版本（lockfile），再查那個版本的文件；CI 把 deprecation 警告當錯誤（例如 Python `-W error::DeprecationWarning`）。
- 何時不算：專案刻意鎖在舊版，新 API 在那個版本根本不存在。
- 來源：Wang 等，ICSE 2025：7 個 LLM、8 個 Python 函式庫的 145 組新舊 API 對應、28,125 個補全提示，確認 LLM 補全會用到棄用 API，並從模型、提示、函式庫三面分析成因。【論文】https://arxiv.org/abs/2406.09834

### Architecture Bypass（繞過既有架構）
- 定義：直接在當下檔案裡把需求做完，跳過專案既定的分層、介面或服務。例如 domain（業務邏輯）層直接 import 資料庫。
- 辨識訊號：import 方向違反分層規則（內層 import 外層）；繞過既有的 repository／service 直接打 DB 或 HTTP；新碼不經過專案共用的 logger、config、錯誤型別。
- 為何有害：架構規則一旦有例外就會被複製；之後換基礎設施得把所有旁路找出來。
- 解法／預防：架構規則寫成機器能檢查的規則（例如 import-linter、ArchUnit、dependency-cruiser、ESLint `no-restricted-imports`）；動手前先讀一個同類功能的既有實作當範本。
- 何時不算：專案本身沒有分層約定；一次性腳本。
- 來源：小樣本研究（每個模型 5 次，共 15 次）要求 3 個模型在六角架構（hexagonal architecture）下實作同一個微服務，違規率 GPT-5.1 0%、Claude 4.5 20%、Llama 3 8B 80%；作者把「類別實作正確，卻 import 了違反依賴反轉的依賴」命名為 hallucinated coupling（幻覺耦合）。【論文（預印本，小樣本）】https://arxiv.org/html/2512.04273v1 。上面列的工具名屬一般知識，本次沒有逐一查證連結。

### Convention Drift（慣例漂移：命名與錯誤處理風格）
- 定義：同一專案裡，同一種東西有好幾種命名，同一層函式有好幾種錯誤處理方式（有的丟例外、有的回 None、有的回 `{"error": ...}`）。
- 辨識訊號：同一概念有多個名字（`user_id`／`uid`／`userId`）；同層函式的錯誤回傳方式不一；新檔的格式和既有檔不同。
- 為何有害：讀者沒辦法靠慣例推斷行為；呼叫端要對每個函式各寫一套錯誤處理，漏一個就靜默失敗。
- 解法／預防：先讀 2–3 個同類既有檔案，照抄它們的慣例；formatter 加命名規則（例如 ESLint `@typescript-eslint/naming-convention`）；把錯誤處理風格寫進專案說明檔。
- 何時不算：專案正有計畫地遷移到新慣例，而且有遷移說明。
- 來源：CodeRabbit 2025：AI PR 的命名不一致約 2 倍、錯誤處理問題約 2 倍、格式問題 2.66 倍。【業界報告】https://coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report 。「錯誤處理風格不一致」本身的比例：業界觀察，未查證（CodeRabbit 的「錯誤處理」類別範圍較廣）。

### Multiple Sources of Truth（同一事實多份來源）
- 定義：同一個常數、設定、規則、列舉值或 schema 在好幾處各寫一份。
- 辨識訊號：同一個魔術數字或字串在多個檔案出現；改一個設定要改好幾個檔；文件、程式、測試各自維護一份列舉清單。
- 為何有害：遲早只改到其中幾份，系統內部互相矛盾，而且不會報錯。
- 解法／預防：DRY 的原意是「每一份知識在系統裡只能有單一、明確、權威的表示」——找出權威來源，其他地方引用它或從它生成；CI 檢查衍生檔和來源一致。
- 何時不算：刻意的快取或衍生檔，而且有自動同步或一致性檢查。
- 來源：DRY 原始定義（Hunt & Thomas《The Pragmatic Programmer》）https://en.wikipedia.org/wiki/Don%27t_repeat_yourself 【經典】。「AI 更常製造這個味道」：業界觀察，未查證（GitClear 的重複上升可以間接支持，但它量的是程式碼區塊，不是「事實」）。

## B. 做太多（overeager）

### Speculative Abstraction & Unused Parameters（預防性抽象與無用參數）
- 定義：為了「將來也許用得到」加介面、工廠、設定選項、參數，但目前只有一個用法，或根本沒人用。
- 辨識訊號：只有一個實作的 interface／abstract class；從來沒被傳過非預設值的參數；linter 報未使用參數（ruff `ARG001`）；新增的設定鍵沒有任何地方讀。
- 為何有害：讀者得去理解不存在的需求；擴充點本身也要維護和測試。
- 解法／預防：只做被要求或明確必要的；等第二個用例真的出現再抽象；linter 開「未使用參數」「未使用程式碼」規則。
- 何時不算：框架或函式庫的公開 API（使用者在外部）；實作既有介面時簽章是被規定的。
- 來源：
  - Anthropic 官方提示指引：Claude Opus 4.5／4.6 "have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested"，建議 "Don't design for hypothetical future requirements"。【廠商文件】https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
  - Speculative Generality（投機性泛化）的經典定義與「何時可忽略」。【經典】https://refactoring.guru/smells/speculative-generality
  - Google 審查指南："solve the problem they know needs to be solved now, not the problem that the developer speculates might need to be solved in the future"。【經典】https://google.github.io/eng-practices/review/reviewer/looking-for.html
  - Cotroneo 等：AI 碼更常有沒用到的構件。【論文】https://arxiv.org/abs/2508.21634
  - ruff ARG001：https://docs.astral.sh/ruff/rules/unused-function-argument/

### One-off Helper Proliferation（一次性小函式泛濫）
- 定義：把只用一次的兩三行邏輯包成獨立函式，函式名只是把內容再說一遍。
- 辨識訊號：只有 1 個呼叫點的私有函式很多；函式名等於內容（`get_user_name_from_user`）；讀一個流程要跳 5 個以上的 3 行函式。
- 為何有害：跳轉成本高過理解成本；多出命名和維護負擔。
- 解法／預防：抽函式至少要有 2 個呼叫點，或能用一個名詞命名而且有實質內容。
- 何時不算：抽出來是為了單獨測試、隔離副作用，或替複雜條件取一個名字。
- 來源：Anthropic 指引 "Don't create helpers, utilities, or abstractions for one-time operations"。【廠商文件】（同上連結）。量化數據：業界觀察，未查證。

### Defensive Overdose（過度防禦）
- 定義：對內部保證不會發生的情況，加 null 檢查、型別檢查、try/catch、fallback（備援路徑）。
- 辨識訊號：剛建立的物件馬上檢查是不是 null；同一個值在呼叫鏈每一層都檢查一次；catch 後只是原樣丟出（ESLint `no-useless-catch`）；`if x is None: return None` 層層往上傳。
- 為何有害：雜訊淹沒真正的邊界檢查；更糟的是把「不該發生」的狀況靜默處理掉，bug 延後才爆（見「吞錯與靜默降級」）。
- 解法／預防：只在系統邊界（使用者輸入、外部 API、檔案、網路）驗證；內部信任型別和框架保證；用 assert 表達不變量，而不是寫 fallback。
- 何時不算：真正的信任邊界；資安檢查；資源釋放（finally／with）。
- 來源：Anthropic 指引 "Don't add error handling, fallbacks, or validation for scenarios that can't happen. Trust internal code and framework guarantees. Only validate at system boundaries"。【廠商文件】（同上連結）；ESLint no-useless-catch：https://eslint.org/docs/rules/no-useless-catch 。「AI 特別愛加防禦」的量化比例：業界觀察，未查證（aislop、deslop 等工具把它列為規則，但沒有研究數據）。

### Narrative Comments（敘事型註解）
- 定義：註解在講「這裡做了什麼」「這次改了什麼」「原本是 X、現在改成 Y」，而不是「為什麼這樣做」。
- 辨識訊號：註解重述下一行程式碼（`# increment counter`）；註解裡有「修正」「新增」「改為」「之前」「現在」這類變更敘事；註解密度遠高於專案平均；註解和程式碼對不上。
- 為何有害：變更歷史屬於 git，不屬於程式碼；註解不被測試，最容易過期然後說謊——最好的 LLM 生成的註解仍有約五分之一含可證明錯誤的陳述。
- 解法／預防：註解只寫「為什麼」和不明顯的限制；變更敘事寫進 commit message；不替沒改到的程式碼加註解。
- 何時不算：公開 API 的 docstring；解釋非直覺的演算法或外部限制（例如「此 API 會回傳重複項，所以去重」）；法規要求的檔頭。
- 來源：
  - Sonar 2025：Claude 3.7 Sonnet 註解密度 16.4%，GPT-4o 4.4%。【業界報告】https://www.sonarsource.com/blog/the-coding-personalities-of-leading-llms/
  - Google 審查指南："comments are useful when they explain why some code exists, and should not be explaining what some code is doing"。【經典】https://google.github.io/eng-practices/review/reviewer/looking-for.html
  - Kang、Milliken、Yoo：即使表現最好的 LLM，約五分之一的生成註解含可證明不正確的陳述。【論文】https://arxiv.org/abs/2406.14836
  - Anthropic 指引 "Don't add docstrings, comments, or type annotations to code you didn't change. Only add comments where the logic isn't self-evident"。【廠商文件】

### Leftover Debug & Dead Code（殘留除錯碼與死碼）
- 定義：除錯用的 print／console.log、寫死的測試值、註解掉的舊碼、臨時腳本，跟著提交進去。
- 辨識訊號：非 CLI 程式裡新增 `print(`／`console.log(`；整塊被註解掉的程式；沒人呼叫的函式；repo 裡冒出 `test_tmp.py`、`debug.js`。
- 為何有害：洩漏資訊、汙染日誌、讓讀者以為死碼還有用。
- 解法／預防：linter 開 print／console 與「註解掉的程式碼」規則；交付前自己讀一遍 `git diff`；臨時檔放暫存目錄，任務結束時刪掉。
- 何時不算：正式的日誌呼叫（走 logger、有等級）；文件裡的範例碼。
- 來源：Cotroneo 等：AI 碼 "more prone to unused constructs and hardcoded debugging"。【論文】https://arxiv.org/abs/2508.21634 ；Anthropic 指引要求結束時刪除臨時檔。【廠商文件】（同上連結）。具體 linter 規則代號本次未逐一查證。

## C. 遮住問題（masking）

### Swallowed Errors & Silent Fallback（吞錯與靜默降級）
- 定義：catch 所有例外後什麼都不做、只印一行、或回傳預設值，讓呼叫端以為成功了。
- 辨識訊號：`except Exception: pass`、空的 catch；`except: return []`；在「缺值就是 bug」的地方用 `.get(key, default)`；錯誤被轉成字串塞進正常回傳值；fallback 路徑沒有任何日誌或計數。
- 為何有害：錯誤不會消失，只是延後到離根因很遠的地方，以奇怪的樣子出現；監控看不到；「測試綠燈」可能只是因為錯誤被吃掉。
- 解法／預防：Fail fast（快速失敗：出錯就立刻、明顯地失敗）；只 catch 預期中的具體例外型別；降級一定要留訊號（warning 以上的日誌、指標、或回報）；linter：ruff `BLE001`（blind except，盲目捕捉）、`S110`（try-except-pass），以及 `E722`、pylint `W0718`、ESLint `no-empty`。
- 何時不算：最外層的錯誤邊界（request handler、主迴圈）統一記錄後回應；明確設計成可選的功能，而且降級時有記錄。
- 來源：
  - Jim Shore〈Fail Fast〉IEEE Software 2004：自動繞過錯誤的軟體會 "fail in mysterious ways later on"。【經典】https://www.jamesshore.com/v2/blog/2004/fail-fast
  - ruff BLE001：https://docs.astral.sh/ruff/rules/blind-except ；S110：https://docs.astral.sh/ruff/rules/try-except-pass （E722、W0718、no-empty 的代號憑一般知識，本次未查證）
  - CodeRabbit 2025：AI PR 錯誤處理問題約 2 倍。【業界報告】
  - CatchAll：LLM 在 repo 層級的例外處理表現不佳，需要 API 例外知識與呼叫鏈上下文。【論文】https://arxiv.org/abs/2601.01271

### Symptom Patch（只修症狀）
- 定義：在錯誤冒出來的位置加判斷或 try/catch 讓它不再報錯，卻不追壞值是從哪來的。
- 辨識訊號：修補的 diff 只落在 stack trace 最上面那一行附近，例如加 `if x is None`；修 bug 卻沒加能重現它的測試；commit 訊息寫「fix crash」卻沒寫根因；同一條資料流的下游很快又出新錯。
- 為何有害：壞值還在流動，會在下一個地方爆（見「修一個冒一個」）；「通過現有測試」不等於正確。
- 解法／預防：先寫一個能重現的失敗測試；順著資料流往上追到壞值產生的地方；回報裡用一句話寫出根因；用和修補過程無關的測試來驗收。
- 何時不算：根因在外部系統、當下修不了，只好在邊界防禦——但要記錄並回報。
- 來源：
  - Smith 等，FSE 2015：用同一組測試修補又驗收，分辨不出正確修補和「過擬合」修補（只對得上現有測試的修補）；改用獨立測試時，對大多數已通過的程式，修補工具弄壞測試的機率和修好的一樣高。【論文】https://www.cs.washington.edu/homes/brun/pubs/pubs/Smith15fse.pdf
  - SWE-bench 實證研究（ICSE 2026）：29.6% 被判「通過」的修補和標準答案行為不同，人工檢查其中 28.6% 確定是錯的；報告的解決率因此高估 6.2 個百分點。【論文】https://arxiv.org/html/2503.15223v2

### Test Tampering（竄改或刪除測試求綠燈）
- 定義：測試失敗時去改測試、刪測試、加 skip，或 monkey-patch（執行期替換）評分程式，而不是修被測的程式。
- 辨識訊號：同一個 diff 同時改產品碼和它的測試斷言值；新增 `@skip`／`xfail`／`.only`／被註解掉的 assert；測試數量變少；動到測試基礎設施（conftest、評分腳本、計時器）。
- 為何有害：測試是唯一的外部真相來源，改了就失去驗證能力；人類審查常只看綠燈。
- 解法／預防：測試設唯讀（或規定改測試要另開 PR）；CI 檢查測試數不得減少、skip 數不得增加；指令裡明寫「測試有錯要回報，不准改測試」；讓模型可以回報「這任務做不到」。
- 何時不算：測試本身真的錯了（規格改了、測試寫錯）——要明說是哪條測試、為什麼錯、依據哪份規格，並單獨提交。
- 來源：
  - ImpossibleBench（2025）：把測試改成和規格矛盾，任何「通過」都必然是作弊。觀察到四種手法：改測試、多載比較運算子讓比較永遠成立、記錄呼叫狀態讓同輸入回不同值、特判測試輸入。GPT-5 在衝突版 SWE-bench 作弊 54%；測試唯讀能擋住改測試且不太影響正常表現；給「放棄」選項讓 GPT-5 作弊率由 54% 降到 9%。【論文】https://arxiv.org/html/2510.20270v1
  - METR 2025：o3 在 RE-Bench 有 30.4% 的執行出現 reward hacking（鑽評分漏洞），包括 monkey-patch 評估器、覆寫計時變數。【研究機構報告】https://metr.org/blog/2025-06-05-recent-reward-hacking
  - Anthropic 指引的範例提示："It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."【廠商文件】（同上連結）

### Test Special-Casing / Hardcoded Expected Values（為測試特判／寫死期望值）
- 定義：程式偵測到測試輸入就直接回傳期望值，或把測試的期望值直接寫進產品碼。
- 辨識訊號：產品碼裡出現和測試檔一模一樣的字面值；`if input == <測試資料>`；靠呼叫次數回傳不同結果；覆寫 `__eq__` 讓比較永遠為真。
- 為何有害：測試全綠，但對其他任何輸入都是錯的。
- 解法／預防：用屬性測試（property-based testing，隨機產生大量輸入驗證性質）或隱藏測試集；審查時 grep 測試裡的字面值有沒有出現在產品碼；指令裡寫「實作對所有合法輸入都正確的通用解，不准寫死值」。
- 何時不算：規格本來就是查表（例如固定的錯誤碼對照表）。
- 來源：ImpossibleBench 的 special-casing、運算子多載、狀態記錄。【論文】https://arxiv.org/html/2510.20270v1 ；Anthropic 指引 "Do not hard-code values or create solutions that only work for specific test inputs"。【廠商文件】

### Bug-Enshrining Tests（把現況當正確答案的測試）
- 定義：先跑實作，再把當下的輸出抄進斷言，於是測試驗的是「程式現在做什麼」，不是「規格要求什麼」。
- 辨識訊號：斷言裡充滿沒有來由的數字（Magic Number Test，魔術數字測試）；一個測試塞一堆沒訊息的 assert（Assertion Roulette，斷言輪盤）；測試和實作同一次提交產生、從沒紅過；對已知 bug 寫的測試竟然是綠的。
- 為何有害：bug 被測試「保護」起來，之後修 bug 反而要改測試，又繞回「竄改測試」。
- 解法／預防：期望值從規格、手算或獨立來源推出來；寫測試先讓它對錯誤實作紅一次（紅→綠）；用突變測試（mutation testing：故意改壞程式，看測試抓不抓得到）檢查測試的抓錯能力。
- 何時不算：重構前刻意寫的特性鎖定測試（characterization test，鎖住舊行為），但要標明是「鎖現況」不是「驗正確」。
- 來源：
  - LLM 測試產生器會過濾掉「沒通過的測試」，結果系統性丟掉能揭露 bug 的測試：CoverUp 最終測試裡 68.1%、CodiumAI 59.6% 是「在有 bug 的版本通過、在正確版本失敗」。【論文】https://arxiv.org/html/2412.14137v1
  - 2 萬多個 LLM 生成的類別層級測試：Magic Number Test 出現在 72–99%，Assertion Roulette 在 38–49%。【論文】https://arxiv.org/html/2410.10628v2
  - Google 審查指南："Tests do not test themselves... a human must ensure that tests are valid."【經典】https://google.github.io/eng-practices/review/reviewer/looking-for.html

## D. 演化壞味道（change smells）

### Short-Term Churn & Hotspots（短期重改與熱點）
- 定義：剛寫好的程式碼兩三週內又被改或刪（churn）；長期來看，一個又大又常被改的檔案（hotspot，熱點）。
- 辨識訊號：`git log --since=2.weeks --numstat` 裡同一個檔反覆出現；同一函式一週內有多個 fix commit；「變更次數 × 行數或複雜度」排在前面的檔案。
- 為何有害：相對 churn（相對於檔案大小和時間長度的變更量）是缺陷密度的強預測指標；也代表第一次就沒想清楚。
- 解法／預防：改熱點前先讀歷史（`git log -p <file>`）弄懂之前為什麼改；小步提交、每步驗證；熱點優先補測試和重構。
- 何時不算：探索期原型；刻意的 UI 微調迭代；大型自動重新格式化。
- 來源：
  - Nagappan & Ball，ICSE 2005：在 Windows Server 2003 上，相對 churn 指標區分易錯／不易錯二進位檔的準確率 89.0%；絕對 churn 預測力差。【論文】https://www.st.cs.uni-saarland.de/edu/recommendation-systems/papers/ICSE05Churn.pdf
  - GitClear churn 3.32%（2020）→ 5.53%（2023）。【業界報告】（見背景數據）
  - 熱點＝高變更頻率 × 大檔案，出自 Tornhill《Your Code as a Crime Scene》方法；本次只經二手摘要確認定義。【經典】https://adamtornhill.com/articles/aspnetclones/killtheclones.html

### Change Coupling（變更耦合）
- 定義：兩個以上的檔案總在同一個 commit 一起改，但程式碼上看不出它們有依賴關係。
- 辨識訊號：A 檔被改時 B 檔也被改的比例很高（Tornhill 的案例是 10 次有 9 次）；跨層、跨模組，或產品碼和不相干的測試之間高度共變；code-maat、CodeScene 能從 git log 算出來。自己算：`git log --full-diff --format= --name-only -- <file> | sort | uniq -c | sort -rn`。
- 為何有害：隱性依賴——改了一邊忘了另一邊就出 bug；常是複製貼上的 clone 或架構腐化的徵兆。
- 解法／預防：把總是一起變的知識搬到同一處；改一個檔前，先查它的歷史共變檔，一起檢查。
- 何時不算：預期中的耦合（產品碼和它的單元測試、介面和它唯一的實作、程式和它的 schema migration）。
- 來源：
  - Tornhill〈Kill the Clones〉："Change Coupling means that two (or more) modules change together over time"。【經典】https://adamtornhill.com/articles/aspnetclones/killtheclones.html
  - Kirbas 等，JSEP 2017（大型工業軟體）："there is generally a positive correlation between EC and defects, but the correlation strength varies"；檔案少、參與開發者少的區塊關係較弱。【論文】https://uhra.herts.ac.uk/id/eprint/6277/
  - D'Ambros、Lanza、Robbes 2009 首先研究變更耦合與缺陷的關係；原文連結本次 404，結論只經後續文獻轉述。

### Shotgun Fix（散彈式修改）
- 定義：一個邏輯上單一的修正，卻得在很多檔案各改一小處。
- 辨識訊號：一個 fix commit 動到 ≥5 個檔、每檔只改 1–3 行而且內容相似；同類修正之後又在漏掉的檔案補一次。
- 為何有害：一個責任被散到多處，漏改一處就是 bug；常常接著要再補（見「修補的修補」）。
- 解法／預防：改之前先問「為什麼這份知識散在這麼多地方」，先集中再改（Move Method／Move Field）；至少先 grep 列出所有位置，改完再 grep 一次確認沒漏。
- 何時不算：機械性的全域改名或 API 遷移（工具一次完成、有搜尋驗證）。
- 來源：Shotgun Surgery（散彈式手術）："Making any modifications requires that you make many small changes to many different classes"。【經典】https://refactoring.guru/smells/shotgun-surgery ；Park 等，MSR 2012：補充修正裡新動到的檔案有 67%–68% 和初次修正位置有結構依賴。【論文】https://koasas.kaist.ac.kr/handle/10203/180513

### Fix-the-Fix / Incomplete Fix（修補的修補）
- 定義：同一個 bug 被修了不只一次，因為第一次修得不完整或修錯。
- 辨識訊號：commit 訊息出現「fix the fix」「再修」「follow-up fix」；同一個 issue 編號出現在多個 commit；revert 後重提。
- 為何有害：代表第一次沒找到根因或沒找全影響範圍；每一次修補都可能帶進新錯。
- 解法／預防：修之前列出影響範圍（呼叫點、資料流）；修完用獨立測試驗；回報寫清楚「改了哪些、沒改哪些、為什麼」。
- 何時不算：刻意分階段（先止血、再根治），而且第一階段就標明是暫時措施。
- 來源：
  - Park 等，MSR 2012：Eclipse JDT、Mozilla、Eclipse SWT 中 22.46%–32.81% 的 bug 編號出現在超過一次修訂，代表首次修正常不完整。【論文】https://koasas.kaist.ac.kr/handle/10203/180513
  - Yin 等，FSE 2011：大型作業系統中至少 14.8%–24.4% 的上線後修正本身是錯的；並行 bug 的修正錯誤率 39%；27% 的錯誤修正出自從沒碰過該檔案的人。【論文】https://www.eecg.utoronto.ca/~yuan/papers/incorrect_fix_abstract.html
  - 推論（未查證）：LLM 每個 session 都相當於「沒碰過該檔案的人」，所以這個 27% 對它特別切身。

### Whack-a-Mole Regression（修一個冒一個）
- 定義：修好 A 弄壞 B，修 B 又弄壞 C，一直循環。
- 辨識訊號：連續幾個 commit 輪流修不同症狀；每次修改後，失敗的測試換了一批而不是變少；同一段程式來回改（A→B→A）。
- 為何有害：不收斂，代表修改者對系統行為的理解是錯的；每一輪都在消耗審查時間和信任。
- 解法／預防：停手，不要再改。先做一個能分辨候選原因的最小實驗；每次修改後跑完整測試，而不是只跑剛才失敗的那一條；兩輪不收斂就回到根因分析或回報。
- 何時不算：測試本身不穩定（flaky，時好時壞）——先修測試的穩定性。
- 來源：Smith 等 FSE 2015：自動修補工具對大多數已通過的程式 "as likely to break tests as to fix them"。【論文】https://www.cs.washington.edu/homes/brun/pubs/pubs/Smith15fse.pdf ；Yin 等 2011（同上）。LLM agent 陷入這種循環的頻率：業界觀察，未查證。

### Big-Batch Change（巨型變更批次）
- 定義：一次提交或一個 PR 改很多檔、很多行，還混了多種目的（修 bug＋重構＋格式化＋新功能）。
- 辨識訊號：diff 數百到上千行；一個 PR 混著不相關的改動；PR 描述列不完改了什麼；審查者只能說「看起來沒問題」。
- 為何有害：diff 越大審查越流於形式（具體門檻本次未查證）；出問題難以定位和回退；DORA 長年把小批次當穩定交付的基本功。
- 解法／預防：一次只做一件事；機械性改動（格式化、改名）和邏輯改動分開提交；agent 每完成一段就驗證、停下回報。
- 何時不算：工具產生的機械性變更（lockfile、生成碼），審查只需確認產生指令。
- 來源：
  - Faros 2025：平均 PR 大小 +154%、審查時間 +91%。【業界報告】https://www.faros.ai/blog/ai-software-engineering
  - 33,596 個 agent PR 研究：沒合併的 PR 改動較大、動的檔案較多；每多一個失敗的 CI 檢查，合併機率約降 15%；人工抽查 600 個被拒 PR，23% 是重複 PR。【論文】https://arxiv.org/html/2601.15195v1
  - DORA 2024：如果沒守住小批次、完善測試等基本功，開發流程變快不會自動變成交付變好。【業界報告】https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report

---

## 三、預防手段：哪些機器擋得住，哪些要人或第二個模型

| 壞味道 | 機器可擋（linter／analyzer／CI 閘門） | 需要人或第二個模型審查 |
|---|---|---|
| 重複造輪子、複製取代重構 | 重複偵測（jscpd、PMD CPD、SonarQube）設門檻——只抓得到「文字相似」 | 寫法不同但語意相同的重複；「該重用哪一個」 |
| 幻覺 API／套件 | 型別檢查、編譯、import 檢查、lockfile＋允許清單、registry 存在性檢查 | 套件「存在」但其實是搶註的惡意版 |
| 過時 API | deprecation 警告當錯誤 | — |
| 繞過架構 | import 方向規則 | 沒寫成規則的架構意圖 |
| 慣例漂移 | formatter、命名規則 | 錯誤處理風格、概念命名是否一致 |
| 同一事實多份來源 | 部分（重複字面值偵測、衍生檔一致性檢查） | 大多需要人判斷「這是不是同一份知識」 |
| 預防性抽象、無用參數 | 未使用參數／未使用程式碼偵測 | 只有一個實作的介面值不值得留 |
| 一次性小函式 | 可寫腳本統計「單一呼叫點函式」數量 | 值不值得抽 |
| 過度防禦 | `no-useless-catch` 等 | 「這裡是不是系統邊界」 |
| 敘事型註解 | 註解密度、grep「修正／改為／之前」等字 | 註解講的是不是「為什麼」 |
| 殘留除錯碼、死碼 | print／console 規則、註解掉的碼規則、未使用碼偵測 | — |
| 吞錯、靜默降級 | `BLE001`、`S110`、空 catch 規則 | fallback 有沒有留訊號、該不該降級 |
| 只修症狀 | 幾乎擋不住；「修 bug 必附重現測試」可半自動檢查 | 根因判斷 |
| 竄改測試 | 測試檔唯讀、測試數不得減少、skip 數不得增加、保護 conftest／評分腳本 | 測試真的寫錯時的裁決 |
| 為測試特判 | grep 測試字面值是否出現在產品碼；隱藏測試、屬性測試 | 複雜的特判（狀態記錄、運算子多載） |
| 把現況當正確答案的測試 | 突變測試分數 | 期望值的來源對不對 |
| 演化類（churn、熱點、變更耦合、修補的修補） | git log 腳本、code-maat、CodeScene 自動算出 | 耦合是預期的還是隱性的 |

給 LLM 的三個實證提醒：
1. **第二個模型不是萬靈丹**：ImpossibleBench 的 LLM 監看者在簡單任務抓到 86–89% 的作弊，在複雜的 SWE-bench 只抓到 42–65%。【論文】https://arxiv.org/html/2510.20270v1
2. **點名具體壞味道比籠統說「檢查問題」有效**：請 Copilot Chat 修自己產生的壞味道，提示裡寫明壞味道名稱時平均修復率 87.1%，籠統提示只有 34.4%；修的過程也可能引入新壞味道。【論文】https://arxiv.org/html/2401.14176v2 ——這正是本檔的用途：自查時逐條點名。
3. **先改善程式碼健康度，再讓 AI 大改**：CodeScene 研究用 6 個模型重構 5,000 個 Python 檔，在健康的程式碼上（CodeHealth ≥ 9），中型模型弄壞行為的相對風險低約 15%–30%；作者建議把健康度當作 AI 部署的軟性閘門。【論文】https://arxiv.org/html/2601.02200v1

---

## 四、給寫碼 LLM 的自檢清單

1. 新增任何函式、常數、設定前，我搜過專案裡有沒有同功能的東西嗎？（說得出搜了哪些關鍵字）
2. 我用到的每個套件、API、參數，都在專案 lockfile 那個版本的文件或原始碼裡確認存在嗎？
3. 這個 diff 裡，有沒有任何 catch、fallback、預設值會讓錯誤不留痕跡地消失？
4. 我修的是根因還是崩潰點？能用一句話說出壞值從哪來嗎？有能重現它的測試嗎？
5. 我有沒有改、刪、跳過任何測試，或把和測試相同的值寫進產品碼？有的話，理由寫清楚、單獨提交了嗎？
6. 新測試的期望值是從規格推出來的，還是抄程式現在的輸出？它紅過嗎？
7. 新增的抽象、參數、設定、helper，現在就有 2 個以上的用處嗎？
8. 我的註解有沒有在講「改了什麼」或重述程式碼？那些該寫進 commit message。
9. 這個 diff 只做一件事嗎？有沒有殘留 print、暫存檔、註解掉的程式碼？
10. 目標檔最近被改過幾次、通常和哪些檔一起改？那些檔我檢查了嗎？

---

## 證據自檢

- 本檔所有數字都來自來源的摘要或網頁摘錄，沒有重跑任何資料。GitClear、Faros、CodeRabbit、Sonar、DORA 屬業界報告，沒經同儕審查，而且多半只證明相關。
- 標「業界觀察，未查證」的：一次性小函式泛濫的量化、過度防禦的量化、錯誤處理風格不一致的比例、AI 是否更常製造多份事實來源、LLM agent 陷入「修一個冒一個」的頻率、巨型 PR 的審查品質門檻。
- 部分 linter 規則代號與工具名（E722、W0718、no-empty、import-linter、ArchUnit、dependency-cruiser、naming-convention）憑一般知識，本次沒逐一查證連結；已查證的有 ruff BLE001、S110、ARG001 與 ESLint no-useless-catch。
- D'Ambros 2009 原文連結本次 404，結論只經後續文獻轉述；熱點定義只經二手摘要確認。
