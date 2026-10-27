# 錄製重播的兩個假象-核對失敗被fail-open吞掉測試照綠-跨案共用的session帳本讓錄製檔依執行順序

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 錄製重播, CassetteMismatch, fail-open, except Exception, 單跑會紅, 依執行順序, aec_ledger, 產出物帳本, 跨案殘留, untracked 錄製檔
- Created-at: 2026-10-16
- Related: hook-內呼叫外部工具的四個坑-home覆寫下claude-dir指錯-pythonw無stdio-5秒預算-探針要隔離global設定
- Source: session:eefb3380 2026-10-16
- Quote: 「<pasted_content id="b168"> 接續「收尾少空轉」第二波（上一波已推 main：ebd44e6c、a9e9f862）。目標：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合。這波做三件： 1. 閱讀路徑量尺移出收尾當下：根層 repo 3 秒內永遠量不完（兩天 11/11 逾時），量不完時還把「手動指令」塞進擋下訊息，模型會接單去跑。改成背景量、結果留到下次收尾附上…」

## 知識

- [臨] 假象一：受測程式裡 fail-open 的 `except Exception` 會吞掉 git_cassette 的 CassetteMismatch（它是 AssertionError 子類），那一步照「查不到」的退路走，測試照樣綠。實例：verify_stop_reconcile g12w「沒改程式碼不附」靠 `_drop_synced` 吞掉核對失敗、退回「照算未同步」才過；真 git 重錄後前置不成立（.md 早已 commit、被 SYNC_BLOCK_SKIPS_SYNCED 剔除）才現形。Cassette.finish 只檢查呼叫數，不知道中途有過被吞的核對失敗。
- [臨] 假象二：hooks 的 per-session 帳本（handlers/aec_ledger 的 WORKFLOW_DIR/aec-tempfiles/<sid>.jsonl）在同一次 pytest 裡跨案共用（資料根整場一份、案例 session id 都一樣），前面案例的暫存 repo 留在帳上，後面每次收尾都去查它們的 git 狀態；auto 模式第一次沒有錄製檔就照這個順序錄下別案路徑，單跑那一案「錄製 30 筆、這次 0 筆」直接錯。hooks/verify/conftest.py 已每案給帳本自己的資料夾（放在受測目錄外）。
- [臨] 看到工作樹裡冒出 untracked 錄製檔：先解開看呼叫的路徑是不是都在這一案自己的 tmp 目錄；有別案路徑＝跨案殘留，刪掉、修隔離，不要 commit。

## 行動

- 改測試或受測程式的 git 互動後，單跑那一案確認錄製檔不依順序
- 受測程式的 fail-open 退路路徑上有 git 呼叫時，懷疑綠燈是吞掉核對失敗換來的：用 --git-record 重錄一次看前置
