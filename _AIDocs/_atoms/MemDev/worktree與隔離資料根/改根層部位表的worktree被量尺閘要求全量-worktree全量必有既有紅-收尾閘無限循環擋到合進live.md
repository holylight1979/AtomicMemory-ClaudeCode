# 改根層部位表的worktree被量尺閘要求全量-worktree全量必有既有紅-收尾閘無限循環擋到合進live

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MeasureGate 循環, 收尾閘無限擋, 根層 worktree, is_root_worktree, 全量 run_verify, PYTEST_MEASURE, 部位表位元組, worktree 既有紅, 擋滿不放行
- Created-at: 2026-10-13
- Related: 驗證閘要能被如實滿足-超過工具10分鐘上限的量尺要讓驗證程式自寫收據並連到真的啟動紀錄
- Source: session:03f81f65 2026-10-13

## 知識

- [臨] 始末：track-know 照派工在 worktree 裡改根層部位表（加類別欄）。live 的 `is_root_worktree` 當時有一條「worktree 與 live 的部位表位元組相同」，表一改，這個 worktree 就失去根層身分，量尺閘改要全量 `run_verify.py`。全量在 worktree 裡有 9 個與本軌無關的既有紅（資料根讀 worktree 沒有的個人檔、live API 對 worktree 索引、計時預算、memory 內容 lint），收據永遠是 FAIL。結果每次結束回合都被擋，累計 22 次以上；使用者兩次選「繼續擋」，我修了 realm_gate 資料根寫死的那一紅，但其餘是環境與資料問題。最終正解由總控裁定 B12：根層身分只看 git 登記（`.git` 指到 live 的 worktrees 管理目錄，而且管理目錄反向指回），不再比部位表；等合進 live 才解開。
- [臨] 根因：身分判定綁在「被改的那個檔」上。第 3 條當初是為了區分「真正的根層 worktree」與「放了根層表副本的外部目錄」，用表的位元組當指紋；但指紋是可變的內容，派工本身就是改它。第二個根因：量尺閘的「擋滿只認使用者放行」加上「每回合重算」，遇到「結構上拿不到的尺」就變成無限循環；而調度又定了「不反覆問原設計者」，兩條規則互打。
- [臨] 防再犯：① 身分類判定只用不會被正常工作改動的事實（git 登記），不用工作產物的內容。② 派工要在 worktree 改根層設定類檔案前，先問「這個檔是不是某個閘的判定依據」，是就把閘的身分判法一併處理。③ 收尾閘第一次擋在「全量」時，先查 worktree 是不是被認成根層 worktree（`lib/overview_hub.is_root_worktree`），不是就是身分問題、不是測試問題，立刻回報調度，不要去追全量的紅。④ 一次性等待（合併、背景量尺）時，循環擋下不進行工具呼叫，只短句回應，讓它自己發過。

## 行動

- 量尺閘擋全量時，先用 is_root_worktree 查 worktree 身分，再決定是修測試還是回報
- 身分類判定不用會被工作改動的內容當指紋
