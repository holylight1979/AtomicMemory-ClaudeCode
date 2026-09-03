# 原子記憶系統 — AI 安裝指南

> **目標讀者**：Claude Code（或相容 AI 助手），代替使用者執行原子記憶系統的合併安裝。
> **若你是人類**：不建議逐步手作。開一個新 Claude Code session，貼 [README.md](README.md) 的「由 AI 全程代跑」prompt，讓 AI 照本檔執行。
> **版本**：以 `version.json` 為準（`guardian` 5.1.0 / `atom_memory` 5.1）。本檔與實碼衝突時以實碼為準，並回報「指南需更新」。

---

## 0. AI 執行守則（開工前必讀）

1. **每一步驗證，每一步回報**。每個 Step 結束告訴使用者「已做 X，接下來做 Y」。
2. **不覆蓋使用者現有設定**：`settings.json` 的 `permissions` / `env` / `statusLine`、`workflow/config.json` 的使用者自訂值、`USER-{user}.md`、`IDENTITY.md` 一律 merge，不 overwrite。
3. **缺套件不自行 pip install / npm i**：列出缺項 + 安裝指令給使用者，等使用者確認再裝。跨平台（Windows / Mac / Linux）指令要對。
4. **帳號密碼絕不主動寫入**：需要時問使用者，或請使用者自己編輯 gitignored 檔。
5. **路徑符號**：Windows 的 `~/.claude/` 實際是 `C:\Users\{user}\.claude\`。用 `pathlib.Path.home()` 或 bash `$HOME`。
6. **缺項不等於裝不了**：§1 每一項都有替代方案與降級行為。缺項只影響對應功能，不影響安裝主流程——先裝完、再回頭補缺項。

---

## 1. 前置需求與降級對照

### 1.1 總則：最壞情況也不會壞掉什麼

- 所有 hook 都是 **fail-open**：hook 自身出錯、逾時、依賴缺席 → 放行工具呼叫、在 stderr / SessionStart 訊息浮出訊號，不阻斷 Claude Code。
- **Claude Code 本體零修改**：系統只靠 `settings.json` 的 `hooks` 區塊、`~/.claude.json` 的 `mcpServers` 掛進去；拔掉這兩塊就回到原生。
- **最壞情況**（只有 Claude Code + Python）＝原生 Claude Code 只多一行 `[Workflow Guardian] Active`、多 trigger/BM25 純文字記憶注入；沒有向量搜尋、沒有 MCP 寫入工具、沒有 Dashboard、沒有 LLM 萃取與 AI 裁判。
- 降級狀態的可見訊號：statusline（`WG:?` 紅字＝Guardian state 壞、`vec✗`＝向量服務未就緒）、SessionStart 的 `[Guardian:*]` / `[Codex Companion]` / `[MCP]` advisory、`Logs/vector-service.log`。

### 1.2 自檢指令

**先全部跑過**再開始裝。結果整理成表回報使用者，缺項不要自己補。

| 項目 | 自檢指令 | 通過標準 |
|------|---------|---------|
| Claude Code | `claude --version`；或問使用者 VS Code 的 Claude Code 面板能否開 | 有 |
| Python | `python --version`（或 `python3`） | ≥ 3.10 |
| Node.js | `node --version` | 任意 LTS（≥ 18） |
| Git | `git --version` | 任意 |
| Ollama | `ollama --version` + `curl -s http://127.0.0.1:11434/api/tags` | 有 daemon 回應 |
| Ollama 模型 | `ollama list` | 含 `qwen3-embedding`、`qwen3:1.7b`、`gemma4:e4b` |
| Python 套件 | `python -c "import lancedb, sentence_transformers; print('ok')"` | 無 ImportError |
| Codex CLI | `codex --version`；再確認已登入（`codex login` 狀態） | 有且已授權 |
| Hook 直譯器路徑 | `python tools/fix-hook-python.py`（在 `~/.claude` 下跑） | 全數 `[OK ]` |

內網遠端 Ollama backend 補查：`curl -s <base_url>/api/tags` 連通；認證型 backend 的憑證走 gitignored 路徑。

### 1.3 逐項：用途 / 缺了怎麼辦 / 完全沒有時系統怎麼保證不壞

每項四欄：**用途**（系統哪部分靠它）→ **替代**（缺了怎麼辦）→ **降級**（完全沒有替代時，哪些功能少了、怎麼告知、不會壞掉什麼）。

**Claude Code**
- 用途：宿主。hooks / MCP / skills 全掛在它身上。
- 替代：無。本系統只服務 Claude Code。
- 降級：不適用。

**Python 3.10+**（hook 純標準函式庫）
- 用途：全部 hook（9 事件）、`lib/` atom 讀寫、`tools/` 全部工具、statusline。
- 替代：無，這是唯一硬依賴。`tools/fix-hook-python.py` 實跑候選直譯器驗版本，下限 3.9（`MIN_VERSION`）；本文件以 3.10 為安裝門檻。
- 降級：沒 Python → hook 指令執行失敗 → Claude Code 視為 hook 錯誤放行，原生功能完全不受影響；記憶系統整個不啟動。

**Node.js**（≥ 18，零 npm 依賴）
- 用途：只有兩處——MCP server `tools/workflow-guardian-mcp/server.js`（5 個 tool：`atom_write` / `atom_promote` / `atom_move` / `atom_edit_meta` / `anti_evasion_report`）與同進程的 Dashboard / HUD 網頁。
- 替代：atom 仍可經 Python 寫入——`lib/atom_io_cli.py` 是 stdin JSON 橋接（不是 argparse），在 `~/.claude` 下跑 `python -m lib.atom_io_cli`，stdin 餵 `{"action": "...", ...}`，action 有 `locate`（算落點）/ `build`（只組內容驗證，不落檔）/ `create_atom`（build→落檔→access→索引；`dry_run: true` 只預覽）/ `append` / `write_raw`。實務上建議直接用 `skills/memory` 與 `tools/` 內的 Python 腳本，或安裝 Node 後走 MCP。
- 降級：`hooks/ensure-mcp.py` 在 SessionStart 找不到 node → 寫 `workflow/mcp-needs-node.flag` 並結束，不註冊 MCP；`anti_evasion_report` 收尾檢核因 MCP tool 不存在而無法提交（Stop 閘為 fail-open，會放行）。hooks、注入、萃取全部照常。

**Git**
- 用途：Stop 同步閘（`hooks/handlers/stop.py` `_detect_uncommitted_files`）、SessionStart 未 push advisory、晉升自動 commit（`self_iteration.auto_commit_promotions`）、`hooks/post-git-pull.sh` pull 後稽核。
- 替代：SVN 工作區同樣被同步閘辨識（`.svn` 目錄）。
- 降級：`_detect_uncommitted_files` 對非 git/svn 目錄回 `None`＝**整個同步閘跳過**（不提醒也不阻斷）；git 執行檔不存在時 `git status` 拋 `FileNotFoundError` → 該組回 `None` → 同樣跳過。其餘閘門不受影響。

**Ollama（本地 daemon `http://127.0.0.1:11434`）**
- 用途：向量嵌入（`qwen3-embedding`）與所有 LLM 萃取（SessionEnd 全量萃取、失敗萃取、使用者決策萃取、episodic 摘要、`heal`）。**全域層檢索本來就不用它**（trigger + BM25 純 Python in-memory）。
- 替代 1：遠端 backend——`workflow/config.json` → `vector_search.ollama_backends`（priority 小者優先；三階段退避：正常 → Short DIE 60s → 10 分鐘內兩次 Short DIE 進 Long DIE，等到下個 6h 邊界；Long DIE 會在 SessionStart 問使用者要不要永久停用）。
- 替代 2：向量嵌入改走本地 `sentence-transformers` + `BAAI/bge-m3`（config 已預設 `fallback_backend` / `fallback_model`；需 pip 裝 `sentence-transformers`，冷啟動可到分鐘級）。
- 降級：兩者皆無 → `indexer.create_embedder` 拋 `RuntimeError`，向量服務起不來（`Logs/vector-service.log` 有證據、statusline `vec✗`、連續 3 session 未就緒時 SessionStart 出 `[Guardian:Vector⚠]`）；專案層檢索只剩 trigger/BM25；萃取類 `ollama_client` 全 backend 不可用回 `None` → 各萃取器跳過並落 atom-debug log / audit。Claude 顯式 `atom_write` 不受影響。

**Ollama 模型（三個，各自缺了影響什麼）**
- `qwen3-embedding`：向量嵌入。缺 → 走 bge-m3 fallback，再缺 → 向量層跳過（同上）。
- `qwen3:1.7b`：本地快篩 LLM（使用者決策萃取 L1、失敗分類等輕量判斷）。缺 → 該 backend 的 llm 請求失敗進退避，改試其他 backend；全無 → 該類萃取跳過。
- `gemma4:e4b`：主萃取 LLM（決策萃取 L2、SessionEnd 全量萃取）。缺 → 同上；全無 → 只剩 Claude 顯式寫入與失敗關鍵字偵測。

**Python 套件 `lancedb`（需 CPU AVX2）與 `sentence-transformers`**
- 用途：`lancedb`＝向量 DB（`memory/_vectordb/`）；`sentence-transformers`＝無 Ollama 時的本地嵌入。
- 替代：`lancedb` 無替代（config 的 `fallback_backend` 只管 embedder，不管 DB）；`sentence-transformers` 的替代就是 Ollama。
- 降級：`lancedb` 缺 → `service.py` 起不來 → `starter.py` 落 `Logs/vector-service.log`、statusline `vec✗`、SessionStart advisory；trigger/BM25 檢索照常。

**Codex CLI 與其授權**
- 用途：Codex Companion（`hooks/codex_companion.py`）的驗收裁判、計畫審查、handoff 自檢——跨廠 AI 審 AI，擁有 block 權。
- 替代：`tools/codex-companion/judge_backend.py` 自動退 headless `claude -p --model sonnet`（config `codex_companion.fallback`）；同廠獨立性降級，**預設只有 advisory 權**（`fallback.allow_block=false`）。codex 授權失敗（未登入 / 401 / 額度）落 `workflow/companion-backend.json` 抑制 24h（`reprobe_hours`）。
- 降級：codex 與 claude 都找不到 → heuristics-only，**SessionStart 揭露一次**（`[Codex Companion] 已停用：…`，每台機器一次）；本地 heuristics 軟閘與其餘 guardian 機制正常。不想要整個功能：`codex_companion.enabled=false`。

**Hook 直譯器路徑**
- 用途：`settings.json` 每條 hook 指令開頭都是**絕對路徑**的 Python（Windows 用 `pythonw.exe` 避免閃 console）。repo 內帶的是原作者機器的路徑。
- 替代：`python tools/fix-hook-python.py --write` 用「跑這行的這支 python」改寫全部 hook 與 statusLine 指令（備份 `settings.json.bak`）；`--use <path>` 指定他支。
- 降級：不校正 → 全部 hook 起不來 → 回到原生 Claude Code，無任何記憶功能，但也不會壞。**不要自作主張改成裸 `python`**：PATH 首位未必是預期那支。

---

## 2. 使用者常問問題

- 「**幫我確認必備套件沒漏？**」 → 跑 §1.2，逐項對照 §1.3 回報缺了會少什麼。
- 「**Python 3.9 可以嗎？**」 → 校正工具接受 3.9，但安裝門檻請以 3.10 為準。
- 「**沒 GPU 會慢嗎？**」 → Ollama 可 CPU（embedding 200–500 ms / qwen3:1.7b 1–3 s）；建議設遠端 GPU backend（§4.4）。
- 「**沒 admin 權限能裝嗎？**」 → 大部分能（Python / Node.js / Ollama 都有 user-local 安裝），pip 套件用 `--user`。
- 「**沒 Node / 沒 Ollama / 沒 Codex 能用嗎？**」 → 能，見 §1.3 各項降級。
- 「**沒看到 Guardian Active？**」 → `python tools/fix-hook-python.py` 看直譯器路徑；再檢查 `settings.json` hooks 是否合併進來。
- 「**MCP 的 `atom_write` 回 `cli parse fail: Unexpected end of JSON input`、stderr 空白？**」 → js 端呼叫的 Python 被 Windows 的 Microsoft Store 佔位 `python.exe`（`%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`，零輸出 exit 9009）攔走。MCP 啟動時自動找絕對路徑（`WG_PYTHON` 環境變數 → 常見安裝路徑 → 退回裸 `python` 並在 stderr 留 WARN）；非標準安裝位置請在 `~/.claude.json` 的 `mcpServers.workflow-guardian.env` 加 `"WG_PYTHON": "<python.exe 絕對路徑>"`（跟 hooks 用同一支），再 Reload Window。
- 「**整個移除？**」 → §8。Claude Code 本體零修改。

---

## 3. 安裝流程（合併安裝，不覆蓋既有設定）

記憶分兩層、**分別從版控拉取**；本流程只安裝根層，專案層不需安裝：

| 層 | 在哪裡 | 做什麼 | 從哪裡拉 |
|----|------|------|------|
| **根層** | `~/.claude`（本套件所在） | 對 Claude Code 本身做能力擴充；跨專案的根本知識住這裡 | 本套件的版控庫（本流程） |
| **專案層** | `{專案}/.claude/memory/` | 日常開發協作；AI 記得這個專案的決策與踩坑 | 各專案自己的 GIT / SVN，pull 即接上，**不需再安裝** |

### Step 0：備份

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.backup 2>/dev/null || true
cp ~/.claude.json ~/.claude.json.backup 2>/dev/null || true
```

### Step 1：取得 repo

兩種情境：
- **`~/.claude` 尚無任何內容** → 直接 `git clone <repo-URL> ~/.claude`，跳到 Step 3。
- **`~/.claude` 已有使用者設定** → clone 到暫存位置再合併：`git clone <repo-URL> /tmp/atomic-memory`（Windows 用 `$TEMP`）。

### Step 2：複製系統檔案（不動使用者個人資料）

全資料夾同步。使用者個人實例（`USER.md` / `USER-{user}.md` / `IDENTITY.md` / `IDENTITY-{user}.md`）一律保留。

> **啟動檔角色**：`CLAUDE.md` 只 `@IDENTITY.md` `@USER.md` `@memory/MEMORY.md`。`IDENTITY.md` 是直接維護的單一真相，`templates/IDENTITY.template.md` 是其備份／還原源（`hooks/user-init.sh` 缺檔時還原；`hooks/handlers/session_start.py` 完整性哨兵偵測被截斷時提醒），兩者需手動同步。`IDENTITY-{user}.md` 是選配個人擴充槽（啟用需在 `CLAUDE.md` 加 `@IDENTITY-{user}.md`），安裝與升級不經手。`USER-{user}.md` 是 USER 的編輯點，每 SessionStart 拷成 `USER.md`；不存在時從 `templates/USER.template.md` 建。`BOOTSTRAP.md` 不被 @import，是 IDENTITY/USER 為空時的問答引導模板。

```bash
SRC=/tmp/atomic-memory
DST=~/.claude

# 啟動文件（不覆蓋個人實例）
cp "$SRC/CLAUDE.md" "$DST/CLAUDE.md"
mkdir -p "$DST/templates"
cp "$SRC/templates/IDENTITY.template.md" "$DST/templates/"
cp "$SRC/templates/USER.template.md" "$DST/templates/"
cp "$SRC/BOOTSTRAP.md" "$DST/BOOTSTRAP.md"
[ ! -f "$DST/IDENTITY.md" ] && cp "$SRC/templates/IDENTITY.template.md" "$DST/IDENTITY.md"
cp "$SRC/version.json" "$DST/version.json"

# 核心模組（整資料夾覆蓋；不含個人 atom 與 runtime state）
rsync -a --delete "$SRC/hooks/" "$DST/hooks/"      # dispatcher + handlers/（9 事件）+ wg_*.py + 獨立 hook
rsync -a --delete "$SRC/lib/" "$DST/lib/"          # atom_io / atom_spec / atom_locations / atom_index_json / atom_access / realm_gate …
rsync -a --delete "$SRC/skills/" "$DST/skills/"    # <!-- skill-count -->21<!-- /skill-count --> 個 active skill + _archived/
rsync -a --delete "$SRC/rules/" "$DST/rules/"
rsync -a "$SRC/tools/" "$DST/tools/"               # 保留 user 自加

# Memory：只補骨架，不動已有 atom
mkdir -p "$DST/memory/_reference" "$DST/memory/_meta"
cp "$SRC/memory/_reference/"*.md "$DST/memory/_reference/" 2>/dev/null || true
cp "$SRC/memory/_meta/forbidden-phrases.json" "$SRC/memory/_meta/taxonomy.json" "$DST/memory/_meta/"
[ ! -f "$DST/memory/MEMORY.md" ] && cp "$SRC/memory/MEMORY.md" "$DST/memory/MEMORY.md"
[ ! -f "$DST/memory/_atom_index.json" ] && cp "$SRC/memory/_atom_index.json" "$DST/memory/_atom_index.json"

# Workflow 設定（不覆蓋既有）
mkdir -p "$DST/workflow"
[ ! -f "$DST/workflow/config.json" ] && cp "$SRC/workflow/config.json" "$DST/workflow/"

# MCP template + 知識庫文件
cp "$SRC/mcp-servers.template.json" "$DST/"
rsync -a "$SRC/_AIDocs/" "$DST/_AIDocs/"
```

> 已存在 `workflow/config.json` 時改執行 JSON merge（不覆蓋 user 設值），新欄位補預設。

### Step 3：合併 `settings.json` 的 `hooks` 區塊

**不要手抄 JSON 模板**（會漂移）。以 repo `settings.json` 的 `hooks` 區塊為準**整段合併**進使用者的 `settings.json`，保留 `permissions` / `env` / `statusLine` 等使用者原有欄位。合併結果應涵蓋下表（9 事件；hook 檔皆在 `hooks/`）：

| 事件 | matcher | 掛的 hook（timeout 秒） |
|------|---------|------------------------|
| SessionStart | — | `run-bash-hidden.py user-init.sh`(5) → `workflow-guardian.py`(8) → `ensure-mcp.py`(5) → `codex_companion.py`(5) |
| UserPromptSubmit | — | `workflow-guardian.py`(8)、`codex_companion.py`(3) |
| PreToolUse | `WebFetch` | `run-bash-hidden.py webfetch-guard.sh`(20) |
| PreToolUse | `Write\|Edit\|NotebookEdit\|Bash\|PowerShell\|Agent\|Task` | `workflow-guardian.py`(5) |
| PostToolUse | `Edit\|Write\|NotebookEdit\|Bash\|Agent\|Task\|mcp__workflow-guardian__anti_evasion_report` | `workflow-guardian.py`(5) |
| PostToolUse | `Edit\|Write\|Bash\|ExitPlanMode\|EnterPlanMode` | `codex_companion.py`(3) |
| PostToolUse | `Write\|Edit\|MultiEdit` | `version_guard.py`(5) |
| PostToolUse | `Write\|Edit\|NotebookEdit\|ExitPlanMode` | `acceptance_spec.py`(5) |
| PreCompact / PostCompact / PostToolBatch | — | `workflow-guardian.py`(5) |
| Stop | — | `workflow-guardian.py`(10)、`codex_companion.py`(150)、`lang_guard.py`(5) |
| SessionEnd | — | `workflow-guardian.py`(30)、`codex_companion.py`(5) |

> `workflow-guardian.py` 是 1 行 shim → `hooks/dispatcher.py` → `hooks/handlers/{event}.py`。指令型式為 `<絕對路徑 pythonw.exe> -c "import runpy,pathlib;runpy.run_path(str(pathlib.Path.home()/'.claude/hooks/xxx.py'),run_name='__main__')"`，bash 類 hook 經 `run-bash-hidden.py` 包一層。
> `statusLine` 也由 repo `settings.json` 提供（`tools/statusline.py`）；使用者已有 statusLine 時保留使用者的。

**合併後必做**：校正直譯器路徑（repo 內是原作者機器的絕對路徑）。

```bash
cd ~/.claude
python tools/fix-hook-python.py            # 只檢查：列出每處直譯器與是否存在
python tools/fix-hook-python.py --write    # 用「跑這行的這支 python」改寫（備份 settings.json.bak）
```

工具會實跑候選直譯器驗版本、`pythonw` 維持 w 版、已全部存在則零改動。Windows 以外的平台沒有 `pythonw`，工具會改成同一支 `python`。

驗證：
```bash
echo '{"hook_event_name":"SessionStart","session_id":"install-test","cwd":"'"$HOME"'"}' | python ~/.claude/hooks/workflow-guardian.py
```
預期輸出 JSON 含 `hookSpecificOutput.additionalContext`。

### Step 4：MCP 註冊（`~/.claude.json`）

`hooks/ensure-mcp.py` 每次 SessionStart 自動做這件事：找 node → 讀 `mcp-servers.template.json` → JS 入口存在的 server 合併進 `~/.claude.json` 的 `mcpServers`（缺整塊才補；已存在且 template `_version` 沒升則不動）→ npm 套件不在磁碟的 server 背景 `npm i -g`（下次 session 才寫入 config）→ 每 7 天背景 `npm outdated/update`。**手動合併只是保險**，正常情況開兩次 session 就齊。

template 內三個 server：

| 名稱 | 來源 | 入口 |
|------|------|------|
| `workflow-guardian` | repo 內建（`npm_package: null`） | `{claude_dir}/tools/workflow-guardian-mcp/server.js` |
| `MCPControl` | npm `computer-use-mcp` | `<npm 全域>/node_modules/computer-use-mcp/dist/main.js` |
| `playwright` | npm `@playwright/mcp` | `<npm 全域>/node_modules/@playwright/mcp/cli.js` |

手動合併規則（若使用者要立刻可用、不等下個 session）：
- entry 形式 `{"type":"stdio","command":"<node 絕對路徑>","args":["<入口絕對路徑>"]}`；**全域安裝 + 絕對路徑**，不要 `cmd /c npx`。
- npm 全域位置：Windows `%APPDATA%\npm\node_modules\{pkg}`；Unix `$(npm root -g)/{pkg}`。
- 已有同名 server 不覆蓋，跳過並回報。
- `ensure-mcp.py` **不會建立** `~/.claude.json`（Claude Code 首次啟動自己建）；檔案不存在時它直接結束。

驗證：`python -c "import json,io;print(list(json.load(io.open('$HOME/.claude.json',encoding='utf-8'))['mcpServers']))"` 含 `workflow-guardian`。MCP server 變更需 VS Code **Reload Window**（或重啟 `claude`）才生效。

> MCP server 自己會再 spawn Python（`lib/paths.js` `resolvePythonExe()`：`WG_PYTHON` → `%LOCALAPPDATA%\Programs\Python\Python3xx`／`%LOCALAPPDATA%\Pythonin`／`C:\Python3xx`／`C:\Program Files\Python3xx` → 裸 `python`）。Python 裝在非標準位置時，把 `"env": {"WG_PYTHON": "<與 hooks 相同的 python.exe 絕對路徑>"}` 加進該 server 的設定；退回裸 `python` 會在 MCP stderr 印 WARN。

### Step 5：初始化個人記憶層

- `memory/MEMORY.md`（Lv1 範疇目錄，由 `tools/sync-memory-index.py --write` 生成，不手編）與 `memory/_atom_index.json`（索引單一來源）若缺，Step 2 已補骨架。
- 首次寫 atom 一律走 MCP `atom_write(mode=create)` 並給 `domain`（Lv1 閉合清單在 `memory/_meta/taxonomy.json`）；分不出範疇的知識不寫。
- 執行 `python tools/sync-memory-index.py --check` 確認索引與檔案一致（不一致再 `--write`）。

### Step 6：索引三檔 git 合併驅動（hook 自動安裝；手動 `--install` 選配）

兩台機器各自新增 atom 後 `git pull --rebase`，atom 本體不衝突，但索引三檔（`MEMORY.md` 範疇計數表、`_ATOM_INDEX.md`、`_atom_index.json`）在同區塊各加一列必衝突。merge driver 是機器級 git 設定（global git config `merge.atomindex` + `~/.config/git/attributes`），版控帶不動，由 hook 自動裝：

- **自動安裝**：PreToolUse hook（`pre_tool_use.check_merge_driver`）在 CC 的 Bash/PowerShell 跑 `git pull / merge / rebase / cherry-pick / stash pop` 前檢查本機是否已裝（`is_installed`：driver command 存在、引號內的直譯器與腳本存在、attributes 標記存在、目標 repo `git check-attr merge` 為 `atomindex`——任一不成立即重裝），缺就跑 `--install`，訊息 `[Guardian:MergeDriver] 已自動安裝索引三檔合併驅動`。
- **自動解衝突（備案）**：git 已停在索引三檔衝突時，`git rebase --continue / merge --continue / cherry-pick --continue / commit / stash pop` 前 hook 先跑 `--resolve`，把語意驅動套在三檔的 stage（:1 base／:2 HEAD／:3 對方）上、寫回並 `git add`，訊息 `[Guardian:IndexConflict] 已自動合併並 add 索引檔：…`；解不掉的列 `⚠ … → 手動 --resolve`。SessionStart 若 repo 卡在 rebase/merge 且三檔未合併，注入一行提示。
- config：`workflow/config.json` `merge_driver.{auto_install,auto_resolve}` 預設 true；hook 內 fail-open、總時限 2.5 秒。
- **手動（選配）**：安裝當下就想裝好、或這台主要不經 CC 用 git：

```bash
python tools/merge-atom-index.py --install   # 寫 global git config merge.atomindex + ~/.config/git/attributes（**/.claude/memory/* 三檔 merge=atomindex）
python tools/merge-atom-index.py --status    # 末行「已安裝」；直譯器換了 hook 會自動重裝，手動重跑 --install 亦可
python tools/merge-atom-index.py --resolve   # git 已停在索引三檔衝突、hook 沒接手時手動解（可加 --cwd <repo>）
```

- driver 綁定：根層 repo 靠自帶的 `.gitattributes`，專案 repo 靠全域 attributes，專案不必改任何檔。
- 根層 repo 全部 LF 由 `.gitattributes`（`* text=auto eol=lf` + 各文字副檔名明釘）與 `.editorconfig` 進版控保證，不需要任何機器安裝；驗證 `python tools/normalize-eol.py --root --check`（有 CRLF/混行尾即 exit 1）。
- 專案記憶樹要一併釘 LF，由**專案 session** 做（根層 session 不碰專案檔），把下面這段貼給專案 session（路徑換成該專案）：

```
在 C:\Projects 專案 session：
1. 確認沒有進行中的 rebase/merge，且 git status 對 .claude/memory 與 .gitattributes 沒有他人的 dirty/staged/untracked 改動（有就停）。
2. python ~/.claude/tools/normalize-eol.py --memory-dir .claude/memory --check   → 看預計異動清單。
3. python ~/.claude/tools/normalize-eol.py --memory-dir .claude/memory --write-gitattributes
4. 對該清單 git diff --ignore-cr-at-eol --stat 必須為 0 行內容差異；commit「chore(memory): 記憶樹換行統一 LF」並 push。
```

- 原理、stage 方向矩陣、失敗模式與 SOP、不在保證範圍見 `_AIDocs/MultiMachineMemorySync.md`；驗證 `tools/verify/verify_merge_atom_index.py`、`hooks/verify/verify_merge_driver_gate.py`。

---

## 4. Ollama + Vector Service

### 4.1 Ollama 模型

```bash
ollama pull qwen3-embedding        # 向量嵌入
ollama pull qwen3:1.7b             # 本地快篩 LLM（~1.2 GB）
ollama pull gemma4:e4b             # 主萃取 LLM（~5 GB）
```

### 4.2 Python 套件

```bash
pip install -r ~/.claude/tools/memory-vector-service/requirements.txt   # lancedb>=0.20 + sentence-transformers>=4.0
```
`lancedb` 需 AVX2；沒有 AVX2 的機器向量層無法啟用，接受 §1.3 的降級即可（trigger/BM25 照常）。

### 4.3 Vector Service

不需手動常駐：每次 SessionStart 由 `hooks/handlers/session_start.py` 背景 spawn `tools/memory-vector-service/starter.py --phase sessionstart`，它負責健檢、殺殘留 pid、起 `service.py`、等待就緒（冷啟動上限 120s）、寫 `workflow/vector_ready.flag`，動作與服務輸出全落 `Logs/vector-service.log`，結果一行 JSON 落 `Logs/vector-observation-probe.log`。

手動驗證／重建：
```bash
curl -s http://127.0.0.1:3849/health        # 預期 {"status":"ok", ...}
curl -s http://127.0.0.1:3849/index/full    # 全量重建，預期 {"indexed":N, "chunks":M}
```
或在 Claude Code 內用 `/vector`。

> 全域層檢索走 BM25 in-memory（`vector_search.global_layer="bm25"`）；Vector Service 只服務專案層 atom、episodic search、跨 session 去重與衝突偵測。

### 4.4 （可選）遠端 Ollama backend

編輯 `workflow/config.json` → **`vector_search.ollama_backends`**（不是頂層）：

```jsonc
"vector_search": {
  "ollama_backends": {
    "rdchat-direct": { "base_url": "http://<gpu-server>:11434", "llm_model": "gemma4:e4b",
                       "embedding_model": "qwen3-embedding:latest", "priority": 1, "enabled": true },
    "local":         { "base_url": "http://127.0.0.1:11434", "llm_model": "qwen3:1.7b",
                       "embedding_model": "qwen3-embedding", "priority": 3 }
  }
}
```

認證型 backend（OAuth / LDAP / bearer）的 `auth` 區塊私下取得範本，憑證走 gitignored 路徑。退避行為見 §1.3「Ollama」。

---

## 5. 安裝後的網頁介面

| 介面 | 位置 | 條件 |
|------|------|------|
| Dashboard | `http://127.0.0.1:3848/` | 由 MCP server `server.js` 同進程提供；MCP 註冊完成並 Reload Window 後才有。port 取 env `WG_DASHBOARD_PORT` → config `dashboard_port` → 3848 |
| Anti-Evasion HUD | `http://127.0.0.1:3848/aec/hud` | 同上 |
| 腦內世界 | `tools/workflow-guardian-mcp/world.html` | **靜態檔，server.js 不服務它**——用瀏覽器直接開檔（file://），頁面自己輪詢 `http://127.0.0.1:3848/api/*`，所以仍需 MCP server 在跑 |

沒有 Node 時三者皆不可用；不影響記憶注入。

---

## 6. 驗證 Checklist

| # | 驗證項 | 指令 / 方法 | 通過標準 |
|---|--------|------------|---------|
| 1 | 版本 | `python -c "import json,io;v=json.load(io.open('version.json',encoding='utf-8'));print(v['atom_memory'],v['guardian'])"` | `5.1 5.1.0` |
| 2 | Hook 直譯器 | `python tools/fix-hook-python.py` | 全數 `[OK ]` |
| 3 | Hook 可執行 | Step 3 的 echo 管線 | 輸出 JSON 含 `additionalContext` |
| 4 | Python 套件 | `python -c "import lancedb, sentence_transformers"` | 無 ImportError（缺＝向量層降級，非失敗） |
| 5 | Ollama 模型 | `ollama list` | 三模型全在（缺＝萃取降級，非失敗） |
| 6 | Vector Service | `curl -s http://127.0.0.1:3849/health` | `{"status":"ok"}`；失敗看 `Logs/vector-service.log` |
| 7 | Memory 健檢 | `python tools/memory-audit.py --global-only` | 無 ERROR |
| 8 | 索引一致 | `python tools/sync-memory-index.py --check` | 無差異 |
| 9 | Skills | Claude Code 內按 `/` | `/memory` `/handoff` `/continue` `/vector` 可見 |
| 10 | MCP servers | `~/.claude.json` 的 `mcpServers` | 至少含 `workflow-guardian` |
| 11 | MCP 5 tool | 問 Claude「列出 workflow-guardian MCP 工具」 | `atom_write` / `atom_promote` / `atom_move` / `atom_edit_meta` / `anti_evasion_report` |
| 12 | 整合 | 開新 session | 看到 `[Workflow Guardian] Active`；statusline 無 `WG:?` |
| 13 | Dashboard | 開 `http://127.0.0.1:3848/` | 有頁面 |
| 14 | 索引合併驅動 | `python tools/merge-atom-index.py --status` | 末行「已安裝」（hook 會在首次合併類 git 指令前自動裝；此處手動確認） |

完整回歸：`python run_verify.py`（基線全數 passed，數字見該腳本輸出）。

---

## 7. 升級

```bash
cd ~/.claude && git pull
python tools/fix-hook-python.py            # pull 後 settings.json 若被更新，重驗直譯器路徑
python tools/merge-atom-index.py --install # 一次性：帶來「合併前自動安裝驅動」hook 的那次 pull 跑的還是舊 hook，這次手動補上；之後每台機器由 hook 自動裝／自動重裝
```

- 上面那次 `git pull` 若本身卡在索引三檔衝突：`python tools/merge-atom-index.py --resolve` 後 `git rebase --continue`（`GIT_EDITOR=true` 可免開編輯器）。
- 已含本版 hook 的機器之後不需要這一步；`--status` 末行「已安裝」即可。

從 4.x 升級需確認：

- [ ] `version.json` 為 `atom_memory: "5.1"` / `guardian: "5.1.0"`
- [ ] `hooks/dispatcher.py` 存在；`hooks/handlers/` 有 **9** 個事件 handler（session_start / session_end / user_prompt_submit / pre_tool_use / post_tool_use / stop / pre_compact / post_compact / post_tool_batch）+ `ups_*.py` 四段 + `_shared.py` + `aec_ledger.py`
- [ ] `hooks/wg_*.py` 為：wg_atoms / wg_coordination / wg_core / wg_docdrift / wg_episodic / wg_evasion / wg_extraction / wg_handoff / wg_parallel / wg_recall_miss / wg_rescue / wg_research / wg_roles（shim 只有 wg_roles）
- [ ] `hooks/` 內**沒有** `quick-extract.py`、`wg_atom_observation.py`（已刪）；`commands/` 已刪（併入 `skills/`）
- [ ] `skills/` 有 <!-- skill-count -->21<!-- /skill-count --> 個 active skill；`skills/_archived/` 放 dormant 的 init-roles / conflict-review
- [ ] `lib/atom_index_json.py` + `memory/_atom_index.json` 存在；`memory/_meta/taxonomy.json` + `forbidden-phrases.json` 存在
- [ ] 核心 atom 已階層化在 `memory/<範疇>/`，`memory/` 根目錄無平鋪 atom；`taxonomy.gate_enabled=true`
- [ ] `workflow/config.json`：`vector_search.global_layer="bm25"`、`bm25_min_score=7.0`、`fusion="rrf"`；無 `codex_companion.subprocess_timeout` 死鍵；`ollama_backends` 在 `vector_search` 底下
- [ ] `tools/workflow-guardian-mcp/server.js` 暴露 5 tool（§6 #11）
- [ ] `tools/codex-companion/judge_backend.py` 存在；無 codex CLI 的環境確認 `claude` 可被找到（備援裁判）
- [ ] Stop hook 只掛 guardian / codex_companion / lang_guard（無 quick-extract）

### 7.1 升級到 scope 分層後：各專案的記憶要整理一次

這版把記憶可見性改成：**personal 只給本人、針對專案的規則進 shared 並以 Author 記提出者、他專案的 atom 不再注入**（`_AIDocs/SPEC_ATOM_V5.md` §2）。升級後程式面自動生效，但**既有專案的存量**（過去自動萃取全落 personal、索引 scope 欄錯標）不會自己歸位：

- 打開任何尚未整理的專案，SessionStart 會出 `[Guardian:ScopeLayout]` 提示；請使用者說「整理記憶分類」，AI 走 `/memory classify`（`tools/classify-project-scope.py plan → 使用者確認 personal 去向 → apply`），完成後打上 `_atom_index.json.layout="scope-v2"` 標記，並把 `.claude/memory/` 變動上該專案版控。
- 「已整理」判定：上述標記，或專案已有 `shared/_taxonomy.json`。
- 只想先修程式能判的部分（索引 scope、懸空條目），可從 `~/.claude` 一次掃全部登記專案：`python tools/sync-atom-index.py --all-projects --fix-scope-from-path`。

> 多職務團隊：從 `skills/_archived/` 復原 init-roles / conflict-review，專案執行 `/init-roles` 建 `memory/shared/_roles.md` + `memory/roles/<role>/`（`tools/init-roles.py`、`tools/conflict-review.py` 仍在）。單人環境不需要。

---

## 8. FAQ

### Q: 啟動變慢？
SessionStart 主路徑 50–200 ms（向量與 MCP 檢查皆背景）。每 prompt 注入主路徑 ~16 ms（BM25 in-memory），有專案層向量查詢時多 200–500 ms。

### Q: Vector Service 起不來？
看 `Logs/vector-service.log`。常見：`lancedb` 未裝或無 AVX2；Ollama 與 sentence-transformers 都不可用（`No embedding backend available`）；port 3849 被佔（改 `vector_search.service_port`）。全域層不依賴它，只有專案層／episodic 降級。

### Q: Ollama embedding timeout？
模型首次載入 5–10 秒。確認 `ollama list` 有模型；daemon 沒回應查 `systemctl status ollama` 或 Windows 工作管理員。遠端 backend 連續失敗會進 Long DIE，SessionStart 會問你要不要停用。

### Q: Hook 執行但 atom 沒注入？
確認 `memory/_atom_index.json` 的 triggers 含 prompt 關鍵字（ASCII 整詞、CJK 子字串）。開 `/atom-debug` 看注入 log；每次注入尾行 `[Context budget: x/y | trim: …]` 顯示預算裁切。

### Q: 不想要某些功能？
`workflow/config.json` 逐鍵關（值一律 `false`）：

| 鍵 | 關了少什麼 |
|----|-----------|
| `enabled` | 整個 Guardian（所有 hook 直接放行） |
| `vector_search.enabled` | 語意搜尋（保留 trigger + BM25） |
| `vector_search.global_layer` | 值 `"bm25"`（預設）或 `"vector"`；全域層改走向量 |
| `vector_search.auto_start_service` | SessionStart 不再自動起向量服務 |
| `response_capture.enabled` | 全部自動萃取（SessionEnd 全量、失敗萃取） |
| `response_capture.failure_extraction.enabled` | 只關失敗關鍵字萃取 |
| `response_capture.per_turn.enabled` | 預設 false，已停產，值保留供回滾 |
| `response_capture.session_end_flush.enabled` | 預設 false，已停產，值保留供回滾 |
| `userExtraction.enabled` | 使用者決策萃取（L0→L1→L2）；只降負擔改 `userExtraction.tokenBudget`（預設 240） |
| `deep_postmortem.enabled` | 高 effort 失敗時要求 Claude 深寫 post-mortem 的 Stop 閘 |
| `cross_session.enabled` | 跨 session 去重／衝突偵測 |
| `docdrift.enabled` | 改碼後提醒對應文件的漂移偵測 |
| `codex_companion.enabled` | AI 裁判（驗收審查／計畫審查／handoff 自檢） |
| `codex_companion.fallback.enabled` | 無 codex 時不退 `claude -p`，直接 heuristics-only |
| `coordination.enabled` | 多 session 同檔改動預警 |
| `guard.pre_action_notice.enabled` | 動手前預告閘（`mode` 可 observe / warn / deny） |
| `guard.cross_realm_write.enabled` | 外部專案 session 不得寫入 `~/.claude` 核心層（hooks/lib/tools/skills/rules 與根層設定檔）的 deny 閘；「專案專屬內容不得落 global」的 realm 閘在 `lib/realm_gate.py`，無開關 |
| `injection.redundancy_gate.enabled` | 同題去冗（trigger 重疊 ≥3 只留節錄） |
| `injection.related_gate.enabled` | related atom 擴散注入 |
| `taxonomy.gate_enabled` | atom 必須帶範疇才能寫入的閘 |
| `realm.llm_fallback.enabled` | 預設 false；開了會用本地 LLM 判定 unknown atom 的 realm |
| `lang_guard.enabled` | 回應英文比例過高時的繁中提醒 |
| `version_guard.enabled` | 檔內版本操作脈絡殘留的 warn（`mode` warn / off） |
| `acceptance_spec.enabled` | 多檔改動要求驗收規格 |
| `deferral_gate.enabled` | Stop 閘攔「推給下個 session」的退縮歸屬 |
| `auto_handoff.enabled` | 壓縮前／token 逼近時自動產 handoff 交接稿 |
| `parallel_agents.enabled` / `research_fanout.enabled` | 多 agent 拆分／研究 fan-out 建議 |
| `aec.hud_autospawn` | 收尾檢核時自動開 HUD |
| `privacy.enabled` / `deny_globs` | git commit 前隱私檔硬閘（staged 比對 deny globs；預設開、globs 可追加） |
| `heal.enabled` | `/heal-review` 自動修復 |
| `episodic.auto_generate` | session 結束自動生成 episodic 摘要 |

### Q: 完全移除？
見 §9。

---

## 9. 移除與清理

- 移除：刪 `settings.json` 的 `hooks` 與 `statusLine`（若是本系統加的）→ 刪 `~/.claude.json` `mcpServers` 內的 `workflow-guardian`（MCPControl / playwright 視需要）→ 刪 `~/.claude/{hooks,lib,tools,skills,rules,memory,workflow,_AIDocs,Logs,templates}`。Claude Code 本體零修改，無殘留。
- 暫存：`rm -rf /tmp/atomic-memory`。

---

## 10. 深度參考

- [README.md](README.md) — 設計理念與使用方式
- [TECH.md](TECH.md) — 技術深度文件（架構 / 流程 / 子系統 / 版本歷史）
- [_AIDocs/SPEC_ATOM_V5.md](_AIDocs/SPEC_ATOM_V5.md) — atom 規格主檔
- [_AIDocs/_INDEX.md](_AIDocs/_INDEX.md) — 知識庫索引
