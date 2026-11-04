<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-troubleshooting | lastmod: 2026-10-24 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-troubleshooting（官方 zh-TW，lastmod 2026-10-24）｜分類：Getting started › Code review and pull requests｜EN 摘要：Fix a Code Review that didn't start, failed, or was skipped for budget, find missing findings, and resolve setup and `REVIEW.md` problems.

# Code Review 疑難排解

> 修正未啟動、失敗或因預算而略過的 Code Review，找出遺漏的發現，並解決設定與 `REVIEW.md` 相關問題。

當 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) 在 pull request 上未如預期運作時，請先查看 **Claude Code Review** check run。其標題會說明審查進行到哪個階段。

## 檢查審查進行到哪個階段

在 pull request 上找到 **Claude Code Review** check run，然後將其標題與下列常見標題進行比對：

| Check run 標題 | 代表意義 | 處理方式 |
| :- | :- | :- |
| **Code review queued...** 或 **Code review in progress...** | 審查尚未完成 | 等待標題變更 |
| **Code review found no issues** | 審查已完成，且未發布任何發現 | 若這不是該 pull request 的第一次審查，請在審查內文中查看[審查略過的發現](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#what-a-later-review-covers)數量。否則無需處理 |
| 表示發現問題的標題 | 審查已完成並有發現 | 若在差異中看不到這些發現，請參閱[找出未顯示為行內留言的問題](#find-issues-that-aren’t-showing-as-inline-comments) |
| **Code review skipped — no new changes** | 最新一次推送未執行自動審查 | 若仍想取得審查，請留言 `@claude review` |
| **Code review not repeated — earlier findings still open** | 最新一次推送未執行自動審查，且先前審查中的 Important 發現仍未解決 | 推送修正，或若仍想取得審查，請留言 `@claude review`。請參閱[推送保留先前結果的情況](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#when-a-push-keeps-the-earlier-result) |
| **Code review failed** 或 **Code review timed out** | 審查未完成 | 若要重新執行，請參閱[重新觸發失敗或逾時的審查](#retrigger-a-failed-or-timed-out-review) |
| **Code review declined** | 審查未執行 | 閱讀 check run 的摘要。若其中提及預算或支出上限，請參閱[審查未執行且 PR 顯示預算訊息](#review-didn’t-run-and-the-pr-shows-a-budget-message) |
| 沒有 check run | 審查未啟動 | 留言 `@claude review`。若之後仍未出現 check run，請參閱[留言命令未啟動審查](#a-comment-command-didn’t-start-a-review) |

## 審查未啟動

當未出現 **Claude Code Review** check run，或 Claude 發布留言表示審查已略過時，請檢查下列情況。

### 留言命令未啟動審查

留言 `@claude review` 之後，請在 pull request 上尋找標題為 **Code review queued...** 或 **Code review in progress...** 的 **Claude Code Review** check run。留言上出現 👀 反應並不代表審查即將進行。若未出現 check run，請逐一檢查下列原因：

* **此儲存庫未啟用 Code Review**：Claude 不會針對該命令發布任何留言或 check run。請聯絡 Owner [新增此儲存庫](https://code.claude.com/docs/zh-TW/code-review-setup.md#add-more-repositories)。
* **留言不符合條件**：該留言是行內留言或審查內文，而非新的頂層留言，或命令未位於留言開頭。編輯先前的留言而非發布新留言同樣不算數，且 pull request 必須處於開啟狀態。請參閱[留言命令的條件](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#comment-commands)，並發布符合條件的新留言。
* **您沒有寫入權限**：您需要具備儲存庫的 write、maintain 或 admin 權限；若是來自 fork 的 pull request，則以基底儲存庫上的權限為準。除非該 pull request 是您自己的，否則 Claude 可能會以[提示](https://code.claude.com/docs/zh-TW/code-review-setup.md#turn-tip-comments-on-or-off)回覆：「No review was started: manual reviews can only be requested by someone with write access to this repository.」請改由具有寫入權限的人員留言。
* **預算已用盡**：Claude 會發布以「⚠️ Code review skipped」開頭的留言。請參閱[審查未執行且 PR 顯示預算訊息](#review-didn’t-run-and-the-pr-shows-a-budget-message)。

### 審查未執行且 PR 顯示預算訊息

當組織的預算不足以支付一次審查時，Code Review 會略過該審查，而 Claude 會在 pull request 上發布以「⚠️ Code review skipped」開頭的留言。在其中部分情況下，也會出現標題為 **Code review declined** 的 check run。

該留言會連結至 [claude.ai/admin-settings/usage](https://claude.ai/admin-settings/usage)，管理員可在此恢復預算。留言的措辭會說明達到的是哪一項上限：

* **「has reached its monthly code review spending cap」**：已達到 [Code Review 的每月支出上限](https://code.claude.com/docs/zh-TW/code-review-costs.md#limit-your-spend)。審查將於下一個計費週期開始時恢復。若要提早恢復，請聯絡管理員提高上限。
* **「has no extra usage available to pay for this review」**：組織的[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)餘額已用完，或已達到其整體每月支出上限。請聯絡管理員加購用量點數或提高該上限。
* **「is too low to start another review」**：剩餘的預算或餘額低於一次審查的預估費用。請聯絡管理員提高上限或加購用量點數。

恢復預算後，請在 pull request 上留言 `@claude review`，以取得先前被略過的審查。此時適用[留言命令的條件](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#comment-commands)，因此留言者需要具備寫入權限。

## 重新觸發失敗或逾時的審查

若 check run 的摘要顯示「The review session was interrupted before it could finish. A new review of this commit has been queued automatically.」，則您無需採取任何動作。該審查會自動重試一次。

否則，當 check run 的標題為 **Code review failed** 或 **Code review timed out** 時，請透過留言或重新執行再次進行審查：

* **留言 `@claude review`**：在 pull request 上以頂層留言的方式發布。這會啟動一次全新的審查，且不會讓 pull request 訂閱之後的推送。
* **點擊 Re-run**：若 pull request 並非[來自 fork](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks)，請在 GitHub 的 **Checks** 分頁中，點擊 **Claude Code Review** 檢查上的 **Re-run**。重新執行會涵蓋 pull request 目前的 head 提交，同樣不會讓 pull request 訂閱之後的推送。

## 找出未顯示為行內留言的問題

若 check run 標題表示已發現問題，但您在差異中看不到行內審查留言，請查看下列其他顯示發現的位置：

* **Check run Details**：在 **Checks** 分頁中，點擊 **Claude Code Review** 檢查旁的 **Details**。嚴重程度表格會列出各項發現及其檔案、行號與摘要，無論行內留言是否被接受皆會列出。
* **Files changed 註解**：開啟 PR 上的 **Files changed** 分頁。具有行號但未以行內留言發布的發現，會以註解的形式顯示在相關行上。
* **審查內文**：沒有行內位置，或位於目前差異範圍之外的發現，會顯示在審查內文中的 **Additional findings** 標題下。

## Check run 提及 REVIEW\.md

以下是 check run 中可能出現的四則 `REVIEW.md` 相關訊息：

* **「This review applied the repository's review instructions (REVIEW\.md) from its default branch, which is not protected against direct pushes.」**：此審查僅讀取了根目錄的檔案。關於保護分支會帶來哪些改變，請參閱[從哪個分支讀取 REVIEW.md](https://code.claude.com/docs/zh-TW/code-review-customize.md#which-branch-review-md-is-read-from)。
* **「were not applied to this review: branch protection could not be confirmed」**：此審查未讀取任何 `REVIEW.md`。
* **「they link to a file this pull request modifies, or carry more links than the review checks」**：此審查略過了根目錄的 `REVIEW.md`，或略過了訊息中所列數量的子目錄 `REVIEW.md` 檔案。請針對每個原因檢查被略過的檔案。若是根目錄的 `REVIEW.md`，也請檢查[它所引入的檔案](https://code.claude.com/docs/zh-TW/code-review-customize.md#include-other-files-in-review-md)：
  * **連結過多**：檔案中含有超過 64 個 Markdown 連結。請將連結減少至 [64 個或更少](https://code.claude.com/docs/zh-TW/code-review-customize.md#include-other-files-in-review-md)。
  * **審查無法解析的連結**：檔案中有格式錯誤的 Markdown 連結。請修正或移除該連結。
  * **指向已變更檔案的連結**：檔案連結至此 pull request 所變更的檔案或資料夾，且審查無法僅排除含有該連結的那幾行。請直接在 `REVIEW.md` 中撰寫該規則。
* **「include line(s) in the root REVIEW\.md were skipped on this review」**：您的根目錄 `REVIEW.md` 已套用，但這些行所指定的檔案並未套用。請查看[在 REVIEW.md 中引入其他檔案](https://code.claude.com/docs/zh-TW/code-review-customize.md#include-other-files-in-review-md)下的清單，若為 skill，另請查看[引入 skill 檔案](https://code.claude.com/docs/zh-TW/code-review-customize.md#include-a-skill-file)下的清單。

## 設定問題

這些情況會在 Owner [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md) 時發生。

### 儲存庫未列在 Add a repository 中

請先依名稱搜尋儲存庫，因為該對話方塊不會完整載入過長的清單。只有 Claude GitHub App 能夠存取的儲存庫才會列在對話方塊中。請點擊 **Install GitHub App**，並授予該應用程式存取此儲存庫的權限。當未列出任何儲存庫時，**Install GitHub App** 會是對話方塊中的一個按鈕；否則，它位於對話方塊中 GitHub 組織篩選選單的底部。

### 測試用的 pull request 上未出現 check run

請確認 **Allow code review** 已開啟、該儲存庫已列在 **Code review** 區段的 **Repositories** 下，且 Claude GitHub App 具有存取該儲存庫的權限。自動審查會略過草稿 pull request，而設為 **Manual (@claude review)** 的儲存庫則需要留言 `@claude review` 才會啟動第一次審查。

## 相關資源

* [在 pull request 上閱讀與請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md)：發現與 check run 的意義，以及留言命令
* [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)：供 Owner 使用，啟用 Code Review 並管理儲存庫
* [Code Review 費用與用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)：預算訊息背後的支出上限
* [自訂 Code Review](https://code.claude.com/docs/zh-TW/code-review-customize.md)：審查會讀取哪一份 `REVIEW.md`
