# 無頭實跑證明正式環境沒被動到不能只比前後相同-期間可能有別的並行工作寫入-要逐檔歸屬看卡片來源欄並grep自己的session-id

- Scope: global
- Author: holylight
- Source: 2026-10-23 Bash 寫入補算改檔實作
- Confidence: [臨]
- Trigger: live 未動, 正式環境沒被動到, 無頭實跑, claude -p 驗收, 前後比對, 並行寫入, 逐檔歸屬, session id grep
- Created-at: 2026-10-23
- Related: 無頭探針驗skill行為-claude-p加setting-sources-project與strict-mcp-config不載使用者層hook與mcp

## 知識

- [臨] 無頭實跑要證明正式環境沒被動到，不能只比實跑前後一不一樣：實跑期間正式環境可能有別的並行工作在寫（實例：多了 8 張別處寫的卡），前後不同不等於受測的寫了。
- [臨] 要逐檔歸屬：多出來的卡看它的 Source 欄是哪個工作寫的；再拿受測 session 自己的 session id 去 grep 正式環境的 workflow、Logs、memory，沒出現才算沒動。

## 行動

- 證「正式環境未動」：列出前後差異的每個檔、逐一判是誰寫的，再 grep 受測 session id；不拿「前後相同」當唯一證據


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-29 | 退役移入 _distant/：v6 開發期專用（無頭驗收實跑怎麼證明 live 沒被動到），開發結束封存；一般版本在「證明repo沒被自己動過…」那張 | memory-audit --delete |
