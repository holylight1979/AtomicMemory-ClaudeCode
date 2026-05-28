# feedback-atom-write-initial-confidence

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: atom_write, 初次寫, 信心度, [固], [臨], [觀], confidence, knowledge 行, 隨手寫 [固]
- Created-at: 2026-05-28

## 知識

- [臨] **atom_write 初次寫入新知識必須用 [臨]、不能直接 [固]**(2026-05-27 user 明訓 + atom_write tool 實作驗證拒接 [固])。原因:[觀]/[固] 反映 cross-session stability、first-write 不能主張。promotion 規則:Confirmations ≥4→[觀] ≥10→[固];ReadHits ≥20/≥50 輔助
- [臨] **適用範圍**:不論 atom 本身的 confidence metadata 為何,新加入的個別 knowledge 行都從 [臨] 開始。atom_write tool 本身在有未驗證規則
- [臨] **例外可首寫 [固]**:未確認 tool 是否唯一例外為「明確硬事實」(檔案路徑、API 簽章、常數)。實作上連同 atom 本身也被護守拒 [固],其他例外需進一步驗證
- [臨] **關聯規則**:[[workflow-rules]] (記住→[固]、反覆模式→[觀]、做取捨→[臨])

## 行動

- （依知識內容判斷）
