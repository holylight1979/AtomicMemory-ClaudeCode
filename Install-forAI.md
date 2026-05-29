# Atomic Memory V5 — AI 安裝指南

> **目標讀者**：Claude / 相容 AI 助手，代替使用者執行原子記憶系統的合併安裝。
> **若你是人類**：建議不要逐步手作，直接在新 Claude Code session 貼 [README.md](README.md) 的「由 AI 全程代跑」prompt，讓 AI 照本指南執行。

---

## 0. AI 執行守則（開工前必讀）

1. **每一步驗證，每一步回報**。每個 Step 結束告訴使用者「已做 X，接下來做 Y，你確認嗎」。
2. **不覆蓋使用者現有設定**：`settings.json` 的 `permissions`、`config.json` 使用者自訂值、`USER.md` 個人資料一律 merge，不 overwrite。
3. **缺套件不自行 pip install / npm i**：列出缺項 + 安裝指令給使用者，**等使用者確認再裝**。跨平台（Windows / Mac / Linux）指令要對。
4. **帳號密碼類絕不主動寫入**：需要時問使用者，或請使用者自己編輯 gitignored 檔。
5. **若發現與本指南不符的真源差異**（代碼已改、路徑異動），以當下代碼 / `version.json` / `_AIDocs/SPEC_ATOM_V5.md` 為準，同時回報「指南需更新」。
6. **路徑符號**：Windows 使用者的 `~/.claude/` 實際是 `C:\Users\{user}\.claude\`。用 `pathlib.Path.home()` 或 bash `$HOME` 確保跨平台。

---

## 1. 必備套件自檢清單

**先全部跑過**再開始裝。結果整理成表回報給使用者，缺項**不要自己補**，給安裝指令由他決定。

| 項目 | 自檢指令 | 通過標準 |
|------|---------|---------|
| Claude Code Extension | 問使用者「VS Code 的 Claude Code 面板能開嗎？」或檢查 `code --list-extensions \| grep claude` | 有 Anthropic 官方 Claude extension |
| Python | `python --version`（或 `python3`）| ≥ 3.10 |
| Node.js | `node --version` | LTS |
| Git | `git --version` | 任意 |
| Ollama | `ollama --version` | 有 |
| Ollama 模型 | `ollama list` | 含 `qwen3-embedding` + `qwen3:1.7b` + `gemma4:e4b` |
| Python 套件 | `python -c "import lancedb; import sentence_transformers; print('ok')"` | 無 ImportError |
| Hook 權限 | 檢查 `settings.json` 是否允許執行 `python` hook | 無 sandbox 阻擋 |

**內網 + 遠端 Ollama backend** 補查：
- 遠端 base URL 連通性（`curl -s <base_url>/api/tags`）
- LDAP bearer token 可認證（可選）

**缺項回報格式**：
```
以下必備項尚未就緒：
1. Python 3.9 → 需升級到 3.10+
2. Ollama 模型 gemma4:e4b 未下載：ollama pull gemma4:e4b
3. lancedb 套件未裝：pip install lancedb>=0.20

你補完後告訴我，我再繼續下一步。
```

---

## 2. 使用者常問問題

- 「**幫我確認必備套件沒漏？**」 → 跑第 1 節
- 「**Python 3.9 可以嗎？**」 → 不行，需 3.10+
- 「**沒 GPU 會慢嗎？**」 → Ollama 可 CPU fallback（embedding 200-500 ms / qwen3:1.7b 1-3 s）；建議設遠端 GPU backend
- 「**沒 admin 權限能裝嗎？**」 → 大部分能（Python / Node.js / Ollama 有 user-local 安裝），pip 套件用 `--user`
- 「**多職務團隊要怎麼啟用？**」 → 專案執行 `/init-roles` 建立 `memory/shared/_roles.md` 白名單與 `role/{name}/` 目錄
- 「**沒看到 Guardian Active？**」 → 檢查 `settings.json` 的 hooks 區塊是否合併進來
- 「**整個移除？**」 → 刪 `settings.json` 的 hooks 區塊，其餘檔案刪掉即可；Claude Code 本體零修改

---

## 3. 安裝流程（合併安裝，不覆蓋既有設定）

### Step 0：備份

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.backup 2>/dev/null || true
cp ~/.claude.json ~/.claude.json.backup 2>/dev/null || true
```

### Step 1：Clone repo 到暫存位置

```bash
git clone <repo-URL> /tmp/atomic-memory
```

### Step 2：複製系統檔案（不動使用者個人資料）

V5 採全資料夾同步策略（不再逐檔列）。使用者個人實例（`USER.md` / `IDENTITY.md` / `IDENTITY-{user}.md` / `USER-{user}.md`）一律保留。

```bash
SRC=/tmp/atomic-memory
DST=~/.claude

# 啟動文件（不覆蓋個人實例）
cp "$SRC/CLAUDE.md" "$DST/CLAUDE.md"
cp "$SRC/IDENTITY.template.md" "$DST/IDENTITY.template.md"
cp "$SRC/USER.template.md" "$DST/USER.template.md"
cp "$SRC/BOOTSTRAP.md" "$DST/BOOTSTRAP.md"
[ ! -f "$DST/IDENTITY.md" ] && cp "$SRC/IDENTITY.template.md" "$DST/IDENTITY.md"
[ ! -f "$DST/USER.md" ] && cp "$SRC/USER.template.md" "$DST/USER.md"

# 版本標識
cp "$SRC/version.json" "$DST/version.json"

# 核心模組（整資料夾覆蓋；不含個人 atom 與 runtime state）
rsync -a --delete "$SRC/hooks/" "$DST/hooks/"      # dispatcher + handlers/ + wg_*.py + 獨立 hook
rsync -a --delete "$SRC/lib/" "$DST/lib/"          # atom_io / atom_spec / atom_locations / atom_index_json / atom_access / ollama_extract_core
rsync -a --delete "$SRC/skills/" "$DST/skills/"    # 20 個 skill
rsync -a --delete "$SRC/rules/" "$DST/rules/"

# Tools（保留 user 自加；只覆蓋系統內建）
rsync -a "$SRC/tools/" "$DST/tools/"

# Memory templates（不動已有的個人 atom）
mkdir -p "$DST/memory/_reference"
cp "$SRC/memory/_reference/"*.md "$DST/memory/_reference/" 2>/dev/null || true
[ ! -f "$DST/memory/MEMORY.md" ] && cp "$SRC/memory/MEMORY.md" "$DST/memory/MEMORY.md"
[ ! -f "$DST/memory/_atom_index.json" ] && cp "$SRC/memory/_atom_index.json" "$DST/memory/_atom_index.json"

# 禁語單一來源（V5 抽 JSON）
mkdir -p "$DST/memory/_meta"
cp "$SRC/memory/_meta/forbidden-phrases.json" "$DST/memory/_meta/"

# Workflow 設定（不覆蓋既有）
mkdir -p "$DST/workflow"
[ ! -f "$DST/workflow/config.json" ] && cp "$SRC/workflow/config.json" "$DST/workflow/"

# MCP template + 知識庫文件
cp "$SRC/mcp-servers.template.json" "$DST/"
rsync -a "$SRC/_AIDocs/" "$DST/_AIDocs/"
```

> 已存在 `workflow/config.json` 時改執行 JSON merge（不覆蓋 user 設值），新欄位（`vector_search.global_layer` / `codex_companion.subprocess_timeout`）補預設。

### Step 3：合併 settings.json hooks 區塊

**不能直接覆蓋**。AI 讀使用者 `settings.json.backup`，只合併 `hooks` 區塊，保留 `permissions` 與 `env`。

目標結構（`permissions` 保留 user 原有）：

```jsonc
{
  "permissions": { /* user 原有 */ },
  "env": { /* user 原有 */ },
  "hooks": {
    "SessionStart": [{"hooks": [{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":5}]}],
    "UserPromptSubmit": [{"hooks": [{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":3}]}],
    "PreToolUse": [{"matcher":"Edit|Write|Bash", "hooks":[{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":3}]}],
    "PostToolUse": [{"matcher":"Edit|Write|Read|Bash", "hooks":[{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":3}]}],
    "PreCompact": [{"hooks": [{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":5}]}],
    "Stop": [{"hooks":[
        {"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":5},
        {"type":"command", "command":"python \"$HOME/.claude/hooks/quick-extract.py\"", "async":true, "timeout":30}
    ]}],
    "SessionEnd": [{"hooks": [{"type":"command", "command":"python \"$HOME/.claude/hooks/workflow-guardian.py\"", "timeout":30}]}]
  }
}
```

> `workflow-guardian.py` 為 1 行 shim → `dispatcher.main()`，handler 在 `hooks/handlers/{event}.py`。
> Python 指令：若 user 系統是 `python3` 而非 `python`，全部改 `python3`。

### Step 4：npm 全域套件 + `~/.claude.json` MCP 合併

```bash
# 讀 mcp-servers.template.json 對每個 server 處理：
npm i -g computer-use-mcp     # 螢幕/滑鼠/鍵盤
npm i -g @playwright/mcp      # 瀏覽器自動化
# 其他 server 依 template 內容
```

合併 `~/.claude.json.mcpServers`（冪等，不覆蓋已有 server）：

```
讀 mcp-servers.template.json 的每個 server
→ 找 npm 套件位置（Windows: %APPDATA%/npm/node_modules/{pkg}；Unix: $(npm root -g)/{pkg}）
→ 在 ~/.claude.json.mcpServers 加 entry，type=stdio
→ npm_package=null 者（如 workflow-guardian）用 entry_absolute 並展開 {claude_dir}=$HOME/.claude
```

關鍵規則：
- **全域安裝 + 絕對路徑**，不要 `cmd /c npx`
- Windows: `C:\\Program Files\\nodejs\\node.exe` + `%APPDATA%/npm/node_modules/{pkg}/...`
- 已有同名 server 不覆蓋，跳過並回報

`workflow-guardian` MCP 暴露 3 tool：`atom_write` / `atom_move` / `atom_promote`。

### Step 5：初始化個人記憶層

若 `~/.claude/memory/MEMORY.md` 不存在才建。已存在不動（user 累積優先）。

AI 把 templates 寫入（若缺）：
- `memory/MEMORY.md` — atom 索引骨架
- `memory/_atom_index.json` — JSON SoT 機器源
- `memory/preferences.md` / `memory/decisions.md` — 全域決策初始空殼

---

## 4. Ollama + Vector Service

### 4.1 Ollama 模型

```bash
ollama pull qwen3-embedding        # 語意搜尋（需 AVX2；無 AVX2 可選 0.6b 小版）
ollama pull qwen3:1.7b             # 本地 LLM 快篩（~1.2 GB）
ollama pull gemma4:e4b             # 主萃取 LLM（~5 GB）
```

### 4.2 Python 套件

```bash
pip install lancedb>=0.20                # Vector DB（需 AVX2）
pip install sentence-transformers>=4.0   # Fallback embedding
# 無 AVX2: pip install chromadb 並改 config.json 的 vector_search.fallback_backend
```

### 4.3 Vector Service 啟動

```bash
cd ~/.claude/tools/memory-vector-service
pip install -r requirements.txt

python ~/.claude/tools/memory-vector-service/service.py &

curl -s http://127.0.0.1:3849/health   # 預期 {"status":"ok", ...}
curl -s http://127.0.0.1:3849/index/full  # 預期 {"indexed":N, "chunks":M}
```

> Vector Service 由 Guardian 每次 SessionStart 自動檢查 + spawn，不需常駐。
> V5 全域層改 BM25 in-memory（`config.json.vector_search.global_layer="bm25"`），Vector Service 僅服務專案層 + episodic search + 跨 session dedup / 衝突偵測。

### 4.4 （可選）遠端 Ollama Backend

GPU 伺服器（Open WebUI + Ollama），編輯 `workflow/config.json.ollama_backends`：

```jsonc
"ollama_backends": {
  "rdchat-direct": {
    "base_url": "http://<gpu-server>:11434",
    "llm_model": "gemma4:e4b",
    "embedding_model": "qwen3-embedding:latest",
    "priority": 1,
    "enabled": true
  },
  "local": { "base_url": "http://127.0.0.1:11434", "llm_model": "qwen3:1.7b", "priority": 3 }
}
```

> 認證型 backend（OAuth / LDAP / bearer）的 `auth` 區塊請**私下取得設定範本**，憑證走 gitignored 路徑。

三階段退避：正常 → Short DIE 60s → Long DIE 等下個 6h 邊界（0/6/12/18）。

---

## 5. 驗證 Checklist

| # | 驗證項 | 指令 / 方法 | 通過標準 |
|---|--------|------------|---------|
| 1 | Python 套件 | `python -c "import lancedb; import sentence_transformers"` | 無 ImportError |
| 2 | Ollama 模型 | `ollama list` | `qwen3-embedding` + `qwen3:1.7b` + `gemma4:e4b` 全在 |
| 3 | Hook 可執行 | `echo '{"hook_event_name":"SessionStart","session_id":"test","cwd":"/tmp"}' \| python ~/.claude/hooks/workflow-guardian.py` | 輸出 JSON 含 `additionalContext` |
| 4 | Vector Service | `curl -s http://127.0.0.1:3849/health` | `{"status":"ok"}` |
| 5 | Memory 健檢 | `python ~/.claude/tools/memory-audit.py` | 無 ERROR |
| 6 | Atom Index SoT | `python -c "from lib.atom_index_json import load_atom_index_json; from pathlib import Path; print(len(load_atom_index_json(Path('memory'))['atoms']))"` | 數字 > 0 |
| 7 | Skills 註冊 | VS Code 按 `/` 看到 `/memory` `/handoff` `/continue` 等 | 20 個 skill 可見 |
| 8 | MCP servers | `~/.claude.json.mcpServers` 含 template 內 server | MCPControl + playwright + workflow-guardian 至少有 |
| 9 | MCP 3 tool | 在 Claude Code 中問「列出 workflow-guardian MCP 工具」 | atom_write / atom_move / atom_promote |
| 10 | 整合驗證 | 開新 Claude Code session | 看到 `[Workflow Guardian] Active` |

---

## 6. 舊版升級

```bash
cd ~/.claude && git pull
```

補確認（V4.1 / V4 → V5）：

- [ ] `version.json` 為 `atom_memory: "5.0"` / `guardian: "5.0.0"`
- [ ] `hooks/dispatcher.py` 存在 + `hooks/handlers/` 8 個 event handler 各一檔
- [ ] `hooks/wg_*.py` 為 6 主模組（core/atoms/extraction/episodic/evasion/docdrift）+ 2 shim（roles/atom_observation）
- [ ] `commands/` **已刪除**（22 檔合 19 skill）
- [ ] `skills/` 含 20 個 skill（19 遷移 + skill-creator 新增）；`/memory` 統一 5 subcmd（health/peek/undo/review/session-score）
- [ ] `lib/atom_index_json.py` + `memory/_atom_index.json` 存在
- [ ] `tools/codex-companion/audit.py` 存在；`tools/codex-companion/service.py` 已刪
- [ ] `memory/_meta/forbidden-phrases.json` 存在
- [ ] `workflow/config.json` 含 `vector_search.global_layer="bm25"` + `codex_companion.subprocess_timeout`
- [ ] `tools/workflow-guardian-mcp/server.js` 暴露 3 tool（非 V4 的 7 tool）

> 多職務團隊：專案執行 `/init-roles` 建立 `memory/shared/_roles.md` + `role/{name}/` 目錄。

---

## 7. FAQ

### Q: 啟動變慢？
**A**: SessionStart 50-200 ms（去重 + 非阻塞 vector）。每 prompt 200-500 ms（BM25 + 向量搜尋）。首次 prompt 500-1500 ms（episodic context search）。

### Q: Vector Service 啟動失敗？
**A**: 檢查 `pip install lancedb`（需 AVX2）。Port 3849 被佔改 `config.json.vector_search.service_port`。無 AVX2 改 ChromaDB 並設 `fallback_backend`。V5 全域層走 BM25 不依賴 Vector Service；專案層需要。

### Q: Ollama embedding timeout？
**A**: 模型首次載入 5-10 秒。確認 `ollama list` 有模型；無反應檢查 daemon（`systemctl status ollama` 或 Windows 工作管理員）。

### Q: Hook 執行但 atom 沒載入？
**A**: 確認 `_atom_index.json` 的 triggers 含 prompt 關鍵字。可開 `/atom-debug` 啟用注入 debug log。

### Q: 使用者決策萃取可關嗎？
**A**: `config.json` 設 `"userExtraction.enabled": false`。只降負擔但保留偵測：調低 `userExtraction.tokenBudget`（預設 240）。

### Q: 多人分層怎麼設？
**A**: 專案 `/init-roles` 建 `memory/shared/_roles.md` 白名單 + `role/{name}/`，管理職用 `/conflict-review` 裁決 `shared/_pending_review/` 敏感原子。

### Q: 不想要某些功能？
**A**: `config.json` 個別關：
- `"enabled": false` → 關整個 Guardian
- `"vector_search.enabled": false` → 關語意搜尋（保留 BM25 + keyword）
- `"vector_search.global_layer": "vector"` → 全域層改用 Vector（預設 BM25）
- `"response_capture.enabled": false` → 關回應萃取
- `"cross_session.enabled": false` → 關跨 session 鞏固
- `"docdrift.enabled": false` → 關文件漂移
- `"codex_companion.enabled": false` → 關 Codex Companion 監督

### Q: 沒 GPU 能用嗎？
**A**: 可以。Ollama CPU fallback 200-500 ms（embedding）、1-3 s（qwen3:1.7b）。加速可設遠端 GPU backend（§4.4）。

### Q: 完全移除？
**A**: 刪 `settings.json` 的 hooks 區塊 → 刪 `~/.claude/{hooks,tools,memory,skills,lib,_AIDocs,workflow}` 等目錄。Claude Code 本體零修改，無殘留。

---

## 8. 清理暫存

```bash
rm -rf /tmp/atomic-memory
```

---

## 9. 深度參考

- [_AIDocs/SPEC_ATOM_V5.md](_AIDocs/SPEC_ATOM_V5.md) — V5 GA 規格主檔
- [_AIDocs/DevHistory/v5-overhaul-2026-05/README.md](_AIDocs/DevHistory/v5-overhaul-2026-05/README.md) — V5 升版完整紀錄
- [TECH.md](TECH.md) — 技術深度文件（架構 / 流程圖 / 子系統）
