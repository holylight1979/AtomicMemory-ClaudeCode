# vendor-二進位-中間目錄路徑會嵌進組件-暫存路徑必須固定否則雜湊不可重現

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: vendor, 雜湊不一致, SHA-256, lock 檔, 外部 dll, deterministic build, BaseIntermediateOutputPath, OutputPath, 鎖定檔, 建置可重現
- Created-at: 2026-08-11
- Related: commit-前必須核對-staged-清單而非只信自己-add-了什麼

## 知識

- [臨] .NET 建置會把中間目錄與 PDB 路徑嵌進組件的 debug directory。即使 `Deterministic=true` 且原始碼完全相同，**只要 `BaseIntermediateOutputPath`/`OutputPath` 換了位置，產出的 dll 雜湊就不同**。
- [臨] 影響：用 lock 檔鎖定外部二進位雜湊時，vendor 腳本的暫存區若用系統 temp（路徑會隨環境變），同一份原始碼每次都產生新雜湊，lock 的 diff 就失去審查意義。暫存區要**固定在 repo 內的 git-ignored 目錄**。
- [臨] 驗證方式：vendor 腳本連續跑兩次，第二次要回報「未變更」。只跑一次看不出不可重現。
- [臨] 反模式：把被引用專案的 `OutputPath` 寫死指向消費方的 `libs/`。這讓「隨手建置一次」等同於「換掉受審二進位」，邊界檢查會因雜湊對不上而 fail。建置輸出應留在自己 bin/，vendor 由專用腳本明確執行。

## 行動

- vendor 腳本的 staging 目錄寫成固定相對路徑，不用 GetTempPath()
- 新增/修改 vendor 流程後，連續跑兩次確認雜湊穩定再提交
- 看到被引用專案的 OutputPath 指向別人的 libs/，視為缺陷而非便利
