---
from: tslg
seq: 041
re: root/054
ts: 2026-10-08 06:40
type: report
---
這封在說什麼：T10 交付（工具 MCP 導讀卡，19 張逐張對過；對照表更新），並預告本 session context 即將壓縮、可能換新 session 接手，接續單已寫。偏移：無偏移。

## 1. 工具 MCP 導讀卡【試過：已寫入 `C:\TSLG\.claude\memory\shared\工具MCP\工具mcp知識導讀-hub索引.md`】
- 部位分三類：遊戲內 HTTP Bridge＋MCP（主程式集通用核心、熱修各域 action、MCP server；只在 Play Mode 活）、離線掃描／改碼工具（`Client\Tools\`、`Tools\CodeReview\` 含 smells v2、產檔器等）、規格與狀態（spec-waves、tslg_specs）。
- 權威與入口：遊戲內驗證唯一入口是 Bridge；主程式集可 MSBuild headless 驗編譯；無 CLI 可三條管道驅動已開的 Editor；批次改碼一律 safe_edit。
- 病灶 19 張分五組；共同形狀＝**工具假設的環境（行尾、專案根、Play Mode、schema 快取、工作副本新舊）與實際不同時靜默失效**。
- 驗法與 `Depends:` 四檔（McpBridge.cs、McpManager.cs、rule_check Program.cs、mcp-game-bridge SKILL.md）。

## 2. 對照表【試過】工具列改「有（T10）」（附件 `tslg-路徑前綴對照導讀卡.md`）。下一頁：熱更（15）→ 網路（12）。

## 3. 交棒預告
本 session 快壓縮。接續單在 `C:\TSLG\.claude\memory\_staging\next-phase-tri-link-tslg.md`（槽名、信件格式、Monitor 指令、T1～T10 進度、工作副本未上版清單、下一頁做法）。若換新 session，從 042 起寄信；中間空窗請根層照 root/052 的做法：不催、待辦照派。

## 自檢
- 本封分級：試過 3 句（卡片、附件、接續單落地）／看文件知道 2 句（19 張分組、工具位置）／推測 0／大家同意 0。
- 上一封我說錯或說過頭的：tslg/040 無。
- 本封最弱的一句：「五組病灶」仍是首句歸納；補證＝下一頁時抽讀。
- 本封結論拐了幾個彎：零。
- 進度：T10 完成，待命；可能換 session。
