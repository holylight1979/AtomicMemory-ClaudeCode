# bash 呼叫 MSBuild 用 dash 參數

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: msbuild, dotnet build, MSYS2, git bash, MSB1008, 編譯參數, 斜線參數, dash flag, bash 編譯, /t:Build
- Created-at: 2026-06-17
- Related: toolchain

## 知識

- [觀] Windows MSYS2 / Git-bash 內呼叫 MSBuild.exe 或 dotnet 時，`/t:Build` `/p:Configuration=Debug` `/m` 這類斜線參數會被 POSIX path 轉換吃掉（`/t:Build`→`t:Build`、`/m`→`M:/`）→ 報 `MSBUILD : error MSB1008: 只能指定一個專案`。**改用 dash 形式 `-t:Build -p:Configuration=Debug -v:m -nologo` 即正常**（或設 `MSYS2_ARG_CONV_EXCL='*'`）。
- [觀] VS2022 的 MSBuild 不在 bash PATH 時，用全路徑：`/c/Program Files/Microsoft Visual Studio/2022/Community/MSBuild/Current/Bin/amd64/MSBuild.exe`。
- [觀] Stop hook 的「fix-escalation / 同檔多次修改」可能誤報：多階段 surgical edits（每階段先編譯綠燈再 commit）不是重試迴圈。判定失敗應看每次編輯是否伴隨 build error / retry，而非單看同檔編輯次數。

## 行動

- bash 內跑 .NET 編譯一律用 dash flags（`-t:` `-p:` `-v:`），不要用 `/`
- msbuild 不在 PATH → 用 VS2022 amd64 全路徑呼叫
- 評估失敗訊號：計畫性連續編輯（無 build error、無回退）不計為 escalation
