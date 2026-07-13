# feedback-live 檔與記憶不留版本操作脈絡（歷史歸專門檔）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 版本殘留, 版本標記, V2.x, v[X.X], V5 Pxx, Phase, Sprint, Wave, 里程碑, milestone, stderr 前綴, spec 錨, 執行流程字串, 變更叙事, 自我更正鏈, 歷史脈絡, 方案代號, 操作日期, commit hash, CHANGELOG, timeless, 註解版本, atom 過時 claim, docstring 版本
- Created-at: 2026-07-01
- Related: feedback-rigor-standards, cognitive-patterns, feedback-memory-system-doc-sync, feedback-程式註解與敘事-現況直覺白話-禁版本脈絡與咬文嚼字

## 知識

- [臨] 硬規則（使用者多次要求）：實戰中的腳本（.py/.js/config/測試）與記憶（atom）只描述「現在怎麼運作」，用 timeless 語氣。禁留任何**執行流程/版本操作脈絡**：① 版本/里程碑標記 v[X.X] / V2.x / **V5 Pxx / Sprint N / Wave N / 非檔名耦合 Phase N**；② 開發用 stderr/debug 前綴 **`[vN.N]` / `[phaseN]`**、debug 事件 key 版本前綴（`_atom_debug_error("V4.1:…")`）；③ **spec/需求交叉引用錨 [Fxx] / Sx.x**；④「原本 X 現改 Y」變更叙事、**新舊 diff、自我更正/撤銷鏈（→ 收斂為單一現況事實）**；⑤ 方案代號（方案甲/乙）；⑥ 操作日期戳、**commit/SVN hash、incident count（第三度/三度/一次）、「實案/實測」事件用語、陳舊 `test_*.py` docstring 自名（改對齊實際檔名）**。
- [臨] 歷史脂絡只存在專門記錄歷史的檔：_CHANGELOG.md / TECH.md / Architecture.md / DevHistory。live 檔要改就直接改成現況，變更緣由寫進 CHANGELOG，不埋進 live 檔或 atom。
- [臨] 既有 atom / 註解內容過時 → 直接修成現況（timeless），不 append「某版本改了什麼」的變更註記（那只是把歷史搬進 live 記憶）。
- [臨] **KEEP 邊界（勿誤剝，本 session 血淚）**：SCHEMA_VERSION / _migrate_vXXX 遷移識別與 schema 欄位版本、**裸 V4/V5/V6 能力世代 scope**（非里程碑 Pxx）、測試 fixture 日期/值、程式實際比對的功能 literal（migrated-v2.21 / JSON key / SVN 錯誤碼 / protocolVersion）、**檔名耦合 Phase N**（verify_*_phaseN.py 標題，且不改檔名）、SPEC §、DevHistory/正位 doc 章節導覽錨。判別問：「此 token 是當前功能識別，還是開發過程脈絡？」前者 KEEP、後者剝；不確定 → KEEP 並標出。
- [臨] **掃除方法（勿信逐檔清單為完整）**：先 pattern-first 全庫 grep（上述①-⑥）再動手——逐檔清單/印象常漏系統性殘留（本 session 首批漏跨目錄陳舊 docstring、漏 stderr 前綴檔）。只動註解/docstring/字串 → run_verify + AST 兜底（行為零改）；atom body 走 byte-exact 不動 frontmatter（零 index/mirror drift）。
- [臨] **主動移除（Point 2，非只別加）**：舊版本宣告在新版本進文件更新階段後要**主動全面移除**（不只「不新增」）——視為系統內部一份子、不再特別標註版本。pattern-first 全庫掃，非等下次遇到才改。
- [臨] **編年不入 atom（Point 3，邊界）**：「發展型編年紀錄」（milestone/「Pn 改了 X」/審查總結/機制演化史）**不進 atom** → 歸 `_AIDocs/DevHistory/` 或 release-note；atom 只收**可重用的 timeless gotcha/機制/決策**（trigger 自動注入的自我防呆）。區別：DevHistory=文件不自動注入；MemDev atom=自動注入+計數。只禁編年、非廢 MemDev realm。規則權威已升 rules/core.md「版本與文件治理」段。

## 行動

- 寫/改 code/test/config/atom **前自檢**：有無 v[X.X]/V5 Pxx/Sprint/Wave/Phase(非檔名)/`[vN]` 前綴/`[Fxx]`·Sx.x 錨/變更叙事/自我更正鏈/方案代號/日期戳/hash；對照 KEEP 邊界排除功能識別後，剩者改 timeless
- 變更緣由與歷史寫 _CHANGELOG.md，不寫進 live 腳本 / atom
- 修 atom 過時 claim 用「改成現況」而非「追加版本註」
