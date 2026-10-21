# 解合併衝突兩側都留只對純加法段成立-hunk切在函式中段會吃掉共用尾行-改用main版加分支尾段重建-解完必跑該檔verify不只py-compile

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-20 G7／G9 合併（hub_config validate_min_map 掉 return、stop.py 重複 import、wg_release_rules G7 段插進函式中段）
- Confidence: [臨]
- Trigger: 兩側都留, resolve_both, 合併衝突, merge conflict, 共用尾行, return errors 掉了, import 重複, 檔尾段, merge main 工作樹, IndentationError 合併後, NoneType is not iterable 合併後
- Created-at: 2026-10-20
- Related: 總控台多軌合併經驗-退回同一面第二次就定死規則或改設計-整批合併後的紅先單跑歸軌補修不reset-接續單要寫舊步驟作廢與停工恢復條件, 記憶索引三檔多機合併必衝突-裝-merge-atom-index-驅動-勿手合
- Quote: 「"下個寫碼session" !? 他們有空就讓他們修完不是嗎..? 這也是我說 "我從未答應把這種東西另外放進修正計畫" 的狀況... 倘若是 Codex 或審查時挖出來的、但LLM判斷後 其實屬於"飄移"的，直接不做，但倘若有關且確實有問題，就應該要立即修正」

## 知識

- [臨] 「兩側都留」（theirs＋ours 串起來）只對純加法的衝突段成立：兩軌各在檔尾加自己的段、或各加一個獨立函式。git 切 hunk 時若把共用的尾行（函式最後的 `return errors`、`})`）留在 hunk 外，兩側都留會讓前一段函式沒有 return 回 None，呼叫端 `errors.extend(None)` 炸 TypeError，整道閘判不出（實測 130 案紅）；import 區兩側都留則剩兩行重複 import。另一型：hunk 的分支側從檔中段開始、main 側一路到檔尾，兩側都留會把分支段插進 main 的函式中間（IndentationError）。
- [臨] 判法：解完先 `py_compile`（抓插錯位置），再跑該檔的 verify 集（抓掉 return 這種編譯過但行為錯的）；兩者缺一不可。分支改動若是純檔尾新增（`git diff <merge-base> HEAD -- 檔` 只有一個 @@ 且在檔尾），最穩是「取 main 版全文＋分支版從段落標記到檔尾」重建，不用 hunk 解。
- [臨] 自動合併（沒報衝突）的檔也要進 verify 集：這次 stop.py 兩段各自完整，但順序（G9 段在前、G7 段在後）是人決定的，案例才證得到。

## 行動

- 工作樹 merge main 解衝突：兩側都留只用在純加法段；hunk 不乾淨就用 main 版＋分支尾段重建
- 解完 py_compile＋該檔 verify 集都跑，再 ff 進 live
