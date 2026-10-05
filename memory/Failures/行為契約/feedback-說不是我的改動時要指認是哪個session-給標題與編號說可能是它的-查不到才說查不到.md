# feedback-說不是我的改動時要指認是哪個session-給標題與編號說可能是它的-查不到才說查不到

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 不是我的, 那不是我的, 其他 session, 未提交的檔, 歸屬, 誰改的, aiTitle, session 標題, 併發 session, 非我造成, 指認 session
- Created-at: 2026-10-05
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [臨] 使用者指正（2026-10-05）：我回報「根層有 23 個未提交的檔，那不是我的」——這種說法會被退避閘質疑，也讓使用者得自己猜是誰的。使用者要的是：能知道目前開著哪些 session 及其關聯時，就回**該 session 的標題或編號**，說「可能是它的」。標題就是使用者在 IDE 分頁上看到、用來辨識的那個名字。
- [臨] 查法（當場實跑可行，約一分鐘）：① `git status --porcelain` 的檔清單 ∩ 各 `workflow/state-<session_id>.json` 的 `modified_files`——命中數最高者即擁有者（實例：23 個未提交檔有 22 個命中 session `32cb5712`）；② 標題在 `~/.claude/projects/<專案 slug>/<session_id>.jsonl` 的 `"aiTitle"` 欄（實例：「AI 模型與內部工具調查」）；③ `ListAgents` 工具列出目前活著的同機 session 與是否 idle。state 檔的首句 prompt 也能佐證關聯（例：那個 session 的開場就是我給的交接 prompt）。
- [臨] 回報寫法：「這 N 個檔可能是《標題》（session 編號前 8 碼）的，它的改檔紀錄命中其中 M 個」；只命中一部分就說剩下的查不到歸屬；完全查不到才說「查不到是哪個 session 的」，並附查過什麼。不要只用否定句交代歸屬。
- [臨] 目的與適用條件（使用者 2026-10-05 補充）：這個做法的用意是「透過自動查詢，精確避免 hook 對你產生不必要的質疑」——用查到的證據取代空口的否定句，退避閘就沒有可質疑的地方。使用者強調：是因為當時的模型（Fable 5.1、high effort）回應讓他放心，才提供這個方法。**適用條件：執行者必須是可信賴的 LLM（至少 Fable 5.1、或 Opus 5.5 以上等最新模型），符合者應自動使用、不必等使用者提醒**；較弱的模型或 sub-agent 不得拿「可能是某 session 的」當成歸屬結論，只能列出查到的原始證據（命中數、標題）讓主對話或使用者判斷。
- [臨] 不得濫用：指認必須來自當下實跑的查詢結果，不能憑印象或推測套一個 session 名字來過閘；命中數偏低或多個 session 都命中時要照實列出，不硬選一個。

## 行動

- 要說「不是我的／非本 session 產物」之前：先跑 state 檔交集＋讀 aiTitle＋ ListAgents
- 回報用「可能是《標題》（編號）的，命中 M/N」，查不到的部分明說
- 指認出擁有者後仍不代它提交，留給該 session 自己收
