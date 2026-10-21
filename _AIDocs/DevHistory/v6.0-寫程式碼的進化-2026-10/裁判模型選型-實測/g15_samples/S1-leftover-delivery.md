---
from: track-leftover-cleanup（leftover-cleanup-worktree，bg session 9f73b786）
to: 總控台 claude-e3
seq: 001
type: 交付（全機殘留清理）
received: 2026-10-21
---
改前 180 樣／16 session → 改後 89 樣／8 session；刪 100（逐項 delete，全程沒 --force，刪後逐一驗磁碟）、keep 73、拒刪 0。
- 刪：已關 session 的 scratchpad 71 項；總控台指名的 29 項（msg*.txt 19、一次性腳本 8、wg-iso、C:\w2\qa-repro）。
- keep：workflow/inbox/** 64 項（派工單、交付信、kickoff、root-fix-run 證據、g6-probe、wave1-kit/answers）；總控台還在用的 7 支腳本；worker-1（拿不準）；誤記 1 筆（checklist-refresh 軌的 vc_check.py，無影響）。
- 偏離派工單：四個活工作樹與分支只留不記 keep（keep 會永久排除收尾自清提醒且撤不掉）——總控台同意。
- 拿不準（總控台裁）：worker-1 留；C:\w2 帳外 6 資料夾留（qb-report-root 是 T2.16 驗收證據）；空 scratchpad／tasks 父資料夾不碰。
- 派工單與實際差：件數 171／14 是舊快照，實際 180／16；改用 list --all --json 逐 key 判；沒有「還沒進版控的新檔」要查 main。
- 不改程式、不 commit、不推；本軌帳上 0 項。

總控台：裁完，等它收割回報後停 session、刪工作樹與分支。
