---
from: projects
seq: 043
re: root/048
ts: 2026-10-08 17:10
type: report
---
這封在說什麼：S7 完成——Server 部位導讀卡樣板寫好、教訓搬進去、路徑前綴對照表放附件。待命；下一頁合服等派。

- [x] **Server 部位導讀卡**：`c:\Projects\.claude\memory\shared\Server\server部位導讀-mapserver主邏輯-上下游與權威-已知病灶-驗證方式.md`（記憶卡片格式）。五段：這部位做什麼與上下游（MapServer 唯一直連 client、其餘 19 服經 Agent 連出、收包入口在 `GameClient.Handler.*.cs`）／權威在哪（軍團事實在 GuildServer、存檔在 PlayerDbServer blob、企劃表靜態載入、共用常數正本在熱更層）／動手前必問（SaveMode 那條教訓）／已知病灶（H-1、H-3、H-5、H-6 殘留、DbTableModule 3 倍數、常數檔 9 分歧、接線缺口 8＋4、logger stdin）／最近驗證 2026-10-08 與驗法。`Depends: path:` 指向 `GameServer.cs`、`GameClient.cs`、`SGIServerSet.cs`、控制塔四個檔，健檢在檔消失時標 stale。（試過：卡片寫入、索引更新；Depends 欄位已確認在檔內）
- [x] **教訓搬家**：「判資料存哪必先查 `SGIServerSet.cs:10` 的 SaveMode 與 DbServer 建表鏈」從 CHANGELOG 06-12 條尾搬進卡片「動手前必問」段，並註明 H-7 就是沒問這題。
- [x] **路徑前綴→導讀卡對照表**：`tri-link\attachments\sgi-路徑前綴對導讀卡.md`，11 列、由上往下第一個命中為準；目前「有卡」的只有 Server（涵蓋 MapServer／Shared／其他服務）與既有的 blob 退版指路卡，合服、Client、Tools、框架四列是排程。附注入時機與「沒交定位三行不准改」的條件，供根層接。

## 跟 TSLG 的 T7 對齊
格式同（做什麼／上下游權威／病灶指向／驗證日期與驗法／`Depends`）；差別是 sgi 的「病灶」能指到控制塔的 H 編號與 §9，TSLG 指踩坑卡。兩邊都還沒驗「注入後 AI 會不會先看」，那是根層的真實 session 量測。

## 自檢
- 本封分級：試過 2 句（卡片寫入、Depends 在檔內）／看文件知道 4 句（卡片內容來源）／推測 1 句（注入後有沒有用）／大家同意 0。
- 上一封說過頭的：projects/042 無。
- 本封最弱的一句：卡片「權威在哪」那段是我從服務目錄與控制塔整理的，沒逐服讀碼核；補證＝每列對一次該服務的 Service 檔。
- 本封結論拐了幾個彎：零。
