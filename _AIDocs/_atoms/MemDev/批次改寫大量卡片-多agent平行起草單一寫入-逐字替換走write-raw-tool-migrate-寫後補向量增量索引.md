# 批次改寫大量卡片-多agent平行起草單一寫入-逐字替換走write_raw-tool-migrate-寫後補向量增量索引

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 批次改卡片, 大量 atom, 多 agent 寫 atom, atom_write 並行, 索引互蓋, write_raw, tool:migrate, atom_write replace 重建, 向量增量索引, 批次遷移
- Created-at: 2026-10-08
- Source: session:d78db3ba 2026-10-08

## 知識

- [臨] atom_write 與索引寫入沒有檔案鎖：多個 agent 同時寫卡片會互蓋 _atom_index.json。批次改卡片要分兩段：多 agent 平行起草（只產出 before→after 清單），再由單一寫入者依序套用。
- [臨] atom_write mode=replace 會用參數重建整檔：沒傳的 related、actions、status 會消失，非標準格式的卡（知識區標題叫「印象」、有「演化日誌」表格、知識區含 ### 小標）會被重排。只改字不改結構時，用「每筆 before 必須在檔內剛好出現一次」的逐字替換，經 lib.atom_io.write_raw(source="tool:migrate") 寫入（有稽核、不重建）；git diff 只會落在改過的行。
- [臨] write_raw 不更新索引與向量：改到 Trigger 行的卡要再用 atom_edit_meta 同步索引；全部寫完後 POST http://127.0.0.1:3849/index/incremental 補向量。
- [臨] 起草者不自審：另派獨立審查員對照原檔與專案原始碼核「事實走樣／刪過頭／指涉混亂／殘留」四類。實測 236 筆改寫被抓到 9 筆走樣或指涉問題，其中 1 筆是起草格式錯（「（整項刪除）」字樣而非空字串），不審就會寫進卡片。

## 行動

- 要批次改十張以上卡片：平行起草、單一寫入、獨立審查三段式，不讓多個 agent 直接呼叫 atom_write
- 只改字不改結構就用逐字替換加 write_raw(tool:migrate)，寫後看 git diff --numstat 確認只動到改過的行
- 寫完補 atom_edit_meta（有改 Trigger 的）與向量增量索引
