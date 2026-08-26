# 汰舊刪腳本要 grep 全 repo 實際呼叫點

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 汰舊, 刪除腳本, 清理舊檔, 死連結, deprecate, 移除檔案, 檔案改名
- Created-at: 2026-08-16

## 知識

- [臨] 删掉一支腳本/模組時，清「白名單、文件連結、索引」不等於清完——真正會爆的是**別種語言裡的寤叫點**（例：Node `path.join(TOOLS_DIR, "x.py")`），它不在 import 圖上，静態檢查與測試都抓不到，只有使用者按下那顆按鈕才發現。實案：guardian dashboard「測試」分頁引用已刪的 test-memory-v21.py 壞了數月無人知。
- [臨] 汰舊收尾固定動作：以**檔名字串**（非僅 import 語法）grep 全 repo，含 .js/.json/.md/.ps1 等非同語言檔；有 UI 入口的功能實點一次才算清完。

## 行動

- 删/改名任何腳本前，先 `grep -rn "<檔名>" .` 全 repo（包含其他語言與設定檔），逐一改接或一併移除
- 被删物件背後有 UI 按鈕/端點者，汰舊後實按一次驗收
