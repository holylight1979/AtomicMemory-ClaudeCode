# 施工子代理交回的py檔常被整檔改成crlf-合併前用git-diff看到crlf警告就先轉回lf再提交

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CRLF will be replaced, 子代理改檔, 換行符, 施工代理, 合併子代理的改動, 行尾
- Created-at: 2026-11-05
- Source: session:9f83cf22#15d1ba32 2026-11-05
- Quote: 「都收割了? 我另外想到 "安裝" 方面有沒有文件需要更新，或者是參閱現有狀態與理解後 改進 的?」

## 知識

- [臨] 同一天兩個 Sonnet 施工代理各改一支 .py（一支新建、一支改幾行），交回來整檔都變 CRLF；git diff 只印一行「CRLF will be replaced by LF」警告、hunk 看起來正常，但工作樹已經是 CRLF。repo 規則全 LF（.gitattributes eol=lf）。

## 行動

- 收代理的改動後，commit 前數一次 \r\n（一行 python 就够），有就整檔轉回 LF 再提
- 派工單可加一句「寫檔用 LF」，但不要信，收回時照數
