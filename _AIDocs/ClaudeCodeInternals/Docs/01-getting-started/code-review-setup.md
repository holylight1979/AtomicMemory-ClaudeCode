<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-setup | lastmod: 2026-10-20 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-setup（官方 zh-TW，lastmod 2026-10-20）｜分類：Getting started › Code review and pull requests｜EN 摘要：Turn on Code Review for your Claude organization: connect GitHub, install the Claude GitHub App, choose repositories, and set when reviews run

# 設定 Code Review

> 為您的 Claude 組織啟用 Code Review：連接 GitHub、安裝 Claude GitHub App、選擇儲存庫，並設定審查的執行時機

身為 Claude 組織的 Owner，您可以在 claude.ai 的 [**Admin settings > Claude Code**](https://claude.ai/admin-settings/claude-code#code-review) 中啟用 Code Review。審查在 Anthropic 的基礎架構上執行，因此無需在儲存庫中新增工作流程檔案。

設定完成後，您可以為每個儲存庫選擇審查的詳盡程度以及執行時機。審查等級越高、審查執行越頻繁，花費就越多。請參閱 [Code Review 費用](https://code.claude.com/docs/zh-TW/code-review-costs.md#pricing)。

## 啟用 Code Review 所需條件

首先確認您的組織[符合 Code Review 的使用資格](https://code.claude.com/docs/zh-TW/code-review.md#availability)。接著確認您本身具備以下存取權，或有具備這些存取權的人員協助：

| 存取權 | 用途 |
| :- | :- |
| 在 Claude 組織中擁有 [Owner 角色](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control) | 管理頁面上的每個步驟 |
| GitHub 組織的 owner | 安裝 Claude GitHub App 並[將其連結至您的 Claude 組織](https://code.claude.com/docs/zh-TW/admin-setup.md#connected-github-accounts)。如果您不是 owner，請在開始之前請一位 owner 安裝並連結此應用程式 |
| 您連接至 Claude 的 GitHub 帳戶對每個要新增的儲存庫具有寫入存取權 | 新增儲存庫 |

## 啟用 Code Review

**1. 點選 Allow code review 開關**

前往 [**Admin settings > Claude Code**](https://claude.ai/admin-settings/claude-code#code-review) 的 **Code review** 區段，然後點選 **Allow code review** 開關。

如果 Code Review 立即啟用且未出現任何對話方塊，表示您的組織已連結 Claude GitHub App 或已新增儲存庫。請前往[新增更多儲存庫](#add-more-repositories)，再回來執行最後一個步驟。

**2. 連接您的 GitHub 帳戶**

如果開啟了 **Connect GitHub** 對話方塊，請點選 **Connect**。如果您的組織使用 GitHub Enterprise Server，請先在對話方塊中選擇您的執行個體。GitHub 會要求您授權 Claude，然後將您帶回管理頁面，並開啟 **Add a repository** 對話方塊。

如果直接開啟了 **Add a repository**，表示您的帳戶已連接，請繼續下一個步驟。

**3. 安裝 Claude GitHub App**

如果您想要的儲存庫已列在 **Add a repository** 對話方塊中，或可在其中搜尋到，請繼續下一個步驟。對話方塊只會列出 Claude GitHub App 可存取的儲存庫，因此如果找不到，請安裝此應用程式：

* 點選 **Install GitHub App**。若未列出任何儲存庫，它會是對話方塊中的一個按鈕；否則，它位於對話方塊中 GitHub 組織篩選選單的底部。GitHub 的安裝頁面會在新分頁中開啟。
* 選擇擁有這些儲存庫的 GitHub 組織。
* 選擇應用程式可存取的儲存庫。
* 核准所要求的權限。這組權限的範圍比審查實際使用的更廣，並與其他 Claude 功能共用，例如 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md)。請參閱[審查可存取的內容](https://code.claude.com/docs/zh-TW/code-review.md#what-a-review-can-access)以及[完整權限清單](https://code.claude.com/docs/zh-TW/github-actions.md#github-app-permissions)。
* 安裝完成後，該分頁會返回 Claude。如果顯示 **Finish connecting GitHub** 按鈕，請點選它，將此安裝連結至您的 Claude 組織。
* 回到管理頁面的分頁，對話方塊中的清單會重新整理。

**4. 選擇儲存庫**

選擇您要進行審查的儲存庫，然後點選 **Continue**。新增儲存庫需要您所連接的 GitHub 帳戶對該儲存庫具有寫入存取權。您之後可以[新增更多儲存庫](#add-more-repositories)。

**5. 點選 Finish**

接著會出現 **Code review is set up** 對話方塊。點選 **Finish** 即可啟用 Code Review。如果以其他方式關閉此對話方塊，您的儲存庫仍會保持已新增狀態，但 **Allow code review** 會維持關閉，您需要透過該開關將其開啟。

每個儲存庫一開始都設定為在每次推送後進行審查，這會執行最多次審查。若要減少審查次數，請[設定審查的執行時機](#set-when-reviews-run)。

**6. 以測試 pull request 驗證**

在您新增的其中一個儲存庫中開啟一個測試 pull request，且不要將其標示為草稿。幾分鐘內會出現名為 **Claude Code Review** 的 check run。如果您已將該儲存庫設定為 **Manual (@claude review)**，請在 pull request 上留言 `@claude review` 以啟動第一次審查。

如果沒有出現 check run，請參閱 [No check run appears on the test pull request](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#no-check-run-appears-on-the-test-pull-request)。

審查結果出現後，請將[在 pull request 上閱讀及請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md)提供給您的開發人員，其中涵蓋嚴重程度等級、留言命令，以及如何回應審查發現。

## 為您的組織設定預設值

身為 Owner，您可以決定審查的詳盡程度及執行頻率。這兩項都位於 [**Admin settings > Claude Code**](https://claude.ai/admin-settings/claude-code#code-review) 的 **Code review** 區段中。

### 設定預設審查等級

審查等級決定每次審查的詳盡程度，越詳盡的審查費用越高。您可以為組織設定一個預設值，並針對個別儲存庫進行覆寫。

| 等級 | 取捨 |
| :- | :- |
| Quick | 較輕量的檢查。最快的等級，費用最低 |
| Standard | 在深度、速度與費用之間取得平衡。預設等級 |
| Deep | 最詳盡的檢查。耗時最長，費用最高 |

* **組織預設值**：在 **Review level** 下選擇一個等級，並以 **Change level** 確認。除非您為某個儲存庫另行設定，否則所有儲存庫都會使用此等級。
* **單一儲存庫**：點選該儲存庫所在列的 **Edit**，然後在其中選擇 **Review level**。第一個選項 **Default** 會沿用組織設定。選擇後等級會立即儲存。

新的等級會套用於變更後開始的審查。關於其他影響每次審查費用的因素，請參閱 [Code Review 費用與使用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)。

### 設定審查的執行時機

每個儲存庫都有各自的 **Review runs** 設定，用於決定其 pull request 何時接受審查。

* **Once after PR creation**：當 pull request 被開啟、重新開啟或標示為可供審查時，執行一次審查
* **After every push**：每次推送至 pull request 分支時執行審查，隨著 pull request 的演進發現新問題，並在您修正所指出的問題時自動解決討論串
* **Manual (@claude review)**：開啟 pull request 或推送至 pull request 不會啟動審查。留言 [`@claude review`](https://code.claude.com/docs/zh-TW/code-review-pull-requests#comment-commands) 以請求審查，或留言 `@claude review always`，讓該 pull request 在後續推送時也會接受審查。

Manual 適用於流量大的儲存庫，讓您選擇特定 pull request 進行審查，或僅在 pull request 準備就緒時才開始審查。若要比較各選項對花費的影響，請參閱[審查的執行頻率](https://code.claude.com/docs/zh-TW/code-review-costs.md#how-often-reviews-run)。

若要變更此設定，請在 **Repositories** 表格中點選該儲存庫所在列的 **Edit**，然後選擇一個 **Review runs** 選項。選擇後會立即儲存，表格的 **Review runs** 欄位會以簡短形式顯示為 Once per PR、Every push 或 Manual。

* **草稿及來自 fork 的 pull request**：無論您選擇哪個選項，[自動審查都會略過這兩者](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks)
* **新儲存庫**：從 **Add a repository** 對話方塊新增的儲存庫一開始設定為 **After every push**。如果其 GitHub 組織已[整體涵蓋](#cover-a-whole-github-organization)，則會改為採用該組織列的設定。

### 開啟或關閉提示留言

提示留言是當審查未啟動時，Claude 在 pull request 上發布的簡短留言，說明原因及後續步驟。**Show tips on pull requests** 預設為開啟。開啟時，Claude 會在下列各情況發布提示，說明：

* **儲存庫設定為 Manual**：如何透過留言請求審查
* **pull request 來自 fork**：維護者可以請求審查
* **機器人，或沒有寫入存取權且並非該 pull request 作者的人留言 `@claude review`**：未啟動審查，以及誰可以請求審查
* **GitHub 組織未連結至您的 Claude 組織**：審查已暫停，以及如何進行連結

關閉此設定即可停止這些留言。

### 開發人員可以變更的項目

開發人員若要變更審查等級、**Review runs** 設定，或哪些儲存庫接受審查，需要向您提出。在沒有 Owner 角色的情況下，他們可以在 GitHub 上執行以下操作：

* **請求審查**：在 pull request 上留言 [`@claude review`](https://code.claude.com/docs/zh-TW/code-review-pull-requests#comment-commands)。這需要對該儲存庫具有寫入存取權，且適用於自動審查會略過的[草稿及來自 fork 的 pull request](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks)。
* **讓單一 pull request 在每次推送時接受審查**：在[既非草稿也非來自 fork](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#review-drafts-and-pull-requests-from-forks) 的 pull request 上留言 `@claude review always`，例如在設定為 Manual 的儲存庫中
* **變更審查所指出的問題**：將 [`REVIEW.md` 和 `CLAUDE.md` 檔案](https://code.claude.com/docs/zh-TW/code-review-customize)提交至儲存庫，例如新增一項檢查

開發人員所請求的審查會[向您的組織計費](https://code.claude.com/docs/zh-TW/code-review-costs.md#pricing)。若要限制 Code Review 每月的花費，請參閱[限制您的花費](https://code.claude.com/docs/zh-TW/code-review-costs.md#limit-your-spend)。

## 管理儲存庫

您可以逐一新增儲存庫，或一次涵蓋整個 GitHub 組織，並在不需要審查的地方停止審查。

### 新增更多儲存庫

若要在設定完成後新增儲存庫，請點選 **Code review** 區段中 **Repositories** 表格上方的 **Add**。**Add a repository** 對話方塊會開啟。選擇儲存庫並點選 **Continue**。

* **某個儲存庫未列出**：請參閱 [A repository isn't listed in Add a repository](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#a-repository-isn’t-listed-in-add-a-repository)。
* **您想要 GitHub 組織中的所有儲存庫**：請[涵蓋該組織](#cover-a-whole-github-organization)，而非逐一選擇儲存庫

### 涵蓋整個 GitHub 組織

若要為 GitHub 組織中的所有儲存庫啟用 Code Review，請在 **Repositories** 表格中該組織所在的列設定 **Review runs**。這會涵蓋該組織中 Claude GitHub App 可存取的所有儲存庫，包括之後新增的儲存庫。這可能會大幅增加花費。需要滿足以下所有條件：

* 您連接至 Claude 的 GitHub 帳戶是該 GitHub 組織的 owner。
* 該組織位於 github.com 上。GitHub Enterprise Server 執行個體及個人 GitHub 帳戶不符合資格。
* 已為您的 Claude 組織或 Code Review 設定[每月花費上限](https://code.claude.com/docs/zh-TW/code-review-costs.md#limit-your-spend)。

若要涵蓋該組織，請點選其所在列的 **Edit**，選擇一個 **Review runs** 選項並確認。選項包括[設定審查的執行時機](#set-when-reviews-run)中的三個選項，再加上 **Off**。

確認後，以下變更會生效：

* **涵蓋範圍**：每個儲存庫會從其下一個 pull request 開始受到涵蓋。如果 Claude GitHub App 是安裝在選定的儲存庫而非全部儲存庫上，Claude 會審查那些儲存庫；請在 GitHub 上變更應用程式的儲存庫存取權以涵蓋其餘儲存庫。
* **現有設定**：該 GitHub 組織中的每個儲存庫都會採用您選擇的選項，包括您先前個別設定的儲存庫。再次設定該列也會產生相同效果。您在其各自所在列上關閉的儲存庫會維持關閉。
* **之後的個別變更**：您之後設定為與其組織不同的儲存庫，會在表格中標示為 **Custom**。
* **審查等級**：組織列本身沒有審查等級。

### 關閉 Code Review 或移除儲存庫

在 [**Admin settings > Claude Code**](https://claude.ai/admin-settings/claude-code#code-review) 的 **Code review** 區段中，選擇與您要停止的項目相符的控制項：

* **單一儲存庫，保留在清單中**：點選其所在列的 **Edit**，然後關閉 **Code review**。表格會將該儲存庫顯示為 Off。
* **單一儲存庫，將其移除**：點選其所在列的 **Edit**，然後點選對話方塊底部的 **Remove repository**。該儲存庫的審查會停止，之後其他 Claude 組織便可以設定該儲存庫。當該儲存庫的 GitHub 組織被整體涵蓋時，您無法將其移除；請改為關閉其 **Code review** 開關。
* **整個 GitHub 組織**：點選該組織所在列的 **Edit**，然後選擇 **Off**。這也會關閉該組織中您逐一新增的儲存庫。
* **全部**：關閉 **Allow code review**。所有儲存庫都不會再啟動新的審查，而您的儲存庫清單會保留，以便您之後重新開啟。

## 相關資源

* [Code Review 費用與使用量](https://code.claude.com/docs/zh-TW/code-review-costs.md)：審查等級及審查執行時機如何影響花費、如何設定花費上限，以及在哪裡查看使用量
* [在 pull request 上閱讀及請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md)：開發人員在 pull request 上看到的內容及留言命令
* [自訂 Code Review](https://code.claude.com/docs/zh-TW/code-review-customize.md)：使用 `REVIEW.md` 和 `CLAUDE.md` 調整 Claude 所指出的問題
* [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md)：在設定之前連接自行託管的 GitHub 執行個體
