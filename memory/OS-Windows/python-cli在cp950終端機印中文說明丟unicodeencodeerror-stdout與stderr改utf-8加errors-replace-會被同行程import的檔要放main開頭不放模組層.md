# python-cli在cp950終端機印中文說明丟UnicodeEncodeError-stdout與stderr改utf-8加errors-replace-會被同行程import的檔要放main開頭不放模組層

- Scope: global
- Author: holylight
- Source: 2026-10-23 C# 閱讀路徑 svn 支援實作
- Confidence: [臨]
- Trigger: UnicodeEncodeError, cp950 --help, argparse 中文說明, sys.stdout.reconfigure, cp950 終端機印中文, errors=replace
- Created-at: 2026-10-23
- Related: pytest內subprocess抓子行程輸出遇cp950中文-reader-thread解碼炸掉-stdout變none-子行程要帶pythonutf8並errors-replace-python-i會忽略pythonioencoding

## 知識

- [臨] Python CLI 在 cp950 終端機印 argparse 說明或報表，只要含 cp950 沒有的字（例：≥）就丟 UnicodeEncodeError 整支停掉。修法：對 stdout、stderr 各做 `stream.reconfigure(encoding="utf-8", errors="replace")`（先用 hasattr 確認有 reconfigure）。
- [臨] 那支檔若也會被別的程式在同一個行程 import（hook 背景工作、pytest），這行放 main() 開頭、不放模組層；放模組層會在 import 時把呼叫端行程的 stdout 一起改掉。

## 行動

- 寫或修會印中文的 Python CLI：在 main() 開頭 reconfigure stdout/stderr 為 utf-8 + errors=replace
- 驗證：在 cp950 終端機實跑 --help
