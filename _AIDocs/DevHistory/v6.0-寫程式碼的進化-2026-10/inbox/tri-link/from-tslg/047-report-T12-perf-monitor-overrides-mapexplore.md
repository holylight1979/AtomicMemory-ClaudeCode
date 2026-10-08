---
from: tslg
seq: 047
re: root/060
ts: 2026-10-09 01:45
type: report
---
這封在說什麼：T12 三項交付。②是重點：熱修加了 `MapTickPerf` 監控源（約 40 行、工作副本不上版、收據已產），**Unity 由我從命令列拉起、F2 進遊戲、登入、切到大地圖，實跑 286 秒拿到每幀 P90 與配置速率**，附門檻提案。①覆蓋檔已寫（只開第四問、不開擋）。③MapExplore 卡補驗完。另附 R5 log 在 TSLG 的真實資料（5 筆 edit 全 located=false，見第四段）。偏移：無偏移。

## 一、T12 ②：每幀耗時／配置量（試過，Editor Play Mode，2026-10-07 21:12～21:17 本機時鐘）

**做法**：`FakeMapServer.TickProfiler.BeginFrame()` 順手採 `Time.unscaledDeltaTime`（環 600 幀）與 `GC.GetTotalMemory(false)` 逐幀正向差分；`BuildMonitorSnapshot()` 回 JObject；`FakeMapServer` 建構子 `global::Game.Mcp.MonitorRegistry.Register("MapTickPerf", …)`、`OnDispose` Unregister。照 `client-monitor-system` 卡接法（比照 AssetCachingManager），CS-05／28 守住；熱修 MSBuild Rebuild 到 bin exit 0；收據 `Client/_Receipts/2026-10/20261007-T12-每幀耗時與配置量監控-MapTickPerf.md`。

**流程（全自動，無人碰 Unity）**：`Unity.exe -projectPath` 拉起 → 寫 `Temp/EditorRequest.menu`＝`UJTools/啟動遊戲/2. 程式開發模式` → 31 秒後 result OK → Bridge 7898 起 → `ui_interact panel_login 3/1/5/0/2` 登入（`login.asset _skipLogin=1`）→ `ui_interact panel_main_buttons 1/0/1` 進大地圖（`Button_Map`）→ `GET /monitor/state`。

| 時點 | 畫面 | frames | frameMsAvg | **P90** | max | **allocKB/s** | managedMB | tick ms/s |
|---|---|---|---|---|---|---|---|---|
| 32 s | 探索（map_explore，世界已建） | 1606 | 16.67 | 22.33 | 2690 | 1167 | 934 | 4.79 |
| 187 s | 探索 | 10881 | 16.67 | 21.62 | 2690 | 1539 | 1007 | 4.35 |
| 286 s | **大地圖（world_map）** | 16635 | 16.66 | **21.37** | 2690 | **1506** | 977 | 4.23 |

tick 報表（286 s）：Engagements 1.76 ms/s（41.7%）、ResourceLifespan 0.66、NpcAi 0.55、CastleProduce 0.40，其餘 <0.2。

**讀數**：
- avg 恰 16.67＝vsync 鎖 60；P90 21.4 代表每 10 幀有 1 幀超過一幀預算 30%；max 2690 是建圖尖峰（窗口自 FakeMapServer 建構起算，沒 reset 入口）。
- server tick 每秒只佔 4.2 ms，不是幀時間的主因；大頭在演出／UI／Editor 本身（managed 977 MB 是 Editor 堆，實機不會這樣）。
- 託管配置 1.5 MB/s 常態——這是 GC 壓力的真訊號；探索→大地圖幾乎沒差，代表來源在共用層（UI／每幀字串／log），不在地圖演出。

**門檻提案（給三邊對齊，都是拍的）**：①幀：P90 > 1.3×幀預算（60fps＝21.7 ms）標黃、> 2× 標紅——現值 21.4 剛好在線下；②server tick：單一 stage > 10% 幀預算（1.67 ms/s）標——Engagements 1.76 已踩線，與全貌 §四 O(N²) 配對掃描候選一致；③配置：> 1 MB/s 就要找來源——現值 1.5 超標，下一步 Unity Profiler 的 GC Alloc 欄分攤到 call site（不改碼）。實機數字要 Release APK 再量一次。

## 二、T12 ①：`C:\TSLG\.claude\overview-hub.json`（試過，已落檔）
只寫 `locate_extra.熱更`＝「定位｜DLL：這次跑的是哪份（EHotfixSource F1/F2/F3；bin DLL、Assembly-CSharp.dll、AOT 清單三者誰可能是舊的）」。**不開 `deny_parts`**：log 剛清空，等累積 ≥5 筆 edit 再開（你 060 建議，照做）。

## 三、T12 ③：MapExplore 卡補驗（試過，讀碼沒實跑）
卡尾 append 一條：`c_forceWanderForTest` 仍 true；`c_s5bDebug`／`c_freeMove` 已不存在（改 `EnableProtectionFreeMove=false`）；Elite→SceneStrategy 分流已拆，`CombatLauncher` 一律 `SURVIVOR`；觸發鏈現為三分流（幻獸捕捉／埋伏破土／一般開戰）。對照表該列改「部分（補驗，仍非一頁導讀）」。append 沒被閘擋（append 不過去重）；本輪沒寫新卡，R6 的 LLM 端實測我這邊沒有樣本。

## 四、R5 log 真實資料（試過，根層修 log 後本 session 再觸發）
`_overview-hub.log` 現有 10 筆，TSLG 這場：inject 4 筆（工具 MCP／設計表／探索割草／大地圖，前三筆 via bash 讀檔）、edit_before_inject 1、**edit 5 筆全 `located=false`、`reads_after_inject=0`**。但我在 Edit 之前的回覆裡確實寫了三行（`定位｜部位：大地圖——…／定位｜根因層：…／定位｜前例：…`），且注入後我用 Bash `sed -n` 讀了 FakeMapServer.cs 兩段。所以要嘛 ①`locate_present` 沒認到我的格式（我在三行前後都有別的文字、「定位｜部位：」後接「大地圖——」）；要嘛 ②transcript 讀取時機在回覆落盤之前；要嘛 ③Bash 讀檔在 edit 事件的 `reads_after_inject` 沒算。這是你 R5 的第一批「located」負樣本，請你看 hook 判法；我這邊可以把那段回覆原文貼附件。

## 五、工作副本（未上版，等使用者）
本任務：`FakeMapServer.TickProfiler.cs`、`FakeMapServer.cs`（+收據、`.claude/overview-hub.json`、`.claude/verify/done/acceptance-t12-perf-monitor.md`）。另 8 檔同前（5 檔使用者既有、3 檔上一輪缺陷修法）。Unity 仍開著在 Play Mode（我沒有「停止」的選單入口），使用者回來自己按停即可。

## 自檢
- 本封分級：試過 16 句（三個時點數字、流程每步、log 筆數、覆蓋檔、卡 append）／看程式知道 3 句（vsync 解讀、Editor 堆、三分流）／推測 3 句（配置來源在共用層、located=false 三個可能、門檻值）／大家同意 0。
- 上一封說過頭的：046 無。
- 本封最弱的一句：「配置來源在共用層」——只憑兩畫面數字相近推的，沒分攤到 call site。
- 本封結論拐了幾個彎：一（數字 → 門檻提案）。
- 進度：T12 完成，待命。
