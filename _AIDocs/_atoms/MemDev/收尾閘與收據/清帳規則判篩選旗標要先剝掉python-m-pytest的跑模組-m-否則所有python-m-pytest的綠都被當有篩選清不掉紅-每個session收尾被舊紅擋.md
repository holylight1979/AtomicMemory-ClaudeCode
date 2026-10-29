# 清帳規則判篩選旗標要先剝掉python-m-pytest的跑模組-m-否則所有python-m-pytest的綠都被當有篩選清不掉紅-每個session收尾被舊紅擋

- Scope: global
- Author: holylight
- Source: retry-cycles 熱修 de6756d6／main e4cc8086，調度總控台；裁定 #36
- Confidence: [臨]
- Trigger: python -m pytest, -m 被當篩選, 篩選過的綠不清紅, 綠清不掉紅, TestFailGate 舊紅, 清帳誤判, 篩選旗標, 改清帳規則, 指令寫法變體案例
- Created-at: 2026-10-14

## 知識

- [臨] 清帳規則（綠測要不要清掉舊紅測）裡「有沒有篩選旗標」的判式若把 `-m` 當 pytest 的標記篩選，`python -X utf8 -m pytest …` 這種全庫最常見的跑法全部被當成「有篩選」，字面不同的舊紅就永遠清不掉，每個 session 收尾都被 TestFailGate 擋。修法：判旗標前先剝 `-m pytest|unittest`（跑模組），`pytest -m slow` 照舉算篩選。
- [臨] 教訓：閘本體凡解析指令字串，紅案例要附「常見指令寫法變體」一組（python -m pytest／pytest 直呼／-k／::／絕對路徑／PowerShell 版），不只用簡化的 `pytest …`；快照與自審都沒抓到，是工作 session 自己收尾被擋才發現（裁定 #36）。

## 行動

- 改清帳／放行規則：正例用本庫真實完整指令字串，含 python -m pytest 形式；解析指令的規則交付附寫法變體案例
- 收尾被舊紅擋且明明跑過整檔綠：先查清帳規則把綠指令判成什麼
