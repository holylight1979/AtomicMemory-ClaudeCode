# feedback-precedent-drift-excuse

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: precedent, 前例, 比照前面, 既有 drift, pre-existing, 範圍外, 延後, dist 沒 commit, 退避
- Created-at: 2026-05-19
- Related: workflow-rules, feedback-clean-before-build

## 知識

- [臨] 引用『前一個 phase/commit 沒做 X，所以這次也不做 X』當作不修的理由前，必須先 git log/show 查證那個前例本身是有意決策還是疏漏——若是疏漏，比照它＝把別人疏漏替自己縮限背書，正中反退避契約『既有 drift』禁語。
- [臨] LineMate session 同型錯犯兩次：(1) PersonaComposer Path.Combine 想『另開 session』被使用者否決；(2) dist 二進位以『Phase 1/2 沒收 dist』為 precedent 不提交，查證後 dist 是 da7c68c 刻意納版控、Phase 1/2 未更新本身就是遺留 drift。兩次都是使用者主動點破。
- [臨] 手上已有正確產物（如已 clean publish 的 dist）且追蹤中檔案過時 → 當場補，不援引前例延後；宣告完成前自問是否用 precedent/範圍外/既有 drift 包裝偷懶。

## 行動

- 要說『比照前例所以不做』前，先 git log/show 查證該前例是有意決策還是疏漏
- 手上已有正確產物且追蹤中檔案過時 → 當場補提交
- 宣告完成前自問：有沒有用 precedent/範圍外/既有 drift 包裝偷懶
