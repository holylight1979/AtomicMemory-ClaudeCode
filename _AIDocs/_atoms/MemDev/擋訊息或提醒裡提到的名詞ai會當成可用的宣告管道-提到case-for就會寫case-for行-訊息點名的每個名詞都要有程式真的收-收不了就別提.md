# 擋訊息或提醒裡提到的名詞AI會當成可用的宣告管道-提到case_for就會寫case_for行-訊息點名的每個名詞都要有程式真的收-收不了就別提

- Scope: global
- Author: holylight
- Source: 2026-10-29 跑 011 判分 C′ G3；修法 commit cd1fd9d7（parse_case_for_decls）
- Confidence: [臨]
- Trigger: 擋訊息提到的名詞, AI 自創宣告格式, case_for｜, 宣告管道, 訊息教的路要收得到, 提醒文字設計, 守門訊息寫法, 連鎖誤判
- Created-at: 2026-10-29

## 知識

- [臨] 守門的擋訊息或提醒裡出現的每一個名詞，AI 都會當成「可以這样寫」的管道：欠案例的擋訊息寫「或驗證範圍宣告的 case_for 列了它」，AI 就在 # 註解裡寫「case_for｜receipt.py：test_cli.py::test_x」，而程式只收 need_goal 的 case_for。AI 的行為是合理的，錯在訊息點名了一條程式沒接的路。
- [臨] 寫守門訊息的判準：訊息裡提到的宣告名、欄位名、標籤，每一個都要有程式真的從 AI 看得到的管道（回覆文字、# 註解指令、thinking）收得到；收不到的就不要寫進訊息，或者補一條讀它的路。判分時看到「AI 照做了、程式沒認」，先查是不是訊息自己教的寫法。

## 行動

- 改擋訊息或提醒文字時，逐個名詞問：AI 照這個字寫一行，哪支程式會讀到？沒有就刪或補路
- 新增宣告行一律走三管道共用讀法（overview_hub.LOCATE_CHANNELS＋assistant_text_after），不另開格式
