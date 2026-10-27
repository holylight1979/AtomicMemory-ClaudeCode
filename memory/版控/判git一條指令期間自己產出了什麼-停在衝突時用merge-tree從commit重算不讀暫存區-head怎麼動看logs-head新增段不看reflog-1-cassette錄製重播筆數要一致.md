# 判git一條指令期間自己產出了什麼-停在衝突時用merge-tree從commit重算不讀暫存區-HEAD怎麼動看logs-HEAD新增段不看reflog-1-cassette錄製重播筆數要一致

- Scope: global
- Author: holylight
- Source: commit:381e3d85 2026-10-21（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: merge-tree --write-tree, 停在衝突, logs/HEAD, reflog -1, REBASE_HEAD, git_cassette, 錄製重播, 舊測試閘 merge 誤擋, python 啟動器 cp950
- Created-at: 2026-10-21
- Quote: 「我今天要下班離開電腦前了、明早才會進公司。 我有另外開一個空Fable Session，title 我也改了名字叫 `(備)v6總控台-人+調`，如果此session的context又快用完(超過85%)了，你再自己去貼session prompt來繼承你； Codex的檢核意見，你要提醒工作session審過 (別呆呆的就又掉進飄移坑)； **用經驗、朝目標、避免飄、不空等、不浪費**。」

## 知識

- [臨] git 停在合併衝突時 HEAD 不動、別軌自動合好的檔在暫存區；要知道「git 自己產出什麼」用 `git merge-tree --write-tree [--merge-base=X^] HEAD X` 從 commit 重算，不讀暫存區（同一支腳本可能 add 了自己的改動）。
- [臨] 判一條指令期間 HEAD 怎麼動，reflog -1 不夠（先 merge 再 commit 只看到 commit）：記執行前 `<gitdir>/logs/HEAD` 的位元組數、事後讀新增那幾行；REBASE_HEAD 這類標記要比內容，同名往下一步內容會變。
- [臨] git_cassette 錄製重播要求呼叫筆數一致：「量到合格就提早停」的迴圈、或閘逾時把子行程砍在半路，都讓錄製與重播筆數不同；計時案要讓被量的子行程一定跑完再拿耗時比門檻；cassette 的 code= 清單裡的程式改了要重錄並 commit，不然每次作廢重錄跑真 git。
- [臨] Windows 上包 git 的 python 啟動器要寫原位元組（sys.stdout.buffer），文字模式遇到 ⚠ 這類字會在 cp950 炸掉。

## 行動

- 要知道 git 自己合了什麼→merge-tree 重算；要知道 HEAD 怎麼動→logs/HEAD 新增段
- 改到 cassette code= 清單的程式就重錄並 commit
