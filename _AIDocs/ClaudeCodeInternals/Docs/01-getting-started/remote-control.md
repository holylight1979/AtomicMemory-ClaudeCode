<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/remote-control | lastmod: 2026-11-02 | section: Getting started / Platforms and integrations -->
> 來源：https://code.claude.com/docs/zh-TW/remote-control（官方 zh-TW，lastmod 2026-11-02）｜分類：Getting started › Platforms and integrations｜EN 摘要：Continue a local Claude Code session from your phone, tablet, or any browser using Remote Control. Works with claude.ai/code and the Claude mobile app.

# 使用 Remote Control 從任何裝置繼續本地會話

> 使用 Remote Control 從您的手機、平板電腦或任何瀏覽器繼續本地 Claude Code 會話。適用於 claude.ai/code 和 Claude 行動應用程式。

Remote Control 將 [claude.ai/code](https://claude.ai/code) 或 Claude 應用程式（[iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 和 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude)）連接到在您機器上執行的 Claude Code 會話。在您的辦公桌開始一項任務，然後從沙發上的手機或另一台電腦上的瀏覽器繼續。

當您在機器上啟動 Remote Control 會話時，Claude 會在整個過程中在本地執行，因此您的程式碼執行和檔案系統存取保持在您的機器上。使用 Remote Control，您可以：

* **遠端使用您的完整本地環境**：您的檔案系統、[MCP servers](https://code.claude.com/docs/zh-TW/mcp.md)、工具和專案設定都保持可用，輸入 `@` 會自動完成來自您本地專案的檔案路徑。
* **同時在兩個介面上工作**：對話和 [subagents](https://code.claude.com/docs/zh-TW/sub-agents.md) 和 [dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md) 的進度在所有連接的裝置上保持同步，因此您可以從終端機、瀏覽器和手機交替發送訊息。
* **從您的手機或瀏覽器傳送影像和檔案**：在 Claude 應用程式或 claude.ai/code 中附加照片或檔案，可以有或沒有標題。Claude 會直接將附加的照片視為您訊息的一部分。Claude Code 會將其他檔案下載到您的機器，並將其作為 `@` 檔案參考傳遞給 Claude。
* **克服中斷**：如果您的筆記型電腦進入睡眠狀態或網路中斷，當您的機器重新上線時，Claude Code 會自動重新連接。

與[網頁版 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)（在雲端基礎設施上執行）不同，Remote Control 會話直接在您的機器上執行並與您的本地檔案系統互動。網頁和行動介面只是該本地會話的一個窗口，因此您的電腦必須保持開啟，且 `claude` 程序必須持續執行。

> [!NOTE]
>
> Remote Control 是 Claude Code 的功能。如需了解其他 Claude 產品中的對話，請參閱 [Claude 說明中心](https://support.claude.com)。

## 需求

在使用遠端控制之前，請確認您的環境符合以下條件：

* **訂閱**：適用於 Pro、Max、Ultra、Team 和 Enterprise 方案。不支援 API 金鑰。在 Team 和 Enterprise 上，擁有者必須先在 [Claude Code 管理設定](https://claude.ai/admin-settings/claude-code)中啟用 Remote Control 切換。
* **自訂角色**：如果您的 Enterprise 組織使用[自訂角色](https://support.claude.com/en/articles/13930452)管理您的存取權，您的角色必須同時授予您雲端工作階段權限與 **Claude Code remote control** 權限。若缺少其中任一項，啟動 Remote Control 時會顯示 [`Remote Control is disabled by your organization's policy`](#remote-control-is-disabled-by-your-organizations-policy)。請要求擁有者檢查您的角色，並在 [**Organization settings > Roles**](https://claude.ai/admin-settings/roles) 中新增缺少的權限。
* **驗證**：執行 `claude` 並使用 `/login` 透過 claude.ai 登入（如果您還未登入）。沒有符合條件的登入，`claude remote-control` 會以錯誤結束，而 `claude --remote-control` 仍會啟動互動式工作階段，並在啟動後不久顯示遠端控制失敗通知。
* **API 端點**：在以下任何配置中都不可用：
  * 您使用 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry。
  * 您將 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 `api.anthropic.com` 以外的主機，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或代理。取消設定該變數以使用遠端控制。
  * 您透過企業 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入。
* **功能旗標評估**：如果您設定了[關閉功能旗標評估的環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)，Remote Control 是否可用取決於您設定的是哪一個：
  * 如果您設定了 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 或 `DISABLE_GROWTHBOOK`，Remote Control 將不可用。在您的 shell 環境或 [`settings.json` 檔案](https://code.claude.com/docs/zh-TW/settings-reference#all-settings)的 `env` 區塊中取消設定該變數，以使用 Remote Control。
  * 如果您只設定了 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK`，Remote Control 保持可用，除非您的組織要求[受信任的裝置](#trusted-devices)。如果是這樣，請取消設定該變數以使用 Remote Control。在設定任一變數的情況下使用 Remote Control，需要 Claude Code v2.1.283 或更新版本，若在 Claude Desktop 應用程式中則需要 v2.1.304 或更新版本。
* **工作區信任**：在您尚未信任的目錄中，`claude remote-control` 會列印信任該目錄會啟用的功能，並在啟動前詢問 `Trust <directory>? [y/N]`。回答 `y` 會儲存該選擇，但在您的主目錄中除外，該目錄中信任永遠不會被儲存，每次執行時都會重新詢問。當其標準輸入或輸出不是終端機時，該命令無法詢問並會以 [`Workspace not trusted`](https://code.claude.com/docs/zh-TW/errors#workspace-not-trusted-when-starting-remote-control) 錯誤結束。

## 啟動 Remote Control 工作階段

您可以從 CLI、[Claude Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)或 VS Code 擴充功能啟動 Remote Control 工作階段。CLI 提供三種呼叫模式；Desktop 應用程式和 VS Code 則使用 `/remote-control` 命令。

> [tab] 伺服器模式
>
> 在專案目錄中執行：
>
> ```bash theme={null}
> claude remote-control
> ```
>
> 在您接受 Remote Control 的一次性確認之前，`claude remote-control` 會說明其功能，並在啟動伺服器前詢問 `Enable Remote Control? (y/n)`。回答 `y` 即可接受並啟動伺服器。若您拒絕，Claude Code 會在不啟動伺服器的情況下結束，並在您下次執行此命令時再次詢問。
>
> 在伺服器模式下，此程序會持續在終端機中執行，等待遠端連線。它會顯示一個 URL，您可以用來[從其他裝置連線](#connect-from-another-device)，也可以按空白鍵顯示 QR 碼，以便從手機快速存取。當遠端工作階段處於作用中狀態時，終端機會顯示連線狀態和工具活動。
>
> 可在 `remote-control` 之後傳入下列任一旗標：
>
> | 旗標 | 說明 |
> | - | - |
> | `--name "My Project"` | 設定自訂工作階段標題，顯示於 claude.ai/code 的工作階段清單中。 |
> | `--remote-control-session-name-prefix <prefix>` | 未設定明確名稱時，自動產生之工作階段名稱的前綴。預設為您機器的主機名稱，產生如 `myhost-graceful-unicorn` 的名稱。設定 `CLAUDE_REMOTE_CONTROL_SESSION_NAME_PREFIX` 亦可達到相同效果。 |
> | `-c`, `--continue` | 恢復此目錄中上一個伺服器啟動時所建立的工作階段，而非建立新的工作階段。請參閱[停止伺服器後恢復工作階段](#resume-sessions-after-stopping-the-server)。不可與 `--session-id`、`--spawn`、`--capacity` 或 `--create-session-in-dir` 合併使用。需要 Claude Code v2.1.200 或更新版本。 |
> | `--session-id <id>` | 依 ID 恢復單一工作階段。請參閱[停止伺服器後恢復工作階段](#resume-sessions-after-stopping-the-server)。不可與 `--continue`、`--spawn`、`--capacity` 或 `--create-session-in-dir` 合併使用。需要 Claude Code v2.1.200 或更新版本。 |
> | `--spawn <mode>` | 伺服器建立工作階段的方式。 • `same-dir`（未儲存模式時的預設值）：所有工作階段共用目前的工作目錄，因此若編輯相同檔案可能會發生衝突。 • `worktree`：每個隨需建立的工作階段都會取得自己的 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md)。需要 git 儲存庫或 [`WorktreeCreate` hook](https://code.claude.com/docs/zh-TW/hooks#worktreecreate)。 • `session`：單一工作階段模式。僅服務一個工作階段，並拒絕其他連線。僅能在啟動時設定。 在執行期間按 `w` 可在 `same-dir` 與 `worktree` 之間切換。您切換到的模式會成為[此專案的預設值](#set-the-default-spawn-mode-for-a-project)。 |
> | `--capacity <N>` | 同時進行的工作階段數量上限。預設為 32。不可與 `--spawn=session` 一起使用。 |
> | `--[no-]create-session-in-dir` | 在伺服器啟動時於目前目錄預先建立一個工作階段，讓您可以立即開始輸入。在 `worktree` 模式下，此工作階段會留在目前目錄，而隨需建立的工作階段則會取得隔離的 worktree。預設為開啟。若您傳入 `--no-create-session-in-dir` 以不建立任何工作階段的方式啟動，Claude Code 會在您停止伺服器時封存伺服器的工作階段，因此將沒有可[恢復](#resume-sessions-after-stopping-the-server)的工作階段。 |
> | `--permission-mode <mode>` | 設定伺服器工作階段的起始[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)，例如 `acceptEdits`。接受 `manual` 作為 `default` 的別名；無法辨識的模式會在啟動時停止伺服器並列出有效的模式。 |
> | `--chrome` / `--no-chrome` | 在伺服器建立的工作階段中開啟或關閉 [Chrome 整合](https://code.claude.com/docs/zh-TW/chrome.md)，讓 Claude 能在您從其他裝置工作時使用您機器上的 Chrome。若未使用任一旗標，伺服器預先建立的工作階段，以及您自行從 claude.ai/code 或 Claude 應用程式啟動的任何工作階段，都會以 Chrome 關閉的狀態開始，即使您已[預設啟用 Chrome](https://code.claude.com/docs/zh-TW/chrome.md#enable-chrome-by-default) 亦然。伺服器為您的某個[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)執行緒啟動的工作階段則會改為遵循該設定，但 `bypassPermissions` 模式除外。需要 Claude Code v2.1.273 或更新版本。 |
> | `-d`, `--debug[=<filter>]` | 為伺服器開啟除錯日誌，可選擇依類別篩選。篩選條件只能以 `=` 形式傳入，例如 `--debug=api,hooks`。需要 Claude Code v2.1.282 或更新版本。 |
> | `--debug-file <path>` | 將除錯日誌寫入指定的檔案。 |
> | `--verbose` | 顯示詳細的連線與工作階段日誌。 |
> | `--sandbox`, `--no-sandbox` | 已於 v2.1.300 移除。若您傳入任一旗標，伺服器會[以錯誤結束](https://code.claude.com/docs/zh-TW/errors.md#sandbox-is-not-supported-by-claude-remote-control)而不會啟動。 |
>
> 若您在 `remote-control` 之前傳入全域 `claude` 旗標，或包裝指令碼加入了此類旗標，Claude Code 不會將該旗標沿用至伺服器建立的工作階段。只有在已知捨棄該旗標不會改變這些工作階段的能力時，Claude Code 才會讓該旗標通過，例如 `--verbose` 或 `--model`。對於任何其他旗標，例如 `--settings`，Claude Code 會[拒絕啟動](https://code.claude.com/docs/zh-TW/errors.md#not-carried-over-to-the-sessions-remote-control-starts)，並指出需要移除的旗標名稱。
>
> 若要將伺服器啟動的工作階段置於沙箱中，請在設定檔中開啟[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。
>
> 若要在終端機中列印 `remote-control` 的旗標，請執行 `claude remote-control --help`。在 v2.1.302 之前，若未以符合資格的帳戶登入，此命令會改為傳回[疑難排解](#troubleshooting)中所列的其中一個錯誤。

> [tab] 互動式工作階段
>
> 若要啟動已啟用 Remote Control 的一般互動式 Claude Code 工作階段，請使用 `--remote-control` 旗標（或 `--rc`）：
>
> ```bash theme={null}
> claude --remote-control
> ```
>
> 可選擇為工作階段傳入名稱：
>
> ```bash theme={null}
> claude --remote-control "My Project"
> ```
>
> 這會在終端機中提供完整的互動式工作階段，您也可以從 claude.ai 或 Claude 應用程式加以控制。與 `claude remote-control`（伺服器模式）不同，您可以在本機輸入訊息，同時該工作階段也可供遠端使用。

> [tab] 從現有工作階段
>
> 若您已在 Claude Code 工作階段中，並希望從遠端繼續，請使用 `/remote-control`（或 `/rc`）命令：
>
> ```text theme={null}
> /remote-control
> ```
>
> 傳入名稱作為引數即可設定自訂工作階段標題：
>
> ```text theme={null}
> /remote-control My Project
> ```
>
> 這會啟動一個 Remote Control 工作階段，並沿用您目前的對話歷程。
>
> 在您接受 Remote Control 的一次性確認之前，`/remote-control` 連線前會出現對話框。選擇 **Enable Remote Control** 即可接受並連線。若您選擇 **Never mind** 或按 Esc，Claude Code 不會連線，並會在您下次執行 `/remote-control` 時再次詢問。
>
> 此命令無法使用 `--verbose` 旗標。

> [tab] VS Code
>
> 在 [Claude Code VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)中，於提示詞輸入框中輸入 `/remote-control` 或 `/rc`。
>
> ```text theme={null}
> /remote-control
> ```
>
> 當 Remote Control 開啟時，Claude Code 會在提示詞輸入框的頁尾顯示 **Remote Control** 指示器。工作階段連線後，按一下指示器即可直接前往該工作階段，或在 [claude.ai/code](https://claude.ai/code) 的工作階段清單中找到它。Claude Code 也會在對話中張貼工作階段 URL。若要中斷連線，請再次執行 `/remote-control`。
>
> 與 CLI 不同，VS Code 命令不接受名稱引數，也不會顯示 QR 碼。工作階段標題會根據您的對話歷程或第一個提示詞產生。

> [tab] Desktop 應用程式
>
> 在 [Claude Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md) Code 分頁的本機工作階段中，於提示詞輸入框中輸入 `/remote-control` 或 `/rc`。
>
> ```text theme={null}
> /remote-control
> ```
>
> 工作階段連線後，即可在 [claude.ai/code](https://claude.ai/code) 的工作階段清單中找到它。若要中斷連線，請再次執行 `/remote-control`。
>
> 若要改為預設為每個工作階段開啟 Remote Control，請參閱[為所有工作階段啟用 Remote Control](#enable-remote-control-for-all-sessions)。

### 檢查連線狀態

在互動式工作階段中，當 Remote Control 已連線時，終端機會顯示 `/rc active` 指示器，並連結至 claude.ai 上的工作階段。當終端機寬度不足以容納時，指示器會隱藏。若要查看工作階段 URL 以及用於[從其他裝置連線](#connect-from-another-device)的 QR 碼，請再次執行 `/remote-control` 以開啟狀態面板。此面板也可讓您在本機工作階段持續執行的同時中斷 Remote Control 連線。

若互動式工作階段中的連線失敗，指示器會變更以顯示失敗，Claude Code 會在通知中顯示原因並將其加入對話中。請執行 `/remote-control` 重新連線，除非原因表示工作階段已在其他地方發生變更：

* **Another connection took over this session**：另一個裝置或 Claude Code 工作階段目前擁有此工作階段。只有在您想要取回時，才執行 `/remote-control`。
* **This session was ended or archived from another device or app**：只有在您想要取回工作階段時，才執行 `/remote-control`。Claude Code 會重新開啟已封存的工作階段。
* **The server no longer reports this session**：此工作階段可能已從其他裝置或應用程式中刪除。

### 從其他裝置連線

Remote Control 工作階段啟用後，您可以透過幾種方式從其他裝置連線：

* 在任何瀏覽器中**開啟 Claude Code 顯示的 URL**，即可前往 [claude.ai/code](https://claude.ai/code)。
* **掃描 URL 旁顯示的 QR 碼**，即可在 Claude 應用程式中開啟。使用 `claude remote-control` 時，按空白鍵可切換 QR 碼的顯示。
* **開啟 [claude.ai/code](https://claude.ai/code) 或 Claude 應用程式**，並在工作階段清單中依名稱找到該工作階段。在 Claude 行動應用程式中，點選導覽列中的 **Code** 即可前往工作階段清單。Remote Control 工作階段在線上時會顯示帶有綠色狀態點的電腦圖示。

連線時，裝置會顯示該工作階段已在背景執行的任何 subagent 和工作流程。從裝置停止其中一個，Claude Code 就會在您的機器上停止該工作。

遠端工作階段標題會依下列順序選定：

1. 您傳給 `--name`、`--remote-control` 或 `/remote-control` 的名稱
2. 您以 `/rename` 設定的標題
3. 現有對話歷程中最後一則有意義的訊息
4. 自動產生的名稱，例如 `myhost-graceful-unicorn`，其中 `myhost` 為您機器的主機名稱，或您以 `--remote-control-session-name-prefix` 設定的前綴

若您未設定明確的名稱，Claude Code 會在您送出提示詞後更新標題以反映該提示詞。當您從 claude.ai 或 Claude 應用程式重新命名工作階段時，Claude Code 也會更新 `claude --resume` 中顯示的本機標題。

若您尚未安裝 Claude 應用程式，請在 Claude Code 中執行 `/mobile` 以顯示 [claude.ai/mobile](https://claude.ai/mobile) 的 QR 碼，它會為您的手機開啟對應的應用程式商店。

### 已連線裝置所見的內容

已連線的裝置會即時顯示終端機中的對話。下列情況超出一般訊息的範圍：

* **壓縮與 `/clear`**：當 Claude Code [壓縮對話](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)時，已連線的裝置會顯示進度，接著顯示對話被壓縮的位置。當您執行 `/clear` 時，已連線裝置上的對話也會重設。
* **使用 `/resume` 切換對話**：已連線的裝置不會收到切換後對話的標題或先前歷程，但雙向的新訊息都會傳送至終端機中目前開啟的對話，或從該對話傳出。若要再次從裝置處理原本的對話，請在終端機中執行 `/resume` 並切換回該對話。
* **使用 `/teleport` 拉取工作階段**：當您使用 `/teleport` 將[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-cloud-to-terminal)拉取至終端機時，已連線的裝置不會收到所拉取對話的先前歷程。雙向的新訊息會傳送至所拉取的對話或從該對話傳出，該對話現在即為終端機中開啟的對話。
* **來自您其他工作階段的訊息**：透過[跨工作階段傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，同一個連線會傳遞您在不同機器上各工作階段之間的訊息。
* **變更的差異**：當工作階段的目錄位於 git 儲存庫中時，已連線裝置的差異窗格會顯示您的變更。在具有領先儲存庫預設分支之提交的分支上，窗格會顯示自該分支從預設分支分出以來的變更，包括您尚未提交的編輯。在預設分支本身，或在未領先預設分支的分支上，窗格只會顯示您尚未提交的變更。
* **模型**：當您從已連線的裝置選擇[模型](https://code.claude.com/docs/zh-TW/model-config.md)時，Claude Code 會以該模型執行工作階段。需要 Claude Code v2.1.238 或更新版本。您從裝置的模型控制項選擇的模型僅適用於目前的工作階段。當您從裝置向互動式工作階段傳送 `/model <name>` 時，Claude Code 也會設定新工作階段的預設值。
* **Effort 等級**：當您從已連線的裝置以 `/effort` 或裝置的 effort 控制項設定 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)時，Claude Code 會將其套用至您機器上的工作階段。若您已使用 `CLAUDE_CODE_EFFORT_LEVEL` 固定等級，工作階段會維持該等級，且 Claude Code 會拒絕從 effort 控制項選擇的不同等級。從 effort 控制項選擇等級需要您的機器上安裝 Claude Code v2.1.234 或更新版本。
* **連線失敗後重新連線**：執行 `/remote-control` 即可重新連線。若在此期間壓縮改寫了對話，或您使用 `/resume` 切換了對話，Claude Code 會封存其先前使用的伺服器工作階段，而不會將其留在工作階段清單中。您仍可在 claude.ai/code 的[已封存工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#find-an-archived-session)中找到該工作階段。在裝置仍連線時切換對話不會封存工作階段。

### 為所有工作階段啟用 Remote Control

除非開啟自動連線，否則 Remote Control 只會在您明確執行 `claude remote-control`、`claude --remote-control` 或 `/remote-control` 時啟用。若要為每個互動式工作階段開啟自動連線，請在 Claude Code 中執行 `/config` 並設定 **Enable Remote Control for all sessions**。此切換開關有三個值：

* **`true`**：互動式工作階段啟動時自動連線。
* **`false`**：關閉自動連線，但來自[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)的 `true` 會優先於此值，因為 Claude Code 會將此選擇儲存至您的使用者設定。專案或本機設定（`.claude/settings.json`、`.claude/settings.local.json`）中的 `false` 即使在受管設定為 `true` 的情況下，仍會關閉自動連線。
* **`default`**：清除您的選擇，若您的組織已設定管理員預設值則遵循該值，否則遵循 Claude Code 目前的預設值。若您設定了 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK`，請參閱[在設定 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK` 時自動連線](#auto-connect-with-disable-telemetry-or-do-not-track)。

VS Code 擴充功能與 Desktop 應用程式也有自動連線切換開關：

* **VS Code 擴充功能**：[命令選單](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box) Settings 區段中的 **Enable Remote Control for all sessions**。
* **Desktop 應用程式**：**Settings > Code** 或 **Settings > Claude Code** 中的 **Connect new sessions to Remote Control**。請參閱[控制哪些工作階段會出現在您的其他裝置上](https://code.claude.com/docs/zh-TW/desktop.md#control-which-sessions-appear-on-your-other-devices)。

若要改從設定檔開啟自動連線，請在您的使用者 `~/.claude/settings.json` 或[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中將 [`remoteControlAtStartup`](https://code.claude.com/docs/zh-TW/settings-reference#remotecontrolatstartup) 設為 `true`。在專案或本機設定（`.claude/settings.json`、`.claude/settings.local.json`）中，Claude Code 會採用 `false` 並為該儲存庫關閉自動連線，但會忽略 `true`，因此簽入的檔案無法為每位開啟該儲存庫的人開啟 Remote Control。

自動連線會以您自己的 claude.ai 帳戶登入，因此它所啟動的工作階段只會出現在您自己帳戶的 Claude 應用程式中，不會授予其他任何人存取權。

開啟此設定後，每個互動式 Claude Code 程序都會註冊一個遠端工作階段。若您執行多個執行個體，每個執行個體都會取得自己的遠端工作階段。若要從單一程序執行多個同時進行的工作階段，請改用[伺服器模式](#start-a-remote-control-session)。

#### 在設定 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK` 時自動連線

若僅設定了 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK`，您的工作階段不會透過組織的管理員預設值或 Claude Code 本身的預設值自動連線。若有其他因素導致您無法使用 Remote Control，例如 `DISABLE_GROWTHBOOK` 或 LLM 閘道，請改從[需求](#requirements)開始。

在僅設定 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK` 的情況下開啟自動連線之前，請確認您的 Claude Code 版本符合[這些變數的需求](#requirements)。接著確認您的組織是否要求 [Trusted Devices](#trusted-devices)：

* **未要求**：在 `/config` 中將 **Enable Remote Control for all sessions** 設為 `true`。
* **已要求**：設定 `DISABLE_TELEMETRY` 或 `DO_NOT_TRACK` 時無法使用 Remote Control。請取消設定這兩個變數中您所設定的那一個。若您的工作階段仍未自動連線，請在 `/config` 中將 **Enable Remote Control for all sessions** 設為 `true`。

### 停止伺服器後恢復工作階段

當您以 Ctrl+C 停止 `claude remote-control` 時，它所服務的工作階段將不再回應來自手機或瀏覽器的操作。只要您未在同一目錄中執行另一個 `claude remote-control`，且未以 `--no-create-session-in-dir` 啟動此伺服器，Claude Code 就不會封存這些工作階段。若要恢復它們，請在同一目錄中執行下列其中一個命令：

* **`claude remote-control`**：恢復伺服器所服務的每個工作階段。
* **`claude remote-control --continue`**：僅恢復伺服器啟動時建立的工作階段，並在該工作階段結束時結束。若此目錄沒有記錄，Claude Code 會使用此儲存庫其他 git worktree 中最新的記錄。
* **`claude remote-control --session-id <id>`**：僅恢復您傳入 ID 的工作階段，並在該工作階段結束時結束。ID 是 claude.ai/code 上工作階段 URL 中位於 `/code/` 與任何 `?` 之間的部分。

這些命令在伺服器停止後約四小時內有效。之後，請執行 `claude remote-control` 以啟動新的工作階段。若您在此期間封存了工作階段，在 Claude Code v2.1.228 或更新版本上，`--continue` 和 `--session-id` 會將其取消封存。

若要恢復以 `claude --remote-control` 或 `/remote-control` 啟動的工作階段，請以 `claude --continue` 或 `claude --resume` 恢復對話。關於恢復的對話所使用的起始權限模式，請參閱[恢復時的權限模式](https://code.claude.com/docs/zh-TW/sessions.md#permission-mode-on-resume)。若 Remote Control 未重新連線，請參閱 [Couldn't reconnect to your Remote Control session](#couldnt-reconnect-to-your-remote-control-session)。

若您在第二個終端機中恢復對話，而第一個終端機仍開啟著 Remote Control，Claude Code 會在第二個終端機中列印 `Remote Control not started here` 通知，並在該處保持 Remote Control 關閉，而不會從第一個終端機奪走該工作階段。在第二個終端機中執行 `/remote-control` 即可將 Remote Control 移至該終端機。

當您在 Claude Desktop 或 IDE 擴充功能中恢復一個曾開啟 Remote Control 的對話時，Claude Code 會將其重新連結至現有的 claude.ai 工作階段，而不會在工作階段清單中新增一個工作階段。

### 為專案設定預設的 spawn 模式

若 `claude remote-control` 在啟動時列印 `Spawn mode: <mode> (saved for this folder; press w to change)`，表示伺服器正以先前為此專案儲存的 spawn 模式啟動。

儲存的模式來自您在自己的終端機中所做的選擇。若 `claude remote-control` 曾在該處詢問 `Spawn mode for this project:`，Claude Code 會保留您的回答：`1` 代表 `same-dir`，`2` 代表 `worktree`。若您在其執行期間按下 `w`，Claude Code 會保留您切換到的模式，即使該次執行是以 `--spawn same-dir` 或 `--spawn worktree` 啟動的亦然。

* 當伺服器以 `same-dir` 或 `worktree` 模式執行時，在伺服器的終端機中按 `w` 即可切換至另一種模式。切換需要 git 儲存庫或 `WorktreeCreate` hook。
* 若要在單次執行中使用不同的模式，請傳入 `--spawn <mode>`。

## 連接和安全性

您的本地 Claude Code 會話僅發出出站 HTTPS 請求，永遠不會在您的機器上開啟入站連接埠。當您啟動 Remote Control 時，它會向 Anthropic API 註冊並輪詢工作。當您從另一個裝置連接時，伺服器會透過串流連接在網頁或行動用戶端與您的本地會話之間路由訊息。

所有流量都透過 TLS 上的 Anthropic API 傳輸，與任何 Claude Code 會話相同的傳輸安全性。連接使用多個短期認證，每個認證的範圍限定為單一目的並獨立過期。

Remote Control 連接時，會話記錄（包括您的訊息、Claude 的回應和工具活動）會儲存在 Anthropic 伺服器上。儲存的記錄可讓對話在您的裝置間保持同步，並讓會話在網路中斷後重新連接。執行和檔案系統存取保留在您的機器上，儲存的記錄會根據[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)政策保留。

若要完全關閉 Remote Control，請使用 [`disableRemoteControl`](https://code.claude.com/docs/zh-TW/settings-reference#disableremotecontrol) 設定。已啟用[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md)或已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織無法啟用 Remote Control。

## 受信任的裝置

> [!NOTE]
>
> 受信任的裝置目前處於測試版。功能和功能可能會隨著體驗的改進而演變。
>
> 受信任的裝置在 Pro、Max、Ultra、Team 和 Enterprise 方案上可用，預設為關閉。在 Team 和 Enterprise 方案上，擁有者會為組織啟用它。在 Pro、Max 和 Ultra 方案上，您可以在設定中的 Cowork 或帳戶頁面上自行啟用**需要受信任的裝置**。

受信任的裝置要求您在從 claude.ai、Claude 行動應用程式或 Claude Desktop 檢視或控制 Remote Control 工作階段之前，必須使用經過驗證的裝置。此要求適用於您組織的每個成員，或在 Pro、Max 或 Ultra 方案上僅適用於您。它將 Remote Control 存取與已知裝置和最近的身分驗證相關聯，而不僅僅是已登入的帳戶。

當設定開啟時，與 Remote Control 會話互動需要以下兩項：

* **已註冊的裝置**：成員用於 Remote Control 的每個瀏覽器、手機或桌面應用程式都會註冊自己的認證。註冊僅在完整登入後不久提供，因此裝置作為真實驗證的一部分加入受信任清單，而不是在背景中無聲地進行。
* **最近的登入**：成員的登入不超過 18 小時。成員不需要每天登入一次，而是使用 Face ID、Touch ID、Windows Hello 或通行金鑰確認存在。此生物識別步驟立即重新整理會話。

生物識別檢查透過作業系統或瀏覽器在裝置上執行，與通行金鑰登入相同的機制。Anthropic 永遠不會接收或儲存指紋、臉部資料或任何其他生物識別資訊。只有裝置的公鑰和基本中繼資料（例如顯示名稱、平台和註冊時間）會被儲存。

該設定適用於 Claude Code 中的 Remote Control，以及 [Cowork](https://claude.com/docs/cowork/overview) 中的 Computer access。本頁面說明 Claude Code 的部分。一般 Claude 聊天、終端機中的 Claude Code 和 API 使用不受影響。

### 為 Team 或 Enterprise 組織啟用受信任的裝置

擁有者從 claude.ai 組織設定啟用該設定。

**1. 前往 Capabilities 頁面**

前往 [**Organization settings > Capabilities > Remote sessions**](https://claude.ai/admin-settings/capabilities)。**需要受信任的裝置**切換會出現在該部分中。

**2. 開啟需要受信任的裝置**

該設定適用於組織的每個成員以及在您啟用它後啟動的 Remote Control 會話。在切換開啟之前已經執行的會話不會被追溯保護，並在沒有裝置要求的情況下繼續，直到它們結束。不提供按團隊或按專案的範圍設定。

**3. 告知成員預期的情況**

在啟用該設定後，成員第一次從瀏覽器、手機或桌面應用程式檢視或控制新的 Remote Control 會話時，系統會提示他們註冊該裝置。提前讓他們知道可以避免混淆。

### 成員看到的內容

註冊是每個裝置的一次性步驟。之後，唯一可見的變化是偶爾的生物識別提示。

* **首次在每個裝置上使用**：成員被要求註冊。如果他們的登入不是最近的，他們首先透過您的一般流程登入，包括 SSO（如果已配置），然後確認註冊。
* **日常使用**：具有已註冊裝置和最近登入的成員看不到任何提示。當登入超過 18 小時時，下一次 Remote Control 互動會顯示單個 Face ID、Touch ID、Windows Hello 或通行金鑰提示。
* **未註冊的裝置**：在裝置被註冊之前，無法檢視或控制 Remote Control 會話。該裝置上的一般 Claude 聊天不受影響。
* **沒有平台驗證器**：沒有 Face ID、Touch ID 或 Windows Hello 的機器上的成員可以使用硬體安全金鑰，或改為再次登入而不是升級。
* **在終端機中**：執行 Claude Code 的機器在開發人員登入 CLI 時會自動接收自己的認證。終端機中沒有單獨的註冊步驟。

### 管理已註冊的裝置

成員可以從帳戶設定中檢視和撤銷自己的裝置。

開啟 [claude.ai/settings/account](https://claude.ai/settings/account#trusted-devices) 並找到**受信任的裝置**部分，以查看每個已註冊的裝置及其名稱、平台和註冊日期。移除裝置會立即撤銷其認證，裝置可以在新登入後稍後重新註冊。如果未更新，認證也會自行過期，因此未使用的裝置會自動從受信任清單中刪除。

對於遺失或被盜的裝置，成員從此頁面移除它。如果成員無法登入，管理員可以在管理員主控台中使用**到處登出**來撤銷該成員的每個會話和已註冊的裝置，之後成員重新註冊他們仍然持有的裝置。

## 遠端控制與雲端工作階段

遠端控制和[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)都使用 claude.ai/code 介面。主要差異在於工作階段執行的位置：遠端控制在您的機器上執行，因此您的本機 MCP 伺服器、工具和專案設定保持可用。雲端工作階段在雲端基礎設施上執行，預設由 Anthropic 管理。

當您正在進行本機工作並想從另一台裝置繼續時，請使用遠端控制。當您想在沒有任何本機設定的情況下開始工作、處理您未複製的儲存庫，或並行執行多個工作時，請使用雲端工作階段。[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)結合了兩者：其執行緒在雲端執行，當您在那裡要求時，它使用遠端控制來[在您的電腦上執行執行緒](https://code.claude.com/docs/zh-TW/claude-projects.md#run-a-thread-on-your-own-computer)。

Claude Code 提供了多種方式讓您在不在終端機時進行工作。它們在觸發工作的方式、Claude 執行的位置以及您需要設定的程度上有所不同。

| | 觸發 | Claude 執行位置 | 設定 | 最適合 |
| :- | :- | :- | :- | :- |
| [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch) | 從 Claude 行動應用程式傳送任務訊息 | 您的機器 (Desktop) | [將行動應用程式與 Desktop 配對](https://support.claude.com/en/articles/13947068) | 在您不在時委派工作，最少設定 |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 從 [claude.ai/code](https://claude.ai/code) 或 Claude 行動應用程式驅動執行中的工作階段 | 您的機器 (CLI、Desktop 或 VS Code) | 執行 [`claude remote-control` 或 `/remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) | 從另一個裝置控制進行中的工作 |
| [Channels](https://code.claude.com/docs/zh-TW/channels.md) | 從聊天應用程式 (如 Telegram 或 Discord) 或您自己的伺服器推送事件 | 您的機器 (CLI) | [安裝頻道外掛程式](https://code.claude.com/docs/zh-TW/channels.md#quickstart) 或 [建立您自己的](https://code.claude.com/docs/zh-TW/channels-reference.md) | 對外部事件 (如 CI 失敗或聊天訊息) 做出反應 |
| [Slack](https://code.claude.com/docs/zh-TW/slack.md) | 在團隊頻道中提及 `@Claude` | Anthropic 雲端 | [安裝 Slack 應用程式](https://code.claude.com/docs/zh-TW/slack.md#setting-up-claude-code-in-slack) 並啟用 [網路上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，適用於 Pro、Max 和 Ultra 方案 | 從團隊聊天進行 PR 和審查 |
| [Self-hosted environments](https://code.claude.com/docs/zh-TW/self-hosted-environments) | 啟動 [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 並選擇您組織的環境 | 您組織的基礎設施 | [部署執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)，在 Team 和 Enterprise 方案上 | 必須在您的網路內執行的雲端工作階段 |
| [Scheduled tasks](https://code.claude.com/docs/zh-TW/scheduled-tasks.md) | 設定排程 | [CLI](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)、[Desktop](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) 或 [雲端](https://code.claude.com/docs/zh-TW/routines.md) | 選擇頻率 | 定期自動化 (如每日審查) |

## 行動推播通知

當遠端控制啟用時，Claude 可以將推播通知傳送到您的手機。

Claude 決定何時推播。它通常在長時間執行的工作完成時或需要您的決定才能繼續時傳送一則通知。您也可以在提示中要求推播，例如 `notify me when the tests finish`。除了下面的兩個開啟/關閉切換外，沒有每個事件的設定。

若要設定行動推播通知：

**1. 安裝 Claude 行動應用程式**

下載 Claude 應用程式，適用於 [iOS](https://apps.apple.com/us/app/claude-by-anthropic/id6473753684) 或 [Android](https://play.google.com/store/apps/details?id=com.anthropic.claude)。

**2. 使用您的 Claude Code 帳戶登入**

使用您在終端機中用於 Claude Code 的相同帳戶和組織。

**3. 允許通知**

接受來自作業系統的通知權限提示。

**4. 在 Claude Code 中啟用推播**

在您的終端機中，執行 `/config` 並啟用 **Push when Claude decides**（當 Claude 決定時推播）以取得主動通知、**Push when actions required**（當需要採取行動時推播）以取得權限提示和問題，或兩者都啟用。

如果通知未送達：

* 如果 `/config` 顯示 **No mobile registered**（未註冊行動裝置），請在您的手機上開啟 Claude 應用程式，以便它可以重新整理其推播權杖。下次遠端控制連線時，警告會清除。
* 在 iOS 上，焦點模式和通知摘要可能會抑制或延遲推播。檢查設定 → 通知 → Claude。
* 在 Android 上，積極的電池最佳化可能會延遲傳遞。在系統設定中將 Claude 應用程式從電池最佳化中豁免。

當您在連線的終端機中輸入或專注時，Claude Code 會略過行動推播通知。若要將此擴展到您在機器上的任何時間，即使在另一個視窗中，請將 [`CLAUDE_CLIENT_PRESENCE_FILE`](https://code.claude.com/docs/zh-TW/env-vars) 設定為標記檔案路徑：當檔案存在時，通知會被略過。設定螢幕鎖定接聽程式或類似工具，以在螢幕解鎖時建立檔案，並在螢幕鎖定時刪除檔案。

## 限制

* **每個互動式程序僅限一個遠端工作階段**：在伺服器模式以外，每個 Claude Code 執行個體一次僅支援一個遠端工作階段。使用[伺服器模式](#start-a-remote-control-session)即可從單一程序執行多個並行工作階段。
* **本機程序必須保持執行**：Remote Control 以本機程序的形式執行。如果您關閉終端機、結束在您機器上執行該工作階段的 Desktop 應用程式或 VS Code，或以其他方式停止 `claude` 程序，工作階段就會離線，直到您[將其恢復](#resume-sessions-after-stopping-the-server)為止。如果您從遠端機器上的終端機執行 `claude`，請在 `tmux` 或 `screen` 中啟動，以便在中斷 SSH 連線後讓工作階段繼續執行。
* **伺服器模式中當機的工作階段**：如果由 `claude remote-control` 提供服務的工作階段當機，請從已連線的裝置向其傳送一則訊息。Claude Code 會再次為其提供服務。您不必重新啟動伺服器。需要 Claude Code v2.1.238 或更新版本。
* **已連線工作階段上的 HTTP 403 拒絕**：互動式工作階段連線後，當您的機器與 Anthropic 伺服器之間的某個環節以 HTTP 403 回應時（這可能發生在 VPN 或網路變更之後），Claude Code 會持續重試最多三分鐘。如果拒絕持續更久，Claude Code 會中斷連線，而原因會指出是什麼拒絕了連線：網路邊緣，或您自己網路上的代理伺服器、VPN 或防火牆。
* **長時間網路中斷**：如果您的機器處於喚醒狀態但無法連上網路，接下來的做法取決於模式：
  * **伺服器模式**：Claude Code 會在大約 10 分鐘後放棄，且 `claude remote-control` 程序會結束。再次執行 `claude remote-control` 以啟動新的工作階段。
  * **互動式工作階段**：繼續在本機工作。Claude Code 會在中斷期間持續重試，並在網路恢復時自動重新連線。
* **無法下載的附件**：如果您從手機或瀏覽器附加的檔案無法下載到您的機器，Claude 仍會收到您的訊息以及已下載的檔案。Claude Code 會在訊息中加入一則附註（例如 `[1 of 3 attachments did not arrive]`）來取代遺失的檔案。
* **狀態心跳失敗**：如果互動式工作階段因 `could not reach the Remote Control server for about 30 minutes` 而中斷連線，請執行 `/remote-control` 重新連線。
* **轉發的對話框會過期**：Claude Code 會讓權限提示和 `AskUserQuestion` 問題保持開啟，直到您回答為止。當 Claude Code 將其他類型的對話框轉發到遠端工作階段時（例如在安全性拒絕後顯示的模型選擇提示），預設會等待五分鐘，然後關閉對話框並以該對話框的無動作預設值繼續。設定 [`dialogExpiry`](https://code.claude.com/docs/zh-TW/settings-reference#dialogexpiry) 以調整或停用此期限。需要 Claude Code v2.1.224 或更新版本。
* **Fable 用量點數同意提示不會被轉發**：Claude Code 只會在工作階段執行的位置顯示工作階段中途的 [Fable 用量點數同意提示](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)，而不會顯示在您的裝置上。當工作階段在終端機中執行，且在 Claude Code 關閉提示之前沒有人在那裡回答時，該回合會在未傳送請求的情況下結束；請參閱[需要確認的提示未獲回應](https://code.claude.com/docs/zh-TW/errors.md#the-prompt-to-confirm-went-unanswered)。
* **部分命令僅限本機使用**：僅在終端機介面中執行的命令（例如 `/plugin` 或 `/resume`）只能從本機 CLI 使用，無論您是否傳入引數。從行動裝置或網頁輸入 `/claude-api` 時也無法使用。Claude 仍可在那裡[自行載入該 skill](https://code.claude.com/docs/zh-TW/skills.md#work-on-claude-api-projects)。以下命令可從行動裝置和網頁使用：
  * 文字輸出命令：`/compact`、`/clear`、`/context`、`/usage`、`/exit`、`/usage-credits`、`/recap` 和 `/reload-plugins`。`/usage-credits` 會輸出計費 URL，而不是開啟瀏覽器。`/reload-plugins` 僅在工作階段於互動式終端機中執行時才能運作；沒有互動式終端機的工作階段會拒絕此命令。
  * `/model`、`/effort`、`/fast`、`/color` 和 `/rename`：以引數傳入值，例如 `/model sonnet` 或 `/effort high`。從行動裝置和網頁使用時，`/model` 和 `/effort` 會以引數取代終端機中的選擇器或滑桿。
  * `/mcp`：從行動應用程式使用時，會傳回伺服器狀態的文字摘要，而不是開啟選擇器。在網頁上，單獨使用 `/mcp` 會開啟 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)目錄，而不是傳回摘要。當工作階段於互動式終端機中執行時，`reconnect`、`enable` 和 `disable` [子命令](https://code.claude.com/docs/zh-TW/commands.md#all-commands)在兩者上皆可使用。不指定伺服器名稱的 `/mcp reconnect` 會重試所有失敗或需要身分驗證的伺服器。若要在不使用選擇器的情況下授權 claude.ai 連接器，請參閱[從您的 shell 再次授權連接器](#authorize-a-connector-again-from-your-shell)。
  * `/config`：從行動應用程式使用時，傳入 `key=value` 以設定某個設定項目，或不帶引數執行以列出您可以設定的設定鍵。在網頁上，`/config` 會改為開啟 **Settings > Code** 或 **Settings > Claude Code**。
  * 在 Team 和 Enterprise 方案中，從行動裝置或網頁執行 `/usage-credits` 不會向您的管理員傳送[用量點數請求](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)。傳送需要一個僅在互動式 CLI 中出現的確認，因此該命令會告知您改在那裡執行。
  * `/autocompact`，自 v2.1.221 起：以引數傳入視窗大小，例如 `/autocompact 500k`。不帶引數時，它會以文字輸出目前的視窗大小，而不是開啟該命令在終端機工作階段中顯示的對話框。
  * `/advisor`，自 v2.1.260 起：以引數傳入模型，例如 `/advisor opus`，或傳入 `off` 以關閉 advisor。兩種形式都僅適用於目前的工作階段，不會變更您儲存的預設值。不帶引數時，它會以文字輸出目前的 advisor，而不是開啟選擇器。
  * `/output-style`，自 v2.1.269 起：以引數傳入風格名稱，例如 `/output-style concise`，或不帶引數執行以列出各種風格。從行動裝置和網頁使用時，您只能列出和選擇[內建風格](https://code.claude.com/docs/zh-TW/output-styles.md#built-in-output-styles)。若要使用[自訂風格](https://code.claude.com/docs/zh-TW/output-styles.md#create-a-custom-output-style)，請在工作階段本身中選擇。
  * `/focus`，自 v2.1.281 起：以引數傳入 `on` 或 `off`，例如 `/focus on`，或不帶引數執行以切換[專注檢視](https://code.claude.com/docs/zh-TW/commands.md#all-commands)。兩種形式都僅適用於目前的工作階段，不會變更您儲存的選擇。

## 從您的 shell 重新授權連接器

當您透過 Remote Control 操作的工作階段中，某個 claude.ai 連接器需要身分驗證時，無法從行動應用程式或網頁使用 `/mcp` 面板。請在執行該工作階段的機器上，從終端機取得授權連結，然後在您正在使用的裝置上開啟該連結。您無法從行動應用程式或網頁執行此命令。從那裡傳送、以 `!` 開頭的內容會作為訊息傳給 Claude，而不會在 [shell 模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#shell-mode-with-prefix)中執行。

**1. 取得授權連結**

在執行該工作階段的機器上的終端機中（例如透過 SSH），執行 `claude mcp login`，並以引號括住連接器的名稱。連接器的名稱以 `claude.ai` 開頭，例如 Slack 連接器的名稱為 `claude.ai Slack`。以下命令會取得 Slack 連接器的連結：

```bash theme={null}
claude mcp login "claude.ai Slack" --no-browser
```

此命令會印出一個 claude.ai 連結並結束。請在瀏覽器中開啟該連結，並在 claude.ai 上完成授權。`--no-browser` 可防止此命令在該機器上開啟瀏覽器，因為該機器可能並非您正在使用的裝置。

**2. 在工作階段中使用連接器**

啟動新的工作階段，或在已執行中的工作階段內重新連線該連接器：

* **新的工作階段**：授權後啟動的工作階段會直接連線到該連接器，無需任何額外步驟。
* **執行中的工作階段**：在 Claude Code 提示字元中，或從行動應用程式或網頁，執行 `/mcp reconnect`，並使用相同的名稱，不加引號。若要確認您的工作階段是否接受從那裡傳送的此命令，請參閱[哪些命令可從行動裝置和網頁使用](#limitations)中的 `/mcp` 項目。

以下命令會重新連線 Slack 連接器：

```text theme={null}
/mcp reconnect claude.ai Slack
```

在終端機中，Claude Code 會印出 `Successfully reconnected to claude.ai Slack`。從行動應用程式或網頁執行時，回覆為 `Reconnected "claude.ai Slack".`

## 疑難排解

### "Remote Control disconnected" 或 "Can't reach"

在 [claude.ai/code](https://claude.ai/code) 或 Desktop 應用程式中，**Remote Control disconnected** 或 **Can't reach** 訊息表示您的瀏覽器或應用程式與您電腦上的 Claude Code 失去聯繫。這兩則訊息都無法告訴您，Claude 或您正在查看的 subagent 是否仍在您的電腦上運作。請在該電腦上檢查 Claude Code 所處的狀態，並依照對應的步驟重新連線：

* **互動式工作階段顯示 `Remote Control disconnected`**：依照[該行所指出原因的重新連線步驟](#session-ended-elsewhere)操作
* **Claude Code 正在執行且未顯示任何失敗**：互動式工作階段會在機器喚醒並連上網路後自行重新連線，因此您不需要採取任何動作。如果您使用的是 `claude remote-control`，請參閱[限制](#limitations)下的 **長時間網路中斷**
* **Claude Code 未在執行**：[重新啟動它並恢復工作階段](#resume-sessions-after-stopping-the-server)

### "Remote Control requires a claude.ai subscription"

您未使用 claude.ai 帳戶登入，或另一個憑證優先於您的登入。此訊息採用以下其中一種形式：

* 已登出，來自 `/remote-control` 或 `--remote-control`：`Remote Control requires a claude.ai subscription.` 或 `/remote-control requires a claude.ai subscription.`
* 已登出，來自 `claude remote-control`：`You must be logged in to use Remote Control. Remote Control is only available with claude.ai subscriptions.`
* 已登入，但正在使用 API 金鑰或權杖：`Remote Control requires claude.ai subscription auth.` 後面跟著正在使用的憑證，例如 `ANTHROPIC_API_KEY is set, so this session is using API-key auth`。`apiKeyHelper` 設定和 `ANTHROPIC_AUTH_TOKEN` 的命名方式相同。

執行 `claude auth login` 並選擇 claude.ai 選項。如果訊息提及 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`，請在設定的位置移除它：您的 shell 環境或[設定檔](https://code.claude.com/docs/zh-TW/settings-reference.md#env)的 `env` 區塊。如果提及 `apiKeyHelper`，請移除該設定。

### "Remote Control requires a full-scope login token"

您使用來自 `claude setup-token` 或 `CLAUDE_CODE_OAUTH_TOKEN` 環境變數的長期權杖進行驗證。這些權杖只能進行模型請求，因此無法建立 Remote Control 工作階段。執行 `claude auth login` 以改用完整範圍的工作階段權杖進行驗證。

### "Unable to determine your organization for Remote Control eligibility"

您的快取帳戶資訊已過期或不完整。執行 `claude auth login` 以重新整理它。

### "Remote Control isn't enabled for this account"

Claude Code 檢查了您登入帳戶的 Remote Control 可用性，檢查結果為關閉。通常的原因是快取的權利在計畫變更後已過期。執行 `claude auth logout` 然後 `claude auth login` 以重新整理它們，並在您使用舊版本時更新 Claude Code。

執行 `claude doctor` 以查看哪個個別資格檢查失敗。環境變數衝突、無法到達的檢查和您組織的 Remote Control 設定各自產生自己的訊息，因此此錯誤表示帳戶層級的檢查本身。

在 v2.1.239 之前，此訊息讀作「Remote Control is not yet enabled for your account」。

### "Couldn't verify Remote Control eligibility"

Claude Code 無法到達功能旗標服務以檢查您的帳戶是否啟用了 Remote Control，通常是因為您離線或代理伺服器阻止了請求。一旦您有網路存取權，請重試，或執行 `claude doctor` 以取得詳細資訊。相關訊息「Couldn't verify your organization's Remote Control policy」表示 Claude Code 在讀取該原則時遇到錯誤，並具有相同的修正方式。

### "Remote Control requires feature-flag evaluation"

設定了[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)以關閉功能旗標評估，完整訊息會命名 Claude Code 找到的變數。在 2.1.154 之前的版本上，相同的設定會改為產生「Remote Control is not yet enabled for your account」。要執行的操作取決於訊息命名的變數：

* **`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 或 `DISABLE_GROWTHBOOK`**：在設定的位置取消設定變數，在您的 shell 環境或 [`settings.json` 檔案](https://code.claude.com/docs/zh-TW/settings-reference#all-settings)的 `env` 區塊中。
* **`DISABLE_TELEMETRY` 或 `DO_NOT_TRACK`**：在 Pro、Max、Ultra、Team 或 Enterprise 計畫上且 `DISABLE_GROWTHBOOK` 未設定的情況下，這些變數會保持 Remote Control 可用，除非您的組織需要[信任裝置](#trusted-devices)。如果需要，在設定的位置取消設定變數以使用 Remote Control。在 v2.1.154 到 v2.1.282 上，設定任一變數時都會看到此訊息，因此請將 Claude Code 更新至符合[這些變數需求](#requirements)的版本。

### "Remote Control is only available when using Claude via api.anthropic.com"

工作階段未直接與 Anthropic API 通訊，Remote Control 需要此功能。這發生在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上。當 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 `api.anthropic.com` 以外的主機時，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或代理伺服器，即使您使用 claude.ai 登入，也會發生這種情況。請參閱[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#remote-control-requires-the-anthropic-api)以取得完整的原因清單。

訊息會命名將工作階段路由離開 Anthropic API 的內容，例如 `CLAUDE_CODE_USE_BEDROCK` 或自訂 `ANTHROPIC_BASE_URL`。如果您有符合資格的 claude.ai 登入，請取消設定命名的變數，如果您在[設定](https://code.claude.com/docs/zh-TW/settings.md)中設定了它，請從 `env` 金鑰中移除它，然後重新啟動工作階段。

### "Remote Control is disabled by your organization's policy"

原則阻止了 Remote Control。按順序檢查這些原因：

* **錯誤提及 `disableRemoteControl`**：您的 IT 管理員已透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)在此裝置上停用 Remote Control，獨立於組織範圍的切換和您的登入方式。
* **您的 claude.ai 計畫是 Pro、Max 或 Ultra**：Claude Code 仍在來自較早登入的 Team 或 Enterprise 組織下登入，因此它會檢查該組織的 Remote Control 原則。執行 `/status` 以查看您的登入使用哪個計畫和組織。執行 `claude auth logout` 然後 `claude auth login` 以在您目前的計畫下重新登入。
* **訊息未說要聯絡您的組織管理員**：您的組織已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)，這會關閉 Remote Control。若要確認，請執行 `/status` 並在 `Organization configuration` 列中尋找 `HIPAA`。擁有者會在[管理設定](https://claude.ai/admin-settings/claude-code)中看到 **Remote Control** 切換呈灰色，且無法將其開啟。如果您對此設定有疑問，請詢問擁有者，擁有者可以聯絡您組織的 Anthropic 客戶團隊。在 v2.1.267 之前，此情況顯示「Remote Control isn't available for your organization due to its compliance policy」。
* **Remote Control 對組織中的其他人有效，但對您無效**：如果您的 Enterprise 組織透過[自訂角色](https://support.claude.com/en/articles/13930452)管理您的存取權，您的角色可能是原因。Remote Control 同時需要雲端工作階段權限和 **Claude Code remote control** 權限。請擁有者檢查您的角色是否包含這兩項權限，並在 [**Organization settings > Roles**](https://claude.ai/admin-settings/roles) 新增缺少的權限。
* **否則，擁有者尚未為您的組織啟用它**：Remote Control 在 Team 和 Enterprise 計畫上預設為關閉。擁有者可以在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 啟用它，方法是開啟 **Remote Control** 切換。此切換是伺服器端組織設定。

在 v2.1.281 之前，當 Claude Code 未在此機器上載入您的組織原則時，此訊息也會出現，例如在離線啟動後。更新版本會改為將該狀態報告為 [`Couldn't verify your organization's policy for remote control`](#couldnt-verify-your-organizations-policy-for-remote-control)。

### "Remote Control was turned off by your organization's policy"

您的組織原則在工作階段連線期間不再允許 Remote Control，因此 Claude Code 中斷了該工作階段的連線。工作階段後續的情況取決於您啟動 Remote Control 的方式：

* **使用 `/remote-control`、`claude --remote-control` 或[自動連線](#enable-remote-control-for-all-sessions)**：工作階段會在沒有 Remote Control 的情況下繼續執行，且 Claude Code 會在 claude.ai 將其封存
* **使用 `claude remote-control`**：伺服器會停止並封存其所服務的工作階段，然後結束

若要再次找到這些工作階段，請在 claude.ai/code 開啟您的[已封存工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#find-an-archived-session)。

Remote Control 不會自行重新連線。若要在您的組織再次允許後重新開啟它，請在工作階段中執行 `/remote-control`，或在 shell 中執行 `claude remote-control`。在此機器上的 Claude Code 擷取到變更後的原則之前，任一命令都會以 [`Remote Control is disabled by your organization's policy`](#remote-control-is-disabled-by-your-organizations-policy) 失敗。開啟中的工作階段大約每小時擷取一次原則。若要找出阻止 Remote Control 的原因，請將命令輸出的完整文字與該項目進行比對。

### "Couldn't verify your organization's policy for remote control"

Claude Code 無法擷取您的組織原則，且此機器上沒有已儲存的副本可改用，因此它會保持 Remote Control 關閉，直到它可以確認您的組織允許它。這通常發生在您離線啟動 Claude Code 或在 VPN 連線之前，或當代理伺服器干擾請求時。在緩慢的連線上，當第一個請求仍在進行中時，它也可能出現。

訊息採用以下其中一種形式：

* 來自 `/remote-control`、`claude remote-control` 或 `claude --remote-control`：`Couldn't verify your organization's policy for remote control. Check your network connection and try again.`
* 來自[自動連線](#enable-remote-control-for-all-sessions)當工作階段啟動時：`couldn't verify your organization's policy — check your network connection and try again`，在通知中以 `Remote Control failed` 為前綴，在對話中以 `Remote Control disconnected` 為前綴。工作階段隨後會保持 Remote Control 關閉。

恢復您的網路連線，然後執行 `/remote-control` 或再次執行命令。每次嘗試都會再次檢查原則，因此您不需要重新啟動 Claude Code。如果訊息持續出現，請執行 `claude doctor` 並閱讀其 `Organization policy` 列，該列說明原則未載入的原因。

在 v2.1.281 之前，此狀態顯示 `Remote Control is disabled by your organization's policy`。

### "Remote credentials fetch failed"

Claude Code 無法從 Anthropic API 取得短期憑證以建立連線。使用 `--verbose` 重新執行以查看完整錯誤：

```bash theme={null}
claude remote-control --verbose
```

常見原因：

* 未登入：執行 `claude` 並使用 `/login` 以您的 claude.ai 帳戶進行驗證。Remote Control 不支援 API 金鑰驗證。
* 網路或代理伺服器問題：防火牆或代理伺服器可能阻止了出站 HTTPS 請求。Remote Control 需要存取埠 443 上的 Anthropic API。
* 工作階段建立失敗：如果您也看到 `Session creation failed — see debug log`，失敗發生在設定的較早階段。檢查您的訂閱是否有效。

### "Couldn't reconnect to your Remote Control session"

當您使用 `claude --resume` 或 `claude --continue` 繼續對話時，Claude Code 會重新連線到該對話中記錄的 Remote Control 工作階段。此訊息表示重新連線因可能是暫時的原因（例如網路中斷或伺服器錯誤）而失敗，因此 Claude Code 無法確認遠端工作階段是否仍然存在。

執行 `/remote-control` 以重試連線，或使用 `claude --remote-control` 啟動新工作階段以建立新的 Remote Control 工作階段。您的本機工作階段在此期間繼續執行而不使用 Remote Control。

### "Previous session is unavailable — run /remote-control to start a new one"

Claude Code 無法恢復先前的 Remote Control 工作階段，並停止而不是自行啟動新工作階段。您可以在使用 `claude --resume` 或 `claude --continue` 繼續對話後看到此訊息，或在 Claude Code [在斷線後自行重新連線](https://code.claude.com/docs/zh-TW/errors.md#remote-control-couldnt-refresh-your-login)後看到此訊息。

執行 `/remote-control` 以在目前登入下啟動新的 Remote Control 工作階段；您的本機工作階段在此期間繼續執行而不使用 Remote Control。相關訊息 `Remote Control could not verify the signed-in account — run /remote-control to reconnect` 具有相同的修正方式。如果您在 `Previous session is unavailable` 後執行 `/remote-control` 而不先重新啟動 Claude Code，Claude Code 會將對話的較早訊息排除在新工作階段之外。

### "Remote Control got an unexpected server response"

Remote Control 伺服器接受了請求，但以此版本的 Claude Code 無法讀取的形式回覆，同時建立遠端工作階段或擷取其憑證。在相同版本上重試會以相同方式失敗。執行 `claude update`，然後執行 `/remote-control` 以重新連線。

### "Your organization requires Trusted Devices for Remote Control, but this device is not enrolled"

您的組織已啟用[信任裝置](#trusted-devices)，此機器尚未註冊。在 Claude Code 中執行 `/login`。註冊作為登入的一部分進行，沒有單獨的註冊命令。

### "session expired for trusted-device check"

您的登入已超過 18 小時。在 Claude Code 中執行 `/login`，或當 claude.ai 或行動應用程式提示您時，使用 Face ID、Touch ID、Windows Hello 或通行金鑰確認。請參閱[信任裝置](#trusted-devices)。

## 相關資源

* [在雲端使用 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)：在雲端執行會話而不是在您的機器上，透過[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)設定
* [跨會話訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)：讓 Claude 在其他機器或您的[雲端會話](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)上傳送訊息給您的會話
* [Channels](https://code.claude.com/docs/zh-TW/channels.md)：將 Telegram、Discord 或 iMessage 轉發到會話中，以便 Claude 在您離開時對訊息做出反應
* [Dispatch](https://code.claude.com/docs/zh-TW/desktop.md#sessions-from-dispatch)：從您的手機傳送任務訊息，它可以生成 Desktop 會話來處理它
* [驗證](https://code.claude.com/docs/zh-TW/authentication.md)：設定 `/login` 並管理 claude.ai 的認證
* [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)：包括 `claude remote-control` 的旗標和命令的完整清單
* [安全性](https://code.claude.com/docs/zh-TW/security.md)：Remote Control 會話如何適應 Claude Code 安全模型
* [資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)：在本地、Remote Control 和雲端會話期間透過 Anthropic API 流動的資料
