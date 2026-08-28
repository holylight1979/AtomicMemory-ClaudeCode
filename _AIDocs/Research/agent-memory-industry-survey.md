# LLM Agent 長期記憶系統 — 業界調查（2025–2026）
> 用途：設計／評估本地原子記憶系統（markdown atom + hook 注入 + 向量服務）時的業界對照基準；涵蓋主流框架機制、檢索/寫入/注入實證、Claude Code 社群做法與缺點。
> 查證日期：2026-08-28；來源皆附 URL；廠商自報數字標明「自報」。

---

## 0. 關鍵字對照表（中↔英）

| 中文 | 英文 |
|---|---|
| agent 長期記憶 | agent memory / long-term memory |
| 情節／語意／程序記憶 | episodic / semantic / procedural memory |
| 記憶鞏固 | memory consolidation |
| 混合檢索 | hybrid retrieval（BM25 + vector） |
| 倒數排名融合 | reciprocal rank fusion (RRF) |
| 重排序 | rerank / cross-encoder |
| 活化值 | ACT-R activation（base-level + spreading + noise） |
| 衰減／近期性 | decay / recency |
| 間隔複習 | spaced repetition / Ebbinghaus forgetting curve |
| 上下文工程 | context engineering |
| 注入預算 | token budget / per-turn injection budget |
| 上下文腐化／迷失於中段 | context rot / lost in the middle |
| 入場閘 | memory admission control |
| 新鮮度／衝突解決 | freshness / memory conflict resolution |
| 記憶評測集 | LoCoMo、LongMemEval、MemConflict、ForgetEval |
| 社群名詞 | Claude Code hooks、MCP memory server、claude-mem、memsearch |

---

## 1. 主流框架比較表

| 框架 | 記憶單位 | 寫入時機 | 檢索 | 遺忘／去重／衝突 |
|---|---|---|---|---|
| **Mem0**（[arXiv 2504.19413](https://arxiv.org/html/2504.19413v1)） | 短句「salient facts」集合；圖版 Mem0^g 為實體-關係圖 | 每輪：以「當前訊息對 + 對話摘要 + 近 10 則訊息」交 LLM 萃取 | 論文版：向量 top-k；2026 版改語意 + BM25 + 實體匹配多訊號融合 + rerank（[自報](https://mem0.ai/blog/state-of-ai-agent-memory-2026)） | 每筆候選取 top-10 相似記憶交 LLM 判 ADD / UPDATE / DELETE / NOOP；無時間衰減 |
| **Letta / MemGPT**（[Letta blog](https://www.letta.com/blog/agent-memory/)） | 常駐 context 的 memory blocks（有字數上限）+ recall（對話史）+ archival（pgvector 段落） | agent 自己 tool call 改寫 block；sleep-time agent 背景整理 | 向量／全文（archival 為向量相似度） | 無明文衝突協定，靠 agent 改寫 block；無自動衰減 |
| **Zep / Graphiti**（[arXiv 2501.13956](https://arxiv.org/abs/2501.13956)） | episode → entity → fact edge；每 edge 帶雙時間軸（valid_at / invalid_at） | 每個 episode 入圖即抽實體與關係 | cosine + BM25 + 圖 BFS，再 RRF / MMR / cross-encoder 重排 | 新事實使舊 edge 失效（invalidate，不刪除） |
| **LangMem**（[conceptual guide](https://github.com/langchain-ai/langmem/blob/main/docs/docs/concepts/conceptual_guide.md)） | semantic（collection 或 profile）、episodic（成功案例）、procedural（system prompt 規則） | hot-path tool（對話中）或背景 memory manager | 相似度 × importance × strength（recency / frequency） | collection 需 consolidate / invalidate；profile 直接覆寫；無自動 decay 細節 |
| **A-MEM**（[arXiv 2502.12110](https://arxiv.org/html/2502.12110)） | Zettelkasten note：內容 + 關鍵字 + tag + context 描述 + 連結 | 每新 note 生成連結，並「演化」舊 note 的屬性 | embedding 相似度 | 無衰減；每操作約 1,200 tokens，較 MemGPT 省 85–93% |
| **ChatGPT memory**（[Willison 2025/05](https://simonwillison.net/2025/May/21/chatgpt-new-memory/)、[OpenAI Dreaming](https://openai.com/index/chatgpt-memory-dreaming/)） | 顯式 saved memories + 背景整理的 chat-history「dossier」 | 使用者說「記住」或背景 curation（Dreaming） | 非 RAG：整段摘要注入 system prompt | 背景 curation；使用者失去 context 控制、舊事污染新對話（Willison 批評） |

---

## 2. 檢索實證

### 2.1 Benchmark 數字

| 來源 | 結論 |
|---|---|
| [LongMemEval（arXiv 2410.10813）](https://arxiv.org/html/2410.10813) | fact-augmented key expansion：recall@k +9.4%、最終準確率 +5.4%；time-aware query expansion：recall +11.3%（round 粒度）／+6.8%（session 粒度）；商用系統相對離線閱讀：ChatGPT −37%、Coze −64%；Llama 3.1 8B 檢索超過 3k tokens 反而掉 |
| [Zep（arXiv 2501.13956）](https://arxiv.org/abs/2501.13956) | LongMemEval 63.8 → 71.2（+18.5%），延遲 −90%；DMR 94.8 vs MemGPT 93.4 |
| [Mem0 論文](https://arxiv.org/html/2504.19413v1) | LoCoMo LLM-as-Judge：Mem0 66.88、Mem0^g 68.44；Zep 61.70（單跳）；OpenAI 52.9（自報）；較 full-context 省 >90% token、p95 延遲 −91% |
| [Mem0 2026 報告（自報）](https://mem0.ai/blog/state-of-ai-agent-memory-2026) | LoCoMo 92.5、LongMemEval 94.4；同表 Zep 80.32 / 71.2、Letta 74.0、OpenAI 52.9 |
| [Mastra Observational Memory](https://mastra.ai/research/observational-memory) | LongMemEval 94.87（gpt-5-mini）、gpt-4o 84.23 > oracle 82.4；**不做逐輪檢索**，固定前綴吃 prompt cache，成本 4–10× ↓；多 session 類別停在 ~87.2% |
| [Verbatim vs Extracted（arXiv 2601.00821）](https://arxiv.org/abs/2601.00821) | 同管線下原文 chunk 勝萃取物：LoCoMo 43.9 vs 28.0、LongMemEval-S 67.4 vs 45.4；語意圖也補不回差距 |

### 2.2 Hybrid + RRF、Rerank

| 來源 | 結論 |
|---|---|
| [Scientific code search（arXiv 2607.05443）](https://arxiv.org/pdf/2607.05443) | Hybrid-RRF 與 Hybrid-Rerank 比較：cross-encoder rerank 在 6 指標中 5 項最佳 |
| [Hybrid search 2026 整理](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026) | WANDS：hybrid NDCG 0.7497，較 BM25（0.6983）／vector（0.6953）+7.4% |
| [Zep](https://arxiv.org/abs/2501.13956)、[memsearch](https://github.com/zilliztech/memsearch)、[Mem0 2026](https://mem0.ai/blog/state-of-ai-agent-memory-2026) | 三者皆採 BM25 + dense + RRF（Zep 另加 MMR / cross-encoder） |

### 2.3 ACT-R / 衰減

| 來源 | 結論 |
|---|---|
| [ACT-R-inspired（HAI 2025）](https://dl.acm.org/doi/10.1145/3765766.3765803) | base-level activation（頻率 + 近期性，decay d≈0.5）+ 語意相似 + 高斯噪音；僅取得摘要層級描述 |
| [Human-Inspired Memory Architecture（arXiv 2605.08538）](https://arxiv.org/html/2605.08538v1) | 純決定性生命週期：指數衰減 λ=0.001（半衰期≈29 天）、成熟期 1 週才達檢索門檻；issue 資料集 58% 減量下留存精度 97.2%；**但 LongMemEval 準確率與 baseline 信賴區間重疊**（76.8 vs 78.4）→ 衰減是省量、不是提準 |
| [MemoryBank（arXiv 2305.10250）](https://arxiv.org/abs/2305.10250) | Ebbinghaus 曲線更新記憶強度；spaced repetition 於 agent 記憶的應用文獻仍少（[FOREVER](https://arxiv.org/html/2601.03938v2) 用於 continual learning replay） |

### 2.4 記憶流冗餘

| 來源 | 結論 |
|---|---|
| [xMemory（arXiv 2602.02007）](https://arxiv.org/abs/2602.02007) | 互動流高度相關、近重複多，扁平相似度會回傳冗餘 context；先解耦成組件再聚合成群組、由上而下檢索 |
| [Chroma context rot](https://www.trychroma.com/research/context-rot) | 打亂順序的 haystack 反比邏輯連貫者表現好（18 模型一致） |

---

## 3. 寫入端

| 主題 | 來源 | 結論 |
|---|---|---|
| 萃取有損 | [arXiv 2601.00821](https://arxiv.org/abs/2601.00821) | 「機制是有損蒸餾，非結構本身」；結構化記憶應**補充**原文而非取代 |
| 新鮮度決定性 | [arXiv 2606.01435](https://arxiv.org/html/2606.01435v1) | BM25 取候選 → LLM 抽同義事實 → 程式 `max(serial)`；MAB FactConsolidation 262K：單跳 82% vs HippoRAG-v2 54%、Mem0 18%、Zep 7%；結論「新鮮度比較移出 prompt、進決定性程式碼」 |
| 入場閘 | [A-MAC（arXiv 2603.04549）](https://arxiv.org/abs/2603.04549) | 五因子：未來效用、事實信心、語意新穎度、時間近期性、內容型別先驗；LoCoMo F1 0.583、延遲 −31%；**內容型別先驗最有影響** |
| 衝突 | [MemConflict（arXiv 2605.20926）](https://arxiv.org/abs/2605.20926) | 三類衝突（動態／靜態／條件）；失敗主因「缺支撐記憶」與「檢回卻沒用」；歷史越長、距離越遠越差 |
| LLM 放置位置 | [arXiv 2606.15903](https://arxiv.org/abs/2606.15903) | 13 種組態：純決定性在同義正規化近 0%；LLM 放 mutation-time hook 整體最佳 91.7–93.2%（2.3s/case vs 決定性 64–191ms） |
| 去重實務 | [Mem0](https://arxiv.org/html/2504.19413v1)、[d2a8k3u](https://github.com/d2a8k3u/claude-code-memory)、[memsearch](https://github.com/zilliztech/memsearch) | Mem0：top-10 相似 + LLM 四操作；d2a8k3u：≥95% cosine 自動合併；memsearch：SHA-256 chunk hash 免重複 embedding |
| 未解 | [Mem0 2026 報告](https://mem0.ai/blog/state-of-ai-agent-memory-2026) | staleness：高相關但過時的事實「自信地錯」；系統多是覆寫而非建模變化 |

---

## 4. 注入端

| 主題 | 來源 | 結論 |
|---|---|---|
| Context rot | [Chroma](https://www.trychroma.com/research/context-rot) | 18 個前沿模型隨輸入變長全部退化；**單一 distractor 即降分**、多個疊加；問句-答案相似度低者退化更快 |
| Anthropic 指引 | [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 「找最小的高訊號 token 集合」；just-in-time：保留輕量指標（路徑/查詢）按需載入；結構化筆記存 context 外再拉回 |
| 官方 auto memory | [Claude Code docs](https://code.claude.com/docs/en/memory) | MEMORY.md 只載前 200 行或 25KB；主題檔按需讀；CLAUDE.md 目標 <200 行，越長遵循度越低；CLAUDE.md 以 user message 注入，非 system prompt |
| 小模型上限 | [LongMemEval](https://arxiv.org/html/2410.10813) | Llama 3.1 8B 檢索超過 3k tokens 掉分 |
| 固定前綴 | [Mastra](https://mastra.ai/research/observational-memory) | 逐輪動態注入破壞 prompt cache；穩定觀察日誌可快取 |
| 社群經驗值 | [SuperBrain](https://alexandrekhoury.com/writing/superbrain-session-memory-claude-code)、[d2a8k3u](https://github.com/d2a8k3u/claude-code-memory)、[alexanderop](https://github.com/alexanderop/claude-code-memory) | SessionStart ≈1,200 tokens；每 prompt ≤6 條精簡匹配；MEMORY.md 2,200 字元 + USER.md 1,375 字元上限；claude-mem v3「全塞」污染 context → v4 退回 800-token 摘要 + 顯式搜尋 |
| 反例 | [Willison](https://simonwillison.net/2025/May/21/chatgpt-new-memory/) | 不可見的整段 dossier 注入使無關舊事污染新任務 |

---

## 5. Claude Code hooks / MCP 社群專案

| 專案 | 做法 | 被指出的缺點 |
|---|---|---|
| [claude-mem](https://github.com/thedotmack/claude-mem)（[hooks 架構](https://docs.claude-mem.ai/hooks-architecture)） | 5 hook：PostToolUse 入佇列 → 背景 Bun worker 叫 LLM 壓縮 → SQLite FTS5；Stop 用 Agent SDK 摘要；SessionStart 注入 10 份摘要 + 50 條觀察的「漸進揭露索引」 | Token 暴衝（[#618](https://github.com/thedotmack/claude-mem/issues/618)：10 則訊息燒完 5 小時額度，confirmed bug）；hook timeout 60–120s；worker 掛需手動重啟；觀察可能靜默遺失；首用約 30s 啟動延遲（[review](https://andrew.ooo/posts/claude-mem-persistent-memory-claude-code/)） |
| [SuperBrain](https://alexandrekhoury.com/writing/superbrain-session-memory-claude-code) | 5 個擷取 hook 零 LLM、append NDJSON；背景蒸餾；SessionStart hybrid（vector + BM25 + RRF）× recency 取 ~1,200 tokens 注入 | 作者自陳核心痛點「storage is solved, injection isn't」：claude-mem 累積 8,785 條觀察無一自動浮現；只在 SessionStart 注入、無逐輪 |
| [alexanderop/claude-code-memory](https://github.com/alexanderop/claude-code-memory) | 拒絕自動擷取；SessionStart 注入受限 MEMORY.md / USER.md；UserPromptSubmit 用 regex 偵測「糾正」；exact-dup no-op；子程序禁寫 skill | 容量極小（2,200 字元）；策展負擔在使用者；skill 歸檔預設 notify-only |
| [d2a8k3u/claude-code-memory](https://github.com/d2a8k3u/claude-code-memory) | 5 類記憶 + 6 種關係；FTS5 + sqlite-vec + TinyBERT cross-encoder；型別化衰減（pattern 慢衰、episodic 快衰、semantic/procedural 永久）；prompt / edit / bash / 錯誤都觸發搜尋；每 prompt ≤6 條 | 首次啟動 10–30s（下載 all-MiniLM-L6-v2 90MB）；文件無明列限制章節 |
| [memsearch（zilliztech）](https://github.com/zilliztech/memsearch) | markdown 為真源、Milvus 為可重建影子索引；BM25 + dense + RRF；SHA-256 chunk 去重；L1 chunk → L2 整節 → L3 原始 transcript 漸進；每輪 Haiku 摘要寫日檔 | 注入預算、chunk 規則、完整 hook 規格未公開 |
| [MCP server-memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) | JSONL 存實體 / 關係 / 觀察，agent 以 tool 讀寫 | 無時間戳、信心分數、實體消歧（[mem0 blog](https://mem0.ai/blog/mcp-knowledge-graph-memory-enterprise-ai)）；memory-poisoning 攻擊面（[arXiv 2604.16548](https://arxiv.org/html/2604.16548v1)） |
| [mem0 MCP / OpenMemory](https://mem0.ai/blog/claude-code-memory) | 雲端 Platform MCP 或本地 OpenMemory MCP | OAuth 到期不刷新（[#4876](https://github.com/mem0ai/mem0/issues/4876)）；add 失敗、search 正常（[#3400](https://github.com/mem0ai/mem0/issues/3400)） |

---

## 6. 對「單人單機 Windows、markdown atom、hook 注入、有向量服務」系統的評估

### 優點
| # | 點 | 依據 |
|---|---|---|
| 1 | markdown 真源 + 可重建索引，透明可稽核 | memsearch、Claude 官方 auto memory 同路線；Willison 批 ChatGPT 缺的正是此透明度 |
| 2 | hook 主動注入，直接對治「有存無用」 | SuperBrain：8,785 條觀察 0 條自動浮現 |
| 3 | trigger / BM25 / vector + RRF 屬已實證主流 | Zep、Mem0 2026、memsearch 同款；LongMemEval 證明索引鍵擴充有效 |
| 4 | 顯式策展寫入 + confidence 分級 | 避開有損蒸餾（2601.00821）與入場噪音（A-MAC） |
| 5 | 本地無雲 | 無 mem0 MCP 類 OAuth / 連線故障（#4876、#3400） |

### 缺點
| # | 點 | 依據 |
|---|---|---|
| 1 | 逐輪動態注入破壞 prompt cache | Mastra 固定前綴達 SOTA 且成本 4–10× ↓ |
| 2 | atom 為萃取物非原文，受 verbatim 差距約束 | 2601.00821：LoCoMo 43.9 vs 28.0 |
| 3 | activation 衰減實證「減量不提準」；對數跨零分數易誤讀 | 2605.08538 CI 重疊；本地已有誤判紀錄（activation 負值≠負相關） |
| 4 | 若衝突／新鮮度交 LLM 判，實證極弱 | 2606.01435：18% / 7% vs 決定性 82% |
| 5 | 業界僅廠商自報，自家回歸集是唯一可信依據 | Mem0 自列「benchmark 不轉移到應用」為未解 |

### 可補強
| # | 點 | 依據 |
|---|---|---|
| 1 | 索引鍵加事實擴充、查詢加時間感知擴充 | LongMemEval +9.4% / +11.3% |
| 2 | 本地小型 cross-encoder rerank | d2a8k3u 用 TinyBERT；2607.05443 5/6 指標最佳 |
| 3 | 注入前近重複去冗、同主題 atom 群組化取代扁平 top-k | xMemory；Chroma distractor |
| 4 | 寫入入場閘：內容型別先驗 + 新穎度；≥95% cosine 自動合併 | A-MAC；d2a8k3u |
| 5 | 背景 Reflector / sleep-time 週期整併 | Letta、Mastra、LangMem 三家共識 |

### 該修正
| # | 點 | 依據 |
|---|---|---|
| 1 | 「哪個較新」一律決定性（timestamp / serial max），不靠 LLM | 2606.01435 |
| 2 | 注入預算硬上限：SessionStart ~1,200 tokens、每輪 ≤6 條、索引 ≤200 行；截到只剩標題等於零效用 | claude-mem v3 教訓；Claude docs 200 行 / 25KB；Chroma distractor |
| 3 | 關鍵 atom 放注入塊頭尾；相似但無關者寧不注入 | lost in the middle；Chroma「單一 distractor 即降分」 |
| 4 | 萃取 atom 必附 provenance 指標，能回讀原文 | 2601.00821「補充非取代」；memsearch L3 |
| 5 | 每個 fail-open 降級必留訊號 | claude-mem「觀察靜默遺失」為反例 |

---

## 7. 來源清單

**論文**
- Mem0：https://arxiv.org/html/2504.19413v1
- Zep：https://arxiv.org/abs/2501.13956
- A-MEM：https://arxiv.org/html/2502.12110
- LongMemEval：https://arxiv.org/html/2410.10813
- Verbatim Chunks Beat Extracted Artifacts：https://arxiv.org/abs/2601.00821
- Don't Ask the LLM to Track Freshness：https://arxiv.org/html/2606.01435v1
- A-MAC Adaptive Memory Admission Control：https://arxiv.org/abs/2603.04549
- MemConflict：https://arxiv.org/abs/2605.20926
- Control-Plane Placement Shapes Forgetting：https://arxiv.org/abs/2606.15903
- Human-Inspired Memory Architecture：https://arxiv.org/html/2605.08538v1
- ACT-R-Inspired Memory Architecture（HAI 2025）：https://dl.acm.org/doi/10.1145/3765766.3765803
- SYNAPSE：https://arxiv.org/abs/2601.02744
- xMemory：https://arxiv.org/abs/2602.02007
- MemoryBank：https://arxiv.org/abs/2305.10250
- FOREVER：https://arxiv.org/html/2601.03938v2
- Memory in the Age of AI Agents（survey）：https://arxiv.org/abs/2512.13564
- Security of Long-Term Memory survey：https://arxiv.org/html/2604.16548v1
- Scientific Code Search（hybrid/rerank）：https://arxiv.org/pdf/2607.05443

**廠商／官方**
- Mem0 State of Agent Memory 2026：https://mem0.ai/blog/state-of-ai-agent-memory-2026
- Mem0 × Claude Code：https://mem0.ai/blog/claude-code-memory
- Mem0 MCP knowledge graph：https://mem0.ai/blog/mcp-knowledge-graph-memory-enterprise-ai
- Letta agent memory：https://www.letta.com/blog/agent-memory/
- LangMem conceptual guide：https://github.com/langchain-ai/langmem/blob/main/docs/docs/concepts/conceptual_guide.md
- Mastra Observational Memory：https://mastra.ai/research/observational-memory
- OpenAI Dreaming：https://openai.com/index/chatgpt-memory-dreaming/
- Anthropic Effective Context Engineering：https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Claude Code memory docs：https://code.claude.com/docs/en/memory
- Chroma Context Rot：https://www.trychroma.com/research/context-rot

**社群**
- Simon Willison on ChatGPT memory：https://simonwillison.net/2025/May/21/chatgpt-new-memory/
- SuperBrain「Storage Is Solved, Injection Isn't」：https://alexandrekhoury.com/writing/superbrain-session-memory-claude-code
- claude-mem：https://github.com/thedotmack/claude-mem ／ hooks：https://docs.claude-mem.ai/hooks-architecture ／ #618：https://github.com/thedotmack/claude-mem/issues/618 ／ review：https://andrew.ooo/posts/claude-mem-persistent-memory-claude-code/
- alexanderop/claude-code-memory：https://github.com/alexanderop/claude-code-memory
- d2a8k3u/claude-code-memory：https://github.com/d2a8k3u/claude-code-memory
- memsearch：https://github.com/zilliztech/memsearch
- MCP server-memory：https://github.com/modelcontextprotocol/servers/tree/main/src/memory
- mem0 issues：https://github.com/mem0ai/mem0/issues/4876 ／ https://github.com/mem0ai/mem0/issues/3400
- Hybrid search 2026 整理：https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026

---

## 8. 未能取得的資料

| 項目 | 狀況 |
|---|---|
| OpenAI「Dreaming」原文 | HTTP 403；僅依搜尋摘要與 Willison 文描述，機制細節未查證 |
| ACT-R-Inspired（HAI 2025）全文 | ACM 403；僅摘要層級（d≈0.5、噪音項），無評測數字 |
| OpenAI Memory FAQ | 403；saved memories 數量上限等未查證 |
| claude-mem #618 根因與修法 | 只取得標題與狀態（confirmed bug, closed），修法內容未查證 |
| A-MEM「六倍多跳提升」 | 僅見於第三方摘要，論文表格未直接核到，未查證 |
| MemConflict 受測六系統名單與數字 | 摘要頁未列，未查證 |
| SYNAPSE、xMemory 具體數字 | 摘要頁未列，未查證 |
