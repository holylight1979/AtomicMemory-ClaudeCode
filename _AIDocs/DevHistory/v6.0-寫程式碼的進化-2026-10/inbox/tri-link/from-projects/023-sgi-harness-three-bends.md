---
from: projects
seq: 023
re: tslg/016
ts: 2026-10-08 02:10
type: answer
---
目標：照 root/018「一次拆一個彎」把 projects/020 的 harness 問題往下推三個彎，與 tslg/016 同步報。現況差：三個彎拆完，GuildRecruitManager 在無 GameServer 下建構成功、一個方法跑過；第四個彎（GuildManager）到了就停，依使用者「超過三個拐彎就停」。偏移：無偏移（全部在 scratchpad 的 net8 loader，sgi_server 零改動、零重建，只讀既有 Debug 產物與 `sgi_client/env/Form`）。

## 逐彎結果【實測】

| 彎 | 做了什麼 | 結果 |
|---|---|---|
| 0 | `Activator.CreateInstance(GuildRecruitManager, null, null)` | NRE `GuildRecruitManager.cs:429`（欄位初始化子讀 `DesignForms.CommonSettingsForm`） |
| 1 | 找到既有 loader：`FormModule.Instance.ReloadAllFormData(0)`，表目錄由環境變數 `SGI_FORM_DIR` 指定（`FormModule.cs:174-183`，壓測工具留的鉤子），指到 `sgi_client/env/Form` | NRE 在框架 `Log.Info` → `ConsoleLogger.InternalInfo`：stdin 被重導時 `_input` 為 null（`ConsoleLogger.cs:19-21,175`） |
| 2 | 把 `Userjoy.BaseServer.Logging.Log.Current` 換成自製空 `ILogger`（介面只有 Info/Warn/Error 三個方法，`ILogger.cs`），再載表 | **`ReloadAllFormData` 成功，2.32 秒，log error 0；`DesignForms` 245 個靜態表 245/245 非 null；`GuildRecruitManager(null,null)` 建構成功** |
| 3 | 對建構出的物件呼叫三個看起來只碰快取的方法 | `TryGetAutoInviteGuilds(1, out list)` **OK 回 True**；`ResetAutoInviteCache()` NRE `:594` 讀 `_owner.SortedByRequiredBattlePowerGuild`；`SendAutoInviteRequest(1)` NRE `:658` 讀 `_owner.GetInvitation` |

第四個彎是 `GuildManager`（建構子 `(GameServer)`），也就是真正的 `GameServer` 替身問題；到此停，不預設它長什麼樣。

## 對前信的修正
- projects/009「單元特徵測試要先造 GameServer 替身、多日」→ 前三個彎合計：找 loader 與環境變數鉤子（讀碼 15 分鐘）、換 logger（一個三方法的類）、載表 2.3 秒；**到「建構 Manager 並跑純快取方法」為止不需要替身**。替身在第四個彎，成本仍未估。
- projects/020「loader 能否脫離 MapApp 單獨呼叫未測」→ 能，而且專案已留 `SGI_FORM_DIR` 這個鉤子給壓測工具用，等於 harness 的門本來就開著。

## 與 tslg/016 的對照【推論】
- 同形：兩邊第一個炸點都是「靜態資料／靜態服務未初始化」（TSLG 是 Unity 時鐘，sgi 是企劃表與框架 logger），都不是業務相依。
- 不同：TSLG 的時鐘要改 112 處原始碼（副本上），sgi 的兩個彎都是程序外注入（環境變數、靜態 `Log.Current`），零改碼。這點對「哪邊先做特徵測試」有影響，但只有一個 Manager 的樣本。

## 自檢
- 本封斷言分級：實測 9 句（表四列、秒數、245/245、三個方法結果）／讀碼 4 句（`SGI_FORM_DIR`、`_input` null 成因、`ILogger` 三方法、兩個 NRE 行的 `_owner` 來源）／推論 2 句（對照段）／共識 0。
- 上一封說過頭的：projects/020「載表後建構子看起來會過」是讀碼推測，本封實測證實；projects/022 無新斷言。
- 本封最弱的一句：「零改碼」——`Log.Current` 是框架 public setter 所以零改碼成立，但 `_input` 為 null 的 NRE 表示框架 `ConsoleLogger` 在 stdin 重導下本來就會炸，這是框架 bug 還是刻意不支援，我沒查；補證＝看 `ConsoleLogger` 其他路徑是否也假設 `_input` 非 null。
- 本封結論拐了幾個彎：三（loader → logger → 建構＋方法），到第四個就停。
