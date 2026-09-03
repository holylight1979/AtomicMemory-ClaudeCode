# codex-log-bloat-analytics

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex, logs_2.sqlite, 日誌暴量, analytics, OTEL, app-server, codex 崩潰, codex 卡頓, --analytics-default-enabled
- Created-at: 2026-06-01
- Related: feedback-tooling-reliability, toolchain

## 知識

- [臨] VSCode ChatGPT 擴充以 `codex.exe app-server --analytics-default-enabled` 啟動；關面板≠關進程，app-server 會在背景常駐持續寫 log（誤判為『node crash 寫 2.2GB』的真兇）
- [臨] 暴量源頭=Codex 內建 DEBUG/TRACE + OpenTelemetry 遙測狂寫 `~/.codex/logs_*.sqlite`；OTEL(opentelemetry_sdk + codex_otel.*) 約佔 69% 列數
- [臨] 源頭治本(官方文件 developers.openai.com/codex/config-advanced/#metrics)：config.toml 加 `[analytics]` 下 `enabled = false` 覆寫 --analytics-default-enabled；此為 core 設定不受 hook trust 影響
- [臨] 出口封頂：寫進已受信任的 Stop hook(context_watch.py)，超 50MB 就 trim 到最近 N 列 + wal_checkpoint(TRUNCATE) + incremental_vacuum；改 .py 內文不動 hooks.json → 不觸發重新信任(trusted_hash 鍵在 hooks.json 條目非 .py 內容)
- [臨] 診斷術：logs_2.sqlite 的 process_uuid 欄=寫入進程 pid，比對運行中 codex.exe 即坐實兇手；砍進程後看 WAL 是否停止增長=活體確認
- [臨] ⚠真正重災源（靈 logs_2.sqlite analytics，是另一條）：把 Claude 的 workflow-guardian-mcp/server.js 掛進 Codex 當 MCP。Codex 以 stdio 啟動 node → 協議不相容每 tick throw → server.js uncaughtException handler 「記 log 却不 exit」→ ~95% CPU 自旋迴圈狂 append guardian-crash.log → 114GB(2026-05) 壞軌 / 2.2GB(本次)
- [臨] 證據：C:\Projects\.codex\perf-samples\samples_foreground_*.csv 錄到 Codex 跨跨 server.js 持續 95% CPU。Python 端 10MB rotation 只在 Claude SessionStart 跑、Codex 不觸發 → 攛不住
- [臨] 修法(server.js:22-67)：crashLog 加 5MB 硬上限(超限 truncate 非 append) + uncaughtException/unhandledRejection 改走 onFatal，同進程累計 20 次 fatal 就 process.exit(1) 斷自旋 + SIGTERM/SIGINT 改為真正 exit（原本只記 log 不死→遗留殺不掉的孤兒 node）
- [臨] 通則：寫給外部 host(Codex) 啟動的 node 崩潰 handler 必須 (1)有檔大小上限 (2)崩潰後 exit 交給 supervisor，不可 log-and-continue；不能依賴 Claude-only 的 SessionStart rotation
- [臨] ⚠隱藏地雷：config.toml 頂層 legacy `profile="x"` + `[profiles.*]` 區段在 Codex 0.134+ 會讓**整份 config 載入失敗**、fallback 預設→所有設定（含 model/sandbox/mcp_servers/[analytics]）全被忽略。後果：先前加的 analytics 關閉「看似有改」其實根本沒生效
- [臨] 診斷：`codex doctor` 看 `✓ config loaded / parse ok`；`codex mcp list` / `features list` 若報 legacy profile 錯 = config 載不起來。修法：刪頂層 profile= + [profiles.*]，有用鍵併入頂層（VSCode app-server 不帶 -p，唯頂層生效）
- [臨] Codex 變聰明的槍桿：model_reasoning_effort=xhigh + model_reasoning_summary=auto + AGENTS.md（非 CLAUDE.md）+ developer_instructions；安全姿態 sandbox_mode/approval_policy。遙測三關：[analytics] enabled=false + [feedback] enabled=false + [otel] exporter=none

## 行動

- 關 Codex 後仍暴量 → Get-CimInstance 找背景 codex.exe（父進程多為 Code.exe，勿砍），Stop-Process 該 codex.exe
- 治本：config.toml [analytics] enabled = false
- 防復發：Stop hook 加 logs_*.sqlite size cap(trim+incremental_vacuum)，勿改 hooks.json 以保信任
- 清現有：codex 進程死後對 logs_*.sqlite trim + VACUUM(auto_vacuum 預設已 INCREMENTAL)
- 副帶：config.toml 頂層 profile= 在 codex 0.135+ 已棄用會被忽略，改用 -p / <name>.config.toml
