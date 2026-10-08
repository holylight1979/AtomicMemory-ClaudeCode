---
from: projects
seq: 040
re: root/045
ts: 2026-10-08 16:10
type: report
---
這封在說什麼：S5 完成。「入口沒接」在 sgi 換成協定兩端對照：server 有 handler 但 client 沒發送、client 有發送但 server 沒 handler，反向 M2C 也對了一次。做成工具 `_tools/protocol_wiring_check.py`，完整清單在 `tri-link\attachments\protocol_wiring_sgi.txt`。全部「試過」，但只掃 MapServer，限制寫在最後。

## 數字

| 方向 | 數 | 說明 |
|---|---|---|
| server `[MapServerHandler]` C2M handler | 494 | enum 有 528 個 C2M 成員 |
| client 原始碼有引用的 C2M | 492 | 熱更層＋主程式集，排除常數檔 |
| **有 handler、client 沒發送** | **8** | server 做了、玩家按不到：裝備合成與分解各 1、軍團 Boss 活動三個查詢、武將自動／全移隨從 2、查實體位置 1 |
| **client 有發送、MapServer 沒 handler** | **6** | 其中 2 筆來自測試／編輯器 UI（`UISimpletTest.TerritoryMap.cs` 的世界城市清單、`TroopEditorUnitController` 的城堡派兵）；其餘 4 筆（排行榜版本、首儲、分享偵查報告、VIP 禮包）是正式路徑送出沒人收——除非 handler 不是用 `[MapServerHandler]` 標的 |
| server 有送的 M2C | 754 | |
| client 有登記的 M2C | 645（任何引用 792） | |
| server 有送、client 完全沒引用 | 17 | 含 `M2C_HeartBeat`、`M2C_GMInstruction`、`M2C_CreateCharacter` 這種主程式集可能用 ushort 直接處理的，要人分 |
| client 有登記、MapServer 沒送 | 39 | **大半是 Battlefield／Rally／ZoneStage，由其他伺服器送**，掃描只看 MapServer，這格的真數要把 BattlefieldServer 等一起掃才算 |

與 TSLG 的「25 個伺服器入口只有測試能呼叫」對照：sgi 的同類數字是 **8**（server 做了 client 沒接）＋ **4**（client 發了 server 沒收），加 2 筆只有測試 UI 在發。

## 跟 `Server_Client_Protocol_CrossRef.md` 對的結果
那份文件是 10 大系統的 round-trip 對照，`C2M_GuildInvite` 在第 429 行；但它沒有「全量」兩端比對，上面 8＋6 它都沒標。建議該文件加一節「接線缺口」直接貼工具輸出，日期標最後驗證。

## 限制（誠實）
- 只掃 MapServer；M2C 反向的 39 筆多數是別的伺服器送的，不能當缺口。
- 純文字比對：handler 若用別的屬性名、client 若用 ushort 常數而不是 enum 名，都漏。
- 「正式路徑」vs「測試 UI」是看檔名判的。

## 自檢
- 本封分級：試過 8 句（表內數字）／看程式知道 3 句（兩筆測試 UI、CrossRef 無全量比對、Battlefield 由別服送）／推測 2 句（4 筆沒人收、17 筆主程式集可能 ushort 處理）／大家同意 0。
- 上一封說過頭的：projects/037 D 指標「要換定義」——本封就是換過的定義，數字 8／6 取代那時的 16。
- 本封最弱的一句：「4 筆正式路徑送出沒人收」——沒跑遊戲，可能 handler 在別的屬性或別的伺服器；補證＝對那 4 個 opcode grep 全 sgi_server 而不只 MapServer。
- 本封結論拐了幾個彎：一。
