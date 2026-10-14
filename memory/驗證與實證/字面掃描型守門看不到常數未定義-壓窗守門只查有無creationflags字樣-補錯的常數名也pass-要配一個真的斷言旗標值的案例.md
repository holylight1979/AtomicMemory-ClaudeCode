# 字面掃描型守門看不到常數未定義-壓窗守門只查有無creationflags字樣-補錯的常數名也PASS-要配一個真的斷言旗標值的案例

- Scope: global
- Author: holylight
- Source: session:f399cdb2 2026-10-13 tools/verify/verify_second_opinion_pack_spawn.py
- Confidence: [臨]
- Trigger: 字面掃描, 守門腳本, creationflags, CREATE_NO_WINDOW, NameError, 閃 console 窗, verify_no_window_spawn, 假通過, 靜態掃描不夠, monkeypatch 斷言
- Created-at: 2026-10-13
- Quote: 「請把知識、經驗，該atoms的都記好，特別是我最後提出的」

- Related: 健康探針要真的用到被依賴的能力-答案只能從那個能力拿到-只回固定字樣的探針探不出沙箱故障

## 知識

- [臨] 實踩：修 tools/second-opinion/pack.py 的 subprocess.run 補 `creationflags=_NO_WINDOW`，但 `_NO_WINDOW` 常數是別的檔的（grep 兩個檔把結果看混），pack.py 裡根本沒定義；壓窗守門 verify_no_window_spawn 只掃字面「有沒有帶 creationflags／startupinfo」，照樣 PASS；整份 tools verify 718 passed 也沒抓到，因為沒有任何測試真的呼叫那條路徑。補一個 monkeypatch subprocess.run、斷言 `creationflags == CREATE_NO_WINDOW` 的案例，第一次跑就紅在 NameError。
- [臨] 通則：字面掃描型守門（grep 有沒有某參數、某關鍵字）只證明「寫了」，不證明「跑得過」；任何這類守門都要配至少一個真的執行到該路徑、斷言實際值的案例。守門腳本本身也要在全量清單裡，不然永遠不會跑。
- [臨] 反向也會壞：字面守門案「數某條件字串出現次數＝2」（讀檔分支都收 PowerShell）在一天內被兩條軌誤紅兩次：一次是分支多加一個工具名讓字面不同，一次是多了第三個讀檔分支。裁定：數字守門退場，改成列舉所有符合形狀的分支、逐一斷言行為（每支都含要求的工具），新增分支不該讓守門紅。同一面第二次紅就改設計，不把 2 改 3。

## 行動

- 改 subprocess 呼叫後：跑一個真的執行該函式的案例，不只跑掃描守門
- grep 多個檔時逐檔看輸出來源，不把別檔的命中當成本檔有
- 新增守門腳本：同時把它加進 run_verify／量尺清單
