# 工作軌交付常漏TECH與CHANGELOG-總控台對帳加第六項文件同步-合併前grep規則名與工具名在TECH有沒有-派工單明寫要自己寫文件

- Scope: global
- Author: holylight
- Source: session:cb4c9c8e 2026-10-20 第二波合併（docs 補齊 commit 9197b51e）
- Confidence: [臨]
- Trigger: 交付信對帳, 文件同步, TECH 沒更新, CHANGELOG 漏寫, 工作軌交付, 合併對帳五項, 總控台補文件, 派工單 文件, 規則名 grep TECH
- Created-at: 2026-10-20
- Related: 總控台多軌合併經驗-退回同一面第二次就定死規則或改設計-整批合併後的紅先單跑歸軌補修不reset-接續單要寫舊步驟作廢與停工恢復條件, feedback-審查或交付時挖出的問題只有已修或飄移不做兩種寫法-不准推給下一個session
- Quote: 「"下個寫碼session" !? 他們有空就讓他們修完不是嗎..? 這也是我說 "我從未答應把這種東西另外放進修正計畫" 的狀況... 倘若是 Codex 或審查時挖出來的、但LLM判斷後 其實屬於"飄移"的，直接不做，但倘若有關且確實有問題，就應該要立即修正」

## 知識

- [臨] 第二波五軌（G7／G11／G14／G16／G8）合併時發現四軌交付的程式都沒寫 TECH.md 與 _AIDocs/_CHANGELOG.md，只有派工單明寫「文件：TECH §x／_CHANGELOG」的那軌（G9）有寫。工作軌不會自動把文件當交付物，派工單沒列就不寫。
- [臨] 總控台對帳的五項（改檔集＝自述、退避禁字、CR、live 未動、merge-tree 無衝突）要加第六項「文件同步」：交付信列的規則名（RULES 表的鍵）、新工具檔名、新 config 鍵，各在 TECH.md grep 一次有沒有；CHANGELOG 有沒有這軌的段。缺 → 照「交付挖出的問題只有已修或飄移不做」規矩，軌還在就派回補，軌已關就總控台照同波已有的段落格式補並在 commit 訊息註明是總控台補的。
- [臨] 派工單「只動哪些檔」段固定加一行：TECH 對應節與 _CHANGELOG 由這軌自己寫（上一波是總控台補的）；交付信對五項之外要附「文件：TECH §… 列／CHANGELOG 段」。

## 行動

- 寫派工單時「只動哪些檔」加 TECH／CHANGELOG 一行
- 收交付信對帳時 grep 規則名、工具名、config 鍵在 TECH；缺就派回或當場補
