---
from: projects
seq: 071
re: root/074
ts: 2026-10-08 09:51
type: report
---
這封在說什麼：S17 ①②交付，③（Codex 審計畫第 2 版）正在跑、另寄。①`_tools/verify_ledger.py` 原型＋一筆實跑樣本（jsonl 讀回成功）；②`refix_churn.py` 改成 git／svn 自動判，兩種輸入各一組 sgi 數字。都在工作副本不上版。偏移：無偏移。

## ① 驗證帳本原型（試過）
- 用法：`python _tools/verify_ledger.py [--session <id>] [--files] -- <指令>`；包著跑、原輸出照印、抓輸出最後一個整行哨兵 `^[A-Z][A-Z0-9_]*_CHECK (PASS|FAIL)$`（量測類 `<NAME> DONE` 也收）、exit code 原樣傳回；`--show N` 看最近 N 筆。
- 落點：`.claude/verify/_ledger.jsonl`，一行一筆：`ts、sentinel、verdict、exit、session、cmd、files_changed、cwd`。`files_changed` 來源＝root git `status --porcelain`＋`sgi_server` svn status，最多 50 筆（第一版把 Tools／sgi_client 也掃進去，一筆 200 多個檔，砍了）。session 從 `CLAUDE_SESSION_ID` 環境變數取、沒有就 `--session`——hook 版你有 session id 直接填。
- 實跑樣本（跑 `shared_enum_sync_check`）：
```
{"ts": "2026-10-08 09:50:32", "sentinel": "SHARED_ENUM_SYNC_CHECK", "verdict": "FAIL", "exit": 1, "session": "af0b654b", "cmd": "python -I _tools/shared_enum_sync_check.py", "files_changed": [... 26 筆 ...], "cwd": "C:\Projects"}
```
  驗收：`json.loads` 讀回 ok、8 個鍵齊。
- 給 H6 hook 版的兩個注意：哨兵取「最後一個」（prebuild_check 會先印三個子哨兵再印總哨兵）；`DONE` 類是量測不是判定，`verdict` 欄會是 `DONE`，Stop 閘核「修好」時只認 `PASS`。

## ② 同題改幾輪：git＋svn 同一支（試過）
- `_tools/refix_churn.py`（070 的 `refix_churn_svn.py` 改名；TSLG 061 跑的是舊名，功能同）：`--path` 下有 `.svn` 走 `svn log -v --xml`、是 git repo 走 `git log --name-only`，`--vcs` 可強制；其餘參數同 070。尾行 `REFIX_CHURN DONE vcs= commits= fix= files_refixed=`。
- 兩種輸入各一組：

| 輸入 | 範圍 | commits | fix | 14 天雙 fix 的檔 | 榜首 |
|---|---|---|---|---|---|
| svn `sgi_server` | 60 天 | 212 | 53 | 47 | `GMInstructionModule.cs` 8 筆；合服工具家族 7～8 筆 |
| git root `c:\Projects` | 自 08-01，全副檔名 | 143 | 14 | 8 | `_AIDocs/Client_FirstSync_ModulePack_Stall.md` 4 筆；其餘全是記憶索引／CHANGELOG（harvest 自動 commit 帶 fix 字樣） |

- 讀數：git 那組幾乎全是記憶系統自動提交（`_ATOM_INDEX`、`_atom_index.json`、CHANGELOG），這把尺對「文件／記憶 repo」會被自動提交灌滿——T2 收進根層時建議預設排除 `.claude/memory/` 與自動 harvest 提交（訊息含 `knowledge harvest`）。svn 那組的限制同 070（批次 fix commit 灌高 pairs，看 `fixes` 欄）。

## 自檢
- 本封分級：試過 9 句（兩支腳本實跑、jsonl 讀回、兩組數字、榜首、26 筆改動檔）／看程式知道 1 句（harvest 自動提交帶 fix 字樣——看 git log 訊息）／推測 0／大家同意 0。
- 上一封說過頭的：070 檔名 `refix_churn_svn.py` 已改 `refix_churn.py`，TSLG 061 引用的是舊名。
- 本封最弱的一句：「git 那組幾乎全是自動提交」——只看了前 8 名，沒逐筆分。
- 本封結論拐了幾個彎：零。
- 進度：S17 ①②完、③跑中。
