# feedback-動手前不要找理由縮小範圍

- Scope: personal:holylight
- Author: holylight
- Source: unknown 2026-05-21（原對話已逾保留期）
- Confidence: [臨]
- Trigger: 退縮, 找理由縮小範圍, 推小範圍, 工程過大, 推測沒驗證, 丟給使用者, 交接文件先給, auth error 自己 retry
- Created-at: 2026-05-21
- Related: (none)
- Quote: 「喔，那當然要搬，提醒的是如果有混雜 部分有隱私、部分不是隱私的，要拆開來」

## 知識

- [臨] 規則 A：使用者明確選大範圍時不要找理由想推小範圍。動手做、做完再評估。**Why**：UBA POC 那場，使用者選「兩類 bundle 一起隔離」，我一直拿『工作量大、要重 build 驗證 7 小時、風險高』推只做一類。被戳穿『2 隻腳本有這麼困難？』後實際動手『cp + 加 2 個 hook + 新建 1 個 partial』就 done。**How to apply**：使用者選大範圍 → 不寫 push-back、直接做完核心動作（cp + edit + diff verify）、完後再列 risk 給選擇。
- [臨] 規則 B：不要過度推測沒第一手驗證的事就放棄某條技術路徑。先試最直接驗證再決定繞路。**Why**：同一場三次踩雷：(1)推測『cm workspace delete 會抹掉 ZIP』→ 實測只刪 workspace 註冊不刪檔；(2)推測『_artifacts repo 本機 cm 連不到』→ 只是 server 名寫成別名，改成登記的全名就 work；(3)推測『Build Artifact API 唯一路徑』→ 完全不需要。每個推測都讓我繞路寫 fallback、白費 token。**How to apply**：『某條路不通』推測 → 先一條 cm/grep/evaluate 驗證、再決定要不要繞。
- [臨] 規則 C：使用者要 prompt / 交接文件就立即停手給、不要繼續做其他事再補。**Why**：同一場使用者首次要『新 session 接續 prompt』我答應卻繼續 refactor，直到他抱怨『prompt 一直沒給、不知道你在前進什麼鬼』才補。**How to apply**：『該重新給我」 / 『prompt / handoff / 交接』等詞 → 立即產出該交付物再回頭做事。
- [臨] 規則 D：可以自己 retry 的指令失敗不要先丟給使用者。**Why**：同一場 cm checkin 出『LDAP 令牌已過期』我立刻提議『請你重新 SSO』，後來自己 retry 一次 cm add + cm checkin 就 work（token 自動 refresh 或 transient）。**How to apply**：cm / git / cloud CLI 出現 token / auth / transient error 時、先自己 retry 1-2 次，確認真的卡住再請使用者協助。

## 行動

- 使用者明確選大範圍：直接做最小可行版本、不先寫 push-back
- 「某條路不通」推測：先一條指令驗證再決定
- 使用者要 prompt / handoff：立即停手產出
- cm / git / cloud CLI auth error：自己 retry 1-2 次再判斷
