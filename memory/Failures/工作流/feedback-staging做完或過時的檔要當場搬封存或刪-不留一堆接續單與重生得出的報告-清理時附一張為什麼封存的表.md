# feedback-staging做完或過時的檔要當場搬封存或刪-不留一堆接續單與重生得出的報告-清理時附一張為什麼封存的表

- Scope: global
- Author: holylight
- Source: session 050c2387 2026-10-27
- Quote: 「staging 下的檔案如果已經很多過時了或做完了，也應該要砍掉才對啊」
- Confidence: [臨]
- Trigger: _staging, staging 清理, 接續單 過時, next-phase 已完成, 封存, 已做完的計爲, 遷移 DevHistory, 重生的報告
- Created-at: 2026-10-27

## 知識

- [臨] 使用者原話：「staging 下的檔案如果已經很多過時了或做完了，也應該要砍掉才對啊」。背景：memory/_staging 累到 16 檔，含 235KB 的老接續單、已実作的草案、已量完的減量接續單、自動交接殘檔、兩份舊健檢輸出。
- [臨] 判準：_staging 只放「還在推進」的文件（現況 checklist、待修清單、最新一份工具輸出）。做完或被取代的接續單與計爲 → 搬 _AIDocs/DevHistory/<封存夾>/ 並附一張「檔｜原本是什麼｜為什麼封存」的表；重跑就有的報告與自動生成的殘檔 → 直接刪。沒逐條核對的就標「未逐條核對、當歷史留檔」，不假裝確認過。
- [臨] 注意：memory/_staging 不在版控（gitignore），git mv 會報 not under version control，用 mv/rm；搬進 _AIDocs 後才會進版控。

## 行動

- 每次改完 _staging 裡的現況文件，順手掃同夾：做完或被取代的當場搬封存或刪
- 封存夾一律附 _INDEX.md 寫為什麼封存，DevHistory/_INDEX.md 加一行指標
