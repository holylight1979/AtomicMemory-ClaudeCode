# 常駐每幀回呼vs按需短命協程-判準與mec實證

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 常駐 Update, 每幀回呼, 每幀輪詢, Tick 浪費, 按需協程, 短命協程, 協程自滅, Timing.RunCoroutine, MEC, WaitForSeconds 成本, RealtimeUpdate, CoroutineHandle, 過渡, 淡入淡出, 等播完, Unity 無播完事件
- Created-at: 2026-09-18
- Related: hotfix-migration-rules, feedback-等秒數是次等方法-固定模式資訊要事件驅動主動處理

## 知識

- [臨] 使用者定調（2026-09-18）：常駐每幀回呼（Update / Tick 註冊）只留給「真的每幀都有事」的系統。物件大多時間閒著或穩定狀態、只在短段「過渡」有事（淡入淡出、接力、等某事結束後通知）→改成事件發生時才開短命協程、做完自滅。把 N 條常駐收成 1 條 Tick 仍是輪詢，使用者視為浪費、不算解。
- [臨] 判準一句話：協程只在「有事必須在『之後』發生」時存在；呼叫當下做得完的直接做。設計時先列出「哪幾種過渡」，超出清單的協程就是 bug。
- [臨] 配套實作型：一物件一個 handle 欄位，新過渡先 kill 舊的再啟（同時最多一條，交錯情境免寫特例）；回呼「只叫一次」靠叫完即清委派，被中斷的協程走不到尾端時由中斷路徑補叫；Dispose 必 kill。
- [臨] MEC 實證（2026-09-18 讀 Timing.cs）：睡眠中的協程每幀只做一次 `localTime < Current` float 比較、不呼叫 MoveNext → `WaitForSeconds(精確秒)` 睡到底成本趨近零；Pro 版有 `Segment.RealtimeUpdate`（deltaTime = unscaledDeltaTime，適合跟 AudioSource 這類不吃 timeScale 的東西同步）；`KillCoroutines(CoroutineHandle)` / `handle.IsValid` 可精準 kill，不需字串 tag；協程第一次 MoveNext 在 RunCoroutine 當下同步執行，讀 DeltaTime 前先 yield 一幀才是該段的值。
- [臨] Unity 沒有 AudioSource「播完」事件：等播完用 clip.length − time 算剩餘秒睡到底，醒來若仍 isPlaying（App 曾切背景、音訊暫停過）就再睡一次。這是用已知長度算的精確等待，不是猜的 timeout。

## 行動

- 看到 Reg*Update / Tick 註冊先問：這物件是不是大部分時間閒著？是 → 列出過渡清單、改短命協程
- 等固定時長的事用 WaitForSeconds(精確值) 睡到底、醒來確認狀態，不寫每幀 poll
- 提案時把「哪些情境仍會生協程、活多久」列成表給使用者看，預設參數（如 fade > 0）會讓「零協程」不成立要明講
