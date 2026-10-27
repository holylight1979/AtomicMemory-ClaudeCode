# 部位表單檔前綴列可以只改一兩個檔的類別-最長前綴勝出-類別只認knowledge-gate字樣只有第二意見讀

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測
- Confidence: [臨]
- Trigger: 部位表單檔列, 單檔前綴, 類別欄, gate 類別, knowledge 類別, 少數檔變高風險, wg_second_opinion, overview-map.md
- Created-at: 2026-10-22
- Related: 部位表前綴一律寫成相對專案根-子字串命中的列會被任何錨在專案根的列整片蓋過, 部位表路徑前綴要用反引號包-沒包整列被解析器略過-表看起來有程式讀到是空的

## 知識

- [臨] `.claude/overview-map.md` 的路徑前綴可以寫成單一檔（要含 /，例 `hooks/handlers/stop.py`；同一格放多個反引號前綴用頓號隔開）；判法是錨在專案根的最長前綴，所以單檔列會蓋過它所在目錄那一列。
- [臨] 類別欄解析器只認 knowledge，其他值一律當 code；hooks/wg_second_opinion 另外讀原字，寫 gate＝這幾檔改了要第二意見。要讓少數檔變高風險又不動其他閘：照抄父目錄列的其他欄位，只換前綴與類別。
- [臨] 副作用：v6 開著時單檔列會被當成獨立部位，改那幾支要多交一組定位。

## 行動

- 要讓幾支檔改了就要第二意見：加單檔列、照抄父列欄位、類別寫 gate，再用 match_row 拿那幾支路徑實測
