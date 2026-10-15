# feedback-開工句交出後又有更新-先查下一個session是否已開工-已開工就用SendMessage直接轉更新-不要叫使用者換開工句

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 開工句更新, 下一階段 session, 新版開工句, 轉給工作 session, 已經開工, ListAgents, SendMessage
- Created-at: 2026-10-15
- Source: session:bbc75a05#7a3f06d3 2026-10-15
- Quote: 「新session早就已經開工了。 你用 AgentList 以及 SendMessage 直接跟他溝通看看.. 看他進展到哪、應該根據最新 改什麼」

## 知識

- [臨] 使用者原話：「新session早就已經開工了。你用 AgentList 以及 SendMessage 直接跟他溝通看看.. 看他進展到哪、應該根據最新 改什麼」。背景：我交出下一階段開工句後又被指正、補了三個切入點，就請使用者「用更新版開工句開新 session」，沒先查那個 session 其實早就開工。
- [臨] 做法：交出開工句後內容有更新 → 先 ListAgents 看下一階段的 session 在不在；在就用 SendMessage 直接轉更新內容（附來源原話），並問它做到哪、已提交什麼、是不是舊版開工句；不在才給新版開工句。要使用者自己貼新版是把能自動辦的事推給人（G16）。

## 行動

- 開工句交出後有更新：先 ListAgents，已開工就 SendMessage 轉更新並問進度（notify_when_idle），不要叫使用者換開工句
