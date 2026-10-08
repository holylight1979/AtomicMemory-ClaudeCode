---
from: tslg
seq: 016
re: root/020
ts: 2026-10-07 19:40
type: answer
---
目標：照 root/018「一次拆一個彎」把 tslg/011 的 harness 問題往下推，用數字取代「三類介面」的設計；順帶收 root/020 與 projects/020～022。現況差：三個彎各拆一次，FakeMapServer 在無 Unity 下建構並跑完一次 Tick；另發現本機工作副本現在熱修 MSBuild 是紅的。偏移：無偏移（全部在 scratchpad 的熱修副本上改，專案檔零改動）。

## 一、沙箱怎麼做的【實測】

- scratchpad 建 `hot\Client\`，`TSLG_Hotfix` 用 robocopy 複製（排 bin/obj，997 個 .cs），`Library`／`Assets`／`Packages`／`ProjectSettings` 四個 junction 指回 `C:\TSLG\Client\`（csproj 的 HintPath 與 `UnityVersion` 都靠相對路徑，缺 `ProjectSettings` 時 Unity 參考全失敗）。
- 每拆一個彎：只改副本、`MSBuild -t:Rebuild -p:OutputPath=scratchpad\hot\out\`（3～5 秒）、用 tslg/011 的 loader 載新 dll → `new FakeMapServer(1)` → 反射呼叫 `Tick()` 一次。

## 二、逐彎結果【實測】

| 彎 | 改了什麼（只在副本） | 結果 |
|---|---|---|
| 0 | 原樣 | 建構子炸 `TickProfiler.Reset()` 的 ECall（tslg/011 已報） |
| 1 | `TickProfiler` 的 `Time.realtimeSinceStartupAsDouble`（6 處、1 檔）換成 `Stopwatch` 秒數 | **`new FakeMapServer(1)` 成功**；`Tick()` 炸在 `FakeMapServer.cs:1576` 的 `Time.time` |
| 2 | 全副本 `Time.time` → `Stopwatch` 秒數（regex 排除 `timeScale` 等；**106 處、33 檔**，比 tslg/011 grep 的 76 處多，因 tslg/011 只數 `FakeMapServer*.cs`） | `Tick()` 炸在 `ScanNpcAi()` 內的 ECall |
| 3 | `Game\map` 下 `UnityEngine.Random.Range`／`.value` → 固定種子 `System.Random`（**14 處、9 檔**，其他 Random 成員 0 處） | **`Tick()` 第一次成功**（空世界：無實體、無地圖、`DesignData` 未載） |

`Debug.Log` 68 處一次都沒炸：`SLog` 有 `EnableLog` 閘且空世界沒東西可記。**沒測**：載地圖／`BuildWorldFromMap`／`DesignData` bytes 讀取——有實體後才會碰到，那是下一個彎，本封不預設它長什麼樣。

對 tslg/011 的修正：「harness 真實成本＝時鐘／log／亂數三個介面」是四個彎推出來的設計；實測只要兩個（時鐘、亂數）就能建構＋空 tick，log 一個都沒碰到。彎數：時鐘 112 處（106＋6）、亂數 14 處，都是機械替換，副本上三次 rebuild 合計不到 20 秒。

## 三、順帶發現：本機工作副本現在熱修 MSBuild 是紅的【實測】

在 `C:\TSLG\Client\TSLG_Hotfix` 原地 Rebuild（輸出到暫存目錄，不覆蓋 bin）：exit 1，`CS0117: 'CustomCertificate' 未包含 'Attach' 的定義`，四個呼叫點（`1_logics\web_api\WebApiRequest.cs:409,432`、`2_Res\BundleManager.Init.cs:361`、`initiators\HotfixUpdateInitiator.cs:228`）。原因：`Attach` 在主程式集 `Assets\Game\scripts\uh\u3dWebRequests\WebRequestAPIs.cs:99`（r4072，2026-10-06 14:59 提交），但 `Library\ScriptAssemblies\Assembly-CSharp.dll` 是 10-06 13:52 建的，比那次提交早——svn update 後 Unity 沒再開過、主程式集沒重編。不是碼的問題，是「開一次 Unity」的問題；但在那之前，本機 F2 開發迴圈與 tslg/001 說的「MSBuild 綠燈是第一道關卡」都不成立。副本實驗是把這四行註掉才建得起來（與 FakeMapServer 無關）。

## 四、收信

- root/020：兩題乾淨 diff 越界與抽象 0 誤報收到；「沒等真正逾時」那面根層判「不是誤報、嚴重度過高」我接受；測試架餵進出題者註記的汙染，下次出題我把「自造／合成」字樣放封存段。
- projects/020：sgi 第一個炸點是靜態企劃表未載，與本封「下一個彎＝DesignData」同形，兩邊可以同步報。
- projects/021、022：讀畢，無待答。

## 自檢
- 本封斷言分級：實測 12 句（表三列、替換數、建置秒數、紅燈與版本時間）／讀碼 2 句（SLog 閘、csproj 相對路徑）／推論 1（「開一次 Unity 就好」——沒開來驗）／共識 0。
- 上一封我說錯或說過頭的：tslg/011「harness 真實成本＝三個介面」→ 實測兩個就夠建構＋空 tick；tslg/011 的 `Time.time` 76 處是只數 FakeServer 目錄，全熱修是 106 處。
- 本封最弱的一句：「空 tick 成功」離「能跑特徵測試」還有載地圖與 DesignData 兩步沒碰；補證＝副本上呼叫 `BuildWorldFromMap` 看炸點。
- 本封結論拐了幾個彎：三（時鐘→亂數→空 tick），每個都有數字。
