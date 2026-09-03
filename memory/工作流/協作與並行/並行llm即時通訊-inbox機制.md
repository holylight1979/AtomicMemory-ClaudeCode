# 並行llm即時通訊-inbox機制

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: inbox機制, 並行LLM, 即時通訊, 跨session通訊, 檔案當信箱, 並行分工, grok協作, ai-inbox, 斷線喚回, monitor喚醒, compat hooks
- Status: 通道運作中；面板 guardian 定調不依賴走 CLI；PostCompact 未驗
- Created-at: 2026-08-24
- Related: workflow-parallel-agents, handoff-綜觀品質與抗失真寫法, 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源, 跨session資訊失真機制與對策, 歸因早停-找到合理嫌疑機制就停止驗證, vscode-reload-對並行ai-session的影響, grok協作實戰認知-特質與監工分工手感, feedback-高速推進每步跨大-禁越執行越偏細節越耗時, 雙claude協作實戰認知-fable監工opus主力的分工手感

## 知識

- [觀] 並行 LLM 即時通訊＝同機同時活著的 session 互傳訊息；三件套＝發現 / inbox（不打斷、下輪才見）/ 非同步。與 handoff（前後任單向一次性）互補。
- [觀] 已部署 Claude↔Grok 檔案信箱 `C:\Users\holylight\.grok\.ai-inbox\`（規則見 `PROTOCOL.md`）：`to-grok\`/`to-claude\` 各自單寫、`NNN-slug.md` 一信一檔回信必填 re、`status-*` 不佔序號。案卷＝信件原檔。
- [觀] 喚醒雙側事件驅動免 cron（Claude 用 Monitor、Grok 用內建 monitor，實測 2 秒級）；雙方 monitor 綁活 session，reload 即死要重掛。已知限制：reload 後 Grok 聲盲直到被使用者戳一句（rules 自檢才重掛），自然互動即自癒。Grok 韌性：`~\.grok\rules\ai-inbox.md` 自動載入＋`~\.grok\hooks\ai-inbox-status.json` 寫 sessionstart/end/postcompact 狀態檔（postcompact 未驗）。
- [觀] 判死：`sessionend` 非保證（硬殺不開火）；用「sessionend 後無新 start」或「新 start 且舊 id 對 ping 靜默逾 10 分」。VSCode Reload＝先起短命 session 再 resume 本尊（雙 sessionstart），不是兩個對手。
- [觀] 斷線救援：面板確認死了才 `grok.exe -p "..." --resume <id> --cwd c:\Users\holylight\.grok --always-approve --no-auto-update`（無頭新 session 實測綠；--resume 對活 id 未測勿試）。
- [觀] guardian MCP 案結論：Grok 面板 session 連線非決定性（同條件 reload 紅→綠→紅）、CLI/無頭穩定綠；曾後的兩輪歸因（wrapper std handle、hooks spawn 風暴）均被後續證據推翻/降級，根因未明、停止追查 → 定調：面板 MCP 不依賴，面板寫 atom 一律 `python -m lib.atom_io_cli`。案卷：.ai-inbox 信 006-011。
- [觀] 跨 harness 相容層風險：Grok 預設執行 `~\.claude\settings.json` 的 hooks（注入類 observe-only 無效＝白跑＋墯 state 風險）；`[compat.claude] hooks=false` 設定層生效但 hook 表仍列 19 條、是否真停 spawn 未證實。分層原則：atom 資料層共用；行為閘門各自（grok-guardian 若做只做 PreToolUse deny＋Stop block）。
- [觀] grok-guardian 紅線閘已落地：`~\.grok\hooks\grok-guardian.py`+`.json`（PreToolUse deny，Grok 寫檔工具禁寫 `~\.claude\` 除 `memory\_staging\`），無頭探針三發實證（核心區 deny、兩合法區放行）；fail-open+stderr 留痕；已知邊界：終端指令繞寫不擋。Grok hook stdin 用 `toolInput`、deny＝stdout `{"decision":"deny"}`；工具本名 `write`/`search_replace`。
- [臨]（2026-08-25）第二通道實戰：`c:\Users\holylight\.grok\.ai-inbox\to-opus\`（Fable 寫）／`to-fable\`（Opus 寫），規則與 Grok 通道同（PROTOCOL.md 末段）；一夜 12 封來回跟完八包。每封信首行校準三項（目標／現況差／偏移）＋必有交付物或裁決，禁進度信——有效防飄。資源通知用 `status-notice-*.md`（不佔序號）宣告「我要佔 port 4321／上實機」。Grok 通道待命未動（最後 to-claude\085）。

## 行動

- 跟 Grok 通信：寫 `to-grok\NNN-slug.md`，對方 monitor 自動叫醒；等回信靠 Monitor 通知不輪詢
- reload/重啟後先重掛自己的 monitor；Grok 側要提醒使用者戳一句才會重掛
- status-* 對帳判生死；確認死了才 --resume
- 涉共用資源先寄信打招呼再動手
