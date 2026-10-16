# 瘦身必載檔時搬走的內容要問需要那一刻會不會在眼前-skill內文只在觸發時載入-通用陷阱別搬進單一情境的skill

- Scope: global
- Author: holylight
- Source: 2026-10-15 瘦身專案必載檔後，使用者問「有沒有導致失能或失智」，逐項重審查出 7 處
- Quote: 先檢查一下改了CLAUDE.md以後，有沒有導致失能或失智的問題?
- Confidence: [臨]
- Trigger: CLAUDE.md 瘦身, 必載, 常駐, 失能, 失智, 搜進 skill, skill 描述精簡, MEMORY.md 瘦身, token 節省, 觸發詞
- Created-at: 2026-10-15

## 知識

- [臨] 砍必載檔（CLAUDE.md、MEMORY.md、skill 描述）時，「別處找得到」不等於「需要時會在眼前」：skill 內文只在該 skill 觸發時載入，atom 只在提示詞命中 trigger 時注入，MCP 工具說明只在呼叫該工具時看到。逐項問「需要它的那一刻，它會不會已經在 context」，答不出來就留在必載檔。
- [臨] 最容易砍錯的是通用陷阱寫在單一情境下：例如「中文路徑經 PowerShell／git-bash 傳給 svn 會亂碼」原本寫在 commit 段，搬進只在 commit 時觸發的 skill 後，平常跑 svn status／diff 的情境就沒人提醒。搬之前先問這條規則適用的情境是不是比那個 skill 寬。
- [臨] 精簡 skill 描述時，使用者會照貼的錯誤字串與口語問法（如「8080 連線失敗」「找不到 X」「有幾支」）是觸發詞，不是冗字。改完用舊描述「」內片語逐一比對新描述，列出掉了哪些再判斷。

## 行動

- 砍必載內容前逐項標「需要時誰會把它送到眼前」，標不出來的不砍
- skill 描述改寫後跑一次新舊觸發片語比對
