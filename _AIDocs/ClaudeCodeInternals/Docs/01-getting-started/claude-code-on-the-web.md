<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-code-on-the-web | lastmod: 2026-10-30 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/claude-code-on-the-web（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Platforms and integrations｜EN 摘要：Run Claude Code sessions in the cloud from your browser, phone, Desktop app, or terminal, move them with `--cloud` and `--teleport`, and auto-fix pull requests.

# 在雲端使用 Claude Code

> 從您的瀏覽器、手機、桌面應用程式或終端機在雲端執行 Claude Code 工作階段，使用 `--cloud` 和 `--teleport` 移動工作階段，以及自動修復 pull request。

> [!NOTE]
>
> 雲端工作階段適用於 Pro、Max、Ultra 和 Team 方案，以及具有高級席位或 Chat + Claude Code 席位的 Enterprise 使用者。如果您的存取權由[自訂角色](https://support.claude.com/en/articles/13930452)管理，您還需要一個包含雲端工作階段權限的角色，才能從瀏覽器、應用程式或終端機在 Anthropic 的基礎設施上啟動工作階段。請 Owner 在 [**Organization settings > Roles**](https://claude.ai/admin-settings/roles) 中將該權限新增至您的其中一個角色。

雲端工作階段是在雲端基礎設施上執行的 Claude Code 工作階段，而不是在您的機器上執行。預設情況下，它在 Anthropic 管理的基礎設施上執行，或在您的組織的[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)上執行（如果路由到那裡）。工作階段在您關閉筆記型電腦後仍會繼續執行，您可以從任何裝置檢查或控制它。它會與您其餘的 Claude 和 Claude Code 使用量一起計入您方案的用量上限，雲端 VM 不另外收費。

若要讓雲端工作階段從 GitHub 複製您的程式碼並推送分支，請使用其中一種 [GitHub 連接方式](#github-authentication-options)連接 GitHub。如果您的儲存庫位於 GitLab、Bitbucket 或其他主機上，請參閱[平台限制](#limitations)以了解可用的功能。

您可以從以下任何介面啟動雲端工作階段：

* **瀏覽器**：[claude.ai/code](https://claude.ai/code)，也稱為網頁版 Claude Code
* **行動裝置**：[Claude 應用程式](https://code.claude.com/docs/zh-TW/mobile.md)中的 **Code** 標籤
* **桌面應用程式**：當您[啟動工作階段](https://code.claude.com/docs/zh-TW/desktop.md#run-long-running-tasks-in-the-cloud)時，在環境選擇器的 **Cloud** 下選擇一個環境
* **終端**：[`claude --cloud`](#from-terminal-to-cloud)
* **雲端排程任務**：[排程和觸發的執行](https://code.claude.com/docs/zh-TW/routines.md)每次都作為雲端工作階段執行

完成設定後，請使用本頁在終端機和雲端之間移動工作、管理和共享工作階段、為 pull request 開啟自動修復，以及進行疑難排解。

> [!NOTE]
>
> 以下情況在其他頁面中說明：
>
> * **啟動您的第一個雲端工作階段**：[開始使用雲端工作階段](https://code.claude.com/docs/zh-TW/web-quickstart.md)會連接 GitHub，並引導您在瀏覽器中完成一項任務
> * **為一項工作使用多個雲端工作階段**：[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)會讓 Claude 為您啟動並追蹤這些工作階段
> * **從另一部裝置控制本機工作階段**：在您的終端機、IDE 或選擇了 **Local** 的 Desktop 應用程式中的工作階段會在您的機器上執行，而 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 可讓您從手機或瀏覽器存取這些工作階段

## 雲端環境

每個雲端工作階段都在一個[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)中執行，這是一個已保存的設定，控制網路存取、環境變數和設定指令碼。

* **您的第一個環境**：如果您還沒有環境，上線會設定一個**預設**環境，具有[**信任**網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#access-levels)，要麼為您建立它，要麼要求您建立它。請參閱[預設環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#the-default-environment)，了解在您的計畫上會發生哪種情況
* **工作階段使用哪個環境**：請參閱[預設環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#the-default-environment)，了解當您有多個環境時工作階段如何選擇環境
* **變更工作階段在啟動時可以存取或執行的內容**：請參閱[設定雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)
* **在沒有任何設定的情況下已安裝的內容**：請參閱[已安裝的工具](https://code.claude.com/docs/zh-TW/cloud-environments.md#installed-tools)

## GitHub 驗證選項

雲端工作階段需要存取您的 GitHub 儲存庫以複製程式碼和推送分支。您可以通過兩種方式授予存取權限：

| 方法 | 運作方式 | 工作階段可以存取的儲存庫 | 最適合 |
| :- | :- | :- | :- |
| **GitHub App** | 在[網頁上線](https://code.claude.com/docs/zh-TW/web-quickstart.md)期間授權 Claude GitHub App | 任何公開儲存庫，以及安裝了 Claude GitHub App 的私人儲存庫 | 瀏覽器上線；想要[自動修復](#auto-fix-pull-requests)的團隊 |
| **`/web-setup`** | 在您的終端中執行 `/web-setup` 以將您的本機 `gh` CLI 令牌傳送到您的 Claude 帳戶 | 您的 `gh` 令牌可以存取的任何儲存庫，無論是否安裝了 Claude GitHub App | 已經使用 `gh` 的個人開發者 |

以下功能取決於儲存庫上是否已安裝 Claude GitHub App：

* **自動修復**：在儲存庫上安裝 Claude GitHub App 也會為其中的 pull request 啟用[自動修復](#auto-fix-pull-requests)
* **專案**：[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)中的執行緒需要在它們複製的每個儲存庫上安裝 Claude GitHub App，無論您使用哪種方法連接。請參閱[設定 GitHub 存取](https://code.claude.com/docs/zh-TW/claude-projects.md#set-up-github-access)

在 Anthropic 代管的環境中，您的 GitHub 認證保持在 Anthropic 伺服器上加密，永遠不會進入工作階段的虛擬機器。來自虛擬機器的 GitHub 操作會通過 [GitHub proxy](https://code.claude.com/docs/zh-TW/cloud-environments.md#github-proxy)，它在伺服器端附加認證。

有關 `/web-setup` 的逐步說明，請參閱[從您的終端機連接](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-from-your-terminal)，包括 `/web-setup` 儲存的內容以及如何移除它。

> [!NOTE]
>
> 啟用[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)或已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織無法使用 `/web-setup` 或其他雲端工作階段功能。使用[客戶管理的加密金鑰](https://platform.claude.com/docs/en/manage-claude/cmek)（CMEK）的組織也無法啟動雲端工作階段。

### Team 和 Enterprise 的快速設定

快速設定是一個組織設定，可減少成員在 GitHub 和環境設定上的步驟。在 Team 和 Enterprise 計畫上，預設情況下它是關閉的。

開啟後，成員會有以下變化：

* **`/web-setup`**：成員可以使用 `/web-setup` 連接 GitHub。此設定關閉時，該命令會被隱藏
* **GitHub App 提示**：瀏覽器上線會跳過 Claude GitHub App 安裝提示
* **第一個環境**：瀏覽器上線會為成員建立[**預設**環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#the-default-environment)，而不是顯示環境表單

[擁有者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control)可以在 [**組織設定 > Claude Code**](https://claude.ai/admin-settings/claude-code) 使用**快速設定**切換來開啟它。

## 在終端機和雲端之間移動任務

這些工作流程需要 [Claude Code CLI](https://code.claude.com/docs/zh-TW/quickstart.md) 登入到同一個 claude.ai 帳戶。您可以從終端機啟動新的雲端工作階段，或將雲端工作階段拉入您的終端機以在本機繼續。雲端工作階段即使在您關閉筆記型電腦後仍會保留，您可以從任何地方（包括 Claude 行動應用程式）監控它們。

> [!NOTE]
>
> 從 CLI，工作階段交接是單向的：您可以使用 `--teleport` 將雲端工作階段拉入您的終端機，但您無法將現有的終端機工作階段推送到雲端。`--cloud` 旗標搭配任務描述會為您目前的儲存庫建立新的雲端工作階段；搭配 `-p` 和工作階段 ID 或 claude.ai/code URL 時，它會改為 [將訊息加入該現有工作階段的佇列](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-follow-ups-from-the-cli)。[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#continue-in-another-surface) 可以從其 **Open in** 功能表，將其 Code 分頁中的本機工作階段傳送到雲端。

### 從終端機啟動雲端工作階段

使用 `--cloud` 旗標從命令列啟動雲端工作階段：

```bash theme={null}
claude --cloud "Fix the authentication bug in src/auth/login.ts"
```

這會在 claude.ai 上建立新的雲端工作階段。雲端 VM 會在您目前的分支上複製您目前目錄的 GitHub 遠端，而不是您的本機簽出，所以如果您有本機提交，請先推送。請參閱 [Send local repositories without GitHub](#send-local-repositories-without-github) 以了解 Claude Code 上傳您的本機儲存庫而不是複製的情況。如果終端機列印出 `Branch <name> is not on GitHub`，請參閱 [Branch is not on GitHub](#branch-is-not-on-github)。

`--cloud` 一次只能與單一儲存庫搭配使用。任務在雲端執行，而您繼續在本機工作。較舊的 `--remote` 拼寫仍然可作為 `--cloud` 的已棄用別名使用。

當雲端容器啟動時，CLI 會顯示設定步驟的即時檢查清單，例如複製儲存庫和執行您的 [setup script](https://code.claude.com/docs/zh-TW/cloud-environments.md#setup-scripts)。它會將您在佈建期間輸入的訊息加入佇列，並在工作階段準備好後傳送它們。

> [!NOTE]
>
> `--cloud` 會建立雲端工作階段。`--remote-control` 無關：它可讓您從 claude.ai 或 Claude 應用程式監控和控制本機 CLI 工作階段。請參閱 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)。

在 claude.ai 或 Claude 行動應用程式上開啟工作階段以檢查進度或直接互動。從那裡您可以控制 Claude、提供回饋或回答問題，就像在任何其他對話中一樣。

如果 Claude 提出問題且工作階段閒置，您仍然可以在回來時回答，直到 [environment expiry](#environment-expired)，工作階段會從您的回答繼續。

#### 雲端任務的提示

**在本機規劃，在雲端執行**：對於複雜的任務，先啟動 Claude 進入規劃模式以協作制定方法，然後將工作傳送到雲端：

```bash theme={null}
claude --permission-mode plan
```

在規劃模式中，Claude 讀取檔案、執行命令以探索，並提出計畫而不編輯原始程式碼。一旦您滿意，將計畫儲存到儲存庫、提交並推送，以便雲端 VM 可以複製它。然後啟動雲端工作階段以進行自主執行：

```bash theme={null}
claude --cloud "Execute the migration plan in docs/migration-plan.md"
```

**並行執行任務**：每個 `--cloud` 命令都會建立自己的雲端工作階段，獨立執行。您可以啟動多個任務，它們都會在不同的工作階段中同時執行：

```bash theme={null}
claude --cloud "Fix the flaky test in auth.spec.ts"
claude --cloud "Update the API documentation"
claude --cloud "Refactor the logger to use structured output"
```

當工作階段完成時，您可以從 claude.ai/code 建立 PR，或 [teleport](#from-cloud-to-terminal) 工作階段到您的終端機以繼續工作。

#### 傳送沒有 GitHub 的本機儲存庫

當您從沒有 git 遠端的儲存庫執行 `claude --cloud`，或從 Claude GitHub App 未安裝的 github.com 儲存庫執行時，Claude Code 會將您的本機儲存庫打包並直接上傳到雲端工作階段。即使您使用 `/web-setup` 連接了 GitHub，這也適用。

對於完整複製，該套件包括您在所有分支上的儲存庫歷史記錄，加上對追蹤檔案的未提交變更。

敏感檔案中未提交變更的處理方式取決於您的平台：

* **macOS、Linux 和 WSL**：Claude Code 會將名稱類似於憑證或金鑰的檔案的未提交變更排除在上傳之外。這涵蓋 `.env` 檔案、Terraform `*.tfvars` 檔案和金鑰檔案，例如 `id_rsa` 和 `*.pem`。它也會排除由 Git LFS 等 git 篩選器所管理之檔案的未提交變更。`Left on this machine:` 通知會列出被排除的檔案，工作階段會以每個檔案的已提交版本啟動，或如果未提交任何版本，則不含該檔案。
* **原生 Windows**：對追蹤檔案的未提交變更會按原樣上傳，無論檔案名稱為何。在啟動雲端工作階段之前，請先隱藏或還原您不希望出現在其中的編輯。

若要在 Claude Code 會從遠端複製時強制上傳套件，請設定 `CCR_FORCE_BUNDLE=1`：

```bash theme={null}
CCR_FORCE_BUNDLE=1 claude --cloud "Run the test suite and fix any failures"
```

打包的儲存庫必須符合這些限制：

* 目錄必須是至少有一個提交的 git 儲存庫
* 打包的儲存庫必須在 100 MB 以下。較大的儲存庫會回退到僅打包目前分支，然後回退到工作樹的單一壓縮快照，如果快照仍然太大則失敗
* 未追蹤的檔案不包括在內；在您希望雲端工作階段看到的檔案上執行 `git add`
* 在 macOS、Linux 和 WSL 上，當 Claude Code 無法遵循影響您的檔案適用哪些屬性規則的 git 設定時，Claude Code 會拒絕上傳，例如在包含的設定檔中設定的 `core.attributesFile`。[拒絕訊息](https://code.claude.com/docs/zh-TW/errors.md#the-repository-upload-cant-follow-a-git-setting) 會命名該設定和修正方式
* 從套件建立的工作階段只有在您的 [GitHub connection](#github-authentication-options) 對該儲存庫具有推送存取權時，才能推送回 GitHub 遠端

在 macOS、Linux 和 WSL 上，上傳還需要 git 2.31 或更新版本以及其支援的簽出結構；而在原生 Windows 上，Claude Code 上傳時不會進行這兩項檢查。當簽出不符合這些需求時，Claude Code 不會啟動工作階段。它會列印包含 `Not uploading this working tree:` 的錯誤，說明原因以及需要變更的內容。以下是常見原因：

* **較舊的 git**：已安裝的 git 早於 2.31。請更新 git，然後重試。
* **上傳不支援的簽出結構**：您是從子模組內、使用 `git clone --separate-git-dir`、`--shared` 或 `--reference` 建立的複製中、設定了 `core.worktree` 的簽出中，或以 reftable 格式儲存 refs 的儲存庫中啟動。請改為從使用一般 `git clone` 建立之複製的主要簽出啟動。
* **使用稀疏簽出的連結 worktree**：`git sparse-checkout` 會將設定寫入 worktree 自己的 `config.worktree` 檔案，而上傳不接受該檔案，因此具有這些設定的 worktree 不會被上傳，Claude Code 透過 [`worktree.sparsePaths`](https://code.claude.com/docs/zh-TW/settings-reference#worktree-sparsepaths) 建立的 worktree 也不會。請改為從儲存庫的主要簽出啟動。
* **保存在工作樹內的 git 設定**：您的 git 設定包含位於簽出內的檔案，例如指向儲存庫內部的 `include.path` 項目。請將該檔案移到工作樹之外或移除該 include，然後重試。

在 macOS、Linux 和 WSL 上，使用 `git clone --filter` 建立的部分複製會以其工作樹的快照（不含歷史記錄）上傳，前提是該複製在本機保有每個追蹤檔案。

對於 `claude --cloud`，如果儲存庫位於 GitHub 上，您可以避免上傳及其需求：推送您的分支、在儲存庫上安裝 Claude GitHub App，然後再次啟動工作階段，使其從 GitHub 複製。

### 從 CLI 傳送後續訊息

一旦雲端工作階段執行，無論它在何處執行，都可以從任何您使用 `claude auth login` 登入的機器上的 `claude` CLI 傳送後續訊息。CLI 使用您的 Anthropic 帳戶憑證進行身分驗證，不傳送任何本機工作階段狀態，因此命令不需要從啟動工作階段的機器執行。

該命令發佈一條訊息並退出：

```bash theme={null}
claude -p "your message" --cloud <session-id>
```

CLI 將訊息加入工作階段的佇列並退出，不等待回覆。使用它來控制長時間執行的工作階段、在目前工作階段仍在完成時將下一步加入佇列，或從 [CI script](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#run-the-test-loop) 傳送後續訊息。您也可以在 stdin 上管道傳輸訊息，而不是將其作為引數傳遞：`echo "your message" | claude -p --cloud <session-id>`。

對於 `<session-id>`，傳遞裸 ID，例如 `session_...` 或 `cse_...`，或工作階段的 `claude.ai/code/<id>` URL，有或沒有配置或查詢字串。在 claude.ai/code 的工作階段清單中找到 ID。

> [!NOTE]
>
> `--cloud` 需要 Anthropic 帳戶。當 Claude Code 針對 Amazon Bedrock、Google Cloud 的 Agent Platform 或其他第三方提供者進行設定時，它不可用。僅透過 `ANTHROPIC_BASE_URL` 設定的 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway) 不算作此檢查的第三方提供者，但您仍需要使用 `claude auth login` 登入。您組織的 `allow_remote_sessions` 原則也必須啟用。擁有者可以在 claude.ai/admin-settings/claude-code 的 Claude Code 管理設定中開啟它。

#### 輸出

成功時，命令會列印工作階段 ID 和檢視工作階段的連結：

```
Sent to cloud session.
Session ID: session_01DiUkqY2kzbUbDmW1w96rfi
View: https://claude.ai/code/session_01DiUkqY2kzbUbDmW1w96rfi?from=cli&m=0
```

傳遞 `--output-format json` 以取得機器可讀的結果：成功時為 `{ok, session_id, url}`，或當傳送失敗時為 `{ok: false, session_id, error}`，例如當工作階段遺失或已封存時。設定錯誤（例如不支援的提供者或已停用的組織原則）會列印到 stderr，不含 JSON。`--output-format stream-json` 不支援 `--cloud <session-id>`。

如果傳送失敗，請參閱 [傳送到雲端工作階段時的錯誤](#errors-when-sending-to-a-cloud-session)。

### 在終端機中繼續雲端工作階段

使用以下任何方式將雲端工作階段拉入您的終端機：

* **使用 `--teleport`**：從命令列執行 `claude --teleport` 以取得互動式工作階段選擇器，或 `claude --teleport <session-id>` 以直接繼續特定工作階段。如果您有未提交的變更，系統會提示您先將它們隱藏。[`--resume`](https://code.claude.com/docs/zh-TW/sessions#resume-a-session) 會從此機器的本機歷史記錄重新開啟對話，不會列出雲端工作階段。
* **使用 `/teleport`**：在現有 CLI 工作階段內執行 `/teleport` 或 `/tp` 以開啟相同的工作階段選擇器，無需重新啟動 Claude Code。
* **從 `/tasks`**：執行 `/tasks` 以查看您的背景工作階段，然後按 `t` 以 teleport 進入其中一個。
* **從 claude.ai/code**：從工作階段功能表選擇 **Open in > Terminal** 以複製可以貼到您的終端機的命令。
* **從雲端工作階段內**：輸入 `/teleport`，Claude Code 會回覆確切的 `claude --teleport <session-id>` 命令，準備從儲存庫的簽出執行。需要工作階段環境中的 Claude Code v2.1.223 或更新版本。

當您 teleport 工作階段時，Claude 會驗證您在正確的儲存庫中，擷取並簽出雲端工作階段的分支，並將對話載入您的終端機。

> [!NOTE]
>
> 如果 Claude Code 已[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)雲端工作階段（在長時間的工作階段中會自動執行），它所摘要的較早訊息不會複製到您的終端機。Claude 會從摘要繼續。若要閱讀原始訊息，請在 claude.ai 或 Claude 行動應用程式上的雲端工作階段中向上捲動。

終端機會取得工作階段的自己副本：那裡的新工作保持本機，不會出現在 claude.ai 上的雲端工作階段或 Claude 行動應用程式中。若要在 teleport 後繼續從您的手機控制，請在本機工作階段中啟動 [`/remote-control`](https://code.claude.com/docs/zh-TW/remote-control)。

#### Teleport 需求

Teleport 在繼續工作階段之前檢查這些需求。如果任何需求未滿足，您會看到錯誤或被提示解決問題。

| 需求 | 詳細資訊 |
| - | - |
| 乾淨的 git 狀態 | 您的工作目錄必須沒有未提交的變更。如果需要，Teleport 會提示您隱藏變更。 |
| 正確的儲存庫 | 您必須從同一儲存庫的簽出執行 `--teleport`，而不是分叉。如果您從不同儲存庫的簽出執行它，Claude Code 會顯示一個錯誤，命名工作階段的儲存庫和您的簽出的儲存庫。如果 Claude Code 無法將您的遠端解析為主機名稱，例如 SSH 主機別名如 `git@work:owner/repo.git`，它會要求您確認，並在遠端的擁有者和儲存庫名稱與工作階段的儲存庫相符時接受簽出。 |
| 分支可用 | 雲端工作階段的分支必須已推送到遠端。Teleport 會自動擷取並簽出它。 |
| 相同帳戶 | 您必須驗證到雲端工作階段中使用的同一 claude.ai 帳戶。 |

當 teleport 擷取工作階段的分支時，擷取作業絕不會在您的終端機中等待輸入。如果 git 或 ssh 需要詢問密碼、金鑰密語或新 SSH 主機的確認，擷取就會失敗，而只有在您的本機複製已有該分支時，簽出才能成功。對於這兩種 SSH 情況，請將您的金鑰載入 `ssh-agent`，並先手動執行一次 `git fetch` 以記錄主機。

#### `--teleport` 不可用

Teleport 需要 claude.ai 訂閱身分驗證。請找出符合您情況的項目：

* **您使用 API 金鑰或 Console 帳戶登入**：在您的 shell 中執行 `claude auth login`，然後使用 claude.ai 登入
* **錯誤命名了您的提供者**：雲端工作階段無法透過第三方提供者取得。請參閱 [錯誤表](#errors-when-sending-to-a-cloud-session)
* **您已透過 claude.ai 登入**：您的組織可能已停用雲端工作階段

## 使用工作階段

工作階段出現在 claude.ai/code 的側邊欄中。從那裡，您可以檢查變更、與隊友共享、封存完成的工作或永久刪除工作階段。

### 雲端工作階段中的權限模式

您可以從[模式下拉式功能表](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)選擇雲端工作階段的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)，無論是在您建立任務時還是在工作階段執行時。

當您執行下列任一操作時，Claude Code 會以工作階段當時所在的權限模式恢復該工作階段：

* 重新開啟其 Anthropic 託管[環境已過期](#environment-expired)的工作階段
* 向自託管執行器[在閒置時釋放](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#runner-cli-flags)的工作階段發送訊息

### 檢查變更

Claude 將其變更推送到分支後，聊天旁面板中的**變更**卡片會顯示新增和移除的行數，例如 `+42 -18`。點擊**變更**卡片上的行數以開啟差異檢視。

* 您也可以點擊工作階段標題列中的**變更**，或標題列 **⋮** 功能表中的**變更**。
* 若要在面板隱藏時顯示它，請點擊工作階段標題列中的**顯示工作階段側欄**圖示，或使用標題列的 **⋮** 功能表。

在差異檢視中，您可以對特定行留言，並與其他分支進行比較：

* **留言**：在特定行上留下內聯評論，然後使用您的下一條訊息將評論發送給 Claude
* **比較**：差異檢視預設會將工作階段的變更與其基礎分支進行比較。若要與儲存庫中的任何其他分支進行比較，請選擇**比較對象**並選擇一個

Claude Code 從原始 git blob 內容計算這些差異，因此儲存庫中設定的差異驅動器和 `textconv` 篩選器不適用。

以下步驟在其他地方有說明：

* **完整逐步說明，包括 PR 建立**：請參閱[檢查和迭代](https://code.claude.com/docs/zh-TW/web-quickstart.md#review-and-iterate)
* **讓 Claude 自動監控 PR 以查找 CI 失敗和審查評論**：請參閱[自動修復 pull requests](#auto-fix-pull-requests)

#### 疑難排解差異檢視中缺少的檔案

當差異檢視與基礎分支進行比較時，您預期的檔案可能不會出現在差異檢視的檔案清單中，無論工作階段是否已推送變更：

* **尚未推送變更**：清單包含 Claude 本身所做的編輯，但不包含 Claude 執行的命令（例如格式化工具）所做的變更
* **已推送變更**：清單包含已推送的提交，但不包含最後一次推送之後所做的變更

若要將缺少的變更加入清單，請要求 Claude 提交並推送。

### 管理上下文

雲端工作階段支援產生文字輸出的[內建命令](https://code.claude.com/docs/zh-TW/commands.md)。只在終端介面中執行的命令，例如 `/plugin` 或 `/resume`，無法使用。在雲端工作階段中開啟選擇器或面板的命令行為不同：

* **`/model`、`/effort`、`/color` 和 `/rename`**：將值作為引數傳遞，例如 `/model sonnet`，而不是開啟終端機選擇器或滑塊。引數形式遵循每個命令的[可用性說明](https://code.claude.com/docs/zh-TW/commands.md#all-commands)。
* **`/fast`**：當快速模式在[您的帳戶上可用](https://code.claude.com/docs/zh-TW/fast-mode.md#requirements)時，為工作階段切換[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-in-cloud-sessions)。需要工作階段環境中的 Claude Code v2.1.271 或更新版本。
* **`/config`**：在瀏覽器中的 claude.ai/code 上，此命令會開啟 **設定 > Code** 或 **設定 > Claude Code**，而不是設定某個值。若要變更雲端工作階段的設定，請在環境上設定[環境變數](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)。在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)執行緒之外、只有一個儲存庫的工作階段中，請改為將該設定鍵提交至該儲存庫的 `.claude/settings.json`。[雲端工作階段中的設定](https://code.claude.com/docs/zh-TW/settings.md#settings-in-cloud-sessions)列出了每個工作階段會讀取的內容。

對於[專案執行緒](https://code.claude.com/docs/zh-TW/claude-projects.md#choose-models-and-let-claude-manage-context)之外的雲端工作階段中的上下文管理：

| 命令 | 在雲端工作階段中有效 | 備註 |
| :- | :- | :- |
| `/compact` | 是 | 總結對話以釋放上下文。接受可選的焦點指示，如 `/compact keep the test output` |
| `/context` | 是 | 顯示目前在上下文視窗中的內容 |
| `/clear` | 是 | 在同一個雲端工作階段中以空白上下文開始新的對話 |

自動壓縮在上下文視窗接近容量時自動執行。雲端工作階段自行設定 [`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`](https://code.claude.com/docs/zh-TW/env-vars)，因此壓縮會在[自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)的中途觸發，而不是在視窗填滿時。該值會覆蓋您在[環境變數](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)中新增的值，因此在那裡新增變數不會變更壓縮觸發的時間。

若要改為變更自動壓縮視窗，請在您的環境變數中設定 [`CLAUDE_CODE_AUTO_COMPACT_WINDOW`](https://code.claude.com/docs/zh-TW/env-vars)，或在未設定變數的工作階段中執行 [`/autocompact`](https://code.claude.com/docs/zh-TW/commands#all-commands)，搭配令牌計數。

[Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 的運作方式與本機相同。Claude 可以使用 Agent 工具生成它們，以將研究或並行工作卸載到單獨的上下文視窗中，保持主對話更輕。在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)的討論串之外，在您的儲存庫的 `.claude/agents/` 中定義的 subagents 會自動載入。

[Agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md) 預設關閉，但可以通過將 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 新增到您的[環境變數](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)來啟用。

### 對話中的外掛建議

若對話中出現一張列出一個或多個[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)並附有**新增**按鈕的卡片，表示 Claude 正在為您的任務建議外掛。Claude 可以在您未要求的情況下提出這些建議。您不必回應，無論如何 Claude 都會繼續執行任務。

#### 新增或移除建議的外掛

在外掛上選擇**新增**，即可為您的 claude.ai 帳戶啟用該外掛，工作階段結束後它仍會保持啟用。若要復原，請從卡片開啟已新增的外掛，選擇**管理**以前往該外掛在 claude.ai 上的頁面，然後從該頁面移除外掛。

#### 關閉外掛建議

若要阻止 Claude 建議外掛，請使用[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)拒絕 `SearchPlugins` 和 `SuggestPluginInstall` 工具。在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)之外、只有一個儲存庫的工作階段中，請將規則提交至該儲存庫的 `.claude/settings.json`，並在 `permissions.deny` 下列出這兩個工具名稱：

```json theme={null}
{
  "permissions": {
    "deny": ["SearchPlugins", "SuggestPluginInstall"]
  }
}
```

當套用於該工作階段的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)設定了 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) 時，Claude Code 會忽略儲存庫 `.claude/settings.json` 中的權限規則，包括這些拒絕規則。在這種情況下，請改為將規則放入那些受管設定中。對於其他設定方式，例如包含多個儲存庫的工作階段或專案中的雲端執行緒，請參閱哪些[設定會套用到雲端工作階段](https://code.claude.com/docs/zh-TW/settings.md#settings-in-cloud-sessions)。

### 取回已排隊的訊息

如果您在 Claude 工作時發送訊息，該訊息會排隊，直到 Claude 讀取它。若要取回已排隊的訊息，請點擊它上面的 ✕。文字會返回到訊息框，以便您可以編輯它或發送其他內容。

如果 Claude 已經讀取訊息，它會保留在對話中。

### 共享工作階段

若要共享工作階段，請根據下面的帳戶類型切換其可見性。之後，按原樣共享工作階段連結。收件者在開啟連結時看到最新狀態，但他們的檢視不會即時更新。

#### 從 Enterprise 或 Team 帳戶共享

對於 Enterprise 和 Team 帳戶，共享的運作方式如下：

* **可見性選項**：**私人**和**Team**。Team 可見性使工作階段對您的 claude.ai 組織的其他成員可見
* **儲存庫存取**：驗證預設啟用，基於連接到收件者帳戶的 GitHub 帳戶
* **您的名稱**：您帳戶的顯示名稱對所有有存取權限的收件者可見
* **Slack 工作階段**：[Slack 中的 Claude](https://code.claude.com/docs/zh-TW/slack.md)工作階段會自動以 Team 可見性共享

#### 從 Max、Ultra 或 Pro 帳戶共享

* **可見性選項**：**私人**和**公開**。公開可見性使工作階段對任何登入 claude.ai 的使用者可見
* **儲存庫存取**：驗證預設未啟用
* **敏感內容**：在共享之前檢查您的工作階段。工作階段可能包含來自私人 GitHub 儲存庫的程式碼和憑證

若要要求收件者具有儲存庫存取權限，或從共享工作階段中隱藏您的名稱，請在 claude.ai 上開啟設定，然後：

* **如果設定功能表顯示 Code 而非 Claude Code**：前往 [**隱私**](https://claude.ai/settings/data-privacy-controls)，其中包含這些設定
* **否則**：前往 [**Claude Code > 共享設定**](https://claude.ai/settings/claude-code)

### 封存工作階段

封存工作階段可將其從側邊欄的工作階段清單中移除。若要封存工作階段，請在側邊欄中將滑鼠懸停在該工作階段上，開啟其 **⋯** 功能表，然後選擇**封存**。

#### 尋找已封存的工作階段

若要查看已封存的工作階段，請前往 [claude.ai/code/sessions](https://claude.ai/code/sessions) 並開啟**已封存**分頁。若要將工作階段放回側邊欄的工作階段清單，請在該分頁上將滑鼠懸停在該工作階段上，開啟其 **⋮** 功能表，然後選擇**取消封存**。

### 刪除工作階段

刪除工作階段會永久移除工作階段及其資料。此操作無法撤銷。您可以從側邊欄、工作階段功能表刪除工作階段，若已封存該工作階段，也可以從**已封存**分頁刪除：

* **從側邊欄**：將滑鼠懸停在工作階段上，開啟其 **⋯** 功能表，然後選擇**刪除**
* **從工作階段功能表**：開啟工作階段，選擇工作階段標題旁的下拉式功能表，然後選擇**刪除**
* **從已封存分頁**：在[**已封存**分頁](#find-an-archived-session)上將滑鼠懸停在工作階段上，開啟其 **⋮** 功能表，然後選擇**刪除**

在刪除工作階段之前，系統會要求您確認。

## 自動修復拉取請求

Claude 可以監視拉取請求並自動回應 CI 失敗和審查評論。Claude 訂閱 PR 上的 GitHub 活動，當檢查失敗或審查者留下評論時，Claude 會調查並推送修復（如果有明確的修復）。

> [!NOTE]
>
> 自動修復需要在您的儲存庫上安裝 Claude GitHub App。如果您還沒有，請從 [GitHub App 頁面](https://github.com/apps/claude)安裝它。

根據 PR 來自何處以及您使用的設備，有幾種方式可以開啟自動修復：

* **在雲端工作階段中建立的 PR**：在 claude.ai/code 開啟工作階段，並在 [**Changes** 卡片](#review-changes)中找到該 pull request。開啟 pull request 標題旁的 **⋮** 選單，並開啟**自動修復**
* **從您的終端**：在 PR 的分支上執行 [`/autofix-pr`](https://code.claude.com/docs/zh-TW/commands)。Claude Code 使用 `gh` 偵測開啟的 PR，生成雲端工作階段，並在一個步驟中開啟自動修復
* **從行動應用程式**：告訴 Claude 自動修復 PR，例如「監視此 PR 並修復任何 CI 失敗或審查評論」
* **任何現有 PR**：將 PR URL 貼到工作階段中並告訴 Claude 自動修復它

若要停止監視，請在工作階段的 [**Changes** 卡片](#review-changes)中，於 pull request 的 **⋮** 選單中關閉**自動修復**，或告訴 Claude 停止監視 PR。

### Claude 如何回應 PR 活動

當自動修復處於活動狀態時，Claude 會收到 PR 的 GitHub 事件，包括新的審查評論和 CI 檢查失敗。對於每個事件，Claude 會調查並決定如何進行：

* **明確的修復**：如果 Claude 對修復有信心且不與早期指示衝突，Claude 會進行變更、推送它，並在工作階段中解釋所做的工作
* **模糊的請求**：如果審查者的評論可以以多種方式解釋或涉及架構上重要的內容，Claude 會在採取行動前詢問您
* **重複或無操作事件**：如果事件是重複的或不需要變更，Claude 會在工作階段中記錄它並繼續

GitHub 不會在基礎分支推進並建立合併衝突時發出 webhook，因此自動修復無法自行對衝突做出反應。若要解決衝突，請開啟工作階段並要求 Claude 進行變基。

Claude 可能會在 GitHub 上回覆審查評論執行緒作為解決它們的一部分。這些回覆使用您的 GitHub 帳戶發佈，因此它們會出現在您的使用者名稱下，但每個回覆都標記為來自 Claude Code，以便審查者知道它是由代理編寫的，而不是由您直接編寫的。

> [!WARNING]
>
> 如果您的儲存庫使用評論觸發的自動化，例如 Atlantis、Terraform Cloud 或在 `issue_comment` 事件上執行的自訂 GitHub Actions，請注意 Claude 可以代表您回覆，這可能會觸發這些工作流程。在啟用自動修復之前檢查您的儲存庫自動化，並考慮為 PR 評論可以部署基礎設施或執行特權操作的儲存庫禁用自動修復。

## 安全性和隔離

每個雲端工作階段通過多個層與您的機器和其他工作階段分離：

* **隔離的虛擬機器**：每個工作階段在隔離的 Anthropic 管理的 VM 中執行。您的組織路由到[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的工作階段改為在您自己的基礎設施上執行，其中隔離是您的部署的責任
* **網路存取控制**：在 Anthropic 託管的環境中，網路存取預設受限，可以禁用。請參閱[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)以了解存取層級、[預設允許的網域](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)，以及不通過允許清單的流量。在自託管環境中，您在自己的網路邊界限制工作階段出口。當以禁用的網路存取執行時，Claude Code 仍然可以與 Anthropic API 通訊，這可能允許資料離開 VM。
* **憑證保護**：在 Anthropic 託管的環境中，git 憑證和簽署金鑰保持在沙箱外，代理伺服器使用限定範圍的憑證代表工作階段進行驗證。在自託管環境中，您的部署提供 git 憑證；請參閱[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)
* **網路機密**：在 Anthropic 託管的環境中，您[新增到雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#add-network-secrets)的金鑰同樣保持在沙箱外，並在符合的請求離開工作階段後附加到這些請求上。自託管環境沒有網路機密
* **安全分析**：程式碼在隔離的工作階段環境內進行分析和修改，然後建立 PR

## 故障排除

對於出現在對話中的執行時 API 錯誤，例如 `API Error: 500`、`529 Overloaded`、`429` 或 `Prompt is too long`，請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md)。這些錯誤及其修復與 CLI 和 Desktop 應用程式共享。下面的部分涵蓋特定於雲端工作階段的問題。

### 工作階段建立失敗

如果新工作階段無法啟動，出現 `Session creation failed` 或在佈建時停滯，Claude Code 無法為工作階段分配 VM。

* 檢查 [status.claude.com](https://status.claude.com) 以查找雲端工作階段事件
* 一分鐘後重試，因為容量是按需佈建的
* 確認您的 GitHub 連線可以到達儲存庫，請遵循[連接 GitHub 後沒有儲存庫出現](https://code.claude.com/docs/zh-TW/web-quickstart.md#no-repositories-appear-after-connecting-github)

### Your new session couldn't start

您的提示詞已回到您送出它的輸入框中。

* **連線中斷**：請檢查您的網際網路連線以及您使用的任何 VPN 或代理伺服器，然後再次傳送您的提示詞
* **伺服器錯誤**：請稍候片刻，然後再次傳送您的提示詞。如果通知再次出現，請檢查 [status.claude.com](https://status.claude.com)

### Can't rewind to this message

當您的工作階段在 Claude Code 版本早於 v2.1.246 的[自架 runner](https://code.claude.com/docs/zh-TW/self-hosted-environments) 上執行時，**Rewind to here** 在最新訊息以外的任何訊息上都會因此錯誤而失敗。請要求負責管理您組織 runner 的人員[升級它們](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#pin-the-version)。

### 無法取得組織 UUID

`claude --cloud` 和 `claude --teleport` 需要使用 claude.ai 帳戶登入。如果您改用 API 金鑰或 Console 登入進行身分驗證，或您儲存的帳戶詳細資訊已過期，您會看到類似以下的訊息：

* `Unable to get organization UUID`
* ``Cloud sessions need a claude.ai sign-in. Run `claude auth login` (or /login in a local session), then try again.``
* ``Cloud sessions aren't available with this Console sign-in. They need a claude.ai sign-in. Run `claude auth login` (or /login in a local session), then try again.``
* 在不提供工作階段 ID 的情況下執行 `claude --teleport` 時，工作階段選擇器中出現 `Error loading Claude Code sessions`

在您的 shell 中執行 [`claude auth login`](https://code.claude.com/docs/zh-TW/cli-reference#cli-commands) 以使用您的 claude.ai 帳戶登入，然後重試命令。在執行中的工作階段內，`/login` 的作用相同。如果錯誤改為指出您的提供者名稱，請參閱[錯誤表](#errors-when-sending-to-a-cloud-session)：雲端工作階段無法透過第三方提供者使用。

從 v2.1.274 到 v2.1.289，登入訊息為 `Claude Code cloud sessions require authentication with a Claude.ai account. API key authentication is not sufficient. Please run /login to authenticate, or check your authentication status with /status.`

### 分支不在 GitHub 上

當 `claude --cloud` 印出以 `Branch <name> is not on GitHub` 開頭的一行時，雲端工作階段仍會啟動，但不是從您的分支啟動。該行會指出工作階段改從何處啟動：您分支歷史中已推送的提交，或儲存庫的預設分支。僅存在於您電腦上的提交以及未提交的變更不會出現在工作階段中。

例如，當您從未推送該分支，或 GitHub 在其 pull request 合併後將其刪除時，您就會看到這一行。如果該行指出的起點包含您的任務所需的內容，請直接使用該工作階段。否則，請推送分支並啟動新的工作階段，使其複製您的分支。

### 遠端控制工作階段已過期或存取被拒絕

`--teleport` 通過與雲端工作階段使用的相同遠端控制工作階段基礎設施連接，因此驗證和工作階段過期錯誤會以遠端控制措辭出現。您可能會看到 `Remote Control session expired` 或 `Access denied`。連接令牌是短期的，並限定於您的帳戶。

* 在本機執行 `/login` 以刷新您的認證，然後重新連接
* 確認您登入到擁有工作階段的相同帳戶
* 如果您看到 `Remote Control may not be available for this organization`，擁有者尚未為您的組織啟用雲端工作階段

### 傳送至雲端工作階段時的錯誤

這些錯誤來自使用 [`--cloud <session-id>`](#send-follow-ups-from-the-cli) 執行 `claude`，無論是否搭配 `-p`。CLI 會在錯誤前加上 `Error: ` 前綴。傳送失敗會包裝為 `failed to send message to cloud session <id>: <reason>`。

| 訊息 | 含義 |
| - | - |
| `Cloud sessions aren't available with <provider>. They run on Anthropic's infrastructure and require an Anthropic account.` | Claude Code 已設定為使用第三方提供者。訊息會以您的設定所使用的標籤指出提供者名稱，例如 `Amazon Bedrock` 或 `Google Vertex AI`。請移除該提供者的設定，例如取消設定 `CLAUDE_CODE_USE_BEDROCK`，並使用 Anthropic 帳戶登入（`claude auth login`）。 |
| `Cloud sessions are disabled by your organization's policy. Contact your organization admin to enable them.` | 您組織的 `allow_remote_sessions` 政策已關閉；請參閱[Cloud sessions are disabled by your organization's policy](https://code.claude.com/docs/zh-TW/errors.md#cloud-sessions-are-disabled-by-your-organizations-policy)。如果訊息改為指出此工作階段正在使用的某個憑證，請參閱[Cloud sessions use your claude.ai login](https://code.claude.com/docs/zh-TW/errors.md#cloud-sessions-use-your-claude-ai-login)。 |
| `Couldn't verify your organization's policy for cloud sessions. Check your network connection and try again.` | Claude Code 尚未完成載入您組織的政策，因此會拒絕傳送，而不是假設允許雲端工作階段。請檢查您的網路連線並重試。 |
| `Cloud sessions aren't available:` 後接原因 | 載入您組織的政策失敗，訊息的其餘部分說明失敗的方式。請針對其指出的原因採取行動；請參閱[Couldn't verify your organization's policy for cloud sessions](https://code.claude.com/docs/zh-TW/errors.md#couldnt-verify-your-organizations-policy-for-cloud-sessions)。 |
| `Attaching to an existing cloud session is not enabled for your account.` | 您在未使用 `-p` 的情況下執行了 `--cloud <session-id>`。請使用 `claude -p "your message" --cloud <session-id>` 傳送訊息。 |
| `Session not found: <id>` | 該 ID 或 URL 與您可存取的任何工作階段都不相符。請對照工作階段的 claude.ai/code URL 進行檢查。 |
| `cloud session <id> is archived and cannot accept new messages` | 該工作階段已封存。請改為啟動新的工作階段。 |

### 環境已過期

雲端工作階段在不活動一段時間後停止，工作階段的 VM 被回收。工作階段在等待您批准 [MCP 連接器](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)工具呼叫或登入 MCP 伺服器時計為不活動，並且可以在該等待期間過期。

從 [claude.ai/code](https://claude.ai/code) 重新開啟工作階段以佈建新 VM：

* **會恢復**：您的對話歷史記錄
* **不會恢復**：在 VM 被回收時仍在執行或尚待執行的背景工作，包括：
  * **Shell 命令**：Claude Code 會告知 Claude 哪些命令已停止。請要求 Claude 重新執行您仍需要的命令。
  * **Subagents**：Claude Code 會告知 Claude 哪些 subagents 已停止，以及其中哪些可以[繼續執行](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents)而不必從頭開始。請要求 Claude 繼續它們的工作。
  * **工作階段範圍的排程任務**：您[在工作階段中排程](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)的任務，以及正在等待下一次迭代的 `/loop`，都不會延續到重新開啟的工作階段。請要求 Claude 再次排程這些任務，或再次執行 `/loop` 以重新啟動迴圈。

## 限制

在依賴雲端工作階段進行工作流程之前，請考慮這些限制：

* **速率限制**：雲端工作階段與您帳戶內所有其他 Claude 和 Claude Code 使用共享速率限制。並行執行多個任務會按比例消耗更多速率限制。
* **時間限制**：Claude 執行的命令和 SessionStart hooks 有您可以變更的預設逾時，且設定指令碼只有在大約五分鐘內完成時才會被快取。請參閱[時間限制](https://code.claude.com/docs/zh-TW/cloud-environments.md#time-limits)
* **儲存庫驗證**：您只能在驗證到相同帳戶時將雲端工作階段拉入您的終端機
* **平台限制**：在 Anthropic 託管環境中複製儲存庫以及建立 pull request 需要 GitHub。自託管 [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md) 執行個體支援 Team 和 Enterprise 計畫。您可以透過設定 `CCR_FORCE_BUNDLE=1`，將 GitLab、Bitbucket 或其他非 GitHub 儲存庫作為[本機捆綁](#send-local-repositories-without-github)發送到雲端工作階段，但工作階段無法將結果推送回該遠端
  * **自託管環境**：若儲存庫位於其他 git 主機上，請參閱[使用 `--environment` 啟動工作階段的需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#start-a-session-on-a-repository-outside-github)。
* **組織 IP 允許清單**：雲端工作階段從 Anthropic 管理的基礎設施而不是您的網路呼叫 Anthropic API，而[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中的工作階段從您自己的網路呼叫它。如果您的組織啟用了 [IP 允許清單](https://support.claude.com/en/articles/13200993-restrict-access-to-claude-with-ip-allowlisting)，每個 Anthropic 託管的雲端工作階段都會失敗，出現身分驗證錯誤。
  * **Code Review 和排程任務**：這同樣適用於 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)，以及在 Anthropic 託管環境中執行的[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。路由到自託管環境的排程任務會從您自己的網路呼叫 API。
  * **取得豁免**：聯絡 [Anthropic 支援](https://support.claude.com/)，以從您組織的 IP 允許清單中豁免 Anthropic 託管的服務。

## 相關資源

* [雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)：為雲端工作階段配置網路存取、環境變數和設定指令碼
* [專案](https://code.claude.com/docs/zh-TW/claude-projects.md)：一個對話，Claude 在其中協調您存放庫上的平行雲端工作階段並回報結果
* [Ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)：在雲端沙箱中執行深度多代理程式碼審查
* [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)：按排程、透過 API 呼叫或回應 GitHub 事件來自動化工作
* [Hooks 配置](https://code.claude.com/docs/zh-TW/hooks.md)：在工作階段生命週期事件執行指令碼
* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md)：所有配置選項
* [安全性](https://code.claude.com/docs/zh-TW/security.md)：隔離保證和資料處理
* [資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)：Anthropic 從雲端工作階段保留的內容
* [Claude Tag](https://claude.com/docs/claude-tag/overview)：在 Slack 中由組織管理的 @Claude，在相同的雲端基礎設施上執行
