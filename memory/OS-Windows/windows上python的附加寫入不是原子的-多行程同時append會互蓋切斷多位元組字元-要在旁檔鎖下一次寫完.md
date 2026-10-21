# Windows上Python的附加寫入不是原子的-多行程同時append會互蓋切斷多位元組字元-要在旁檔鎖下一次寫完

- Scope: global
- Author: holylight
- Source: track-index-tools-fix 000（e7197deb）探針實測；lib/verify/verify_atom_io_audit_log.py
- Confidence: [臨]
- Trigger: append 互蓋, O_APPEND, 多行程寫 jsonl, 非 UTF-8 位元組, 稽核帳壞行, msvcrt locking, 共用 log 寫入
- Created-at: 2026-10-21
- Quote: 「妳有開好、加速後，再跟我講一次狀態、開幾個..」

## 知識

- [臨] Windows 上 open("a") 與 os.open(O_APPEND) 都是 CRT 先跳到檔尾再寫，多行程同時 append 會互蓋並切斷多位元組字元：8 行程×500 行實測 382～404 行非 UTF-8、掉約三成。改成整行先編成位元組、在旁檔 .lock 用 msvcrt（非 Windows 用 fcntl）鎖下一次寫完 → 4000/4000 完整。
- [臨] 孤立代理字元用嚴格 utf-8 編碼會丟 UnicodeEncodeError（不是 OSError），寫入端用 errors=backslashreplace；讀取端逐行容錯、壞行印 stderr 行號，不炸也不無聲略過。共用入口：lib.atom_io._audit_lock／iter_audit_entries。

## 行動

- 多行程共用的 jsonl／log 一律走 lib.atom_io._audit_lock 同款寫法；讀取端逐行容錯
- 看到 jsonl 有壞行先查是不是多行程 append，不要先怀疑編碼設定
