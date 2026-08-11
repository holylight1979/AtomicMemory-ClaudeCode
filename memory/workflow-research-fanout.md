# workflow-research-fanout

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 幫我搜索, 幫我查, 搜索, 搜尋, 查詢, 我想知道, 想了解, 研究一下, 調查一下, 關鍵字擴充, 知識檢索, research fanout, 多 agent 搜尋, 最佳實踐
- Created-at: 2026-08-11
- Related: workflow-parallel-agents, workflow-rules, decisions

## 知識

- ### 為什麼單獨分模組（實測依據）
- [臨] 檢索意圖不在 `wg_parallel` 的任一計分維度（連接詞/批量詞/跨目標動詞/多檔）。實測「幫我搜索 X 的差別」等 score 皆 **0** — 這才是它對檢索型全啶的原因
- [臨] 曾誤寫主因為 `_is_pure_question` 濾掉純問句，實測推翻：那只對「什麼是 X」開頭的無動詞句生效，而那類 research 也不接管
- [臨] 並行價值定義不同：parallel＝「多個目標」，research＝「同一問題的多個檢索角度」（單目標也值得 fan-out）。放寬 parallel 門檻會讓所有單目標 prompt 誤觸發
- [臨] 中文密度高：`min_prompt_chars` 設 5（「幫我查最佳實踐」僅 7 字元即完整請求；沿用 parallel 的 15 會擋掉合法短請求）
- 
- ### 兩階段 SOP（knowledge 模式）
- [臨] Stage A 關鍵字擴充：1-2 agent，產出同義詞 + 中↔英對應 + 上下位概念 + 常見誤稱；回報限純關鍵字清單
- [臨] Stage B 併搜：帶全部關鍵字，同 message dispatch ≥2 agent — 一路掃記憶庫/_AIDocs（既有結論優先），一路 WebSearch 補外部
- [臨] A→B 是**真序列依賴**（B 要 A 的關鍵字）無法 pipeline；故 A 必須輕，並行主力放 B。Stage A 只開 1-2 個：低分歧一次性工作，多開只增 barrier 等待
- [臨] 中↔英術語橋是 Stage A 真正價值點 — 本地 atom 庫中文、外部知識英文，缺這層兩邊都搜不到
- 
- ### codebase 模式
- [臨] 訊號：「在哪個檔」「誰呼叫」或明示檔名 → 單階段 dispatch ≥2 個 `Explore`，各給不同命名慣例切面；不需關鍵字擴充與 WebSearch（本地 symbol 精確，擴充只引噪音）
- 
- ### 不該 fan-out
- [臨] 記憶庫/`_AIDocs` 已有結論 → 直接引用禁重掃；使用者在思考出聲而非要檢索 → 交付物是評估；答案已在當前 context → fan-out 只是繞圈
- 
- ### 回歸防線
- [臨] rules/core.md 原則 → 本 atom 手冊 → `wg_research.py` 推播（同 parallel 三層慣例）；開關 `research_fanout.enabled`
- [臨] `hooks/verify/verify_research_fanout.py` 21 綠釘住：兩模式分流、6 反例不誤觸發、cooldown、kill switch、以及「parallel 對檢索型恆 0 分」這個分模組前提

## 行動

- 看到 `[Research:Fanout] knowledge` → 先跑 Stage A（1-2 agent 回純清單），再帶關鍵字 dispatch Stage B 併搜
- 看到 `[Research:Fanout] codebase` → 直接 dispatch ≥2 個 Explore，跳過擴充與 WebSearch
- Stage B 前先自問：記憶庫既有結論是否已足夠？
- 判定不適合 fan-out 時在回應裡明說原因
- 改偵測邏輯前先跑 `pytest hooks/verify/verify_research_fanout.py`
