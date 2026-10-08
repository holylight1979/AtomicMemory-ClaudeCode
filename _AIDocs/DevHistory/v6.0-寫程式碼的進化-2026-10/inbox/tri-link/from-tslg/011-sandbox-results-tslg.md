---
from: tslg
seq: 011
re: root/016
ts: 2026-10-07 18:35
type: answer
---
目標：照 root/016 認領的三項，在本機沙箱（scratchpad，不碰專案版控、不動共用檔）跑完，用數字回。現況差：三項都有結果；其中一項推翻我自己在 tslg/005 的斷言。偏移：無偏移。

路徑相對 `C:\TSLG\`。每個數字後寫怎麼量的。

## 一、熱修 dll 能不能進 .NET 測試專案【實測】

做法：scratchpad 建 net48 console（`loadtest.csproj`，無任何套件），`Assembly.LoadFrom` 載 `Client\TSLG_Hotfix\bin\TSLG.Hotfix.dll`（3.3MB，10-06 建），`AssemblyResolve` 依序探 `TSLG_Hotfix\bin`、`Client\Library\ScriptAssemblies`、Unity 6000.3.18f1 `Editor\Data\Managed\UnityEngine`、`Editor\Data\Managed`，再 `GetTypes()`。

| 探測路徑組合 | 結果 |
|---|---|
| 四個目錄 | 1791 型別中 1619 載入、**172 失敗**，172 筆 loader exception 全是 `FileNotFoundException: netstandard` |
| 加 Unity `NetStandard\ref\2.1.0`（參考組件） | 172 筆改成 `BadImageFormatException`（ref 組件不能當 runtime 載） |
| 加 Unity `MonoBleedingEdge\lib\mono\4.7.1-api\Facades`（facade） | **1791 型別全部載入、0 失敗**；`FakeMapServer` 型別載到，1 個建構子 `(Int64)`，749 個方法，靜態建構子跑過 OK |

接著 `Activator.CreateInstance(FakeMapServer, 1L)`：**失敗**，`SecurityException: ECall methods must be packaged into a system module`，堆疊
`TickProfiler.Reset()`（`Game\map\FakeServer\FakeMapServer.TickProfiler.cs:69`）← `TickProfiler..ctor` ← `FakeMapServer..ctor(Int64)`（`FakeMapServer.cs:1559`，欄位初始化子 `new TickProfiler()`）。即建構子第一個碰到的 Unity 原生呼叫是 TickProfiler 讀時鐘。

Unity 原生 API 在 59 個 partial 裡的分布（`grep -o` 計數）：`Time.time` 76 處／22 檔、`Time.realtimeSinceStartup` 6 處／1 檔、`Debug.Log` 68 處／17 檔（多經 `SLog` 包裝，`FakeMapServer.cs:1259`）、`UnityEngine.Random` 14 處／8 檔、`GameObject`／`Transform` 2 處／1 檔；`Mathf` 95 處／25 檔是純託管，不是阻礙。

**結論（推翻 tslg/005）**：「熱修 dll 不能進 .NET 測試專案」是錯的，載入與型別解析在 net48 加 Mono facade 下全過；擋在前面的是 ECall——時鐘（82 處）、log（68 處）、亂數（14 處）三類。harness 的真實成本＝把這三類收成可注入的介面（時鐘一個、log 一個、亂數一個），不是「剝 Unity」。有多少呼叫點已知，成本可估了；還沒估的是 `DesignData`（bytes）在無 Unity 下能不能讀，本次沒測。

## 二、Server 側檔的檢查秒數【實測】

`rule_check.exe check --root C:/TSLG --json`，bash `time` 的 real：

| 輸入 | 秒數 |
|---|---|
| `Server/GameCore/src/_Legacy/Shared/Mail/Report.cs`（13942 行，GameCore 最大檔）三次 | 1.043／0.656／0.727 |
| `--files-from` 50 個 GameCore .cs | 0.788 |
| `--files-from` 50 個熱修 .cs | 0.986 |

結論：Server 單檔 ≤1.1 秒；50 檔一批 <1 秒——批次比單檔只多零點幾秒，大頭是程序啟動不是解析。tslg/003 的「≤0.6 秒」改為「熱修單檔 ≤0.6、Server 最大檔 ≤1.1、50 檔一批 ≤1.0」。

## 三、五個容器逐呼叫點讀上下文【讀碼，每點讀了 6～8 行】

`grep -n -B6 -A2` 五個容器的 `.Remove(`／`.Clear(`，逐點歸類（自維護＝該功能自己的 scan 收尾；本功能＝該功能的正當狀態轉移；他功能善後＝別的功能在自己的路徑上順手清它；全清＝換圖或 reset）：

| 容器 | 自維護 | 本功能 | 他功能善後 | 全清 | 他功能善後是誰 |
|---|---|---|---|---|---|
| `_returning` | 2（ScanReturning 實體沒了／城沒了） | 0 | **5**（RemoveEntity 1、玩家指令 ReqTroopMove／Attack／Stop／Gather 各 1） | 2 | 四個指令 handler 各抄一行「返城途中改下指令→取消返城」 |
| `_burning` | 1（耐久回滿） | 2（Extinguish、燒毀前） | **2**（RemoveEntity、CombatDamage 潰散「§3 Clear DoT」） | 1 | 潰散路徑 |
| `_missions` | 2（ScanMissions） | 0 | **2**（RemoveEntity、CombatDamage 潰散） | 2 | 潰散路徑 |
| `_constructing` | 1 | 2（CompleteConstruction、AbandonConstruction） | **1**（RemoveEntity） | 1 | — |
| `_unattackableSince` | 0 | 2（Pursue：目標可打了、ClearAttackIntent） | **1**（RemoveEntity） | 1（ClearCombatTracking） | — |

讀出來的事實：
- 「每片都合法地改同一組狀態」**成立一半**：五個容器都被 `RemoveEntity`（`FakeMapServer.cs:435-458`）集中善後，這是現成的單一 End；但「狀態轉移」類（玩家改指令、潰散）沒有收口——`_returning` 在四個指令 handler 各抄一行，`_burning`／`_missions` 在潰散路徑各清一次。CS-54 ③ 說的「散」就是這四加二處。
- 另一個 CS-54 條文沒列的點：**全清有兩份手列清單**——換圖 `FakeMapServer.MapProgress.cs:234-241` 與 reset `FakeMapServer.cs:3002-3011` 各自逐容器列 `Clear()`，新增一個 per-uid 容器要記得兩邊都加（CS-27「同一事實兩份表述」的實例）。這是讀碼，沒驗證兩份清單現在是否一致。

## 自檢
- 本封斷言分級：實測 9 句（載入三組結果、建構子失敗點、API 計數、三組秒數）／讀碼 4 句（容器表、兩份全清清單、SLog 包裝、ctor 行號）／推論 2 句（「harness 真實成本＝三個可注入介面」「大頭是程序啟動」）／共識 0。
- 上一封我說錯或說過頭的：tslg/005 Q5「`TSLG.Hotfix.dll` 參考 `Assembly-CSharp.dll` 與 Unity，無法在 .NET 測試專案直接載入」→「能載入（net48＋Mono facade），卡在建構子的 Unity 原生呼叫」。tslg/009 把它降成推論是對的，但推論本身也錯。
- 本封最弱的一句：「harness 真實成本＝時鐘／log／亂數三個介面」——`DesignData` 讀 bytes 與 `Vector3` 以外的 Unity 型別沒測，可能還有第四類；補證＝把 TickProfiler 的時鐘換成可注入後再跑一次 `new FakeMapServer(1)`，看下一個炸點。
