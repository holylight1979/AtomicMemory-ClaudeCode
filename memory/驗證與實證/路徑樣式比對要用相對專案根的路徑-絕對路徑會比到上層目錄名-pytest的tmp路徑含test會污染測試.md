# 路徑樣式比對要用相對專案根的路徑-絕對路徑會比到上層目錄名-pytest的tmp路徑含test會污染測試

- Scope: global
- Author: holylight
- Source: commit:e8fef8a2 2026-10-12（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: glob, fnmatch, 路徑樣式比對, 絕對路徑, tmp_path, pytest tmp, 測試檔判定, verify_case_globs, 案例判定, 假綠
- Created-at: 2026-10-12
- Related: 從文字抓windows絕對路徑的正則要加磁碟代號前不接字母-否則網址的p冒號斜線被當成p槽路徑

## 知識

- [臨] 用 glob（fnmatch、`**/*test*`）判斷「這個檔是不是測試檔／某類檔」時，先把路徑轉成相對專案根的路徑再比。拿絕對路徑比，寬鬆樣式會比到專案根以外的上層目錄名（`C:\latest\…`、`D:\tests-env\…`），專案裡每個檔都被判成同一類。
- [臨] pytest 的 tmp_path 目錄名本身含 test（`pytest-of-<user>\test_<案名>\`）。用它建真檔去測任何路徑樣式邏輯，結果會被這個上層目錄名污染，可能假綠也可能假紅。測路徑樣式時用虛構的專案根（如 `c:\proj\…`）走樣式判定，檔案存在與否另外查真檔。
- [臨] 發現經過：記憶系統「改了程式要補驗證案例」的查核以 verify_case_globs 判案例檔，拿絕對路徑比對；寫「刪掉案例不算」的測試時用 tmp_path 建檔，程式檔也被判成案例、自己清掉欠帳，閘沒擋才追出來。真實專案放在名字含 test 的目錄下也會中。
- [臨] 同類第二例：部位表 `lib/overview_hub.match_row` 的非錨定子字串命中拿整條絕對路徑比，根層 repo 的根目錄本身叫 `.claude`，表上沒列的根層檔（TECH.md、.gitignore、workflow/config.json）全落到 `.claude/` 列。根目錄本身的名字也是「根以外」，比對要從根以下開始（`p[len(root):]`），反例要含「根目錄名等於某列前綴」。

## 行動

- 寫或審「用樣式判斷路徑類別」的程式：確認比對的是相對專案根的路徑，並加一個「專案根位於含關鍵字的目錄下」的反例
- 測路徑樣式邏輯時不用 tmp_path 的絕對路徑走樣式判定
