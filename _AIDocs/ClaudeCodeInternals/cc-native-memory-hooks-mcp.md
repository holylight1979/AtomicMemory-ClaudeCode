# Claude Code 原生 Memory / Hooks / MCP / Context 官方規格

- Scope: global
- Confidence: [固]
- Trigger: auto-memory, autoMemoryDirectory, MEMORY.md, project-slug, CLAUDE.md 階層, CLAUDE.local.md, @import, rules/*.md, path-scoped rules, hook events, UserPromptSubmit, additionalContext, hookSpecificOutput, hook timeout, SessionEnd 1.5, MCP scope, .mcp.json, mcp__server__tool, MAX_MCP_OUTPUT_TOKENS, compaction, PreCompact, prompt caching, cacheTtl, changelog 2.1.248, native-memory-bridge
- Last-used: 2026-08-28
- Confirmations: 1
- Related: cc-hook-system, cc-context-management, cc-skills-plugins, cc-harness-overview

> 本檔＝**官方文件**查證版（2026-08-28），與 `cc-hook-system` / `cc-context-management` 的反編譯實測互補：官方頁說「契約是什麼」，實測檔說「binary 實際怎麼跑」。兩者衝突時以官方頁為契約、實測為該版本行為。標 **[實測]** 者為本機驗證、非官方文字。

## 知識

### 1. Auto-memory（原生自動記憶）

- [固] 路徑：`~/.claude/projects/<project-slug>/memory/`。結構＝`MEMORY.md`（索引）＋ 多個主題 `.md`。可用設定 `autoMemoryDirectory` 改路徑。
- [固] 載入預算：每 session 啟動**只載 `MEMORY.md` 前 200 行或 25KB（先到者為準）**；主題檔不預載，由模型按需 Read。→ MEMORY.md 必須是「指標」而非「內容」。
- [固] Subagent 有**獨立**的 auto-memory 目錄，不與主 session 共用。
- [固] 主題檔可加 frontmatter `type: user | feedback | project | reference`（可選）；寫入時系統自動補 `modified` 時戳。
- [固] **無跨專案記憶**：同一 repo 的各 worktree 共用同一份；不同機器不同步（純本機檔案）。
- [實測] project-slug 規則：取 cwd，**每個非英數字元各轉一個 `-`**，磁碟代號小寫。例：`c:\Users\x\.claude` → `c--Users-x--claude`（`:` 與 `\` 各一個 `-`，`.` 也轉 `-`）。官方頁未明文列出此規則。

### 2. CLAUDE.md 階層與載入

- [固] 載入順序（前者為基底、後者疊加）：
  1. 管理政策（managed policy，組織層）
  2. `~/.claude/CLAUDE.md`（使用者全域）
  3. `./CLAUDE.md` 或 `./.claude/CLAUDE.md`（專案根）
  4. 子目錄 `CLAUDE.md`（**按需**——進到該目錄的檔案時才載）
  5. `.claude/rules/*.md`（**path-scoped**，可用 frontmatter 限定適用路徑）
  6. `CLAUDE.local.md`（個人覆寫，不進版控）
- [固] `@import`：路徑相對於**該檔所在位置**；遞迴上限 **4 層**；import 專案外的檔案**首次需使用者批准**。
- [固] 指令：`/init` 產生 CLAUDE.md（設 `CLAUDE_CODE_NEW_INIT=1` 走互動式多階段）；`/memory` 檢視／編輯已載入的記憶檔。
- [固] **已無「#」快速加記憶**捷徑（舊版行為，現版移除）。
- [固] 尺寸：單檔建議 **≤200 行**；**>4MB 直接跳過不載**。

### 3. Hooks

#### 3.1 事件表（28 種）

| 類別 | 事件 |
|------|------|
| Session | `SessionStart`, `SessionEnd`, `InstructionsLoaded` |
| Prompt | `UserPromptSubmit`, `UserPromptExpansion` |
| Tool | `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch` |
| Permission | `PermissionRequest`, `PermissionDenied` |
| Stop | `Stop`, `StopFailure` |
| 顯示 | `Notification`, `MessageDisplay` |
| Agent / Task | `SubagentStart`, `SubagentStop`, `TaskCreated`, `TaskCompleted`, `TeammateIdle` |
| 環境變動 | `ConfigChange`, `CwdChanged`, `DirectoryAdded`, `FileChanged`, `WorktreeCreate`, `WorktreeRemove` |
| Compact | `PreCompact`, `PostCompact` |
| Elicitation | `Elicitation`, `ElicitationResult` |

- [固] 較新事件（`PostToolBatch`、`PostCompact`、`TeammateIdle` 等）舊版 binary 不認得且**靜默忽略**；版本分裂細節見 `cc-hook-system`。

#### 3.2 UserPromptSubmit 注入協議

- [固] 成功路徑：**exit 0 + stdout 輸出 JSON**。要注入 context 必須寫在 `hookSpecificOutput.additionalContext`——放在頂層 `additionalContext` 不會被採用：
  ```json
  {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "……"}}
  ```
- [固] 阻擋：**exit 2**（stderr 內容回饋給模型）或 JSON `permissionDecision: "deny"`（PreToolUse 類）。多個 hook 同時回應時**最嚴格者優先**（deny > ask > allow）。

#### 3.3 Timeout 表

| 情境 | 預設上限 |
|------|---------|
| `command` / `http` / `mcp_tool` 型 hook（一般） | 10 分鐘 |
| `UserPromptSubmit` | **30 秒** |
| `MessageDisplay` | 10 秒 |
| `prompt` 型 hook | 30 秒 |
| `agent` 型 hook | 60 秒 |
| `SessionEnd` | **全部 hook 共 1.5 秒** |

- [固] 每個 hook 可在設定內用 `timeout`（秒）自訂，但不能超過事件級上限。

### 4. MCP

- [固] Scope 三層：
  - `local`（**預設**）：寫在 `~/.claude.json` 的該專案條目，只有本機該專案看得到。
  - `project`：`.mcp.json` 進版控，團隊共用；**首次使用需信任確認**。
  - `user`：`~/.claude.json` 跨專案，所有專案可用。
- [固] Hook matcher 命名：`mcp__<server>__<tool>`；plugin 內的 server 為 `mcp__plugin_<plugin>_<server>__<tool>`。matcher 支援 regex，例 `mcp__playwright__.*`。
- [固] hook type `mcp_tool` 可讓 hook **直接呼叫 MCP tool**，不經 shell。
- [固] 工具輸出上限 **25KB**（超過截斷），環變 `MAX_MCP_OUTPUT_TOKENS` 可調。
- [固] 工具 schema 根級 `anyOf` / `oneOf` 會被**自動展平**成單一 object schema。

### 5. Context 與 prompt cache

- [固] 自動 compaction：接近上限時自動壓縮；壓縮後**重注入 project-root CLAUDE.md**（含 @import）。手動 `/compact`。
- [固] Hook 接點：`PreCompact`（可存檔／注入指示）；`SessionStart` 以 `matcher: "compact"` 可攔「壓縮後重啟」時機。
- [固] 1M context 模型：可用時**自動選用**，不需手動切。
- [固] Prompt caching：cache 以「前綴一致」計。**每輪 `additionalContext` 變動 → 該輪新增內容不在 cache**，但前綴（system prompt、CLAUDE.md、先前對話）仍命中。→ 動態注入的成本＝注入段本身，不會打掉整條 cache。
- [固] 2.1.248 修正 OAuth token 刷新導致 cache miss；新增 `experimental.cacheTtl` 設定。

### 6. 官方最佳實踐

- [固] **CLAUDE.md 放行為指導**：build 指令、程式慣例、「永遠做 X／絕不做 Y」——穩定、可版控、團隊共用。
- [固] **auto-memory 放學習**：使用者的修正、偏好、無法從程式碼推導出的脈絡——會變、個人的。
- [固] CLAUDE.md **>200 行** → 拆成 skills（按需載入）或 `.claude/rules/*.md`（path-scoped），別再往主檔堆。
- [固] MEMORY.md 當索引用（200 行／25KB 是硬牆），內容進主題檔。

### 7. 近期 changelog（節錄）

| 版本 | 變更 |
|------|------|
| 2.1.248 | Hook 靜默失敗改為報錯；hook stdout JSON 解析失敗報錯（不再吞掉）；新增 `experimental.cacheTtl`；修 OAuth 刷新致 cache miss |
| 2.1.246 | `Notification` hook 在 Desktop / VS Code 修復；Bash cgroup 隔離改 opt-in |
| 2.1.238 | MCP `headersHelper` 不再繼承憑證類環變；MCP 連線中斷改明確提示 |

- [固] 2.1.248 的「靜默失敗改報錯」直接影響本專案：過去 hook 輸出壞 JSON 只是沒注入，現在會浮出錯誤——符合「可觀測性鐵律」，但也代表 hook 輸出必須嚴格合法。

### 8. 與本專案（~/.claude 原子記憶系統）的接點

只列事實，不列建議：

- [實測] **橋接檔**：`projects/c--Users-holylight--claude/memory/atom-index-bridge.md` 由 `tools/native-memory-bridge.py` 從 `memory/_atom_index.json` 鏡像產生（frontmatter `type: reference`），內容＝每個核心 atom 的「名稱 → Read 路徑 + trigger」指標，不含知識本體。`tools/sync-memory-index.py --write` 尾端（第 741 行附近）自動呼叫重產；失敗只 stderr 告警不阻斷。契約測試在 `hooks/verify/verify_native_bridge.py`。
- [實測] 原生 `MEMORY.md`（`projects/<slug>/memory/MEMORY.md`）只放一行指向橋接檔，遵守第 1 節的 200 行／25KB 預算；真正的 atom 索引在 `memory/MEMORY.md`（經 `~/.claude/CLAUDE.md` 的 `@memory/MEMORY.md` import 載入，走第 2 節路徑而非 auto-memory 路徑）。
- [實測] **UPS 30 秒上限**是注入管線（`hooks/workflow-guardian.py`）的硬約束；本機 `settings.json` 實際設 `timeout: 8`（guardian）＋ `3`（codex_companion），遠低於官方上限，換取 prompt 回應延遲。注入走第 3.2 節的 `hookSpecificOutput.additionalContext`。
- [實測] **SessionEnd 全部 hook 共 1.5 秒**是萃取（extraction）改走 detached worker 的根因：`hooks/extract-worker.py` 由 guardian 以獨立子程序 spawn（`run-hidden.py` 負責 Popen），存活超過 hook timeout，本機 LLM 萃取約 60 秒可跑完。`settings.json` 內 SessionEnd 的 `timeout: 30` 對官方 1.5 秒硬牆無效——只能靠 detached。
- [固] 第 5 節的 cache 行為說明為何 per-turn 注入預算要控在 token 而非字元（見 atom [[注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產]]）：每輪注入段全額計費、不命中 cache。

## 來源

- https://code.claude.com/docs/en/memory.md（Auto-memory、CLAUDE.md 階層、@import、/init、/memory）
- https://code.claude.com/docs/en/hooks-guide.md（事件表、注入範例）
- https://code.claude.com/docs/en/hooks.md（JSON 協議、exit code、timeout 表、matcher 命名）
- https://code.claude.com/docs/en/context-window.md（compaction、1M、prompt cache）
- https://code.claude.com/docs/en/mcp.md（scope、.mcp.json、輸出上限）
- https://github.com/anthropics/claude-code/releases（2.1.238 / 2.1.246 / 2.1.248）
- 本機實測：`settings.json`、`tools/sync-memory-index.py`、`tools/native-memory-bridge.py`、`hooks/extract-worker.py`、`hooks/run-hidden.py`（查證日 2026-08-28）
