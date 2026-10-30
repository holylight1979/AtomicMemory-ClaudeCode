# CC的VSCode擴充回覆內檔案連結相對session-cwd解析-井號片段非數字找標題-路徑內的井號與百分號要編碼

- Scope: global
- Author: holylight
- Source: ~/.vscode/extensions/anthropic.claude-code-2.1.304-win32-x64（webview/index.js 的 _v、_G1、M35；extension.js 的 openFile、ae1、P81）；commit 6d9a466c
- Confidence: [臨]
- Trigger: VS Code 擴充, markdown 連結, 檔案連結, 可點連結, 錨點, heading anchor, #L12, 相對路徑連結, 回覆裡的連結點不開, CLAUDE_CODE_ENTRYPOINT, claude-vscode
- Created-at: 2026-10-22
- Related: claude-p無頭跑會被hook判成無法互動-問人類流程驗不到-預設claude-code-entrypointclaude-vscode可保留但-p沒有askuserquestion

## 知識

- [臨]（讀擴充 2.1.304 webview／extension.js 並抽函式實跑）回覆裡的 markdown 連結 `[字](路徑#片段)`：片段是數字（`#12`、`#L12-20`）→ 跳行號；片段非數字 → 當標題找：標題文字先去掉 `[x](y)` 連結、轉小寫、空白換 `-`、去標點後整串比對（`## [R1](卡)` 的錨點是 `r1`；`<a id>` 不認、`## R1 一句話` 會變成 `r1-一句話`）。
- [臨] 相對路徑以 session 的 cwd 為基準 join（第一個工作區資料夾被換成 cwd），`../` 照常解析；Windows 絕對路徑 `C:/…` 另有專門處理也點得開。開檔前會 decodeURIComponent 並拒含 `:` 或 `\\` 的相對路徑，所以路徑一律用 `/`；路徑裡有字面 `#` 會解析失敗（點了沒反應）、字面 `%20` 會被解成空白——兩者要編成 `%23`、`%25`；空白、括號編成 `%20`、`%28`、`%29` 免得切斷 markdown 連結。中文不必編碼。
- [臨] hook 判「這則回覆會在 VS Code 顯示」用繼承來的 CLAUDE_CODE_ENTRYPOINT：claude-vscode＝VS Code；cli＝終端機（含背景 job）；sdk-*＝claude -p／SDK 無頭。hook 的 stdin／stdout 是管線，TTY 判斷沒用。

## 行動

- 要在回覆或 hook 注入文字裡放可點的檔案連結：路徑相對 hook 收到的 cwd、用 `/`，錨點用只寫代號的標題，路徑裡的 空白 ( ) % # 先編碼
- 連結點不開先查片段是不是被當行號、路徑裡有沒有字面 # 或 %、標題 slug 對不對
