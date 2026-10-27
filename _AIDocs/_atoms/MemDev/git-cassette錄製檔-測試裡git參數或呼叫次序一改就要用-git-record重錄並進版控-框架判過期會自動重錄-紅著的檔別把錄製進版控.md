# git-cassette錄製檔-測試裡git參數或呼叫次序一改就要用--git-record重錄並進版控-框架判過期會自動重錄-紅著的檔別把錄製進版控

- Scope: global
- Author: holylight
- Source: session aa80b4c2 2026-10-20 合併 GitLab !5／!6／!9 後 verify_stop_reconcile 86 紅、verify_normalize_eol 1 紅的追查
- Confidence: [臨]
- Trigger: CassetteMismatch, --git-record, cassette, 錄製檔, 重錄, 第 N 筆呼叫和錄製不同, 錄製檔過期, verify_stop_reconcile 大量 ERROR, 行為改了 → 用 --git-record 重錄, 夾具改名, 錄音衝突, auto 模式重錄
- Created-at: 2026-10-20
- Depends: path:C:/Users/holylight/.claude/lib/git_cassette.py
- Quote: 「跑"什麼"要14分鐘? 該死的不相干全量測試?」

## 知識

- [臨] 測試的 git／svn 子行程由 lib/git_cassette.py 錄一次之後重播（錄製檔在各 verify 目錄的 cassettes/<測試檔>/，入版控）。重播逐筆比對 exe＋argv＋cwd＋text：測試 helper 的 git 參數一改（例：加 `-c core.autocrlf=false`）或產品碼多叫一次 git（例：多一個 `check-ignore`），整檔測試 CassetteMismatch 成片 ERROR——不是程式壞，是錄製檔過期。修法：`pytest <檔> --git-record` 重錄，錄製檔連同程式一起 commit（同伴 MR 常漏附）。
- [臨] 框架自己也會切到錄製模式：錄製檔不在、格式舊、git 版本不同、或「被 git 叫起來的程式改了」（例：改了 merge-atom-index.py 這類合併驅動腳本）。所以改了那些腳本後跑一輪測試，一堆錄製檔會變 M；只提交「該檔測試全綠」的重錄結果，這台機器基準就紅的測試檔（環境問題）不要把它的錄製進版控，否則等於把這台機器的環境固化給別人。
- [臨] 一個 Bash 指令裡用 `git checkout -- <路徑>`／`git restore <路徑>` 丟掉錄製檔改動會被 OverviewHub 閘擋（判不出寫入目標）；要只提交一部分就用 `git add <明確路徑>` 挑，別碰其他的，worktree 刪掉時一起消失。
- [臨] verify_stop_reconcile 的錄音在每筆 git 呼叫前會比對受測目錄內容；改了測試夾具檔名後，只刪不合的那幾份錄音、用預設 auto 模式重跑（缺檔才錄），不要整支 --git-record（會把上百份錄音全換掉，diff 很髒）。
- [臨] 兩條分支各自重錄同一份錄音、合併時衝突：刪掉衝突的那幾份，用合併後的程式重錄，不取任一邊。

## 行動

- 看到成片 CassetteMismatch：先看訊息裡「錄製」vs「這次」的 argv 差在哪，是參數或次序改了就重錄，不要去改程式
- 重錄後跑一次不帶 --git-record 的重播確認過，再把 cassettes/<該檔>/ 連程式一起 commit
- 合併別人改到 git 合併驅動腳本的 MR 後，只提交全綠測試檔的重錄結果
