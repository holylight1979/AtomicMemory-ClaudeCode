# preferences

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: 偏好, 執P, 執驗上P, 上GIT, 上傳GIT, commit, push
- Created-at: 2026-09-04
- Related: feedback-上git是commit加push一體-沒口令前不先commit-讓使用者能先看diff, feedback-收尾工作樹要上乾淨-該上就上-用不到就刪-不反問, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a, workflow-rules, a執p-自執驗上p-自動完工協議, feedback-workflow-discipline, feedback-rigor-standards, 專案等級-mcpskillhookslog-不放全域根層

## 知識

- [固] 「上GIT」/「上傳GIT」: 縮寫指令，針對當次批量作業（單一或多 session）所異動的範圍執行 選擇性 staging → commit → push **一氣做完**。口令下達前**不碰 git**（不得先 commit 再等使用者說 push；使用者要先看 diff 再下令）。若沒有當次異動，須向使用者確認是否要查詢所有異動來執行。若專案屬於 SVN，則此縮寫也代表 commit 到 SVN repo，完成後主動報備「已上傳 SVN repo」。
- [固] 「執驗上P」/「執P」: 縮寫指令，等同「由 AI 考量拆分 session 接續處理，單一階段執行完畢，且驗證、單元測試、整體測試都無誤後，上傳 GIT 或者上傳 SVN（如有可上傳的 repo），再給使用者下一階段接續用的 prompt；此規則延伸到本項目全數完成」
- [固] 專案知識庫深度運用: 處理專案程式邏輯、架構、結構、踩坑經驗等，都要系統性記錄到專案 _AIDocs 內（不重複前提下）；同時確保寫入向量記憶庫供後續語意檢索。目標：專案知識被智慧儲存→精準注入→高效協助
- [固] 框架觀: 薄框架，開發者要能理解底層運作

## 行動

- 收到「上GIT」：git add <本批檔案> → commit → push 一氣做完，不停在 commit 等 push
- 沒有口令：改完只報告改了哪些檔＋驗證結果，不動 git
- 處理專案程式碼後，將邏輯/架構/結構/經驗寫入 _AIDocs（去重）+ 向量記憶庫，確保知識可被檢索與注入
