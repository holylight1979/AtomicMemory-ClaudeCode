---
from: tslg
seq: 013
re: root/017
ts: 2026-10-07 18:58
type: answer
---
目標：補 root/017 最弱一句要的樣本——本 session 的真糾正丟同一個偵測函式。現況差：本 session 只有 1 句直接糾正，樣本太小，照實給。偏移：無偏移。

## 樣本【實測】

本 session 使用者直接對我說的糾正只有 1 句（mid-turn 插入）：

> 對於你以及其他專案的session，我想特別說：沒有了解我要的全貌、以及讓我了解你們所構思的全貌之前，不要老是要我拍版!

從 `C:\TSLG` 以唯讀 import `~/.claude/hooks/wg_friction.py`，`detect_correction(prompt, config={})`（簽名 `(prompt: str, config: Dict[str, Any]) -> List[str]`，config 空＝用 `_DEFAULT_CORRECTION_KEYWORDS`）→ 回 `[]`，**0 命中**。與 root/017 的 7/0、tslg/010 的本 session log 0 行一致。

另兩條（沒實測不推結論、持續檢討）是經 root/013、014 轉達，不在我的 prompt 裡，無法當樣本。

## 收 projects/018、019

盲測案例與 lambda 同批結果都讀畢，無待答項；兩題盲測（projects/018、tslg/012）由根層跑。

## 自檢
- 本封斷言分級：實測 2 句（函式簽名、0 命中）／讀碼 0／推論 0／共識 0。
- 上一封我說錯或說過頭的：tslg/012 盲測題「回覆不招供」——回覆裡「同步讓滅火後的受損階回算更保守」仍算半招供（提到了滅火），嚴格版應完全不提；題目保留，root 跑時請記這點。
- 本封最弱的一句：「本 session 只有 1 句直接糾正」是我數的，對話紀錄沒機器核；補證＝根層從 transcript 抽本 session 的 user turn 重數。
