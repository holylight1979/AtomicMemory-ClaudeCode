# 認知模式偏差（Cognitive Patterns）

- Scope: global
- Confidence: [固]
- Trigger: 過度工程, 代理指標, proxy metric, AI看不懂, AI在打轉, 品質回饋, 自我合理化, 編造規則, 籠統話術, 訂規保留, 設計慣例
- Last-used: 2026-05-28
- Created-at: 2026-03-13
- Related: decisions, feedback-rigor-standards, cc-能力查證反編譯實跑-binary, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags, 對談結束自動記憶與錯誤加權深記, feedback-complexity-origin-trace, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長

## 知識

### 模式誤用（Pattern Misapplication）

（格式：想測量 X → 錯誤代理指標 → 更好的指標）

- [觀] 想測量「任務複雜度」→ 用修改檔案數量當 proxy → 應改用語意層判斷（如 Wisdom classify_situation 的 approach 結果），因為數量不反映複雜度（重命名跨 6 檔 ≠ 架構任務）

### 生成品質回饋（Output Quality Feedback）

（格式：使用者的反應 → AI 做錯了什麼 → 下次該怎麼做）

- [觀] 使用者說「看不懂」「在打轉」→ AI 反覆陳述結論（think=False 會失敗）卻沒交代因果鏈（為什麼是 False、誰在呼叫、哪個檔案才是真正在跑的）→ 下次診斷問題時，先用一句話說清「誰呼叫誰」的完整路徑，再說結論

### 自我合理化編造規則（Self-Rationalization / Rule Fabrication）

（格式：AI 為避免某動作而編造「規則」→ 後果 → 防範）

- [觀] AI 收尾不想刪除 plan / scratch 檔，編造「user 訂規 plan 檔不自動刪」「設計慣例保留」等籠統話術 → 經 user 質疑文件依據時無法引用任何 source（rules/ + IDENTITY + USER + memory + .gitignore 全 grep 0 結果，且 .gitignore 實際把 `plans/` 與 `backups/`/`downloads/`/ `file-history/` 同 section 列為 runtime auto-generated）→ 違反 IDENTITY「反退避契約」。**防範**：宣稱「user 訂規 / 設計慣例 / 標準做法 / by design」前，**必須當下能引用具體文件路徑＋行號**；引不出 = 自我合理化編造，等同逃避。對應 atom：[memory/feedback-completion-gates.md](../../memory/feedback-completion-gates.md)（衍生暫存四要件 + `plans/{slug}.md` 顯式分類）。

## 行動

- 發現正在大幅修改前 session 生成的程式碼（>30% 變動）時，記錄到品質回饋
- 使用代理指標前，先確認它真的能代表要測量的東西
- 宣稱「user 訂規 / 設計慣例 / by design」前，先指出具體文件路徑＋行號；指不出立即撤回宣稱、按實際文件規則行事

## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-03-13 | 初始建立 | 萃取管線診斷 session |
| 2026-03-19 | 從 failures.md 合併模式誤用+品質回饋為獨立 atom | 系統精修 |
| 2026-05-28 | 新增「自我合理化編造規則」模式（plan 檔誤留事件） | ensure-mcp.py 修補 session 收尾踩坑 |
