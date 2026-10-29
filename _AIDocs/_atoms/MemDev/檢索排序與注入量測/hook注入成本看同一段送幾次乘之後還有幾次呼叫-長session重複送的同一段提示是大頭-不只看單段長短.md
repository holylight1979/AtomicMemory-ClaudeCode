# hook注入成本看同一段送幾次乘之後還有幾次呼叫-長session重複送的同一段提示是大頭-不只看單段長短

- Scope: global
- Author: holylight
- Source: merge 4f3dc85a（注入噪音減量）2026-10-27
- Confidence: [臨]
- Trigger: 注入成本, 重複注入, 同一段提示重送, 注入重讀, 注入減量, 長 session token, additionalContext 重讀, 去重省 token, 注入噪音
- Created-at: 2026-10-27
- Related: v60-hook代價大頭在被提醒被擋後多跑的模型呼叫與擋訊息重讀-不在hook程式本身, claude-code的resume接續後前面回合hook注入的內容仍在context-只有壓縮才丟-判送過沒要跟壓縮時間比不能因resume重置

## 知識

- [臨] hook 注入的每一段，之後到 compact／session 結束的每次模型呼叫都會再讀一次；成本≈「同一段送幾次 × 每次之後還有幾次呼叫 × 段長」。
- [臨] 長 session 裡重複送的同一段提示是注入成本大頭：真實 session 有這類提示的平均含重讀 60.8 萬 token，去重後 11.4 萬。第一回合量尺量到的注入重讀只佔約 7%，是因為短 session 重送次數少。

## 行動

- 挑注入減量目標：先按「送幾次×剩餘呼叫數」排，再看單段長短
- 同一段內容沒變就不重送（重置條件綁壓縮）
