# 並行llm即時通訊-inbox機制

- Scope: global
- Author: holylight
- Source: commit:d823a10 2026-08-24（原對話已逾保留期）
- Confidence: [觀]
- Trigger: inbox機制, 並行LLM, 即時通訊, 跨session通訊, 檔案當信箱, 並行分工, grok協作, ai-inbox, 斷線喚回, monitor喚醒, compat hooks, to-opus, to-fable
- Status: 通道運作中；面板 guardian 定調不依賴走 CLI；PostCompact 未驗
- Created-at: 2026-08-24
- Related: workflow-parallel-agents, handoff-綜觀品質與抗失真寫法, 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源, 跨session資訊失真機制與對策, 歸因早停-找到合理嫌疑機制就停止驗證, vscode-reload-對並行ai-session的影響, grok協作實戰認知-特質與監工分工手感, feedback-高速推進每步跨大-禁越執行越偏細節越耗時, 雙claude協作實戰認知-fable監工opus主力的分工手感, feedback-多session協作時主持端要派工問進度分工寫文件-不要只回信等信-閒置session要給解決問題的工作-文件分開寫再彙整, 根層與專案session對齊認知用root-link雙槽與tri-link三槽信箱-落專案inbox

## 知識

- [觀] 並行 LLM 即時通訊＝同機同時活著的 session 互傳訊息，與 handoff（前後任單向一次性）互補。
- [臨] Claude 對 Claude 目前用原生 SendMessage：ListAgents／`claude agents --json` 找地址，閒置的收件端自動開回合，crossSessionInbound=accept。`.ai-inbox\to-opus\`／`to-fable\` 在原生能即時送達後退場，舊信只當案卷。檔案信箱只留三種用途：案卷、跨人跨帳號（mailbox）、對象不是 Claude Code（Grok）。每封首行校準三項（目標／現況差／偏移）＋必有交付物或裁決、禁進度信，換了通道仍適用。
- [觀] Claude↔Grok 檔案信箱 `C:\Users\holylight\.grok\.ai-inbox\`（規則 `PROTOCOL.md`）：`to-grok\`／`to-claude\` 各自單寫、`NNN-slug.md` 一信一檔回信必填 re、`status-*` 不佔序號。喚醒雙側事件驅動（Claude 用 Monitor、Grok 用內建 monitor，2 秒級），reload 即死要重掛；reload 後 Grok 聲盲直到被使用者戳一句。
- [觀] Grok 韌性：`~\.grok\rules\ai-inbox.md` 自動載入（開場自檢重掛 monitor）＋`~\.grok\hooks\ai-inbox-status.json` 寫 sessionstart／end／postcompact 狀態檔（postcompact 未驗）。`[compat.claude] hooks=false` 設定層生效，但 hook 表仍列 19 條、是否真停 spawn 未證實。
- [觀] 判死：`sessionend` 非保證（硬殺不開火）；用「sessionend 後無新 start」或「新 start 且舊 id 對 ping 靜默逾 10 分」。VSCode Reload＝先起短命 session 再 resume 本尊（雙 sessionstart）。斷線救援：確認死了才 `grok.exe -p "..." --resume <id> --cwd c:\Users\holylight\.grok --always-approve --no-auto-update`。
- [觀] Grok 面板 MCP 連線非決定性、CLI／無頭穩定，根因未明已停追 → 面板寫 atom 一律 `python -m lib.atom_io_cli`（案卷 .ai-inbox 信 006-011）。Grok 預設會執行 `~\.claude\settings.json` 的 hooks；分層原則：atom 資料層共用、行為閘門各自。
- [觀] grok-guardian 紅線閘：`~\.grok\hooks\grok-guardian.py`+`.json`（PreToolUse deny，Grok 寫檔工具禁寫 `~\.claude\` 除 `memory\_staging\`），終端指令繞寫不擋。Grok hook stdin 用 `toolInput`、deny＝stdout `{"decision":"deny"}`；工具本名 `write`／`search_replace`。

## 行動

- 跟另一個 Claude Code session 說話：用 SendMessage，不開檔案信箱
- 跟 Grok 通信：寫 `to-grok\NNN-slug.md`，對方 monitor 自動叫醒；等回信靠 Monitor 通知不輪詢
- reload／重啟後先重掛自己監 Grok 信箱的 monitor；Grok 側要提醒使用者戳一句才會重掛
- 涉共用資源先發訊息打招呼再動手
