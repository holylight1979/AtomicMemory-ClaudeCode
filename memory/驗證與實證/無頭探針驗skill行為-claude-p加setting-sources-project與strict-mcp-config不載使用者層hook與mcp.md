# 無頭探針驗skill行為-claude-p加setting-sources-project與strict-mcp-config不載使用者層hook與MCP

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測；2026-10-23 斷路器修補實測；2026-10-23 state 讀改寫握鎖修補實測；2026-10-23 第二意見等待修補實測；2026-10-23 判分修補實測
- Confidence: [臨]
- Trigger: 無頭探針, claude -p, --setting-sources project, --strict-mcp-config, skill 行為實測, stream-json, 探針不寫 live, 無頭實跑工作樹 hook, --no-session-persistence, Not logged in, WG_CLAUDE_DIR, transcript 路徑不存在, --settings 合併不取代, project,local, --mcp-config, --resume 兩回合, projects slug, enabled=false, 包裝 hook, 受測 AI 不呼叫工具就收尾, ensure-mcp.py, user-init.sh, rmtree 唯讀, 排除詞判不出完成
- Created-at: 2026-10-22
- Related: 無頭受測要關掉全部hook用claude--settings的disableAllHooks旗標-hooks只來自使用者層settings-資料根放空settings不生效, Git-Bash傳斜線開頭參數給Windows原生程式會被轉成路徑-例claude-p的slash指令-MSYS_NO_PATHCONV只能加在那一次呼叫-全域export會讓python讀不到斜線c路徑

## 知識

- [臨] 實測 skill／設定對模型的效果又不讓使用者層 hook 寫進正式資料：暫存目錄放 `.claude/skills/<探針>/SKILL.md`，在那裡跑 `claude -p "<問題>" --setting-sources project --strict-mcp-config --no-session-persistence --model <小模型> --output-format stream-json --verbose`（前者不掛使用者層 hook、後者不載使用者 MCP），讀輸出的 tool_use／tool_result。
- [臨] Git Bash 傳 / 開頭參數只在那次呼叫前加 MSYS_NO_PATHCONV=1；claude.exe 不在 PATH 用 tools/codex-companion/judge_backend.resolve_claude_bin 找。
- [臨] 無頭實跑工作樹的 hook（配方一）：暫存專案 .claude/settings.json 把各 hook 指到工作樹的 hooks/workflow-guardian.py，加 `--setting-sources project --strict-mcp-config --permission-mode bypassPermissions`。`--settings` 跟使用者層合併不取代，只加它 live 舊 hook 會一起跑；用 --settings 掛本樹 hook 要配 `--setting-sources project,local`（事件、matcher、timeout 照抄 live），`--strict-mcp-config` 配 `--mcp-config`：用本樹 hooks/run-hidden.py 包 node 跑本樹的 server.js（env 帶 WG_CLAUDE_DIR）。只把資料根 WG_CLAUDE_DIR、WG_TEST_LOGS_DIR 指到受版控 repo 外的暫存（放 repo 裡會被背景同步提交），測 v6 行為加 WG_V6=1。啟動腳本範本：C:\Users\holylight\.claude-wt\_evidence\track-locate-batch-pickone\run_headless.py。
- [臨] 配方二：資料根 config 設 enabled=false 讓 live hook 直接退出，`--settings` 掛包裝 hook 把 load_config 的 enabled 蓋回 true 再跑工作樹 dispatcher；不載 MCP 時資料根要關 verify_scope 與 overview_hub.need_goal。
- [臨] 受測專案不掛 ensure-mcp.py（會合併 ~/.claude.json）、user-init.sh（會寫 ~/.claude/USER.md）；資料根用種子複本、不動種子；C:\w4 的 .git 物件檔唯讀，rmtree 先 chmod。
- [臨] 設定目錄用 live 的：HOME／USERPROFILE 或 CLAUDE_CONFIG_DIR 指到暫存會回「Not logged in」（登入憑證跟著設定目錄走）。
- [臨] 驗靠 transcript 判斷的閘或跑 --resume 兩回合，不能加 --no-session-persistence（加了 hook 拿到的 transcript 路徑不存在，閘全退回舊判法）；不加時紀錄寫進 live 的 ~/.claude/projects/<暫存目錄 slug>/：跑前後比 projects 目錄數與 live git status，跑完 jsonl 移到暫存當證據、刪自己的 slug；並行實跑可能同時新建 slug，只動符合自己名字樣式的。
- [臨] --strict-mcp-config 讓 need_goal 這類 MCP 工具不在，改程式檔的題目會被擋到底；挑不改程式檔的題，或另載 MCP。
- [臨] 開場「接公司記憶」「先立目標樹」提示會讓受測 AI 一個工具都不呼叫就收尾；prompt 開頭明講「這題沒有目標樹工具、公司記憶不用接、直接用工具做」。收尾含「中途」「還沒」這類排除詞會判不出宣告完成、閘不觸發，必要時 --resume 補一回合請它直接說完成。

## 行動

- 實測 skill／設定效果：暫存目錄放專案層 skill，claude -p 加 --setting-sources project --strict-mcp-config 跑，讀 tool_use／tool_result
- 無頭實跑 hook：設定目錄用 live、只換 WG_CLAUDE_DIR／WG_TEST_LOGS_DIR；要驗靠 transcript 的閘就不加 --no-session-persistence，跑完搬走並刪掉 projects 下那個 slug 目錄
- 受測專案不掛 ensure-mcp.py、user-init.sh；資料根用種子的複本
- 受測 prompt 開頭明講不用接公司記憶、沒有目標樹工具、直接用工具做
