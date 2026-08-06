# OTEL 遙測評估結論-不實作-兩目標指標皆測不到

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: OTEL, OpenTelemetry, 遙測, telemetry, hook 延遲量測, token 稅量測, CLAUDE_CODE_ENABLE_TELEMETRY
- Created-at: 2026-07-08

## 知識

- [觀] 評估結論（2026-07 C12）：不實作 OTEL export（CLAUDE_CODE_ENABLE_TELEMETRY=1）。原始目標「hook 延遲 / 注入 token 稅真實分布」兩者 OTEL 都測不到——官方匯出面（metrics: session/token.usage/cost/lines_of_code/commit…；events: user_prompt/api_request/tool_result…）無 per-hook execution latency；api_request 只有整段 input tokens，無法歸因到個別注入源
- [觀] 成本面：需常駐 OTLP collector/Prometheus + 儲存 + 查詢面板，單人單機違反 Native-first 輕量原則；效益面：僅得 per-request token/cost 分布（已有 Context budget 自報 + injection budget 粗覆蓋）
- [觀] 若未來真需 hook 延遲分布：dispatcher 入口計時落 JSONL（~20 行、零依賴）即可，比 OTEL 便宜兩個數量級；重評門檻 = 需要跨機聚合或多人環境時

## 行動

- 被要求量測 hook 延遲/token 稅時：先引本結論，勿重啟 OTEL 評估；需要時走 dispatcher 自我計時路線
