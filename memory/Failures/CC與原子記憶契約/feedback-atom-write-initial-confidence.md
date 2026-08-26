# feedback-atom-write-initial-confidence

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_write, 初次寫, 信心度, [固], [臨], [觀], confidence, knowledge 行, 隨手寫 [固]
- Created-at: 2026-05-28

- Related: realm-範疇分區機制-v5

## 知識

- [臨] **atom_write 初次寫入新知識必須用 [臨]、不能直接 [固]**(2026-05-27 user 明訓 + atom_write tool 實作驗證拒接 [固])。原因:[觀]/[固] 反映 cross-session stability、first-write 不能主張。promotion 規則:Confirmations ≥4→[觀] ≥10→[固];ReadHits ≥20/≥50 輔助
- [臨] **適用範圍**:不論 atom 本身的 confidence metadata 為何,新加入的個別 knowledge 行都從 [臨] 開始。atom_write tool 本身在有未驗證規則
- [臨] **例外可首寫 [固]**:未確認 tool 是否唯一例外為「明確硬事實」(檔案路徑、API 簽章、常數)。實作上連同 atom 本身也被護守拒 [固],其他例外需進一步驗證
- [臨] **關聯規則**:[[workflow-rules]] (記住→[固]、反覆模式→[觀]、做取捨→[臨])
- [固] create 除了必須 `[臨]` 之外，`domain` 也必填（`<Lv1>[/<Lv2>]`，Lv1 閉合清單 `memory/_meta/taxonomy.json`；缺或未知 → 拒並列全部 Lv1；`allow_new_category=true` 才准開新 Lv1，應極少用）。兩條都是「首寫不能斷言的事就別斷言」：信心層級交跨 session 晉升、範疇交閉合清單。拿不準就 `dry_run=true` 先看落點。

## 行動

- （依知識內容判斷）
