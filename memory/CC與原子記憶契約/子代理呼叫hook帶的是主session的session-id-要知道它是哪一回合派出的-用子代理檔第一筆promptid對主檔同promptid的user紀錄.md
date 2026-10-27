# 子代理呼叫hook帶的是主session的session_id-要知道它是哪一回合派出的-用子代理檔第一筆promptId對主檔同promptId的user紀錄

- Scope: global
- Author: holylight
- Source: 分支 subagent-quote-fix 46fac1a0
- Confidence: [臨]
- Trigger: 子代理 hook, agent_id, session_id 共用, promptId, 派出回合, 子代理寫卡, 背景子代理, 本回合使用者原話, subagents/agent-
- Created-at: 2026-10-27
- Related: 子代理的對話紀錄是獨立檔-讀transcript的hook閘要分主檔與子代理檔-使用者原話只認主檔, 從transcript回找使用者原話要停在開回合的紀錄-越過同伴訊息與背景通知會走到開工句, 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞

## 知識

- [臨]（實查本機）Claude Code 子代理呼叫 hook 時，input 的 session_id 是主 session 的（另帶 agent_id 才分得出是子代理）；按 session_id 存的狀態（例：「本回合使用者原話」），子代理讀到的是主 session 此刻的那一份。
- [臨] 拿那份狀態當子代理的觸發原話會配錯：背景子代理還在跑時，主 session 可能已經換到下一回合；或派它的那一回合是同伴訊息、背景通知開的續跑回合，狀態裡的原話沿用的是前一則真人訊息。
- [臨] 對法：子代理 transcript（`<session_id>/subagents/agent-<agent_id>.jsonl`）第一筆紀錄的 promptId，對主 transcript 裡第一筆同 promptId 的 type=user 紀錄＝開那一回合的訊息（本機 238 份子代理檔全對得上）。那筆是真人訊息才算使用者原話；是同伴訊息、背景通知、或對不到 → 當作沒有原話。子代理檔裡的 user 訊息是主 session 的 AI 寫給它的任務，不是使用者的。

## 行動

- hook 要用「使用者這回合說了什麼」時先看 input 有沒有 agent_id：有就用 promptId 對回派出的那一回合，不讀按 session_id 存的狀態
- 對到的開回合紀錄要再判一次是不是真人訊息，不是就不取
