# 比較多跑的LLM代價看處理的token量不看美金-串跑第一跑付建快取的錢-美金會讓先跑的那組看起來比較貴

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 代價, 成本比較, cost_usd, 多跑比較, 對照組, 快取, cache_creation, token 量, 量測, A/B
- Created-at: 2026-10-22
- Source: session:c1ef07bd 2026-10-22

## 知識

- [臨] 同一台機器、同一份系統提示連續跑幾次無頭 session 做對照時，第一跑要付「建快取」（cache_creation，單價較高），後面幾跑在快取期限內直接讀快取（cache_read，單價很低）。用美金比，先跑的那組會被墊高。實例：一句話探針，對照組先跑 0.17 美元，後跑的實驗組只要 0.11 美元，實際上實驗組讀的 token 比較多。
- [臨] 比代價要用模型實際處理的 token 量：輸入＝input＋cache_creation＋cache_read，輸出分開列；美金只放附錄當參考。真的要比美金，就把兩組交錯跑，並在報告標出哪一跑是冷快取。

## 行動

- 做多跑對照時，主表用輸入（含讀快取與建快取）與輸出 token，美金只當附錄參考
- 兩組交錯跑，並標出第一跑是冷快取
