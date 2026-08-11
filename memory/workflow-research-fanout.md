# workflow-research-fanout

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 幫我搜索, 幫我查, 搜索, 搜尋, 查詢, 我想知道, 想了解, 研究一下, 調查一下, 關鍵字擴充, 知識檢索, research fanout, 多 agent 搜尋, 最佳實踐
- Created-at: 2026-08-11
- Related: workflow-parallel-agents, workflow-rules, decisions

## 知識

- ### 為什麼檢索型請求要單獨判準
- [臨] `wg_parallel` 以「切面數」計分（多目標/多檔/批量詞），且 `_is_pure_question` 主動濾掉「什麼是 X」「為什麼 Y」開頭 prompt — 檢索型請求正是那種句型，靠 parallel 機制永遠不觸發
- [臨] 檢索型的並行價值不在「多個目標」，在「同一問題的多個檢索角度」：單一問題也值得 fan-out
- [臨] `hooks/wg_research.py` 補這個缺口：偵測檢索動詞 → 判 knowledge / codebase 兩模式 → 注入 `[Research:Fanout]`；命中時抑制 `[Parallel:Suggest]` 避免重複佔位
- 
- ### 兩階段 SOP（knowledge 模式）
- [臨] Stage A 關鍵字擴充：1-2 agent，任務＝術語同義詞 + 中文↔英文對應 + 上下位概念 + 常見誤稱，一路查網路確認業界實際用語；回報格式限「純關鍵字清單」
- [臨] Stage B 併搜：帶 Stage A 全部關鍵字，同 message dispatch ≥2 agent — 一路掃原子記憶庫/_AIDocs（既有結論優先，命中就別重查），一路 WebSearch/WebFetch 補外部最新
- [臨] A→B 是**真序列依賴**（B 的 prompt 要 A 產出的關鍵字），無法 pipeline；故 A 必須輕（agent 少、回報短），並行主力放 Stage B
- [臨] Stage A 只開 1-2 個而非「幾個」：關鍵字擴充是低分歧一次性工作，多開只增 barrier 等待，不增品質
- [臨] 中文↔英文術語橋是 Stage A 的真正價值點 — 本地 atom 庫是中文、外部知識以英文為主，缺這層對應會兩邊都搜不到
- 
- ### codebase 模式（本地程式碼定位）
- [臨] 訊號：「在哪個檔」「誰呼叫」「這個函式」或明示檔名/路徑 → 單階段，dispatch ≥2 個 `Explore` agent，各給不同命名慣例/目錄切面
- [臨] 不需 Stage A 關鍵字擴充、不需 WebSearch — 本地 symbol 名是精確的，擴充只會引入噪音
- 
- ### 不該 fan-out 的情況
- [臨] 記憶庫/`_AIDocs` 已有結論的問題：直接引用，禁重掃（核心規則「已有文件直接引用」）
- [臨] 使用者在描述問題/思考出聲而非要檢索 → 交付物是評估不是搜尋結果
- [臨] 答案在當前 context 已具備：fan-out 只是把已知的東西再繞一圈
- 
- ### 注入層次
- [臨] rules/core.md 原則 → 本 atom 手冊 → `wg_research.py` 即時推播；同 `workflow-parallel-agents` 的三層慣例
- [臨] 開關：`workflow/config.json` → `research_fanout.enabled`；cooldown 2 turns（追問時已在流程內，不重複提醒）

## 行動

- 看到 `[Research:Fanout] knowledge` → 先跑 Stage A 關鍵字擴充（1-2 agent，回純清單），再帶關鍵字 dispatch Stage B 併搜
- 看到 `[Research:Fanout] codebase` → 直接 dispatch ≥2 個 Explore agent，跳過關鍵字擴充與 WebSearch
- Stage B 前先自問：記憶庫既有結論是否已足夠？足夠就引用不重掃
- 判定不適合 fan-out 時，在回應裡明說原因（同 parallel 慣例）
