---
from: projects
seq: 044
re: root/049
ts: 2026-10-08 18:00
type: report
---
這封在說什麼：S8 完成——合服部位導讀卡寫好、對照表第 4 列改「有」。待命；第三頁 Client 等派。

- [x] **合服部位導讀卡**：`c:\Projects\.claude\memory\shared\合服\合服部位導讀-merge工具四模式八步驟-世界模型與不變量-動手前必問-已知病灶-驗證方式.md`。五段同 Server 卡：做什麼（四模式八步驟、單一出口、同事以 AI 依驗收規格寫、總綱與待辦文件在哪、**文件行號基準 r15343 落後程式 r16564 要先抽查**）／上下游與權威（一世界一 AccountDB、合服寫 MapMapping 不改 resident、blob 唯一路、只有 Step 6/7 寫 DB、無 rollback、GuildDB 共用無閘門）／動手前必問（新步驟同時接拆服、結束碼契約一碼一動作、轉換期例外記帳不加內層 catch、企劃表路徑、foreach 禁 LINQ 豁免）／已知病灶（部分合服不支援、接續合服只保證一跳、孤兒聊天列只 Waived、OBT 未驗、沙箱只做過本機小規模、工具本身的空 catch 與 CS-53 誤報、Log.Current）／最近驗證與驗法（`run_pkg2_*.sh`、`run_pkg3_full.sh` 哨兵、本地快速上手）。`Depends:` 指 `Program.cs`、`BaseFlow.cs`、`MergeFlow.cs`、總綱、待辦五個檔。病灶段連到 failures 那張「新增處置步驟要同時接拆服」與 LINQ 豁免卡。（試過：寫入與索引；內容來自文件與 ls，未重跑沙箱）
- [x] 對照表第 4 列 `sgi_server/ServerTools/Merge/` → 有卡。
- 對照表現況：有卡 3（Server、合服、存檔退版指路）、排程 2（Client、工具鏈）、文件代用 1、無 1（框架）。

## 自檢
- 本封分級：試過 1 句（卡片寫入）／看文件知道 5 句／推測 0／大家同意 0。
- 上一封說過頭的：無。
- 本封最弱的一句：病灶段「文件落後程式兩個月」——我只比了總綱頭的 r15343 與 svn log 最新 r16564，沒逐條核哪些段落失準；補證＝對 Step1～Step8 各抽一個行號。
- 本封結論拐了幾個彎：零。
