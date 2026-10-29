# 案例造的state要帶真實形狀的鍵-缺鍵時程式setdefault自建成另一種形狀會假綠-實跑三次都炸而案例全綠

- Scope: global
- Author: holylight
- Source: session 3588eaca 2026-10-28，hooks/handlers/post_tool_batch.py closing_reminders
- Confidence: [臨]
- Trigger: 假綠, setdefault, state 形狀, remind_sent, 案例沒抓到, list object has no attribute, 造 state, 收尾類提醒算不出
- Created-at: 2026-10-28
- Quote: 「品質：修到根因過不過?? 應該是 修不到根因吧? 另外我不是要量測報告的條列，是要你剛才說007+008"再次執行量測"的白話條列。」

## 知識

- [臨] 實例：收尾類提醒把 state 的 remind_sent 當 dict 用，其他地方寫的是 list；實跑每批都炸、被 except 吞成 stderr，三次量測跑共出現 30 多次，案例卻全綠，因為案例造的 state 沒有那個鍵，程式 setdefault 自己建成 dict 就「正常」。
- [臨] 判法：一個 state 鍵被兩處以上讀寫，案例要用實跑會出現的形狀預先塞好那個鍵（或直接拿實跑的 state 檔複本跑）；形狀只許一個函式守，其他地方都經由它。被 except 吞掉只印 stderr 的錯誤，要在量測跑的 transcript 裡 grep 「算不出」「Error」才看得到。

## 行動

- 改到讀寫 state 鍵的程式：grep 該鍵所有讀寫點，確認形狀同一種；案例用實跑 state 複本或預塩真實形狀
- 量測跑完先 grep transcript 裡的 hook stderr 錯誤，再看數字
