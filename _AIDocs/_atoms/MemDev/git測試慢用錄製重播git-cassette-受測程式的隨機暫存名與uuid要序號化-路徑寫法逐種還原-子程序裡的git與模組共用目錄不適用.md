# git測試慢用錄製重播git_cassette-受測程式的隨機暫存名與uuid要序號化-路徑寫法逐種還原-子程序裡的git與模組共用目錄不適用

- Scope: global
- Author: holylight
- Source: session:8d787d66 2026-10-15
- Quote: 「GO」
- Confidence: [臨]
- Trigger: git_cassette, 錄製重播, --git-record, 測試建 repo 太慢, git 子程序測試, CassetteMismatch, WG_GIT_CASSETTE, cassettes
- Created-at: 2026-10-15
- Related: feedback-全量測試從流程拔掉改增量待補-全量紅了指不出誰修修完又要全量-收尾跑llm適度擴展的可能相關清單

## 知識

- [臨] 測試慢在每案開 git 建 repo 時，用 lib/git_cassette.py（根 conftest 的 git_cassette fixture）：測試檔加一個 autouse fixture 呼叫 git_cassette(exclude=..., code=...)，第一次跑真 git 錄下、之後重播；行為改了用 pytest --git-record 重錄。細節見 TECH 驗證段。
- [臨] 重播對不上的五種來源（實遇）：受測程式的 mkstemp／mkdtemp 隨機檔名與 uuid4（fixture 已改序號、暫存目錄搬進 tmp_path/_tmp）；路徑短檔名／長檔名、正反斜線混用（逐種寫法各自還原，否則 check-ignore --stdin 回聲的路徑對不上）；受測程式寫的 .log／.jsonl 帶時間（不比）；commit 訊息帶當天日期（正規化）；有時間預算的程式在負載下錄製會多重試幾次、呼叫數不同（單獨重錄那支）。
- [臨] 不適用：git 在受測程式開的子程序裡跑（攔不到，子程序的非決定性效果會讓下一筆對不上）、repo 建在每案 tmp_path 之外（例 verify_install 的模組共用目錄）。被 git 叫起來的本專案程式（合併驅動）重播時不會跑，要列進 code 讓它改了自動重錄。
- [臨] 錄製工具自己的輔助動作（問 git／svn 版本）不能借用 fixture 換上的暫存名序號或受測目錄：曾用 TemporaryDirectory 吃掉一個號，單獨錄的檔整檔重播就差一位（claude-0b 回報）。tool_version 現在自己用 pid＋時間命名、建在 session 暫存根，單獨跑一支錄也對得上；之後給錄製工具加輔助動作照同一條。

## 行動

- 新套一支測試檔：加 fixture → --git-record 錄一次 → 不帶參數重播一次；重播紅先看訊息是「指令不同」還是「目錄內容不同」、是哪個檔
- 錄製要在機器不忙時單獨跑，有時間預算的案在負載下會錄到不同的呼叫數
