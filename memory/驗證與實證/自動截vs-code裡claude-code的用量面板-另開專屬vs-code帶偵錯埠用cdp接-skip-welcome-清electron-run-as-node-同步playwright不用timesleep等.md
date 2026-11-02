# 自動截VS Code裡Claude Code的用量面板-另開專屬VS Code帶偵錯埠用CDP接-skip-welcome-清ELECTRON_RUN_AS_NODE-同步Playwright不用time.sleep等

- Scope: global
- Author: holylight
- Source: session:247954c1 2026-11-02; tools/usage-snapshot/usage_snapshot.py
- Confidence: [臨]
- Trigger: VS Code 自動化, Claude Code 用量面板, Account & Usage, /usage, connect_over_cdp, remote-debugging-port, user-data-dir, ELECTRON_RUN_AS_NODE, skip-welcome, webview frame, 用量截圖, Electron CDP
- Created-at: 2026-11-02
- Related: 自動化開claude-ai用量頁-headless-edge撞cloudflare人類驗證-日常chrome-profile被鎖不可借用-改專屬chrome-profile一次登入, electron-uia-automation
- Quote: 「再嘗試用vs code.. 不要幾次沒成功就退了」

## 知識

- [臨] 做法：Code.exe 加 `--user-data-dir=<專屬>`（跟日常那個分開，才能另起一個實例）＋`--remote-debugging-port`，Playwright `connect_over_cdp` 接上；擴充套件的 webview 是 workbench 頁的子框架（url 帶 extensionId），框架內的元素可以直接操作和截圖。登入沿用 ~/.claude 的憑證，不用另外登入。
- [臨] 坑：從 VS Code 終端機或 CC 裡跑時，環境帶著 `ELECTRON_RUN_AS_NODE=1`，Code.exe 會被當成 Node 執行（stderr 出現 bad option）→ 啟動前拿掉它和 `VSCODE_*`。新的設定資料夾會跳出「登入 Copilot」引導視窗擋住整個畫面 → 加 `--skip-welcome`。
- [臨] 坑：同步版 Playwright 只在呼叫它的 API 時才處理事件；用 time.sleep 輪詢 `page.frames`，新開的框架永遠不會出現 → 改用 `page.wait_for_timeout`。視窗被遮住時 click 會卡在等畫面穩定 → 加 `--disable-features=CalculateNativeWinOcclusion` 這類參數，輸入框用 focus 不用 click。
- [臨] Claude Code 擴充套件的 Account & Usage 面板：在分頁輸入框打 `/usage` 再按 Enter 叫出；預設顯示 Day，要點 Week；面板太高會被切掉 → `set_viewport_size` 撐高，不要靠最大化（受螢幕高度限制）。開分頁會起一個 CLI 程序，開場 hook 照跑。

## 行動

- 要自動化 VS Code 或擴充套件畫面：另開專屬實例＋偵錯埠＋CDP，不用 UIA 或鍵盤模擬
- 啟動前清 ELECTRON_RUN_AS_NODE，加 --skip-welcome
- 同步 Playwright 輪詢用 page.wait_for_timeout
