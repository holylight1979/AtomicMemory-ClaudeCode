# codex-handoff自檢誤報文件截斷-真因是輸入靜默截斷非模型幻覺

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: codex 誤報, handoff 自檢, 文件截斷, 誤報截斷, 審查者輸入, 6000字, _read_handoff_content, 頭尾採樣, codex companion 截斷
- Created-at: 2026-08-05
- Related: 原子記憶審查總結-好機制被小故障卡死非過重-拔前先實證, feedback-tooling-reliability, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, 專案工作驗收裁判的分級啟動與殺閘設計

## 知識

- [臨] 實案（2026-08-05）：codex handoff 自檢連 4 輪 severity=high 報「文件在句中截斷/斷鏈」，實際檔案完整。真因＝`hooks/codex_companion.py::_read_handoff_content` 靜默切前 6000 字（檔案 12778 字），無截斷標記——codex 拿到的輸入真的斷在句中，**是忠實審查了被污染的輸入，不是幻覺**。第 6000 字位置與 codex 報的截斷點逐字吻合＝定罪證據。
- [臨] 修法（已落）：頭尾採樣（head 4500 + tail 1500）+ 明確標記「中段省略：全文 N 字…勿把採樣截斷誤判為文件截斷」。尾段保留讓 codex 看得到文末授權/收尾段——先前反覆誤報「缺 §9 授權條件」同為此因。verify=tools/codex-companion/verify/verify_handoff_content_sampling.py。
- [臨] 通則：AI 裁判連續誤報同型問題時，先查「我們餵給它什麼」——**審查者拿到的輸入 ≠ 磁碟上的檔案**，中間每一道採樣/截斷/遮蔽都可能製造假缺陷。我曾未查實碼就誤診為「codex 讀到編輯中間態」＝未實證先斷言的反例。
- [臨] 同型第二實例（plan_review，2026-08-06 根治）：`plan_content` key 全庫從無寫入端，assessor 恆 fallback 成 tool trace 摘要；Write content 在 hook 入口整包丟棄、ExitPlanMode plan 被 [:200] 靜默截 → 歷史 105 次 plan_review 100% 只收到動作紀錄，codex 回「未提供計畫正文」全是忠實行為。與 handoff [:6000] 案共同根源：餵給裁判的輸入 ≠ 磁碟上的 artifact。
- [臨] 根治後的結構性防線（單點補丁之外）：輸入組成規則收斂到單一模組（tools/codex-companion/artifact_io.py 統一原則 + assessor.build_prompt 純函式），caller（hook）只傳觸發事實不各自組裝；「artifact 必附實體內容、動作紀錄不得替代本體、解析不到就 skip+metric 不空審」三原則程式化；輸入完整性 verify（verify_prompt_input_integrity.py）直接對送出的 prompt 斷言正文存在——裁判輸入管線自此有守門測試，不靠人肉發現誤報才回頭查。

## 行動

- AI 裁判/審查 agent 連續誤報同型缺陷 → 先 dump 實際送出的 prompt/輸入比對磁碟原檔，再談模型能力
- 任何餵給裁判的內容截斷必附明確標記（全文字數+採樣範圍），禁靜默切斷
- 長文件送審必含結尾段（授權/收尾常在文末）——頭尾採樣優於純頭部截斷
