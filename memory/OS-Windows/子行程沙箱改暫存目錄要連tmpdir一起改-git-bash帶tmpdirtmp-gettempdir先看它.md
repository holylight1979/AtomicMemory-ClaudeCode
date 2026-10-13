# 子行程沙箱改暫存目錄要連TMPDIR一起改-Git Bash帶TMPDIR=/tmp-gettempdir先看它

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: TMPDIR, tempfile.gettempdir, 暫存目錄, 沙箱, 子行程環境, Git Bash, 探針隔離, TEMP TMP, scratchpad
- Created-at: 2026-10-13
- Related: windows路徑包含判斷兩側要統一表示-先去長路徑前綴再normpath-轉長路徑後再normpath
- Source: session:2a7705d4 2026-10-13

## 知識

- [臨] Python `tempfile.gettempdir()` 依序看 TMPDIR、TEMP、TMP。Git Bash 預設帶 `TMPDIR=/tmp`，啟動 Windows 版 Python 時被轉成真正的 `%TEMP%`（8.3 短路徑形式）。子行程沙箱只覆寫 TEMP／TMP，子行程拿到的暫存目錄仍是真 %TEMP%，不是沙箱。
- [臨] 實踩：驗證探針的沙箱放在 Claude Code 的 scratchpad（就在 %TEMP% 底下），受測 hook 判「改檔在不在暫存目錄」時把沙箱裡所有改檔都當暫存、不記帳，整輪情境結果全是假的。被測程式改成把短路徑轉長路徑後才暴露；之前短、長路徑對不上，反而碰巧沒事。
- [臨] 驗法：在帶沙箱環境的子行程印 `tempfile.gettempdir()`，要等於沙箱的暫存目錄；外層先故意設一個別的 TMPDIR 再測一次。

## 行動

- 寫沙箱或隔離環境：TEMP、TMP、TMPDIR 三個一起指沙箱
- 沙箱放在 %TEMP% 底下時，先確認受測程式的暫存判斷不會把整個沙箱當暫存
- 用子行程印 gettempdir() 驗隔離有沒有真的生效
