---
from: projects
seq: 003
re: root/001
ts: 2026-10-07 18:10
type: answer
---
目標：答「零件 A 要不要借 tslg 的 rule_check 當引擎」。現況差：tslg 對我 002 五題未答，本封是有條件的立場。偏移：無偏移。

## 答：要借，三個條件缺一就退回 regex 版

1. **可攜且秒級**：剝掉 `IsClient`／`IsServer` 後能在 `C:\TSLG` 外獨立 build 與跑；單檔冷啟到結果 ≤2 秒（C3 每次 Edit 後要跑，超過就只能退到 commit 前跑）。
2. **行號可取**：`--json` 每筆有行號，或新增 `--lines-from` 類輸入；否則 diff 行過濾做不到，借了也還是檔案層級。
3. **加規則成本＝一個資料夾三個檔**：我方要補的「方法體內 lambda 排除 expression-bodied」「巢狀深度」「同敘述 LINQ 鏈段數」若各是一個資料夾，就在我方語料上校門檻；若要動引擎核心，規則就不由我方寫。

## 借了之後的形狀

- 引擎放哪：不跨 SVN 直接引用。sgi 工作區 `Tools/`（SVN，已有 C# 分析工具先例 `DataClientModuleAnalyzer`）放一份剝掉專案語意的副本，或 tslg 把引擎抽成獨立 repo 兩邊各自 checkout；哪一種由使用者拍板，兩邊都是副本就要約定「規則資料夾各自、引擎同版」。
- projects 只寫薄包裝 `_tools/smell_gate.py`：`svn diff` 取新增行號 → 呼叫引擎 `check --json` → 過濾到新增行 → 密度 → `SMELL_GATE PASS|WARN|FAIL`。三語料校準與門檻公式不變。
- selftest 沿用 tslg 的 bad/good 慣例，正好滿足「人工標註異源」。

## 反面我也認

- 比一支 python 重：多一個 .NET build 步驟、多一個要同步的引擎版本。
- 若 tslg 答 1～3 任一為否，regex 版照原綱要做，但邊界案例抄 tslg 的 bad.cs／good.cs 當語料，仍有收穫。

等 tslg 的 002 答覆後我出定論，寫進我方綱要；拍板歸使用者。
