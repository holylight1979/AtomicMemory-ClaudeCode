# hook 內呼叫外部工具的四個坑-HOME覆寫下CLAUDE_DIR指錯-pythonw無stdio-5秒預算-探針要隔離global設定

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: PreToolUse, hook 子行程, CLAUDE_DIR, Path.home, HOME 覆寫, pythonw, stdout None, 5 秒, hook timeout, 探針, GIT_CONFIG_GLOBAL, 隔離測試, run_verify 並行, 假紅
- Created-at: 2026-09-03
- Related: repo-全面-lf-決策與守衛鏈, heredoc反斜線三連踩post-mortem-含反斜線的腳本一律write成檔再跑

## 知識

- [臨] hooks/wg_core.py 的 `CLAUDE_DIR = Path.home()/".claude"`：hook 在 HOME／USERPROFILE 被覆寫的環境（隔離探針、CI、別人的包裝器）會指到不存在的目錄。hook 要呼叫自家 tools/ 腳本時用 `Path(__file__).resolve().parents[N]` 定位，不要用 CLAUDE_DIR（pre_tool_use.py `_MERGE_TOOL` 已改）。
- [臨] settings.json 的 PreToolUse hook timeout 是 5 秒，整條閘門鏈共用；新閘若要 spawn 子行程，給自己絕對 deadline（check_merge_driver 是 2.5s）、每個子行程各自 timeout、逾時 fail-open 只留提示。Windows 上每個 git spawn 約 0.1 秒，一個工具內 30 次 spawn 就爆預算；用 `git cat-file --batch`、一次 `git add` 多檔把 spawn 數壓到個位數。
- [臨] hook 在 pythonw 下跑，子行程的 sys.stdout/stderr 可能是 None：被 hook 叫的 CLI 要用容錯的 `_out()`，別直接 print；且 `sys.executable` 會是 pythonw.exe，寫進 git config 當 driver 會讓診斷全消失（映射到同目錄 python.exe）。
- [臨] 真 hook 進程探針：餐 JSON 進 hooks/workflow-guardian.py stdin，env 設 GIT_CONFIG_GLOBAL／XDG_CONFIG_HOME／GIT_CONFIG_NOSYSTEM 隔離，但 HOME 不要覆寫（會碰到第一點）。全套 run_verify 別與其他 pytest／探針並行：Windows 目錄移除競態會讓 atom_categorize undo 類測試假紅，量時間的預算題也會被拖慢（已改量兩次取最快）。

## 行動

- 新 hook 閘要叫自家工具：檔案相對定位、Windows-safe wrapper（capture、UTF-8、CREATE_NO_WINDOW、timeout）、給絕對 deadline；用真 hook 進程探針驗一次，不只直呼函式
- 全套 verify 單獨跑；偵到單跑會過的紅燈先排除並行負載再判
