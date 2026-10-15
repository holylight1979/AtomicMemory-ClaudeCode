# Git-Bash傳斜線開頭參數給Windows原生程式會被轉成路徑-例claude-p的slash指令-MSYS_NO_PATHCONV只能加在那一次呼叫-全域export會讓python讀不到斜線c路徑

- Scope: global
- Author: holylight
- Source: 調度總控台 q5 續接 smoke 實踩 2026-10-14
- Confidence: [臨]
- Trigger: MSYS_NO_PATHCONV, Git Bash 路徑轉換, claude -p, slash 指令被轉成路徑, C:/Program Files/Git, /continue, headless claude, MSYS2_ARG_CONV_EXCL
- Created-at: 2026-10-15
- Related: bash-呼叫-msbuild-用-dash-參數
- Quote: 「確認看看還有什麼沒做或者沒收割的，要關session了」

## 知識

- [臨] 實踩：在 Git Bash 用 `claude.exe -p "/continue"` 跑無介面 session，參數 `/continue` 被 MSYS 當成 POSIX 路徑轉成 `C:/Program Files/Git/continue`，claude 收到的是一個路徑字串、不是 slash 指令，不報錯也不執行指令。句中的 /handoff（不在參數開頭）不受影響。
- [臨] 修法是只在那一次呼叫前加 `MSYS_NO_PATHCONV=1`（或寫成 `//continue`）。不要在腳本裡全域 export：同一支腳本後面用 Windows 版 python 讀 `/c/Users/...` 這種路徑時就不再被轉成 `C:/...`，整堆 FileNotFoundError。

## 行動

- 在 Git Bash 叫原生程式、參數以斜線開頭：只對那一次呼叫加 MSYS_NO_PATHCONV=1，別全域 export
- 無介面 session 結果怪：先看它收到的參數是不是被轉成了路徑
