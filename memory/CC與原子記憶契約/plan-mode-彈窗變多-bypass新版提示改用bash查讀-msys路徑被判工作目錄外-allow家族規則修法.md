# plan-mode-彈窗變多-bypass新版提示改用bash查讀-msys路徑被判工作目錄外-allow家族規則修法

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: plan mode, 權限詢問, permission prompt, bypass, bypassPermissions, cd /c/, Read(//c/, settings.json allow, useAutoModeDuringPlan, 彈窗變多
- Created-at: 2026-10-01

## 知識

- [臨] 2026-10-01 實查（CC 2.1.286）：Plan Mode 執行階段突然大量彈權限詢問，根因是三件事疊加——①新版 bypass 模式系統提示明文指示模型「用 Bash 的 cat/grep/sed 取代 Read/Grep/Edit」（GitHub issue #91683，2026-09-03，2.1.259 起）；②Plan Mode 是獨立權限模式、暫停 bypass，Bash 要通過內建唯讀判定（ls/cat/grep/head/tail/find/wc/cd/唯讀 git），含 sed、python -c、find 配未引號 glob、cd 後接重導向、無法解析的跳脫都會問；③Windows 上模型寫 `cd /c/Users/...`（MSYS 路徑），CC 認不出等於 `C:\Users\...`，當成 cd 到工作目錄外——證據是 settings.json 被自動寫入雙斜線 `Read(//c/Users/.../**)` 規則。
- [臨] 「Yes, don't ask again」對複合指令存的是整條精確比對規則，幾乎不會再命中，只會堆垃圾；修法改寫 allow 家族規則：`Bash(cd *)`、`Bash(cat *)`、`Bash(grep *)`、`Bash(sed -n *)`、`Bash(head *)`、`Bash(tail *)`、`Bash(ls *)`、`Bash(find *)`、`Bash(wc *)`（`:*` 與 ` *` 等價；Plan Mode 也吃 allow 規則）。`Bash(python -c *)` 等於放行任意 Python，是取捨。官方另有 `useAutoModeDuringPlan: true` 讓 auto mode 分類器在 Plan Mode 代審，依賴 auto mode 可用，未驗。
- [臨] 行為面修法已寫入 rules/core.md：Plan Mode 查讀一律 Read/Grep/Glob（永不彈窗），Bash 不加 `cd /c/...` 前綴。

## 行動

- Plan Mode 查讀用 Read/Grep/Glob，不用 Bash cat/grep/sed；Bash 直接寫絕對路徑不加 cd 前綴
- settings.json allow 出現整條複合指令或 Read(//c/...) 雙斜線規則 → 視為路徑誤判症狀，清掉並改家族規則
