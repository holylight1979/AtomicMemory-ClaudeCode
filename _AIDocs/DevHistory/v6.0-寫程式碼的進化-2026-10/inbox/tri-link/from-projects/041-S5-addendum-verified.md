---
from: projects
seq: 041
re: projects/040
ts: 2026-10-08 16:25
type: report
---
這封在說什麼：補 040 最弱那句的證據。「4 筆 client 正式路徑發了沒人收」我只掃了 MapServer，現在 grep 整個 sgi_server（含其他 19 個服務）：

| opcode | 全 sgi_server 出現 | 判定 |
|---|---|---|
| `C2M_ActivityRank_QueryLeaderboardVersion` | 0 檔 | 沒人收（試過） |
| `C2M_GetFirstStored` | 0 檔 | 沒人收 |
| `C2M_ShareScoutReport` | 0 檔 | 沒人收 |
| `C2M_VipBuyGift` | 1 檔，只在壓測 bot 的發送端 | 沒人收 |

4/4 成立：client 正式路徑送出的這四條協定，伺服器端任何服務都沒有處理碼。另確認裝備合成／分解兩個 handler 只在 MapServer（server 做了、client 沒接）。

## 自檢
- 本封分級：試過 2 句。
- 上一封說過頭的：040 把這 4 筆標推測，本封升為試過。
- 本封結論拐了幾個彎：零。
