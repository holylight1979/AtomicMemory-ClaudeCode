# 切入點識別字樣含常見中文詞會被中文trigger子字串誤中無關卡-等淬鍊才綁卡的列用英數字樣

- Scope: global
- Author: holylight
- Source: commit:a71121dc 2026-10-21（原出處已隨工作信箱清理）
- Confidence: [臨]
- Trigger: 切入點識別字樣, 關鍵字退路, trigger 子字串, 誤中無關卡, 登錄表新列, entry_note, SELFSCORE_ASK, CLAUDE_CODE_SESSION_ID, guard log 秒級配對
- Created-at: 2026-10-21
- Quote: 「我今天要下班離開電腦前了、明早才會進公司。 我有另外開一個空Fable Session，title 我也改了名字叫 `(備)v6總控台-人+調`，如果此session的context又快用完(超過85%)了，你再自己去貼session prompt來繼承你； Codex的檢核意見，你要提醒工作session審過 (別呆呆的就又掉進飄移坑)； **用經驗、朝目標、避免飄、不空等、不浪費**。」

## 知識

- [臨] 切入點的識別字樣若含常見中文詞（例「自檢」），關鍵字退路會被別張卡的中文 trigger 子字串比對誤中，把無關卡送進問句；還沒綁判準卡、等帳本淬鍊的登錄列，識別字樣用英數（例 SELFSCORE_ASK）。
- [臨] Claude Code 2.1.304 給 Bash 工具子行程設了 `CLAUDE_CODE_SESSION_ID`，命令列工具可用它對上 hook 的 session。
- [臨] guard log 的 at 只到秒，問與答同一秒就配不上；答的那筆自己在 payload 帶微秒 at（會覆蓋預設）就配得上；問與答跨標的（問 G8 答 G3）要靠登錄表 responses 的 match 鍵對上才算回應。

## 行動

- 新增登錄列先用英數識別字樣實跑一次看送了哪幾張卡
- 工具寫 guard log 自帶微秒 at


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-30 | 退役移入 _distant/：描述的機制（切入點登錄表的識別字樣與 entry_note 關鍵字退路送卡、問答配對）已從寫碼守門拔除；CLAUDE_CODE_SESSION_ID 一事另有無頭探針卡記載 | memory-audit --delete |
