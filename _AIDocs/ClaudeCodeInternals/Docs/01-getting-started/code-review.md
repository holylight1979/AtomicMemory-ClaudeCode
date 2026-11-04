<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review | lastmod: 2026-10-24 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review（官方 zh-TW，lastmod 2026-10-24）｜分類：Getting started › Code review and pull requests｜EN 摘要：Catch bugs in GitHub pull requests with Code Review: Claude reviews each change, verifies its findings, and comments inline. For Team and Enterprise plans

# Code Review

> 使用 Code Review 捕捉 GitHub pull request 中的錯誤：Claude 審查每項變更、驗證其發現結果，並發佈內聯評論。適用於 Team 和 Enterprise 方案

透過 Code Review，Claude 會審查您 GitHub 儲存庫中的 pull request。多個 agent 會連同周圍程式碼一起閱讀每項變更，尋找邏輯錯誤、安全漏洞或破損的邊界情況等問題。驗證步驟會在回報發現結果之前，根據程式碼檢查這些發現結果。

發現結果會以內聯評論的形式出現在相關的程式碼行上，並按[嚴重程度](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#severity-levels)排名，同時在 pull request 上提供摘要和檢查執行。審查永遠不會批准或阻止 pull request，因此是否合併的決定仍由您的團隊掌握。

![四個階段審查的圖表。GitHub 上的 pull request 會交給多個在 Anthropic 基礎設施上並行搜尋的 agent。驗證步驟會移除誤判，其餘發現結果經過去重並按嚴重程度排名，審查會將內聯評論、摘要和檢查執行發佈回 GitHub。](https://mintcdn.com/claude-code/gLJVaPQEgKC8ZyUD/images/code-review-pipeline.svg?fit=max\&auto=format\&n=gLJVaPQEgKC8ZyUD\&q=85\&s=0351c96df9efa3105172eb00a672f130)

> [!NOTE]
>
> Code Review 使用 AI 審查程式碼，可能會遺漏錯誤、安全漏洞或其他問題。沒有發現結果的審查並不代表您的程式碼沒有錯誤或是安全的。

若要啟用 Code Review，您 Claude 組織的擁有者需依照[設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md) 操作。Claude 也可以在不使用此服務的情況下審查程式碼。在任何方案上，於您的 Claude Code 工作階段中執行 [`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local)，或[比較所有選項](#compare-ways-to-get-a-review)。

## 可用性

在設定 Code Review 之前，請確認您的組織符合資格：

* **方案**：[Team 和 Enterprise](https://code.claude.com/docs/zh-TW/feature-availability.md)
* **程式碼託管**：託管於 GitHub 的儲存庫，包括 [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md) 以及具備資料落地功能的 GitHub Enterprise Cloud。若要使用資料落地，請由擁有者依照 [GitHub Enterprise Server 管理員設定](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#admin-setup)操作，並輸入您企業的 `ghe.com` 主機名稱。
* **資料保留**：對於啟用了 [Zero Data Retention](https://code.claude.com/docs/zh-TW/zero-data-retention.md) 或套用了 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織，Code Review 不可用，且不在 Anthropic 的商業夥伴協議（BAA）涵蓋範圍內。
* **加密金鑰**：Code Review 目前尚不適用於使用客戶管理加密金鑰（CMEK）的組織。
* **雲端供應商**：即使您的開發人員透過 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 使用 Claude Code，您仍需要一個使用上述方案之一的 Claude 組織

## 設定及使用 Code Review

請依您需要完成的事項選擇頁面：

> [card] [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)
>
> 檢查需求、安裝 Claude GitHub App，並選擇儲存庫、審查等級以及審查執行的時機

> [card] [自訂 Code Review](https://code.claude.com/docs/zh-TW/code-review-customize.md)
>
> 使用儲存庫中的 `REVIEW.md` 和 `CLAUDE.md` 檔案調整要標記的內容

> [card] [在 pull request 上閱讀及請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md)
>
> 閱讀發現結果及其嚴重程度，並透過評論請求另一次審查

> [card] [Code Review 疑難排解](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md)
>
> 修正未啟動、失敗或因預算而略過的審查

> [card] [Code Review 成本與使用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)
>
> 了解審查的計費方式、估算支出、設定每月支出上限，並追蹤審查活動

## 審查的運作方式

預設情況下，Code Review 專注於正確性：會破壞生產環境的錯誤，而不是格式偏好或缺少的測試涵蓋範圍。若要變更它標記的內容，請[新增指導檔案](https://code.claude.com/docs/zh-TW/code-review-customize.md)到您的儲存庫。

審查在 Anthropic 基礎設施上分四個階段執行：

1. **尋找**：多個 agent 並行檢查差異和周圍程式碼。
2. **驗證**：驗證步驟根據程式碼檢查候選發現結果，並過濾掉誤判。
3. **排名**：剩餘的發現結果經過去重並按嚴重程度排名。
4. **發佈**：審查將其結果發佈到 pull request 上。

每次審查會在 pull request 上留下以下內容：

* **發現結果**：相關程式碼行上的內聯評論，並在審查正文中提供摘要
* **檢查執行**：名為 **Claude Code Review**，其[詳細資訊](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#check-run-output)中列出發現結果。檢查執行不會以失敗作結。
* **取代發現結果的說明**：當檢查執行的標題顯示為 **Code review found no issues** 時發佈

Code Review 會選擇審查所執行的 Claude 模型，其管理設定不提供模型選擇。若要讓審查更徹底或更精簡，請變更[審查等級](#review-levels)。

擁有者啟用 Code Review 後，每個儲存庫都有一項設定決定[審查執行的時機](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-when-reviews-run)：在 pull request 開啟時執行一次、每次推送後執行，或僅在請求時執行。無論設定為何，對儲存庫具有寫入權限的人都可以在 pull request 上評論 `@claude review` 來[啟動審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#comment-commands)。

### 審查等級

審查等級決定每次審查的徹底程度，越徹底的審查成本越高：

* **Quick**：較輕量的檢查。速度最快、成本最低的等級。
* **Standard**：在深度、速度和成本之間取得平衡。預設等級。
* **Deep**：最徹底的檢查。耗時最長、成本最高。

擁有者可以[為組織選擇一個等級](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-the-default-review-level)，並可為個別儲存庫指定自己的等級，例如為例行的程式碼庫使用 Quick，為關鍵的程式碼庫使用 Deep。關於影響每次審查成本的其他因素，請參閱 [Code Review 成本與使用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)。

### 審查可以存取的內容

審查透過擁有者[在設定期間安裝](https://code.claude.com/docs/zh-TW/code-review-setup.md#turn-on-code-review)的 Claude GitHub App 存取您的儲存庫：

* **執行位置**：在 Anthropic 基礎設施上的受管理環境中。審查不會在[自行託管的環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中執行。
* **讀取和寫入的內容**：在審查中，對您儲存庫的存取是唯讀的，審查不會推送提交。在 pull request 上，它會發佈評論和[檢查執行](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#check-run-output)、解決自己先前的評論執行緒，並可以用 👀 回應評論命令。應用程式本身擁有由其他 Claude 功能共享的[更廣泛權限集](https://code.claude.com/docs/zh-TW/github-actions.md#github-app-permissions)。
* **檢查程式碼的方式**：審查透過閱讀差異和周圍程式碼進行，不會建置或執行您的程式碼。

### 誰控制審查

* **誰可以啟動審查**：在自動執行審查的情況下，開啟 pull request 或推送到 pull request 會啟動審查，[草稿和分叉除外](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks)。在某些推送之後，Code Review 會改為[保留先前的結果](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#when-a-push-keeps-the-earlier-result)。[評論命令](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#comment-commands)僅在來自對儲存庫具有寫入權限的人時才會啟動審查。
* **遵循哪些指示**：來自基礎分支或預設分支的 `REVIEW.md`，[絕不會來自 pull request 本身的變更](https://code.claude.com/docs/zh-TW/code-review-customize.md#which-branch-review-md-is-read-from)。

## 比較取得審查的方式

若要找出您可使用的選項，請對照您的方案和程式碼託管檢查**誰可以使用**欄位：

| 選項 | 啟動審查的方式 | 執行位置 | 誰可以使用 |
| :- | :- | :- | :- |
| [Code Review](#how-reviews-work) | 依各儲存庫設定的 pull request 活動，或 `@claude review` 評論 | Anthropic 基礎設施 | 使用 Team 或 Enterprise 方案且擁有 GitHub 儲存庫的組織，需由擁有者啟用 |
| [`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) | 您在分支上執行命令 | 您的 Claude Code 工作階段 | 任何人，任何方案 |
| [Ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md) | 您從 Claude Code 啟動 | 雲端沙箱 | 需要使用 claude.ai 帳戶登入。關於無法使用的情況，請參閱 [Ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md) |
| 在您自己的 CI 中使用 Claude，搭配 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 或 [GitLab CI/CD](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md) | 您管道的事件，例如每個 pull request 或 merge request | 您自己的 CI 執行器 | 在 GitHub 或 GitLab 上擁有 Claude API 金鑰或雲端供應商憑證的任何人 |
| 您自己的審查者，作為 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 或 [skill](https://code.claude.com/docs/zh-TW/skills.md) | 您或 Claude 在工作階段中叫用它 | 您執行 Claude Code 的任何位置 | 任何自行撰寫的人 |

## 相關資源

* [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md)：在自行託管的 GitHub 執行個體上使用 Code Review
* [GitHub App 權限](https://code.claude.com/docs/zh-TW/github-actions.md#github-app-permissions)：Claude GitHub App 請求的完整權限集
* [How Anthropic secures its AI-native software development lifecycle](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle)：自動化審查如何作為 Anthropic 安全開發流程的一層
