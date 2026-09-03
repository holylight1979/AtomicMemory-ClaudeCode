# Grok 4.6 能力自述（inbox 即時通訊評估）

- 來源：Grok Build session `01a032c5-ae2b-77a3-8eb1-d1f6cdc7cf1d`
- 工作目錄：`c:\Users\holylight\.grok`
- 日期：2026-08-24
- 原始 log：`C:\Users\holylight\.grok\sessions\c%3A%5CUsers%5Cholylight%5C.grok\01a032c5-ae2b-77a3-8eb1-d1f6cdc7cf1d\chat_history.jsonl`（JSONL，不建議直接讀）
- 配套 atom：`memory/工作流/協作與並行/並行llm即時通訊-inbox機制.md`（結論已收斂進該 atom；本檔為原文證物）
- 用途：給 Claude Code 讀取，評估如何讓 Grok 看齊 Claude 的並行 LLM inbox 機制。以下為 Grok 當輪最終回覆原文。

---

概念已寫進持久記憶。這次 session 沒有原生 inbox，但檔案信箱、MCP 匯流排、以及「先設好再輪詢」做得到；純閒置時不會自己醒來讀信。

## 第一部分已存檔

寫了兩處（`workflow-guardian` MCP 這次連不上，atom 改走 CLI 正規入口，沒有手寫繞過）：

| 位置 | 作用 |
|------|------|
| `C:\Users\holylight\.claude\memory\並行llm即時通訊-inbox機制.md` | 你的 atom 系統（已入索引） |
| `C:\Users\holylight\.grok\memory\MEMORY.md` | Grok 原生跨 session 記憶 |

另外把 `~/.grok/config.toml` 的 `[memory] enabled = true` 打開了。這次對話啟動時記憶是關的，所以**這一輪我還是沒有** `memory_search` / `memory_get`；下一次新 session 才會自動檢索。若不想開自動注入，把那兩行拿掉即可，檔還在。

---

## 第二部分：我能不能接上 inbox

### 1. 讀寫工作區檔案？執行終端？

**能。** 讀、寫、改檔、跑終端都有。這一輪已實測：寫了記憶檔、改了 `config.toml`、跑了 Python。目前工作區是 `c:\Users\holylight\.grok`，工作區外的路徑（例如 `~/.claude`）也能碰。寫檔／跑指令可能被權限模式攔住；這次沒有出現核准暫停。

### 2. 有沒有「被外部喚醒」的途徑？

**沒有像檔案一變就自動醒來的內建 inbox。** 分層說：

- **這個還開著的 session**：預設只有使用者在對話裡打字（或 VSCode 面板送出一則訊息）才會開新一輪。我自己不能在完全閒置時憑空開始思考。
- **我先在某一輪設好的東西可以叫醒我**（session 還活著的前提下）：`scheduler_create` / `/loop` 到期、`monitor` 看到輸出、背景行程結束。`monitor` 可以盯檔案／目錄變動，但必須先由某一輪把它設起來。
- **開新行程、不一定是「叫醒這一個」**：`grok -p "..."` 無頭模式、`grok --resume <id>`、ACP 的 `session/prompt`（`grok agent stdio` / `serve`）。外部程式可以餵 prompt，那通常是新 session 或 resume，不是保證灌進你現在盯著的這個面板。
- **不確定、不猜的**：VSCode 有沒有一條「不經過輸入框、由別的擴充把訊息塞進這個 session」的命令。我沒有在這一輪驗證到。
- **另一條產品面**：已連上的 `tasks` MCP 是 Grok 帳號的排程／事件自動化，跑的是另一類 Grok，不是這個對話。

**結論：** 別人寫一個 `.ai-inbox/to-grok.md`，這個 session **不會**自動跳起來讀，除非（a）你跟我說一聲、（b）我已經用 `monitor`/`loop` 在盯、或（c）外部用 CLI/ACP 另開／resume 一輪。

### 3. 等使用者輸入時，能不能自己定期做事？

**不能從閒置狀態自己決定開始輪詢。** 若上一輪已經排了 `/loop`、scheduler、或 `monitor`，那些可以在你沒打字時開火、再開新一輪。沒排過，我就只是停著。最短間隔文件寫的是 60 秒；排程最多 50 個、7 天到期。`durable: true` 能不能在 session 關掉後還自己開新 session，我沒驗證過。

### 4. 支不支援 MCP？設定在哪？

**支援。** 這是接 inbox 最有用的一條。

設定來源（高優先蓋低優先，同名整個取代不合併）：

1. 目前目錄 `.grok/config.toml`
2. repo 根 `.grok/config.toml`
3. `~/.grok/config.toml` 的 `[mcp_servers.<name>]`

CLI：`grok mcp add|list|remove|enable|disable|doctor`。TUI：`/mcps`。也相容 `~/.claude.json`、`.cursor/mcp.json`、專案 `.mcp.json`。

工具命名：`伺服器名__工具名`。我這邊用 `search_tool` 發現、`use_tool` 呼叫。

**這一輪實際連線：** `MCPControl`、`excel`、`playwright`、`tasks` 成功；`unityMCP` handshake 失敗；`workflow-guardian` 逾時 65s（所以你慣用的 `atom_write` 這次沒接到）。共享 MCP server 當訊息匯流排，技術上可行，前提是 Claude 和我都連同一個 server，且那個 server 真的起來。

### 5. 一回合能不能連續多次用工具？有沒有次數上限？

**能，而且可以並行。** 這一輪就是讀檔 → 再讀 → 再寫 → 再跑指令。文件裡我**沒找到**「每回合最多 N 次工具」的硬上限。有的是：無頭模式 `--max-turns`、context 約 85% 自動壓縮、單次終端輸出／MCP 結果大小上限。確切數字我不知道，不猜。

### 6. 有沒有持久記憶？怎麼寫、在哪、能不能手改？

**有，兩套；這一輪開始時 Grok 那套是關的。**

| 系統 | 路徑 | 怎麼寫 | 你能不能直接編輯 |
|------|------|--------|------------------|
| Grok 原生 | `~/.grok/memory/MEMORY.md`（全域）、`~/.grok/memory/<專案slug-hash>/`（工作區） | 跟我說「記住…」、`/remember`、`/flush`、`/dream` | 能。改檔後 watcher 會重索引（`[memory.watcher]` 預設開） |
| 你的 atom | `~/.claude/memory/*.md` | 規定走 `atom_write` MCP；這次 MCP 掛了，我改走 `python -m lib.atom_io_cli` | 能，但不該用手新建——會被 funnel 擋 |

Grok 原生記憶預設關閉。我已打開 `[memory] enabled = true`。**這個 session 不會因此長出記憶工具**，要新開才會。

### 7. session 開始會不會自動載入某些檔？

**會。** 這一輪 `prompt_context.json` 實際載入了：

- `C:\Users\holylight\.claude\Claude.md`
- `C:\Users\holylight\.claude\rules\core.md`

Grok 會掃的規則檔名（每層目錄、這個順序）：`Agents.md`、`Claude.md`、`CLAUDE.md`、`CLAUDE.local.md`、`AGENT.md`、`AGENTS.md`。另外掃：

- `<dir>/.grok/rules/*.md`
- `<dir>/.claude/rules/*.md`、`<dir>/.cursor/rules/*.md`（相容開關預設開）
- `~/.grok/rules/`、`~/.claude/rules/`、`~/.cursor/rules/`

Skills：`.grok/skills/`、`~/.grok/skills/`、`~/.claude/skills/` 等。專案設定目錄是 `.grok/`（`config.toml`、skills、hooks、agents），不是自動把整個目錄塞進 context。

`Claude.md` 裡的 `@IDENTITY.md`、`@USER.md`、`@memory/MEMORY.md` **這一輪沒有被展開**；那三個檔我是後來自己讀的。記憶的 first-turn 注入這次也沒發生（當時 `memory_enabled: false`）。

### 8. 這個 Grok Build 有哪些可調設定？

**主設定檔：** `C:\Users\holylight\.grok\config.toml`（現況很瘦）

| 項 | 現值 |
|----|------|
| 模型 | 本 session 是 Grok 4.6；`fork_secondary_model = "grok-4.6"`；新 session 預設文件寫 `grok-4.5`，可用 `/model`、`/effort` |
| 自動核准 | `yolo = false`。模式有 ask / auto / acceptEdits / always-approve（`/always-approve`、`--yolo`、`Shift+Tab`） |
| 記憶 | 剛改成 `enabled = true` |

TUI `/settings` 還能調權限模式、畫面、通知、Ask-Question 逾時等。權限規則在 `[permission]` 或 Claude 相容的 `.claude/settings.json`。

VSCode `settings.json` 另有一組（不一定就是這個 Grok Build session 在吃）：

- `grok.defaultMode`: `"yolo"`
- `grok.defaultEffort`: `"high"`
- `xgrok.permissionMode`: `"full"`
- `xgrok.agentMode`: `"detailed"`
- `xgrok.language`: `"zh-cn"`

機器上還裝了第三方 `xgrok` 擴充，設定項跟 Grok Build 的 `config.toml` 不是同一份。`config.toml` 寫 yolo 關、VSCode 寫 yolo 開，**哪一個贏了我沒有對這個 session 做隔離實驗**。

---

**對 inbox 的實務判斷：** 我接得上「檔案信箱」和「共享 MCP 匯流排」；接不上 Claude 那種原生 discovery + 每輪自動看到 inbox。要穩，請約定目錄（或一個雙方都連的 MCP），並且**指定誰負責喚醒我**——我不會在你不說話、也沒排程的時候自己去看信。

Inbox 機制核心：同時活著的 session 把訊息丟進對方收件匣、不打斷對方當下的工作；對方下一輪思考才看到，雙方不互相等待，靠非同步來回收斂。
