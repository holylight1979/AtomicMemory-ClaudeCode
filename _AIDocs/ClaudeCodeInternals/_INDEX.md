# Claude Code Internals — 架構深度分析索引

> 來源：https://claude-code-harness-blog.vercel.app/（14 章完整收錄）
> 用途：開發 hooks、skills、tools、MCP 伺服器時的架構參考
> 最近更新：2026-11-04（新增 `Docs/` 官方文件全收割 228 頁＋索引＋現況對帳＋進化分析；收割工具 `tools/cc_docs_harvest.py`）
> 前次：2026-05-27（V5 GA 簽收同步；本資料夾為 CC 主程式架構參考，與我們 V5 升版無直接耦合）
>
> ⚠️ **來源與時效說明**（user 補註，2026-05-28）：本資料夾為 2026 年 4 月初**從錯放出來的 CC sources（claude-code 主程式源碼）產生的研究紀錄**。Claude Code 自此後仍在快速演進，且 CC 內部結構未公開穩定 API。**本資料夾僅有「部分參考價值」**：
> - 適合：理解 CC harness 大方向（query loop、tool system、hook lifecycle、permission funnel 等概念架構）
> - 不適合：當作精確規格直接套用（行數、欄位名、private API、feature flag 等具體實作很可能已過時）
> - 開發 hook/skill/MCP 時：以 CC 官方文件 + 實測 hook event 行為為主，本資料夾為輔助理解。

## 官方文件收割（2026-11-04 起，現行規格以此為準）

> `Docs/` 是 code.claude.com/docs/zh-TW **全部 228 頁官方 markdown 原文**（含 changelog／claude-tag 英文版），依官方分類八夾落檔，另附 LLM 導讀卡與索引。上面 14 章是 2026-04 源碼研究紀錄，只當概念參考；**查功能、鍵名、事件名、數字限制一律先查 `Docs/`**。

| 入口 | 用途 |
|------|------|
| [Docs/_INDEX.md](Docs/_INDEX.md) | 高速閱讀索引：八夾總覽＋各頁一句話／何時讀／關鍵字 |
| [Docs/_KEYWORDS.md](Docs/_KEYWORDS.md) | 關鍵字反查（2,348 詞 → 頁）＋各頁「記憶系統接點」彙整 |
| [Docs/_GLOSSARY.md](Docs/_GLOSSARY.md) | 453 個新名詞／術語白話表 |
| [Docs/08-whats-new/TIMELINE-新功能與新名詞.md](Docs/08-whats-new/TIMELINE-新功能與新名詞.md) | 新名詞首次出現版本、165 版時間線、已移除／改名 |
| [Docs/_現況對帳-原子記憶系統用到的CC機制.md](Docs/_現況對帳-原子記憶系統用到的CC機制.md) | 原子記憶系統現用的 hook 事件／設定／擴充／多 session 對帳表＋自製但原生可能已有的 25 項候選 |
| [../DevHistory/v6.1-對CC適應性補正-2026-11/analysis/](../DevHistory/v6.1-對CC適應性補正-2026-11/analysis/) | 依官方新能力分析原子記憶系統可進化點（三面向＋總整）；v6.1 照它做完，歸在 DevHistory |
| `python ~/.claude/tools/cc_docs_harvest.py fetch` / `index` | 重抓原文與 manifest／重建索引三檔 |

---

## 文件清單

| # | 文件 | 對應章節 | 說明 | keywords |
|---|------|---------|------|----------|
| 1 | cc-harness-overview.md | Ch.1 | 架構鳥瞰、啟動序列因果鏈、端對端旅程、責任矩陣 | harness engineering, 架構, 啟動序列, startup flow, query loop, 責任矩陣 |
| 2 | cc-tool-system.md | Ch.2 | Tool 型別定義、fail-closed 預設、雙軌驗證、執行狀態機 | tool system, Tool interface, buildTool, inputSchema, fail-closed, isConcurrencySafe, isReadOnly |
| 3 | cc-agent-orchestration.md | Ch.3 | 子代理 FSM、CacheSafeParams、Prompt Cache Sharing、Worktree 隔離 | agent, subagent, CacheSafeParams, prompt cache, worktree, coordinator mode, multi-agent, fork |
| 4 | cc-permission-system.md | Ch.4 | 四層權限、七步決策漏斗、Promise.race 競賽、BashClassifier | permission, 權限, PermissionMode, BashClassifier, bypassPermissions, racing, denial tracking |
| 5 | cc-hook-system.md | Ch.5 | 14 種 Hook 事件、JSON 協議、updatedInput、PromptRequest、超時隔離 | hook, hooks.json, pre_tool_use, post_tool_use, session_start, lifecycle, permission_request |
| 6 | cc-context-management.md | Ch.6 | 四層壓縮策略、Microcompact、contextCollapse、CLAUDE.md 載入、Memoization | context, compaction, autocompact, microcompact, collapse, CLAUDE.md, memoize |
| 7 | cc-query-loop.md | Ch.7 | Master FSM、Generator 模式、Batch Partition、Terminal/Continue 條件 | query loop, concurrency, batch partition, StreamingToolExecutor, generator, 狀態機 |
| 8 | cc-skills-plugins.md | Ch.8 | Skill markdown 定義、MCP Transport、Plugin 隔離、MCP Sampling | skill, plugin, MCP, SkillTool, MCPTool, MCP sampling, MCP transport |
| 9 | cc-state-management.md | Ch.9 | 極簡 Store、ToolUseContext DI、DeepImmutable、雙層快取 | state, AppState, AppStateStore, ToolUseContext, DeepImmutable, 依賴注入 |
| 10 | cc-design-patterns.md | Ch.10 | 7 大設計模式、Harness Engineering Checklist | design pattern, 設計模式, fail-open, fail-closed, memoize, subprocess JSON, checklist |
| 11 | cc-prompt-engineering.md | Ch.11+13+14 | 5 層優先、17 Section、DYNAMIC_BOUNDARY、防禦性模式、Tool Prompt | prompt, system prompt, DYNAMIC_BOUNDARY, prompt cache, section, NO_TOOLS, BashTool prompt |
| 12 | cc-feature-inventory.md | Ch.12 | Feature flags、隱藏 CLI 參數 30+、環境變數、Server commands | feature flag, GrowthBook, KAIROS, daemon, bridge, agent triggers, cron, claude server |
| 13 | console-window-forensics.md | 本機實測 | Windows 黑窗（閃 console）完整案卷：機制、修法三式、診斷工具、2026-09-02 殘餘閃窗源判定 | 黑窗, 閃窗, console, WindowsTerminal -Embedding, CREATE_NO_WINDOW, pythonw, run-hidden, console-window-trace |
| 14 | cc-native-memory-hooks-mcp.md | 官方文件 2026 | Auto-memory 路徑與 200 行預算、CLAUDE.md 六層載入、28 種 Hook 事件＋UPS 注入協議＋timeout 表、MCP scope、compaction/cache、2.1.238–248 changelog、與原子記憶系統橋接接點 | auto-memory, MEMORY.md, project-slug, CLAUDE.md 階層, @import, rules, UserPromptSubmit, additionalContext, hook timeout, SessionEnd 1.5s, MCP scope, .mcp.json, MAX_MCP_OUTPUT_TOKENS, compaction, prompt cache, cacheTtl, native-memory-bridge |

---

## 關聯圖（開發時查閱路徑）

```
開發 Hook     → cc-hook-system → cc-tool-system → cc-permission-system
開發 Skill    → cc-skills-plugins → cc-tool-system → cc-query-loop
開發 MCP      → cc-skills-plugins → cc-agent-orchestration
優化 Prompt   → cc-prompt-engineering → cc-context-management
理解並行      → cc-query-loop → cc-tool-system → cc-design-patterns
多 Agent      → cc-agent-orchestration → cc-permission-system → cc-query-loop
除錯/功能探索 → cc-feature-inventory
```
