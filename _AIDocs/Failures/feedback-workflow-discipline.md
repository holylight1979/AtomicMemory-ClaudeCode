# feedback-workflow-discipline

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: handoff, 續接, 下 session, next-phase, 順手修補, drift 修補, 重複失敗, fix-escalation, 裁決, 決策推薦, plan 路徑, SessionStart hook, commit message, 上 GIT
- Created-at: 2026-05-26
- Related: feedback-completion-gates, feedback-tooling-reliability, feedback-rigor-standards, workflow-parallel-agents, feedback-memory-system-doc-sync, realm-範疇分區機制-v5, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags, a執p-自執驗上p-自動完工協議, goal-driven-verify-loopkarpathy-吸收, 自己flag的維護動作直接做完不要反問, feedback-complexity-origin-trace, handoff-綜觀品質與抗失真寫法, 跨session資訊失真機制與對策, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, 模型行為移植-fable行為契約必載檔, preferences, feedback-程式註解與敘事-現況直覺白話-禁版本脈絡與咬文嚼字, 禁語-hook-不開引用豁免誤報噪音-vs-契約破洞不對稱, feedback-整理歸檔任務-狀態變更即決策-活項對照閘-方向不明動手前先問

## 知識

- [觀] handoff prompt 含六區塊自足性：現狀/改動清單/驗證/下一步/危險/規則連結，不靠模型記憶

- [觀] SessionStart hook 禁寫死特定 plan/phase 路徑，phase 狀態走 _staging/next-phase.md 或 hook 獨立 config

- [觀] 途中 drift ≤ 5 行 → 當場修；5-20 行 → 修 + diff；cross-檔 → handoff 明寫超出原因

- [觀] 重複失敗 ≥ 2 次啟動 fix-escalation（6 Agent 精確修正會議）

- [觀] 裁決 / 技術選擇不列選單；先推薦一個 + 理由 + 主要權衡

- [觀] git commit message 繁體中文（prefix 與 Co-Authored-By footer 保留英文）

- [觀] 「前例」/「既有 drift」/「pre-existing」 需附「檢測時點 + 不修風險」才可跳過
- [觀] 暫時關閉全域系統設定必寫 handoff：如為推進其他工作而臨時關閉 hooks / 服務 / gate（settings.json hooks 區 / Vector Service / Codex Companion 等），必須在 handoff 交接文件明寫『已暫關 X / 還原條件 Y / 影響範圍 Z』，避免下個 session 不知情導致多 session drift。V5 Wave 4-5 期間 settings.json hooks 暫關 22 天即此覆轍（commit 04b35b4 砍 308 行未交接，hook 系統實際停擺直到 Wave 5 Session 5 重建）。
- [觀] 給人閱讀文件（TECH.md / README / DocIndex / Architecture / Install-forAI）承載衍生事實（skill/atom 計數、knowledge 格式規則），真 SoT 在 code / SPEC / `_atom_index.json` → 單一 feature 漣漪到 5-7 檔；Guardian 覆轍偵測對 TECH.md「same_file_3x」易誤報（實為多次合法 doc-sync、非卡關 retry）。對策：給人文件對 SoT 用 cross-ref（→SPEC §X）、勿複製規則本體；計數類儘量指向 JSON SoT，減少漣漪面。
- [觀] auto-handoff（程式自動備 stub）≠ 手動 /handoff（六區塊完整品質）：PreCompact/SessionEnd 自動寫的是**客觀骨架 stub**（主觀區塊留 TODO(模型補全)），手動 /handoff 才產六區塊完整自足版。auto stub = 「沒手動也有保底」、**不取代**手動；should_write_stub 偵測到既有手寫 next-phase*.md 即不覆蔓（尊重更佳手寫版）。見 [[a執p-自執驗上p-自動完工協議]]。

## 行動

- handoff 寫足六區塊

- drift 按門檻當場修

- 重複失敗 ≥ 2 次 → fix-escalation

- 裁決先推薦 + 理由

