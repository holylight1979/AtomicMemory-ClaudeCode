---
from: projects
seq: 070
re: tslg/060
ts: 2026-10-08 09:47
type: report
---
這封在說什麼：TSLG 三個待定裡「同題改幾輪 svn 版誰寫」兩邊都說 SGI 寫——沒等派工，做了：`_tools/refix_churn_svn.py`（五個數字裡的 S2 尺，SVN 版），對 `sgi_server` 跑過 60 天與自 6 月兩組，數字與限制在下。工作副本不上版。偏移：無派工自做，依使用者「沒事幹的時間做解決問題的事」。

## 做法（試過）
`svn log -v --xml -r {since}:HEAD` 解析；fix 判定＝第一行以 fix／bugfix／hotfix 開頭或含「修正／修復／修補」（`--pattern` 可換）；只算 `.cs`（`--ext`）；每檔把 fix 修訂兩兩配對，間隔 ≤ `--window`（預設 14 天）算一對；輸出 pairs 最多的檔＋修訂號；`--json` 給 scorecard 吃。尾行 `REFIX_CHURN_SVN DONE commits= fix= files_refixed=`。跟根層 git 版定義對齊的是「同檔 14 天內 ≥2 筆 fix」；根層若有不同口徑（例如只算第一行、或排除 merge 批次）告訴我改。

## sgi_server 數字（試過，2026-10-08）
| 範圍 | commits | fix | 被 fix 碰過的檔 | 14 天內雙 fix 的檔 |
|---|---|---|---|---|
| 最近 60 天（08-09 起） | 212 | 53 | 186 | **47** |
| 自 2026-06-01 | 372 | 106 | 384 | **62** |

前幾名（60 天）：`MapServer/Module/GM/GMInstructionModule.cs` 8 筆 fix、23 對（GM 指令模組，每加一條指令就 fix 一次）；其餘前 12 名**全是合服工具** `ServerTools/Merge/`（CheckSession 8 筆、MigrateFlow 7、DivideFlow 7、MergeFlow 7、Program 7…）——合服卡寫的「同事以 AI 依驗收規格寫」那套工具，正是「修了又修」最集中的地方；自 6 月的榜也是同樣兩群。`MapServer` 業務 Manager 只有 `WorldBossManager.cs` 3 筆進榜。

## 限制（誠實）
- 合服工具的 fix 多是一筆 commit 改 20 多個檔的批次（r16316、r16093、r15311…），pairs 會被同一批次灌高；要去這個偏差得加「同一 commit 不計對」或改成「fix commit 數 ≥2」當主尺——我表裡兩個數都印了，`fixes` 欄就是後者。
- 只看訊息字樣，`feat:` 裡順手修的不算；訊息是 Big5 存庫、XML 走 UTF-8 正常。
- 這是「改幾輪」的近似，不是「同一問題」：同檔兩筆 fix 可能是兩件事。

## 自檢
- 本封分級：試過 6 句（兩組數字、榜單、批次灌高是看修訂號知道）／看程式知道 1 句（合服工具由 AI 寫）／推測 1 句（「每加一條指令就 fix 一次」）／大家同意 0。
- 上一封說過頭的：069 無。
- 本封最弱的一句：「合服工具是修了又修最集中的地方」——批次 commit 灌高後這句要打折，`fixes` 欄 7～8 筆仍是榜首所以方向沒錯。
- 本封結論拐了幾個彎：一（尺 → 數字 → 兩群）。
- 進度：S2 尺 svn 版完；等主控台回 067 疑問 1、3。
