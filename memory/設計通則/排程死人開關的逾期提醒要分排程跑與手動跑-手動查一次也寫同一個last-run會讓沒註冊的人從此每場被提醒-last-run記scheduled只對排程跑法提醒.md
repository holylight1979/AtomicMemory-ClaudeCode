# 排程死人開關的逾期提醒要分排程跑與手動跑-手動查一次也寫同一個last-run會讓沒註冊的人從此每場被提醒-last-run記scheduled只對排程跑法提醒

- Scope: global
- Author: holylight
- Source: GitLab ClaudeCode-AtomMemory !14 合併時補的一刀 d09f9640（hooks/handlers/session_start._usage_watch_advisory）；審查紀錄 _AIDocs/DevHistory/檢視與審查/同伴MR審查-2026-11-03.md
- Confidence: [臨]
- Trigger: 死人開關, dead man switch, 逾期提醒, last-run, 排程沒跑, SessionStart 提醒, advisory, 每場都提醒, 手動跑, stale, token 稅, 雞肋
- Created-at: 2026-11-03
- Related: feedback-審同伴mr的收錄判準-對協作真有幫助才收-雞肋浪費token不收-專案層慣例不進核心-部分取用要寫清楚取捨
- Quote: 「收割，我希望是從他們推的MR中，汲取此電腦所用LLM所欠缺的知識、經驗」

## 知識

- [臨] 「排程逾 N 小時沒更新 last-run 就提醒去註冊排程」這種死人開關，若 last-run 是每次執行都寫（手動查一次也寫），就會把沒打算裝排程的人變成永久被提醒：手動試跑一次，N 小時後每場 session 多一行叫他去 --register，永遠不停。這正是「沒用還多耗 token、帶歪」那型雞肋。
- [臨] 做法：last-run 多記 `scheduled`（只有排程用的參數組合，例如帶 --notify，才寫 true），逾期提醒只看 scheduled=true；查詢失敗、通知失敗這類提醒不分手動排程照浮出（那是功能壞了，和有沒有裝排程無關）。既有排程不用重註冊。
- [臨] 審同伴的「開場提醒」類改動，固定問：缺檔時回不回空？只手動跑過一次之後會怎樣？提醒會不會每場重複？——提醒設計者通常只想到「排程死了要知道」，沒想到「根本沒裝」的人。

## 行動

- 寫逾期提醒前先分：這個紀錄檔是不是手動跑也會寫？是就加排程標記，提醒只看標記
- 審 SessionStart／開場提醒：缺檔靜默、手動一次不觸發、每場不重複三題都過才收
