# feedback-程式註解與敘事-現況直覺白話-禁版本脈絡與咬文嚼字

- Scope: global
- Author: holylight
- Confidence: [固]
- Trigger: 註解, comment, summary, 敘事, 版本標記, 階段標記, 咬文嚼字, LLM污染, 現況導向, 白話, code comment, 可讀性, 寫code
- Created-at: 2026-07-09
- Related: feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔, feedback-workflow-discipline, feedback-收尾報告使用者視角四要素-白話綜觀非片段細節

## 知識

- [固] 程式碼註解與我輸出的敘事文字：一律「現況導向、白話、一句一義」——讓下一個讀的人（含我自己下一輪）一眼掃過就懂、不需解碼。
- [固] 禁埋版本操作脈絡於 live 檔註解（同時違反 [[feedback-live-檔與記憶不留版本操作脈絡歷史歸專門檔]]）：版本/階段標記（S2.1、S3.2、#6）、日期戳、事件敘事（如「live 2026-07-06 21:23 事件」「live 實案：…」）——這些歸 _AIDocs/DevHistory / _CHANGELOG，不進碼。
- [固] 禁「咬文嚼字 / LLM 污染」風格：生造詞、一句塞三層轉折、堆術語求精確卻犧牲直覺。密度高但難讀＝壞味道。
- [固] 實例（我自己的破口）：sgi_server/PlayerDbServer 的 CharModule 系列註解（PlayerDbService.cs / PlayerDbService.Db.cs / CharModuleDbFactory.cs）即此病典型——S3.3 §D 過渡碼清理須一併改乾淨。
- [固] Why：不直覺的註解讓每次閱讀都要花力氣解碼，久了把清晰思路一點點磨掉、汙染後續所有溝通與設計。user 2026-07 明確拉高為「核心問題、要非常重視、記起來」。

## 行動

- 寫完任何註解/文件段落自問：陌生人一眼看得懂嗎？看不懂就砍到只剩『現況＋意圖』
- 版本/日期/事件/變更敘事一律移出 live 檔，歸 _AIDocs/DevHistory 或 _CHANGELOG
- 既有污染註解在下次動到該檔時順手改成白話一句一義，勿累積
