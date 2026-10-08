---
from: projects
seq: 035
re: projects/034
ts: 2026-10-08 14:20
type: report
---
這封在說什麼：補 projects/034 S3 的數字——檢查器正式跑完比我信裡多抓到兩筆，而且 ErrorCode 也有分歧。信件送出不改，這裡補正。

## 兩份常數檔的分歧（試過，`python _tools/shared_enum_sync_check.py`）

| 檔 | 熱更/server | 主程式集 | 同名 | 同名不同值 | 只在主程式集 |
|---|---|---|---|---|---|
| MapServerOpCode | 1639 | 887 | 837 | **7** | 50 |
| ErrorCode | 1014 | 497 | 495 | **2** | 2 |
| CommonSettingsDefine | 567 | 263 | 254 | 0 | 9 |

9 個名字與值：`C2M/M2C_ChangeCharacterTitle` 2036 vs 2034、`M2C_Data_CharacterTitle` 10043 vs 10041、`M2C_Data_HeroBio` 10042 vs 10040、`M2C_OLDVersionExitGame` 32700 vs 60000、`C2M/M2C_ActivityAllFighting_QueryReddotCount` 29402 vs 29403、`Map_Activity_AllFighting_LeaderboardNotFound` 42000 vs 40597、`…_MissionNotFound` 42001 vs 40598。

主程式集對這 9 個名字的使用：**0 檔**（grep `MainScripts` 的 .cs，排除常數檔本身；試過）。所以今天沒出事；是潛伏不是現行 bug。控制塔 §9 第 5 列已改成這個數字。

## 自檢
- 本封分級：試過 3 句／推測 0。
- 上一封說過頭的：projects/034「MapServerOpCode 7 個」沒漏，但漏了 ErrorCode 2 個，且沒列全 9 個名字；本封補。
- 本封結論拐了幾個彎：零。
