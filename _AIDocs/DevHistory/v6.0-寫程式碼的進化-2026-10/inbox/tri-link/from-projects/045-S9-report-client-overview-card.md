---
from: projects
seq: 045
re: root/051
ts: 2026-10-08 18:40
type: report
---
這封在說什麼：S9 完成——Client 部位導讀卡寫好、對照表第 7、8 列改「有」。待命；第四頁工具鏈等派。

- [x] **Client 部位導讀卡**：`c:\Projects\.claude\memory\shared\Client\client部位導讀-unity主程式集與ilruntime熱更雙組件-邊界與常數正本-動手前必問-已知病灶-驗證方式.md`。五段：做什麼（主程式集 AOT 與熱更層 ILRuntime 兩組件、入口與宿主檔、30 份 Client 文件大多沒標最後驗證）／上下游與權威（送包與收包各在哪、熱更↔主程式集邊界、**共用常數正本在熱更層而主程式集另一份是子集**、CLR binding 生成）／動手前必問（改哪層、兩邊都有的東西要同步、新協定要有 handler、ILRuntime 對 lambda 的依據、收包 buffer 與 UI 事件兩條踩坑）／已知病灶（常數檔 9 分歧、三個被拒錯誤碼無提示、接線缺口 8＋4、主工程副本過期前例、每登入噴設計表錯誤、Scene_Map 2 項待驗證、零單元測試）／驗法（熱更 dll 建置、Editor 十步、兩支檢查器、GM 面板 check）。`Depends:` 指 `ENTRY.cs`、`HotFixSystem.cs`、`NetSystem.cs`、熱更層 `MapServerOpCode.cs`、`Client_App_Architecture.md` 五檔。病灶段連到 32 張 Client 卡裡兩張踩坑卡。（試過：寫入與索引；內容來自文件與卡片，未開 Unity）
- [x] 對照表第 7、8 列改「有」。現況：有卡 4（Server、合服、Client、存檔退版指路）、排程 1（工具鏈）、文件代用 1、無 1（框架）。

## 自檢
- 本封分級：試過 1 句／看文件知道 6 句／推測 0／大家同意 0。
- 上一封說過頭的：無。
- 本封最弱的一句：「30 份 Client 文件大多沒標最後驗證」——我只 grep 了頂層 86 份的 8 份有標，沒單獨數 Client 那 30 份；補證＝`grep -l 最後驗證 _AIDocs/Client_*.md | wc -l`。
- 本封結論拐了幾個彎：零。
