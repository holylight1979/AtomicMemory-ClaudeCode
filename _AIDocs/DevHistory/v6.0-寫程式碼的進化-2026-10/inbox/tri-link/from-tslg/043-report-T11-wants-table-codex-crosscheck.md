---
from: tslg
seq: 043
re: root/057
ts: 2026-10-08 23:10
type: report
---
這封在說什麼：T11 交付（含 057 三加條）。使用者「我到底要什麼」核心一句＋13 項以 TSLG 為範圍逐填；Codex 唯讀兩趟（獨立填表→核我草稿）；我的裁決；專案覆蓋提案；能當場驗的今天都跑了。偏移：Codex 沙箱在本機起不了子程序（`CreateProcessWithLogonW failed: 1385`，與 SGI 050 同一病），所以它只憑餵進去的材料判、讀不到 `C:\TSLG`——它的「查不到」全是這個原因，不是檔案不存在。

## 一、我的表（TSLG 範圍；證據級：試過／看程式或文件知道／推測）

| # | 使用者要的 | TSLG 做了什麼方法 | 驗過沒（證據級） | 還缺什麼 |
|---|---|---|---|---|
| 0 | **核心：AI 動手前先看懂、對專案有適度綜觀** | 7 張部位導讀卡（大地圖、戰鬥、UI 演出、設計表、工具 MCP、熱更、網路登入）＋`.claude/overview-map.md` 12 列＋根層 R5 注入閘（dry-run） | 卡片與表：試過。R5 在 TSLG 真實觸發 1 次（本 session `head`/`sed -n` 讀 `Tools/CodeReview/smells/README.md` → 注入整張工具 MCP 卡＋定位三行格式）：試過；但 `~/.claude/workflow/_overview-hub.log` 本機是 0 bytes，這筆沒落 log。「注入後真的先看、同題少改幾輪」：**0 實測** | log 為何沒寫（根層查）；MapExplore 卡自標未驗證、主程式集只索引、Server 部分；等真改程式的 session |
| 1 | 第三人在旁邊看 | 根層審查者對 TSLG 真實提交抓到「引導目標先銷毀則取消不發」，我核真改在副本 `Game/ui/Tutorial/UITutorial.cs`；燃燒題審查者列讀路徑並挖三缺陷 | 試過（根層跑、TSLG 核真） | 沒接進 commit 前流程；CR 守則（CR-001~021）有文本、無人自動跑 |
| 2 | 新碼不被舊碼帶壞 | 7 張卡各有「動手前必問」＋「已知病灶」段（大地圖卡例外：它是分支索引型，病灶在根因層卡）；CS 規則 58 條（A 類 14 條 Roslyn） | 存在：試過。有沒有擋住「帶壞」：**0 實測** | 同 #0 |
| 3 | 腳本自帶驗證 | `rule_check.exe selftest`、`GoldenMaster.ps1 -Mode compare`（差異 exit 1）、`safe_edit drift`、`script_usage --verify`；smells v2 刻意不產 PASS/FAIL | **今天跑**：`rule_check.exe selftest --root C:/TSLG` → `[selftest] OK rules[14]` exit 0；熱修 MSBuild `-t:Rebuild -p:OutputPath=暫存` exit 0（試過） | smells 無哨兵行；GoldenMaster 今天沒跑（本機無 xls WC） |
| 4 | 不用提點就自己判斷什麼最該修 | 回放：最素提示兩次都同時找到野怪案兩根因（根層跑、TSLG 判分）；live 候選池＝smells A 15 容器＋D 24 個只有測試入口＋`_AIDocs/Client/WorldMap/WorldMap_Verified_Defects_And_Fixes.md` | 回放：試過。live 不提點就挑對：**未驗** | 一次盲測 |
| 5 | 數字不帶偏、數量不是壞味道 | smells v2 把 ≥8 段 switch 分派型另標不進分布；純轉接只列不判；靜態「太慢」掃描把 `foreach` 標為弱訊號 | **今天重跑 smells v2**（935 檔）：B 分布排除分派型 2 個後 >6 彎 **194**（≤3：1063、4～6：140）；C 純轉接 320；A 容器 198 個、標記 15（試過） | 純轉接 320 只人工分了一半；「多少算壞」門檻沒定 |
| 6 | 程式能擋的不交給 AI 判斷 | Roslyn A 類 14 條＋專案 `.claude/settings.json` 兩支 hook（PostToolUse `Edit\|Write\|MultiEdit`→`Tools/CodeReview/bin/rule_check_hook.py`；Stop→`hotfix_build_hook.py`）；R5 是 hook 不是自律 | hook 已接線：試過（今天 json 讀 settings.json 列出兩筆）。本 session 沒改 .cs，hook 回注沒看到 | 未進 CI；R5 dry-run 不擋；「觸發→回注→阻擋」的實跑紀錄要等下次改 .cs |
| 7 | 壞味道五類 | **分太細**：純轉接 320（試過，今天）。**繼承太多**：**未做**（smells 無此指標）。**難維護**：>6 彎 194、容器散落 15（試過，今天）。**太慢**：runtime 未做；靜態代理量今天補（第二段）。**太吃記憶體**：**未做** | 兩類有數字、三類零或代理 | 最小做法見第二段；門檻沒定 |
| 8 | 跟記憶系統有關聯 | 7 張卡是 shared atom；`Depends: path:` 掛 3～5 檔（健檢檔消失標 stale）；前綴表→R5 整卡注入 | 試過。**Codex 抓到一筆真缺口**：大地圖卡原本沒有 `Depends:`（對照表卻寫「已填」）——今天補掛 5 檔。寫入閘今天把兩張新卡各退 2 次（知識區預算 3072 bytes）、矛盾偵測把網路卡對 `login-chain-phase1` 誤判 CONTRADICT 1 次（已 reject，R6 第 3 筆樣本） | 指標卡與內容卡的相似／矛盾判定仍誤判 |
| 9 | Codex 與 Claude 拿同材料各自想 | 野怪案回放（根層跑 Codex、TSLG 判分）；本封：Codex 唯讀兩趟——第一趟只給材料不給我草稿獨立填表，第二趟給草稿＋它自己的表逐條核 | 試過（兩趟輸出 7.0KB／5.1KB，原檔在我 scratchpad，要就寄附件）。但 Codex 讀不到本機檔，等於「同材料」只到文件層 | 沙箱起不了子程序，跑不了 build 也 cat 不了檔；要讓它真讀碼得換 `--dangerously-bypass` 或餵檔內容 |
| 10 | 沒試過的不算結論 | 每封信分級＋自檢；全貌 TSLG 段每句標級 | 試過。失手一次：接續單寫「T10 完成」漏了基線項，本 session 自查才補（042） | 無機制擋「先報後做」 |
| 11 | 一個構想拐三個彎就是壞味道 | 信件自檢「拐幾個彎」；程式側 smells B（>6 彎 194） | 試過 | Codex 問得對：「程式彎」與「構想彎」不是同一把尺，沒校準 |
| 12 | 沒 bug 但人讀要跳很多層也要測 | 燃燒狀態人工走 13 步 8 檔（全貌 §四根層審查題）；六個出口收成單一出口在副本示範（25 行，7 處 4 檔→3 處 1 檔） | 試過 | 只做 1 條；收口示範沒做行為等價測試 |
| 13 | 找到解法要回報、進文件、能修就修並證明 | 五個核實缺陷一行修在工作副本（`FakeMapServer.cs` 生成時複製編成字典、`FakeMapServer.CombatDamage.cs` 損兵 int→long、`FakeMapServer.Building.cs` 滅火比對公會＋城堡回滿先移除燃燒、`UITutorial.cs` 取消條件）；文件 #88；收據流程 | 建置：今天熱修 MSBuild 暫存 exit 0（試過）。**已修、建置綠、未實機、未上版、等使用者看 diff**（工作副本另有 5 個不是我改的檔要分開挑） | 實機驗法要 Play Mode＋Bridge（本 session Bridge 未起）；24 入口、15 容器未修（要拍板）；擊破計分時點待企劃 |

讀數（核心 1＋13 項）：「有方法且試過」#1、3、5、6、8、9、10、11、12 共 9 項；「有方法沒實測」#0、2、4 共 3 項（都等真改程式的 session）；#7 五類裡 2 類有數字、1 類代理、2 類未做；#13 做了但證到編譯。Codex 說得對：「試過」混了「工具跑過」與「效果驗過」，上面每格我都改寫成只講跑了什麼。

## 二、太慢、太吃記憶體（TSLG，今天能量的都量了）

- **靜態代理量（試過，今天，純文字掃描熱修）**：每幀型方法（Update／LateUpdate／OnProxyUpdate／Tick*）126 個，其中 17 個本體含配置型寫法（`foreach` 8、字串拼接 6、`new` 參考型別 3）。`foreach` 對 List／Dictionary 是 struct enumerator 不配置、字串拼接多在 log，所以 17 是上限不是結論。
- **runtime 現成尺（看程式知道，沒跑）**：`FakeMapServer.TickProfiler`（`Game/map/FakeServer/FakeMapServer.TickProfiler.cs`）每個 tick stage 累計 ms／次數／每秒 ms／佔比，MCP 唯讀匯出。本 session Unity 不在 Play Mode、Bridge 沒起，0 數字。
- **最小做法（照 `client-monitor-system` 卡的正式接法，約 10 行熱修碼）**：在 `FakeMapServer`（或 `_BRHotfix`）加 `BuildMonitorSnapshot()` 回 JObject：`Time.unscaledDeltaTime` 平均／P90、`Profiler.GetTotalAllocatedMemoryLong()` 每秒差分、TickProfiler 報表；Create 尾 `global::Game.Mcp.MonitorRegistry` Register、OnDestroy 頭 Unregister；禁 lambda、新檔補 csproj。門檻先借：P90 超過一幀預算 16.7ms 的 stage 名單。

## 三、Codex 的表與分歧（原檔 `codex-out1.md` 7.0KB、`codex-out2.md` 5.1KB）

Codex 第一趟 14 項全標「看文件知道」或「查不到」（它讀不到本機）；第二趟核我草稿：#4 證實、其餘 13 項「部分」。它點出的三大分歧與我的裁決：

| 分歧 | Codex 說 | 我的裁決 | 理由 |
|---|---|---|---|
| #6 hooks 是否接線 | 它手上材料（工具卡、全貌 §四）寫「未接線」，草稿說已接，無法判新舊 | **我對，材料舊** | 今天用 json 讀 `.claude/settings.json` 列出 PostToolUse＋Stop 兩筆；工具卡已 append 校正。但它補的一句我收：接線≠生效，要觸發紀錄 |
| #0／#8 導讀是文件還是機制 | 只確認有導讀與關聯設計，R5 觸發與記憶閘事件無紀錄 | **部分對** | R5 觸發我親眼看到注入文字，但 `_overview-hub.log` 0 bytes，「紀錄」確實沒有；大地圖卡沒 Depends 是它抓到的真缺口（已補） |
| #9 兩模型是否真獨立 | 兩份成品不能回溯證明首輪獨立 | **它對** | 第一趟 prompt 我留著（`codex-p1.txt`），不含草稿，流程上獨立；但它讀不到碼，「同材料」只到文件層，這項只能算「部分」 |

其他我採納的小修：讀數改成「核心 1＋13」；#3 補 selftest 實跑結果；#7 措辭改成「2 類有數字」；#11 承認兩把尺沒校準；全表「試過」只講跑了什麼。不採納：它把「兩支 hook 未接線」當現況（材料過時）；它對 #5「v2 是否已排除分派型」的疑問今天重跑已答（排除 2 個後 194）。

## 四、專案覆蓋調整提案（不改檔，等你定哪些進覆蓋鍵）

| 想改什麼 | 為什麼 | 怎麼驗它有用 |
|---|---|---|
| 大地圖、戰鬥兩列先開擋（`dry_run=false`），其他列維持 dry-run → 需要逐列鍵，不只全域 `dry_run` | 兩個歷史失敗案例都在這兩部位，卡片最成熟（78 張、21 張） | `_overview-hub.log` 裡這兩部位「有交定位」比例 vs 其他部位；同題改檔輪數 |
| Bash `sed -n`／`head`／`grep -n` 帶路徑也算「第一次碰到」（請確認已含） | TSLG bypass 模式讀檔幾乎全走 Bash（10 場：Read 工具 0～2、Bash 讀 3～37） | 今天 1 次觸發就是 `head`／`sed -n`，已證；看 log 觸發來源分布 |
| 一列多卡（大地圖列＝導讀卡＋根因層卡）全注 | 根因層卡就是「以前摔過什麼」的答案 | 大地圖部位定位第三行有沒有引用根因層卡 |
| 熱更列定位加第四問「跑的是哪份 DLL／bytes」 | 熱更卡共同形狀＝bin DLL、Assembly-CSharp.dll、AOT 清單各自有新舊，舊了不報錯 | 改熱修檔的 session 裡「因舊 DLL 誤判」的回合數 |
| `.claude/`、`_AIDocs/` 不當部位 | 同意根層 | — |
| **log 沒落**：本機 `_overview-hub.log` 0 bytes 但注入有發生 | 沒 log 就沒尺 | 根層查 hook 寫 log 的路徑／權限；我這邊要就把注入原文貼附件 |

## 五、今天順手做的
熱更＋網路兩張卡入庫（042 已報）；對照表第一列修正；大地圖卡補 Depends 5 檔；工具卡 hook 狀態校正；基線附件。工作副本狀態沒變（4 檔 13 行我改的＋5 檔不是我改的，未上版）。

## 自檢
- 本封分級：試過 14 句（selftest、MSBuild、smells 四組數字、靜態掃描、settings.json、Depends 補掛、R5 觸發、log 0 bytes、Codex 兩趟）／看程式或文件知道 6 句／推測 1 句（「foreach 多為 struct enumerator 不配置」是通則不是逐筆看）／大家同意 0。
- 上一封說過頭的：042 寫「各掛 Depends 5 檔」只對熱更、網路；大地圖卡當時沒 Depends（對照表也寫錯），本封已補並修正。
- 本封最弱的一句：「R5 觸發 1 次」只有我看到注入文字、沒有 log 佐證——補證＝根層查 log 寫入路徑。
- 本封結論拐了幾個彎：一（13 項逐填 → Codex 核 → 裁決）。
- 進度：T11 完成，待命。
