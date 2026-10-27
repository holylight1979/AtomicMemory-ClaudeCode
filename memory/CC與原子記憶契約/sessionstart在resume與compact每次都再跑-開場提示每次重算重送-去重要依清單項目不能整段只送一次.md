# sessionstart在resume與compact每次都再跑-開場提示每次重算重送-去重要依清單項目不能整段只送一次

- Scope: global
- Author: holylight
- Source: merge 4f3dc85a（注入噪音減量）2026-10-27
- Confidence: [臨]
- Trigger: SessionStart, SessionStart resume, SessionStart compact, 開場提示重送, 開場去重, 重複注入, 依項目去重, 中段開場, 整段只送一次
- Created-at: 2026-10-27
- Related: claude-code的resume接續後前面回合hook注入的內容仍在context-只有壓縮才丟-判送過沒要跟壓縮時間比不能因resume重置

## 知識

- [臨] Claude Code 的 SessionStart hook 在 resume、compact 每次都會再跑，開場提示每次重算重送；一個長 session 會收到好幾份開場。
- [臨] 同一 session 中段的開場清單（例：覆轍／待辦類清單）常帶新信號，去重要依清單項目：送過的項目不再送、新項照送；整段只送一次會吞掉新信號。

## 行動

- 寫 SessionStart 注入：先假設它在同一 session 會跑好幾次，用 source 分 startup／resume／compact
- 清單類開場段以項目為單位去重，重置條件綁壓縮
