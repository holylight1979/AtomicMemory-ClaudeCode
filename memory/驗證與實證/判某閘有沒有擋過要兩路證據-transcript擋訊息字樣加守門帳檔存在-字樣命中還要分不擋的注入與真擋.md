# 判某閘有沒有擋過要兩路證據-transcript擋訊息字樣加守門帳檔存在-字樣命中還要分不擋的注入與真擋

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 擋次, 有沒有擋過, 閘擋幾次, hook_success, hook_blocking_error, 守門帳, grep 擋訊息, 擋次誤算
- Created-at: 2026-10-27
- Related: claude-code的stop擋訊息在transcript是兩份-使用者訊息與hook-blocking-error-量重讀或重播時算同一次問要共用起點
- Source: session:17c8cd5c 2026-10-27

## 知識

- [臨] 判「某閘有沒有擋過、擋幾次」用兩路證據互相印證：①transcript 裡的擋訊息字樣；②該閘擋下時一定會寫的帳檔存不存在（例：對帳閘一擋就留 guard-reconcile.jsonl）。帳檔不存在而字樣有命中，先懷疑字樣算錯。
- [臨] 字樣命中還要看紀錄類型：Claude Code 的 hook_success（hook 正常結束、只附注入、不擋）也會帶同樣字樣，只有 hook_blocking_error 這類才是真擋。只 grep 字樣就算擋次會灌水。

## 行動

- 算擋次：字樣命中後再分紀錄類型，只認真擋那類
- 同時查該閘的帳檔，兩路對不上就先查計數方法
