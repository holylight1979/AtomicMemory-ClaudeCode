# pwsh-傳中文路徑給svn-exe會亂碼且big5的一字含@位元組觸發peg解析-改用python-subprocess

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svn 中文路徑, svn add 亂碼, peg revision is not allowed, E200009, E020024, Error resolving case, pwsh svn, PowerShell svn 亂碼, svn add --parents 建錯目錄, cp950 路徑, 一 a440, svn 路徑含 @, subprocess svn
- Created-at: 2026-09-18
- Related: svn-commit-中文訊息在-cp950-主控台會亂碼-必加-encoding-utf-8, workflow-svn

## 知識

- [臨] 實測（2026-09-18，svn 1.14.5，pwsh 7）：pwsh 把含中文的路徑當引數傳給 svn.exe 會亂碼——svn 收到的名字不是磁碟上的名字，`svn status <path>` 看似能跑，但 `svn add --parents` 會照亂碼名字新建一層假目錄（如 `shared\¼ö§ó`）並排程 added，`svn commit` 則報 E020024 Error resolving case。Python `subprocess.run([...])`（CreateProcessW 寬字元）傳同一條路徑完全正常。
- [臨] 另一個雷：Big5 的「一」是 A4 40，第二位元組是 '@'；路徑若以 cp950 位元組進到 svn，會被當 peg revision 切開→ E200009 "a peg revision is not allowed here"。尾端補 `@` 只是繞過解析，亂碼本身沒解。
- [臨] 收拾法：`svn status --xml` 拿到的路徑是正確 UTF-8，用 Python 解析後對 item=added 且磁碟上是空目錄的項目 `svn revert` + `os.rmdir`，再用 Python 重做 add/commit。
- [臨] 亂碼目錄名若含 cp950 無法表示的 Latin-1 字（º ¥ ¬ ³ ½ ª ¼ ö § ¾ Ô ° «…），連 Python subprocess 也定址不到（CRT 寬→ANSI best-fit 成別的字，`svn revert` 回 Skipped），磁碟目錄刪掉後會卡在 status=missing。最後手段：備份 `<wc-root>/.svn/wc.db` 後用 sqlite3 刪 `NODES` 中 `local_relpath=<完整相對路徑> AND op_depth>0` 與 `ACTUAL_NODE` 同路徑列，前提是該路徑只有 op_depth>0 的列、無 op_depth=0 base、無子節點（純 schedule-add 空目錄）；再 `svn cleanup` 驗。注意 local_relpath 相對於 WC 根（`svn info --show-item wc-root`），巢狀子目錄要加前綴。

## 行動

- Windows 上要把含中文的路徑傳給 svn.exe：一律走 Python subprocess（list 引數），不走 pwsh 也不走 bash 字串拼接
- 看到 svn 報 peg revision / Error resolving case 且路徑含中文 → 先懷疑引數編碼，不要試圖跟檔名硬拼
- svn add --parents 失敗後立刻 `svn status --xml` 找 item=added 的空目錄清掉，別留到 commit
