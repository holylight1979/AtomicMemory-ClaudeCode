# Windows剛被別的行程搬動或寫入的檔會短暫拒絕存取-資料夾內有開著的檔就搬不動-多行程搶檔要對PermissionError稍等重試

- Scope: global
- Author: holylight
- Source: commit:15a4ae88、3443bdce（PR #4 mailbox 整併）2026-10-21
- Confidence: [臨]
- Trigger: PermissionError, Errno 13, WinError 32, WinError 5, rename 失敗, 搶檔, 並發讀寫, 共用資料夾, SMB, 防毒掃描, flaky, 偶發紅, os.rename, retry_on_busy
- Created-at: 2026-10-21
- Related: windows的git把worktree的git檔設成隱藏-python直接覆寫會permissionerror-要先unlink再寫
- Quote: 「好奇你的流程怎麼沒有寫之前有出的 側寫視角 那些? XD」

## 知識

- [臨] 兩個行程搶同一個檔（一個 os.rename 搬走、另一個馬上 open 讀）時，Windows 上讀的那方會短暫拿到 PermissionError [Errno 13]（不是 FileNotFoundError），負載高時才明顯：mailbox 壓測 3 支並行×80 輪，修前 6/160、修後 0/240。改名本身的「只有一人成功」鎖不受影響，壞的是鎖之後那步讀／寫。
- [臨] 資料夾裡任一檔被開著（例如附件開在 Excel），rename 那個資料夾丟 PermissionError WinError 5；檔案本身開著時 rename 它是 WinError 32（本機 NTFS 實測，Python open 不帶 FILE_SHARE_DELETE）。先搬 A 再搬 B 的兩步搬移，第二步失敗要把第一步退回，不然兩者分家。
- [臨] 修法：開檔／改名／附加寫入包一層「碰到 PermissionError 等 0.2 秒、最多 5 次，仍不行才報『被其他程式開著』」；FileNotFoundError 代表被別人搬走，不重試、照搶輸處理。刪除類（rmtree）不自動重試，改成先刪附屬再刪主檔，失敗時主檔還在、重跑可刪乾淨。
- [臨] 反方向也成立：Windows 上一支 Python 用 open() 開著檔讀時（CRT 開檔不帶 FILE_SHARE_DELETE），另一邊對同名檔 os.replace（暫存檔換上）會 PermissionError（WinError 5，實測）。多程序共用狀態檔、用「暫存檔＋os.replace」寫時，讀也要拿同一把鎖，或對 replace 做有限次重試。

## 行動

- 寫多行程共用資料夾的程式：凡 open／rename／append 剛被別人動過的檔，一律走「PermissionError 稍等重試」的包裝
- 並發測試偶發紅：先用壓力探針（多支並行、幾十輪、收 stderr 原文）確認是 Errno 13 短暫拒絕，再修；不要憑錯誤字串尾巴猜是哪一步
