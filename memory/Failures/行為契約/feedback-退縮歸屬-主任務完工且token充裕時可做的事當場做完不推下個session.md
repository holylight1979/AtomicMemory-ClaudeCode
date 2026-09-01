# feedback-退縮歸屬-主任務完工且token充裕時可做的事當場做完不推下個session

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 下個 session, 下一個 session, 不是本次, 不在本案, 非我造成, 獨立議題, 遺留議題, 另案, 退縮歸屬, DeferralGate, 收尾, 遠留項目, 你可以推進的
- Created-at: 2026-08-27
- Related: 自己flag的維護動作直接做完不要反問, feedback-workflow-discipline, feedback-收尾報告使用者視角四要素-白話綜觀非片段細節, 自己指出的更好做法若成本低就當場做掉-不要列成設計債丟給使用者

## 知識

- [臨] 使用者指正（2026-08-27）：一顆 atom 瘦身明明十分鐘，我卻寫成「要不要下個 session 做」——原因是拿任務單的「純文件、不寫 atom」當範圍邊界，再套「遺留項目＝下階段」的分階段模板。這是退縮歸屬：把**帶受詞、可做的事**（成果類已確定必做項目、新發現的 bug、已知舊 bug、很快的小問題、修掉報備一下會增加信任的事、自己的過失、非自己的過失、非階段計畫內容）推給「下個 session／不是本次／不在本案／獨立議題／非我造成」。
- [臨] 判準（使用者定）：**主任務已完工或即將完工 ∧ context 用量 ≤ 1M 的 75% ∧ 處理後不會飄移主任務認知** → 當場做掉；不能做只有三種理由（不可逆／需使用者拍板業務取捨／會飄移），要一句話明寫；或使用者已明示延後（引原話）。「任務單範圍外」不是理由——可逆且屬自然延伸的維護動作本就該直接做（[[自己flag的維護動作直接做完不要反問]]）。
- [臨] 程式化：Stop 閘 `DeferralGate`（`hooks/handlers/stop.py`，純函式 `wg_evasion.deferral_gate_reason`），詞表 `memory/_meta/forbidden-phrases.json` 類別 `deferral-attribution`，門檻 `workflow/config.json deferral_gate`（max_context_ratio 0.75、min_object_chars 6）。擋回三選一 (a) 做掉 (b) 一句不能做的理由 (c) 使用者原話。使用者命令式延後語（`deferral_user_ok`）為逃生門；使用者「質問為何要新開 session」不算放行。
- [臨] 「分階段執行」≠「每階段換 session」。使用者連問兩次「Phase 2/3 此 session 不適合做嗎？」（2026-09-01 scope 三階段）：context 健康、程式脈絡與定案都在手上時，換 session 反而是飄移來源。接續 prompt 只當備援（context 快滿、或使用者要收工時才用），預設直接續做下一階段。

## 行動

- 收尾前自檢：每一句「下個 session／獨立議題／不在本案」都問一次——現在能做嗎？能就做，不能寫一句理由
- 任務單的範圍邊界不是拒做可逆小事的理由
