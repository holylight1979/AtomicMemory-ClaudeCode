# svn一次查多檔-info與status帶多條路徑可跨巢狀工作副本一次查-有未進版控的目標exit1但xml照樣完整-log要連伺服器要並行

- Scope: global
- Author: holylight
- Source: commit 4831257d（~/.claude）
- Confidence: [臨]
- Trigger: svn info, svn status, svn log, 批次, 多個路徑, 巢狀工作副本, W155010, mbcs, ANSI 碼頁
- Created-at: 2026-10-29
- Related: 判斷檔案在某日之後真的改過要看版控最後變更不看mtime-update與checkout會把mtime設成當下-本機未提交才看mtime-commit不動mtime不能當跨次快取鍵, 取svn工作副本的base版-先用status-xml挑出本地改過的檔只對它們svn-cat-r-base-沒改過的base就是工作樹內容
- Quote: 「有沒有要收割的經驗知識? 應該可以關 session 了齁?」

## 知識

- [臨] `svn info --xml`、`svn status -q --xml` 可一次帶多條路徑，分屬不同巢狀工作副本也行；svn.exe 每叫一次約 0.15–0.3 秒，逐檔叫幾十條就是好幾秒。
- [臨] 目標含未進版控的檔：info 印 W155010、exit 1，但 stdout 的 XML 仍完整列出其他目標 → 看 XML 不看 exit code；`status -q` 不列未進版控的檔。
- [臨] info／status 只讀本地；`svn log` 要連伺服器，多條要並行跑。
- [臨] svn.exe 以 ANSI 碼頁收 argv：Python `s.encode("mbcs")` 嚴格模式不做 best-fit，可先判路徑會不會被換字。

## 行動

- 查一批檔的版控狀態：同一 VCS 合成一次呼叫，info 與 status 並行，解析 XML 而非看 exit code
