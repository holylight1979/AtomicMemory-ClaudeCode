# 驗證優先：診斷前禁止規劃

- Scope: global
- Confidence: [固]
- Last-used: 2026-03-22
- Confirmations: 3

## 知識

- [固] 大型/第三方專案診斷，必須先 100% 驗證根因再規劃，不可靠假設展開計畫
- [固] 優先查 runtime 狀態（process age、temp logs、route registration），非 config 或程式碼
- [固] 使用者的質疑是重要信號 — 他們比 AI 更了解自己的環境
- [固] 三個 curl 測試 30 秒定位根因，比啟動 4 個 agent 研究程式碼有效得多

## 案例摘要

LINE Bot 不回應（2026-03-22）：AI 看到 ngrok 就假設 URL 過期，啟動 4 agent + Plan Mode 設計方案 — 全錯。3 個 curl 30 秒就能定位真因（Gateway 路由 404）。重啟即解。