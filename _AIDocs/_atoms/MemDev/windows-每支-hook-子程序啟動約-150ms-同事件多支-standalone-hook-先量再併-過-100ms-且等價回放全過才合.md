# Windows 每支 hook 子程序啟動約 150ms-同事件多支 standalone hook 先量再併-過 100ms 且等價回放全過才合

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: standalone hook, hook 合併, PostToolUse 延遲, python 啟動成本, settings.json hooks, hook 數量, version_guard, acceptance_spec, 事件等價回放, hook 效能
- Created-at: 2026-09-21

## 知識

- [臨] 2026-09-21 實測：PostToolUse 三支 hook（guardian＋version_guard＋acceptance_spec）並跑關鍵路徑中位 651.9ms，併成 guardian 一支 490.9ms，省 ≈161ms／每次 Edit·Write；Windows 上每個 Python 子程序啟動 ≈150ms，所以「同一事件掛幾支 hook」本身就是延遲來源，與各 hook 做什麼無關（兩支只 import stdlib）。merge-atom-index 同理：14 個序列 git 子程序是瓶頸，併行後 2.6s→1.5–2.0s。
- [臨] 合併判準與做法：先量三支並跑 vs 單支的真實延遲，省不到 100ms 不合；被併的 hook 改成 run(input_data, config) -> list[str] 模組、保留 __main__ 可獨跑；用事件等價回放測試（同一批 tool 事件，合併前後 systemMessage／additionalContext 逐筆相同）守等價；回滾＝settings.json 加回原區塊。已知語意差要寫進 CHANGELOG（guardian 總開關關掉時被併的也停）。
- [臨] 判斷為什麼會寫成這樣：新功能各自加一支 hook 最省事、也最不會互相干擾，成本是每支 150ms 的隱形稅，沒人量就沒人覺得慢。

## 行動

- 新增 hook 前：同事件已有 guardian handler 就寫成模組函式讓它呼叫，不另掛 settings.json 區塊
- 覺得 hook 慢：先數同事件掛幾支子程序，再看各支做什麼
