# Claude Code Hook System

- Scope: global
- Confidence: [固]
- Trigger: hook system, hooks.json, pre_tool_use, post_tool_use, session_start, session_end, hook event, hook 事件, lifecycle hook, 生命週期, hook 開發, permission_request, PromptRequest, hook timeout, updatedInput, sub-agent injection, Agent tool, tool_response, hot reload
- Last-used: 2026-04-01
- Confirmations: 1
- Related: cc-harness-overview, cc-tool-system, cc-permission-system, cc-skills-plugins

## 知識

### Hook 事件類型（14 種）
- [固] setup, session_start, session_end
- [固] pre_tool_use, post_tool_use
- [固] pre_compact, post_compact
- [固] permission_denied, stop_failure
- [固] subagent_start, subagent_stop
- [固] task_created, task_completed
- [固] **2026-06-01 實測補正（反編譯實跑 binary 字串表 + Zod schema，非上游 dated source）**：真實事件名為 **camelCase**（非上列 snake_case）。實跑 v2.1.159 roster：`PreToolUse`/`PostToolUse`/`PostToolUseFailure`/**`PostToolBatch`**/`UserPromptSubmit`/`UserPromptExpansion`/`SessionStart`/`SessionEnd`/`Setup`/`PreCompact`/**`PostCompact`**/`Notification`/`MessageDisplay`/`SubagentStart`/`SubagentStop`/`TaskCreated`/`TaskCompleted`/`Stop`/`StopFailure`/`InstructionsLoaded`/`ConfigChange`/`CwdChanged`/`FileChanged`/`WorktreeCreate`/`WorktreeRemove`/`Elicitation` 等。
- [固] **版本分裂陷阱**：`PostCompact`/`PostToolBatch` 等較新事件**僅存在於新版**——實測 VSCode 擴充套件 `claude.exe` **v2.1.159 有**；終端 native install **v2.1.37 grep 0 次（不存在）**。未知事件的 hook 設定會被**靜默忽略**（不報錯）。為新事件設 hook 前先確認執行環境版本。
- [固] `PostToolBatch`：一批（含並行）工具全解析後觸發**一次**（`PostToolUse` 為 per-tool），於下個 model request 前；payload `tool_calls[]`，**支援 additionalContext 注入且可 block**，無 matcher。
- [固] `SessionStart.source` enum = `startup|resume|clear|`**`compact`**；`PreCompact`/`PostCompact` matcher = `trigger`(`manual`/`auto`)；`PostCompact` payload = `trigger`+`compact_summary`；`InstructionsLoaded.load_reason` 含 `compact`（→ 壓縮時 CLAUDE.md/@import 重載，atom 索引不丟）。壓縮完成路徑（`compact_end`）實測觸發 **PostCompact**（`bPH`）。

### Hook 定義格式（.claude/hooks.json）
- [固] 條件觸發：`if: { tool: "BashTool", input_contains: "npm publish" }`
- [固] 執行：`run: "node scripts/check.js"`, `shell: "bash"`, `env: {...}`

### 執行架構
- [固] 三層序列：Harness 匹配 → 子程序執行（JSON over stdout/stdin）→ 結果聚合
- [固] executeHooks 是 async generator，逐步 yield 結果（不等全部完成）
- [固] 子程序完成由三路 Promise.race：childClosePromise / childErrorPromise / childIsAsyncPromise

### 環境變數注入
- [固] CLAUDE_TOOL_NAME, CLAUDE_TOOL_INPUT, TOOL_INPUT_FILE_PATH, TOOL_INPUT_COMMAND
- [固] CLAUDE_SESSION_ID, CLAUDE_PROJECT_DIR

### Hook 來源與優先級（5 層）
- [固] 使用者全域 → 專案 → Plugin hooks → Skill hooks → MDM/Managed

### Hook 修改工具輸入（updatedInput）
- [固] Hook 可回傳 updatedInput 改寫工具輸入（如 `--force` → `--force-with-lease`）
- [固] 透明度代價：Claude 不知道實際執行與其意圖的差異
- [固] **欄位名是 `updatedInput`（非 `modifiedInput`）**，置於 `hookSpecificOutput`（與 `permissionDecision` 同層）；值為**完整 tool_input 物件**（取代原 input，須保留所有原鍵、只改目標欄）。2026-06-01 對 **Agent/Task 工具實測採納**：PreToolUse prepend 記憶 blob 到 sub-agent 的 `prompt`，sub-agent 實際收到（以 PostToolUse `tool_response.prompt` 為 ground truth 驗證，非靠 sub-agent 自評——LLM 對自身完整 prompt 內省不可靠）。
- [固] settings.json hooks 設定**檔案變更即熱重載**：同一 session 內新增/改 matcher 即生效，無需重啟 CC（與「Memoized Hook Loading：檔案變更驅動快取失效」一致）。
- [固] Agent/Task 的 PostToolUse `tool_response` 含 `agentId` / `agentType` / `content`(list[{type,text}]) / `prompt`(**注入後的完整 prompt**) / `status` / `totalTokens` / `usage`；頂層另有 `tool_use_id` / `transcript_path` / `cwd` → 可**無狀態**回推 PreToolUse 注入內容並做歸因（避開 Pre→Post 跨進程關聯與 parallel agent race）。

### PromptRequest 協議（Hook 向使用者提問）
- [固] Hook 輸出 PromptRequest JSON → Claude Code 呈現選項 → 使用者選擇 → PromptResponse 寫回 stdin
- [固] 多個請求必須序列化（promptChain），無法並行

### permission_request Hook 特殊語義
- [固] 在權限決定過程中執行（與 InteractiveHandler / BashClassifier 競爭）
- [固] 原子性 claim() 機制：Hook claim 成功 → 使用者對話框被取消
- [固] 企業 MDM hook 可完全繞過人工審批

### 超時與錯誤隔離
- [固] TOOL_HOOK_EXECUTION_TIMEOUT_MS = 10 分鐘
- [固] Hook 崩潰/超時 → 結果被忽略，工具照常執行（建議性而非強制性）
- [固] Memoized Hook Loading：檔案變更驅動快取失效

### Hook 輸出能力差異（additionalContext 可用性）
- [固] PostToolUse 的 additionalContext 是**即時生效**的（同一 turn 內 Claude 可見，不需等下一輪）
- [固] Async hook 完成後 systemMessage 自動注入下一輪（additionalContext 同理，但 Stop 不適用）
- [固] Stop hook 不支援 additionalContext，只有 block + reason + systemMessage
- [固] **2026-06-01 實測：支援 `hookSpecificOutput.additionalContext` 注入的事件**（Zod schema 實證）：`UserPromptSubmit`(required) / `PostToolUse` / **`PostToolBatch`** / `SessionStart` / `SubagentStart` / `PostToolUseFailure` / `UserPromptExpansion` / `Notification` / `Setup`。
- [固] **⚠ `PostCompact` 不支援 additionalContext（無法注入）**——只收 `trigger`+`compact_summary`。故「壓縮後重注入記憶」**不能靠 PostCompact**，須改用 `SessionStart(compact)` 或 **`PostToolBatch`**。本核心選配 #4 採「PostCompact stash → 下個 PostToolBatch 一次性注入」閉合 mid-turn auto-compact 失憶缺口（`plans/deep-wobbling-bentley.md`、`hooks/handlers/post_compact.py`+`post_tool_batch.py`）。
- [觀] 待實測（Phase-0 `/compact` 探針 `Logs/compact-probe.log`）：2.1.159 auto-compact 是否**也**觸發 `SessionStart(source=compact)` → 判定 `session_start.py` 既有 compact 分支是否已成死碼。

## 行動

- 開發 hook 腳本：用 JSON stdout/stdin 協議，任何語言都可
- pre_tool_use 用於攔截/修改工具輸入；post_tool_use 用於觀察記錄
- permission_request 用於自動化權限決策（但需注意監督空間消失）
- 來源：https://claude-code-harness-blog.vercel.app/chapters/05-hook-system/
