<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/security-guidance | lastmod: 2026-10-23 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/security-guidance（官方 zh-TW，lastmod 2026-10-23）｜分類：Getting started › Code review and pull requests｜EN 摘要：Install the security-guidance plugin to have Claude review its own code changes for vulnerabilities and fix them in the same session.

# 在 Claude 編寫程式碼時捕捉安全問題

> 安裝 security-guidance 外掛程式，讓 Claude 檢查自己的程式碼變更是否存在漏洞，並在同一個工作階段中修復它們。

security-guidance 外掛程式讓 Claude 在工作時檢查自己的程式碼變更是否存在常見漏洞，並在同一個工作階段中修復發現的問題。該外掛程式可以捕捉注入、不安全的反序列化和不安全的 DOM API 等問題，防止程式碼進入拉取請求，減少人工審查人員的安全審查負擔。

安裝後，外掛程式會自動執行。無需調用任何內容，也無需記住任何單獨的命令。

該外掛程式是 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) 的工作階段內伴侶，Code Review 在拉取請求上執行。此外掛程式減少了進入 PR 的內容。Code Review 捕捉遺漏的內容。有關外掛程式如何與按需審查和 CI 掃描分層的資訊，或掃描您已有的程式碼而非 Claude 正在編寫的變更，請參閱 [此功能如何與其他安全工具配合](#how-this-fits-with-other-security-tools)。

## 先決條件

* Python 3.7 或更高版本在您的 `PATH` 上。代理提交審查需要 Python 3.10 或更高版本，當 Claude Code 使用第三方提供者（例如 Amazon Bedrock 或 Google Cloud 的 Agent Platform）時，所有模型支援的審查也需要 Python 3.10 或更高版本。該外掛程式偏好版本化的直譯器 `python3.13` 到 `python3.10`，然後回退到 `python3`、`python` 和 `py -3`
* 您工作目錄的 git 儲存庫。端回合和提交審查會針對 git 狀態進行 diff，並在儲存庫外無聲跳過。每個編輯的模式檢查在任何地方都有效

首次執行時，外掛程式會在 `~/.claude/security/` 下建立虛擬環境，並將 Claude Agent SDK 安裝到其中，這需要 `pip` 和網路存取。如果該安裝失敗，或可用的 Python 版本早於 3.10，第一方驗證的提交審查會回退到單次審查而不是代理審查；在第三方提供者（例如 Amazon Bedrock 或 Google Cloud 的 Agent Platform）上，模型支援的審查需要 SDK 本身，因此會被跳過。當較舊的 Python 是原因時，外掛程式會顯示一次性通知。

## 安裝外掛程式

在終端機 Claude Code 工作階段中，從 [官方 Anthropic 市場](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md) 安裝：

```text theme={null}
/plugin install security-guidance@claude-plugins-official
```

`/plugin` 會開啟終端機 CLI 中的互動式面板。如果 Claude 回覆 `/plugin` 在此環境中不可用，請以其他方式安裝：

* **Claude 桌面應用程式、本機或 SSH 工作階段**：使用 [安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin) 下的 **Desktop app** 分頁
* **VS Code 擴充功能**：從 [**Manage plugins** 對話框](https://code.claude.com/docs/zh-TW/vs-code.md#manage-plugins) 安裝
* **雲端工作階段**：雲端工作階段不會從您的使用者設定或儲存庫的 `.claude/settings.json` 載入外掛程式，如 [您的設定中有哪些內容會保留](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup) 所說明。如需您的組織透過受管設定發佈的外掛程式，請參閱 [為您的組織管理外掛程式](https://code.claude.com/docs/zh-TW/plugins/org.md)

終端機安裝會提示輸入範圍。選擇使用者範圍以將外掛程式寫入您的使用者設定，這樣它會在您在此機器上啟動的每個新本地工作階段中載入。

如果安裝失敗，請比對 Claude Code 報告的訊息：

* `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市場，然後重試安裝。
* `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過時。請使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱 [Plugin not found in marketplace](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。

檢查安裝摘要。如果它報告 `Run /reload-plugins to apply.`，請參閱 [在不重新啟動的情況下套用外掛程式變更](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins) 以在您目前的工作階段中啟用外掛程式。

### 在本地工作階段中為您的團隊啟用

要在您的團隊成員在儲存庫中啟動的本地工作階段中開啟外掛程式，請在專案的簽入設定中聲明它：

```json .claude/settings.json theme={null}
{
  "enabledPlugins": {
    "security-guidance@claude-plugins-official": true
  }
}
```

管理員可以通過在 [受管設定](https://code.claude.com/docs/zh-TW/admin-setup.md) 中設定 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 來組織範圍內啟用外掛程式。

## 外掛程式檢查的內容

外掛程式在三個點檢查 Claude 的工作，每個點的深度不同：

* [在每個檔案編輯上](#on-each-file-edit)：快速模式匹配危險呼叫，無需模型呼叫
* [在每個回合結束時](#at-the-end-of-each-turn)：對該回合更改的所有內容進行背景模型審查
* [在 Claude 進行的每次提交或推送上](#on-each-commit-or-push-claude-makes)：讀取周圍程式碼的更深層代理審查

您可以通過 [添加自己的規則](#add-your-own-rules) 擴展每一層。內置檢查無法單獨移除，但您可以 [獨立禁用每一層](#disable-or-uninstall)。

### 每次檔案編輯時的檢查

當 Claude 寫入檔案時，外掛程式會掃描新內容中的已知危險模式。這是一個沒有模型呼叫的模式匹配，因此不會增加使用成本。

示例模式類別：

* 動態程式碼執行：`eval(`、`new Function`、`os.system`、`child_process.exec`
* 不安全的反序列化：`pickle`
* DOM 注入：`dangerouslySetInnerHTML`、`.innerHTML =`、`document.write`
* 工作流檔案：`.github/workflows/` 下的編輯，可以授予儲存庫級別的權限

檢查在編輯完成後執行，並將警告附加到 Claude 的下一步上下文中。每個警告在每個工作階段中每個檔案每個模式觸發一次，因此同一檔案中的重複匹配不會淹沒對話。

您可以使用 `security-patterns.yaml` 檔案 [添加自己的模式](#add-custom-per-edit-patterns) 到此層。

### 每個回合結束時的檢查

一個回合是 Claude 響應的一輪：您發送一條消息，Claude 工作並回覆，回合結束。在每個回合之後，外掛程式計算工作樹中在回合期間更改的所有內容的 git diff，包括來自 Claude 的編輯工具、Bash 命令和子代理的更改，並將其發送到專注於安全的單獨 Claude 審查。審查在背景中執行，因此 Claude 的回覆不會延遲。如果審查發現問題，Claude 會被重新提示發現的內容，並作為後續行動解決它們。

這捕捉了字符串匹配無法捕捉的問題，例如：

* 授權繞過
* 不安全的直接物件參考
* 注入
* 伺服器端請求偽造
* 弱密碼學

您可以直接在您的工作階段中看到發現和 Claude 的解決方案。審查涵蓋每個回合最多 30 個更改的檔案，並在最多連續三次後才讓位給您。

### Claude 每次提交或推送時的檢查

當 Claude 通過其 Bash 工具執行 `git commit` 或 `git push` 時，外掛程式在背景中執行對變更的更深層代理審查。此審查讀取周圍程式碼，包括呼叫者、清理程式和相關檔案，以決定發現是否真實，然後再報告它。額外的上下文使假陽性在看起來危險但在您的程式碼庫中安全的模式上保持低位。

此層僅在 Claude 通過其 Bash 工具進行的提交和推送上觸發。您從自己的 shell 執行的提交，包括工作階段內的 `!` shell 逃逸，不會被審查。提交和推送審查限制為每滾動小時 20 次。如果提交審查的發現重複了端回合審查已經報告的內容，Claude 不會被重新提示，因此乾淨的提交不會從此層產生可見的輸出。

### 審查獨立性和限制

外掛程式不會要求編寫程式碼的同一 Claude 實例對自己進行評分。每個編輯檢查是一個確定性的字符串匹配，不涉及模型。端回合和提交審查作為單獨的 Claude 呼叫執行，具有新鮮的上下文和安全聚焦的提示：審查者從 diff 開始，對原始方法沒有投資，並且僅被指示查找問題。

沒有任何層阻止寫入或提交。發現作為指令到達編寫 Claude，Claude 在對話中解決它們，審查模型可能會遺漏問題。將外掛程式視為深度防禦的一層，而不是完整的安全解決方案。請參閱 [此功能如何與其他安全工具配合](#how-this-fits-with-other-security-tools)。

## 添加自己的規則

外掛程式有兩個擴展點：用於模型支持的審查的 Markdown 指導檔案，以及用於每個編輯字符串匹配的 YAML 或 JSON 模式檔案。兩者都是附加的。您可以添加檢查，但無法從這些檔案中禁用內置檢查。

### 為模型支持的審查添加指導

在您的專案中建立 `.claude/claude-security-guidance.md`，並用純文字描述您的威脅模型和審查清單。模型支持的審查將其作為附加上下文與內置漏洞清單一起載入。

以下示例適用於具有角色門控管理員路由和客戶資料日誌記錄政策的網路服務：

```markdown .claude/claude-security-guidance.md theme={null}
# 此儲存庫的安全指導

- 不要在 INFO 級別或更高級別記錄 `customer_id` 或 `account_number`。
- `/admin` 下的所有路由必須在任何資料庫讀取之前呼叫 `require_role("admin")`。
- 使用 `crypto.timingSafeEqual` 進行令牌比較，而不是 `===`。
```

這些規則是審查者的指導，而不是確定性的護欄。外掛程式將違規作為發現呈現給 Claude 修復，但它不會阻止寫入或保證捕捉每個違規。指導是附加的：說要忽略漏洞類別的規則不會抑制這些發現。對於硬執行，將外掛程式與 [阻止編輯受保護檔案的鉤子](https://code.claude.com/docs/zh-TW/hooks-guide.md#block-edits-to-protected-files) 或 CI 檢查配對。

### 添加自訂的每個編輯模式

建立 `.claude/security-patterns.yaml` 以將 regex 或子字符串規則添加到 [每個編輯模式檢查](#on-each-file-edit)。這些作為確定性字符串匹配與內置模式一起執行：

```yaml .claude/security-patterns.yaml theme={null}
patterns:
  - rule_name: internal_api_key
    substrings: ["sk_live_", "AKIA"]
    reminder: "硬編碼的 API 金鑰前綴。從秘密管理器載入認證。"
  - rule_name: tenant_unfiltered_query
    regex: "\\.objects\\.all\\(\\)"
    paths: ["**/src/tenants/**"]
    reminder: "多租戶程式碼必須按 org_id 篩選。"
```

| 欄位 | 類型 | 描述 |
| :- | :- | :- |
| `rule_name` | string | 警告中顯示的識別碼 |
| `reminder` | string | 附加到 Claude 上下文的警告文本，上限為 1 KB |
| `regex` | string | 針對編輯內容匹配的 Python regex |
| `substrings` | list | 文字子字符串；提供此或 `regex` |
| `paths` | list | 可選的 glob 模式；規則僅適用於匹配的檔案。Glob 會針對完整檔案路徑進行匹配，因此請在專案相對模式前加上 `**/` |
| `exclude_paths` | list | 可選的 glob 模式以跳過；與 `paths` 相同的匹配 |

外掛程式還讀取 `.claude/security-patterns.yml` 和 `.claude/security-patterns.json`，具有相同的架構。JSON 適用於任何 Python 安裝。YAML 形式需要 PyYAML 可導入，外掛程式不會為您安裝。外掛程式載入最多 50 個自訂規則，並跳過看起來容易發生災難性回溯的 regex。

### 規則檔案查找位置

外掛程式在相同位置查找 `claude-security-guidance.md` 和 `security-patterns.yaml`，與外掛程式的啟用方式無關：

| 範圍 | 路徑 | 備註 |
| :- | :- | :- |
| 使用者 | `~/.claude/claude-security-guidance.md` | 適用於您機器上的每個專案 |
| 專案 | `.claude/claude-security-guidance.md` | 與儲存庫一起簽入 |
| 專案本地 | `.claude/claude-security-guidance.local.md` | 用於個人覆蓋；將其添加到您的 `.gitignore` |

外掛程式載入所有存在的位置並連接它們，指導檔案的組合上限為 8 KB。管理員可以通過設備管理將使用者範圍檔案推送到 `~/.claude/` 來分發組織範圍的規則。相同的路徑適用於 `security-patterns.yaml`。

## 使用成本

[每個檔案編輯時的模式檢查](#on-each-file-edit) 不進行模型呼叫，不增加成本。[每個回合結束時](#at-the-end-of-each-turn) 和 [每次提交或推送時](#on-each-commit-or-push-claude-makes) 的審查各自花費額外的模型使用，計入您的 [使用](https://code.claude.com/docs/zh-TW/costs.md)，就像任何其他 Claude 請求一樣。提交審查是代理性的，每次提交可能需要多個模型回合。預期大約每個更改檔案的回合進行一次審查呼叫，每次提交進行一次更深層的審查，兩者都受上述上限的限制。

預設情況下，兩種審查都在 Claude Opus 模型上執行。設定 `SECURITY_REVIEW_MODEL` 為端回合審查選擇不同的模型，設定 `SG_AGENTIC_MODEL` 為提交審查選擇不同的模型。

外掛程式在所有計畫上可用。

## 禁用或卸載

要關閉各個層同時保持其餘層，請設定匹配的環境變數：

| 變數 | 效果 |
| :- | :- |
| `ENABLE_PATTERN_RULES=0` | 禁用 [每個編輯模式檢查](#on-each-file-edit) |
| `ENABLE_STOP_REVIEW=0` | 禁用 [端回合 diff 審查](#at-the-end-of-each-turn) |
| `ENABLE_COMMIT_REVIEW=0` | 禁用 [提交和推送審查](#on-each-commit-or-push-claude-makes) |
| `ENABLE_CODE_SECURITY_REVIEW=0` | 一次禁用所有模型支持的審查 |
| `SECURITY_GUIDANCE_DISABLE=1` | 禁用外掛程式而不卸載 |

要在您的使用者範圍中暫停外掛程式：

```text theme={null}
/plugin disable security-guidance@claude-plugins-official
```

要從您的使用者範圍中移除它：

```text theme={null}
/plugin uninstall security-guidance@claude-plugins-official
```

如果外掛程式通過專案的 `.claude/settings.json` 啟用，從 `/plugin` 禁用它會將覆蓋寫入您的 `.claude/settings.local.json`，而不是編輯簽入的檔案，因此外掛程式對您保持關閉，而不影響隊友。同一對話框也提供選項以移除外掛程式供所有人使用，方法是從共享的 `.claude/settings.json` 中移除它。如果它通過 [受管設定](https://code.claude.com/docs/zh-TW/admin-setup.md) 啟用，只有管理員可以禁用它。

## 外掛程式如何與 Claude Code 整合

外掛程式完全建立在 [hooks](https://code.claude.com/docs/zh-TW/hooks.md) 上，這是在 Claude 迴圈中的特定點執行您自己的程式碼的機制。它註冊：

| Hook 事件 | 目的 |
| :- | :- |
| `SessionStart` | 啟動外掛程式的 Python 環境 |
| `UserPromptSubmit` | 捕捉端回合審查 diff 的工作樹基線 |
| `PostToolUse` 在 `Edit`、`Write` 和 `NotebookEdit` 上 | 每個編輯模式匹配 |
| `Stop` | 端回合 diff 審查，在背景中執行 |
| `PostToolUse` 在 `Bash` 上，篩選為 `git commit` 和 `git push` | 提交和推送審查，在背景中執行 |

如果您構建自己的 hooks，[外掛程式的源代碼](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance) 是從 hook 執行單獨模型呼叫並將結果反饋到工作階段的工作示例。

## 此功能如何與其他安全工具配合

外掛程式是深度防禦方法中的一層。它最早捕捉問題，當程式碼仍在編輯器中時，但它不是保證，也不能替代後來的檢查。典型的堆棧：

| 階段 | 工具 | 涵蓋的內容 |
| :- | :- | :- |
| 在工作階段中 | Security guidance 外掛程式 | Claude 編寫的程式碼中的常見漏洞，在同一工作階段中修復 |
| 按需、單次掃描 | [`/security-review`](https://code.claude.com/docs/zh-TW/commands#all-commands) | 對當前分支的一次性安全檢查，在您要求時執行 |
| 按需、深度掃描 | [Claude Security 外掛程式](https://code.claude.com/docs/zh-TW/claude-security.md) | 對儲存庫或差異的多代理漏洞掃描，具有獨立審查的發現和修補程式 |
| 在拉取請求上 | [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)，Team 和 Enterprise 計畫 | 具有完整程式碼庫上下文的多代理正確性和安全審查 |
| 在 CI 中 | 您現有的靜態分析和依賴掃描器 | 語言特定的規則、供應鏈檢查和外掛程式不嘗試的政策執行 |

若要在您已有的程式碼中尋找安全問題，而不是在 Claude 正在編寫的變更中，請在工作階段中要求 Claude 審查特定檔案或目錄是否存在漏洞，或使用 [Claude Security 外掛程式](https://code.claude.com/docs/zh-TW/claude-security.md) 對整個儲存庫進行更深入的多代理掃描；[`/security-review`](https://code.claude.com/docs/zh-TW/commands#all-commands) 僅涵蓋您當前分支上的變更。無論哪種方式，審查都會讀取您簽出中的原始程式碼，而不是執行中的網站或已部署的服務。

## 故障排除

外掛程式將執行時診斷寫入 `~/.claude/security/log.txt`。如果審查未出現，請先檢查那裡。

審查層在對話中無聲跳過的常見原因：

* 目錄不是 git 儲存庫：端回合和提交審查需要 git 狀態，並在儲存庫外跳過
* 工作階段沒有 Anthropic 身份驗證且沒有設定第三方提供者：模型支持的審查會跳過，只有每個編輯模式檢查執行
* `security-patterns.yaml` 檔案存在但 PyYAML 不可導入：檔案被忽略。改用 `security-patterns.json`

## 相關資源

要深入了解此頁面涉及的部分：

* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：設定 PR 時間多代理審查
* [使用 hooks 自動化工作流](https://code.claude.com/docs/zh-TW/hooks-guide.md)：在相同的生命週期點構建您自己的檢查
* [在官方 marketplace 中尋找 plugins](https://code.claude.com/docs/zh-TW/plugins/anthropic-marketplaces.md#find-plugins-in-the-official-marketplace)：瀏覽其他官方 plugins 的位置
