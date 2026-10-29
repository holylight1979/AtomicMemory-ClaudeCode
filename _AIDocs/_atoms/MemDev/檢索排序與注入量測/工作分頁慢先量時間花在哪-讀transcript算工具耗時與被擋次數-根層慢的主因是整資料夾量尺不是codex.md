# 工作分頁慢先量時間花在哪-讀transcript算工具耗時與被擋次數-根層慢的主因是整資料夾量尺不是codex

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 處理速度很慢, 為什麼這麼慢, 分頁好慢, 量尺太久, tools/verify 12 分鐘, MeasureGate 太重, 時間花在哪
- Created-at: 2026-10-14
- Source: session:242d1f2a#7ed3489d 2026-10-14
- Quote: 「skill-console 修正的處理速度超級慢! 為什麼呢? 是又被機制啟動Codex亂檢查又失去目標校準能力了嗎 ?」

## 知識

- [臨] 使用者問某工作分頁為何超慢、是不是 Codex 亂查或目標校準失靈。實測（讀該 session transcript，算工具起訖時間）：Codex 0 次、need_goal 22 次合計約 45 秒，測試合計約 40 分鐘。主因是部位表的量尺是整個資料夾：tools 部位＝pytest tools/verify（約 12 分鐘），lib 部位＝pytest lib/verify（約 2 分鐘）；改一行預設值或一行註解，MeasureGate 就要跑整把尺。派工時多碰一個部位（連註解）就多一把尺。工具：workflow/inbox/_console/session_timeline.py.txt <transcript>，印慢呼叫、工具耗時、被擋次數、Codex 次數。

## 行動

- 使用者說慢：先跑 session_timeline 量，再下結論，不猜 Codex 或目標
- 派工時只列必要的檔；不為一行註解碰另一個有量尺的部位
