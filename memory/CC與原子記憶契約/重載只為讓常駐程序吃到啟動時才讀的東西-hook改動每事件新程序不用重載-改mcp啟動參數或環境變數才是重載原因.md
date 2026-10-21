# 重載只為讓常駐程序吃到啟動時才讀的東西-hook改動每事件新程序不用重載-改mcp啟動參數或環境變數才是重載原因

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/LLM切入點自評-2026-10-21.md E17
- Confidence: [臨]
- Trigger: 重載原因, RELOAD_ADVICE_ALREADY_LOADED, Reload Window, 重新載入視窗, ReloadAdvice, 已載入磁碟上最新的程式
- Created-at: 2026-10-21
- Quote: 「A」

## 知識

- [臨] 判準看「誰是常駐程序、它啟動時讀了什麼」：hooks/*.py 每個事件起新程序，改完下一個事件就生效，永遠不是重載理由；MCP server 的程式碼若閘已查到服務載入最新版，也不必再重載。
- [臨] 真的要重載：改了只在服務啟動時讀一次的東西——MCP 啟動設定（.mcp.json 的 command／args／env）、服務啟動時讀一次的設定檔；這時程式版本雖新，跑著的程序仍帶舊參數，保留那句並寫「重載原因：改了 <檔與欄位>，服務是用舊值啟動的」。
- [臨] 反例：寫「重載原因：改了某支 hooks/*.py」是錯的（hook 不需重載）；隨口叫人重載還會打斷並行 session、重編 claude-xx 通訊名。

## 行動

- 先列這次改的檔，逐個問「它是不是被常駐程序在啟動時讀」；全否 → 拿掉那句
- 有 → 保留並寫「重載原因：改了 <檔與欄位>，服務是用舊值啟動的」
