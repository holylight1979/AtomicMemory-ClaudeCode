# pytest內subprocess抓子行程輸出遇cp950中文-reader-thread解碼炸掉-stdout變None-子行程要帶PYTHONUTF8並errors-replace-python-I會忽略PYTHONIOENCODING

- Scope: global
- Author: holylight
- Source: session 8f368a10 2026-10-13（自驗腳本盲陷阱檢查）
- Confidence: [臨]
- Trigger: subprocess capture_output, UnicodeDecodeError 0xb8, _readerthread 警告, stdout None, PYTHONUTF8, PYTHONIOENCODING, python -I, cp950, 子行程中文輸出
- Created-at: 2026-10-13

## 知識

- [臨] Windows 上父程式用 subprocess.run(..., capture_output=True, text=True, encoding="utf-8") 抓子 Python 行程的中文輸出：子行程 stdout 預設 cp950，父端 reader thread 解碼炸 UnicodeDecodeError（0xb8）；pytest 只印 PytestUnhandledThreadExceptionWarning，結果 result.stdout 變 None，後面斷言出現「argument of type 'NoneType' is not iterable」這種離題的 TypeError。
- [臨] 修法：子行程 env 帶 PYTHONUTF8=1（dict(os.environ, PYTHONUTF8="1")），父端加 errors="replace" 保底。
- [臨] 父程式本身用 python -I 跑時，-I 會忽略所有 PYTHON* 環境變數，外層 export PYTHONIOENCODING=utf-8 無效、終端中文仍亂碼；改用 python -X utf8。

## 行動

- Windows 抓子 Python 行程中文輸出：env 加 PYTHONUTF8=1、encoding utf-8 + errors replace
- 看到 stdout 為 None 的 TypeError 先往上找 reader thread 的解碼警告
- 需要 utf-8 輸出時用 python -X utf8，不靠 -I 配環境變數
