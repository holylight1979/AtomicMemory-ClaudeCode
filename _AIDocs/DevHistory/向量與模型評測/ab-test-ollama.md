# Ollama Dual-Backend A/B 萃取品質實測（2026-03-13）

> 從 toolchain-ollama.md 移出的完整實測數據。結論已保留在 atom 內。

## 測試設計
- 2 段真實 transcript（Redmine debug + NuGet build），各 4000 字送入萃取 prompt

## 對比結果

| 維度 | rdchat qwen3.5 (think=T, 8192) | local qwen3:1.7b (think=F, 2048) |
|------|------|------|
| JSON 格式 | OK | OK |
| 回應時間 | 38-43s | 6-13s |
| 萃取項目數 | 2-4 項（精簡） | 4-6 項（較多但淺） |
| 平均 content 長度 | 83-89 字 | 38-49 字 |
| type 多樣性 | factual+architectural+decision+procedural | 幾乎全 factual |
| 具體性 | 高（含路徑+數值+決策理由） | 中（偏短，缺細節） |
| 噪音 | 極低 | 低（偶有淺層重複） |
