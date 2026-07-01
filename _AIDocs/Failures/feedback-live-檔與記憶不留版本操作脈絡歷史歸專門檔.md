# feedback-live 檔與記憶不留版本操作脈絡（歷史歸專門檔）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 版本殘留, 版本標記, V2.x, v[X.X], 變更叙事, 歷史脂絡, 方案代號, 操作日期, CHANGELOG, timeless, 註解版本, atom 過時 claim, docstring 版本
- Created-at: 2026-07-01
- Related: feedback-rigor-standards, cognitive-patterns, feedback-memory-structure

## 知識

- [臨] 硬規則（使用者多次要求）：實戰中的腳本（.py/.js/config/測試）與記憶（atom）只描述「現在怎麼運作」，用 timeless 語氣。禁留任何版本操作脂絡：v[X.X] / V2.x 等版本標記、「原本 X 現改 Y」的變更叙事、方案代號（如「方案A」）、操作過程日期。
- [臨] 歷史脂絡只存在專門記錄歷史的檔：_CHANGELOG.md / TECH.md / Architecture.md / DevHistory。live 檔要改就直接改成現況，變更緣由寫進 CHANGELOG，不埋進 live 檔或 atom。
- [臨] 既有 atom / 註解內容過時 → 直接修成現況（timeless），不 append「某版本改了什麼」的變更註記（那只是把歷史搬進 live 記憶）。

## 行動

- 寫/改 code/test/config/atom 前自檢：有無 v[X.X] / V2.x / 變更叙事 / 方案代號 / 操作日期；有則改 timeless
- 變更緣由與歷史寫 _CHANGELOG.md，不寫進 live 腳本 / atom
- 修 atom 過時 claim 用「改成現況」而非「追加版本註」
