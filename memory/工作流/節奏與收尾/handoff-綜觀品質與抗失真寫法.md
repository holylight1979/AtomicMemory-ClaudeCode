# handoff-綜觀品質與抗失真寫法

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: handoff, 續接, 下 session, next-phase, /continue, 交接, 接續 prompt, 綜觀, 失真, 多 session, 寫接續文, handoff 品質, 新開 session
- Created-at: 2026-06-18
- Related: feedback-workflow-discipline, 跨session資訊失真機制與對策, a執p-自執驗上p-自動完工協議, goal-driven-verify-loopkarpathy-吸收, feedback-completion-gates, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, feedback-整理歸檔任務-狀態變更即決策-活項對照閘-方向不明動手前先問, feedback-收尾報告使用者視角四要素-白話綜觀非片段細節, feedback-模糊裁示不硬化先深問-決策選項含使用到再問, 並行llm即時通訊-inbox機制, 回訪機制-改完一週後看數據交給到期自動跑-交接以接手者零記憶為前提, workflow-rules

## 知識

- [固] **結構完整≠語意正確（本 atom 的定位）**：既有 /handoff 六區塊 + [[feedback-workflow-discipline]] 只保證「欄位都在」；本 atom 補**品質層**——欄位填好仍可能漏 why、漏疑問、過度聚焦大需求下的小細節，導致新 session 無法綜觀。硬前提：下個 Claude 看不到本次對話任何內容，凡「剛才/之前/那個方法」皆斷鏈，文件必須自足。
- [固] **大局 vs 細節雙防護，缺一即偏**。防失大局：目標(寫 outcome 與「為何而做」，非任務清單)＋每個決策附一行 why＋未解問題獨立區＋下一步＋成功判準。防失細節：現狀三態(已完成/進行中/未開始)＋失敗嘗試清單＋危險區＋檔案路徑:行/關鍵 command/git ref。只有細節→知做什麼不知為何；只有大局→重踩坑重做。
- [固] **只寫 delta，不複述通則（直擊「多餘又重複的非重點」痛點）**：handoff 只放「本 session 特有、會變、接手必知」的增量；通用規則/SOP（如「SVN 別亂 commit」「git 流程」這類每次重抄的）用 [[連結]] 帶過、不整段重貼。重複樣板會稀釋新 session 的注意力預算（context 遠未滿即 drift），且降低真正重點被讀到的機率。一句話：**寫變化與特例，不寫常態與通則**。
- [固] **why（前因後果）是壓縮時最先被犧牲、又最致命的部分**：只寫「改用方案 B」不寫「因為 A 有並發問題」，會讓新 session 無法判斷此決策是否仍適用——這正是「過度聚焦小細節、漏掉大 why」的根。每個已鎖定決策＋每個被否決的 alternative 都要附理由（≈ADR 的 Context/Decision/Consequences；所有成熟交接格式都強制記 why）。
- [固] **未解問題/不確定性必須獨立成區（直擊「沒寫到疑問」痛點）**：沒寫出的不確定，新 session 會用「看似合理的假設」默默填補 → 隱性 drift、錯誤發展、錯誤認知。每條未解問題寫成「可被回答的具體問句」，逼下一步顯式決策、而非默默腦補。
- [固] **標「已驗證✓ vs 假設✗」＋ load-bearing 事實逐字保留＋矛盾顯式裁決**：未驗證項標「待確認，勿據此鎖死」(防 anchoring 早期假設鎖死、防 compounding 小錯滾雪球)；數值/路徑/識別碼逐字保留原文、不改寫成模糊描述(防 lossy-summary 填補式捏造)；新舊資訊衝突直接寫「以 X 為準、作廢 Y」＋時間戳、不並列丟給下游(防 context clash)。機制全表見 [[跨session資訊失真機制與對策]]。
- [固] **強制對抗式自我複審（最高槓桿、有實證的剛性需求）**：寫完 handoff 後作者不會自動發現自己的缺口，必須再跑一輪批判複審，逐項自問——新 session 懂為何而做嗎？漏寫未解問題嗎？把假設當事實寫了嗎？重貼了通則嗎？關鍵約束有放在首尾嗎？2026-06 dogfood 實證：CC 直到被使用者提醒『認真做兩項確認』，才在自己剛寫的 next-phase.md 找到幾個會引發失真/錯誤認知的缺口並補上 → 證明 self-critique 必須**制度化**（流程強制一步），不能靠自覺。
- [固] **接收端開場先回讀（read-back，閉環確認）**：/continue 或新 session 接手時，先用自己的話覆述「現狀＋下一步＋我理解的約束」再動工（≈醫療 I-PASS synthesis-by-receiver / 交班 read-back），當場暴露理解落差；文件要自足到允許接手者「回問澄清」而非盲目執行。長度紀律：全文應能 ~2 分鐘掃完，過長＝混入低訊號內容，刪冗餘 log/樣板。

## 行動

- 寫 handoff/next-phase → 過「大局 5 項＋細節 4 項」雙清單，缺項補齊才交付
- 只寫 delta；通用規則/SOP 用 [[連結]] 帶過、不整段重貼
- 每決策附 why；未解問題獨立成區；load-bearing 事實逐字保留並標 verified-vs-assumption
- 交付前強制跑一輪對抗式自我複審（對照本 atom 自問清單），別等被提醒才補
- 接手端先 read-back（覆述現狀+下一步+約束）再動工
