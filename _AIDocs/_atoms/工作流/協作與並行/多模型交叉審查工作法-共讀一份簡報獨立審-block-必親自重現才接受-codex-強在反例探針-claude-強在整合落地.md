# 多模型交叉審查工作法-共讀一份簡報獨立審-BLOCK 必親自重現才接受-Codex 強在反例探針 Claude 強在整合落地

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 多開 agent, Codex 審查, 交叉審查, 多模型, 不被帶偏, BLOCK/WARN, 審查簡報, fan-out 審查, gpt-6-astra, 全面檢視, reply_review, 裁決紀錄
- Created-at: 2026-09-21
- Related: workflow-research-fanout, workflow-parallel-agents, 雙claude協作實戰認知-fable監工opus主力的分工手感

## 知識

- [臨] 2026-09-21 全面檢視實戰（5 Claude agent＋7 Codex gpt-6-astra，再兩輪 Codex 複審）：可行的流程＝主持方先寫一份共用簡報（範圍、已知事實、禁區、輸出格式），各 agent 獨立審完各交摘要；主持方把結論分 BLOCK／WARN／建議三級，每個 BLOCK 自己重跑探針或讀碼重現，重現不了就降級不採。十份審查交叉印證同一核心結論（記帳與評估失真而非系統過重）時才動大手術。
- [臨] 強項分工：Codex 擅長挑邊界反例與追問「這個數字怎麼量的」（本輪五個 BLOCK 全部成立：_AIAtoms 基底、歷史查詢否定、否定窗口誤殺、路標未讀穿透、子代理借父證據），弱在對本機環境與工具鏈的掌握；Claude 主持方擅長整合、落地、寫測試、操作工具，弱在對自己方案的自我否證。「不被彼此帶偏」的操作定義＝對方的每個主張都要能指出證據位置，指不出就記為待驗不採。
- [臨] 保留裁決要留痕：主持方不採對方建議時（如 gain 採用規則、cross_session 預設）在計畫檔寫「[AI] 保留裁決＋理由」，讓使用者能看見分歧而不是只看見結論。

## 行動

- 派多模型審查前：先寫一份共用簡報，列範圍、已知事實、禁區、要的輸出格式
- 收審查結果：分級 BLOCK／WARN，BLOCK 逐條親自重現，重現不了降級
- 與對方意見不同：寫保留裁決＋理由進計畫檔，不默默覆蓋
