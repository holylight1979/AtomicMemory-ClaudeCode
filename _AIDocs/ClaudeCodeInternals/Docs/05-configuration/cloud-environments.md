<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/cloud-environments | lastmod: 2026-11-02 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/cloud-environments（官方 zh-TW，lastmod 2026-11-02）｜分類：Configuration › Environments｜EN 摘要：Configure cloud environments for Claude Code cloud sessions: network access levels, environment variables, setup scripts, and environment caching.

# 設定雲端環境

> 為 Claude Code 雲端工作階段設定雲端環境：網路存取層級、環境變數、設定指令碼和環境快取。

> [!NOTE]
>
> 雲端環境適用於 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，該功能適用於 Pro、Max、Ultra 和 Team 方案，以及具有 [premium seats 或 Chat + Claude Code seats](https://support.claude.com/en/articles/11845131-use-claude-code-with-your-team-or-enterprise-plan) 的 Enterprise 使用者。

每個 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 都在雲端環境中執行。您可以設定環境以允許或拒絕 [網路存取](#access-levels)、[為工作階段設定環境變數](#set-environment-variables)、儲存工作階段可使用但無法看到的 [網路機密](#add-network-secrets)，以及在 Claude 開始工作前執行 [設定指令碼](#setup-scripts)。

相同的環境適用於您啟動雲端工作階段的任何地方：

* [Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)
* [Claude 行動應用程式](https://code.claude.com/docs/zh-TW/mobile.md)
* 您的瀏覽器在 [claude.ai/code](https://claude.ai/code)
* 終端機搭配 [`claude --cloud`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#from-terminal-to-cloud)
* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)
* [Claude Tag](https://claude.com/docs/claude-tag/overview)

這些使用介面中的每一個也可以路由到 [自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)。[可用性和限制](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations) 涵蓋當 Claude Tag 工作階段在其中執行時 Claude 尚無法使用的內容。

> [!NOTE]
>
> [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段將網頁和行動介面連接到您自己機器上的工作階段，該工作階段使用您機器的網路和檔案，而不是雲端環境。若要選擇 Claude Tag 頻道使用的環境，請參閱 [設定 Claude Tag 頻道使用的環境](#set-the-environment-a-claude-tag-channel-uses)。

## Default 環境

如果您還沒有環境，上線設定會為您設定 **Default** 環境。具體方式取決於您在哪裡上線：

* **CLI 流程（例如 `/web-setup`）**：為您建立 **Default**
* **Pro、Max 和 Ultra 上的網頁上線設定**：您會自動取得 **Default**
* **Team 和 Enterprise 上的網頁上線設定**：顯示 **Create your first cloud environment** 表單，除非擁有者已開啟[快速設定](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#quick-setup-for-team-and-enterprise)；保持表單的預設值並點擊 **Create & finish** 以取得相同的 **Default** 環境

**Default** 本身不帶有任何設定：

* [**Trusted** 網路存取](#access-levels)：工作階段可以到達套件登錄檔和其他[允許清單中的網域](#default-allowed-domains)，但無法透過工作階段的網路到達其他任何內容。
* 無其他設定：**Default** 不定義任何環境變數或設定指令碼，因此工作階段只會以[預先安裝的工具](#installed-tools)開始。

只有 **Default** 可用時，每個工作階段都在其中執行。當您有多個環境時，工作階段會根據介面選擇一個：

* 在桌面應用程式、行動應用程式和 claude.ai/code 上，您自己啟動的工作階段使用[選擇器](#configure-your-environment)中顯示的環境。當您尚未選擇時，擁有者設定的[組織預設](#organization-shared-environments)會填入選擇。[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#project-settings-reference)中的執行緒改用專案設定中設定的環境。
* 從 CLI，Claude Code 使用您的 [`/remote-env` 選擇](#select-an-environment-from-the-cli)，或在您的清單有一個時回退到 Anthropic 託管的環境，否則回退到您清單中第一個不是橋接環境的環境，即 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 登錄以代表您自己的機器而非雲端環境的項目。對於[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)，在[分派工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#run-the-test-loop)時使用其 `ccpool_` ID 傳遞 `--environment <environment-id>` 會覆蓋該調用的 `/remote-env` 選擇和回退。Claude Code 拒絕傳遞給該旗標的 Anthropic 託管 `env_` ID，因此使用 `/remote-env` 來定位這些。該旗標需要 Claude Code v2.1.224 或更新版本。

當預設不夠時，請設定環境：當 Claude 需要到達[預設允許清單](#default-allowed-domains)之外的網域、需要為其工作階段設定環境變數，或需要在開始工作前安裝相依性時。

## 設定您的環境

在 [claude.ai/code](https://claude.ai/code) 上開始新工作階段的畫面中，從訊息框下方的環境選擇器新增、編輯和封存環境。若要前往該畫面，請完成 [Web 入門設定](https://code.claude.com/docs/zh-TW/web-quickstart.md)。若為 Desktop 應用程式，請參閱[雲端工作階段](https://code.claude.com/docs/zh-TW/desktop.md#cloud-sessions)。您建立的環境是您帳戶的個人環境；由擁有者建立的[共用環境](#organization-shared-environments)會與它們一起出現在選擇器中。請參閱[已安裝的工具](#installed-tools)以了解無需任何設定即可使用的工具。

選擇器只會在您傳送新工作階段的第一則訊息之前出現。若要編輯您自己執行中雲端工作階段的環境，請選擇頂端工作階段標題後方的插入號，然後選擇**編輯雲端環境**。

**1. 開啟環境選擇器**

在新工作階段畫面上，選擇訊息框下方那一列中的第一個控制項。

**2. 新增或編輯環境**

* **新增環境**：選擇選單底部的**新環境**以開啟**新環境**對話框。填寫表單並選擇**新增環境**。您的新工作階段接著會使用您新增的環境。
* **編輯環境**：在**雲端**下找到其列。如果**雲端**是單一列，請選擇它以開啟清單。如果您的環境未列在**雲端**下，請選擇該標題下的**更多**列。將滑鼠懸停在環境的列上，然後選擇其右側出現的設定圖示以開啟其對話框。

當您新增環境或編輯您自己的環境時，請選擇對話框的[**網路存取**](#network-access)、[**設定指令碼**](#add-a-setup-script)或[**環境變數**](#set-environment-variables)列以開啟該設定。完成最後一項變更後，若為新環境請以**新增環境**儲存，若為現有環境請以**儲存變更**儲存。若要儲存工作階段可使用但無法看到的金鑰，請參閱[新增網路機密](#add-network-secrets)。

### 設定環境變數

環境變數使用 `.env` 格式，每行一個 `KEY=value` 對。純值不需要引號，如果您用匹配的一對引號引用值，引號不會成為值的一部分。引用跨越多行或包含 `#` 的值：在未引用的值中，`#` 開始註解，該行的其餘部分會被捨棄。

以下範例定義三個變數。

```text theme={null}
NODE_ENV=development
LOG_LEVEL=debug
DATABASE_URL=postgres://localhost:5432/myapp
```

工作階段會將環境的值讀入普通環境變數中，Claude 執行的任何命令都可以讀取，除了 `OTEL_*` 變數。Claude Code 使用這些變數進行自己的[遙測匯出](https://code.claude.com/docs/zh-TW/monitoring-usage.md#telemetry-from-cloud-sessions-and-claude-tag)，不會將它們傳遞給它執行的命令。

在 Anthropic 託管的環境中，工作階段在您建立時讀取環境的值，以及之後每次 Claude Code 在工作階段的 VM 中啟動時讀取，這發生在兩種情況下：

* **VM 在閒置後被還原**：在幾分鐘沒有活動後，工作階段的 VM 會暫停，其檔案已儲存。您的下一條訊息會還原相同的 VM 並再次啟動 Claude Code。
* **VM 被回收並重新建立**：如果暫停的 VM 已被[回收](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#environment-expired)，重新開啟工作階段會佈建一個全新的 VM。

編輯、新增或移除變數後，Anthropic 託管環境中的現有工作階段會保留它最後讀取的值，直到其 VM 下次被還原或重新建立，然後使用您的變更。其 VM 在工作階段閒置後會自動暫停，您無法自行暫停。若要立即使用新值，請要求 Claude 在它執行的命令上設定它，例如 `LOG_LEVEL=trace npm test`，或啟動新工作階段。

雲端工作階段在啟動時也會自行設定一些變數。對於 [`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#manage-context)，工作階段設定的值會覆寫您在此新增的值，因此在此新增該鍵沒有效果。

使用該環境的任何人都可以讀取這些值。在 Anthropic 託管的環境中，對於 agent 代理伺服器可以附加到請求的金鑰，請改用[網路機密](#add-network-secrets)。[永遠不會取得機密的請求](#requests-that-never-get-the-credential)列在那裡。

### 新增網路機密

網路機密是您儲存在雲端環境上的 API 金鑰或 token，以便 Claude 可以從環境中的任何工作階段呼叫該 API，而無需看到金鑰。Anthropic 的 agent 代理伺服器會在每個請求離開工作階段的 VM 後，將金鑰新增到您列出的主機的請求中，因此金鑰本身始終保留在 VM 之外。

網路機密在 Pro、Max、Ultra、Team 和 Enterprise 方案上可用。若要確認您是否可以自行新增，請參閱[需求](#requirements)。

#### 需求

這些需求決定您是否可以新增機密，以及 agent 代理伺服器在新增後是否可以使用它：

* **角色**：在所有方案上，無論您的角色為何，都可以在自己的環境上新增和刪除機密。在 Team 和 Enterprise 上，擁有者在您的 claude.ai 組織中持有組織管理員角色，管理員則沒有，這會改變您在以下情況中看到的內容：
  * **您自己的環境**：若沒有組織管理員角色，**新增機密**會開啟[較簡短的表單](#add-a-secret-without-the-role)
  * **共用環境**：擁有者從管理設定[新增和刪除其機密](#add-a-credential)。若沒有組織管理員角色，請擁有者新增機密，因為該環境的對話框沒有**網路機密**區段
* **環境類型**：已存在的 Anthropic 託管雲端環境。[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)沒有網路機密
* **API 可達性**：API 接受來自網際網路的連線，因為請求來自 Anthropic 的網路
* **加密金鑰**：如果您的組織使用客戶管理的加密金鑰，您無法儲存網路機密

#### 新增機密

您一次新增一個機密。若要變更機密的主機或值，請刪除它並再次新增。

若要將機密新增到[共用環境](#organization-shared-environments)，請從[管理設定](https://claude.ai/admin-settings)中的**雲端環境**頁面開啟該環境進行編輯，然後在其**網路機密**區段中從步驟 2 繼續。如果您使用 Team 或 Enterprise 方案且未持有[組織管理員角色](#requirements)，請在您自己的環境上執行步驟 1，然後[填寫較簡短的表單](#add-a-secret-without-the-role)。

**1. 開啟環境的網路機密**

在 [claude.ai/code](https://claude.ai/code) [開啟環境進行編輯](#configure-your-environment)。在**編輯雲端環境**對話框中，選擇**網路機密**列。您會看到環境上已有的機密，每個都顯示它適用的主機。

**2. 新增機密**

選擇**新增機密**（在管理設定中標示為**新增**）並填寫表單。保留預設的**機密類型** **Bearer**，用於在請求標頭中傳輸的 API 金鑰，並填寫這些欄位：

* **名稱**：機密的標籤，例如 `Internal billing API`
* **允許的網站**：API 的主機，例如 `api.example.com`。前導 `*.` 符合每個子網域
* **自訂標頭**：標頭的一列，該標頭攜帶金鑰。該列以 `Authorization` 作為標頭的**名稱**和 `Bearer` 作為其**前綴**開始；將金鑰本身貼上為**值**。對於採用裸值的標頭（如 `X-Api-Key`），變更名稱並清除前綴

對於以其他方式進行身分驗證的 API，請選擇不同的**機密類型**。清單與 [Claude Tag](https://claude.com/docs/claude-tag/overview)（Team 和 Enterprise 方案的 Slack 整合）為[連線](https://claude.com/docs/claude-tag/admins/add-connections)提供的清單相同。

**3. 儲存機密**

選擇**新增**。機密連同其主機出現在清單中，無需對話框的**儲存變更**按鈕即已儲存。儲存後，您無法再次檢視該值。

若要確認機密有效，請在環境中啟動工作階段並要求 Claude 呼叫 API，例如使用 `curl`。API 的回應就像金鑰在請求中一樣，金鑰不會出現在工作階段的環境變數或任何檔案中。如果清單將機密標記為**未傳送**，其下方的註記會說明原因和解決方法。兩個主機重疊但不完全相符的機密不會獲得標記，agent 代理伺服器只會傳送其中一個。

#### 沒有組織管理員角色時新增機密

如果您使用 Team 或 Enterprise 方案且未持有[組織管理員角色](#requirements)，**新增機密**表單只接受一個主機的一個機密。選擇您環境的[**網路機密**列](#add-a-credential)，然後選擇**新增機密**。填寫這些欄位，然後選擇表單的**新增機密**按鈕：

* **主機**：取得機密的單一主機，例如 `api.example.com`。表單不接受 `*.` 萬用字元
* **名稱**：機密的選用標籤
* **機密類型**：**Token** 用於在請求標頭中傳輸的金鑰，或選擇**使用者名稱和密碼**。若為 token，請將金鑰貼上為**值**

#### 哪些請求會取得機密

當請求的主機符合您在該機密上列出的主機之一時，agent 代理伺服器會將機密附加到請求。工作階段可以到達這些主機，即使環境的[網路存取層級](#access-levels)否則不允許，除了[永遠不會取得機密的主機](#requests-that-never-get-the-credential)。機密適用於在環境中執行的每個工作階段，無論誰啟動它，直到您刪除它。

#### 永遠不會取得機密的請求

agent 代理伺服器永遠不會將您新增的機密附加到這些請求：

* **GitHub**：[GitHub 代理伺服器](#github-proxy)改為驗證對 GitHub 的請求，因此您不需要為其提供網路機密
* **Anthropic API 和公開套件登錄**：`api.anthropic.com`、`registry.npmjs.org`、`jsr.io`、`npm.jsr.io`、`pypi.org`、`files.pythonhosted.org`、`index.crates.io` 和 `proxy.golang.org`
* **設定指令碼請求**：Claude Code 在啟動時連線到 agent 代理伺服器，這發生在[設定指令碼](#setup-scripts)執行之後
* **Claude Code 的遙測匯出**：Claude Code 自行傳送其[遙測匯出](https://code.claude.com/docs/zh-TW/monitoring-usage.md#telemetry-from-cloud-sessions-and-claude-tag)，而不是透過它執行的命令，該請求不會通過 agent 代理伺服器

### 從 CLI 選擇環境

在您的終端機中執行 `/remote-env` 以選擇您從 CLI 建立的雲端工作階段的預設環境，例如 [`claude --cloud`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#from-terminal-to-cloud)。該命令開啟現有環境的選擇器，並將您的選擇儲存到[使用者設定](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中的 `remote.defaultEnvironmentId` 鍵，因此它適用於您機器上的每個專案，直到您變更它，除非在更高優先順序的[設定層級](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)（例如儲存庫的專案設定）上設定相同的鍵。

[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments) ID（形式為 `ccpool_...`）遵循更嚴格的來源規則。請參閱 [`remote.defaultEnvironmentId`](https://code.claude.com/docs/zh-TW/settings-reference#remote-defaultenvironmentid) 以了解 Claude Code 從哪些設定層級接受它。

`/remote-env` 只設定預設值：它不啟動工作階段，也無法新增或編輯環境。從[環境選擇器](#configure-your-environment)管理它們。

### 封存環境

若要封存您自己的環境之一，請開啟它進行編輯，選擇**封存環境**，然後確認。如果該環境已[與您的組織共用](#organization-shared-environments)，則改由擁有者從[管理設定](https://claude.ai/admin-settings)中的**雲端環境**頁面封存，因此除非您本身是擁有者，否則請詢問擁有者。

封存會影響新工作階段，而不是執行中的工作階段：

* 已在環境中執行的工作階段會繼續工作。
* 環境從選擇器和 `/remote-env` 中消失，因此您無法為新工作階段選擇它。
* 環境上的網路機密在其執行中的工作階段中保持附加。在封存前刪除您不再需要的任何機密。
* 在任何使用介面上，都沒有新工作階段可以在封存的環境中啟動：
  * **已儲存的 CLI 預設**：如果環境是您儲存的 [CLI 預設](#select-an-environment-from-the-cli)，當您的清單有 Anthropic 託管環境時，Claude Code 會在其中啟動 CLI 雲端工作階段。否則，會在清單中第一個不是 [Remote Control 橋接環境](#the-default-environment)的環境中啟動。
  * **明確設定**：任何明確設定使用該環境的項目，例如[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md#environments-and-network-access)，無法在其中啟動新工作階段。請將其指向另一個環境。

當您不再需要某個 Anthropic 託管環境時，請將其封存。環境對話框和**雲端環境**管理頁面都沒有刪除 Anthropic 託管環境的選項。如果該環境是[自託管](https://code.claude.com/docs/zh-TW/self-hosted-environments)的，擁有者可以從管理設定中的**雲端環境**頁面將其刪除。如果您不是擁有者，請請擁有者將其刪除。

### 組織共用環境

在 Team 和 Enterprise 方案上，擁有者可以建立與組織的每個成員共用的雲端環境。相同的角色管理**雲端環境**管理頁面上的所有其他內容，包括[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)；管理員角色無法開啟該頁面。可以開啟它的完整角色清單是[管理伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)的角色清單。

共用環境會在每個成員的[環境選擇器](#configure-your-environment)中出現，在**組織**標題下，位於成員自己的環境之後（在**個人**標題下），因此團隊可以標準化一個設定，而不是每個成員重新建立它。選擇共用環境的設定圖示會為每個成員（包括擁有者）開啟其設定的唯讀摘要。

擁有者以兩種方式之一將環境提供給組織：

* **建立共用環境**：使用[管理設定](https://claude.ai/admin-settings)中的**雲端環境**頁面，這也是擁有者編輯和封存共用環境的地方。每個都有一個名稱、一個[網路存取層級](#access-levels)、`.env` 格式的[環境變數](#set-environment-variables)和一個[設定指令碼](#setup-scripts)。
* **共用個人環境**：在環境選擇器中開啟您自己的環境之一進行編輯，然後從**誰可以使用它**列共用它。環境保留其 ID，因此已使用它的工作階段和排程任務不受影響，每個成員都可以看到它並在其中啟動工作階段。

擁有者在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 分別選擇組織的[預設環境](#the-default-environment)。

若要為共用環境的工作階段提供它們無法讀取的金鑰，請在**雲端環境**頁面編輯該環境時新增[網路機密](#add-network-secrets)。不要在其變數中包含機密，因為每個成員的工作階段都會讀取它們。

### 設定 Claude Tag 頻道使用的環境

在 [Claude Tag](https://claude.com/docs/claude-tag/overview) 頻道中，Claude 作為您組織的共用身分工作，而不是任何成員，因此頻道工作階段只使用組織層級的環境，即共用環境或[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)。若要為頻道提供不是[預先安裝](#installed-tools)的工具鏈（例如 .NET），擁有者可以從**雲端環境**管理頁面建立[共用環境](#organization-shared-environments)，其中包含安裝它的[設定指令碼](#setup-scripts)。以兩種方式之一將頻道指向環境：

* 在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 將共用或自託管環境設定為組織的[預設環境](#the-default-environment)。
* 在 Claude Tag 管理設定中[將其釘選到頻道](https://claude.com/docs/claude-tag/admins/troubleshooting#channel-sessions-use-the-wrong-environment-or-can%E2%80%99t-find-one)。

## 網路存取

每個環境設定一個網路存取層級，控制其工作階段可以進行的出站連線。預設層級 **Trusted** 允許套件登錄和其他[允許清單中的網域](#default-allowed-domains)；**Custom** 採用您自己的網域清單。

若要變更環境的網路存取，[開啟它進行編輯](#configure-your-environment)並在對話框中使用 **Network access** 選擇器。[共用環境](#organization-shared-environments)在該處以唯讀方式開啟，因此擁有者改為從[管理設定](https://claude.ai/admin-settings)中的 **Cloud environments** 頁面變更其網路存取。開啟選擇器的控制項出現在[預設環境](#the-default-environment)下列出的應用程式使用介面上，以及在[雲端排程任務編輯器](https://code.claude.com/docs/zh-TW/routines.md#environments-and-network-access)中。個人環境在您的 claude.ai 帳戶設定中沒有單獨的頁面。

當您變更 Anthropic 託管環境的網路存取時，其現有工作階段在約一分鐘內遵循新設定，用於通過工作階段的[網路允許清單](#access-levels)的請求。您不需要啟動新的工作階段。

> [!NOTE]
>
> 您在工作階段或排程任務上啟用的 MCP 連接器無需將其主機新增到 **Allowed domains**，因為連接器流量通過 Anthropic 的伺服器而不是工作階段的網路。這依賴於[安全性和隔離](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#security-and-isolation)下提到的相同 Anthropic 繫結通道。關閉任何您不需要的連接器，以限制 Claude 可以到達的工具。

### 存取層級

[環境對話框](#configure-your-environment)中的 **Network access** 欄位採用以下四個層級之一：

| 層級 | 出站連線 |
| :- | :- |
| **None** | 透過工作階段網路沒有出站網路存取 |
| **Trusted** | 僅[允許清單中的網域](#default-allowed-domains)：套件登錄、GitHub、雲端 SDK |
| **Full** | 任何網域 |
| **Custom** | 您自己的允許清單，可選擇包括預設值 |

無論您選擇哪個層級，工作階段仍然可以到達這些，因為每個都採用不通過工作階段網路允許清單的路徑：

* GitHub，透過其[單獨的代理伺服器](#github-proxy)
* 您啟用的 [MCP 連接器](#network-access)，其流量通過 Anthropic 的伺服器
* 您在環境的[網路密鑰](#add-network-secrets)上列出的主機，除了[永遠不會取得密鑰的主機](#requests-that-never-get-the-credential)
* Anthropic API，用於 Claude Code 自己的請求，即使在 **None** 時，如[安全性和隔離](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#security-and-isolation)下所述

### 允許特定網域

若要允許不在 Trusted 清單中的網域，在環境的網路存取設定中選擇 **Custom**，然後在 **Allowed domains** 欄位中每行列出一個網域。此範例允許內部專案可能需要的三個主機。

```text theme={null}
api.example.com
*.internal.example.com
registry.example.com
```

此環境中的工作階段現在可以到達 `api.example.com`、`internal.example.com` 的任何子網域和 `registry.example.com`，以及透過工作階段網路沒有其他網域。[GitHub 流量](#github-proxy)、[MCP 連接器流量](#network-access)和對環境[網路密鑰](#add-network-secrets)主機的請求（除了[永遠不會取得密鑰的主機](#requests-that-never-get-the-credential)）不通過此允許清單。前導 `*.` 符合每個子網域。若要也保留[Trusted 網域](#default-allowed-domains)，請勾選 **Also include default list of common package managers**；取消勾選以僅允許您列出的內容。

如果您的組織使用 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md#availability)，工作階段讀取它們不需要 `*.frame.claudeusercontent.com` 在清單中。當清單省略該主機時，Claude Code 改為透過工作階段與 Anthropic 的連線讀取 artifact 內容。在兩種情況下將主機保留在允許清單中：

* **此環境中的工作階段開啟另一個組織的公開 artifact**：Claude Code 直接從主機擷取這些，因此將其新增到此清單。
* **您正在設定本機 CLI 或自託管執行器**：將主機保留在該允許清單中。請參閱[網路存取需求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)和自託管[網路需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#network-requirements)。

每個環境都有自己的允許網域清單；沒有組織層級的允許清單，管理員可以推送到每個成員的環境。沒有[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)將網域新增到環境的網路允許清單。若要為團隊提供一個標準清單，擁有者可以建立一個具有 **Custom** 網路存取和該清單的[組織共用環境](#organization-shared-environments)。

### GitHub 代理伺服器

在 Anthropic 託管的環境中，所有 GitHub 操作都通過專用代理伺服器進行，該代理伺服器將您的真實 GitHub 憑證保留在工作階段的 VM 外，獨立於環境的[存取層級](#access-levels)。自託管環境中的工作階段使用您的部署提供的憑證進行 git 操作驗證；[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git) 涵蓋選項，包括每個工作階段鑄造的憑證和選擇加入此相同代理伺服器。代理伺服器提供：

* **Git 憑證**：VM 內的 git 用戶端使用範圍憑證，代理伺服器驗證並將其交換為您的實際 GitHub token。
* **API 請求**：來自內建 GitHub 工具的請求，以及來自 [`proxy-injected` 預留位置](#work-with-github-issues-and-pull-requests)下的 `gh` 的請求，使用您的真實憑證進行。
* **推送限制**：代理伺服器會拒絕分支刪除，以及推送分支以外的任何內容（例如標籤）。它不限制推送可以更新哪些分支。若要進行此限制，請在 GitHub 上使用分支保護規則或規則集。
* **儲存庫範圍**：代理伺服器為附加到工作階段的儲存庫提供 GitHub API 請求服務。針對其他儲存庫的 API 請求會收到 403，其訊息以 `GitHub access to` 開頭並包含 `is not enabled for this session`。當儲存庫未附加時，您透過 `github.com/{owner}/{repo}/archive/` 或 `codeload.github.com` URL 擷取的原始碼封存檔也會收到相同的 403，即使是公開儲存庫也一樣。
* **GraphQL 限制**：代理伺服器會以 403 拒絕對 GitHub GraphQL 端點的請求，其訊息以 `GitHub GraphQL is not available from Claude Code sessions` 開頭，並指出 REST 備援 `gh api repos/{owner}/{repo}/...`。使用 GraphQL 的 `gh` 子命令（例如 `gh pr` 和 `gh issue`）會收到相同的 403。限制適用於通過代理伺服器的每個請求，無論您提供的憑證如何，因此您設定的 `GH_TOKEN` 會收到相同的 403。Claude 無法通過代理伺服器到達僅存在於 GraphQL 中的 GitHub API，例如 Projects v2。

來自公開儲存庫的已提交檔案通過 `raw.githubusercontent.com` 到達，[安全代理伺服器](#security-proxy)改為處理。該網域在預設[Trusted 清單](#default-allowed-domains)中，因此除非環境的[存取層級](#access-levels)排除它，否則這些檔案保持可到達。

### 安全代理伺服器

Anthropic 託管環境中的雲端工作階段在 HTTP/HTTPS 網路代理伺服器後面執行，用於安全和濫用防止目的；在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#default-deny-egress)中，出站流量改為通過您自己的網路邊界。來自 Anthropic 託管工作階段的所有出站網際網路流量都通過此代理伺服器，該代理伺服器提供：

* 防止惡意請求
* 速率限制和濫用防止

## 雲端工作階段中可用的功能

在 Anthropic 代管的環境中，每個工作階段都會取得一個執行 Ubuntu 24.04 on x86\_64 的全新虛擬機器 (VM)，無論您自己的作業系統和 CPU 架構為何，您的儲存庫已複製且常見工具鏈已預先安裝。當相依套件提供預編譯的二進位檔案（例如具有原生擴充功能的 Ruby gems 或預先建置的 Python wheels）時，請使用其 x86\_64 Linux 建置以符合 VM。本節涵蓋 Anthropic 代管的預設值、內建的 GitHub 工具、如何[執行測試和服務](#run-tests-start-services-and-add-packages)、每個 VM 取得的[資源限制](#resource-limits)，以及[時間限制](#time-limits)對長時間執行的工作。

> [!NOTE]
>
> 您的組織路由到[自我代管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的工作階段改為在您自己的執行器上執行，使用您的執行器映像提供的工具。

### 從您的設定中保留的內容

> [!NOTE]
>
> 在此表中的儲存庫設定中，[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)中的雲端對話串只會載入儲存庫根目錄的 `CLAUDE.md`、`.claude/CLAUDE.md`，以及非[路徑特定](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)的 `.claude/rules/` 檔案。請參閱[對話串會從您的儲存庫中取得哪些內容](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)。

雲端工作階段從您儲存庫的全新複製開始。您提交到儲存庫的任何內容都可用。您只在自己的機器上安裝或設定的任何內容在工作階段中都不可用。您的組織政策透過[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)單獨到達。

| | 在雲端工作階段中可用 | 原因 |
| :- | :- | :- |
| 您儲存庫的 `CLAUDE.md` | 是 | 複製的一部分 |
| 您儲存庫的 `.claude/settings.json` hook 和權限規則 | 是，在具有一個儲存庫的工作階段中 | 複製的一部分。對於具有多個儲存庫的工作階段，請參閱[它讀取哪些設定](https://code.claude.com/docs/zh-TW/settings.md#settings-in-cloud-sessions) |
| 您儲存庫的 `.mcp.json` MCP 伺服器 | 是，在具有一個儲存庫的工作階段中 | 複製的一部分，從工作階段的工作目錄中找到。對於自我代管環境，請參閱[套用哪個儲存庫的設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#repository-settings-in-sessions-with-several-repositories) |
| 您儲存庫的 `.claude/rules/` | 是 | 複製的一部分 |
| 您儲存庫的 `.claude/skills/`、`.claude/agents/`、`.claude/commands/` | 是 | 複製的一部分 |
| 在您儲存庫的 `.claude/settings.json` 中宣告的外掛程式和市集 | 否 | 雲端工作階段不會安裝儲存庫在 [`enabledPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#enabledplugins) 下開啟的外掛程式，包括來自它在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 下列出的市集的外掛程式 |
| 您的組織的[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) | 是，除了在 [Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段中 | 在工作階段開始時從 Anthropic 的伺服器擷取。請參閱[使用介面涵蓋範圍](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)以了解 `availableModels` 如何在雲端工作階段中強制執行。透過 MDM 或受管設定檔部署到您的裝置的設定不適用，因為工作階段在 Anthropic 管理的 VM 上執行；在[自我代管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中，工作階段也會根據[Claude Code 如何結合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)讀取執行器映像中的受管設定檔 |
| 您的使用者 `~/.claude/CLAUDE.md` | 否 | 位於您的機器上，不在儲存庫中。請參閱[在不提交到儲存庫的情況下新增個人偏好設定](#add-personal-preferences-without-committing-to-the-repo) |
| 您的使用者 `~/.claude/skills/`、`~/.claude/agents/`、`~/.claude/commands/` | 否 | 位於您的機器上，不在儲存庫中。改為將它們提交到儲存庫的 `.claude/` 目錄。雲端工作階段會自動載入[您在 claude.ai 上啟用的 skill](https://code.claude.com/docs/zh-TW/skills.md#skills-in-cowork-and-cloud-sessions) |
| 僅在您的使用者設定中啟用的外掛程式 | 否 | 使用者範圍的 `enabledPlugins` 位於您機器上的 `~/.claude/settings.json` 中 |
| 您使用 `claude mcp add` 在預設本機範圍或使用者範圍新增的 MCP 伺服器 | 否 | 這些寫入您機器上的 `~/.claude.json`，不是儲存庫。使用 `claude mcp add --scope project` 新增伺服器，它會寫入儲存庫的 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope)，並提交該檔案。具有一個儲存庫的工作階段會載入它 |
| 您儲存庫的 `.claude/settings.json` `env` 區塊中的傳輸變數，例如 `NODE_EXTRA_CA_CERTS` 和[mTLS 用戶端憑證變數](https://code.claude.com/docs/zh-TW/network-config.md#mtls-authentication) | 否 | 代管環境管理工作階段的 API 連線，因此 Claude Code 會忽略這些金鑰，並在工作階段的偵錯日誌中記錄每個被忽略的金鑰 |
| Claude 呼叫的服務的 API 金鑰和 token | 在 Anthropic 代管的環境中，作為[網路機密](#add-network-secrets) | 您在環境上新增金鑰一次，agent 代理伺服器會將其附加到您列出的主機的請求。agent 代理伺服器[無法附加](#requests-that-never-get-the-credential)的金鑰保留在環境變數中 |
| 像 AWS SSO 這樣的互動式驗證 | 否 | 不支援。SSO 需要無法在雲端工作階段中執行的瀏覽器型登入 |

若要在雲端工作階段中提供您自己的設定，請將其提交到儲存庫。

任何使用環境的人都可以讀取其環境變數和設定指令碼。**環境變數**下的對話方塊註記會說明這一點，並警告不要在那裡放置機密。在 Anthropic 代管的環境中，改為將 agent 代理伺服器可以附加的金鑰儲存為[網路機密](#add-network-secrets)。

#### 在不提交到儲存庫的情況下新增個人偏好設定

在 Anthropic 代管的環境中，新增一個寫入 `~/.claude/CLAUDE.md` 的[設定指令碼](#setup-scripts)，用於存放您不想放入共用儲存庫的偏好設定。Claude Code 會在工作階段中將該檔案載入為[使用者指令](https://code.claude.com/docs/zh-TW/memory.md#choose-where-to-put-claude-md-files)。此範例設定了提交訊息的偏好：

```bash theme={null}
#!/bin/bash
mkdir -p ~/.claude
cat > ~/.claude/CLAUDE.md <<'EOF'
Use conventional commit messages.
EOF
```

請將指令碼放在您自己的其中一個環境上，而不是[共用環境](#organization-shared-environments)。

在下一個雲端工作階段中執行 `/context`，並確認 `/root/.claude/CLAUDE.md` 出現在 **Memory files** 下。

### 已安裝的工具

雲端工作階段預先安裝了常見的語言執行時、建置工具和資料庫。下表按類別總結了包含的內容。

| 類別 | 包含 |
| :- | :- |
| **Python** | Python 3.x with pip、poetry、uv、black、mypy、pytest、ruff |
| **Node.js** | 20、21 和 22，with npm、yarn、pnpm、bun¹、eslint、prettier、chromedriver |
| **Ruby** | 3.1、3.2、3.3 with gem、bundler、rbenv |
| **PHP** | 8.3 with Composer |
| **Java** | OpenJDK 21 with Maven and Gradle |
| **Go** | Go with module support |
| **Rust** | rustc and cargo |
| **C/C++** | GCC、Clang、cmake、ninja、conan |
| **Docker** | docker、dockerd、docker compose |
| **Databases** | PostgreSQL 16、Redis 7.0 |
| **Browser** | Chrome for Testing，位於 `/usr/bin/google-chrome`，並將 `CHROME_PATH` 環境變數設定為該路徑 |
| **Utilities** | git、gh、jq、yq、ripgrep、tmux、vim、nano |

¹ Bun 已安裝，但在套件擷取時有已知的[代理伺服器相容性問題](#install-dependencies-with-a-sessionstart-hook)。

若要取得此表中大多數工具的版本，請要求 Claude 在雲端工作階段中執行 `check-tools`。這是安裝在工作階段 VM 上的 shell 命令，不是您使用 `/` 輸入的命令；您要求 Claude 是因為 [Claude 為您執行所有 VM 命令](#run-tests-start-services-and-add-packages)。對於它不報告的工具，例如 Ruby、PHP、bun、PostgreSQL 或 Redis，請要求 Claude 執行該工具自己的版本命令，例如 `psql --version`。

Node.js 版本安裝在 `/opt/node20`、`/opt/node21` 和 `/opt/node22`，預設情況下 22 在 `PATH` 上。若要使用不同的版本，請要求 Claude 將該版本的 `bin` 目錄（例如 `/opt/node20/bin`）前置到 `PATH`。

此清單外的工具鏈（例如 .NET SDK）即使其套件登錄在[預設允許清單](#default-allowed-domains)上也不會預先安裝。使用[設定指令碼](#setup-scripts)安裝它們。

### 使用 GitHub issue 和 pull request

雲端工作階段包括內建的 GitHub 工具，讓 Claude 可以讀取 issue、列出 pull request、擷取差異和發佈評論，無需任何設定。這些工具透過 [GitHub 代理伺服器](#github-proxy)進行身分驗證，使用您在 [GitHub 驗證選項](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#github-authentication-options)下設定的任何方法，因此您的 token 永遠不會進入容器。

您可以在[環境設定](#set-environment-variables)中自己設定 `GH_TOKEN` 或 `GITHUB_TOKEN`，或將兩者都保留未設定，讓 [GitHub 代理伺服器](#github-proxy)為您進行身分驗證：

* 如果您設定了 token，它會原封不動地傳遞到容器，因此您的指令碼和 GitHub 的 [`gh` CLI](https://cli.github.com) 會直接使用它。
* 如果您都沒有設定，且 [GitHub 代理伺服器](#github-proxy)正在為您的工作階段處理身分驗證，兩個變數在 Claude 執行的命令中都讀取為佔位符字串 `proxy-injected`，代理伺服器會在出站 GitHub 請求上替換您的真實憑證。針對已附加儲存庫的 `gh api` 呼叫無需您自己的 token 即可運作，但直接讀取 `GITHUB_TOKEN` 的指令碼會取得佔位符，而不是可用的 token。

您設定的 token 是一個普通的環境變數，因此任何使用環境的人都可以讀取它；代理伺服器路徑將憑證保留在環境設定和工作階段 VM 之外。

若要檢查哪種情況適用於您的工作階段，請要求 Claude 執行 `echo $GH_TOKEN`。

GitHub 的 [`gh` CLI](https://cli.github.com) 已預先安裝。如果您需要內建工具未涵蓋的 GitHub 操作，請要求 Claude 使用 `gh api` 呼叫 REST API。使用 REST API 的 `gh` 子命令（例如 `gh workflow list`）也能運作。代理伺服器會[拒絕使用 GraphQL 的子命令](#github-proxy)，例如 `gh pr` 和 `gh issue`。`gh` 會自動讀取 `GH_TOKEN`，因此您不需要執行 `gh auth login`。

### 將輸出連結回工作階段

每個雲端工作階段在 claude.ai 上都有一個逐字稿 URL，工作階段可以從 `CLAUDE_CODE_REMOTE_SESSION_ID` 環境變數讀取其自己的 ID。使用此功能在 PR 主體、提交訊息、Slack 貼文或產生的報告中放置可追蹤的連結，以便審查者可以開啟產生它們的執行。

Claude 在雲端工作階段中建立的提交包括 `Claude-Session: <url>` git trailer，PR 主體包括工作階段 URL 在其自己的行上。若要省略 trailer 和 PR 主體連結，請將 [`attribution.sessionUrl`](https://code.claude.com/docs/zh-TW/settings-reference#attribution-sessionurl) 設定為 `false`。

若要在提交或 PR 以外的內容中包含工作階段連結，例如 Claude 發佈的 Slack 訊息或它寫入的報告檔案，請讓 Claude 執行以下命令並使用其輸出。該命令將環境變數值中的 `cse_` 前置詞轉換為逐字稿 URL 預期的 `session_` 前置詞：

```bash theme={null}
echo "https://claude.ai/code/${CLAUDE_CODE_REMOTE_SESSION_ID/#cse_/session_}"
```

### 執行測試、啟動服務和新增套件

您無法進入工作階段 VM 的 shell。Claude 為您執行每個命令，因此請將本節中的工作表述為提示詞中的請求。

#### 執行測試

Claude 會在處理工作時執行測試。在您的提示詞中要求它，例如「修復 `tests/` 中失敗的測試」或「在每次變更後執行 pytest」。隨[預先安裝的工具鏈](#installed-tools)提供的測試執行器（例如 pytest 和 cargo test）無需額外設定即可運作。您的專案宣告為相依性的執行器（例如 jest）會隨您的相依套件一起安裝。

#### 啟動服務

PostgreSQL 和 Redis 已預先安裝，但預設情況下不執行。要求 Claude 啟動您需要的任何一個；它執行的命令是：

```bash theme={null}
service postgresql start
```

```bash theme={null}
service redis-server start
```

Docker 可用於執行容器化服務。要求 Claude 執行 `docker compose up` 以啟動您專案的服務。拉取映像的網路存取遵循您環境的[存取層級](#access-levels)，[受信任的預設值](#default-allowed-domains)包括 Docker Hub 和其他常見登錄。

如果您的映像很大或拉取速度很慢，請將 `docker compose pull` 或 `docker compose build` 新增到您的[設定指令碼](#setup-scripts)。[環境快取](#environment-caching)會保留拉取的映像，因此每個新工作階段都會在磁碟上擁有它們。快取只儲存檔案，不儲存執行中的程序，因此 Claude 仍會在每個工作階段中啟動容器。

#### 新增套件

若要新增未預先安裝的套件，請使用[設定指令碼](#setup-scripts)。[環境快取](#environment-caching)會保留指令碼安裝的內容，因此您在那裡安裝的套件在每個工作階段開始時都可用，無需每次重新安裝。您也可以要求 Claude 在工作階段中期安裝套件，但這些安裝不會延續到其他工作階段。

### 資源限制

Anthropic 代管環境中的雲端工作階段執行時具有可能隨時間變化的近似資源上限：

* 4 vCPU
* 16 GB 的 RAM
* 30 GB 的磁碟

VM 可能會停止需要明顯更多記憶體的工作，例如大型建置工作或記憶體密集型測試。對於超出這些限制的工作負載，請使用 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 在您自己的硬體上執行 Claude Code，或在[自我代管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中執行雲端工作階段，該環境位於您的組織操作的計算上。

### 時間限制

在 Anthropic 代管環境中，這些時間限制適用於雲端工作階段中的長時間執行工作，例如建置、安裝或測試執行。每個項目都連結到定義限制的部分。

* **Claude 執行的命令**：雲端環境不會設定自己的命令逾時，因此 Bash 工具的預設值適用。Claude 預設等待前景命令 2 分鐘，最多可要求 10 分鐘。

  當命令達到其[逾時](https://code.claude.com/docs/zh-TW/tools-reference.md#timeout-and-output-limits)時，Claude Code [將其移到背景](https://code.claude.com/docs/zh-TW/tools-reference.md#foreground-commands-that-move-to-the-background)，而不是停止它，除非命令以 `sleep` 開頭。以這種方式移動的命令可以繼續執行最多 30 分鐘，然後 Claude Code 在其[背景時間限制](https://code.claude.com/docs/zh-TW/tools-reference.md#time-limit-for-background-commands)處停止它。將 `BASH_DEFAULT_TIMEOUT_MS` 設定為 `1800000` 毫秒以上會延長該限制以及前景預設值。
* **SessionStart hook**：Claude Code 在 600 秒後取消 `command` hook，除非您在 hook 項目上設定 [`timeout`](https://code.claude.com/docs/zh-TW/hooks#common-fields)（以秒為單位）。Claude Code 不會對您使用 [`async: true`](https://code.claude.com/docs/zh-TW/hooks#run-hooks-in-the-background) 執行的 hook 強制執行逾時。
* **設定指令碼**：花費超過大約五分鐘的指令碼不會被快取。[指令碼需求](#script-requirements)涵蓋如何保持在該時間以下。
* **閒置工作階段**：在幾分鐘沒有活動後，工作階段的 VM 會暫停並保存其檔案，稍後可以回收暫停的 VM。[設定環境變數](#set-environment-variables)描述工作階段在每種情況下會取得什麼，[環境已過期](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#environment-expired)涵蓋如何重新開啟其 VM 已被回收的工作階段。

若要提高環境工作階段的命令逾時，請將 [`BASH_DEFAULT_TIMEOUT_MS` 和 `BASH_MAX_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 新增到其[環境變數](#set-environment-variables)。兩者都採用毫秒。例如，`BASH_DEFAULT_TIMEOUT_MS=600000` 使 10 分鐘成為預設值。

## 設定指令碼

設定指令碼是一個 Bash 指令碼，在新的雲端工作階段啟動時執行，在 Claude Code 啟動之前執行。使用設定指令碼來安裝相依性、設定工具，或取得工作階段需要但未預先安裝的任何內容。

指令碼以 root 身份在 Ubuntu 24.04 上執行，因此 `apt install` 和大多數語言套件管理員都能運作。

### 新增設定指令碼

若要將設定指令碼新增至您自己的環境，可以輸入或貼上指令碼，或載入 `setup.sh` 等文字檔。[新增或編輯環境](#configure-your-environment)，然後選取 **Setup script** 列。在開啟的方塊中輸入指令碼，或選取 **Choose file**，以最大 64 KB 的檔案文字取代方塊中的內容。接著選取 **Add environment** 或 **Save changes**。

此範例安裝 [ShellCheck](https://www.shellcheck.net/)，這不是預先安裝的。

```bash theme={null}
#!/bin/bash
apt update && apt install -y shellcheck
```

### 指令碼需求

設定指令碼有四個限制條件需要考慮：

* **Exit zero**：如果指令碼以非零狀態結束，工作階段將無法啟動。在非關鍵命令後附加 `|| true`，以便間歇性安裝失敗不會阻止工作階段。
* **在五分鐘內完成**：將指令碼的總執行時間保持在大約五分鐘以內，以便[環境快取](#environment-caching)可以建立。當設定耗時超過五分鐘時，環境不會被快取。使用 `&` 和 `wait` 並行執行獨立安裝，並將任何無法納入的單一下載移至[SessionStart hook](#setup-scripts-vs-sessionstart-hooks)，在背景中啟動它。如果新工作階段在設定期間停滯或失敗，請參閱[新工作階段在設定期間掛起或逾時](https://code.claude.com/docs/zh-TW/web-quickstart.md#new-sessions-hang-or-time-out-during-setup)。
* **安裝的網路存取**：套件安裝需要連接到登錄檔。預設的 **Trusted** 層級涵蓋[常見套件登錄檔](#default-allowed-domains)，包括 npm、PyPI、RubyGems 和 crates.io；使用 **None** 網路存取時，安裝會失敗。
* **環境的變數尚未設定**：指令碼會在工作階段設定環境的[環境變數](#set-environment-variables)之前執行。請在指令碼本身中設定指令碼所需的任何值。

### 環境快取

設定指令碼在您第一次在環境中啟動工作階段時執行。當設定在[大約五分鐘](#script-requirements)內完成時，Anthropic 會快照檔案系統，並將該快照重複用作後續工作階段的起點。新工作階段會以您的相依性、工具和 Docker 映像已在磁碟上開始，並跳過設定指令碼步驟。即使指令碼安裝大型工具鏈或拉取容器映像，這也能保持啟動速度快。如果設定耗時超過大約五分鐘，環境不會被快取。

快取是檔案系統快照，因此它會保留設定指令碼寫入磁碟的內容，並丟失任何僅在執行中的內容。您安裝的套件、您拉取的 Docker 映像和您寫入的檔案都會保留。指令碼啟動的資料庫、`docker compose up` 堆疊或任何其他背景程序不會；透過詢問 Claude 或使用 [SessionStart hook](#setup-scripts-vs-sessionstart-hooks) 在每個工作階段啟動這些。

當您變更環境的設定指令碼或允許的網路主機時，以及當快取在大約七天後達到過期時，設定指令碼會再次執行以重建快取。在 Anthropic 託管環境中，當工作階段的 VM 在[閒置後恢復](#set-environment-variables)時，設定指令碼不會執行，因此對指令碼的變更只有在其 VM 被[回收](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#environment-expired)並重建時才會到達現有工作階段。若要立即套用變更，請在工作階段中執行命令或啟動新工作階段。

您不需要自己啟用快取或管理快照。

### 設定指令碼與 SessionStart hooks

使用設定指令碼來佈建 VM 本身：未[預先安裝](#installed-tools)的工具鏈和 CLI 工具。使用 [SessionStart hook](https://code.claude.com/docs/zh-TW/hooks.md#sessionstart) 進行應在各處執行的專案設定，雲端和本機，例如 `npm install`。

設定指令碼和 SessionStart hooks 在雲端工作階段啟動時按固定順序執行。下表比較您在哪裡設定它們、何時執行以及在哪裡執行。

| | 設定指令碼 | SessionStart hooks |
| - | - | - |
| **您在哪裡設定它們** | [claude.ai/code](https://claude.ai/code) 的環境對話框，加上[共用環境](#organization-shared-environments)的 **Cloud environments** 管理頁面 | [設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)，例如您的儲存庫的 `.claude/settings.json`；請參閱[您的設定中保留的內容](#what-carries-over-from-your-setup)，了解哪些檔案到達雲端工作階段 |
| **它們何時執行** | 在 Claude Code 啟動之前，當存在[快取環境](#environment-caching)時跳過 | 在 Claude Code 啟動後，在每個工作階段（包括已恢復的工作階段）上 |
| **它們在哪裡執行** | 僅限雲端工作階段 | 本機和雲端工作階段 |

如果您在使用者層級 `~/.claude/settings.json` 中有 SessionStart hooks，不要期望它們在雲端中：使用者層級設定保留在您的機器上。其他 hooks 執行的位置取決於工作階段執行的位置：

* **Anthropic 託管環境**：Claude Code 執行來自您組織的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的 hooks，並且在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串之外，也執行來自儲存庫的 hooks。[Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段不會接收伺服器管理設定，因此來自伺服器管理設定的 hooks 不會在那裡執行。
* **[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#permissions-and-tool-approval)**：Claude Code 也執行操作員從執行器主機的 `~/.claude/` 中植入的 hooks，以及執行器映像的受管設定檔中的 hooks，當該檔案是 Claude Code 應用的[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)之一時。

### 使用 SessionStart hook 安裝相依性

若要僅在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串之外的雲端工作階段中安裝相依性，請將 SessionStart hook 與檢查其執行位置的指令碼配對。

首先，將 SessionStart hook 新增至您的儲存庫的 `.claude/settings.json`。此設定告訴 Claude Code 在工作階段啟動或恢復時執行儲存庫中的 `scripts/install_pkgs.sh`：

```json theme={null}
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR\"/scripts/install_pkgs.sh"
          }
        ]
      }
    ]
  }
}
```

`matcher` 將 hook 限制為 `startup` 和 `resume` 事件，`$CLAUDE_PROJECT_DIR` 解析為儲存庫根目錄，因此 hook 無論工作階段的工作目錄如何都能找到指令碼。

接下來，在 `scripts/install_pkgs.sh` 建立指令碼。它在雲端外立即結束，然後安裝您的相依性。當 `package.json`、`package-lock.json` 和指令碼本身自上次成功安裝以來都未變更時，它會跳過 `npm install`：

```bash theme={null}
#!/bin/bash

if [ "$CLAUDE_CODE_REMOTE" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR" || exit 1
hashes=node_modules/.install_pkgs.sha256

if ! sha256sum --check --status "$hashes" 2>/dev/null; then
  # Delete the old hashes first, so a failed install runs again next time
  rm -f "$hashes"
  if npm install; then
    sha256sum scripts/install_pkgs.sh package.json package-lock.json > "$hashes" || rm -f "$hashes"
  fi
fi

# pip skips requirements that are already satisfied
pip install -r requirements.txt
exit 0
```

`CLAUDE_CODE_REMOTE` 檢查是將安裝限制在雲端工作階段的原因：工作階段 VM 的環境將該變數設為 `true`，本機上永遠不會是 `true`，因此在您的筆記型電腦上，指令碼在安裝任何內容之前結束。

若要確認 `npm install` 已成功，請啟動雲端工作階段並要求 Claude 顯示 `node_modules/.install_pkgs.sha256`。該檔案會列出這三個檔案各自的雜湊值。如果該檔案不存在，請要求 Claude 執行 `npm install` 並回報錯誤。

> [!NOTE]
>
> 如果 `npm install` 會讀取其他檔案，例如工作區的 `package.json`、`.npmrc` 或您的 `postinstall` 指令碼的輸入，請將它們新增至儲存雜湊值的 `sha256sum` 命令中。否則，在其中某個檔案變更後，您仍會保留舊的套件。

#### 雲端工作階段中的限制

SessionStart hooks 在雲端中的行為與本機相同，但有以下注意事項：

* **每個工作階段一個儲存庫**：在 Anthropic 託管環境中，具有多個儲存庫的工作階段不會從任何儲存庫的 `.claude/settings.json` 載入 hooks，因此您在其中定義的 SessionStart hook 不會執行。請改用[設定指令碼](#setup-scripts)為這些工作階段安裝相依性。若為自託管環境，請參閱[適用哪個儲存庫的設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#repository-settings-in-sessions-with-several-repositories)。
* **不適用於專案的雲端討論串**：[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)中的雲端討論串不會執行來自儲存庫 `.claude/settings.json` 的 hooks，無論儲存庫數量為何。在 Anthropic 託管環境中，請使用[設定指令碼](#setup-scripts)為討論串安裝相依性。在自託管環境中，請改用[執行器主機設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#repository-settings-in-sessions-with-several-repositories)中的 hook。
* **無雲端專用範圍**：hooks 在本機和雲端工作階段中執行。若要跳過本機執行，請在 `CLAUDE_CODE_REMOTE` 環境變數不為 `true` 時提前結束，如[相依性安裝指令碼](#install-dependencies-with-a-sessionstart-hook)所示。
* **需要網路存取**：安裝命令需要連接到套件登錄檔。如果您的環境使用 **None** 網路存取，這些 hooks 會失敗。**Trusted** 下的[預設允許清單](#default-allowed-domains)涵蓋 npm、PyPI、RubyGems 和 crates.io。
* **Proxy 相容性**：在 Anthropic 託管環境中，所有出站流量都通過[安全 proxy](#security-proxy)，某些套件管理員無法與此 proxy 正確搭配運作；Bun 是一個已知的範例。在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#default-deny-egress)中，出站流量通過您自己的網路邊界。
* **增加啟動延遲**：hook 在每次工作階段啟動或恢復時執行，不同於設定指令碼，設定指令碼受益於[環境快取](#environment-caching)。透過跳過已完成的工作來保持安裝指令碼快速，如[相依性安裝指令碼](#install-dependencies-with-a-sessionstart-hook)所示。

若要自訂基礎映像，請使用設定指令碼在[提供的映像](#installed-tools)上安裝您需要的內容，或使用 `docker compose` 作為 Claude 旁邊的容器執行您自己的映像。目前不支援完全取代基礎映像。

## 預設允許的網域

使用 **Trusted** 網路存取，工作階段預設可以到達以下網域。標記為 `*` 的網域表示萬用字元子網域符合，因此 `*.gcr.io` 允許 `gcr.io` 的任何子網域。

> [accordion] Anthropic 服務
>
> * api.anthropic.com
> * docs.claude.com
> * platform.claude.com
> * code.claude.com
> * claude.ai
> * claude.com
> * support.claude.com
> * anthropic.com
> * [www.anthropic.com](http://www.anthropic.com)

> [accordion] 版本控制
>
> * github.com
> * [www.github.com](http://www.github.com)
> * api.github.com
> * npm.pkg.github.com
> * raw\.githubusercontent.com
> * pkg-npm.githubusercontent.com
> * objects.githubusercontent.com
> * release-assets.githubusercontent.com
> * codeload.github.com
> * avatars.githubusercontent.com
> * camo.githubusercontent.com
> * gist.github.com
> * gitlab.com
> * [www.gitlab.com](http://www.gitlab.com)
> * registry.gitlab.com
> * bitbucket.org
> * [www.bitbucket.org](http://www.bitbucket.org)
> * api.bitbucket.org

> [accordion] 容器登錄
>
> * registry-1.docker.io
> * auth.docker.io
> * index.docker.io
> * hub.docker.com
> * [www.docker.com](http://www.docker.com)
> * production.cloudflare.docker.com
> * production.cloudfront.docker.com
> * download.docker.com
> * gcr.io
> * \*.gcr.io
> * ghcr.io
> * mcr.microsoft.com
> * \*.data.mcr.microsoft.com
> * public.ecr.aws

> [accordion] 雲端平台
>
> * cloud.google.com
> * accounts.google.com
> * gcloud.google.com
> * \*.googleapis.com
> * storage.googleapis.com
> * compute.googleapis.com
> * container.googleapis.com
> * azure.com
> * portal.azure.com
> * microsoft.com
> * [www.microsoft.com](http://www.microsoft.com)
> * \*.microsoftonline.com
> * packages.microsoft.com
> * dotnet.microsoft.com
> * dot.net
> * visualstudio.com
> * dev.azure.com
> * \*.amazonaws.com
> * \*.api.aws
> * oracle.com
> * [www.oracle.com](http://www.oracle.com)
> * java.com
> * [www.java.com](http://www.java.com)
> * java.net
> * [www.java.net](http://www.java.net)
> * download.oracle.com
> * yum.oracle.com
> * \*.r2.cloudflarestorage.com

> [accordion] JavaScript 和 Node 套件管理員
>
> * registry.npmjs.org
> * [www.npmjs.com](http://www.npmjs.com)
> * [www.npmjs.org](http://www.npmjs.org)
> * npmjs.com
> * npmjs.org
> * yarnpkg.com
> * registry.yarnpkg.com
> * jsr.io
> * npm.jsr.io

> [accordion] Python 套件管理員
>
> * pypi.org
> * [www.pypi.org](http://www.pypi.org)
> * files.pythonhosted.org
> * pythonhosted.org
> * test.pypi.org
> * pypi.python.org
> * pypa.io
> * [www.pypa.io](http://www.pypa.io)

> [accordion] Ruby 套件管理員
>
> * rubygems.org
> * [www.rubygems.org](http://www.rubygems.org)
> * api.rubygems.org
> * index.rubygems.org
> * ruby-lang.org
> * [www.ruby-lang.org](http://www.ruby-lang.org)
> * rubyforge.org
> * [www.rubyforge.org](http://www.rubyforge.org)
> * rubyonrails.org
> * [www.rubyonrails.org](http://www.rubyonrails.org)
> * rvm.io
> * get.rvm.io

> [accordion] Rust 套件管理員
>
> * crates.io
> * [www.crates.io](http://www.crates.io)
> * index.crates.io
> * static.crates.io
> * rustup.rs
> * static.rust-lang.org
> * [www.rust-lang.org](http://www.rust-lang.org)

> [accordion] Go 套件管理員
>
> * proxy.golang.org
> * sum.golang.org
> * index.golang.org
> * golang.org
> * [www.golang.org](http://www.golang.org)
> * goproxy.io
> * pkg.go.dev

> [accordion] JVM 套件管理員
>
> * maven.org
> * repo.maven.org
> * central.maven.org
> * repo1.maven.org
> * repo.maven.apache.org
> * maven.google.com
> * jcenter.bintray.com
> * gradle.org
> * [www.gradle.org](http://www.gradle.org)
> * services.gradle.org
> * plugins.gradle.org
> * plugins-artifacts.gradle.org
> * kotlinlang.org
> * [www.kotlinlang.org](http://www.kotlinlang.org)
> * spring.io
> * repo.spring.io

> [accordion] 其他套件管理員
>
> * packagist.org (PHP Composer)
> * [www.packagist.org](http://www.packagist.org)
> * repo.packagist.org
> * nuget.org (.NET NuGet)
> * [www.nuget.org](http://www.nuget.org)
> * api.nuget.org
> * pub.dev (Dart/Flutter)
> * api.pub.dev
> * hex.pm (Elixir/Erlang)
> * [www.hex.pm](http://www.hex.pm)
> * cpan.org (Perl CPAN)
> * [www.cpan.org](http://www.cpan.org)
> * metacpan.org
> * [www.metacpan.org](http://www.metacpan.org)
> * api.metacpan.org
> * cocoapods.org (iOS/macOS)
> * [www.cocoapods.org](http://www.cocoapods.org)
> * cdn.cocoapods.org
> * haskell.org
> * [www.haskell.org](http://www.haskell.org)
> * hackage.haskell.org
> * swift.org
> * [www.swift.org](http://www.swift.org)

> [accordion] Linux 發行版
>
> * archive.ubuntu.com
> * security.ubuntu.com
> * ubuntu.com
> * [www.ubuntu.com](http://www.ubuntu.com)
> * \*.ubuntu.com
> * ppa.launchpad.net
> * launchpad.net
> * [www.launchpad.net](http://www.launchpad.net)
> * \*.nixos.org

> [accordion] 開發工具和平台
>
> * dl.k8s.io (Kubernetes)
> * pkgs.k8s.io
> * k8s.io
> * [www.k8s.io](http://www.k8s.io)
> * releases.hashicorp.com (HashiCorp)
> * apt.releases.hashicorp.com
> * rpm.releases.hashicorp.com
> * archive.releases.hashicorp.com
> * hashicorp.com
> * [www.hashicorp.com](http://www.hashicorp.com)
> * repo.anaconda.com (Anaconda/Conda)
> * conda.anaconda.org
> * anaconda.org
> * [www.anaconda.com](http://www.anaconda.com)
> * anaconda.com
> * continuum.io
> * apache.org (Apache)
> * [www.apache.org](http://www.apache.org)
> * archive.apache.org
> * downloads.apache.org
> * eclipse.org (Eclipse)
> * [www.eclipse.org](http://www.eclipse.org)
> * download.eclipse.org
> * nodejs.org (Node.js)
> * [www.nodejs.org](http://www.nodejs.org)
> * developer.apple.com
> * developer.android.com
> * pkg.stainless.com
> * binaries.prisma.sh

> [accordion] 雲端服務和監控
>
> * http-intake.logs.datadoghq.com
> * \*.datadoghq.com
> * \*.datadoghq.eu
> * api.honeycomb.io

> [accordion] 內容傳遞和鏡像
>
> * sourceforge.net
> * \*.sourceforge.net
> * packagecloud.io
> * \*.packagecloud.io
> * fonts.googleapis.com
> * fonts.gstatic.com

> [accordion] 架構和設定
>
> * json-schema.org
> * [www.json-schema.org](http://www.json-schema.org)
> * json.schemastore.org
> * [www.schemastore.org](http://www.schemastore.org)

> [accordion] Model Context Protocol
>
> * \*.modelcontextprotocol.io

## 相關資源

* [Cloud sessions reference](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：啟動、管理和共用雲端工作階段
* [Cloud sessions quickstart](https://code.claude.com/docs/zh-TW/web-quickstart.md)：連接 GitHub 並啟動您的第一個雲端工作階段
* [Claude Tag](https://claude.com/docs/claude-tag/overview)：Claude 從 Slack 啟動的工作階段在相同的環境中執行
* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)：排程執行使用相同的環境和網路存取層級
* [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)：改為在您自己的機器的網路和檔案上執行工作階段
* [Self-hosted environments](https://code.claude.com/docs/zh-TW/self-hosted-environments)：在您組織自己的基礎設施上執行雲端工作階段
* [SessionStart hooks](https://code.claude.com/docs/zh-TW/hooks.md#sessionstart)：儲存庫提交的設定，在本機和雲端工作階段中執行
* [Server-managed settings](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：從管理主控台傳遞的組織政策
