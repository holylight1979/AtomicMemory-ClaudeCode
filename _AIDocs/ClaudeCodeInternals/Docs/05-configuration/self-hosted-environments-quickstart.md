<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart | lastmod: 2026-10-28 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart（官方 zh-TW，lastmod 2026-10-28）｜分類：Configuration › Environments｜EN 摘要：Set up your first self-hosted environment: install Claude Code, create the environment, start a runner, and route a session to it.

# 自託管環境快速入門

> 設定您的第一個自託管環境：安裝 Claude Code、建立環境、啟動執行器，並將工作階段路由到該環境。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[可用性和限制](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations)涵蓋啟用路徑。本頁面讓您的第一個工作階段執行；請參閱[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)了解它們是什麼，以及[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)以進行強化和艦隊配方。

[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)在您的組織運營的基礎設施上執行 Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，由您部署的執行器程序執行。本快速入門設定您的第一個環境，這是最小的可行設定：單一主機上的一個執行器，執行一個測試工作階段。有兩個步驟：[建立環境、啟動執行器並將工作階段路由到該環境](#set-up-an-environment-and-runner)，然後[從您的終端傳送後續訊息到執行中的工作階段](#send-a-follow-up-message-to-a-running-session)。您將在兩個介面之間移動：claude.ai 用於建立環境、檢查其狀態和路由工作階段，以及主機上的終端用於執行器執行的所有操作。

完成後，您將在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上擁有一個環境、一個輪詢工作的執行器，以及在您的主機上執行的工作階段。在連接真實存放庫或內部系統之前，請完成[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)，其中涵蓋安全態勢、出口控制、git 認證和編排。

## 先決條件

### 組織和角色

claude.ai 端需要：

* **允許自託管環境**由[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上開啟；在開啟之前，**新增**按鈕不會出現。如果您不持有該角色，持有該角色的人可以建立環境並將其密鑰交給您；本頁面上的執行器和終端步驟不需要 claude.ai 角色，而在步驟檢查管理 UI 中的狀態時，執行器自己的日誌行會給您相同的信號。
* 由擁有者開啟的 [GitHub 連接器](https://claude.ai/admin-settings/connectors)，以及每位開發人員自己的 [GitHub 連線](https://code.claude.com/docs/zh-TW/web-quickstart.md#connect-github)，以便他們在啟動工作階段時可以選擇 github.com 儲存庫。

### 主機和網路

執行器主機需要：

* 具有到 `api.anthropic.com` 的出站 HTTPS、到 `claude.ai` 和下面安裝步驟重定向到的下載主機，以及到您的 git 主機以進行複製的 Linux 或 macOS 主機或容器；[網路需求表](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#network-requirements)有完整清單。Windows 不支援作為執行器主機；改為在 Linux 容器中執行執行器。開發人員工作站不受影響，因為工作階段從瀏覽器中的 claude.ai 啟動。
* 用於測試工作階段的儲存庫：公開儲存庫，或此主機已能透過其 HTTPS URL 複製且不會被要求提供憑證的儲存庫。僅有 SSH 金鑰是不夠的，因為執行器會複製儲存庫的 `https://` URL。若要改為透過 SSH 複製，請參閱[為私人網路重寫 git URL](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#rewrite-git-urls-for-private-networks)。
* 與實時同步的時鐘，例如使用 NTP。

### 執行器主機上的軟體

在啟動之前在主機上安裝：

* **Claude Code v2.1.224 或更新版本**，使用任何[標準安裝方法](https://code.claude.com/docs/zh-TW/setup.md)。執行器是標準 `claude` 二進位檔的一部分，較早版本無法識別 `self-hosted-runner` 子命令。為 Claude Tag 工作階段提供服務的執行器需要 v2.1.229 或更新版本，且其 `PATH` 上需有 `python3`，因為[控制平面為這些工作階段提供的 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#how-each-session’s-config-is-assembled) 會執行 `python3`。若要固定您的艦隊執行的確切版本，請參閱[安裝特定版本](https://code.claude.com/docs/zh-TW/setup.md#install-a-specific-version)。對於容器映像，請參閱[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#build-the-runner-image)中的 Dockerfile。
* **Git 2.24 或更新版本**。部署頁面上的某些 git 選項需要較新的版本；[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)說明每個下限。

確認主機已準備好：

```bash theme={null}
claude self-hosted-runner --help
```

準備好的主機會列印執行器的使用文字，列出 `--environment-secret-file` 等旗標。在 2.1.224 之前的版本上，該命令會改為列印一般 `claude --help` 輸出。如果您看到該輸出，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)。如果您從容器映像執行 `claude`，請使用 2.1.224 或更新版本[重新建置映像](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#build-the-runner-image)。

## 設定環境和執行器

使用[引導式設定](#run-the-guided-setup)或[手動步驟](#set-up-manually)。引導式設定是單一命令，會啟動互動式 Claude Code 工作階段，並引導您完成其餘步驟。在無法進行互動式工作階段的主機上，請改用手動步驟。當持有擁有者角色的人員已建立環境並將其密鑰交給您時，也請使用手動步驟，因為引導式設定需要以擁有者身分登入。

### 執行引導式設定

引導式設定會引導您在管理 UI 中建立環境、使用您保存的密鑰檔案啟動本機執行器、確認執行器註冊，並將速查表寫入 `./runner-setup/CHEAT-SHEET.md`。執行之前，請確認您的登入狀態和版本：

* **登入**：在您已使用持有擁有者角色的帳戶透過 `claude auth login` 登入的機器上執行它。若僅使用 API 金鑰或第三方模型提供者，工作階段會啟動，但其組織檢查會失敗。
* **版本**：確認[版本檢查](#software-on-the-runner-host)已通過。在 2.1.224 之前的版本上，setup 命令會啟動一個 Claude 工作階段，將這些字詞作為提示詞，而不是引導式設定。

若要啟動引導式設定，請在您的 shell 中執行設定子命令並按照提示進行：

```bash theme={null}
claude self-hosted-runner setup
```

設定本身不會啟動測試工作階段：它會告訴您在 claude.ai/code 啟動一個。設定的最後一步會停止它所啟動的執行器。如果您在該步驟之前離開設定，執行器會繼續執行。若要在最後一步之後繼續，請在您的 shell 中使用 `./runner-setup/CHEAT-SHEET.md` 中的命令再次啟動執行器，然後[將工作階段路由到環境](#route-a-session)。

### 手動設定

在 claude.ai 上建立環境，從主機上的終端機啟動執行器，然後返回 claude.ai 確認執行器出現，並將工作階段路由到它。如果持有擁有者角色的人員已建立環境並將其密鑰交給您，請從步驟 2 開始。

**1. 建立環境**

前往管理設定中的[**雲端環境**頁面](https://claude.ai/admin-settings/cloud-environments)。在**自託管環境**下，選擇**新增**，命名環境，然後選擇**建立**。在精靈的第二步，選擇**複製環境金鑰**以複製環境密鑰，管理 UI 將其標記為環境金鑰。claude.ai 只顯示一次密鑰，您之後無法檢索它；它在建立後 365 天過期。環境的 `ccpool_...` ID 在其詳細對話方塊中保持可見；您需要它用於[令牌驗證](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)中的 `aud` 檢查，以及用於從 CI [分派測試工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#run-the-test-loop)。

如果您遺失密鑰或需要輪換它，請從環境的**設定**標籤建立新密鑰，將新密鑰推出到您的執行器，然後撤銷舊密鑰。持有已撤銷密鑰的執行器在下一次驗證輪詢時失敗並退出，記錄 `poll auth failed`，您的編排器使用新密鑰重新啟動它們。

**2. 啟動執行器**

建立密鑰目錄。此命令和下一個命令使用 `/etc/claude`，這需要 root，且它們建立的密鑰檔案只能由執行它們的使用者讀取。如果執行器將以其他使用者身分執行，它會以 `error: Failed to read environment secret file <path> (EACCES: permission denied, open '<path>')` 退出。在這種情況下，請以執行器的使用者身分執行這兩個命令，並使用該使用者可寫入的目錄取代 `/etc/claude`，然後將相同路徑傳遞給 `--environment-secret-file`。執行器程序可以讀取的任何路徑都有效。

```bash theme={null}
mkdir -p /etc/claude
```

將環境密鑰寫入檔案。下面的命令從您的終端讀取，以便密鑰保持在 shell 歷史記錄之外：貼上您複製的值，按 Enter，然後按 Ctrl-D，子 shell 的 `umask` 使檔案只能由其擁有者讀取。

```bash theme={null}
(umask 077 && cat > /etc/claude/environment-secret)
```

選擇基本目錄，將下面執行器命令中的 `<writable-dir>` 替換為執行器可以寫入或建立的絕對路徑。執行器在啟動時建立目錄，然後簽出存放庫並在其下建立每個工作階段的目錄。沒有 `--base-dir`，它使用 `/workspace`，這只在該目錄已存在且可寫或您以 root 身份啟動執行器時有效。

> [!WARNING]
>
> 請使用專供執行器使用的目錄，而不是您的家目錄或存放您自己複製之儲存庫的目錄。執行器會將它在 `<writable-dir>/<repo-owner>/<repo>` 找到的任何內容視為自己的複製，並可能重設它以及覆寫或刪除其中的檔案。

如果執行器無法建立或寫入基本目錄，它在啟動時會以指出該目錄的錯誤退出，而不是註冊。請參閱[疑難排解](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#troubleshooting)。

然後使用 `--environment-secret-file` 和 `--base-dir` 啟動執行器：

```bash theme={null}
claude self-hosted-runner --environment-secret-file '/etc/claude/environment-secret' --base-dir '<writable-dir>'
```

執行器向您的環境註冊後會記錄 `Registered: runner_id=<runner-id>`，然後開始輪詢工作。以此命令啟動時，它會在服務完一個工作階段後按設計退出，而不是在每個回合之後退出。若要服務更多工作階段，請在它每次退出時再次啟動執行器。有關何時會發生這種情況以及執行器會記錄什麼，請參閱[如果執行器退出](#if-the-runner-exits)。

**3. 驗證執行器出現**

返回[**雲端環境**頁面](https://claude.ai/admin-settings/cloud-environments)。您的環境狀態在執行器啟動後幾秒內從**未部署執行器**變更為**健康**；開啟環境並選擇**活動**以查看執行器本身。如果您無法存取管理頁面，上一步執行器日誌中的 `Registered: runner_id=<runner-id>` 行可提供相同的訊號。

**4. 將工作階段路由到環境**

在 claude.ai/code 啟動工作階段，並從環境選擇器中選擇您的環境，其中自託管環境與 Anthropic 託管的環境並排出現。對於儲存庫，請選擇[先決條件](#host-and-network)中的儲存庫：公開儲存庫，或此主機已可以透過其 HTTPS URL 複製且不會被要求提供憑證的儲存庫。

下一個可用的執行器會拾取佇列中的工作階段，並記錄 `Picked up session <session-id>` 以及其活動計數和容量，因此您可以從執行器自己的輸出確認哪個主機接收了工作階段。在 [claude.ai/code](https://claude.ai/code) 觀看工作階段工作並閱讀 Claude 的回覆。

如果工作階段沒有開始工作，請對照您看到的情況：

* **工作階段保持佇列狀態**：請參閱[疑難排解](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#troubleshooting)。
* **工作階段因 git 錯誤而無法啟動**：如果錯誤包含 git 的 `could not read Username for`，後面接著您的 git 主機 URL，表示執行器沒有該主機的 HTTPS 憑證。
  * **提供 HTTPS 憑證**：請參閱[設定 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)
  * **改用 SSH 複製**：如果執行器主機已有 SSH 金鑰，請參閱[為私有網路重寫 git URL](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#rewrite-git-urls-for-private-networks)
  * **完成任一修正後**：再次啟動執行器並觀察失敗的工作階段，而不是啟動新的工作階段。如果它已失敗多次，請等待數分鐘，直到執行器記錄 `Picked up session`。
  * **若要改用其他儲存庫**：[封存](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#archive-sessions)或[刪除](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#delete-sessions)失敗的工作階段，然後再次啟動執行器並啟動新的工作階段。否則，執行器可能會拾取失敗的工作階段，而不是新的工作階段。

### 如果執行器退出

如果執行器在此快速入門期間退出，請再次啟動它。執行器可能會自行退出：

* **已無執行中的項目**：日誌顯示 `[runner:exit] account workload drained — exiting`。執行器在不再執行任何工作階段時會[按設計退出](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)，例如：
  * **您封存或刪除了工作階段**：再次啟動執行器
  * **工作階段無法啟動**：[修正原因](#session-doesnt-start)，然後再次啟動執行器
* **失去聯繫**：日誌顯示一行 `[runner:fatal]`，並帶有 `runner record gone server-side` 或 `poll auth failed`。如果執行器與 Anthropic 失去聯繫一段時間，例如因為主機進入睡眠狀態，它可能會在下次連線到 Anthropic 時退出。

完成一個回合並不會結束您的測試工作階段。第一個回合之後，工作階段仍處於附加狀態，執行器也仍在執行，因此您可以[向工作階段傳送後續訊息](#send-a-follow-up-message-to-a-running-session)，而無需先重新啟動執行器。

對於生產環境，在編排器下部署執行器，該編排器在退出時重新啟動它，並在執行器啟動後立即持續退出時等待更長的時間再重新啟動。請參閱[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)和[當執行器退出時](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#when-the-runner-exits)。

## 傳送後續訊息到執行中的工作階段

一旦工作階段在您的環境上執行，從任何您使用 `claude auth login` 登入的機器上的 `claude` CLI 傳送後續訊息；該命令不需要從啟動工作階段的機器執行。該命令發佈一條訊息：

```bash theme={null}
claude -p "your message" --cloud <session-id>
```

對於 `<session-id>`，傳遞裸 `session_...` 或 `cse_...` ID 或工作階段的 claude.ai/code URL。成功傳送會列印 `Sent to cloud session.` 以及工作階段 ID 和檢視連結。接受的 ID 形式、JSON 輸出，以及帳戶和原則需求在[從 CLI 傳送後續訊息](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-follow-ups-from-the-cli)上，因為該命令對 Anthropic 託管的工作階段的工作方式相同。

## 接下來的步驟

* [部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)：強化部署、控制出口、設定 git 認證，並在 Kubernetes 或 Compose 下執行艦隊
* [自訂工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md)：包裝器指令碼、生命週期掛鉤、隨需執行器、MCP 伺服器和權限
* [端到端測試](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md)：一個 CI 煙霧測試，分派工作階段並讀取 Claude 的回覆
