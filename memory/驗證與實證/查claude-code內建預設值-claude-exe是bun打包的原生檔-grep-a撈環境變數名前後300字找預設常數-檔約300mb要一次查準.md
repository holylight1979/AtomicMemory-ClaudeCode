# 查claude-code內建預設值-claude-exe是bun打包的原生檔-grep-a撈環境變數名前後300字找預設常數-檔約300MB要一次查準

- Scope: global
- Author: holylight
- Source: 2026-10-23 第二意見等待修補實測
- Confidence: [臨]
- Trigger: claude.exe 預設值, Claude Code 內建預設, grep -a, bun 打包, minified, 環境變數預設值, 執行檔實查, 原生檔撈原始碼
- Created-at: 2026-10-22
- Related: claude-code的mcp工具呼叫上限約27小時但互動模式滿120秒自動轉背景-要等長工作的mcp工具每次等待短於120秒分段等

## 知識

- [臨] claude.exe 是 bun 打包的原生執行檔，裡面帶著 minified 的程式碼；`grep -a -o '.\{300\}<環境變數名>.\{300\}' claude.exe` 撈得到那個變數附近的程式碼與預設常數。
- [臨] 預設值常寫成「環境變數不在就用某常數」，例 `??a.MCP_TOOL_TIMEOUT??Hr`，再 grep `Hr=` 找出常數值。
- [臨] 檔案約 300MB，一次掃超過 2 分鐘會被轉背景；要先想好要撈的字串一次查準，不要反覆小查。

## 行動

- 查 Claude Code 某設定的內建預設：grep -a -o 撈環境變數名前後各 300 字，再 grep 常數名找值
