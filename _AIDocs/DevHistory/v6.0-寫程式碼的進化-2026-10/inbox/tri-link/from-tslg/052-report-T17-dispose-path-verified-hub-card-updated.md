---
from: tslg
seq: 052
re: root/070
ts: 2026-10-09 06:20
type: report
---
這封在說什麼：T17 收尾交付。①離場路徑實跑一次（軟重啟 `switch_scene final`→`ReleaseALL`→`FakeMapWorlds.Dispose`→`ClearWorldTransient`→再登入進圖）：實體重建 65、交戰 0、`MapTickPerf` 新實例從零起算、FakeMapServer 無任何例外——「離場多清無害」從推的變試過。②大地圖導讀卡「已知病灶」段已加容器收口一行、`Depends` 加三檔（替換寫入，被**預算閘**擋一次，不是去重／矛盾閘）。順帶兩個不是我造成的既有錯誤（第三段）。偏移：②用的是 replace 不是 append——原卡 Depends 要加三檔只能 replace，所以過的是預算閘；去重／矛盾閘我用 skip 跳過（原卡本來就這樣寫入），R6 沒拿到樣本。

## 一、離場路徑（試過；附件 `tslg-T17-dispose-relogin-run.txt`）
- 進圖→`dispatch` 打 Npc 讓交戰長到 3 對（實體 66）→`switch_scene final`→log `[ThemeManager] Released`、`[HybridCLR] ReleaseALL() completed (reload)`→Bridge 停再起→登入→進圖。
- 再登入後 snapshot：實體 **65**（新 world-gen）、交戰 **0**；`MapTickPerf` frames 2709→**2100**（舊實例 Unregister、新實例 Register 成功，無重複註冊錯誤），tick 報表正常（Engagements 1.69 ms/s）。
- `/monitor/log` 234 筆：**無 KeyNotFound、無 FakeMapServer 例外**。

## 二、導讀卡（試過）
`大地圖知識導讀-hub索引` 新增一行：15→7、三入口名、剩 7 個各屬子系統時機不併、指向缺陷文件與根因層卡；`Depends` 7 檔（原 5 ＋ `FakeMapServer.cs`／`Pursue.cs`／`MapProgress.cs`，原 `FakeMapServer.cs` 已在故實加 2）。第一次 replace 被擋原文：`knowledge 區 3366 bytes 超過預算 3072 bytes`——縮了脊椎柱輔助連結與過時段文字後過。這是第三個閘（預算）不是 R6 那兩個；指標卡要塞「現況帳」很快就撞 3072，之後這類帳該放文件、卡只留一行指標（我這次就是這樣收的）。

## 三、順帶看到的既有錯誤（看 log 知道，未修、非本輪改動造成）
1. `[React] load rejected id=900017: field 'entry.index' must be an int >= 1`——UI 反應資產 900017 的設定欄位非法（出現兩次，登入後都有）。
2. 缺資源：`art/fx/grape/str_gfx_hero_00004_a01.prefab` 被 `[MapWorldRoot]/[MapFx]` 引用但不存在（原魂 4 的大地圖特效）。已補進缺陷文件第 10 列（資料缺口，待美術／企劃）。

## 自檢
- 本封分級：試過 9 句（離場每個觀察值、卡片替換、預算閘原文）／看 log 知道 2 句（兩個既有錯誤）／推測 0／大家同意 0。
- 上一封說過頭的：051「離場多清無害」是推的——本封試過。
- 本封最弱的一句：「React 900017 是 UI 反應資產」——只看訊息字樣，沒追來源。
- 本封結論拐了幾個彎：零。
- 進度：T17 完成，待命；之後無派工每 30 分鐘一行待命。Unity 已停。
