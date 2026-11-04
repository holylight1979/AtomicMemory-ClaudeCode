<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/auto-mode-config | lastmod: 2026-11-02 | section: Administration / Setup and access -->
> 來源：https://code.claude.com/docs/zh-TW/auto-mode-config（官方 zh-TW，lastmod 2026-11-02）｜分類：Administration › Setup and access｜EN 摘要：Tell the auto mode classifier which repos, buckets, and domains your organization trusts. Set environment context, override the default block and allow rules, and inspect your effective config with the auto-mode CLI subcommands.

# 設定自動模式

> 告訴自動模式分類器您的組織信任哪些儲存庫、儲存桶和網域。設定環境內容、覆蓋預設的封鎖和允許規則，並使用自動模式 CLI 子命令檢查您的有效設定。

[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)讓 Claude Code 無需例行權限提示即可執行，方法是透過分類器路由工具呼叫，該分類器會封鎖任何不可逆、破壞性或針對您環境外的操作。拒絕和明確要求規則在分類器之前進行評估，仍然會封鎖或提示。使用 `autoMode` 設定區塊告訴該分類器您的組織信任哪些儲存庫、儲存桶和網域，以便它停止封鎖例行內部操作。

> [!NOTE]
>
> 此頁面是設定參考。開啟和關閉自動模式涵蓋在「權限模式」頁面上：
>
> * **在工作階段中切換到自動模式，或退出自動模式**：請參閱[切換權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)
> * **在自動模式中啟動工作階段**：請參閱[以不同的權限模式啟動](https://code.claude.com/docs/zh-TW/permission-modes.md#start-in-a-different-mode)

自動模式適用於所有提供者上的所有使用者，包括 Anthropic API、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和已登入的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段。如果 Claude Code 報告您的帳戶無法使用自動模式，請檢查[完整要求](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)，其中也涵蓋支援的模型和 Team 及 Enterprise 方案上的組織層級控制。

根據預設，分類器只信任工作目錄和目前儲存庫的已設定遠端。推送到您公司的原始碼控制組織或寫入團隊雲端儲存桶等操作會被封鎖，直到您將它們新增到 `autoMode.environment`。

此頁面涵蓋如何：

* [為推送和提取請求新增人工檢查點](#add-a-human-checkpoint)，使用 `permissions.ask`
* [定義受信任的基礎結構](#define-trusted-infrastructure)，使用 `autoMode.environment`
* [使用 `/auto-mode-setup` 產生環境項目](#generate-environment-entries)
* [檢查拒絕](#review-denials)，以便您知道接下來要新增什麼

## 常見的邊界

自動模式允許推送到您正在使用的儲存庫的任何分支（包括預設分支），並預設建立拉取請求。名稱標記為部署或發佈目標的非預設分支（例如 `production`、`release` 或 `gh-pages`）不受該預設涵蓋：分類器會根據其自身條件判斷推送到該分支，包括作為生產部署。推送的內容仍然會被檢查，因此強制推送、秘密進入提交，或在 CI 或部署管道執行時會將秘密發送到儲存庫外的變更仍然會被阻止。

如果您想在 Claude 的推送和拉取請求命令之前進行人工檢查點，請新增權限規則：下面的[配方](#add-a-human-checkpoint)會保持自動模式對所有其他操作開啟。

### 新增人工檢查點

最直接的機制是 [`permissions.ask`](https://code.claude.com/docs/zh-TW/permissions#permission-rule-syntax)。內容範圍的 ask 規則（如下面的規則）在分類器之前進行評估，並且始終強制權限提示，即使在自動模式下也是如此，因為明確的 ask 規則是您要求提示該操作的明確意圖。在您的[設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中新增規則：

```json theme={null}
{
  "permissions": {
    "ask": [
      "Bash(git push *)",
      "Bash(gh pr create *)"
    ]
  }
}
```

這些規則符合以 `git push` 或 `gh pr create` 開頭的命令。Claude 以其他方式寫入的推送，例如 `git -C <dir> push` 或 `git -c <key>=<value> push`，[不符合規則](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)，因此不會被檢查點。對於檢查完整命令文字的檢查點，請新增 [PreToolUse hook](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse)。

選擇與邊界需要有多堅定相符的機制：

| 邊界 | 機制 | 自動模式中的行為 |
| :- | :- | :- |
| 在操作前提示 | `permissions.ask` | 始終為符合內容範圍規則（如上面的配方）的命令提示。分類器無法自動批准符合的操作。 |
| 永不執行操作 | `permissions.deny` | 在諮詢分類器之前阻止。分類器和使用者意圖都無法覆蓋它。 |
| 此工作階段的一次性邊界 | 在對話中陳述，例如「在我審查之前不要推送」 | 分類器會阻止符合的操作，但如果[內容壓縮](https://code.claude.com/docs/zh-TW/costs.md#reduce-token-usage)移除了陳述該邊界的訊息，邊界可能會遺失。使用 ask 或 deny 規則以獲得持久保證。 |

## 分類器讀取設定的位置

分類器讀取與 Claude 本身載入相同的 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) 內容，因此在您專案的 CLAUDE.md 中的指令（例如「永遠不要強制推送」）會同時引導 Claude 和分類器。請從該處開始了解專案慣例和行為規則。

對於跨專案適用的規則，例如受信任的基礎設施或組織範圍的拒絕規則，請使用 `autoMode` 設定區塊。分類器從以下範圍讀取 `autoMode`：

| 範圍 | 檔案 | 用途 |
| :- | :- | :- |
| 單一開發者 | `~/.claude/settings.json` | 個人受信任的基礎設施 |
| 組織範圍 | [受管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) | 分散給所有開發者的受信任基礎設施 |
| `--settings` 旗標或 Agent SDK | 內嵌 JSON | 自動化的每次調用覆蓋 |

分類器不會從 `.claude/settings.json` 或 `.claude/settings.local.json` 中的專案設定讀取 `autoMode`。兩個檔案都位於儲存庫目錄中，因此已簽入的儲存庫或建置步驟可能會注入自己的允許規則。請將 `.claude/settings.local.json` 中的任何 `autoMode` 區塊移至 `~/.claude/settings.json`。

來自每個範圍的項目會被合併。開發者可以使用個人項目擴展 `environment`、`allow`、`soft_deny` 和 `hard_deny`，但無法移除受管理設定提供的項目。由於允許規則在分類器內部充當軟區塊規則的例外，開發者新增的 `allow` 項目可以覆蓋組織的 `soft_deny` 項目：組合是累加的，而不是硬政策邊界。

> [!NOTE]
>
> 分類器是在[權限系統](https://code.claude.com/docs/zh-TW/permissions.md)之後執行的第二道閘門。對於無論使用者意圖或分類器設定如何都必須永遠不執行的動作，請在受管理設定中使用 `permissions.deny`，它會在諮詢分類器之前阻止該動作，且無法被覆蓋。

## 定義受信任的基礎設施

對於大多數組織，`autoMode.environment` 是您唯一需要設定的欄位。它告訴分類器哪些儲存庫、儲存桶和網域是受信任的：分類器使用它來決定「外部」的含義，因此任何未列出的目的地都是潛在的資料外洩目標。

`claude auto-mode defaults` 會列印三種環境項目。

* **Context slots**：描述您的組織、技術堆疊和安全態勢，以便分類器讀取您的上下文中的其他規則。每個預設為 `None configured` 或保守假設（名稱如下）：
  * **Organization**
  * **Claude Code 的主要用途**：預設為軟體開發
  * **雲端提供者**
  * **儲存庫可見性**：除非其遠端主機和名稱另有指示，或分類器讀取的對話中較早的可見性檢查顯示它是公開的，否則儲存庫被假定為私有。

    在 Claude Code 本身發送的分類器請求中，分類器讀取您的訊息和 Claude 執行的命令，而不是它們的輸出。證據必須是分類器能讀取的內容，例如您自己的訊息將儲存庫命名為公開；單獨執行 `gh repo view` 的輸出無法到達它。
  * **內部共享 / 程式碼片段託管**：公開貼上和 gist 服務被視為在信任邊界之外，直到您命名其中一個
  * **組織特定的 CLI**
  * **祕密管理**
  * **CI/CD 部署目標**
  * **網路態勢**
  * **Host containment**：預設為具有開放網際網路的普通開發人員機器或 CI 執行器。如果 Claude Code 在具有出口允許清單或不得接觸的鄰近項目的容器、VM 或 pod 中執行，請命名允許的主機、雲端中繼資料端點是否應可到達，以及任務使用的雲端專案、叢集或登錄以及使用的身分。在此項目命名該身分之前，分類器[阻止](https://code.claude.com/docs/zh-TW/permission-modes.md#what-the-classifier-blocks-by-default)主機自身認證的請求。需要 Claude Code v2.1.257 或更新版本
  * **受保護的部署命名空間 / 環境**：在您命名它們之前，回退到「敏感遠端目標」啟發式
  * **資料保留 / 解密**
* **Trust slots**：命名分類器視為在您邊界內的內容。槽位為「受信任的儲存庫」、「原始碼控制」、「受信任的內部網域」、「受信任的雲端儲存桶」、「關鍵內部服務」和「內部套件登錄」。儲存庫和原始碼控制項目預設為工作儲存庫及其配置的遠端。其他所有信任槽位預設為 `None configured`，因此在您新增之前，沒有其他內容是受信任的。儲存庫的可見性僅限於機密資料：私有儲存庫是機密資料的可接受目的地，但將儲存庫設為私有永遠不會清除祕密或個人或受信任的資料進入其中，分類器將從工作儲存庫外部移植、重新指向或首次讀取的內容視為不是該儲存庫自己的工作。
* **Sensitivity slots**：命名保護規則視為高風險的內容。槽位為「敏感資料位置和受眾」、「敏感遠端目標」和「受保護的 IaC 範圍」。每個預設為廣泛的啟發式，例如將任何名稱包含 `prod` 或 `production` 的主機或命名空間視為敏感遠端目標，因此保護規則在您配置任何內容之前就處於活動狀態。在敏感槽位中命名具體目標會使這些規則應用於命名的目標，而不是啟發式。

若要在預設值旁邊新增您自己的項目，請在陣列中包含字面字串 `"$defaults"`。預設項目會在該位置拼接，因此您的自訂項目可以在它們之前或之後。

以下範例保留預設項目並新增組織的儲存庫、儲存桶、網域和服務。

```json theme={null}
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Source control: github.example.com/acme-corp and all repos under it",
      "Trusted cloud buckets: s3://acme-build-artifacts, gs://acme-ml-datasets",
      "Trusted internal domains: *.corp.example.com, api.internal.example.com",
      "Key internal services: Jenkins at ci.example.com, Artifactory at artifacts.example.com"
    ]
  }
}
```

儲存您的設定後，執行 `claude auto-mode config` 以[確認有效規則](#inspect-the-defaults-and-your-effective-config)包含您的項目。

項目是散文，不是正規表達式或工具模式。分類器將它們讀取為自然語言規則。按照您向新工程師描述基礎設施的方式編寫它們。徹底的環境部分涵蓋：

* **Organization**：您的公司名稱以及 Claude Code 主要用於什麼，例如軟體開發、基礎設施自動化或資料工程
* **Source control**：您的開發人員推送到的每個 GitHub、GitLab 或 Bitbucket 組織
* **雲端提供者和受信任的儲存桶**：Claude 應該能夠讀取和寫入的儲存桶名稱或前綴
* **Trusted internal domains**：您網路內 API、儀表板和服務的主機名稱，例如 `*.internal.example.com`
* **Key internal services**：CI、構件登錄、內部套件索引、事件工具
* **Internal package registry**：私有 npm、PyPI 或其他登錄，安裝應該透過它進行，因此繞過它安裝公開登錄的安裝會被阻止
* **Sensitive data locations & audiences**：保存個人資料、機密業務資料、認證、受管制資料或類似敏感資料的儲存桶、資料庫或路徑，以及每個位置中的資料可能與之共享的受眾，以便分類器保護這些位置而不是從內容猜測。
* **Sensitive remote targets**：計為生產環境的命名空間、主機或容器，因此遠端 shell 和埠轉發進入它們需要您的明確批准
* **Protected IaC scopes**：應用或銷毀應始終需要您命名變更的基礎設施資源
* **Additional context**：受管制行業限制、多租戶基礎設施或影響分類器應視為風險的合規要求

一個有用的起始範本：填入括號中的欄位並移除任何不適用的行。

```json theme={null}
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Organization: {COMPANY_NAME}. Primary use: {PRIMARY_USE_CASE, e.g. software development, infrastructure automation}",
      "Source control: {SOURCE_CONTROL, e.g. GitHub org github.example.com/acme-corp}",
      "Cloud provider(s): {CLOUD_PROVIDERS, e.g. AWS, GCP, Azure}",
      "Trusted cloud buckets: {TRUSTED_BUCKETS, e.g. s3://acme-builds, gs://acme-datasets}",
      "Trusted internal domains: {TRUSTED_DOMAINS, e.g. *.internal.example.com, api.example.com}",
      "Key internal services: {SERVICES, e.g. Jenkins at ci.example.com, Artifactory at artifacts.example.com}",
      "Additional context: {EXTRA, e.g. regulated industry, multi-tenant infrastructure, compliance requirements}"
    ]
  }
}
```

您不需要一次填入所有內容。合理的推出：從預設值開始，新增您的原始碼控制組織和關鍵內部服務，這可以解決最常見的誤報，例如推送到您自己的儲存庫。接下來新增受信任的網域和雲端儲存桶。當出現阻止時填入其餘部分。

## 使用 `/auto-mode-setup` 產生環境項目

執行 `/auto-mode-setup`，讓 Claude Code 根據您的專案以及您最近在該專案中的工作階段，草擬 `autoMode.environment` 項目，有時也會草擬[規則項目](#override-the-block-and-allow-rules)。如果您接受草稿，Claude Code 會將其寫入 `~/.claude/settings.json`。

> [!NOTE]
>
> `/auto-mode-setup` 適用於 Pro、Max、Ultra、Team 和 Enterprise 方案，以及使用 Claude Console API 金鑰時。在 Pro、Max、Ultra 或 Team 方案中，您需要 v2.1.228 或更新版本，若是原生 Windows 則需要 v2.1.233 或更新版本。在 Enterprise 方案中或使用 Claude Console API 金鑰時，您需要 v2.1.283 或更新版本。如果您的工作階段中沒有此命令，請參閱 [`/auto-mode-setup` 傳回「Unknown command」](#auto-mode-setup-returns-unknown-command)。

### `/auto-mode-setup` 會讀取哪些內容

如果 `~/.claude/settings.json` 中已經有 `autoMode` 項目，Claude Code 會先詢問要新增到您的環境清單還是取代它，並且無論哪種情況都會保留您撰寫的規則。接著，Claude Code 會詢問您如何使用此專案，並在掃描任何內容之前提供兩項選用掃描。在掃描中，Claude Code 一律會讀取以下來源：

* 此專案的 `CLAUDE.md`、`README.md`、設定檔和 git remote
* 您的 `autoMode` 和 `permissions.allow` 設定
* Claude 在您最近於此專案中的工作階段所執行命令中的主機、bucket 和命令名稱，絕不包含您的訊息

兩項選用掃描各新增一個來源：

* 您 shell 歷史記錄中每個命令的第一個字
* 您家目錄下各儲存庫的遠端主機和名稱

### 檢閱並儲存草稿

Claude Code 會在背景中掃描，然後向您顯示草稿。您只能整體接受或捨棄草稿，因此之後請編輯 `~/.claude/settings.json` 來調整個別項目。當您接受時，Claude Code 會寫入草稿，並將其與您現有的設定進行協調：

* Claude Code 寫入的 `environment` 清單不含 `"$defaults"`，因為草稿已明確列出其未變更的內建項目
* Claude Code 會在草稿新增項目的每個 `allow`、`soft_deny` 和 `hard_deny` 清單中包含 `"$defaults"`，除非您已經撰寫了不含它的 `allow` 清單，如此一來，您尚未取代的[內建規則](#override-the-block-and-allow-rules)仍會保持生效
* 儲存後，Claude Code 會提議移除 `~/.claude/settings.json` 中自動模式會忽略的 `permissions.allow` 規則（例如 `Bash(*)`），或會自動核准破壞性命令的規則

接著執行 `claude auto-mode config` 以[查看實際生效的結果](#inspect-the-defaults-and-your-effective-config)。

### 關閉 `/auto-mode-setup`

當自動模式已封鎖數個動作，而您仍然沒有任何 `autoMode.environment` 項目時，Claude Code 會在回合結束時顯示標題為「Teach auto mode about your environment?」的對話框，並提議為您執行 `/auto-mode-setup`。若要停止此提議但保留命令，請在該對話框中選取 **Don't show again**。

若要同時關閉命令和提議，請將此 [`skillOverrides`](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings) 項目新增到 `~/.claude/settings.json`：

```json theme={null}
{
  "skillOverrides": {
    "auto-mode-setup": "off"
  }
}
```

`/auto-mode-setup` 是內建命令，而非[隨附 skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)，因此此 `skillOverrides` 項目仍然適用於它，但 [`disableBundledSkills`](https://code.claude.com/docs/zh-TW/settings-reference#disablebundledskills) 無法將其關閉。

### `/auto-mode-setup` returns "Unknown command"

如果在 Claude Code 提示字元輸入 `/auto-mode-setup` 時顯示 `Unknown command: /auto-mode-setup`，請檢查以下原因：

* **安裝或升級後的第一個工作階段**：啟動新的工作階段。如果該工作階段中仍然沒有此命令，請參閱[後續工作階段啟動時也沒有此命令的設定情況](https://code.claude.com/docs/zh-TW/env-vars.md#first-session-after-an-install-or-upgrade)。
* **版本過舊**：在您的 shell 中執行 `claude --version`。如果版本低於[您方案的最低版本](#generate-environment-entries)，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。
* **遙測已關閉、第三方供應商或 Claude apps 閘道**：在 v2.1.304 之前，此命令在[已關閉功能旗標擷取的工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)中無法使用。如果您的工作階段屬於其中之一，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code) 至 v2.1.304 或更新版本。

在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，此命令會改為顯示 `/auto-mode-setup isn't available in this environment.`。請在終端機的互動式工作階段中執行此命令。

## 覆蓋阻止和允許規則

三個額外的欄位讓您取代分類器的內建規則清單：

* `autoMode.hard_deny`：無條件安全邊界
* `autoMode.soft_deny`：使用者意圖可以清除的破壞性操作
* `autoMode.allow`：軟阻止規則的例外

每個都是散文描述的陣列，讀取為自然語言規則。對於在分類器之前執行的工具模式型硬阻止，請使用 [`permissions.deny`](https://code.claude.com/docs/zh-TW/permissions)。

在分類器內，優先順序分為四個層級：

* `hard_deny` 規則無條件阻止。使用者意圖和 `allow` 例外不適用。
* `soft_deny` 規則接著阻止。使用者意圖和 `allow` 例外可以覆蓋這些。
* `allow` 規則然後覆蓋匹配的 `soft_deny` 規則作為例外。
* 明確的使用者意圖覆蓋剩餘的軟阻止：如果使用者的訊息直接且具體地描述 Claude 即將採取的確切操作，分類器允許它，即使 `soft_deny` 規則匹配。

一般請求不算作明確意圖。要求 Claude「清理儲存庫」不授權強制推送，但要求 Claude「強制推送此分支」則授權。

要放寬，當分類器重複標記預設例外不涵蓋的常規模式時，新增到 `allow`。要加強，對於預設值遺漏的特定於您環境的破壞性風險，新增到 `soft_deny`，或對於必須永遠不能跨越的安全邊界，新增到 `hard_deny`。

要保留內建規則同時新增您自己的規則，請在陣列中包含字面字串 `"$defaults"`。預設規則會在該位置拼接，因此您的自訂規則可以在它們之前或之後，並且當內建清單在版本發佈中變更時，您繼續繼承更新。

下列範例在所有四個清單中保留預設值，並將組織特定的規則新增到每個清單。

```json theme={null}
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Source control: github.example.com/acme-corp and all repos under it"
    ],
    "allow": [
      "$defaults",
      "Deploying to the staging namespace is allowed: staging is isolated from production and resets nightly",
      "Writing to s3://acme-scratch/ is allowed: ephemeral bucket with a 7-day lifecycle policy"
    ],
    "soft_deny": [
      "$defaults",
      "Never run database migrations outside the migrations CLI, even against dev databases",
      "Never modify files under infra/terraform/prod/: production infrastructure changes go through the review workflow"
    ],
    "hard_deny": [
      "$defaults",
      "Never send repository contents to third-party code-review APIs"
    ]
  }
}
```

> [!CAUTION]
>
> 設定 `environment`、`allow`、`soft_deny` 或 `hard_deny` 中的任何一個而不包含 `"$defaults"` 會取代該部分的整個預設清單。如果您設定沒有 `"$defaults"` 的陣列，您會捨棄該部分的內建規則：
>
> * `soft_deny`：每個內建軟阻止規則，包括強制推送、`curl | bash`、生產部署和自動模式繞過
> * `hard_deny`：內建資料外洩規則

每個部分獨立評估，因此單獨設定 `environment` 會保持預設 `allow`、`soft_deny` 和 `hard_deny` 清單完整。

只在您打算完全掌控清單時才省略 `"$defaults"`。要安全地執行此操作，執行 `claude auto-mode defaults` 列印內建規則，將它們複製到您的設定檔案中，然後根據您自己的管道和風險容限檢查每個規則。

## 從 `/permissions` 編輯規則

若要檢視和編輯分類器規則和 `environment` 項目而不開啟設定檔，請執行 [`/permissions`](https://code.claude.com/docs/zh-TW/permissions#manage-permissions) 並選取 **Auto mode** 索引標籤。該索引標籤需要 Claude Code v2.1.246 或更新版本，且僅在 [auto mode 可供您的工作階段使用](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 時才會出現。

Claude Code 會將來自 [managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 或 `--settings` 旗標的項目顯示為唯讀，並將您在該索引標籤上所做的每項變更儲存到 `~/.claude/settings.json`。

## 透過分類器路由所有 shell 命令

根據預設，narrow Bash 和 PowerShell 允許規則（例如 `Bash(npm test)`）在自動模式中保持有效。Claude Code 會在分類器執行前解析它們，除非命令帶有[每個命令允許的網域](https://code.claude.com/docs/zh-TW/sandboxing.md#per-command-allowed-domains-in-auto-mode)。Claude Code 只會暫停授予任意程式碼執行權限的廣泛規則，例如 `Bash(*)` 或萬用字元解釋器，以及每個命名 [`Monitor`](https://code.claude.com/docs/zh-TW/tools-reference#monitor-tool) 的規則，因為 Monitor 命令會透過 shell 執行。這表示 narrow 規則仍然可能讓破壞性引數通過而不被分類器看到，例如規則前綴未預期的指令碼路徑或旗標。

將 `autoMode.classifyAllShell` 設定為 `true`，以在自動模式啟用時暫停每個 Bash 和 PowerShell 允許規則，讓分類器評估每個 shell 命令，無論您的允許清單為何，除了[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)。

```json theme={null}
{
  "autoMode": {
    "classifyAllShell": true
  }
}
```

這會用延遲換取涵蓋範圍：允許規則會立即核准的命令現在會等待分類器決定，每個 shell 命令都計為一次分類器呼叫。

此設定僅在自動模式啟用時適用，您的允許規則在其他權限模式中的行為正常。

## 檢查預設值和您的有效設定

`claude auto-mode` 子命令可幫助您檢查、驗證和重設您的設定。

將內建的 `environment`、`allow`、`soft_deny` 和 `hard_deny` 規則列印為 JSON：

```bash theme={null}
claude auto-mode defaults
```

若要讀取一個規則的完整措辭而不需透過 `jq` 管道，請傳遞 `--label` 並加上規則標籤的開頭，例如 `claude auto-mode defaults --label 'Git Destructive'`。比對是對每個規則標籤的不區分大小寫前綴，沒有比對的部分會列印為空列表。

列印分類器實際使用的內容為 JSON，其中您的設定已套用（如果已設定）或使用預設值：

```bash theme={null}
claude auto-mode config
```

`defaults` 和 `config` 都會將四個規則列表列印為單一 JSON 物件，每個規則都是散文字串。這是一個截斷的範例：

```json theme={null}
{
  "allow": [
    ...
    "Test Artifacts: Hardcoded test API keys, placeholder credentials in examples, or hardcoding test cases. Placeholder means authored as a placeholder — a file or value copied from a real secret or sensitive path is never a test artifact (see Sensitive-Source Provenance).",
    ...
  ],
  "soft_deny": [
    "Git Destructive [named+specifics — **must name:** the destructive operation and its target]: Force pushing (`git push --force`), deleting remote branches, tags, or releases, or rewriting remote history. Also `git commit --amend` when the commit being rewritten is not the agent's own unpushed work: either no prior `git commit` is visible (HEAD pre-dates the session), or a `git push` of the current branch is visible after the most recent commit (it has been pushed). Clears when the user asked to amend/reword/fixup, or when it is a message-only reword (`--amend -m …`, nothing newly staged) of a commit the agent visibly created this session.",
    ...
  ],
  "hard_deny": [...],
  "environment": [
    ...
    "**Trusted repo**: The git repository the agent started in (its working directory) and its configured remote(s). When the repo's public/private visibility is given — by the Repository visibility entry or the user's own message — use it to scope what is OK to commit or push there: confidential material is fine in a private repo; in a public one, only that repo's own work is — and content ported, repointed, or first read from outside this session's repo is not its own work, whoever directed the port. Visibility scopes confidential material only: secrets and sensitive data (personal & entrusted) are never cleared into any repo by its visibility (see Definitions).",
    ...
  ]
}
```

取得 AI 對您自訂 `allow`、`soft_deny`、`hard_deny` 和 `environment` 項目的回饋：

```bash theme={null}
claude auto-mode critique
```

如果您已撰寫自訂規則，`claude auto-mode critique` 會檢查它們並標記模稜兩可、冗餘或可能導致誤判的項目。

若要捨棄您的自訂設定並回復到內建預設值，請執行重設子命令，它會從您的使用者設定檔案中移除 `autoMode` 部分：

```bash theme={null}
claude auto-mode reset
```

該命令會摘要說明它將移除的內容，並在寫入前詢問 `Reset auto mode configuration to defaults?`；傳遞 `--yes` 以略過確認。重設只會變更 `~/.claude/settings.json`：來自[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)或 `--settings` 旗標的 `autoMode` 規則仍然適用。

## 檢視拒絕

若要讓 Claude 重試被封鎖的動作，請使用 `/permissions` 中的 **Recently blocked** 標籤：

**1. 開啟標籤**

在您的工作階段中執行 `/permissions` 以開啟權限對話框，然後選取 **Recently blocked** 標籤。

**2. 檢查動作**

反白選取該動作所在的列，並在清單下方閱讀其命令或輸入。請以命令或輸入為準，而非該列的描述，因為描述是由 Claude 或工具撰寫的。

**3. 核准動作**

按 `r` 以核准該動作，並讓 Claude 重試。

**4. 關閉對話框**

按 `Esc` 以關閉對話框並套用您的核准。如果您開啟 `/permissions` 時 Claude 正在工作，請在 Claude 完成後傳送一則訊息，讓 Claude 重試該動作。否則，您不需要傳送任何內容：Claude 會立即繼續，並可能重試該動作。如果沒有重試，請在您的下一則訊息中指明該動作，如[您在對話中表明的核准](https://code.claude.com/docs/zh-TW/permission-modes.md#approvals-you-state-in-conversation)所述。

核准動作並不會新增權限規則。在自動模式中，重試的動作會再次經過檢查，因此可能再次被封鎖。若要從現在開始允許某個命令通過，請[新增 `allow` 規則](#fix-a-denial-with-an-allow-rule-an-environment-entry-or-a-retry)。

如果您不希望 Claude 立即重試，您可以核准動作留待稍後、收回核准，或關閉對話框並捨棄您的核准：

* **核准留待稍後**：在該列上按 `Enter`，然後按 `Esc`。該列會離開標籤，Claude 可能會在您的下一則訊息之後、Claude 完成時重試該動作。如果您也在另一列上按了 `r`，則您按 `Enter` 的那一列會留在標籤上，且 Claude 不會被告知該動作。請在下次造訪時核准該列，或在兩列上都按 `r`
* **收回核准**：在您按 `Esc` 之前，在該列上按 `Enter`，無論您是以 `Enter` 或 `r` 核准的
* **關閉對話框並捨棄您的核准**：按兩次 `Ctrl+C`

當某列無法顯示其完整的命令或輸入，或動作沒有對應的列時，您無法從標籤核准該動作：

* **該列顯示 `This row can't be approved here`**：如果您確實打算執行該動作，請在您的下一則訊息中告訴 Claude，Claude 可能會再次嘗試
* **沒有對應的列，且對話中出現 `Not run` 或分類器錯誤**：自動模式的分類器未做出判決。若要了解如何執行該動作，請閱讀[自動模式無法判定動作的安全性](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)

### 使用允許規則、環境項目或重試來修復拒絕

通知內容類似 `bash blocked by auto mode · /permissions · Auto mode: [Data Exfiltration]`。若要查看其背後的命令或 URL，請使用 **Recently blocked** 標籤、hook 或對話：

* **Recently blocked 標籤**：反白選取該動作所在的列。在[螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md)中，所有命令和輸入會顯示在清單之前。
* **Hook**：若要以程式設計方式擷取拒絕的確切輸入，請新增 [`PermissionDenied` hook](https://code.claude.com/docs/zh-TW/hooks#permissiondenied)，它會將其作為 `tool_input` 接收。如果您的 hook 讀取 `reason`，請預期不會有 `Auto mode:` 前綴，且會出現 `Blocked by classifier` 之類的文字，而非 `No reason provided`。
* **對話**：找到該工具呼叫。如果呼叫顯示為縮短或摺疊成摘要行（例如 `Ran 3 shell commands`），請按 `Ctrl+O` 開啟[逐字稿檢視器](https://code.claude.com/docs/zh-TW/interactive-mode.md#transcript-viewer)，它會展開該呼叫。

呼叫下方的文字會告訴您是否有任何需要修復的內容。暗色的 `Not run · auto mode's check had no usable answer` 列，或報告分類器本身問題的文字（例如 `Auto mode could not evaluate this action`），表示 Claude Code 在沒有分類器判決的情況下阻止了呼叫。若為 `Not run` 列，請按 `Ctrl+O` 閱讀完整訊息，然後參閱[自動模式無法判定動作的安全性](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)或[伺服器未傳回安全判決](https://code.claude.com/docs/zh-TW/errors.md#the-server-returned-no-safety-verdict)以了解該怎麼做。

否則，`Blocked by auto mode` 行表示分類器判定呼叫不安全。若要讓呼叫通過，請依據 Claude 嘗試到達或執行的內容採取對應的步驟：

* 一個 Claude 在整個任務中需要的目的地，例如套件登錄、內部網域或儲存庫主機：將其新增至 `autoMode.environment`。
* 一個您想要從現在開始無需檢視即可執行的命令：新增 `allow` 規則。
* 一個您確實打算執行的一次性動作：在您的下一則訊息中說明該意圖，並讓 Claude 重試。

您可以從 `/permissions` 對話框的 [**Auto mode** 標籤](#edit-rules-from-permissions)新增環境項目或 `allow` 規則。

方括號中的文字，例如 `[Data Exfiltration]`，是分類器符合的規則名稱。若要閱讀該規則的完整措辭，請參閱[檢視預設值和您的有效設定](#inspect-the-defaults-and-your-effective-config)。

### 修復重複拒絕

同一目的地的重複拒絕通常表示分類器缺少背景資訊。將該目的地新增至 `autoMode.environment`，或[執行 `/auto-mode-setup`](#generate-environment-entries) 讓 Claude Code 草擬項目，然後執行 `claude auto-mode config` 以確認變更已生效。

## 另請參閱

* [權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)：什麼是自動模式、預設情況下它會阻止什麼，以及哪些工作階段會以自動模式啟動
* [受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：在整個組織中部署 `autoMode` 設定
* [權限](https://code.claude.com/docs/zh-TW/permissions.md)：在分類器執行前套用的允許、詢問和拒絕規則
* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md#automode)：每個設定鍵，包括 `autoMode`
