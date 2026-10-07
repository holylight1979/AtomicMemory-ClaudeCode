# feedback-規則型卡片只寫現況白話句-判準寫改的是什麼不是session在哪-規則本體進憲法層必載檔不只住atom

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 規則型 atom, 技術臭味, 日期進 atom, 憲法等級, 必載契約, always-load-contracts, 判準, 寫規則, preferences 改寫, 路徑揭露
- Created-at: 2026-10-07
- Source: session:f1e8b9d8#39480514 2026-10-07
- Quote: 「該記的經驗知識都處理好了? 可以關閉session了?」

## 知識

- [臨] 始末：把「記憶系統相關直上版控」寫進 preferences atom 時，一句裡塞了路徑清單、config 鍵名與日期，判準還寫成「session cwd 在 ~/.claude」。使用者連指三點：判準要是「改的是什麼」不是「人在哪」；規則卡片不該有技術臭味；日期不進 atom。他進一步問：這類規則是不是該是「憲法等級」——答案是對的。
- [臨] 根因：行為規則只住在 atom 裡就會飄——atom 靠 trigger 命中、有預算上限、會被截斷、自由文字無閥；這與之前「上GIT 契約偏移」是同一種病。正解分三層：規則本體進必載檔（rules/core.md／USER／IDENTITY）並登記必載契約表讓系統守缺句；atom 與 USER 只留一句白話指向它；寫入端加程式閥擋規則型卡片的日期戲與 config 鍵名。
- [臨] 寫規則卡片的自檢：陣生人一眼看得懂嗎？有沒有路徑、鍵名、日期、實作細節？有就移到 TECH／CHANGELOG，卡片只留「什麼情況做什麼」。

## 行動

- 寫或改行為規則：先問它該不該是必載層；是就進 rules/core.md／USER 並登記契約表，atom 只留指向句
- 規則卡片的知識行自檢：無路徑、無鍵名、無日期、白話一句一義；判準用「改的是什麼」類的對象性條件
