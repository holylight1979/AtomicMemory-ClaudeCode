# 判斷檔案在某日之後真的改過要看版控最後變更不看mtime-update與checkout會把mtime設成當下-本機未提交才看mtime-commit不動mtime不能當跨次快取鍵

- Scope: global
- Author: holylight
- Source: commit 4831257d（~/.claude）
- Confidence: [臨]
- Trigger: mtime, 最後變更, last-changed, 改過沒, 比卡新, svn update, git checkout, 誤報, 快取失效
- Created-at: 2026-10-29
- Depends: path:~/.claude/tools/atom-health-check.py
- Related: 大型svn工作副本整棵svn-status很慢-每檔約45微秒-hook裡查svn狀態要設時間上限-逾時改查點名的檔並記住這個根很慢
- Quote: 「有沒有要收割的經驗知識? 應該可以關 session 了齁?」

## 知識

- [臨] svn update／checkout、git pull／checkout 會把檔案 mtime 設成寫入當下：拿 mtime 判「這檔在某日之後改過」，程式沒變、只是這台剛 update 也會被當成改過。
- [臨] 正確口徑：檔在版控且乾淨 → 版控最後變更（svn info last-changed-revision／date、git log -1 -- <檔>）；本機有未提交修改或不在版控 → mtime（版控日期看不到沒提交的改動）。目錄：svn 目錄的 last-changed 涵蓋子孫，git log -- <目錄> 同理。
- [臨] 同一天分先後：同一個 svn repo 比版號（巢狀工作副本常同 repo，看 repository uuid），跨 repo 或 git 比提交時間；svn 日期是 UTC，先轉本地再取日期。
- [臨] svn commit 不改工作檔 mtime → 拿 (路徑, mtime) 當跨次快取鍵，改完再提交後會回舊答案；快取只放單次執行內。

## 行動

- 寫「X 之後改過沒」這類檢查前先問：這檔會不會被 update 刷新 mtime？在版控裡就問版控
- 參考實作：tools/atom-health-check.py 的 _ChangeClock
