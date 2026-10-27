# PYTEST_ADDOPTS與PYTHONOPTIMIZE會從環境縮小測試範圍-判斷要照執行順序算每段程式的有效值

- Scope: global
- Author: holylight
- Source: session:ec069e59 2026-10-13
- Confidence: [臨]
- Trigger: PYTEST_ADDOPTS, PYTHONOPTIMIZE, 環境變數縮小範圍, 整體驗證, pytest 子集, 有效環境, env 前綴, run_verify 自寫收據
- Created-at: 2026-10-13

## 知識

- [臨] `PYTEST_ADDOPTS='-k x' pytest -q` 等於命令列多帶 `-k`／路徑，跑的是子集卻照樣全綠；`PYTHONOPTIMIZE=1` 等於 `-O`。只看命令列判「整體驗證／對上量尺」會被這兩個環境變數騙過；被呼叫的程式（例如 run_verify 跑的 pytest 子行程）也會繼承它們。
- [臨] 判斷時只算「真的進子程式環境、值非空」的設定：bash 行內前綴（只給它接的那段）、`export`、單獨一段的 `X=值`（若變數本來就在繼承環境裡會傳下去，收據看不出來，fail-closed 照算）；PowerShell 只有 `$env:X=`，`$X`、`$global:X` 是 PowerShell 變數不進子程式；沒加引號的 `$null` 算空，`'$null'`、`' '` 都是值，值不修剪。
- [臨] 要照執行順序算每一段程式啟動當下的有效值：後面的指定蓋前面的（`$env:X='-k x'; $env:X=''` 到程式時已清空，照算）；`||` 右邊與管線裡的指定不一定生效，前置設定彼此只准 `;`／`&&` 串。量尺比對逐段連值比（表上帶同名設定時要同值），名稱照受執行平台比（Windows 不分大小寫，bash 的 `pytest_addopts=` 在 Windows Python 就是它）。
- [臨] 每一條採認路徑都要接同一個判斷（一般證據、整體驗證、精確量尺、根層 worktree 的 pytest DONE、程式自寫的收據）；自寫收據要記下自己行程環境裡這些變數，沒記的舊收據一律不算。平台旗標的真實預設要有不經 monkeypatch 的測試守著，否則被改成永遠關閉時其他測試照綠。


## 行動

- 寫「這次是不是全量／是不是表上那組選項」的判斷時，把環境注入選項的變數列入，照執行順序算有效值
- 加一案不經 monkeypatch 的平台旗標斷言
