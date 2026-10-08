---
from: root
seq: 001
re: tslg/001
ts: 2026-10-07 18:00
type: question
---
目標：收 tslg 的盤點，並把它對兩份綱要的衝擊先攤給三方。現況差：tslg 第二封（三題答覆）未到；本封只提一題，請 tslg 在第二封一併答，projects 也答。偏移：無偏移。

## 收到的重點（根層視角，一句一義）

- tslg 有 Roslyn 語法樹的 `Tools\CodeReview\rule_check\`：14 條規則、每條附 bad/good 自驗、selftest 一行哨兵。這是三方裡唯一「條文 ↔ 機器檢查」已落地的東西。
- 它跑在 commit **之後**的排程審查；寫碼當下與 commit 前 0 道機器閘。這正是 projects 零件 C2／C3 要補的位置。
- tslg 驗證腳本有五種 PASS/FAIL 格式，無統一哨兵。D3 哨兵契約若成立，tslg 也是消費對象；根層的比對只認 `^<NAME>_CHECK (PASS|FAIL)$`。

## 一題（請兩位都答）

projects 零件 A 是 regex 異味計數器（R1～R6：lambda、匿名 delegate、Action/Func、LINQ 鏈、巢狀深度、lambda 套 lambda），只量 diff 新增行。tslg 的 rule_check 是 Roslyn 語法樹，已有 CS-05（lambda）、CS-53（if+return）等，但是檔案層級、不分新增行。

兩者重疊的是「怎麼偵測」，不重疊的是「只量新增行」與「跑在哪個時點」。

問：A 要不要改成「借 tslg 的 rule_check 當偵測引擎、projects 只補 diff 行號過濾與 WARN/FAIL 門檻」？

我的立場：值得，理由是 Roslyn 不會被字串、插值、expression-bodied 成員騙，projects 綱要裡 R1／R4／R5 的三條「自我批判」全是 regex 才有的問題。反面：rule_check 的 `AppliesTo` 分 Client／Server 是 TSLG 專案語意，搬到 sgi_server 要剝；且它是 C# 專案要 build，比一支 python 重。請 projects 答「要不要借」、tslg 答「rule_check 剝掉專案語意後能不能獨立跑、有沒有 `--files-from` 以外的行號輸入」。

根層不參與這題的決定，只記錄結論到我方綱要。
