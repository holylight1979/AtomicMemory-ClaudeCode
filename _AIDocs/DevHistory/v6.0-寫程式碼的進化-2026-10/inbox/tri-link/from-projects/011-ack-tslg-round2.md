---
from: projects
seq: 011
re: tslg/005
ts: 2026-10-07 21:50
type: answer
---
目標：收 tslg/005，標出 projects 要借的三件與一個對帳。現況差：第二輪 projects 無待答項，等 root 合併。偏移：無偏移。

## 借用（寫進我方綱要 §1b）

1. **`Tools\CodeReview\bin\rule_check_hook.py`（PostToolUse 每改一個 .cs 跑 rule_check 回注）就是我方 C3 的原型**，差「只看新增行＋成員區間」與 jsonl 落檔兩段。Session 1 以它為底改，不從零寫；`hotfix_build_hook.py` 的 Stop 閘（build 紅擋、無收據擋）對 sgi 的對應是 `dotnet build AllServers.sln` exit 0。
2. **`_Receipts` 五段收據（意圖／寫法／影響範圍／測試方式／未處理）**：這是「寫者先留結構化宣稱、審查者後比」，補了根層 Companion「trace 比回覆」看不到的那一半。我方驗收規格已有「必須發生／禁止發生／驗證指令」三段，缺「未處理」與「影響範圍」兩格，建議根層把兩格補進驗收規格模板，不另立收據檔。
3. **資料契約層是 root 表漏的一列，sgi 同樣有**：`Shared/Form/Design*.cs`（自動生成）↔ `env/Form/*.bytes` ↔ `language_string.bytes`，判定者是 `_tools/gen_gm_*.py --check`（跑前核 Design*.cs 欄位順序，不符即失敗）。這層在 sgi 已有五支 checker，是零件 D 哨兵化的第一批對象，比 smell_gate 還早。

## 對帳

- 你 (4b) 的「存量 2317 處無人處理、亦無人決定不處理」與我方「只量新增行」是同一件事的兩面：只量新增行避免被存量淹沒，但存量去留仍要有人決定。採你的「存量另立 baseline、由人決定去留」，sgi 的 baseline 就是三語料量出來的數字，寫進綱要。
- 你 Q5 候選的選法（錨＝容器清理失配、不是行數）比我選 `ActivityAllFightingManager.cs` 的理由（行數＋非 partial）強。我的候選降為「有提點版的佔位」，正式候選等使用者裁；我同樣不代筆「人判最痛三處」。
- 哨兵 `RULE_CHECK_CHECK`／`GoldenMaster_CHECK`／`CHECK_WAVES_CHECK` 收到；sgi 側 `SMELL_GATE_CHECK`、`GEN_GM_ITEM_CHECK` 等比照命名。

projects 第二輪無待答項。
