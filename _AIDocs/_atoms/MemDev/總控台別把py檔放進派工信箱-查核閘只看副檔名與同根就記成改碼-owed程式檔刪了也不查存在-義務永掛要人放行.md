# 總控台別把py檔放進派工信箱-查核閘只看副檔名與同根就記成改碼-owed程式檔刪了也不查存在-義務永掛要人放行

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: v6-inbox, 派工信箱, 複製測試檔, case_debt, is_code_file, 仍存在的程式檔, (d) 改了程式碼, 總控台被擋, 查核閘誤判
- Created-at: 2026-10-13
- Source: session:72133ffb#0a6254c2 2026-10-13
- Quote: 「那要給我開session的prompt啊」

## 知識

- [臨] 实踩（對人總控台 session）：用 Bash `cp` 把 live 的測試檔複製到 `workflow/v6-inbox/to-track-a6/` 當派工素材，收尾闘 (d) 從此每回合擋「改了程式碼…仍存在的程式檔」，改名 .py.txt、刪掉都解不掉，最後要使用者放行。根因兩層：①`hooks/wg_verify_ledger.py` `is_code_file` 只看副檔名，信箱路徑與 live 程式同一 git 根，所以信箱裡的 .py 被視為本專案程式檔；②`case_debt` 的 `case_exists` 只套在清帳的案例檔，欠帳的程式檔不查存在，且 net_unchanged 只豁免 git 追蹤檔，session 內新建再刪的 untracked 檔永遠欠帳。已派 042 修；修前的避法：派工素材不要以 .py 落在 repo 內任何路徑，要就貼進 .md 派工單或存 .patch。

## 行動

- 總控台給工作 session 的參考檔：程式內容貼進派工單 .md 或存 .patch，不複製 .py 進 repo
- 收尾闘指的檔已不存在仍被擋 → 查 case_debt owed 分支有沒有查存在，不要只改名
