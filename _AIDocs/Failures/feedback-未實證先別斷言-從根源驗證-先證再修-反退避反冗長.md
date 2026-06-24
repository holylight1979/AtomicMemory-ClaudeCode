# feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 未證實, 斷言, 必爆, 先證再修, proof-first, show don't tell, 從根源驗證, 對帳, 交接單, 講人話, DB 鍵, 計畫 checklist
- Created-at: 2026-06-24
- Related: cognitive-patterns, feedback-workflow-discipline, handoff-綜觀品質與抗失真寫法, feedback-rigor-standards, feedback-completion-gates, feedback-complexity-origin-trace

## 知識

- [臨] **未實證不得斷言（最核心）**：p_group 案我拿程式碼註解「正式服必爆」當事實、把預防性 `Log.Warn` 當『已發生的錯誤』、沒查 charId 真實範圍就斷言。最後從根源驗證（追到 AccountServer 發號 + 9 位混淆），證實 charId 恆 < 10^9、`(int)charId` **永不截斷**——整個 blocker 是誤判、修法根本不需要。教訓：斷言『嚴重度/會不會發生』前**先實證**（跑/查/追根源）；分清『機制存在』≠『實際會發生』。
- [臨] **從根源驗證**：user 要的是『驗證生成帳號的來源、從根源對齊』。別停在『外部、查不到』就放棄——順著帳號→charId 發號鏈追到底，才得到決定性答案。
- [臨] **問題未證實前，計畫第一步＝先證再修（proof-first）；show don't tell**：別『很嘴』繞著未證實問題打轉。用實跑流程自我認證、把後果示範出來（如 scratchpad 跑 server 同一行 `unchecked((int)charId)`），再下結論。
- [臨] **開工先對帳權威計畫；交接單『建議』≠『授權』**：被重建版 `next-phase.md` §6『下一關 p_group/必爆』帶跑偏，它沒對帳權威總計畫（該計畫早把 p_group park 為極高風險、排在 S2.2/S2.3 之後）。先讀權威計畫確認在做哪份、是否衝突再開工。
- [臨] **反退避、反冗長**：把優劣明顯的技術選擇包成 menu 丟回 user 裁決＝退避（該自己決就決，只升級**真正需 user 權限**者如組織授權）；把簡單事拉成超長計畫＝SGI 接手者最痛恨的過度工程；耗時過長、巨量廢話 user 視為嚴重。已跑的調查要 salvage。
- [臨] **先講人話再談技術 + 術語先定義**：先白話講『誰是什麼、扮演什麼角色』（p_group=角色分區鍵，不是 index/效能），再進細節；別丟未定義黑話（如『純 app』）。
- [臨] **DB 鍵鐵則 + schema 變更影響面**：鍵必須忠實表示定義域、絕不可靜默截斷/撞鍵（uint64→BIGINT UNSIGNED 沒得選，別拿工程便利當選項）；改欄位型別前先評估存量資料遷移 + 下游（client/協定）衝擊。
- [臨] **計畫文件 hygiene**：① 每份計畫保留**可勾選執行 checklist**（好習慣，不可為精簡砍掉）；② 另建**持久主 checklist** 涵蓋整個計畫 + 未來擴展，後續每 session 必查必勾，作跨 session 治理錨點。
- [臨] **別把 user 的 reasoned pushback 標成『直覺/猜』**：user 明言其質疑來自『大量經驗 + 知識 + 與人共事的認知 + 仔細審核我的回應』，非直覺。反覆說『你的直覺對』是誤讀且不尊重。對待 user 質疑：當成高信號的 informed review，先自查我哪裡可能錯、對實質回應，別用『instinct/gut』輕描淡寫帶過。

## 行動

- 斷言嚴重度/會不會發生前先實證（跑/查/追根源）；機制存在≠會發生
- 外部成因別停在『查不到』，順鏈追到根源
- 問題未證實→計畫先證再修（proof-first）+ show don't tell
- 開工先對帳權威計畫；交接單建議≠授權
- 明顯技術選擇自己決（反退避）；簡單事簡單做（反冗長）；salvage 已跑調查
- 先白話講角色再談技術；術語先定義
- DB 鍵不可截斷；改 schema 先評估存量+下游
- 計畫留可勾 checklist + 建持久主 checklist 供跨 session 必勾
