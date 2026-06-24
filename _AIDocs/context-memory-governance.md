# 上下文與記憶治理（Context & Memory Governance）— 設計憲法

> 用途：原子記憶系統「注入 / 萃取 自檢」設計的**對齊標的（design constitution）**。
> 起因：大型專案多 session 接續下，AI 焦點模糊、回應偏門、範圍縮小卻更耗時，疑與「讀了專案原生內容後被汙染→扭曲避重」有關。
> 結論定性：**「省 token」是成本指標；「避免汙染」是品質指標。真正要養的是「精準命中的直覺」＝ relevance gating + selective forgetting + 最小高訊號集。問題不在量，在治理。**
> 建立：2026-06-24（研究：CC Opus ×2 web agent + Codex 第二意見，交叉驗證）

---

## 0. 一句話定位

你感受到的不是「token 太多」，而是 **「狀態化上下文 ＋ 長期記憶的治理失敗」**——錯誤、過期、干擾、偏見、未遺忘的資訊被持續帶回推理迴路。學界/業界已把這整組現象正式命名並體系化（2023→2026），分四層 + 一個人類科學根。

---

## 1. 術語地圖（四層 + 根）

| 層 | 名稱 | 是什麼 | 何時引用 |
|---|---|---|---|
| L1 病徵分類法 | **How Long Contexts Fail（Drew Breunig）** | 4 失效模式：poisoning / distraction / confusion / clash。與本系統症狀近乎一對一 | 要「精準命名正在發生什麼」 |
| L2 可量測現象 | **Context Rot（Chroma 2025）** | 「context 越長→輸出越不可靠」，遠在塞爆視窗前就退化；distractor 隨長度放大 | 要一個業界 buzzword |
| L3 工程學門 | **Context Engineering（Karpathy / Anthropic / LangChain 2025）** | 母學門：「找出能最大化期望結果的、最小的一組高訊號 token」 | 設計「塞什麼進視窗」 |
| L4 治理學門 | **Agent Memory Management / Memory Governance** | 跨 session 記憶如何形成、檢索、更新、**遺忘**、汙染、漂移、治理 | 設計「長期記憶庫」←本系統正是這個 |
| 根 人類科學 | **Cognitive Load Theory（Sweller 1988）** | 工作記憶有硬上限；extraneous load（無關材料）直接拖垮處理 | 要「為何會這樣」的母理論 |

> 旁支根理論：Information Overload（Toffler 1970，白話本名）/ Bounded Rationality·poverty of attention（Simon 1971，注意力是被消耗的稀缺資源）/ Signal-to-Noise（Shannon 1948，統計框架）/ ML 類比 Catastrophic Forgetting（序列學新知覆蓋舊知）+ Concept Drift（舊假設隨時間失效）。

---

## 2. 病徵 → 術語 對應表（本系統實際症狀）

| 使用者原話 | 正式術語 | 定義（意譯） |
|---|---|---|
| 讀了專案原生內容後被**汙染**→扭曲、避重 | **Context Poisoning** | 一個幻覺/錯誤進了 context，被反覆引用，變成後續推理的假地基 |
| 焦點越來越糊、範圍越做越小又**過度耗時** | **Context Distraction** | context 長到模型過度聚焦於 context 本身，忽略訓練學到的能力 |
| 回應越走越**偏門** | **Context Confusion** | context 裡的多餘內容被拿去生成，產出低品質回應 |
| 多 session 累積的**矛盾**資訊 | **Context Clash** | 新累積的資訊/工具和既有資訊互相打架 |
| 中段塞進去的知識「明明有給卻沒被用對」 | **Lost in the Middle**（Liu 2023） | U 型曲線：首尾資訊高取用、中段被嚴重忽略 |
| 多 session 早期理解被侵蝕 | **Multi-turn goal drift / 記憶覆蓋** | 早期假設「鎖死」後漂離真意；模型走錯一步後不易自我恢復 |

---

## 3. 反框：把「直覺」工程化

- **避免汙染 > 省 token**：浪費只是成本指標之一；汙染是品質殺手。研究界共識：問題不在量，在治理。
- **最小高訊號集（Anthropic）**：注入的目標不是「給更多」，是「給剛好能命中下一步的最小高訊號集」。
- **Selective Forgetting（選擇性遺忘）**：長時程 agent 的核心能力不是記更多，而是**知道何時丟棄 / 降權 / 隔離**舊資訊。
- **Memory-induced drift**：記憶裡的偏好/偏見會在**不相關任務**中偷偷影響決策與工具呼叫——即「回應越走越偏門」的記憶側根因。

---

## 4. 對到本系統管線的落點（Task 2 hook 設計的標的）

> 既有 anti-pollution DNA（順著長、非打掉重練）：`decisions.md` 已把 ReadHits 降為純曝光計數、不參與晉升（防純注入頻率劣化品質，Xiong 2505.16067）。本表是它的延伸。

| 失效模式 | 系統風險點（檔） | 候選自檢 hook 方向 |
|---|---|---|
| **Poisoning** | 萃取把幻覺/誤判寫成 atom，之後反覆注入（`wg_extraction.py` / `memory-write-gate.py`） | 萃取 write-gate 加「來源實證 / 信心」閘；低信心 atom 注入前標記隔離 |
| **Distraction** | SessionStart/UPS 注入過多 atom，context 變肥（`ups_inject.py`） | 注入預算動態收斂；ReadHits 高但 use 低者降權（已有 Wilson，可加「分心懲罰」項） |
| **Confusion** | 語意檢索召回「相關但無關」distractor（`ups_search.py` BM25/Vector） | 注入前 relevance gate（lexical+vector 雙閘已有雛形）+「最小集」裁切 |
| **Clash** | 多 session atom 互相矛盾（已有 `/conflict`、`memory-conflict-detector.py`） | 注入時即時 clash 偵測 → 自我提示「這兩條衝突，先確認」 |
| **(跨層) Forgetting 缺位** | 只有 λ 慢衰減，缺主動隔離（SessionEnd 鞏固） | 過期 / 低效用 atom 主動隔離；session 收尾自檢「這輪注入有沒有幫上忙」閉環 |

---

## 5. 來源（已 fetch 驗證者標 ✓）

- ✓ Breunig, *How Long Contexts Fail* (2025-06-22): https://www.dbreunig.com/2025/06/22/how-contexts-fail-and-how-to-fix-them.html
- ✓ Breunig, *How to Fix Your Context* (2025-06-26): https://www.dbreunig.com/2025/06/26/how-to-fix-your-context.html
- ✓ Chroma, *Context Rot* (2025-07-14): https://www.trychroma.com/research/context-rot
- ✓ Liu et al., *Lost in the Middle* (TACL 2023): https://arxiv.org/abs/2307.03172
- Anthropic, *Effective context engineering for AI agents* (2025-09): https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Karpathy, "context engineering" (2025-06-25): https://x.com/karpathy/status/1937902205765607626
- LangChain, *Context Engineering for Agents*: https://www.langchain.com/blog/context-engineering-for-agents
- Laban/Hayashi et al., *LLMs Get Lost in Multi-Turn Conversation* (2025-05): https://arxiv.org/abs/2505.06120
- Cognitive Load Theory（Sweller 1988, *Cognitive Science* 12(2):257-285）: https://en.wikipedia.org/wiki/Cognitive_load
- Information Overload（Toffler 1970）: https://en.wikipedia.org/wiki/Information_overload
- Simon, poverty of attention (1971): https://hapgood.us/2018/10/08/designing-organizations-for-an-information-rich-world/

> Memory Governance / Selective Forgetting 概念為真且主流（Codex 第二意見 cross-check 一致）；其提供的具體 arXiv 編號未獨立驗證、依使用者決定丟棄（概念已內化，不影響本文結論）。

---

## 6. 關聯

- atom：[[記憶汙染與上下文腐化-注入萃取自檢]]（跨專案行為守則，本文的可注入精簡版）
- atom：[[cognitive-patterns]]（認知偏差，姊妹篇，管代理指標誤用/自我合理化）
- atom：[[decisions]]（ReadHits 降權的 anti-pollution DNA）/ [[decisions-architecture]]（管線架構）
- doc：[Architecture.md](Architecture.md) / [DocIndex-System.md](DocIndex-System.md)（hook 管線全貌）
