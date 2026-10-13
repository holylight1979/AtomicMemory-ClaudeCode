# 接派工單先核實檔案路徑與跑法-pytest收0案不是綠-掃描型verify腳本要直接python跑

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/to-track-a6/000-prompt.md 第 3、4 項；from-track-a6/001 交付信
- Confidence: [臨]
- Trigger: 派工單, 路徑寫錯, no tests ran, pytest exit 5, 收 0 案, 掃描腳本, verify 腳本, 跑法, 核實路徑, 工作 session
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的工作 session track-a6（A6 共用檔：settings/config/TECH/Architecture/CHANGELOG/README/Install-forAI/健檢/coding-style/atom 改寫＋pack.py 小修提交），對人總控台是 claude-91、調度總控台是 claude-9f。第一步用 EnterWorktree 切進 work…」

## 知識

- [臨] 實例：派工單寫「確認 run_verify 掃到 tools/verify/verify_no_window_spawn.py」並指定 `pytest -q … tools/verify/verify_no_window_spawn.py`；實際檔在 hooks/verify/，而且是 main() 印 PASS 的掃描腳本、沒有 test_ 函式。照抄會得到「找不到檔」，換對路徑後 pytest 也只收 0 案（no tests ran，exit 5），容易誤以為驗過。
- [臨] 判準：派工單裡的路徑與指令多半是寫單者憑記憶寫的。執行前用 Glob／ls 核實檔在哪，打開檔頭看它是 pytest 案還是自帶 main 的腳本；不符就照實際位置與跑法執行，交付信寫明「派工單第 N 項應為 …」，不在單上寫的位置另建同名檔湊路徑。
- [臨] pytest 尾行 `no tests ran` 或 exit 5 不是綠；多檔一起跑時，某檔收 0 案會被其他檔的 passed 蓋掉，看不出來。懷疑時單獨跑那一檔，或看 collected 數。

## 行動

- 接到派工單：每個點名的檔先 Glob 核實位置、讀檔頭確認跑法，再照實際跑
- 交付信列出派工單與實際不符之處，讓寫單者改單
