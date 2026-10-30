# 無頭探針驗skill行為-claude-p加setting-sources-project與strict-mcp-config不載使用者層hook與mcp

- Scope: global
- Author: holylight
- Source: 2026-10-22 dev-residue 減量實測；2026-10-23 斷路器修補實測；2026-10-23 state 讀改寫握鎖修補實測；2026-10-23 第二意見等待修補實測；2026-10-23 判分修補實測
- Confidence: [臨]
- Trigger: 無頭探針, claude -p, --setting-sources project, --strict-mcp-config, skill 行為實測, stream-json, 探針不寫 live, 無頭實跑工作樹 hook, --no-session-persistence, Not logged in, WG_CLAUDE_DIR, transcript 路徑不存在, --settings 合併不取代, project,local, --mcp-config, --resume 兩回合, projects slug, enabled=false, 包裝 hook, 受測 AI 不呼叫工具就收尾, ensure-mcp.py, user-init.sh, rmtree 唯讀, 排除詞判不出完成, CLAUDE_EFFORT, 子行程繼承環境變數, ListAgents
- Created-at: 2026-10-22
- Related: 無頭受測要關掉全部hook用claude-settings的disableallhooks旗標-hooks只來自使用者層settings-資料根放空settings不生效, git-bash傳斜線開頭參數給windows原生程式會被轉成路徑-例claude-p的slash指令-msys-no-pathconv只能加在那一次呼叫-全域export會讓python讀不到斜線c路徑
- Quote: 「施工agent若能多開就多開，提速吧」

## 知識

- [臨] 實測 skill／設定效果又不讓使用者層 hook 寫進正式資料：暫存目錄放 `.claude/skills/<探針>/SKILL.md`，跑 `claude -p "<問題>" --setting-sources project --strict-mcp-config --no-session-persistence --model <小模型> --output-format stream-json --verbose`（不掛使用者層 hook、不載使用者 MCP），讀 tool_use／tool_result。
- [臨] Git Bash 傳 / 開頭參數只在該次呼叫加 MSYS_NO_PATHCONV=1；claude.exe 不在 PATH 用 tools/codex-companion/judge_backend.resolve_claude_bin。
- [臨] 配方一（跑工作樹 hook）：暫存專案 .claude/settings.json 把 hook 指到工作樹 hooks/workflow-guardian.py＋`--setting-sources project --strict-mcp-config --permission-mode bypassPermissions`；`--settings` 與使用者層合併不取代，用它要配 `--setting-sources project,local`（事件、matcher、timeout 照抄 live），`--strict-mcp-config` 配 `--mcp-config`（本樹 hooks/run-hidden.py 包 node 跑本樹 server.js，env 帶 WG_CLAUDE_DIR）。只把 WG_CLAUDE_DIR、WG_TEST_LOGS_DIR 指到 repo 外暫存（repo 內會被背景同步提交），測 v6 加 WG_V6=1。範本：C:\Users\holylight\.claude-wt\_evidence\track-locate-batch-pickone\run_headless.py。
- [臨] 配方二：資料根 config 設 enabled=false 讓 live hook 退出，`--settings` 掛包裝 hook 把 load_config 的 enabled 蓋回 true 再跑工作樹 dispatcher。
- [臨] 受測專案不掛 ensure-mcp.py（合併 ~/.claude.json）、user-init.sh（寫 ~/.claude/USER.md）；資料根用種子複本；C:\w4 的 .git 物件唯讀，rmtree 先 chmod。設定目錄用 live 的（HOME／CLAUDE_CONFIG_DIR 指暫存會 Not logged in）。
- [臨] 子行程會繼承 CLAUDE_EFFORT、CLAUDE_CODE_ENTRYPOINT、CLAUDE_CODE_MESSAGING_SOCKET／TOKEN、CLAUDE_CODE_SESSION_ID，effort 與入口跟著本 session 走，開前先清。受測 session 出現在 ListAgents，別的 session 點名一次就多一則同伴訊息和回覆、那跑作廢；量測期間別對受測目錄的 session 寄信。
- [臨] 驗靠 transcript 的閘或 --resume 兩回合不能加 --no-session-persistence（hook 拿到的 transcript 路徑不存在）；不加時紀錄寫進 live ~/.claude/projects/<slug>/：前後比目錄數與 git status，跑完 jsonl 移暫存、只刪符合自己名字樣式的 slug。
- [臨] 開場「接公司記憶」會讓受測 AI 不呼叫工具就收尾，prompt 開頭明講免接、直接做；收尾含「中途」「還沒」判不出完成，必要時 --resume 請它直接說完成。

## 行動

- 實測 skill／設定效果：暫存目錄放專案層 skill，claude -p 加 --setting-sources project --strict-mcp-config 跑，讀 tool_use／tool_result
- 無頭實跑 hook：設定目錄用 live、只換 WG_CLAUDE_DIR／WG_TEST_LOGS_DIR；驗靠 transcript 的閘不加 --no-session-persistence，跑完搬走並刪自己的 slug
- 開受測子行程前清掉 CLAUDE_EFFORT 與 CLAUDE_CODE_* 繼承變數；量測期間不對受測 session 寄信；prompt 開頭明講免接公司記憶、直接用工具做
