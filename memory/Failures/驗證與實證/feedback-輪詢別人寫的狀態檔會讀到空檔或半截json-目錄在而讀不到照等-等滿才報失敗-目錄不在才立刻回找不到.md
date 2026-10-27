# feedback-輪詢別人寫的狀態檔會讀到空檔或半截json-目錄在而讀不到照等-等滿才報失敗-目錄不在才立刻回找不到

- Scope: global
- Author: holylight
- Source: 2026-10-23 第二意見等待修補實測
- Confidence: [臨]
- Trigger: 輪詢狀態檔, status.json, 非原子寫入, write_text 改狀態檔, 讀到空檔, 半截 JSON, JSONDecodeError, 輪詢誤報失敗
- Created-at: 2026-10-22
- Related: windows上python的附加寫入不是原子的-多行程同時append會互蓋切斷多位元組字元-要在旁檔鎖下一次寫完

## 知識

- [臨] 輪詢別人寫的狀態檔：對方若不是原子寫入（例如 write_text 直接改 status.json），輪詢端偶爾會讀到空檔或沒寫完的 JSON。
- [臨] 處理：目錄在而讀不到時照等，等滿才報失敗；目錄不在才立刻回找不到。

## 行動

- 寫輪詢狀態檔的程式：讀不到或 JSON 壞掉當「還沒好」繼續等；只有目錄不存在才立刻回找不到
