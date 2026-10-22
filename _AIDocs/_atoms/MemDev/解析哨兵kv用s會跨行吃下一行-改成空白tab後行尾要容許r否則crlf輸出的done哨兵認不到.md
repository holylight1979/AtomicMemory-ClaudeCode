# 解析哨兵k=v用\s+會跨行吃下一行-改成空白tab後行尾要容許\r否則CRLF輸出的DONE哨兵認不到

- Scope: global
- Author: holylight
- Source: track-gate-fixes-007 交付（main 3778d793）
- Confidence: [臨]
- Trigger: 哨兵解析, DONE 哨兵, k=v, parse_sentinels, CRLF, 跨行, 收據認不到
- Created-at: 2026-10-22

## 知識

- [臨] 解析 `<NAME> DONE k=v` 哨兵時用 `\s+` 分隔會跨行，把下一行的 `exit=0` 當成同一筆的欄位。改成 `[ \t]+` 之後，行尾要容許 `\r`，否則 Windows 上 CRLF 輸出的 DONE 哨兵認不到（閘小修 007 自己改出來的回歸，codex 抓到）。
- [臨] 同字哨兵多行（迴圈跑三類變異各印一行）要記次數 n，不能合成一筆。

## 行動

- 改哨兵正則時補 CRLF 輸出與多行同字的案例
