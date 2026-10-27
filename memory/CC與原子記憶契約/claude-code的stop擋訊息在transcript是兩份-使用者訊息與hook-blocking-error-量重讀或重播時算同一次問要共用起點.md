# Claude Code的Stop擋訊息在transcript是兩份-使用者訊息與hook_blocking_error-量重讀或重播時算同一次問要共用起點

- Scope: global
- Author: holylight
- Source: merge 7eaf2824（擋訊息瘦身）2026-10-27
- Confidence: [臨]
- Trigger: Stop hook feedback, hook_blocking_error, 擋訊息兩份, Stop 擋訊息, 重讀量, 事件帳重播, 判準卡去重, transcript 計數, 已送過判定
- Created-at: 2026-10-27
- Related: 用事件帳重播量改動省多少前先拿舊碼重播跟實跑transcript逐字對帳-對上了才換新碼量-重播輸入要還原到當時

## 知識

- [臨] Claude Code 把同一則 Stop 擋訊息寫成兩份進 transcript：一份是 user 訊息「Stop hook feedback:…」，一份是 system 的 hook_blocking_error。
- [臨] 量重讀量或做事件帳重播時，這兩份是同一次問：用同一個起點判「送過沒」，不能讓第二份把第一份當成已送過。
- [臨] 實例：重播判準卡去重時，收尾那則的卡被第二份算成已送、假省 260 tok；改成同一次呼叫內兩份共用起點後才對上實跑。

## 行動

- 數 transcript 裡的擋訊息或注入次數前，先把同一次 Stop 擋的兩份歸成一次
- 去重或已送判定以「同一次 hook 呼叫」為單位，不以紀錄列為單位
