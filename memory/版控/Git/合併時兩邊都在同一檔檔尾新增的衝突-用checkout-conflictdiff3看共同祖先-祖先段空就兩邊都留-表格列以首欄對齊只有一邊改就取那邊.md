# 合併時兩邊都在同一檔檔尾新增的衝突-用checkout--conflict=diff3看共同祖先-祖先段空就兩邊都留-表格列以首欄對齊只有一邊改就取那邊

- Scope: global
- Author: holylight
- Source: 2026-10-14 合併實踩（兩條分支同時動規則檔與文件）
- Confidence: [臨]
- Trigger: 合併衝突, 檔尾新增, 兩邊都加, diff3, conflict=diff3, 表格衝突, 多分支合併, 案例檔衝突, CHANGELOG 衝突
- Created-at: 2026-10-14
- Quote: 「你是 v6.0 的「調度總控台」（接任），對人總控台是 claude-06（原設計者只跟它講話，你不直接問原設計者）。第一件事：用絕對路徑讀 C:\Users\holylight\.claude\workflow\v6-inbox\_console\調度交接-2026-10-14-b.md 全文，再讀 C:\Users\holylight\.claude\memory\_staging\next…」

## 知識

- [臨] 多分支並行最常見的衝突型：兩邊都在同一檔的檔尾（或同一區塊末）各自新增（規則表、案例檔、CHANGELOG 頂端）。解法：`git checkout --conflict=diff3 -- <檔>` 拿到帶共同祖先的三段標記；祖先段是空的就代表兩邊都是純新增，兩段都留（順序照合併方向：main 的在下、自己的在上，或依文件既有排序）。
- [臨] markdown 表格衝突：以首欄（列名）對齊逐列比，只有一邊改的列取那邊，兩邊都改同一列才真的要人判；列序照原表，衝突標記全清。解完要重跑兩邊的案例與探針確認不互踩。

## 行動

- 檔尾雙新增衝突先 --conflict=diff3 看祖先段，空就兩邊都留；表格逐列對首欄
