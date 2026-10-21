# memory/CC與原子記憶契約 — 範疇索引

> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。

## 本層 atom

| Atom | 說明 |
|------|------|
| atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人 | atom-scope-讀取端可見性-候選池一次收窄-他專案不進池-personal只給本人 |
| atom-write-global必須省略project-cwd | atom-write-global必須省略project-cwd |
| bash寫入目標解析器會把python-c與pytest-c當成無法判定而擋-改寫成腳本檔或讓pytest自找ini-grep工具預設跳過gitignore檔 | bash寫入目標解析器會把python-c與pytest-c當成無法判定而擋-改寫成腳本檔或讓pytest自找ini-grep工具預設跳過gitignore檔 |
| cc-windows-hook與statusline經git-bash執行-dollar變數與波浪號展開-百分號不展開-settings可寫localappdata與home去機器路徑 | cc-windows-hook與statusline經git-bash執行-dollar變數與波浪號展開-百分號不展開-settings可寫LOCALAPPDATA與HOME去機器路徑 |
| cc同伴訊息封裝只轉義正文裡的cross-session-message閉合標籤-其他harness標籤原樣保留 | CC同伴訊息封裝只轉義正文裡的cross-session-message閉合標籤-其他harness標籤原樣保留 |
| claude-code設定目錄claude-config-dir取值是有值就用-空字串當沒設-不去空白-設定檔與claudejson都跟著搬-和記憶系統資料根是兩件事 | Claude Code設定目錄CLAUDE_CONFIG_DIR取值是有值就用-空字串當沒設-不去空白-設定檔與.claude.json都跟著搬-和記憶系統資料根是兩件事 |
| claude-p無頭跑會被hook判成無法互動-g9第二意見整條不觸發-預設claude-code-entrypointclaude-vscode可保留但-p沒有askuserquestion | claude-p無頭跑會被hook判成無法互動-G9第二意見整條不觸發-預設CLAUDE_CODE_ENTRYPOINT=claude-vscode可保留但-p沒有AskUserQuestion |
| claude-p的json回傳遇背景通知只剩通知那一小段-result與被拒清單要從transcript補整回合-total-cost-usd是session累計 | claude-p的json回傳遇背景通知只剩通知那一小段-result與被拒清單要從transcript補整回合-total_cost_usd是session累計 |
| claude背景session實測-用vscode擴充那支claudeexe起-bg-agents總覽enter就是attach-人能直接選答-hook全套照跑-esc兩下是rewind-關視窗不影響-用stop收 | claude背景session實測-用vscode擴充那支claude.exe起-bg-agents總覽Enter就是attach-人能直接選答-hook全套照跑-esc兩下是rewind-關視窗不影響-用stop收 |
| commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令 | CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令 |
| decisions | 全域決策 |
| edit工具new-string尾端空白會被裁掉-切點停在空白上會黏字-切點要停在非空白字元並看diff | Edit工具new_string尾端空白會被裁掉-切點停在空白上會黏字-切點要停在非空白字元並看diff |
| escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造 | escalation-hook 在 edit-count-proxy 上 false-fire 的辨識（無真實失敗迴圈時不盲從不編造） |
| hook-systemmessage-只給使用者看-模型讀不到-要回饋模型用additionalcontext或deny-reason | hook-systemMessage-只給使用者看-模型讀不到-要回饋模型用additionalContext或deny-reason |
| hook超過settings的timeout會被cc整支取消只在transcript留hook-cancelled-收尾所有守門靜默失效-加段就要量耗時並在超時前降級留帳 | hook超過settings的timeout會被CC整支取消只在transcript留hook_cancelled-收尾所有守門靜默失效-加段就要量耗時並在超時前降級留帳 |
| mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口 | mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口 |
| plan-mode-彈窗變多-bypass新版提示改用bash查讀-msys路徑被判工作目錄外-allow家族規則修法 | plan-mode-彈窗變多-bypass新版提示改用bash查讀-msys路徑被判工作目錄外-allow家族規則修法 |
| pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次 | pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次 |
| realm判core還是local-問換一個不用記憶系統的專案還用不用得上-例子取自記憶系統不算local-拿不準回core | realm判core還是local-問換一個不用記憶系統的專案還用不用得上-例子取自記憶系統不算local-拿不準回core |
| sessionstart的提示只有模型看得到-要使用者做決定就寫成叫模型用askuserquestion問的指示-問到有答案為止不要只提示一次 | SessionStart的提示只有模型看得到-要使用者做決定就寫成叫模型用AskUserQuestion問的指示-問到有答案為止不要只提示一次 |
| skill-description沒加引號遇到空白加井號會被yaml當註解截斷-觸發條件消失且不報錯-一律雙引號 | skill-description沒加引號遇到空白加井號會被yaml當註解截斷-觸發條件消失且不報錯-一律雙引號 |
| sync-atom-index對空索引用add-from-frontmatter補不齊且每次張數不同-整份重建要用rebuild | sync-atom-index對空索引用add-from-frontmatter補不齊且每次張數不同-整份重建要用rebuild |
| 使用者原話算不算長期決策-對這次產出的糾正或指示不算-萃取不准比原話寬 | 使用者原話算不算長期決策-對這次產出的糾正或指示不算-萃取不准比原話寬 |
| 切入點識別字樣含常見中文詞會被中文trigger子字串誤中無關卡-等淬鍊才綁卡的列用英數字樣 | 切入點識別字樣含常見中文詞會被中文trigger子字串誤中無關卡-等淬鍊才綁卡的列用英數字樣 |
| 原子記憶是llm切入點的調校層-閘與案例守流程卡守判斷-驗收判錯先歸因改卡不加閘-文字評分只附不擋且裁判用開源免費llm | 原子記憶是LLM切入點的調校層-閘與案例守流程卡守判斷-驗收判錯先歸因改卡不加閘-文字評分只附不擋且裁判用開源免費LLM |
| 原話不在任何一則的誤判先查那則原話當下有沒有掛在樹上-樹結束後收的原話要等重開才掛-不要先猜正規化 | 原話不在任何一則的誤判先查那則原話當下有沒有掛在樹上-樹結束後收的原話要等重開才掛-不要先猜正規化 |
| 去重宣告看主張不看主題-新內容說舊卡哪句錯就是取代-補同一條判準的實例才是同一條 | 去重宣告看主張不看主題-新內容說舊卡哪句錯就是取代-補同一條判準的實例才是同一條 |
| 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾 | 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾 |
| 回合意圖分類吃到同伴訊息正文-clean-prompt只剔ide區塊-重構意圖會被派工信觸發-所有吃turn-intent的閘與選片都受影響 | 回合意圖分類吃到同伴訊息正文-clean_prompt只剔IDE區塊-重構意圖會被派工信觸發-所有吃turn_intent的閘與選片都受影響 |
| 壓縮後根層-claudemd-由磁碟重讀不需自製-constraint-pinning-真正會丟的是對話中的計畫脈絡-用-staging-計畫檔加-sessionstart-resume-指標接續 | 壓縮後根層 CLAUDE.md 由磁碟重讀不需自製 constraint pinning-真正會丟的是對話中的計畫脈絡-用 _staging 計畫檔加 SessionStart resume 指標接續 |
| 外部程式改claude-json要拿claude-code同一把鎖-建claude-json-lock目錄-鎖內重讀只合併要改的鍵-暫存檔再replace-換行照原檔 | 外部程式改claude-json要拿claude-code同一把鎖-建claude-json-lock目錄-鎖內重讀只合併要改的鍵-暫存檔再replace-換行照原檔 |
| 失敗的工具呼叫cc只送posttoolusefailure-靠posttooluse記改檔與紅測的機制看不到exit1的heredoc寫檔-修改清單與紅測清單會漏記 | 失敗的工具呼叫CC只送PostToolUseFailure-靠PostToolUse記改檔與紅測的機制看不到exit1的heredoc寫檔-修改清單與紅測清單會漏記 |
| 宣稱與退避詞表降成提示-收尾用宣稱行與不做行留給llm介入-程式只查有沒有回證據對不對並留帳 | 宣稱與退避詞表降成提示-收尾用宣稱行與不做行留給LLM介入-程式只查有沒有回證據對不對並留帳 |
| 專案層tool事件閘要用原生hooks-根層只轉送sessionstart給project-hooks | 專案層tool事件閘要用原生hooks-根層只轉送SessionStart給project_hooks |
| 換資料根的session向量檢索查的是全機共用live向量庫再用資料根可見池過濾-bm25為主時向量只在全沒命中才打-新卡要等向量重建 | 換資料根的session向量檢索查的是全機共用live向量庫再用資料根可見池過濾-bm25為主時向量只在全沒命中才打-新卡要等向量重建 |
| 收割只寫讀程式讀不出下次會重犯的使用者糾正與被證錯的卡必收程式常數與當天狀態不收 | 收割只寫讀程式讀不出、下次會重犯的；使用者糾正與被證錯的卡必收，程式常數與當天狀態不收 |
| 瘦身必載檔時搬走的內容要問需要那一刻會不會在眼前-skill內文只在觸發時載入-通用陷阱別搬進單一情境的skill | 瘦身必載檔時搬走的內容要問需要那一刻會不會在眼前-skill內文只在觸發時載入-通用陷阱別搬進單一情境的skill |
| 程式核對ai宣告行時對象名只認整名或邊界結尾-子字串會一行清多條帳-引言與圍欄裡的行不算回答 | 程式核對AI宣告行時對象名只認整名或邊界結尾-子字串會一行清多條帳-引言與圍欄裡的行不算回答 |
| 綁了entry的判準卡是量尺-非總控台session要改得先宣告改判準卡哪張理由留帳-不唯讀以保留判錯當天落卡的迴路 | 綁了entry的判準卡是量尺-非總控台session要改得先宣告改判準卡哪張理由留帳-不唯讀以保留判錯當天落卡的迴路 |
| 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器 | 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器 |
| 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送 | 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送 |
| 身份與職能自動來自ad-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders | 身份與職能自動來自AD-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders |
| 部位表前綴一律寫成相對專案根-子字串命中的列會被任何錨在專案根的列整片蓋過 | 部位表前綴一律寫成相對專案根-子字串命中的列會被任何錨在專案根的列整片蓋過 |
| 部位表路徑前綴要用反引號包-沒包整列被解析器略過-表看起來有程式讀到是空的 | 部位表路徑前綴要用反引號包-沒包整列被解析器略過-表看起來有程式讀到是空的 |
| 重載只為讓常駐程序吃到啟動時才讀的東西-hook改動每事件新程序不用重載-改mcp啟動參數或環境變數才是重載原因 | 重載只為讓常駐程序吃到啟動時才讀的東西-hook改動每事件新程序不用重載-改mcp啟動參數或環境變數才是重載原因 |
| 驗證範圍的收據要在前景直接跑那一項-指令尾只接tail不夾grep-背景跑與超過十分鐘的不算-改檔排在跑範圍之前 | 驗證範圍的收據要在前景直接跑那一項-指令尾只接tail不夾grep-背景跑與超過十分鐘的不算-改檔排在跑範圍之前 |
