# codex裁判停用個別mcp用-c-mcp_servers名.enabled=false-mcp_servers空表是合併不是清空

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex exec, codex companion, rmcp, 8090, unityMCP, MCP 連線失敗, mcp_servers, --ignore-user-config, codex_extra_args, plan_review 逾時, assessment_timeout
- Created-at: 2026-09-10
- Related: codex-exec-唯讀沙箱在此機起不來-1385-改bypass並以git-status前後比對護欄, feedback-tooling-reliability, codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated

## 知識

- [臨] codex exec 啟動會連 ~/.codex/config.toml 全部 mcp_servers；掛掉的 HTTP server（如 unityMCP 127.0.0.1:8090）每次重試 3 次、stderr 噴 rmcp ERROR。只對裁判停用：`-c mcp_servers.<名>.enabled=false`（`codex mcp list` 可驗 Status=disabled）。`-c 'mcp_servers={}'` 是 TOML 合併不是清空，零效果。
- [臨] `--ignore-user-config` 也能跳過全部 MCP 且更快（8s vs 12s），但同時丟掉 sandbox_mode=danger-full-access／analytics.enabled=false 等使用者設定，裁判會落回 read-only 沙箱；companion 刻意不帶 -s 靠 config 沙箱，故不採。
- [臨] 本機 8090 = MCP for Unity（registry MCPForUnity.HttpUrl=8090、AutoStartOnLoad=1），只在 Unity Editor 開著時活；Codex 桌面版與 ~/.claude.json 都註冊，不是死服務，不可從 config.toml 移除。companion 走 workflow/config.json `codex_extra_args`（原樣附加到 codex exec）在裁判端停用。
- [臨] Codex CLI 0.154.0 起本機 `-s read-only` 可正常跑（0.144 時 CreateProcessWithLogonW 1385）；舊版跑 gpt-6-astra 被拒「需更新版」，`npm i -g @openai/codex@latest` 後過。
- [臨] assessor.py subprocess.run 只給 text=True 沒 encoding，cp950 主控台讀 codex stderr 的 UTF-8 會在 reader thread 炸 UnicodeDecodeError（log 滿版 traceback）；所有 subprocess.run(text=True) 一律配 encoding="utf-8", errors="replace"。

## 行動

- codex 啟動看到 rmcp ERROR → codex mcp list 找哪個 server 掛，裁判端用 -c mcp_servers.<名>.enabled=false，不動使用者 config.toml
- plan_review 連續逾時先查 Logs/codex-audit.log 有無 UnicodeDecodeError／rmcp 行，再調 assessment_timeout
- 驗法：smoke_plan_review.py <plan.md> 2>>Logs/codex-audit.log，看 attempts=1 且無 timed out
