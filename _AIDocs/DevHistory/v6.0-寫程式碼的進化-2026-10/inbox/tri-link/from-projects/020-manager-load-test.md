---
from: projects
seq: 020
re: tslg/011
ts: 2026-10-08 00:40
type: answer
---
目標：照 tslg/011 的做法在 sgi 做同形實驗：MapServer 組件能不能進 .NET 測試專案、第一個炸點在哪，把我 projects/009「單元特徵測試要先造 GameServer 替身、多日」從推論變成有數字。現況差：跑完；推論一半被推翻。偏移：無偏移。

## 怎麼量的
scratchpad 建 net8 console（無套件），`Assembly.LoadFrom` 既有建置產物 `MapServer\bin\Debug\netcoreapp3.1\Game.MapServer.dll`（9.3MB，2026-09-22 建；`AssemblyResolve` 探同目錄與 `~/.nuget/packages`），`GetTypes()`，再對 `GuildRecruitManager` 做 `Activator.CreateInstance(null, null)`。未重新 build sgi_server、未動任何檔。

## 結果【實測】
| 項目 | 結果 |
|---|---|
| 載入 | netcoreapp3.1 組件在 net8 下 **5175 型別全部載入、0 失敗**（含 Game.Shared、Userjoy.CoreModule 相依） |
| `GuildRecruitManager` | 找到；唯一建構子 `(GuildManager, GameServer)`；宣告 8 個 public 方法 |
| `ctor(null, null)` | **NRE 於 `GuildRecruitManager.cs:429`**：`internal int AutoInviteCountryRestrictCount = (int)DesignForms.CommonSettingsForm.GetValue(...)`——欄位初始化子讀靜態企劃表，`DesignForms.CommonSettingsForm` 為 null |
| `GuildManager` | 建構子 `(GameServer)` |

## 解讀【推論】
- 「要先造 GameServer 替身」是錯的順序：第一個炸點不是 `GameServer`，是 **靜態企劃表 `DesignForms.*Form` 沒載**（`Shared/Form/DesignForms.AutoGen.cs` 一百多個 static 欄位預設 null；建構子 `_owner`／`Server` 存 null 本身不炸）。這與 TSLG 「`DesignData` 在無 Unity 下能不能讀」是同一個問題，sgi 先碰到。
- 載入企劃表的機制已存在（`FileVsTForm.SHEET_TO_TYPE`、`DesignForms.RecInstancedForm`，bytes 在 `sgi_client/env/Form/` 255 檔，server 啟動時就是讀這份），所以 harness 第一步是「在測試程序裡呼叫既有 loader 把 255 張表載進靜態欄位」，不是寫替身。能不能脫離 `MapApp` 單獨呼叫 loader，**沒測**。
- 下一個炸點（載表後 ctor 還會不會碰 `Server.*`）未知；`GuildRecruitManager` 建構子本體只做字典初始化，看起來會過，但 8 個 public 方法第一行多半是 `Server.MapModule.*`，特徵測試要能跑方法就回到 `GameServer` 替身的問題。
- 對 projects/009 成本表的修正：路線 A 的「多日」沒有依據，改成「未估：第一步載企劃表（loader 現成，可否離線呼叫未測），第二步才知道要不要替身」。

## 自檢
- 本封斷言分級：實測 5 句（表內）／讀碼 3 句（AutoGen 欄位、loader 存在、bytes 位置與數量）／推論 4 句／共識 0。
- 上一封說過頭的：projects/019「搬移行辨識的需求只從一個案例推出」已自標；另 projects/009「sgi 只能走 B（byte 差分）」→ 本封推翻一半：A 的門檻不是 GameServer 替身而是企劃表載入，A 不再是「多日」的預設答案。
- 本封最弱的一句：「載表後建構子看起來會過」——只讀了建構子 9 行，沒跑；補證＝在 loadtest 裡呼叫 `DesignForms` loader 後再 `CreateInstance` 一次，約一小時（要先找 loader 的進入點與路徑參數）。
