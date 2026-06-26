# JARVIS 式企業 AI 開發協作平台 — 發想與前瞻設計

> **立場**：這是一份「說不定某天會真的拿出來設計、做成成品」的發想文件。內容以**可執行的設計參考**書寫，而非空想——每一塊都對照現有商業/開源方案、給可仿效的設計取捨、並標明「若要在現有原子記憶系統上長出來，該從哪裡接」。
>
> **來源**：2026-06-26 一輪對談的 gap 分析（使用者提出 16 條願景需求，問「原子記憶系統還缺什麼才能當核心」）+ 後續多 agent 研究補充（編排框架、企業平台、記憶/路由/RAG/STT/合規、協定生態）。
>
> **性質**：`_AIDocs/Vision/` 發想層，read-on-demand 參考、零 session 注入成本。內容含前瞻推測，已盡量標注「已驗證 vs 推測」。技術現況以各子檔來源 URL 為準（會過時）。

---

## 一句話定調

**原子記憶系統現在是一顆很完整的「海馬迴」，但 JARVIS 不是一顆海馬迴、是一個「大腦」。**

使用者問「記憶系統還缺什麼才能當核心」——這個提問本身需要先校正：在這套 C/S 願景裡，**真正的核心是「編排者（Orchestrator）」，記憶是它最關鍵的器官之一，但不是它本身**。現有系統把「長期記憶 + 行為治理」做到了個人單機的天花板，可是願景裡 16 條需求，記憶直接覆蓋的只有約 3 條。其餘是大腦還沒長出來的部位。

缺口分兩層看：

- **(A) 記憶要怎麼升級才配當這顆大腦的海馬迴** → 服務化、多租戶、真權限、規模化。
- **(B) 大腦其他器官根本還沒有** → 編排、模型路由、工具生態、攝取、感官、運動、免疫。

---

## 願景 16 條 × 現況覆蓋度

> 完整需求原文見本主題的對話起點。編號沿用 gap 分析。

| # | 願景需求 | 現況覆蓋 | 缺口性質 | 深掘 |
|---|---------|---------|---------|------|
| 3 | 分層記憶、跨專案不重工 | 🟢 **70%** scope 四層 + realm 分區 | 缺中心化共享、即時同步 | [01](01-memory-as-shared-cortex.md) |
| 10 | 開發知識最大保留 | 🟢 **70%** atom + episodic + 萃取管線 | 缺多人匯流、規模化 | [01](01-memory-as-shared-cortex.md) |
| 12 | 作業紀錄、月工作日誌 | 🟡 **40%** journal skill（事後聚合） | 缺即時「伴隨焦點」採集 | [07](07-work-journal-and-activity.md) |
| 11 | 自我維護與擴展 | 🟡 **35%** atom-heal/wisdom/docdrift（限記憶層） | 缺服務層自維運 | [09](09-evolution-from-current-system.md) |
| 1 | 客戶端 AI + 內部伺服器、自主分類 | 🔴 **15%** 有 scope 概念，無真伺服器 | 地基缺 | [01](01-memory-as-shared-cortex.md) · [09](09-evolution-from-current-system.md) |
| 6 | 私有平台 + 權限控管 + AI自維護 | 🔴 **10%** 管理職認證是「君子協定」 | 地基缺（最關鍵） | [08](08-security-governance-compliance.md) |
| 2 | 跨各家大模型主動分工 | 🔴 **5%** 只有 Claude+Ollama 固定二分 | 編排層缺 | [03](03-model-routing.md) |
| 4 | 跨企劃/程式/美術/PM/QA 整合 | 🔴 **10%** 有角色 scope，無協作引擎 | 編排層缺 | [02](02-orchestration-core.md) |
| 5 | 工具開發→伺服器認證註冊→共享 | 🔴 **5%** MCP 各自手動配置 | 工具生態缺 | [04](04-tool-registry-and-protocols.md) |
| 8 | 主動彙整 GitLab 可共享知識 | 🔴 **10%** read-project 手動單次 | 攝取管線缺 | [05](05-knowledge-ingestion.md) |
| 16 | 定期跨專案無效率/設計修補報告 | 🔴 **5%** 記憶 per-project 隔離 | 攝取+編排缺 | [05](05-knowledge-ingestion.md) · [02](02-orchestration-core.md) |
| 7 | 翻譯 | 🟡 LLM 能做，無 pipeline/術語庫 | 體驗缺 | [06](06-multimodal-io.md) |
| 9 | 會議麥克風→記錄+即時翻譯 | 🔴 **0%** 無 audio 管線 | 感官缺 | [06](06-multimodal-io.md) |
| 15 | 更好的畫面檢視 | 🔴 **10%** playwright/excel 截圖雛形 | 感官缺 | [06](06-multimodal-io.md) |
| 13 | 請假/填單/會議召開 | 🔴 **0%** 無公司系統 connector | 運動缺 | [08](08-security-governance-compliance.md) |
| 14 | 串手機 APP | 🔴 **0%** 純桌面 | 跨裝置缺 | [09](09-evolution-from-current-system.md) |

---

## 缺口歸納

### A. 記憶本身要補的「硬骨頭」（配當海馬迴）

現況最致命的前提：**它是單機檔案系統 + git/svn 最終一致同步，且權限是榮譽制。** 詳見 [01-memory-as-shared-cortex.md](01-memory-as-shared-cortex.md)。

| 缺口 | 現況 | 要變成 |
|------|------|--------|
| 服務化 / 中心化 | atom 散在各人 `~/.claude`，靠 git commit/pull 手動同步 | 中央 atom store（DB）、並發寫入、server push 即時同步 |
| 真權限（AuthZ） | 管理職＝自我宣告 + 改 `_roles.md` 白名單即可提權；personal 層同機可讀 | SSO/LDAP、RBAC、加密 at-rest、**retrieval 時就過濾無權內容** |
| 規模化檢索 | 全域 BM25 in-memory ~56 atoms | 公司級數萬 atom → 向量 DB 叢集 + 權限感知檢索 |
| 多人衝突合併 | 三時段衝突偵測 + pending review（單人視角） | 多人同改的 CRDT/OT 合併、即時鎖 |
| 不可篡改稽核 | JSONL audit（本機可改） | 簽章 / append-only / 合規級審計 |

> 一句話：**現在的 scope 是「注入過濾」，不是「存取控制」。** 這是它離公司級核心最遠的一條鴻溝。

### B. 核心的其他器官（記憶之外，但要它當核心就得長）

| 器官 | 對應願景 | 缺什麼 | 深掘 |
|------|---------|--------|------|
| **前額葉：編排引擎** | #2 #4 #16 | 多 agent 任務分解→指派→交付→驗收的長時程狀態機。**真正的「核心」，目前完全缺** | [02](02-orchestration-core.md) |
| 模型路由器 | #2 | model registry + 能力/成本/延遲評分 + 動態選模 + fallback | [03](03-model-routing.md) |
| 工具註冊中心 | #5 | MCP 上架/版本/簽章認證/相容性/權限/分發 | [04](04-tool-registry-and-protocols.md) |
| 攝取管線 | #8 #16 | GitLab connector + 排程爬取 + 自動萃取分類 + 中央「能讀全部專案」分析角色 | [05](05-knowledge-ingestion.md) |
| 多模態感官 | #7 #9 #15 | realtime STT + 語者分離 + 即時翻譯 + 落 atom；出圖；螢幕理解 | [06](06-multimodal-io.md) |
| 運動/自動化 | #13 | HR/日曆/表單 connector + 流程自動化 + 生產級排程中樞 | [08](08-security-governance-compliance.md) |
| 跨裝置 | #14 | client-server 協定 + 行動端 thin client | [09](09-evolution-from-current-system.md) |
| 免疫：服務自維運 | #11 #6 | 部署/健康監控/自動擴容/跨客戶端版本升級協調 | [09](09-evolution-from-current-system.md) |

---

## 2026 業界收斂洞察（研究補充）

發想時值得對齊的三個現實：

1. **業界已收斂出「三層棧」**：**A2A**（agent 之間協調，Linux Foundation，150+ 組織）+ **MCP**（agent 對工具，Anthropic）+ **shared context layer**（治理過的業務知識）。我們的原子記憶系統，定位上就是要長成第三層的「治理知識層」。詳見 [04](04-tool-registry-and-protocols.md)。

2. **最接近願景的現有商業驗證 = Glean**：permissions-aware knowledge graph、model-neutral（15+ LLM）、Enterprise Agent Development Lifecycle、依任務選模（Adaptive Reasoning）、治理 SKU（Glean Protect Plus），$300M ARR。它驗證了「權限感知知識層 + 多模型 + 企業治理」這條路商業上走得通。我們和它的差異化護城河在**記憶品質治理**（信任分級/效用閉環/遺忘/反退避），見 [01](01-memory-as-shared-cortex.md) 與 [09](09-evolution-from-current-system.md)。

3. **「哪家在哪方面強就派誰」已有現成範式 = Microsoft Agent Framework 1.0 的 Magentic-One**：一個 manager 依任務進度與 agent 能力動態挑下一個該行動的 agent。這正是願景 #2 的編排骨架。見 [02](02-orchestration-core.md)。

---

## 建議演進路徑（P0 → P2）

不要平行鋪開——有嚴格的地基依賴關係。完整落地切入點見 [09-evolution-from-current-system.md](09-evolution-from-current-system.md)。

**P0 — 地基（沒有它，後面全是孤島）**
1. **記憶服務化**：把 atom store 從「單機檔案」抽成「有 API 的中央服務」（先 server，client 仍可離線快取）。
2. **真身份與權限**：AuthN/AuthZ + 權限感知檢索。

> 理由（第一性原理）：你列的每一條——工具共享、GitLab 彙整、會議記錄、跨專案報告——要「被所有人共享」的前提，都是先有一個**有權限的、中心化的、可被多客戶端即時讀寫的知識服務**。沒有這個地基，其他子系統各自長出來也只是 N 個互不相通的單機外掛。**記憶服務化＝把它從「個人海馬迴」變成「公司共享皮層」，這一步做完，它才真的有資格叫「核心」。**

**P1 — 核心編排能力**：編排引擎（[02](02-orchestration-core.md)）→ 模型路由器（[03](03-model-routing.md)）→ 工具註冊中心（[04](04-tool-registry-and-protocols.md)）。

**P2 — 感官與觸手**：攝取管線（[05](05-knowledge-ingestion.md)）→ 多模態（[06](06-multimodal-io.md)）→ 自動化 connector（[08](08-security-governance-compliance.md)）→ 跨裝置（[09](09-evolution-from-current-system.md)）。

---

## 子檔導讀

| 檔 | 主題 | 對應願景 | 一句話 |
|----|------|---------|--------|
| [01](01-memory-as-shared-cortex.md) | 記憶作為共享皮層 | #1 #3 #10 | 從單機海馬迴升級為多租戶、權限感知的中央知識層（Mem0/Zep/Cognee/RLS/Qdrant） |
| [02](02-orchestration-core.md) | 編排核心 + 跨角色協作 | #2 #4 #16 | 大腦的前額葉：多 agent 任務分解→指派→驗收（LangGraph/CrewAI/MS Agent Framework/ADK/Devin） |
| [03](03-model-routing.md) | 多模型主動分工 | #2 | 哪家在哪方面強就派誰（Portkey/OpenRouter/RouteLLM + 成本品質權衡） |
| [04](04-tool-registry-and-protocols.md) | 工具認證註冊與互通協定 | #5 | 工具開發完→簽章註冊→他人共享（MCP Registry/A2A/AGNTCY 三層棧） |
| [05](05-knowledge-ingestion.md) | 知識攝取 + 跨專案分析 | #8 #16 | 主動彙整 GitLab、跨專案找無效率（Glean/Sourcegraph/SCIP） |
| [06](06-multimodal-io.md) | 多模態感官 | #7 #9 #15 | 會議 STT/即時翻譯/出圖/螢幕理解（WhisperX/Fireflies/diarization） |
| [07](07-work-journal-and-activity.md) | 作業紀錄與月誌 | #12 | LLM 伴隨焦點記重點，但避開 Recall 的隱私紅線（事件日誌設計） |
| [08](08-security-governance-compliance.md) | 安全/權限/治理/合規 | #6 #13 | RBAC/SSO/不可竄改稽核 + 業務流程自動化（EU AI Act/AI Gateway） |
| [09](09-evolution-from-current-system.md) | 從現有系統如何長出來 | #11 #14 | 最關鍵的落地切入點：用現有零件逐步演進、不重造輪子 |

---

## 收束（對發想者的提醒）

- **記憶系統當核心，缺的不是「記憶功能」，而是「從單機升級為服務」的那一整圈**：服務化 + 真權限 + 規模化。這三項是它配當核心的入場券。
- **真正的「核心」其實是編排引擎**，是整張圖裡最大的空洞——現有的 Auto-Handoff / sub-agent / Fix Escalation 都是它的零件，但還沒組成一個會分工、會驗收的「前額葉」。
- **好消息**：最難、最少人做對的部分（長期記憶品質治理：信任分級、效用閉環、衝突偵測、遺忘、反退避）已經啃下來了。那是 JARVIS 的「記憶品質」護城河，多數人連這層都沒有。剩下的多是工程量大但路徑明確的「接管線」。

> 各子檔的「現有系統落地切入點」一節，是這份發想最有實作價值的部分——它把每個遠大目標釘回「現在的程式碼裡，從哪個檔/哪個機制開始改」。
