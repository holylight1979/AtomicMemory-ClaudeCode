# 下一波調整計畫：讓「用 CC＋原子記憶系統交 AI 寫程式」的人自動得到你要的那些東西（第 3.1 版：SGI 四題回信併入；併入兩專案的 Codex 審查裁決、補角色／變量／奇耙設定三節；等你答第十節、根層 Codex 審完才定實作順序）

> 給誰看：你。再來是接手做這波調整的根層 session。
> 這份在說什麼：上一波（三方討論、R4～R6）是「朝解決問題去驗」；這一波倒過來——把那一波**旁觀 AI 怎麼失手、怎麼才做對**吸收到的經驗，逐條變成記憶系統本身的機制（hook、MCP、atom 注入、分範圍萃取、品質變量），讓未來任何一個裝了 CC＋原子記憶系統的人、任何一個專案，AI 一接手就自然懂得怎麼思考判斷、怎麼深入、怎麼綜觀，不靠人提點。
> **範圍（你 2026-10-08 補述的原話拼的）**：本次改進**只限根基**——根層、專案層、公司層全域都能用的**帶變量規則**；**本次參與的兩個專案預設不再做任何進一步調整**（已做的擴欄、副本工具只當樣本與輸入）。根層負責吸收、理解、轉化，並定清楚未來根層與專案層各扮演什麼角色、根層要調什麼、開什麼變量給專案層、多專案的奇耙設定怎麼處理。兩個專案 session 是專案層視角；負責專案的程式人員受的開發教育不同，思路會不同，這是輸入的價值，不是要統一的東西。
> 讀法：每句後面標可靠度——【試過】【看程式知道】【推測】【大家同意】；「機制」欄寫的是提議，標「做了」的才是已存在。
> 名詞：**hook**＝CC 在每個動作前後自動跑的小程式；**MCP**＝CC 外掛的工具伺服器（atom_write 等）；**注入**＝把記憶卡片塞進 AI 的上下文；**萃取**＝從對話或程式裡把知識寫成卡片；**變量**＝可以用腳本算出來的品質數字，或專案可以覆蓋的設定值；**部位**＝專案裡一塊有自己邊界的東西（大地圖、戰鬥、Server…），`overview-map.md` 一列一個；**導讀卡**＝每個部位一頁的「做什麼、上下游、動手前必問、已知病灶、驗法」；**ledger**＝驗證帳本，腳本每印一行 PASS／FAIL 就自動記一筆的檔。

## 一、你要的清單（逐項編號，後面所有表都對這個號）

| # | 你要的（原話拼的） |
|---|---|
| 核 | AI 處理眼前需求時同時適度綜觀專案，不繞同一死胡同、不修症狀亂改 |
| 1 | 第三人在旁邊看 |
| 2 | 新碼不被舊碼帶壞 |
| 3 | 腳本自帶驗證 |
| 4 | 不用提點就能自己判斷什麼最該修 |
| 5 | 數字不帶偏、數量不是壞味道 |
| 6 | 程式能擋的不交給 AI 判斷 |
| 7 | 壞味道含：分太細、繼承太多、難維護、太慢、太吃記憶體 |
| 8 | 跟記憶系統有關聯 |
| 9 | Codex 與 Claude 拿同材料各自想 |
| 10 | 沒試過的不算結論 |
| 11 | 一個構想拐三個彎就是壞味道 |
| 12 | 沒 bug 但人讀要跳很多層也要測 |
| 13 | 找到解法要回報、進文件、能修就修並證明 |
| 新 | 對未來的使用者與新專案也成立（零卡片、零歷史的專案一接手就有這些行為）——本波新增；**是硬要求還是目標，等第十節第 1 題** |

## 二、三邊共識的骨架（四樣基礎設施 × 五個過程數字 × 一層結果題組）

上一波靠人補了五張卡、一張表、三支檢查器才成立「有東西可看」【試過，SGI】；三邊各自寫完發現要補的不是更多規則，是四樣基礎設施【大家同意】：

| 基礎設施 | 一句白話 | 誰提 |
|---|---|---|
| ① 部位 profile 當一等公民 | `overview-map.md` 一列＝一個部位的檔案：卡、病灶文件在哪、量尺在哪、檢查器清單、讀路徑樣本、必問第四問；atom 加 `Part:` 欄 | SGI、TSLG |
| ② 驗證紀錄有落點 | hook 自動收腳本尾行哨兵 `<NAME>_CHECK PASS|FAIL` 進專案 ledger；收尾、審查者、下一 session 都看 ledger 不翻信箱 | SGI；TSLG 的工具自檢併同一收集器 |
| ③ 教訓有歸宿 | 萃取時先問「下次會在哪個路徑再遇到」→ 有部位就進該部位的**病灶文件**（固定格式表），卡只留一行指標；現況帳與清單一律文件 | 三邊（兩專案都撞過卡片 3072 預算） |
| ④ 閘有自然數據 | 五個過程數字 SessionEnd 自動算；每條機制另配一個**結果題組**（固定輸入＋預核答案＋可重跑指令） | TSLG 提五數；兩邊 Codex 都指出五數只量「流程發生了」不量「要求達成了」→ 加結果題組【大家同意】 |

**五個過程數字（S1～S5，全部腳本算，禁 AI 估；只設下限門檻、不設上限獎勵，避免 AI 為分數亂讀）**

| 代號 | 名稱 | 怎麼算 | 現況 |
|---|---|---|---|
| S1 | 首改前綜觀 | 第一次改某部位前：有沒有讀該部位導讀卡、讀了幾個 Depends 檔、跨幾目錄（`_overview-hub.log`） | 做了（R4、R5）；報表工具要做 |
| S2 | 同題改幾輪（代理） | 主尺＝同檔 fix 類提交數 ≥2（14 天窗），pairs 只輔助、同一 commit 不計對；排除 `.claude/memory/` 與自動收割提交 | git／svn 版 SGI 原型做了（`_tools/refix_churn.py`，當樣本）；根層收進 T2 |
| S3 | 修根因比例 | 定位三行「根因層」寫根因且「前例」指到一張存在的卡（`located_quality`） | 要做 |
| S4 | 工具靜默失效率 | SessionStart 健檢 selftest 紅燈數；ledger 漏收／誤收由單元測試三案守 | 要做 |
| S5 | 注入命中率 | 被注入的卡在同 session 後續被讀／引用 vs 被判無關 | 要做 |

**數字→行動回路（沒有回路 scorecard 只是儀表板，TSLG 裁決）**：S2 榜單前 N 自動成「下一張導讀卡／病灶文件」候選並在注入時附上；S1 低於專案基線連續 N 場 → 提醒該部位可從 dry-run 升擋。

**結果題組（每條機制配一題，放 `<專案>/.claude/verify/cases/`，與 ledger 同一個家；格式：輸入、預核答案、重跑指令、命中／誤報怎麼算）**
- 核：三個歷史案例回放（已有材料做法，全貌§三）＋真實 session 的 S1／S2。
- H3 召回：已標註「相關卡」的路徑案例，量召回率與無關注入率。
- H5／M4 候選池：固定候選池＋預核優先項，量前三命中（TSLG #88 文件、SGI 控制塔 §9 是現成正解集，都偏小）。
- H6 ledger：重播三反例（無關 PASS、改完後的舊 PASS、非零 exit）量攔截率。
- T2：人工標註「同題」提交樣本，量準確率。
- P2 證法：刻意改壞一個常數看 FAIL 檢出。
- 新：零卡 repo 第一個 session 有部位入口＋骨架卡注入＋空段提示（「有綜觀」不是 bootstrap 能保證的，不進驗收）。

## 三、機制總表（併三邊與兩份 Codex 裁決；每條回指第一節編號；「層」＝根層通用／專案覆蓋）

> 落點代號：H＝hook、M＝MCP 工具、A＝atom 注入／萃取、T＝根層工具或 skill、R＝規矩（rules／範本）、P＝專案層樣板（根層只定格式，專案自己填）。

| 代號 | 對應# | 機制（一句白話） | 側觀瞬間（證據） | 層 | 驗 |
|---|---|---|---|---|---|
| H1 | 核 | OverviewHub 注入句型改「找到第一個根因後再找第二個；找不到就寫一句『為什麼不存在』才算完」；不再用「交出 X」句型 | 回放最素提示找到兩個根因、要求「先寫定位」反而找一個就停【試過】 | 根層；句型可覆蓋 | 題組「核」 |
| H2 | 核 | PostCompact 重注「主目標＋目前部位」兩行 | 長對話前文把視野釘在某層【推測，TSLG】 | 根層 | S2 |
| H3 | 核、2、8 | **路徑→卡片召回**：讀或改檔 X 時列 `Depends: path:` 含 X 的 atom 一行指標；atom `Part:` 欄做部位親和加權（`part_affinity_boost`），不同部位 cold 卡降權 | SGI 卡在、關鍵字沒對上、四個月後重摔【試過】；TSLG cold 卡 4 顆 3 顆無關【試過】 | 根層機制；Depends／Part 專案填 | 題組 H3、S5 |
| H4 | 核、6 | R5 擋的判準改「讀了該部位導讀卡＋至少一個 Depends 檔，且三行有交」（純數量只進 scorecard，不當閘——Codex：讀檔數當閘就是被數字帶偏）；三行只在 thinking 時提醒改放工具參數；Bash 改檔型指令（sed -i、python 寫檔）納入同一檢查；前例可填「無」但 S3 另計 | T12 五筆負樣本＝注入後讀 0 檔就改【試過】；Codex B3【看程式知道】 | 根層；`deny_parts` 專案 | S1、S3 |
| H5 | 核、4 | 注入文字帶「填空範本」：前例那行要填一張存在的卡名或「無」；提示詞出現「該修什麼／優先／重構／改了還是不對／又壞了」→ 注入當前部位病灶文件前 N 筆＋根因層卡＋兩問（這個數值有幾份存法？這個失敗有沒有訊號？） | 盲測單挑 0 中、挑 3 件 1 中【試過】；大地圖兩個歷史案例共同形狀【試過】 | 根層機制；清單專案填 | 題組 H5 |
| H6 | 3、10、13 | **驗證紀錄收集器**：PostToolUse 抓 Bash 輸出最後一個整行哨兵（`_CHECK PASS|FAIL`、量測類 `DONE`）寫 `<專案>/.claude/verify/_ledger.jsonl`，每筆綁 ts、session、cmd、exit、受測版本（VCS rev＋改動檔）；Stop 閘：宣告「修好／綠／PASS」或句子標【試過】時對本 session ledger 核，沒有對應筆就提醒（只認 PASS，DONE 是量測不是判定） | 證據只住信箱與 scratchpad【試過】；SGI 045 先報後做【試過】；SGI 原型 `_tools/verify_ledger.py` 實跑一筆【試過，當樣本】 | 根層 hook；格式專案不改 | 題組 H6、S4 |
| H7 | 3、6 | SessionStart 健檢跑專案登記的 `tool_selftests[]`（指令＋預期哨兵），紅燈進 Guardian，結果寫 `workflow/` 報告或 ledger；**卡不動**，只有狀態翻轉（接線↔未接線）才改卡一行指標 | TSLG 工具卡病灶段「兩支 hook 未接線」已過時【試過】；反覆 append 會撞三個閘【看程式知道，Codex】 | 根層 hook；清單專案填 | S4 |
| H8 | 7d、7e | 改了有「量尺」欄的部位、收尾前沒跑量法 → Stop 提醒；提示詞含「太慢／卡／記憶體／效能」→ 注入該部位量尺與基線卡；基線卡 write-gate 檢「尺＋條件＋日期」三欄齊 | 太慢／太吃記憶體到最後才有量法【試過】；Editor 配置數字比實機高 13 倍【試過】 | 根層 hook；尺與門檻專案填 | 題組「基線卡三欄齊」 |
| M1 | 8 | write-gate 擋回訊息分三型說「這類卡該怎麼收」：指標卡只留一行指標、互補卡 append 前先算預算、超了路由到該部位文件＋卡一行指標、現況帳放文件；標題含「導讀／hub索引」的**新建**卡檢查五段齊＋`Depends` 必填（不回溯既有卡） | 指標卡撞 3072、互補卡被判矛盾、Server 卡 append 超預算【試過】 | 根層 MCP | 寫入被擋後第二次就過的比例 |
| M2 | 2、13 | knowledge_harvest 萃取路由：先問「下次會在哪個路徑再遇到」→ 有部位 → 進該部位病灶文件、卡只在指標缺時 append 一行；沒有 → 問「換專案還會遇到嗎」→ 會 → 先跑「去專案細節」檢查（專案名、路徑、代號）再走 global，realm 拒了落 shared 標「候選全域」不重試；只在記憶系統裡 → local。收尾報告加「本 session 證據落在哪個持久路徑」欄 | realm 閘三次擋回一次【試過】；教訓散在 CHANGELOG 尾巴【看程式知道】 | 根層 MCP | S2、S5 |
| M3 | 1、9 | `second_opinion(kind, part)`：打包（部位卡＋病灶文件前 N＋本 session diff 或草稿＋ledger 紀錄）→ 材料雜湊 → replay-guard → `codex exec`（唯讀、skip-git-repo-check、材料內嵌）→ 回「它的表／分歧／裁決」三段；**同材料獨立作答的定義**＝Claude 先把自己的表落檔再開 Codex 輸出，兩個檔的時間戳就是證據；Stop 時 diff 落在 deny 部位建議跑 | 每趟手工拼材料、踩兩個坑【試過】；Codex 5 推翻全因材料沒附執行紀錄【試過】 | 根層 MCP | 腳本數信件／收尾報告「三段齊全率」（不手數） |
| M4 | 4 | `project_smells(part)`：回該部位候選池前 N 筆（專案登記 `smells_cmd`／`smells_report`）；報告過期只提醒，不在 SessionStart 背景跑 | 候選池人手跑、人手讀【試過】 | 根層 MCP；產生器專案 | 題組 H5 |
| T1 | 新 | `/overview init`（或 `install.py --scaffold-parts`）：掃頂層目錄＋VCS fix 熱點 → 產 `overview-map.md` 草稿＋每部位五段卡骨架（非程式路徑 `_AIDocs/`、`.claude/memory/`、設定目錄預設入表）；骨架卡走受閘控的寫入、Lv1 先映射既有閉合清單（Server／Client／Tools／文件…）確需才開；處理「表有列、卡沒建成」不一致；`install.py --verify` 檢查表存在且每列卡名存在 | 兩專案卡、表全是人手寫【試過】；「文件」Lv1 被擋【試過】 | 根層工具；內容專案填 | 題組「新」 |
| T2 | 核、S2 | `refix-metric.py`：git 與 svn 都算；主尺 fix commit 數 ≥2、pairs 輔助、同 commit 不計對；排除記憶目錄與自動收割提交；fix 判定樣式可覆蓋（含中文「修正／修復／修補」） | SGI 原型兩種輸入各一組【試過，當樣本】；git 那組幾乎全是自動收割提交【試過】 | 根層 | 題組 T2 |
| T3 | 核 | `overview-hub-report.py`：log＋ledger → 每 session 一行 S1～S5；SessionEnd 自動寫 scorecard 到 `workflow/`；帶「數字→行動回路」（第二節） | — | 根層 | S1～S5 |
| R1 | 3 | 腳本尾行哨兵格式寫進 rules；PostToolUse 看 `.py` 跑完沒哨兵提醒 | 三支檢查器哨兵格式不一【試過】 | 根層規矩；名專案自選 | S4 |
| R2 | 10 | 證據四級＋自檢段從「信件格式」升為所有收尾報告格式；anti_evasion (a) 欄帶證據級；驗法與 H6 合併（格式本身不當驗法） | 信件自檢有效、收尾訊息沒有【試過】 | 根層規矩 | H6 |
| R3 | 5、11、12 | 掃描數字只進報表不進結論；導讀卡「權威原則」段可標「這裡的分層是刻意的」；profile「讀路徑樣本」欄；構想彎數只留自檢欄位不裝測量。驗法：「跳很多層」＝專案掃描器 >6 彎方法數前後（TSLG 現 194 可量）；「數字不帶偏」＝基線卡三欄齊；「刻意分層 vs 分太細」人判、標不可量 | 4150 純轉接前 15 筆全刻意分層【試過】；兩尺沒校準【大家同意】 | 專案填；根層範本 | 如左 |
| P1 | 6 | 專案層 `prebuild_check.py` 樣板：讀 profile 檢查器清單依序跑、任一 FAIL exit 1；接不接打包前是政策 | SGI 第一天 FAIL【試過】 | 專案樣板 | — |
| P2 | 13 | 行為保持重構證法做成 skill 樣板（舊源碼解析預期 vs 新建置反射實跑，印哨兵）；去專案細節後可進 global | SGI 44/44【試過】 | 專案樣板；根層 skill | 題組 P2 |
| A1 | 核、4、10 | 三邊 AI 在討論裡自己犯的行為偏差寫成根層 atom（把第一句當全部、從最大檔出發、看函式名下結論、連寫「無待答項」其實沒派工）；**只涵蓋核、4、10**，其餘項不涵蓋；驗法＝有沒有被召回，不是有沒有遵守 | 全貌§二【試過】 | 根層 | S5 |

## 四、未來的角色分工（這是你要根層想清楚的事）

**根層（`~/.claude`，記憶系統本體）**
- 只做機制、格式、預設值、量尺、報表、閘；**不寫專案內容、不替專案填表**。多專案的差異一律靠變量吸收，不在 hook 裡寫專案分支。
- 每個機制出廠三件：verify 案、變量預設、一句「專案什麼情況該覆蓋」。
- 根層 session 的日常角色＝看 scorecard 與回路（哪個專案 S1 低、哪個部位 S2 高、哪個閘誤判多），調預設值或修閘；不派專案工。
- 根層 session 動手改記憶系統前，自己也走同一套：動手前讀 `_AIDocs/Architecture.md` 對應列＝它的導讀卡，定位三行放工具參數，哨兵進 ledger（根層自己也是一個專案）。

**專案層（`<專案>/.claude/`）**
- 擁有並維護：`overview-map.md`（profile 表）、導讀卡、病灶文件、量尺門檻、檢查器清單、`overview-hub.json` 覆蓋值、`verify/cases/` 題組。
- 不改 hook／MCP；要根層改機制 → 寫成可貼上的 prompt 交使用者（既有規矩）。
- 專案 session 的 AI 在未來每次改碼的自然流程（全部由機制推著走，不靠記）：碰部位→整卡注入＋候選池前 N→定位三行放工具參數（含第二根因或「為什麼不存在」）→改→跑量法與檢查器→哨兵自動進 ledger→收尾帶證據級，宣告「修好」被對帳。

**專案層視角的修正（SGI，projects/073；TSLG 回信後補）**
- 流程起點太晚：最貴的失敗（存檔重構三個月退回）錯在**立案層**，改碼那天每步都沒偏。H3／H5 的「碰部位」要含 Edit 落在 `_AIDocs/`、計畫檔、`_staging/`；那時注入的不是部位卡，是**權威地圖**（要查什麼→唯一來源）→ profile 加 `authority_map` 欄。
- 少「驗收規格」這個物件：每次提交帶「必須發生／禁止發生／驗證指令」三段，正是 ledger 要對帳的承諾、也是結果題組的來源 → 根層出預設範本 `verify_spec_template`，專案可關；ledger 筆要能指向哪條規格。
- 少「跨 repo 的上下游」：一條協定跨 3 repo 2 台 server、一個檔同時是 Client 與 Server 部位（`<Compile Link>`）→ profile 加 `upstream`／`downstream`，`Part:` 允許多值。
- SGI 最容易回到修症狀的四個環節【推測，樣本小】：跨 server 回覆值翻譯層（只看到一半 handler 就補 if）、存檔層（沒先查 SaveMode）、驗收規格驅動的工具修補（每輪只修當下炸的）、框架層無卡。對應：前兩個靠 `locate_extra` 第四問；第三個給 H5 一個可機器偵測的觸發＝**同一檔同一 session 第二次 Edit**；第四個＝無卡列注入上游卡的病灶段。
- 根層 session 的 E2E 不得碰專案 live log／ledger——寫進根層自己的導讀卡病灶段，不只寫 verify。

**公司層（`/org` 接上的公司記憶 repo）**
- 放全公司共用的變量預設（例如大家都 svn、提交訊息 Big5、哨兵命名、fix 判定樣式）與工具卡；合併順序 **根層預設 < 公司層 < 專案層**（現在只有根層 < 專案層，公司層那段要加）。

## 五、變量總表（根層開給專案層的；全部住 `<專案>/.claude/overview-hub.json`，公司層同名檔可先蓋一層）

| 變量 | 預設 | 專案什麼情況該覆蓋 | 狀態 |
|---|---|---|---|
| `enabled` | true | 整個專案不要注入閘 | 做了 |
| `dry_run` | true | 要擋 | 做了 |
| `deny_parts` | [] | 只對成熟部位擋 | 做了 |
| `max_card_chars` | 6000 | 卡特別長或 context 緊 | 做了 |
| `locate_template` | 三行預設 | 專案想換問法 | 做了 |
| `locate_extra` | {} | 某部位要第四問 | 做了 |
| `min_overview_evidence` | `{"card": true, "depends_files": 1}` | 部位 Depends 少或檔很大 | 要做（H4） |
| `part_affinity_boost` | 1.5 | cold 卡太多或太少 | 要做（H3） |
| `path_bases` | [專案根] | 表裡路徑有第二個基準（TSLG 熱更子目錄＋專案根兩種）【試過，tslg/062】 | 要做 |
| `vcs` | auto（子目錄各自偵測 `.svn`／`.git`） | 工作區混多 repo（SGI root git＋sgi_server svn）【試過】 | 要做（T2、H6） |
| `log_encoding` | utf-8 | svn 訊息 Big5【試過，SGI】 | 要做（T2） |
| `fix_patterns` | fix／bugfix／hotfix／修正／修復／修補 | 團隊提交慣例不同 | 要做（T2） |
| `refix_window_days`、`refix_exclude` | 14、[`.claude/memory/`、收割提交] | 節奏不同 | 要做（T2） |
| `ledger_path`、`sentinel_regex` | `.claude/verify/_ledger.jsonl`、`^[A-Z][A-Z0-9_]*_(CHECK (PASS|FAIL)|DONE)$` | 既有腳本哨兵格式不同 | 要做（H6） |
| `smells_cmd`、`smells_report`、`smells_max_age_days` | 無、無、7 | 有候選池產生器 | 要做（M4） |
| `tool_selftests[]` | [] | 有要健檢的工具 | 要做（H7） |
| `codex_review_on_stop` | false | 想在 deny 部位改完自動跑第二意見 | 要做（M3） |
| `codex_cmd` | 既有三旗標樣板 | 沙箱型別不同（本機 read-only 曾 1385）【試過】 | 要做（M3） |
| `min_overview_evidence.part_files` | 1 | Depends 指的檔跟這次改的 Manager 無關時，「讀過該前綴下任一檔」才合理【SGI】 | 要做（H4） |
| `vcs_roots[]` | 自動偵測 | 工作區有 12 GB 的 svn 子目錄，auto 掃它幾十秒；要明列哪些 repo 進 `files_changed`（`ledger_files_scope`）【SGI】 | 要做 |
| `commit_encoding`／`commit_cmd_template` | UTF-8 | svn 提交不帶 `--encoding UTF-8` 訊息以 Big5 存庫、事後改不掉；任何根層自動提交工具都得吃【SGI，試過】 | 要做 |
| `refix_same_commit_pairs` | false | 一筆 commit 改 20 檔把 pairs 灌高【SGI、TSLG】 | 要做（T2） |
| `tool_selftests[].expected` | PASS | 檢查器「預期 FAIL 直到某事處置」要能登記，否則健檢天天紅【SGI】 | 要做（H7） |
| `readonly_paths[]` | [] | 自動生成產物（protoc、ExcelToData、auto_generate）Edit 一律擋、不分 dry_run【SGI】 | 要做 |
| `build_cmd`（按部位） | 無 | 同工作區多 TFM、熱更 dll 另一套建置；H8／P2 要知道怎麼建【SGI】 | 要做 |
| `authority_map`、`upstream`／`downstream`（profile 欄） | 空 | 立案層召回、跨 repo 上下游【SGI】 | 要做（表格式） |
| `verify_spec_template` | 三段範本 | 專案不用驗收規格可關【SGI】 | 要做 |
| `prebuild_checks[]` | [] | P1 讀的清單【SGI】 | 要做 |
| `console_codepage`／`PYTHONIOENCODING` | utf-8 | 主控台 950，hook spawn 的 python 印中文亂碼【SGI，試過】 | 要做（根層工具一律設） |
| `test_runner` | auto（有測試框架先用） | 零測試專案走反射／離線載入／`--check`【SGI】 | 要做（H6／P2 不假設有測試框架） |
| `commit_policy` | ask | 使用者個人規矩「上GIT」口令；記憶系統 auto【SGI】 | 已是規矩，做成變量 |
| `docs_index`／`changelog` 路徑 | `_AIDocs/_INDEX.md`、`_AIDocs/_CHANGELOG.md` | 文件卡「改完三問」要指到專案自己的【SGI】 | 要做 |
| `smells_cmd` 的落點問題 | — | 兩專案共用的掃描器沒地方住：該進公司層或根層 skill【SGI】 | 待定（公司層） |
| 根層自己的（專案不覆蓋）：`card_budget` 3072、`dedup_pointer_score` 0.95、`pointer_markers` | — | — | 做了 |

## 六、多專案的奇耙設定，根層怎麼處理（這波真遇到的；原則：變量吸收，不寫專案分支）

| 奇耙 | 哪個專案 | 根層處理 |
|---|---|---|
| 表裡路徑兩種基準、反斜線、glob | TSLG（熱更子目錄 vs 專案根） | 既有：路徑正規化、glob 錨根；加 `path_bases` 多基準核存在性 |
| 一個工作區多個 repo、git 與 svn 混用、3 repo 2 台 server | SGI | `vcs: auto` 逐子目錄偵測；ledger 受測版本欄記「哪個 repo 的 rev」 |
| 提交訊息 Big5 | SGI svn | `log_encoding` |
| 熱更層與主程式集分開、Unity Play Mode 才能量 | TSLG | 量尺欄自由文字＋指令；H8 只提醒不跑 |
| 候選池產生器要 dotnet、8 秒、黑窗坑 | TSLG | M4 手動呼、不背景跑 |
| Codex 唯讀沙箱起不來（1385）、讀不到本機、MCP 舊程序載不到新碼 | 本機 | `codex_cmd` 可覆蓋；材料內嵌；MCP 改動只在新 session 生效寫進 atom（做了） |
| 三個 session 同機共用 `~/.claude` live 檔 | 根層 | log／ledger 以專案根分檔；verify 一律 monkeypatch 路徑（做了） |
| 框架目錄沒卡、文件目錄也是部位 | SGI（Orbit-Serverbase、_AIDocs） | 表允許「無卡」列仍要定位；T1 骨架預設把非程式路徑入表 |
| 哨兵格式不一、量測類不是判定 | SGI、TSLG | `sentinel_regex`；DONE 與 PASS 分開認 |
| svn 提交中文訊息要 `--encoding UTF-8 -F <utf8 檔>`，否則 Big5 存庫改不掉 | SGI | `commit_encoding`／`commit_cmd_template` |
| 自動生成產物不可手改（protoc、Design*.cs、auto_generate） | SGI | `readonly_paths` 直接擋 |
| 一檔兩部位（client 正本 `<Compile Link>` 進 server）、路徑→部位不是 1:1 | SGI | `Part:` 多值、`upstream`／`downstream` |
| TFM 釘死 3.1 但工具是 net8、本機多 SDK | SGI | `build_cmd` 按部位 |
| 伺服器工作目錄在另一個 repo、不帶參數起的 port 跟文件不同、要 15～16 台服才開 port | SGI | 量尺欄自由文字；根層不替專案起服 |
| 框架 logger 在 stdin 重導時 NRE，不能背景管線起 server | SGI | 根層「起 server 量數字」類工具一律給 console |
| 主控台字碼頁 950、MSYS bash 下含中文的 `/c/` 路徑壞 | SGI、根層 | 根層工具設 `PYTHONIOENCODING`、路徑用 `C:/` 形式 |
| 工作區＝root git＋三個獨立 svn＋獨立 git；打包 CI 在另一台機 | SGI | `vcs_roots`；P1 落點由專案填 |
| 專案層 Lv1 閉合清單 | SGI | T1 先映射、映不到才 `allow_new_category` |
| 零測試專案 | SGI | `test_runner` |
| 工作副本混著別人的 M | SGI | ledger／T2 以「本 session 動過的檔」為準，不是全部 M |
| 同一部位兩列、部位名帶括號 | TSLG 表第 2 列 | `Part:` 值＝「部位」欄去括號後的字（parse 已去括號【看程式知道】）；一個部位一個值 |

## 六之二、哪些是專案習慣、哪些該通用（兩專案自標；SGI 到，TSLG 待）

| 主張 | 屬性 | 落法 |
|---|---|---|
| 驗收規格三段隨每次提交 | SGI 習慣 | 預設範本，變量可關 |
| 控制塔唯一讀起點、權威地圖、矛盾裁定段 | SGI 習慣 | `authority_map` 欄；裁定段預設空 |
| 整行哨兵格式 | SGI 定的 | 已是預設 |
| FastProof 證法 | SGI 專屬（C#＋svn BASE） | skill 只抽原則「預期來自舊源碼、實際來自新產物、兩邊不同來源才不是自證」 |
| 零測試所以靠反射 | SGI 特殊 | 通用預設「有測試框架先用」，`test_runner` |
| 「上GIT」口令 | 使用者個人 | `commit_policy` |
| `_AIDocs` 每改追 CHANGELOG／INDEX | SGI 習慣 | 路徑做變量，段落預設帶 |
| 高風險先讀文件分級 | SGI 習慣 | 等於 `deny_parts`＋`locate_extra`，不另設 |
| 找到壞味道當場修並證明 | 使用者對 AI 的要求 | 通用（#13），證明手段專案的 |
| 多 session 信箱協定（自檢、分級） | 這波養出來的 | 通用，可做 skill |

## 七、部位 profile 的格式（總控台已定：`overview-map.md` 擴欄，不另立檔）

一列一個部位，現有欄（路徑前綴｜部位｜導讀卡｜狀態）之後加五欄，全部是路徑或短字串，空白允許：

`｜病灶清單｜量尺（量法｜指令｜門檻）｜檢查器清單｜讀路徑樣本｜第四問`

- 解析器只從「導讀卡」欄取卡名、「狀態」欄取狀態，擴欄裡的反引號指令不會被誤當卡名【試過：commit 162787c，29 案綠，兩專案現表 25 列解析結果不變】。
- TSLG 已把自己的表擴成九欄、大地圖與戰鬥兩列填滿、路徑逐一核存在【試過，tslg/062】——**當樣本用，本波不要求其他列或 SGI 跟進**。
- atom 加 `Part:` 欄，值＝該專案表「部位」欄文字；只在專案 shared 層有效，不跨專案統一；`Part:` 可由範疇資料夾自動推、人核推不出的【推測，TSLG】。

## 八、新專案 bootstrap（對「新」那條；是硬要求還是目標看第十節第 1 題）

1. 新專案跑 `/overview init` → 掃頂層目錄與 fix 熱點 → 產表草稿＋每部位五段卡骨架（空段有提示句）；Lv1 先映射既有清單。
2. 第一個 session：OverviewHub 注入骨架卡，空段提示「這部位還沒人寫，動手前先補『做什麼與上下游』再改」；第一張卡由這一步長出來（解 H4 冷啟動：前例「無」合法）。
3. 每次 fix 類提交，M2 提示把教訓進病灶文件；S2 榜單前 N 自動成下一張卡候選。
4. 門檻、最該修規則、檢查器清單由專案在 `overview-hub.json` 與表裡填。
驗收只到「有入口＋骨架注入＋空段提示」；「≤1 個 session 有綜觀」是目標不是驗收。

## 九、Codex 審本計畫的分歧與裁決

- **SGI（projects/072，原文 `attachments/sgi-codex審計畫v2-原文.md`）**：沒推翻任何機制，推翻「驗法」——五數全是過程量 → 本版加結果題組；H1 加停止條件；M3 定義同材料獨立作答；S6 手數改腳本數；T1 Lv1 先映射；A1 限範圍；H7 不進卡；三處契約矛盾（第五節 append 進卡、S6、M3）本版全改。不採：H6「不能阻止未試先報」——dry-run 是政策。
- **TSLG（tslg/063，原文 `attachments/tslg-codex審計畫v2回覆.md`）**：最重一句「沒有從需求成立反推的成效驗收」→ 同上加題組；H4 讀檔數當閘＝被數字帶偏 → 改成「讀卡＋≥1 Depends 檔」；T3 要回路；T2 主尺改 fix 數；R3 驗欄補；H6 綁受測版本；M1 預算路由；M2 去專案細節；H7 撤 append。
- **根層**：跑中（材料＝本版＋三份輸入；題型同兩專案）。

## 十、要問你的（兩專案的六題總控台已定，這裡只剩要你拍的三題）

1. 「未來的使用者」是否包含**零卡片、零歷史的新專案**？根層假設是，所以第八節 bootstrap（T1）列為硬要求；若只指現在這幾個專案，T1 可延後。（兩邊 Codex 都指出這題不答，「新」同時是硬要求又是待拍，計畫內部矛盾。）
2. 注入閘出廠預設：根層建議**出廠 dry-run、由專案開 deny**（未來使用者先看到提醒不被擋）；若你要出廠就擋，H4 的新判準要先在兩專案各量一場。
3. 太慢／太吃記憶體（7d、7e）根層只做格式與提醒（H8），量法與門檻專案填；要不要根層也出一支通用 .NET 量測包裝（dotnet-counters 60 秒＋P90 報表）？根層建議先不做，等兩專案各自跑出門檻再抽共用。

## 十一、實作順序（第 4 版才定；三邊目前建議）

TSLG 建議 CP 值順序：H3 部位親和（改排序、零新資料）→ H4 擋的判準 → M1 卡片結構化 → H5／M4 候選池注入 → H7 自檢 → M3 Codex 工具化 → H8、R2。根層補：T1 若第十節第 1 題答「是」就排第一；H6 ledger 要早（R2、H8、M3 都吃它）；公司層合併順序與 `path_bases`／`vcs` 這類「多專案吸收」變量跟 H6 同批，因為 T2、H6 第一天就碰到。

## 十二、來源

- 上一波全貌（第 6 版定稿）：`C:\Users\holylight\.claude\memory\_staging\全貌-AI寫碼守門三方討論.md`
- SGI 輸入：`c:\Projects\.claude\inbox\tri-link\attachments\sgi-下一波調整計畫輸入-側觀角度.md`（projects/067～072）；樣本工具 `c:\Projects\_tools\verify_ledger.py`、`refix_churn.py`（工作副本，不上版）
- TSLG 輸入：`c:\Projects\.claude\inbox\tri-link\attachments\tslg-下一波調整提案-記憶系統側.md`（tslg/058～063）；樣本表 `C:\TSLG\.claude\overview-map.md`（已擴欄）
- 根層：本檔第 1 版（併入第三節）；解析修正 commit 162787c
