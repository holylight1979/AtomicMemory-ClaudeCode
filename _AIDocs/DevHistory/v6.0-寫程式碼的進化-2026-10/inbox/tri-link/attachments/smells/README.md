# smells v2 — 「不是 bug 但壞味道」四個可數指標（純語法，Roslyn）

做什麼：對一個 C# 目錄（partial 類別跨檔合併）數四件事，列清單給人判，不產 PASS/FAIL。

| 指標 | 數什麼 | 判讀 |
|---|---|---|
| A 狀態所有權散落 | 每個 private 容器欄位（Dictionary／HashSet／List…）的改動點（Add／Remove／Clear／索引賦值）散在幾個檔、幾個方法 | ≥3 檔或 ≥6 處 → 該收成 Begin/End 單一出入口（CS-54） |
| B 讀路徑長度 | public 方法沿同類別委派鏈最深一條：委派跳數＋條件巢狀深度 | ≤3 綠、4～6 看一眼、>6 標；含 ≥8 段 switch 的分派型方法另標 `[switch-dispatcher]`、不進分布 |
| C 純轉接 | 方法體只有一行呼叫且引數原樣傳過去（override 不算） | 只列清單，一半是合理包裝 |
| D 入口可達性 | 指定類別的 public `<prefix>*` 方法，分五類：直接已接（被 `--wired-file` 呼叫）／間接已接（被已接入口在類別內呼叫，傳遞閉包）／只有測試路徑（`--test-dirs`）／只被類別內部非入口方法呼叫／沒人呼叫 | 「只有測試路徑」＝功能做了一半 |

怎麼跑（本專案）：

```
dotnet run -c Release --project Tools\CodeReview\smells -- Client\TSLG_Hotfix --entry-class FakeMapServer --entry-prefix Req --wired-file Game/map/FakeServer/FakeMapServer.Rpc.cs --test-dirs "MCP/,/Editor/,Test"
```

參數：`--entry-class`（預設 FakeMapServer）、`--entry-prefix`（預設 Req）、`--wired-file`（相對根目錄、逗號分隔，玩家路徑的分派檔）、`--test-dirs`（路徑片段、逗號分隔，預設 `MCP/,/Editor/,Test`；SGI 用 `Module/GM/`）。
相依只有 `Microsoft.CodeAnalysis.CSharp 4.1.0`（與 `rule_check` 同版）；935 檔約 8 秒。

限制：純語法樹、無語意模型——同名方法以第一個宣告為準、介面跳只認同檔、跨類別的呼叫不追；D 的「間接已接」只追同類別內的呼叫，入口經別的類別轉一手會漏。

版本：v2（入口可達性加傳遞閉包、測試路徑參數化、分派型方法另標）。
