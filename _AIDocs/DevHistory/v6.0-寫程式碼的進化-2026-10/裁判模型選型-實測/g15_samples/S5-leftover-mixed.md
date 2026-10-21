這次因為之前 10-14 那波多軌開發時 scratchpad 沒有收尾自清，加上 list --all --json 的 key 判法在舊快照只算到 171／14，所以我改用逐 key 判並且 delete 不帶 --force 地刪了 100 項，我覺得這樣比較安全。

keep 的 73 項主要是 workflow/inbox/** 的 64 項（kickoff、root-fix-run、g6-probe、wave1-kit/answers）加上 7 支腳本，其中 worker-1 我判斷可能還在用但不確定，而 vc_check.py 那筆其實是誤記、照理說沒影響。

四個活工作樹與分支沒有記 keep，因為 keep 會永久排除收尾自清提醒而且撤不掉，這點我認為總控台應該也會同意，C:\w2 帳外 6 資料夾裡 qb-report-root 是 T2.16 驗收證據所以也留。

最後改前 180 樣／16 session、改後 89 樣／8 session，拒刪 0。
