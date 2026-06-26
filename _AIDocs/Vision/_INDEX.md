# Vision — 發想與前瞻設計索引

> 本資料夾收容**發想類延伸知識**：尚未開工、但「說不定某天會真的拿出來設計、做成成品」的前瞻平台設計、現有應用比對、架構推演。
> 性質：read-on-demand 參考層，**非 atom、非 `_atoms/`、零 session 注入成本**（同 ClaudeCodeInternals / DevHistory）。版控、跨 session、外部專案零負擔。
> 與 `memory/_staging/` 區別：_staging 放「進行中規劃/TODO」（gitignored、易變）；Vision 放「有深度、值得長期保留迭代的發想」（版控、穩定）。
> 最近更新：2026-06-26（建立 Vision 分類 + 首個主題：JARVIS 企業 AI 平台）

---

## 主題清單

| # | 主題 | 緣起 | 涵蓋願景 | 入口 |
|---|------|------|---------|------|
| 1 | JARVIS 式企業 AI 開發協作平台 | 2026-06-26 對談：使用者提 16 條「企業內部 JARVIS」願景，問「原子記憶系統還缺什麼才能當核心」 → gap 分析 + 多 agent 研究補充 | 16 條願景全覆蓋（記憶/編排/路由/工具生態/攝取/多模態/作業紀錄/安全治理/演進） | [jarvis-enterprise-ai-platform/README.md](jarvis-enterprise-ai-platform/README.md) |

---

## 主題 1 — JARVIS 企業 AI 平台：子檔清單

> 定調：**原子記憶系統是「海馬迴」，JARVIS 是「大腦」；真正的核心是編排者，記憶是它最關鍵的器官。** 完整對照與路線圖見主題 [README](jarvis-enterprise-ai-platform/README.md)。

| 檔 | 主題 | 對應願景 | keywords |
|----|------|---------|----------|
| [README](jarvis-enterprise-ai-platform/README.md) | 定調 + 願景16條對照 + 缺口分級 + P0-P2 路線 + 子檔導讀 | 全 | jarvis, 願景, gap 分析, 海馬迴, 編排核心, 演進路徑 |
| [01](jarvis-enterprise-ai-platform/01-memory-as-shared-cortex.md) | 記憶作為共享皮層（多租戶/權限感知檢索） | #1 #3 #10 | mem0, letta, zep, cognee, 多租戶, RLS, qdrant, 權限感知檢索, 存取控制 |
| [02](jarvis-enterprise-ai-platform/02-orchestration-core.md) | 編排核心 + 跨角色協作（前額葉） | #2 #4 #16 | langgraph, crewai, autogen, magentic, agent framework, adk, devin, 任務編排, 驗收閘 |
| [03](jarvis-enterprise-ai-platform/03-model-routing.md) | 多模型主動分工（哪家強派誰） | #2 | model router, portkey, openrouter, routellm, litellm, capability scoring, 成本品質 |
| [04](jarvis-enterprise-ai-platform/04-tool-registry-and-protocols.md) | 工具認證註冊與互通協定 | #5 | mcp registry, a2a, agntcy, 簽章, content-addressed, 三層棧, 工具上架 |
| [05](jarvis-enterprise-ai-platform/05-knowledge-ingestion.md) | 知識攝取 + 跨專案分析 | #8 #16 | glean, sourcegraph, scip, gitlab orbit, 知識圖, 權限同步, 無效率報告 |
| [06](jarvis-enterprise-ai-platform/06-multimodal-io.md) | 多模態感官（STT/翻譯/出圖/螢幕） | #7 #9 #15 | whisperx, fireflies, diarization, 即時翻譯, stable diffusion, qwen-vl, 螢幕理解 |
| [07](jarvis-enterprise-ai-platform/07-work-journal-and-activity.md) | 作業紀錄與月誌（避監視紅線） | #12 | 作業紀錄, recall, rewind, 事件日誌, 決策日誌, 隱私分級, 員工監控合規 |
| [08](jarvis-enterprise-ai-platform/08-security-governance-compliance.md) | 安全/權限/治理/合規 + 業務流程 | #6 #13 | rbac, sso, jwt, 檢索acl, 不可竄改稽核, eu ai act, ai gateway, 請假填單 |
| [09](jarvis-enterprise-ai-platform/09-evolution-from-current-system.md) | 從現有系統長成平台（落地切入點總整合） | #11 #14 + 綜合 | 演進路線圖, 絞殺者模式, local-first, 跨裝置, 自維護, 護城河, P0-P2 |
