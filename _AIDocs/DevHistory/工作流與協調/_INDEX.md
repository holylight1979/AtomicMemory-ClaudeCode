# 工作流與協調 — 多 session／多 agent 協作與 session 管理

> 多個 Claude 或 Codex 同時工作時怎麼分工、怎麼避免互踩，以及 session 本身生命週期的設計紀錄。

| 檔 | 一句話 |
|---|---|
| `session-mgmt.md` | SessionStart 去重 + 孤兒 state 清理 + merge self-heal（2026-04） |
| `multi-agent-cleanup-protocol.md` | 多大師協作流程通用版：CC ≥ Codex 席次、防 Codex 幻覺、Windows sandbox 修復、收尾 checklist |
| `session-coordination-bus.md` | 跨 session 衝突預警計畫（2026-07）：查證 CC 原生無跨 session 管道、七席共議、probe 實測、Stage 2/3 延後條件 |
| `pan-deny-judgement-2026-08-06.md` | PAN 動手前預告閘門 warn→deny 終局判讀：四門檻逐筆證據，漏偵率過高故不翻（閘門後來整個拆除） |
