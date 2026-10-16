# hook 內呼叫外部工具的四個坑-HOME覆寫下CLAUDE_DIR指錯-pythonw無stdio-5秒預算-探針要隔離global設定

- Scope: global
- Author: holylight
- Source: commit:549fccd 2026-09-03（原對話已逾保留期）
- Confidence: [臨]
- Trigger: PreToolUse, hook 子行程, CLAUDE_DIR, Path.home, HOME 覆寫, pythonw, stdout None, 5 秒, hook timeout, 探針, GIT_CONFIG_GLOBAL, 隔離測試, run_verify 並行, 假紅, 背景量測, 手動指令, 閱讀路徑量尺
- Created-at: 2026-09-03
- Related: repo-全面-lf-決策與守衛鏈, heredoc反斜線三連踩post-mortem-含反斜線的腳本一律write成檔再跑, svn測試與hook的三個實測事實-diff3相鄰改動自合-整wc-status爆預算-只信xml輸出, 真hook子行程探針只設wg-claude-dir隔離不了守門紀錄-guard-log-dir固定家目錄-要再帶wg-test-logs-dir與home-userprofile
- Quote: 「<pasted_content id="b168"> 接續「收尾少空轉」第二波（上一波已推 main：ebd44e6c、a9e9f862）。目標：收尾流程不再讓模型為了同一件事反覆重跑測試、反覆多花回合。這波做三件： 1. 閱讀路徑量尺移出收尾當下：根層 repo 3 秒內永遠量不完（兩天 11/11 逾時），量不完時還把「手動指令」塞進擋下訊息，模型會接單去跑。改成背景量、結果留到下次收尾附上…」

## 知識

- [臨] hooks/wg_core.py 的 `CLAUDE_DIR = Path.home()/".claude"`：hook 在 HOME／USERPROFILE 被覆寫的環境（隔離探針、CI、別人的包裝器）會指到不存在的目錄。hook 要呼叫自家 tools/ 腳本時用 `Path(__file__).resolve().parents[N]` 定位，不要用 CLAUDE_DIR（pre_tool_use.py `_MERGE_TOOL` 已改）。
- [臨] settings.json 的 PreToolUse hook timeout 是 5 秒，整條閘門鏈共用；新閘若要 spawn 子行程，給自己絕對 deadline（check_merge_driver 是 2.5s）、每個子行程各自 timeout、逾時 fail-open 只留提示。Windows 上每個 git spawn 約 0.1 秒，一個工具內 30 次 spawn 就爆預算；用 `git cat-file --batch`、一次 `git add` 多檔把 spawn 數壓到個位數。
- [臨] hook 在 pythonw 下跑，子行程的 sys.stdout/stderr 可能是 None：被 hook 叫的 CLI 要用容錯的 `_out()`，別直接 print；且 `sys.executable` 會是 pythonw.exe，寫進 git config 當 driver 會讓診斷全消失（映射到同目錄 python.exe）。
- [臨] 真 hook 進程探針：餵 JSON 進 hooks/workflow-guardian.py stdin，env 設 GIT_CONFIG_GLOBAL／XDG_CONFIG_HOME／GIT_CONFIG_NOSYSTEM 隔離，但 HOME 不要覆寫（會碰到第一點）。全套 run_verify 別與其他 pytest／探針並行：Windows 目錄移除競態會讓 atom_categorize undo 類測試假紅，量時間的預算題也會被拖慢（已改量兩次取最快）。
- [臨] 第五坑（Stop 接閱讀路徑量尺）：hook 裡「同一批輸入只量一次」的快取鍵要涵蓋所有會改變「量不量得到」的狀態：只比檔案大小與時間，使用者只 git add 不改檔就會命中快取而漏量（要把還沒 git add 的清單併進鍵）；逾時過的根之後連 git 子行程都不起。
- [臨] 第六坑：工具成本比 hook 預算大一個數量級就不能在 hook 當下同步跑——根層 repo 閱讀路徑比較一次實測 56 秒、Stop 給 3 秒，兩天 11/11 逾時。現行做法：Stop 只交工作（寫工作檔、DETACHED 起背景行程、不等），背景只寫自己的結果檔、不碰 state（避開 write_state 競寫），之後的收尾收結果附一次；一個 session 同時一個背景工作，量測中又改的記 pending。量不完的訊息只寫原因、絕不附「手動：python …」——模型會把它當待辦去跑（一場跑了 5 次）。測試端：hooks/verify/conftest 每案把 _spawn_worker 換成不起行程，背景邏輯用同行程直接跑；逾時用假 run 丟 TimeoutExpired，不真睡。

## 行動

- 新 hook 閘要叫自家工具：檔案相對定位、Windows-safe wrapper（capture、UTF-8、CREATE_NO_WINDOW、timeout）、給絕對 deadline；用真 hook 進程探針驗一次，不只直呼函式
- 工具實際耗時超過 hook 預算 → 改背景跑、下次收結果，不在 hook 裡等；失敗訊息只寫原因不附可執行指令
- 全套 verify 單獨跑；偵到單跑會過的紅燈先排除並行負載再判
