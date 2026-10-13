# Edit工具new_string尾端空白會被裁掉-切點停在空白上會黏字-切點要停在非空白字元並看diff

- Scope: global
- Author: holylight
- Source: session:23787466 2026-10-13 track-g12（v6/track-g12 commit 0a2f492、39bb754 內修回）
- Confidence: [臨]
- Trigger: Edit 工具, new_string, old_string, 行尾空白, 尾端空白, trailing whitespace, 黏字, 切點, Edit 後看 diff
- Created-at: 2026-10-13

## 知識

- [臨] 實踩（同一 session 兩輪共 4 處）：Edit 的 old_string 與 new_string 都以空白結尾（切點停在 `defs = `、`"max_turns_before": `、`b_entries = `、`P15_MOVE = ` 後面）時，結果檔裡那個空白不見了，變成 `defs =[item…`、`"max_turns_before":max(`、`b_entries ={`、`P15_MOVE =(`。推論：new_string 的尾端空白被裁掉，old_string 照原樣比對、吃掉原檔的空白（若兩邊都裁，原檔空白會留下、結果正確）。Edit 回報成功、Python 語法合法、測試照綠，只有看 diff 才發現。
- [臨] 防法：old_string／new_string 的開頭與結尾都停在非空白字元（切點往後延伸一個字元，例 `defs = [item`）；一批 Edit 做完用 `git diff` 全看一遍，專找 `=[`、`={`、`":x` 這類黏字。

## 行動

- 寫 Edit 時 old_string／new_string 的頭尾不停在空白上
- 多處 Edit 後 git diff 全看一遍找黏字，再跑測試與提交
