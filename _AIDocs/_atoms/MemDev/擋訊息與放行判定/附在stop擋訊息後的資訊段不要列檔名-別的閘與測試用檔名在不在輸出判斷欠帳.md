# 附在Stop擋訊息後的資訊段不要列檔名-別的閘與測試用檔名在不在輸出判斷欠帳

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: piggyback, _piggyback, 擋訊息附段落, Stop 附訊息, 檔名不在輸出, 欠帳斷言, 合 main 撞別軌測試, ReadingPath
- Created-at: 2026-10-13
- Source: session:6ea645d0 2026-10-13

## 知識

- [臨] 始末：Stop 把「這次對閱讀路徑的影響」經 _piggyback 併進別的閘的擋訊息，段落列了「不在 git 工作區、還沒 git add、沒量到」的檔名。合 main 後兩次撞到別軌的案（e8 044、know 的前綴正規化案）：它們用 `"b.py" not in out` 判斷「這個檔不再欠案例」，整個 stdout 都算，我的段落一點名就紅。根因：擋訊息是多個閘共用的輸出通道，對帳類閘的測試把「檔名出不出現」當欠帳代理。
- [臨] 正解：附在別的閘擋訊息後的資訊段只報個數（「還沒 git add 的新檔 N 個」），檔名交給 git status；只留量測結果本身非列不可的函式名。別軌的案不改；本軌單元案斷言「只報個數、不列檔名」。做新的 piggyback 段落前先 grep 測試裡 `not in out` 的寫法，看會不會撞。

## 行動

- 往 Stop 擋訊息加資訊段：不列檔名，只報個數
- 合 main 後別軌案紅在 `X not in out`：先查自己附的段落有沒有點名
