# 寫碼風格外部查證：控制流階梯、巢狀閾值、扁平化過頭

> 查證日期 2026-09-03。用途：`rules/coding-style.md` 各條的來源與依據；規則本體只留結論，這裡放出處。
> 查證方式：研究 agent WebSearch/WebFetch 6+ 來源，另派 Codex（gpt-5 系）獨立審閱；兩者分歧處在 §6 記錄。

## 1. 控制流「偏好階梯」

業界沒有單一階梯，三個獨立脈絡拼起來與規則一致：

| 來源 | 主張 | URL |
|------|------|-----|
| W3C Rule of Least Power（Berners-Lee） | 能用表達力最弱的構件就別用更強的 | https://www.w3.org/2001/tag/doc/leastPower.html |
| Duffield: Array Functions and the Rule of Least Power | 套到迴圈：`some/every < find < filter < map < reduce < forEach < for`；弱構件能犯的錯少、回傳型別一眼可知 | https://jesseduffield.com/Array-Functions-And-Rule-Of-Least-Power/ |
| C++ Core Guidelines ES.71–76 | range-for > for（有明顯迴圈變數）> while（無迴圈變數）；避免 do-while、goto | https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines |
| Code Complete ch.17 | 遞迴前先考慮迭代＋stack；階乘/費氏用遞迴是教科書的蠢例 | https://www.goodreads.com/notes/11357965-code-complete/56969661-phong-b-nguyen/28992962-5d04-4cd2-b482-c8cad94fe0a3 |
| Ajami/Feitelson 實測（220 名工程師） | for 顯著比 if 難、倒數迴圈比正數難、部分否定式讓述詞更難 | https://link.springer.com/article/10.1007/s10664-018-9628-3 |

**採用的分層依據**：不用語法名稱分，用「讀者要追蹤多少狀態」分。直線 → guard/早退（讀完即忘）→ 有界迭代（長度、型別可預測）→ 分支（switch 認知分低於 if-else 鏈）→ 無界迭代 → 遞迴（SonarSource +1）→ 高階/metaprogramming。與 SonarSource 計分和工作記憶研究同源。

## 2. 壓平巢狀的手法

| 手法 | 一句白話 | 來源 |
|------|---------|------|
| Guard clause／早退 | 先踢掉例外，主路徑不縮排 | https://blog.codinghorror.com/flattening-arrow-code/ |
| 反轉條件 | `if ok {…}` 改 `if !ok return` | https://www.youtube.com/watch?v=CFRhGnuXG-4 （CodeAesthetic: Never Nester） |
| 抽出函式（深模組） | 內層迴圈體有名字就抽，但要抽成介面小、做事多的深模組 | https://www.mattduck.com/2021-04-a-philosophy-of-software-design.html |
| continue/break 提早離開 | 迴圈內不包 if，不符者直接跳；SonarSource 不對無標籤 break/continue 記分 | https://blog.scitools.com/cognitive-complexity-metric-plugin/ |
| 表驅動 | if 鏈長 → 查表/dict dispatch；「能用 if 選的都能用表選」 | https://www.oreilly.com/library/view/Code-Complete,-Second-Edition/0735619670/ch18.html |
| Result/Option 管線（ROP） | 錯誤走另一軌取代層層 null 檢查；作者自警別套到領域錯誤以外 | https://fsharpforfunandprofit.com/rop/ ／ https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/ |
| 合併條件 | 同運算子串 `a && b && c` 只算 1 分，混用才加分 | SonarSource 白皮書（§3） |

Codex 補充：Set/Dict 預建索引不只壓平巢狀搜尋，常把重複掃描降成單次查詢；但要以資料量與可讀性為準，不能見雙層迴圈就機械改寫。

## 3. 巢狀深度閾值

| 來源 | 主張 | URL |
|------|------|-----|
| Linux kernel coding style | 「超過 3 層縮排你就完了，去修程式」；另附 5–10 個區域變數上限 | https://docs.kernel.org/process/coding-style.html |
| Code Complete §19.4 | 引 Chomsky/Weinberg（Yourdon 1986）「少有人能理解 3 層以上巢狀 if」；多數研究建議 ≤3–4 層 | （書） |
| CodeAesthetic: Never Nester | 3 層為容忍上限 | 同 §2 |
| SonarSource Cognitive Complexity | 每個控制結構 +1、再加當前巢狀層數；早退、方法呼叫、switch 各 case 免費；直接遞迴 +1；函式預設閾值 15。第 3 層一個 if = 1+2 = 3 分 | https://www.sonarsource.com/docs/CognitiveComplexity.pdf |
| Cowan 2001 | Miller 7±2 修正為約 4 個 chunk | https://www.cambridge.org/core/services/aop-cambridge-core/content/view/44023F1147D4A1D44BDC0AD226838496/S0140525X01003922a.pdf/the-magical-number-4-in-short-term-memory-a-reconsideration-of-mental-storage-capacity.pdf |
| Hermans《The Programmer's Brain》 | 以工作記憶解釋讀碼超載 | https://www.happycoders.eu/books/the-programmer-s-brain/ |
| arXiv 2602.07882（2026） | 巢狀對 LLM 的難度呈 Θ(n²)（扁平為 Θ(n)）；扁平化重寫讓修復任務提升至 20.9% | https://arxiv.org/html/2602.07882v1 |

工作記憶推論：每層 = 一個待記條件，3 層 + 函式本身目的 = 4 chunk 剛好滿載，第 4 層必溢出。此為合理解釋而非證明（見 §6）。

## 4. 扁平化過頭（LLM 常犯的反面）

| 反面 | 主張 | URL |
|------|------|-----|
| 淺模組／小函式氾濫 | Ousterhout：介面成本 > 功能；Sridharan：失去局部性、命名負擔、ravioli code | https://www.mattduck.com/2021-04-a-philosophy-of-software-design.html ／ https://news.ycombinator.com/item?id=14988206 |
| 過度 one-liner | Google Python 風格明禁多重 for 子句的 comprehension，「為可讀性最佳化，不為簡潔」 | https://google.github.io/styleguide/pyguide.html §2.7 |
| 聰明 > 清楚 | Go 諺語 Clear is better than clever；Kernighan「寫時用盡聰明，除錯時怎麼辦」 | https://dev.to/chenge/go-proverbs-from-robpike-34gl ／ https://en.wikiquote.org/wiki/Brian_Kernighan |
| 早退散落 | 30 行以上函式中隨處 return 反而看不到流程 | https://schneide.blog/2010/03/01/readability-of-guard-clauses-in-methods/ |
| LLM 實證 | KISS Sorcar：LLM 傾向多餘抽象/helper/間接層；「What to Cut」預測 AI 生成中 review 時會被刪的函式（AUC 87%） | https://arxiv.org/pdf/2604.23822 ／ https://arxiv.org/abs/2602.17091 |

## 5. Codex 獨立審閱要點（2026-09-03，codex exec）

- 「能用 if 就不用 for」是類型錯誤：分支處理選擇、迴圈處理重複。LLM 誤用型：動態集合硬展開成多個 if、為避 while 用不自然的 for 做重試/狀態收斂、迴避 any/find、重新實作標準庫。
- 「絕對精準」對 LLM 無牽引力，會被當自我肯定；要換成契約、測試、邊界檢查、不確定性標示。
- 「全知視角、高速重整」一半有害：鼓勵過度讀檔與無關重構。改成「全貌意識 + 明確停止條件」。
- 集中重複邏輯要限定「必須同步變更的知識」，不是外觀相似的 code；否則長出萬用 helper 與參數爆炸。
- 「明點」不適合寫成人格，要變成固定觸發點（動手前、結果違反預期、交付前）+ 固定輸出（目標/事實/假設/下一個可判別動作）+ 證據不符時更新假設而非辯護。即貝氏更新式除錯 + 最小可判別實驗。
- 與 Karpathy 守則四處張力：think-before-coding vs 高速動工、simplicity vs 語法崇拜、surgical changes vs 反覆重整/集中邏輯、goal-driven vs 全知視角。
- 建議優先序：正確與安全邊界 > 專案既有約束 > 可讀可驗證的簡單 > 最小修改面 > 個人語法偏好。

## 6. 研究 vs Codex 的分歧

| 議題 | 研究 agent | Codex | 規則採用 |
|------|-----------|-------|---------|
| 巢狀 =3 的理論根據 | 四個獨立來源共識 + Cowan 4 chunk 可解釋 | 沒有研究證明第三層是跨語言硬臨界；7±2 或 4 chunk 不能直接換算成程式層數 | 3 層門檻採共識；工作記憶只當解釋不入規則；判準用 Codex 的「三個獨立條件 vs 同一局部決策」 |
| 控制流階梯 | 最小威力原則支持「弱構件優先」 | 反對拿語法名稱排尊卑 | 先選語義，再在同語義候選裡取讀者要記最少狀態的構件 |
| 高速動工 | 未涉及 | 建議刪，LLM 會讀成少查證 | 保留意圖，改寫為「先立最小可驗證假設就動工、小步推進」 |
