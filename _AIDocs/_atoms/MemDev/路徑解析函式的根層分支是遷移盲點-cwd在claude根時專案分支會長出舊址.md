# 路徑解析函式的根層分支是遷移盲點-cwd在claude根時專案分支會長出舊址

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: resolve_failures_dir, memory/failures, 舊址重生, get_project_memory_dir, 根層分支, failure_writeback, 流浪檔, 路徑遷移, cwd 在 ~/.claude, FailureDetect
- Created-at: 2026-08-26
- Related: hud暫存清單靠prose猜路徑的失敗-改殘檔帳本以檔案系統為權威, 歸因早停-找到合理嫌疑機制就停止驗證, realm-範疇分區機制-v5

## 知識

- [臨] 始末：修完 extract-worker「無專案 memory 時 fallback 指 V3 舊址 memory/failures/」並 git rm 該目錄後，同一 session 的背景失敗萃取（[Guardian:FailureDetect]）在 16:43 又把小寫 `memory/failures/wrong-assumptions.md` 生回來。最終正解：`wg_core.resolve_failures_dir` 在 `get_project_memory_dir(cwd)` 回傳**根層 memory/ 本身**（cwd ∈ ~/.claude）時，不得走 `mem / "failures"` 專案佈局，要落全域家族目錄 `FAILURES_DIR`。
- [臨] 根因：路徑解析函式有兩條分支（專案層／全域 fallback），第一次修只看到「無專案」那條，沒盤點「專案＝根層本身」這個邊界——`get_project_memory_dir` 把 ~/.claude 當成一個專案回 MEMORY_DIR，於是專案分支在根層長出專案佈局。表面症狀（同名檔重生）讓人以為是舊碼殘留，其實是**同一函式的另一條分支**。
- [臨] 設計原理：`get_project_memory_dir` 回 MEMORY_DIR 給根層是為了讓 scope 解析、索引定位在 ~/.claude 內也有「專案記憶目錄」可用；`resolve_failures_dir` 借用它時沿用了「有專案 memory → <mem>/failures」的專案佈局，沒意識到根層的失敗家族有自己的目錄規則。
- [臨] 運作邏輯：Stop hook 偵測失敗回報 → 背景 extract-worker `_failure_writeback(ctx.cwd)` → `resolve_failures_dir(cwd)` → cwd=~/.claude → 專案分支 mkdir `memory/failures/` → `_create_failure_atom` 落檔 → 下次全域健檢把它當 atom 掃到。斷點在 resolve 的分支選擇，不在寫檔模板。
- [臨] 防再犯：改任何「依 cwd 解析目錄」的函式時，測三種 cwd——外部專案、非專案目錄、**~/.claude 本身及其子目錄**；用 audit log（memory/_meta/atom_io_audit.jsonl 的 op/source/path）追寫手而非猜；被 git rm 的目錄若再出現，先查 audit log 的 ts/source 再動手。已加回歸測試 tools/verify/verify_project_layer_smoke.py（cwd=~/.claude → memory/Failures）。

## 行動

- 改 cwd→目錄的解析函式：三種 cwd（外部專案／非專案／~/.claude 本身＋子目錄）都要測
- 同名檔／目錄被刪後重生：先讀 atom_io_audit.jsonl 找 op/source/ts，再改碼
- 修 fallback 分支時把同函式所有分支列出來逐條檢查邊界，不只修報錯那條
