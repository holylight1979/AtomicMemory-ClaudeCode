# 多工人並行改同一套hooks的派工守則-檔案所有權表-共用出口主持端先做-settings單一擁有者-工人只回報片段-腳本式verify不進pytest清單

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 多工人, 並行施工, 派工守則, 檔案所有權, 共用守則檔, BRIEF, settings.json 誰改, 工人回報格式, 二十個 agent, 一天完工, 並行改 hooks
- Created-at: 2026-11-04
- Source: session:ad474d11#6b975fab 2026-11-04
- Quote: 「沒有要收割的知識經驗的話，我要關session囉」

## 知識

- [臨] 一天 20 個子代理並行改同一套 hooks 沒互踩的做法：①派工前寫一份共用守則檔（鐵律＋回報四段：改了哪些檔／驗了什麼沒驗什麼／發現／要改但不屬於我的檔），每個工人只讀它＋自己那幾張提案卡；②每個工人一張檔案所有權清單，動別人的檔只能寫進回報；③多人都要碰的共用出口（例 hook 輸出字元上限）主持端先做成一個 helper 再派工，工人只呼叫；④`settings.json`、`dispatcher` 路由表這類單點由主持端擁有，工人回報要加的 JSON 片段，主持端一次套；⑤工人不 commit，主持端收完跑受影響驗證再一筆上。
- [臨] 第二波（會碰第一波同檔的項目）等第一波收完再派；各自獨立的面向可同時派、同一條管線（UPS、Stop）的改動放同一個工人。
- [臨] 收尾踩到的：工人用 heredoc 寫含反斜線的 Python 會把 live hook 弄壞幾秒（守則要寫死用 Edit／Write）；工人留下 CRLF 工作副本（收尾統一轉 LF）；腳本式 verify（自印哨兵、模組層 sys.exit）放進 pytest 清單會 INTERNALERROR，要直接跑；`git add -A` 會把暫存 lock 檔帶進 commit（.gitignore 先補）。

## 行動

- 派多工人前：寫共用守則檔＋所有權表＋共用 helper 先做＋單點檔指定唯一擁有者
- 收尾：轉 LF、腳本式 verify 直接跑、檢查 git add -A 帶進什麼
