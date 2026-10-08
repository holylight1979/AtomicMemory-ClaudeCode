# 測試收尾不清共用的live量測檔-多session同機共用~claude時truncate會刪掉別人的真實資料-測試用monkeypatch改路徑

- Scope: global
- Author: holylight
- Source: session e40bc31f 2026-10-07，tri-link projects/052、tslg/043 回報 log 0 bytes
- Confidence: [臨]
- Trigger: 清 log, truncate, 測試殘留, 共用檔, 多 session, E2E 收尾, 量測 log, monkeypatch LOG_PATH, 別的 session 的資料
- Created-at: 2026-10-07
- Quote: 「接手「AI 寫碼守門三方討論」的根層總控端。先讀 C:\Users\holylight\.claude\memory\_staging\next-phase-AI寫碼守門三方討論.md 全文，照「下一步」做：重掛 Monitor 盯 c:\Projects\.claude\inbox\tri-link\ 的 from-projects 與 from-tslg、對帳信箱、做 R4 與 R5、每 6…」

## 知識

- [臨] 實踩：用真 hook 入口跑 E2E 後用 `: > workflow/_overview-hub.log` 清測試殘留，結果把同一台機器上另兩個專案 session 剛寫進去的真實觸發紀錄也刪了（~/.claude 是全機共用，hook 寫的量測檔就是共用檔），專案回報「log 0 bytes」我才發現。判準：任何「本 session 以外也會寫」的檔（workflow/ 下的 log、state、ledger）一律不在測試收尾清；測試要寫檔就 monkeypatch 路徑到 tmp，用真入口跑 E2E 也先改模組的路徑常數再跑。

## 行動

- 測試或 E2E 會寫到 ~/.claude/workflow/ → 先 monkeypatch／setattr 路徑到 tmp，絕不事後 truncate 真檔
- 清殘留前自問：這個檔別的 session 會不會也寫？會就只刪自己那幾行（按 session id 過濾）
