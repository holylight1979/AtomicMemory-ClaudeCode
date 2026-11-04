<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-costs | lastmod: 2026-10-29 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-costs（官方 zh-TW，lastmod 2026-10-29）｜分類：Getting started › Code review and pull requests｜EN 摘要：Estimate and cap what your organization spends on Claude Code Review: how reviews are billed through usage credits, what drives cost, and where to track usage.

# Code Review 費用與用量

> 估算並限制您的組織在 Claude Code Review 上的支出：審查如何透過用量點數計費、哪些因素影響費用，以及在何處追蹤用量。

[Code Review](https://code.claude.com/docs/zh-TW/code-review.md) 沒有固定的單次審查價格。您的支出取決於每次審查的費用以及執行的審查次數：

* **每次審查的費用**：隨[審查等級](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-the-default-review-level)、變更的大小、周邊程式碼的複雜度，以及需要驗證的候選問題數量而增減
* **審查次數**：由每個儲存庫中[審查的執行頻率](#how-often-reviews-run)決定

## 定價

Code Review 依 token 用量透過[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)計費，與您方案內含的用量分開計算。審查費用會計入您的組織，而非開啟 PR 或請求審查的開發人員。無論您的組織是否將 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 用於其他 Claude Code 功能，費用都會出現在您的 Anthropic 帳單上。

### 審查的執行頻率

從管理頁面新增的儲存庫預設為 **After every push**，此設定執行的審查次數最多。每個儲存庫的 [**Review runs** 設定](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-when-reviews-run)決定一個 pull request 會進行多少次審查：

* **Once after PR creation**：在 pull request 開啟、重新開啟或標記為可供審查時執行一次審查
* **After every push**：每次推送時執行，費用會乘以推送次數
* **Manual (@claude review)**：開啟或推送時皆不執行審查

留言命令、草稿以及來自 fork 的 pull request 會調整這些次數：

* **在 Once after PR creation 或 Manual 模式下使用 `@claude review always`**：[讓該 PR 加入推送觸發的審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#comment-commands)，因此在該留言之後，每次推送都會產生額外費用
* **在 After every push 模式下使用 `@claude review always`**：推送本來就會觸發審查，因此此訂閱不會改變每次推送的費用
* **`@claude review`**：執行單次審查，不會訂閱未來的推送
* **草稿與來自 fork 的 pull request**：[自動審查會略過這兩者](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks)，因此對它們的推送不會增加審查次數

## 估算您的支出

在大規模推行之前，請先進行小規模試行，以根據您自己的 pull request 估算每月支出。

1. 為試行設定[每月支出上限](#limit-your-spend)。
2. 為幾個具代表性的儲存庫啟用 Code Review，並將 **Review runs** 設為 **Once after PR creation** 或 **Manual (@claude review)**。
3. 在執行數次審查後，前往 [**Admin settings > Claude Code**](https://claude.ai/admin-settings/claude-code#code-review) 的 **Code review** 區段，在 **Repositories** 表格的 **Average cost** 欄中查看每個儲存庫的平均單次審查費用。
4. 將該平均值乘以該儲存庫每月開啟的 pull request 數量。若使用 **After every push**，請再乘以每個 pull request 的一般推送次數。

儲存庫的平均值會隨其 pull request 的大小以及您選擇的審查等級而變動。

## 限制您的支出

若要為 Code Review 設定每月支出上限，請前往 [claude.ai/admin-settings/usage](https://claude.ai/admin-settings/usage)，並為 Claude Code Review 服務設定上限。此上限適用於整個組織。

當下列任一項用盡時，Code Review 會略過審查：

* **Code Review 支出上限**：您為 Claude Code Review 服務設定的每月上限。此上限會在下一個計費週期開始時重設；若您提高上限，審查會更早恢復。
* **組織支出上限**：您的組織在用量點數上的整體每月支出上限。可在同一頁面提高此上限。
* **用量點數餘額**：您的組織的用量點數餘額。可在同一頁面加值點數。

當剩餘額度少於單次審查的預期費用時，Code Review 也會略過審查。審查被略過時，開發人員會看到一則 [PR 上的留言](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#review-didn’t-run-and-the-pr-shows-a-budget-message)，其中會說明原因並附上用量設定的連結。

若要監控支出，請使用[分析儀表板](#view-usage)。

## 檢視用量

前往 [claude.ai/analytics/code-review](https://claude.ai/analytics/code-review) 查看整個組織的 Code Review 活動。

| 區段 | 顯示內容 |
| :- | :- |
| PRs reviewed | 所選時間範圍內每日審查的 pull request 數量 |
| Code Review cost | 本月至今的 Code Review 支出 |
| Feedback | 因開發人員已處理問題而自動解決的審查留言數量 |
| Code Review findings | 所選時間範圍內，Claude 已發布之審查中每日[依嚴重程度等級分類的發現項目](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#severity-levels)數量 |
| Repository breakdown | 各儲存庫已審查的 PR 數量、已解決的留言數量與審查執行次數，並附有估算費用與各 PR 檢視 |

只有在選取當月時，Code Review cost 卡片才會顯示金額。分析中的費用數字可能與您的帳單不同。Repository breakdown 的費用是以牌價估算，未計入任何折扣或點數，且僅涵蓋 Claude 已在 pull request 上發布的審查。如需與帳單一致的支出資訊，請參閱您的 Anthropic 帳單。

## 相關資源

* [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)：在此為每個儲存庫選擇審查等級與審查執行時機
* [在 pull request 上閱讀與請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md)：留言命令、來自 fork 的 pull request，以及審查被略過時開發人員看到的預算訊息
* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：審查會檢查哪些內容以及會發布哪些內容
* [有效管理費用](https://code.claude.com/docs/zh-TW/costs.md)：Claude Code 其他部分的支出控制與用量追蹤
