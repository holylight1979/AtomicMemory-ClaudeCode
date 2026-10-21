# 切入點識別字樣含常見中文詞會被中文trigger子字串誤中無關卡-等淬鍊才綁卡的列用英數字樣

- Scope: global
- Author: holylight
- Source: 某工作軌 005 交付信（總控台代寫）
- Confidence: [臨]
- Trigger: 切入點識別字樣, 關鍵字退路, trigger 子字串, 誤中無關卡, 登錄表新列, entry_note, SELFSCORE_ASK, CLAUDE_CODE_SESSION_ID, guard log 秒級配對
- Created-at: 2026-10-21

## 知識

- [臨] 切入點的識別字樣若含常見中文詞（例「自檢」），關鍵字退路會被別張卡的中文 trigger 子字串比對誤中，把無關卡送進問句；還沒綁判準卡、等帳本淬鏉的登錄列，識別字樣用英數（例 SELFSCORE_ASK）。
- [臨] Claude Code 2.1.304 給 Bash 工具子行程設了 `CLAUDE_CODE_SESSION_ID`，命令列工具可用它對上 hook 的 session。
- [臨] guard log 的 at 只到秒，問與答同一秒就配不上；答的那筆自己在 payload 帶微秒 at（會覆蓋預設）就配得上；問與答跨標的（問 G8 答 G3）要靠登錄表 responses 的 match 鍵對上才算回應。

## 行動

- 新增登錄列先用英數識別字樣實跑一次看送了哪幾張卡
- 工具寫 guard log 自帶微秒 at
