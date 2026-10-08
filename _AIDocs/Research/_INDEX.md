# Research — 外部調查與業界比對索引

> 對外部世界（論文、廠商、社群專案）的查證整理；每份附查證日期與來源 URL，廠商自報數字標「自報」。
> 與本系統的判讀與取捨不放這裡，放 `DevHistory/`（帶日期的評估）或 `Architecture.md`（現況）。

## 文件清單

| # | 文件 | 說明 | keywords |
|---|------|------|----------|
| 1 | agent-memory-industry-survey.md | 2025–2026 LLM agent 長期記憶業界調查：Mem0/Letta/Zep/LangMem/A-MEM/ChatGPT 機制比較、LoCoMo/LongMemEval 檢索實證、寫入與注入端對策、Claude Code hooks/MCP 社群專案缺點、對本地 markdown-atom＋hook 系統的優缺/補強/修正評估 | agent memory, long-term memory, Mem0, Letta, MemGPT, Zep, Graphiti, LangMem, A-MEM, LoCoMo, LongMemEval, hybrid retrieval, BM25, RRF, rerank, ACT-R, decay, context rot, token budget, memory conflict, freshness, claude-mem, memsearch, MCP memory |
| 2 | coding-style-research.md | `rules/coding-style.md` 的出處：控制流階梯（最小威力原則、C++ Core Guidelines、Code Complete、Ajami/Feitelson 實測）、壓平手法、巢狀閾值（Linux kernel、SonarSource 認知複雜度、Cowan 4 chunk、arXiv 巢狀對 LLM Θ(n²)）、扁平化過頭反例、Codex 獨立審閱要點與分歧裁決 | coding style, 寫碼風格, 控制流, guard clause, nesting, 巢狀, cognitive complexity, least power, never nester, deep module, one-liner, Karpathy, codex review |
| 3 | grok-build-capability-self-report-2026-08.md | Grok Build（Grok 4.6）對「能否接上 Claude 的並行 inbox 機制」的能力自述原文（2026-08-24 session）：檔案讀寫／被外部喚醒途徑／閒置輪詢／MCP 設定層／工具連用上限／兩套持久記憶／自動載入的規則檔／可調設定；結論已收斂進 atom `並行llm即時通訊-inbox機制` | grok, grok build, inbox, 並行 LLM, monitor, scheduler, MCP, config.toml, 記憶, rules 載入, 跨 harness |
| 4 | code-smells/README.md | 何謂壞味道（code smells）參考文件：閱讀樹根＋九分支（經典目錄、設計與架構、C#／.NET 與 Unity、Client/Server 線上遊戲、並行效能資源、測試資料設定註解、可讀性與度量門檻、AI 寫碼與演化、本機兩個遊戲專案的案例與判斷原則）＋513 條一句話索引 `00-index.md`；症狀路由、重疊對照、證據等級 | code smell, 壞味道, 臭味, anti-pattern, 反模式, refactoring, 重構, Fowler, God Class, Shotgun Surgery, design smell, architecture smell, async void, sync over async, IDisposable, Unity, client/server, 信任用戶端, 刷物, 冪等, test smell, SQL antipattern, cognitive complexity, 巢狀, 狀態所有權, 雙存, 靜默失敗, AI 生成程式碼 |
