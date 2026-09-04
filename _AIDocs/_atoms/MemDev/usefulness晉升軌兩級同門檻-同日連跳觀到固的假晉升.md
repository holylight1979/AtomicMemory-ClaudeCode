# usefulness晉升軌兩級同門檻-同日連跳觀到固的假晉升

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_promote, 晉升, Promotion Suggestions, usefulness, Wilson, 臨觀固, memory health, 連跳
- Created-at: 2026-08-05
- Related: atom-usefulness-loop, 健檢error與索引矛盾即解析器誤報-audit跨層全掃自08-31起-週報global-only看不到專案層

## 知識

- [臨] confirmations 軌的門檻分兩級（[臨]→4 / [觀]→10），但 **usefulness 軌兩級共用同一組 lb≥0.6 / n≥3**。後果：用 usefulness 把 atom 從 [臨] 提到 [觀] 後，**同一次健檢的下一輪它馬上又合格 [觀]→[固]**（實測：5 顆專案 atom 提完立刻重新出現在 Promotion Suggestions）。
- [臨] 照表執行等於一天內用**同一批證據**把 [臨] 打到 [固]，繞過「提完後要再被實際用一段時間」的分級本意。

## 行動

- 跑晉升批次：同一次健檢內每顆 atom 只升一級，[觀]→[固] 留到下一輪（需新增 usefulness 證據）
- 只有 confirmations 軌（跨 session 再確認）達標的才直接推 [固]
