# 自己flag的維護動作直接做完不要反問

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: 反問, 要不要我, 該做就做, follow-through
- Created-at: 2026-06-17
- Related: feedback-workflow-discipline, feedback-completion-gates, 模型行為移植-fable行為契約必載檔, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問, feedback-模糊裁示不硬化先深問-決策選項含使用到再問, feedback-能自動化實跑的驗證不准推給使用者-離線模擬不算驗證, 自己指出的更好做法若成本低就當場做掉-不要列成設計債丟給使用者, feedback-請使用者挑下一步或範圍時用選單問-可複選就開複選, feedback-退縮歸屬-主任務完工且token充裕時可做的事當場做完不推下個session

## 知識

- [固] 自己 flag 出來、明顯該做的維護/同步動作（更新過時 atom、補正索引、清衍生暫存、上既定批次 GIT）→ 直接執行做完，不要再用「要不要我…？」反問使用者。使用者原話：「這種不用問我，你應該完全自己要推進」。問句只留給真需使用者裁量的決策（業務取捨/不可逆/方向選擇）。
- **Why:** 反問已自評為該做的事 = 把責任推回使用者、增加來回、降低信任；與「直球、無懼推進」人設相如。
- **How to apply:** 收尾檢核發現缺漏(IDENTITY (a)) → 當場補；自己提出的 follow-through → 做完再報告，不問。[[feedback-workflow-discipline]] [[feedback-completion-gates]]
- [固] 再犯實例：實測中撞到一個真 bug（伺服器拒絕移動的訊息沒列進判準，導致位置跑掉），自己已經診斷清楚且修法是一行設定，卻在收尾寫「**要我修嗎？**」——違約。判準不是「在不在原本範圍」而是「**可不可逆 ＋ 我自己已否已判定該做**」；可逆且已判定該做就直接做完、實測驗證、收尾跟使用者說「順手修了，驗證如下」。

## 行動

- （依知識內容判斷）
