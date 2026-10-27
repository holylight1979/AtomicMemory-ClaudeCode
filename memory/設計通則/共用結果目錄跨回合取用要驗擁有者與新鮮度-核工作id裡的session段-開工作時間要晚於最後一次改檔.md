# 共用結果目錄跨回合取用要驗擁有者與新鮮度-核工作id裡的session段-開工作時間要晚於最後一次改檔

- Scope: global
- Author: holylight
- Source: 2026-10-23 第二意見等待修補實測
- Confidence: [臨]
- Trigger: 共用結果目錄, 跨回合取結果, job_id, 結果擁有者, 結果新鮮度, 別 session 的工作, 取到 done 就算跑過, 結果過期, session 前 8 碼, ID 前綴碰撞, tool_use_id 歸屬
- Created-at: 2026-10-22
- Related: 放行或豁免要綁使用者看過的那幾件-鍵用規則加完整對象-之後又改了檔就失效, 閘要求的動作若要等長工作就要同時給兩條路-工具本身分段同步等到結果-承認等待中用一行結構化宣告-否則照做了還被擋

## 知識

- [臨] 結果目錄是多個 session 共用的；「本回合取到 done 就算跑過」會讓別 session 的工作、或開工作之後又改過程式的工作混過。
- [臨] 跨回合取用要核兩件：工作 id 裡的 session 段是不是自己；開工作的時間晚於最後一次改檔。
- [臨] 工作 id 只帶 session 前 8 碼時，比 session 段不夠：掃目錄找「本 session 的工作」會把前 8 碼相同的別 session 工作收進來、取回別人的結果；工作目錄的 request.json 多半沒記完整 session_id，也不能拿來核。歸屬改用這次工具呼叫自己回的 id：hook 輸入的 tool_response，沒帶就照 tool_use_id 到本 session transcript 找。

## 行動

- 跨回合認領共用目錄裡的結果：先比工作 id 的 session 段，再比開工作時間與最後一次改檔時間
- 工作 id 只含 session 短前綴時不靠掃目錄比前綴，改用工具呼叫回傳的 id（tool_response，或 tool_use_id 對 transcript）
