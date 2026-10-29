# Windows暫存區路徑是8.3短檔名-abspath不展開-路徑比對要用realpath

- Scope: global
- Author: holylight
- Source: C:/Users/holylight/.claude/hooks/handlers/aec_ledger.py（_key）；hooks/verify/verify_session_artifacts.py::test_short_and_long_names_are_the_same_place
- Confidence: [觀]
- Trigger: 8.3 短檔名, 短檔名, HOLYLI~1, gettempdir, TEMP 路徑, abspath, realpath, 路徑比對, is_under_tempdir, scratchpad 路徑, 暫存區判定, 路徑去重
- Created-at: 2026-10-16
- Quote: 「/continue C:\Users\holylight\.claude\memory\_staging\next-phase-hud-1b.md」

## 知識

- [觀] Windows 的 TEMP 環境變數常是 8.3 短檔名（例 C:\Users\ABCDEF~1\AppData\Local\Temp），tempfile.gettempdir() 原樣回傳；os.path.abspath／normpath 不展開短檔名，os.path.realpath 會展開成長檔名（路徑尾段不存在也會展開已存在的前段）。git worktree list 回報的也是長檔名。
- [觀] 後果：拿 abspath 比「在不在暫存區之下」或做去重鍵，同一個地方的短／長兩種寫法比不上——AI 常用長檔名寫進 scratchpad，就被判成「專案外」；工作樹路徑對不上 git 回報的清單就被當成不在了。實測一份產出物帳本約 63 項暫存檔因此被誤分類。
- [觀] pytest 的 tmp_path 已經 resolve 成長檔名，測試裡兩邊都是長檔名，這個錯在測試照不出來；要測得用 ctypes GetShortPathNameW 取短名（磁碟沒開 8.3 名就 skip）。
- [觀] Node 的 os.tmpdir() 也回 8.3 短名，py 端已 realpath 的路徑是長名，兩邊字串直接比不相等；js 測試斷言只比檔名，或兩邊都先 realpath。

## 行動

- Windows 上做路徑比對、前綴判斷、去重鍵，一律 os.path.normcase(os.path.realpath(p))，不用 abspath
- 測路徑比對時刻意餵一個 8.3 短名版本（GetShortPathNameW）
