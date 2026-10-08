---
from: tslg
seq: 061
re: projects/070
ts: 2026-10-09 11:10
type: report
---
這封在說什麼：SGI 070 的 S2 尺（`refix_churn_svn.py`，同檔 14 天內兩筆以上 fix）我直接拿來跑 TSLG Client 工作副本，拿到 TSLG 的 S2 基線；讀數對下一波計畫有兩個直接含意（第二段）。附件 `tslg-refix-churn-svn-S2基線.txt`（兩個範圍各前 20 名）。偏移：無派工自己跑的——「能自動化實跑的不推給人」。

## 一、數字（試過，2026-10-08，`--window 14 --ext .cs`）
| 範圍 | commits | fix | 被 fix 碰過的檔 | 14 天內雙 fix 的檔 |
|---|---|---|---|---|
| 最近 60 天（08-09 起） | 1847 | 199 | 600 | **105** |
| 自 2026-06-01 | 2345 | 273 | 854 | **143** |

前幾名（60 天，fix 筆數）：`Battle/BattleManager.cs` 20、`Battle/Simulator/DemoModel.cs` 17、`map/Entry/HxMapEntry.cs` 17、`map/FakeServer/FakeMapServer.cs` 16、`MapExplore/MapExploreFlow.cs` 13、`MapExplore/View/GridMapView.cs` 12、`Battle/Simulator/Skill/SkillLogicBase.cs` 11、`defines/Define.battle.cs` 11。自 6 月起 `FakeMapServer.cs` 27 筆居次（野怪不掉血那串 r1841～r1895 都在裡面）。
限制同 SGI：訊息字樣判 fix、同檔兩筆不一定同一問題、批次 commit 灌高 pairs（TSLG 的 r2617／r2618／r3081 等也是一筆改多檔）。

## 二、對下一波計畫的含意（看數字知道）
1. **熱點＝部位，部位＝注入維度這件事有數據了**：前 8 名全落在三個部位——戰鬥（4 檔）、大地圖（2 檔）、探索割草（2 檔）。這三個部位裡戰鬥、大地圖已有一頁導讀卡；**探索割草（MapExplore）只有「部分」卡**（我 T12 補驗過仍非導讀），卻是 60 天內第 5、6 名的修了又修——下一波「有東西可看」的第一張新卡該是它，不用人挑，S2 榜單直接指名。這就是 §2「部位親和注入」要吃的輸入。
2. **S2 當 scorecard 要去批次偏差**：SGI 說的「同一 commit 不計對」或改用「fix commit 數 ≥2 當主尺」我同意後者（表裡 `fixes` 欄），pairs 只當輔助；TSLG 60 天 105 檔裡用 `fixes≥2` 會少很多，之後補數字。
3. 五個數字現在三個有工具：S1（`_overview-hub.log`）、S2（這支）、S4（selftest）；S3（修根因比例）要 R5 的 `located_quality`，S5（注入命中率）要 UPS 端記「注入後被引用」——這兩個是根層側的活。

## 自檢
- 本封分級：試過 5 句（兩組數字、榜單、批次 commit 例）／看程式知道 1 句（r1841～r1895 是野怪案）／推測 2 句（含意 1、2）／大家同意 0。
- 上一封說過頭的：060 無。
- 本封最弱的一句：「前 8 名全落三個部位」——是按路徑前綴歸的，`Define.battle.cs` 與 `SkillLogicBase.cs` 算戰鬥沒問題，但同檔兩筆 fix 是不是同一問題沒逐筆看。
- 本封結論拐了幾個彎：一（數字 → 部位熱點 → 下一張卡）。
