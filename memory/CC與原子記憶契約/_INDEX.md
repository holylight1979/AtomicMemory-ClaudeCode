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
| commitorder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令 | CommitOrder閘只認最新一則使用者原話-中間夾系統通知或背景事件就要請使用者重下口令 |
| decisions | 全域決策 |
| edit工具new-string尾端空白會被裁掉-切點停在空白上會黏字-切點要停在非空白字元並看diff | Edit工具new_string尾端空白會被裁掉-切點停在空白上會黏字-切點要停在非空白字元並看diff |
| escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造 | escalation-hook 在 edit-count-proxy 上 false-fire 的辨識（無真實失敗迴圈時不盲從不編造） |
| hook-systemmessage-只給使用者看-模型讀不到-要回饋模型用additionalcontext或deny-reason | hook-systemMessage-只給使用者看-模型讀不到-要回饋模型用additionalContext或deny-reason |
| mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口 | mcp-json-與-user-scope-同名-server-並存雙開-黑窗第四層破口 |
| plan-mode-彈窗變多-bypass新版提示改用bash查讀-msys路徑被判工作目錄外-allow家族規則修法 | plan-mode-彈窗變多-bypass新版提示改用bash查讀-msys路徑被判工作目錄外-allow家族規則修法 |
| pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次 | pretooluse的additionalcontext不是寫前攔截-edit-payload已生成-提醒只影響下一次 |
| sessionstart的提示只有模型看得到-要使用者做決定就寫成叫模型用askuserquestion問的指示-問到有答案為止不要只提示一次 | SessionStart的提示只有模型看得到-要使用者做決定就寫成叫模型用AskUserQuestion問的指示-問到有答案為止不要只提示一次 |
| skill-description沒加引號遇到空白加井號會被yaml當註解截斷-觸發條件消失且不報錯-一律雙引號 | skill-description沒加引號遇到空白加井號會被yaml當註解截斷-觸發條件消失且不報錯-一律雙引號 |
| 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾 | 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾 |
| 壓縮後根層-claudemd-由磁碟重讀不需自製-constraint-pinning-真正會丟的是對話中的計畫脈絡-用-staging-計畫檔加-sessionstart-resume-指標接續 | 壓縮後根層 CLAUDE.md 由磁碟重讀不需自製 constraint pinning-真正會丟的是對話中的計畫脈絡-用 _staging 計畫檔加 SessionStart resume 指標接續 |
| 宣稱與退避詞表降成提示-收尾用宣稱行與不做行留給llm介入-程式只查有沒有回證據對不對並留帳 | 宣稱與退避詞表降成提示-收尾用宣稱行與不做行留給LLM介入-程式只查有沒有回證據對不對並留帳 |
| 專案層tool事件閘要用原生hooks-根層只轉送sessionstart給project-hooks | 專案層tool事件閘要用原生hooks-根層只轉送SessionStart給project_hooks |
| 瘦身必載檔時搬走的內容要問需要那一刻會不會在眼前-skill內文只在觸發時載入-通用陷阱別搬進單一情境的skill | 瘦身必載檔時搬走的內容要問需要那一刻會不會在眼前-skill內文只在觸發時載入-通用陷阱別搬進單一情境的skill |
| 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器 | 跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器 |
| 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送 | 跨session訊息在收件端進計畫模式時會被扣住等使用者核准-逾時就作廢不送達-補充事項要寫進開工句或等對方離開計畫模式再送 |
| 身份與職能自動來自ad-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders | 身份與職能自動來自AD-帳號即get-current-user-職能由whoami群組對映-查不到就空不預設programmer-裁決名單review-deciders |
| 部位表前綴一律寫成相對專案根-子字串命中的列會被任何錨在專案根的列整片蓋過 | 部位表前綴一律寫成相對專案根-子字串命中的列會被任何錨在專案根的列整片蓋過 |
| 部位表路徑前綴要用反引號包-沒包整列被解析器略過-表看起來有程式讀到是空的 | 部位表路徑前綴要用反引號包-沒包整列被解析器略過-表看起來有程式讀到是空的 |
| 驗證範圍的收據要在前景直接跑那一項-指令尾只接tail不夾grep-背景跑與超過十分鐘的不算-改檔排在跑範圍之前 | 驗證範圍的收據要在前景直接跑那一項-指令尾只接tail不夾grep-背景跑與超過十分鐘的不算-改檔排在跑範圍之前 |
