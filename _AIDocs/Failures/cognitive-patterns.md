# 認知模式偏差（Cognitive Patterns）

- Scope: global
- Confidence: [固]
- Trigger: 過度工程, 代理指標, proxy metric, AI看不懂, AI在打轉, 品質回饋, 自我合理化, 編造規則, 籠統話術, 訂規保留, 設計慣例, 截斷, 採樣, 完整內容, 品質判定, excerpt
- Last-used: 2026-05-28
- Created-at: 2026-03-13
- Related: decisions, feedback-rigor-standards, cc-能力查證反編譯實跑-binary, windows-cc-hook-閃-console-pythonw-修-layer-1勿只補巢狀-creationflags, 對談結束自動記憶與錯誤加權深記, feedback-complexity-origin-trace, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, 跨session資訊失真機制與對策, escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造, 自動萃取層淨值審查-調整式拔除-2026-07, feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔, feedback-completion-gates, 並行agent產出併入交付物必須標驗證強度分層, 歸因早停-找到合理嫌疑機制就停止驗證

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
- [觀] **負向存在斷言的範疇敏感**（2026-06-26 實例）：宣稱某檔/commit「不存在 / 被捧造」前，必須窮舉所有合理位置——多 repo realm 系統下 core(`~/.claude`) 與專案(`C:/Projects`) 是**不同 git repo**。本次只查 core repo 就斷言 prior session 捧造 `classify-project-atoms.py`/`eddd8f3`，改查專案 repo 後兩者皆真實。「not found」只代表「我查的地方沒有」，非「不存在」。**防範**：負向斷言（不存在/捧造/必爆）前先列待查範疇清單逐一證偉，尤其跨 repo / 跨 realm。對應 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]]。
- [觀] **截斷/取樣視圖 → 過度一般化斷言**（2026-06-30，draft taxonomy/去蕪引擎開發實例）：為省 token 用 `excerpt=body[:200]` 餵 LLM 分類器並據此跨 48 條樣本斷言「draft 不是垃圾、is_real 全高」，**從未讀過任何一份完整 draft**。user 連問兩次「你看過完整內容嗎」並出示一份截斷 draft（內容斷在半詞 `Deser`、反引號未閉合）後，改讀完整內容 + 寫確定性掃描器，實證 142 條中 **40% 是截斷損壞或近重複**（GM Blocker 5 份重複、RebuildBlobAsync 4 份…）。
- [觀] **根因（非表面症狀）**：把「取樣/截斷視圖」當成「全集」下一般化斷言。excerpt[:200] 截斷本身是 runner 為批量省 token 的合理設計——錯在**用它的輸出回答「全集有無垃圾」這個它根本沒看全的問題**——「分類用的輸入視圖」≠「品質判定的證據」，局部（分類）成立不可推及（品質）。斷點：截斷發生在 200 字後、近重複在各自 excerpt 下看似獨立 → 兩種主垃圾恰好都在取樣視窗外，視圖系統性盲視。同一截斷視圖同時餵 LLM 與自評，污染雙方。屬 [[feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長]] 具體實例（機制存在≠實際成立）。
- [觀] **防再犯**：對「資料品質/有無垃圾/全集性質」類斷言，先讀**數份完整**樣本 + 跑**確定性全集掃描**（截斷:末字非終止符/括號反引號不對稱；重複:文本相似度叢集），不可只憑截斷 excerpt 或 LLM 評分。LLM 評分本身也只在完整內容上才可信。

## 行動

- 發現正在大幅修改前 session 生成的程式碼（>30% 變動）時，記錄到品質回饋
- 使用代理指標前，先確認它真的能代表要測量的東西
- 宣稱「user 訂規 / 設計慣例 / by design」前，先指出具體文件路徑＋行號；指不出立即撤回宣稱、按實際文件規則行事
- 斷言產物品質/完整性/重複/「沒問題」前，讀完整內容或跑全量確定性掃描（截斷訊號、文本相似度），不從截斷/採樣/單一視窗斷言；確定性結構偵測優先於 LLM 主觀評分
