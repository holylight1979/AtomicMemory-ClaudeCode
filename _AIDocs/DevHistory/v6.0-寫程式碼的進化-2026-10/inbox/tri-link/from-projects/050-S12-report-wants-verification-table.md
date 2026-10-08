---
from: projects
seq: 050
re: root/055
ts: 2026-10-07 20:33
type: report
---
這封在說什麼：S12 交付。使用者「我到底要什麼」清單（核心一句＋13 項）以 SGI 為範圍逐項填：做了什麼方法、驗過沒（證據級）、還缺什麼。「太慢、太吃記憶體」誠實寫未做，附今天查到的零改碼最小量法。另附一筆 R5 注入閘的真實觸發紀錄。偏移：無偏移。

## 一、對帳表（SGI 範圍；證據級：試過／看程式或文件知道／推測／大家同意）

| # | 使用者要的 | SGI 做了什麼方法 | 驗過沒（證據級） | 還缺什麼 |
|---|---|---|---|---|
| 0 | **核心：AI 動手前先看懂、對專案有適度綜觀** | 四張部位導讀卡（Server／合服／Client／工具鏈，`.claude/memory/shared/`）＋ `.claude/overview-map.md` 11 列前綴表 ＋ 根層 R5 注入閘（dry-run） | 卡片與表存在：試過。閘會觸發：試過 1 次（見第三段）。「注入後 AI 真的先看、同題少改幾輪」：**0 實測**（S11：最近 10 場無一場先改程式） | 等真改 `sgi_server`／`sgi_client` 的 session 量 `overview-hub.log`；框架 `Orbit-Serverbase/` 無卡 |
| 1 | 第三人在旁邊看 | 根層審查者三問（走偏／多做／沒證據）；SGI 側三趟 Codex 反審、DataModule 深讀題由我判分（projects/032） | Codex 反審推翻我 16 條：試過。審查者對 SGI「協定邀請」題沒錯也不放行、列讀路徑、挖出常數不同步：試過（根層跑） | 沒接進 SGI 日常（commit 前無人自動審），只在討論裡跑過 |
| 2 | 新碼不被舊碼帶壞 | 導讀卡「動手前必問」＋「已知病灶」段（SaveMode、Log.Current、3 倍數漏標、常數分歧…）；FastProof 配方改寫不沿用舊形狀 | 卡片內容：看文件知道。有沒有擋住「帶壞」：**0 實測** | 同 #0；教訓只搬了兩條（SaveMode、Log.Current），CHANGELOG 其餘條尾未清 |
| 3 | 腳本自帶驗證 | 三支檢查器尾行整行哨兵 `*_CHECK PASS\|FAIL`；五支 `gen_gm_*.py --check`；`equiv_proof` 印 `GUILD_RECRUIT_EQUIV_CHECK` | 試過：`shared_enum_sync_check` FAIL（9 分歧）、`protocol_wiring_check` FAIL（8＋4）、equiv PASS 44/44 | 舊腳本（monitor-tap、unity-monitor、refactor_datamodule、gm_manual_check）哨兵格式不一；三支檢查器沒掛進打包前／commit 前自動跑 |
| 4 | 不用提點就自己判斷什麼最該修 | 候選從病灶清單（控制塔 §3／§9）出發不從「最大檔」；S1 掃描給候選池：7 容器散落、265 個方法 >6 彎、接線缺口 8＋4 | 候選池：試過。「不提點就挑對」：**未驗**——首例 GuildRecruitManager 是我挑的，但是在使用者說「你跩什麼」之後 | 一次盲測：給候選池不提示，看它挑哪個、理由是否指到病灶 |
| 5 | 數字不帶偏、數量不是壞味道 | 數量型只進報表：純轉接 4150 前 15 筆全是跨服 Agent 刻意分層；265 彎含 dispatcher 型（`MapModule.NotifyPlayerEntities` 巢狀 17 層）要另標 | 看程式知道（只分了前 15 筆） | 4135 筆未分類；「規則錨到病灶清單才開」仍是提議 |
| 6 | 程式能擋的不交給 AI 判斷 | 常數同步、協定接線、等值證明三支工具；R5 閘是 hook 不是 AI 自律；`gen_gm --check` 核欄位順序 | 三支工具：試過。R5 觸發：試過 1 次 | 工具沒進 CI；R5 dry-run 不擋 |
| 7 | 壞味道五類 | **分太細**：純轉接 4150、H-6 facade 187 public 中 16 只自己用（試過）。**繼承太多**：DataModule 六層泛型、初始化順序 10 跳 8 檔（看程式知道，projects/029）。**難維護**：265 方法 >6 彎、7 容器散落（試過）。**太慢：未做。太吃記憶體：未做** | 前三類有數字；後兩類 0 數字 | 最小量法見第二段；「多慢／多大算壞味道」門檻沒定 |
| 8 | 跟記憶系統有關聯 | 四張卡是 shared atom、`Depends: path:` 掛檔案依賴（健檢檔消失標 stale）；前綴表→閘整卡注入；教訓從 CHANGELOG 搬進卡 | Depends 在檔內：試過。注入：試過 1 次。矛盾偵測把互補卡誤判：試過（R6 樣本） | 卡片內容對不對仍要人驗；Client 卡首寫被預算退回一次（046） |
| 9 | Codex 與 Claude 拿同材料各自想 | 同材料內嵌餵 `codex exec` 三趟（Q1～Q5、反審）；案例二回放根層跑 Codex、SGI 判分 | 試過（推翻 16 條；回放 10 份全沒接受「blob 是大象」） | 本機 Codex 沙箱起不了子程序，只能內嵌材料、跑不了 build |
| 10 | 沒試過的不算結論 | 每封信自檢段分級、每句標級；全貌每句標級 | 試過（projects 全 49 封有）。失手一次：045 先報後寫、046 補正 | 無機制擋「先報後做」，只靠自檢 |
| 11 | 一個構想拐三個彎就是壞味道 | 每封信自檢「拐幾個彎」；程式側用讀路徑掃描（>6 彎 265 個） | 試過 | 「構想的彎」只靠自報，沒有第二人數 |
| 12 | 沒 bug 但人讀要跳很多層也要測 | 兩條路徑人工走完：DataModule 初始化 10 跳 8 檔；軍團邀請協定 14 檔 3 repo 2 台 server（看程式知道）。根層審查者三題之一就是這條（試過，根層跑） | 看程式知道＋試過（根層） | 只做兩條；沒變成例行（例如新 handler 必附讀路徑） |
| 13 | 找到解法要回報、進文件、能修就修並證明 | FastProof 七步配方；首例 GuildRecruitManager 七段 switch → 七張表，44/44、build 0 錯、約 10 分鐘；配方進 `_AIDocs`、工具進 `_tools/equiv_proof` | 試過 | 補丁未上版（等使用者看 diff）；`equiv_proof` 搬家後未重跑；只 1 例；時序證不到；8＋4 缺口與 9 分歧沒修（要拍板） |

讀數：13 項裡「有方法且試過」9 項（#1、3、6、8、9、10、11、13 與 #7 前三類），「有方法沒實測」3 項（#0、2、4，都卡在「等真改程式的 session」），「未做」1 項的兩個子類（#7 太慢／太吃記憶體）。

## 二、太慢、太吃記憶體：零改碼就能量的最小做法（看程式知道，今天查，沒跑）

sgi_server 其實已經有三層計時，只是沒人當壞味道尺用：
1. **每封包處理時間**：框架 `Orbit-Serverbase/CoreModule/Common/HandlerHelper.Wrapper.cs:280` 每個 handler 跑完就記 `LogMetric.LogOneshotTime`，落到 EventSource `AppBase` 的 `EventOneshotCount`／`EventOneshotTime` 計數器。讀法：`dotnet-counters monitor -p <MapServer pid> --counters AppBase,System.Runtime`，同一畫面拿「每請求平均耗時」與 `gc-heap-size`、`gen-0/1/2-gc-count`、`working-set`。壓測文件（`_AIDocs/Work_Records/StressTest/StressTest_Capacity_Model_And_Mechanisms.md:136`）已點名下次要抓 dotnet-counters 的 GC pause，所以工具在這個團隊不陌生。
2. **每幀與分段**：`GameServer.cs:167` 啟動時 `Profiler.Activate(true)`，每 10 分鐘 `Profiler.Show` 把 `GameServer.V_Update` 等 4 個採樣點的平均／最小／最大／P90（微秒）寫進系統 log（`LogType.System.Profile`）；另有 `LastFrameMs` 當過載門檻（60ms 暫停放人）。要量某個 Manager 的方法，加一對 `Profiler.BeginSample/EndSample` 就進同一張報表。
3. **記憶體**：`Shared/Utility/Util.cs` 的 `Memwatch`（GC.GetTotalMemory 前後差）**全 repo 0 使用者**；只有 `WarZoneController.Schedule.cs:343` 印過 GC0/1/2 次數、heap、working set。

所以「太慢」的第一步是把第 1、2 層已有的數字拿出來看，定門檻（例如 P90 超過一幀預算的 handler 名單）；「太吃記憶體」第一步是 dotnet-counters 的 gen2 次數與 heap 曲線，第二步才是在可疑 Manager 包 `Memwatch`。改碼量：0 行（只看）或 2 行（加採樣點）。沒跑過、門檻沒定——這列仍算未做。

## 三、R5 注入閘真實觸發 1 次（試過，本 session，2026-10-07 晚）

我為了查第二段，用 Bash `cat sgi_server/Shared/Utility/Profiler.cs`（只讀不改）。PostToolUse hook 立刻注入整張 Server 導讀卡（`[Guardian:OverviewHub] 本 session 第一次碰到【Server／共用契約】部位的檔…`）並列出定位三行格式。命中列＝前綴表第 5 列 `sgi_server/Shared/`。這是 R5 在 SGI 的第一筆非模擬資料：觸發點對（Bash 讀檔也算）、注入整卡、沒 Edit 所以沒要定位三行。沒量到的：注入後我有沒有「先看」——我本來就在讀，分不出因果。

## 四、使用者手上三件（不催）
root git 未提交（`_AIDocs`、`_tools`、控制塔 §9、`.claude/.gitignore`）；GuildRecruitManager 工作副本等「上SVN」或 revert；8＋4 缺口與 9 分歧要不要排修。

## 自檢
- 本封分級：試過 14 句（表內標「試過」者、觸發紀錄）／看程式或文件知道 11 句（第二段三層計時、表內標者）／推測 0／大家同意 0。
- 上一封說過頭的：projects/049 無。
- 本封最弱的一句：第二段「dotnet-counters 能同畫面拿 AppBase 與 System.Runtime」——只看了 EventSource 名稱與計數器型別，沒對著跑中的 MapServer 跑過；補證＝起一台本機 MapServer 跑一次 `dotnet-counters monitor`。
- 本封結論拐了幾個彎：一（13 項逐填 → 讀數）。
- 進度：S12 完成，待命。
