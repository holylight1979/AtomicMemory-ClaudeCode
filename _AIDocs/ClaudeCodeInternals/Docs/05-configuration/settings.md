<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/settings | lastmod: 2026-11-03 | section: Configuration / Settings -->
> 來源：https://code.claude.com/docs/zh-TW/settings（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Settings｜EN 摘要：Change Claude Code settings, pick the scope a key belongs in, verify the change, and learn which value Claude Code uses when a key is set in several places.

# 設定檔案和優先順序

> 變更 Claude Code 設定、選擇金鑰所屬的範圍、驗證變更，並了解當金鑰在多個位置設定時 Claude Code 使用哪個值。

設定是變更 Claude Code 行為方式的 JSON 金鑰：它啟動時使用的模型、它可以在不詢問的情況下執行的內容、它無法讀取的檔案、它在您的終端機中的外觀，以及您的組織強制執行的內容。

> [!TIP]
>
> 若要查詢特定金鑰，請前往[所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md)，其中列出每個金鑰及其設定位置、預設值和範例。

Claude Code 從 JSON 設定檔案（例如 `~/.claude/settings.json`）讀取設定。它在幾個位置尋找它們，而[它讀取設定的檔案決定了設定適用於誰](#settings-files-and-who-they-affect)。本頁涵蓋這些檔案：將設定放在哪個檔案中、如何變更設定並確認其已應用，以及當相同金鑰在多個檔案中設定時 Claude Code 使用哪個值。[設定權限](https://code.claude.com/docs/zh-TW/permissions.md)涵蓋 Claude Code 可以在不詢問的情況下執行的內容以及如何編寫 `allow`、`ask` 和 `deny` 規則。

> [!NOTE]
>
> 本頁涵蓋在您的機器上執行的 Claude Code：終端機、[VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 和 [JetBrains](https://code.claude.com/docs/zh-TW/jetbrains.md) 擴充功能，以及[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)，它們都讀取相同的設定檔案。[Claude Code on the web](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 上的雲端工作階段在不同的機器上執行並僅讀取其中一些；請參閱[雲端工作階段中的設定](#settings-in-cloud-sessions)。

## 設定檔案及其影響範圍

Claude Code 從四個檔案讀取設定，組織也可以從 claude.ai 主控台傳遞受管設定。每個來源都有一個範圍：設定儲存在其中的人員和專案集合，無論是只有您、專案中的每個人，還是組織中的每個人。

| 範圍 | 檔案 | 影響對象 | 用途 |
| :- | :- | :- | :- |
| 使用者 | `~/.claude/settings.json` | 您，在此機器上的每個專案中 | 個人偏好設定：佈景主題、編輯器模式、預設模型、您自己的權限規則 |
| 共享專案 | `.claude/settings.json` | 每個在包含它的資料夾中工作的人。在 git 儲存庫中，提交它以便隊友取得 | 團隊權限、hook、外掛和專案需要的環境變數 |
| 專案本機 | `.claude/settings.local.json` | 您，僅在此一個專案中。Claude Code 在建立檔案時將其保留在 git 之外；如果您手動建立，請自行將其新增至 `.gitignore` | 一個專案的個人覆寫，以及在共享前進行測試 |
| 受管 | `managed-settings.json` 和其他[受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) | 您的組織部署到的每個人；[設定優先順序](#settings-precedence)說明哪些內容可以覆寫它 | 安全政策和合規要求 |

在「檔案」欄中，`~/.claude` 是您家目錄中的 `.claude` 資料夾，而單獨的 `.claude` 是您專案內的 `.claude` 資料夾。

### 比較每個設定檔案的範圍

假設您在機器上有三個專案 `website/`、`api/` 和 `acme-app/`，隊友有自己的 `acme-app/` 複製，而您在 `acme-app/` 上啟動[雲端工作階段](#settings-in-cloud-sessions)。

下圖顯示當您從這些資料夾啟動 Claude Code 時，設定適用於哪些資料夾。按一下設定檔案以查看它到達的資料夾。

Settings file

Your machine

A teammate’s machine

A cloud session

* **`~/.claude/settings.json`**：您機器上的每個專案，而不會到達隊友的機器或雲端工作階段
* **`acme-app/.claude/settings.json`**：您的 `acme-app/`。只有在您將檔案提交到版本控制時，它才會到達隊友的複製和雲端工作階段；在您這樣做之前，它就像任何其他檔案一樣在您的磁碟上，沒有人有它
* **`acme-app/.claude/settings.local.json`**：僅您的 `acme-app/`。Claude Code 在第一次寫入檔案時將其新增至您的全域 git 排除項目，因此它保留在您的提交之外；如果您手動建立檔案，[自行將其新增至 `.gitignore`](#keep-personal-settings-out-of-a-repository)
* **受管設定**，無論是 `managed-settings.json` 檔案、MDM 政策，還是來自 claude.ai 主控台的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)：您的組織部署到的每台機器上的每個專案，或您使用組織帳戶登入的地方。只有伺服器受管設定才能到達雲端工作階段

### 尋找或建立您的設定檔案

安裝 Claude Code 不會建立任何設定檔案。如果您的機器或專案已經有一個，它來自以下來源之一：

* **受管**：您的組織部署它。您不建立或編輯它。
* **共享專案**：已經使用 Claude Code 的專案可能已提交一個。如果沒有，請在專案資料夾中的 `.claude/settings.json` 建立一個。
* **使用者**和**專案本機**：自行建立它們，或讓 Claude Code 建立它們。它在您第一次在 `/config` 選單中變更儲存在使用者設定中的選項時寫入 `~/.claude/settings.json`，例如佈景主題，以及在您第一次在權限提示上給予常設核准時寫入 `.claude/settings.local.json`，例如針對 Bash 命令選擇「是的，不要再問」。少數 `/config` 選項，包括**顯示提示**，改為儲存至 `.claude/settings.local.json` 而不是使用者檔案。

> [!NOTE]
>
> 在 Windows 上，`~/.claude` 表示 `%USERPROFILE%\.claude`。若要將家目錄檔案保留在其他地方，請設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)；Claude Code 會改為在那裡儲存您的設定、工作階段歷史記錄和外掛。

Claude Code 也保留第五個檔案 [`~/.claude.json`](https://code.claude.com/docs/zh-TW/claude-directory#ce-claude-json)，它為自己寫入；您不需要編輯它。它保留您的帳戶詳細資料、[MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)設定、每個專案的狀態（例如信任決定），以及 `/config` 為您寫入的[全域設定鍵](https://code.claude.com/docs/zh-TW/settings-reference.md#global-config-settings)。

### 與您的團隊共享設定

提交 `.claude/settings.json` 以便複製儲存庫的每個人都取得相同的權限、hook 和外掛。每個隊友仍然可以在自己的 `.claude/settings.local.json` 中為自己覆寫它，因此個人例外不需要提交。如需完整的團隊檔案，請參閱[團隊的共享設定](https://code.claude.com/docs/zh-TW/settings-example.md#a-teams-shared-settings)。

您提交的某些內容會等到每個隊友[信任資料夾](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，而少數設定鍵永遠不會從儲存庫檔案生效；[對不適用的設定進行疑難排解](#common-cases)涵蓋兩者。

### 將個人設定保留在儲存庫之外

若要在一個專案中為自己變更設定而不為隊友變更，請將其儲存在專案內的 `.claude/settings.local.json` 中。Claude Code 在提交的 `.claude/settings.json` 上套用該檔案，因此如果您的團隊檔案設定 `"model": "claude-sonnet-5"` 而您想要 Opus，請在本機檔案中放入 `"model": "claude-opus-5-5"`，只有您的工作階段會變更。

Claude Code 也寫入此檔案，將其保留在您的提交之外，並在不需要信任步驟的情況下套用其允許規則：

* **Claude Code 也寫入它。** 當 Claude 要求執行 Bash 命令的權限，而您選擇「是的，不要再問」時，Claude Code 會將該[權限核准](https://code.claude.com/docs/zh-TW/permissions.md#permission-system)儲存在此處作為 `allow` 規則。
* **您不需要自行 gitignore 它，除非您手動建立它。** Claude Code 在尚未忽略它的 git 儲存庫中第一次寫入檔案時，它會將 `**/.claude/settings.local.json` 新增至您的全域 git 排除項目檔案，因此檔案在每個儲存庫中保留在您的提交之外。當您的全域 git 設定將 `core.excludesFile` 設為絕對路徑或 `~` 前綴路徑時，該檔案就是 `core.excludesFile`；否則它是 `$XDG_CONFIG_HOME/git/ignore`，或當 `XDG_CONFIG_HOME` 未設定時為 `~/.config/git/ignore`。如果您手動建立檔案，而 Claude Code 尚未寫入它，請自行將其新增至 `.gitignore`。
* **其 allow 規則在檔案保持未追蹤時不等待信任。** 因為檔案是您的而不是儲存庫的，Claude Code 套用其 `allow` 規則而不需要它對提交檔案要求的[工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)步驟。如果檔案由 git 追蹤，信任步驟也適用於它；請參閱[當您的本機設定檔案需要信任時](https://code.claude.com/docs/zh-TW/permissions.md#when-your-local-settings-file-needs-trust)。

#### Claude Code 在 git 儲存庫中保留本機檔案的位置

當 Claude 要求執行 Bash 命令的權限，而您選擇「是的，不要再問」時，Claude Code 會將該核准儲存為 `.claude/settings.local.json` 中的 `allow` 規則。如果您在 git 儲存庫的子目錄中啟動 Claude Code，它會在儲存庫根目錄讀取和寫入該檔案，並在整個儲存庫中套用核准。在 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中，它使用主簽出根目錄的檔案。

兩個規則限定根位置：

* **當檔案改為與 `.claude/settings.json` 保持在一起時**：在 git 儲存庫之外，當儲存庫根目錄是您的家目錄時，在 Windows 上，或當儲存庫根目錄或其 `.git` 或 `.claude` 項目不由您的使用者擁有時。
* **檔案中的路徑不在儲存庫根目錄錨定**：以 `/` 開頭的權限規則或相對沙箱路徑[改為在工作階段的主要工作目錄錨定](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。

在 v2.1.211 之前，Claude Code 在啟動目錄中保留檔案。它仍然會讀取較早版本留在該處的檔案，與根檔案一併讀取；當兩者設定相同的設定鍵時，以根的值為準，而兩個檔案的權限規則都適用。Agent SDK 的 [`resolveSettings()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#resolvesettings) 協助程式始終從啟動目錄讀取檔案。

Claude Code 從工作階段的[主要工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)讀取共享 `.claude/settings.json`，因此若要使用在儲存庫根目錄提交的檔案，請從那裡啟動 Claude Code。在您[使用 `/cd` 移動工作階段](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory)後，Claude Code 改為從新目錄讀取兩個專案檔案，按相同規則放置本機檔案。從您移動到的目錄讀取它們需要 Claude Code v2.1.246 或更新版本。若是從桌面應用程式啟動的 worktree 工作階段，請參閱[worktree 與主簽出共享的內容](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)。

### 檢查您的組織強制執行的內容

如果您的組織管理 Claude Code，某些設定是為您決定的，您在自己的檔案中放入的任何內容都不會變更它們。若要查看哪些，請執行 `/status`：`Setting sources` 行會列出適用於您的受管來源。受管設定在此機器上 Claude Code 執行的任何地方適用；[開發人員可以變更的內容](https://code.claude.com/docs/zh-TW/managed-settings.md#what-a-developer-can-change)涵蓋本機管理員權限和 Claude Code 以外的工具。

受管設定透過受管設定頁面上的[傳遞機制](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)到達您，最常見的是：

* [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)，Claude Code 從 claude.ai 管理主控台或自行託管的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)擷取
* MDM 或作業系統層級政策，以及系統目錄中的 `managed-settings.json` 檔案
* 嵌入主機（例如 Claude Desktop），透過 SDK `managedSettings` 選項；請參閱[從嵌入主機控制政策](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)

在 Claude Desktop 應用程式中於您的機器上執行的 [Cowork](https://claude.com/docs/cowork/overview) 工作階段中，Claude Code 不會從 claude.ai 管理主控台擷取伺服器受管設定，且它會讀取部署到您裝置的政策，除非您組織的 Claude Desktop 設定設定了 `requireCoworkFullVmSandbox`。[政策適用的位置和時間](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)涵蓋 Cowork 和雲端工作階段。

如果您是管理員，[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md) 會逐步說明選擇要強制執行的內容，而[部署受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)涵蓋傳遞以及如何確認政策生效。關於 claude.ai 管理主控台中受管設定編輯器可能顯示的警告，請參閱[設定伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#configure-server-managed-settings)。

## 變更設定

您可以從 `/config` 功能表、編輯設定檔案或一個工作階段的命令列變更設定。

Claude Code 的系統提示未發佈。若要給 Claude 常設指示，請使用 [`CLAUDE.md` 檔案](https://code.claude.com/docs/zh-TW/memory)或 `--append-system-prompt` 旗標。

### 使用 /config 功能表

在 Claude Code 內執行 `/config` 並開啟 **Config** 標籤。它列出一小組個人選項，例如主題、編輯器模式和詳細輸出，而不是每個設定金鑰。選擇一個選項來變更它；Claude Code 為您儲存它：

* **大多數選項**：`~/.claude/settings.json`
* **少數選項，例如顯示提示**：`.claude/settings.local.json`
* **[全域設定選項](https://code.claude.com/docs/zh-TW/settings-reference.md#global-config-settings)**：`~/.claude.json`

若要設定一個選項而不使用功能表，請傳遞 `key=value`，例如 `/config verbose=true`。

> [!NOTE]
>
> `/config` 是終端機介面的一部分。[VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 聊天面板和[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)不開啟它；通過編輯設定檔案或通過這些應用程式自己的設定在那裡變更設定。

### 編輯設定檔案

在您的編輯器中開啟您想要的範圍的設定檔案，並新增或變更金鑰。設定檔案是嚴格的 JSON：`//` 註解或尾部逗號是語法錯誤，Claude Code 在下次啟動時將檔案報告為[設定錯誤](#fix-a-broken-settings-file)。例如，若要讓 Claude Code 執行您的 lint 和測試命令而不詢問並停止讀取 `.env` 檔案，請將此新增到 `~/.claude/settings.json`：

```json ~/.claude/settings.json theme={null}
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(npm run lint)",
      "Bash(npm run test *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)"
    ]
  }
}
```

`permissions` 下的每個項目都是命名工具及其可能執行的操作的規則；[設定權限](https://code.claude.com/docs/zh-TW/permissions.md)解釋語法。`$schema` 行指向 Claude Code 設定的[已發佈 JSON 架構](https://json.schemastore.org/claude-code-settings.json)，它在 VS Code、Cursor 和任何其他支援 JSON 架構的編輯器中為您提供自動完成和內嵌驗證。架構可能滯後於最新的 CLI 版本，因此最近記錄的金鑰上的驗證警告並不意味著您的設定無效。

儲存後，在 Claude Code 內執行 `/status` 以確認檔案已載入；[確認已載入的內容](#check-what-loaded)說明 `Setting sources` 行顯示的內容以及如何報告損壞的檔案。

如需完整的個人檔案、團隊檔案和組織檔案，每個都帶有每個金鑰的註解，請參閱[範例設定檔案](https://code.claude.com/docs/zh-TW/settings-example.md)。

### 為一個工作階段變更設定

若要嘗試值而不儲存它，請在啟動 Claude Code 時設定它。該值適用於該工作階段，您的設定檔案保持原樣。您有三種方式執行此操作：

* **`--settings`**：將金鑰作為 JSON 傳遞，內嵌或作為檔案路徑。Claude Code 在您的使用者、專案和本機檔案上方以及受管設定下方應用它。它可以設定您的使用者設定檔案可以設定的任何金鑰；它無法設定 `Managed` 或 `Global config` 金鑰。
* **該金鑰的旗標**：某些金鑰有自己的旗標，例如 `model` 的 `--model` 和 `effortLevel` 和 `modelSettings` 的 `--effort`。
* **環境變數**：在執行 `claude` 之前匯出金鑰的配對變數，例如 `ANTHROPIC_MODEL` 用於 `model`。

[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)上的每個金鑰項目列出其每個工作階段覆蓋及其優先順序，因此檢查您想變更的金鑰的項目。

您在工作階段內執行的命令大多儲存您的選擇：當您在 `/config` 中變更設定時，Claude Code 將其寫入您的設定檔案，而 `/model` 將值儲存為新工作階段的預設值。

如果您在 `/model` 選擇器中按 `s`，Claude Code 會切換模型而不將其儲存為您的使用者預設值。[調整努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)說明哪些 `/effort` 選擇 Claude Code 儲存為您使用的模型的預設值，哪些僅適用於目前工作階段。

例如，若要在 Opus 上啟動一個工作階段而不變更您的預設值：

```bash theme={null}
claude --settings '{"model": "claude-opus-5-5"}'
```

### 編輯何時生效

Claude Code 監視您的設定檔案並在它們變更時重新載入它們，因此它應用大多數編輯到執行中的工作階段而不需要重新啟動，包括對 `permissions`、`hooks` 和認證協助程式（例如 `apiKeyHelper`）的編輯。Claude Code 也在其資料夾在工作階段啟動時存在時載入您在中途建立的設定檔案。對於專案的 `.claude/` 資料夾，即使您在同一工作階段中建立資料夾，它也會載入檔案。

重新載入涵蓋使用者、專案、本機和受管設定，Claude Code 為它偵測到的每個設定檔案變更執行 [`ConfigChange` hook](https://code.claude.com/docs/zh-TW/hooks#configchange)，而不是來自 MDM 或 claude.ai 主控台的受管設定。來自 MDM 或 claude.ai 主控台的受管設定按排程而不是保存時到達執行中的工作階段；[傳遞表](https://code.claude.com/docs/zh-TW/managed-settings.md#choose-a-delivery-mechanism)按來源給出它。

Claude Code 只在工作階段啟動時讀取某些金鑰一次，因此對其中一個的編輯不會到達執行中的工作階段。也等待重新啟動的管理員端金鑰（例如 `requiredMinimumVersion`）列在[政策適用的位置和時間](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)下。您最可能在中途編輯的是：

* [`model`](https://code.claude.com/docs/zh-TW/settings-reference#model)：使用 [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) 在中途切換。每個模型都有自己的提示快取，因此切換後的第一個請求會重新讀取整個對話未快取；請參閱[切換模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)
* [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 和 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings)：使用 [`/effort`](https://code.claude.com/docs/zh-TW/model-config#adjust-effort-level) 在中途變更努力

如果您在工作階段中途移除 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories)，檔案工具會在執行中的工作階段內保持該封鎖。若要解除封鎖，請從每個設定它的設定檔案中移除該金鑰，然後重新啟動每個執行中的工作階段。

### 確認已載入的內容

在 Claude Code 內執行 `/status` 以查看哪些設定來源是使用中的。**Status** 標籤包含 `Setting sources` 行，列出 Claude Code 為目前工作階段載入的每個設定檔案，例如 `User settings` 或 `Project local settings`。當[受管設定](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-how-settings-reach-devices)生效時，受管設定項目在括號中顯示它們如何到達您的機器。

該行確認 Claude Code 讀取了哪些檔案；它不顯示哪個檔案提供了每個金鑰。若要列出 Claude Code 拒絕的項目，請執行 [`claude doctor`](https://code.claude.com/docs/zh-TW/debug-your-config)；對於專案或受管設定設定的模型，啟動標頭命名設定它的檔案。`/status` 和 `/config` 在不同標籤上開啟相同的對話框，**Config** 標籤不是您 `settings.json` 內容的檢視。

### 修復損壞的設定檔案

如果您輸入錯誤的 JSON 或將金鑰設定為 Claude Code 不接受的值，Claude Code 在互動式工作階段啟動時會告訴您。它顯示的內容取決於檔案受影響的程度：

* **設定錯誤**：使用者、專案或本機檔案有無效的 JSON 或架構拒絕的值。在互動式工作階段啟動時，Claude Code 顯示一個對話框，讓您用 Claude 的幫助修復檔案、退出或繼續而不使用損壞的設定。
* **設定警告**：只有個別項目失敗，例如格式錯誤的權限規則或未知的 hook 事件名稱。Claude Code 跳過這些值並保持檔案的其餘部分生效。
* **受管設定**：Claude Code 繼續強制執行檔案的其餘部分。[受管設定中的無效項目](https://code.claude.com/docs/zh-TW/managed-settings.md#invalid-entries-in-managed-settings)說明它丟棄的內容以及哪些金鑰回退到更嚴格的值，直到您修復它們。對於不是有效 JSON 的受管設定文件，請參閱[受管設定文件無法解析](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-document-could-not-be-parsed)。
* **設定錯誤**：`~/.claude.json` 無法解析。Claude Code 將損壞的檔案複製到 `~/.claude/backups/.claude.json.corrupted.<timestamp>` 並詢問是否退出並手動修復它或重設為預設設定；`-p` 執行列印錯誤並退出。若要恢復您之前的狀態，請複製回 `~/.claude/backups/` 中最近五個 `.claude.json.backup.<timestamp>` 檔案之一，Claude Code 在寫入檔案前儲存。

繼續後，執行 `/status` 以查看受影響的檔案，執行 `claude doctor` 以查看每個錯誤的詳細資訊。

`-p` 執行不顯示對話框。除非[受管設定文件無法解析](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-document-could-not-be-parsed)，Claude Code 跳過損壞的檔案或值並繼續其餘部分，因此在忽略設定的 `-p` 執行後，執行 `claude doctor` 以查看它丟棄的內容。

## 設定優先順序

當同一個鍵出現在多個位置時，Claude Code 會使用設定該鍵的最高層級中的值。下方的堆疊顯示各個層級，最高層級位於最上方；較高層級中的鍵會覆寫其下方任何位置的相同鍵。

Settings precedence, highest first: managed settings, command line, project local, shared project, user. A key set at a higher level overrides the same key set lower down.

依序排列，優先順序最高者在前：

1. **受管設定**：您的組織透過 `managed-settings.json` 檔案、MDM 政策，或來自 claude.ai 主控台的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)所部署的設定。您自己的設定檔或 `--settings` 中的任何內容都無法覆寫受管的鍵，而像 `--model` 這樣的旗標只能從您的組織允許的模型中選擇。受管的 [`model`](https://code.claude.com/docs/zh-TW/settings-reference#model) 是起始預設值，而非鎖定；鎖定由 [`availableModels`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodels) 和 [`deniedModels`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmodels) 負責。當您的組織提供多個受管來源時，[受管層級內的優先順序](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)規則說明了 Claude Code 會從每個來源讀取什麼。
2. **命令列**：您在啟動 `claude` 時透過 `--settings <file-or-json>` 傳入的 JSON，僅適用於該工作階段；請參閱[針對單一工作階段變更設定](#change-a-setting-for-one-session)。您在此處設定的鍵會覆寫專案和使用者設定檔中的相同鍵，而您未設定的鍵則保留這些檔案中的值。其他旗標（例如 `--model`）會為工作階段設定單一項目，且不屬於此堆疊；[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)中各鍵的條目會說明哪些旗標會覆寫該鍵。
3. **專案本機設定**（`.claude/settings.local.json`）：您在此專案中的個人設定。
4. **共用專案設定**（`.claude/settings.json`）：您的團隊簽入版本控制的設定。
5. **使用者設定**（`~/.claude/settings.json`）：您適用於所有專案的個人設定。

環境變數不是此堆疊中的一個層級。當某個行為同時具有 shell 變數和設定鍵時，由哪一個生效是依每一組個別決定的，而非依層級：在您的 shell 中匯出的 `ANTHROPIC_MODEL` 會優先於任何檔案中的 `model` 鍵，而 `ANTHROPIC_DEFAULT_MODEL` 僅在沒有任何檔案設定 `model` 時才會生效。[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md#precedence)說明了哪些鍵有對應的變數，以及 Claude Code 會先讀取哪一個。設定檔中的 `env` 區塊是一般的鍵，遵循上述層級。

對於少數與安全性相關的鍵，Claude Code 會採用來自較低層級的較嚴格值，而非受管值；[受管設定優先順序的例外](#exceptions-to-managed-settings-precedence)列出了這些鍵。

### 清單會合併而非覆寫

當您在多個檔案中設定相同的清單鍵（例如 `permissions.allow`）時，Claude Code 會合併這些清單，而不是只選擇其中一個，因此每個檔案都可以新增項目，而不會移除其他檔案的項目。有四個存放模型清單或個別模型項目的鍵遵循各自的規則：

* [`fallbackModel`](https://code.claude.com/docs/zh-TW/settings-reference#fallbackmodel) 是一個有序的鏈，其中位置具有意義，因此 Claude Code 會從定義該鍵的優先順序最高的檔案中取用完整的值。
* [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 存放一個有序的列清單加上一個取代旗標，因此 Claude Code 絕不會合併來自兩個來源的列。它會從受管設定、`--settings` 和使用者設定中定義該鍵的最高者取用完整的值，並忽略專案和本機設定中的該鍵。需要 Claude Code v2.1.242 或更新版本。
* [`availableModels`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodels)：當 Claude Code 套用的受管設定定義了它時，Claude Code 會原樣套用該清單，並忽略您在使用者、專案或本機設定中新增的項目，除非嵌入 Claude Code 的應用程式提供了自己的模型清單；請參閱[受管設定優先順序的例外](#exceptions-to-managed-settings-precedence)。在多個受管來源之間，此清單也絕不會合併；[Claude Code 如何結合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明了套用哪個來源的清單。在非受管範圍之間，Claude Code 會照常合併陣列。
* [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings)：Claude Code 會一次針對一個模型解析它，並與 [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 一起解析。`modelSettings` 條目說明了哪個檔案的值會套用到某個模型。

### 優先順序範例

在 Claude 工作時，Claude Code 會在旋轉指示器下方顯示一行提示，例如「Use /config to change your default permission mode (including Plan Mode)」。假設您想關閉這些提示，因此在 `~/.claude/settings.json` 中將 [`spinnerTipsEnabled`](https://code.claude.com/docs/zh-TW/settings-reference#spinnertipsenabled) 設為 `false`。下方的每個情境都是可能將提示重新開啟的情況，以及您可以採取的因應方式。

#### 團隊設定覆寫個人設定

您團隊的 `.claude/settings.json` 將其設為 `true`。Claude Code 會使用專案的值，因為共用專案位於使用者之上，因此您只會在該專案中看到提示，其他地方則不會。

您可以取回您的值：在該專案的 `.claude/settings.local.json` 中新增 `"spinnerTipsEnabled": false`。專案本機位於共用專案之上，因此您在該處的工作階段將不再顯示提示，而您隊友的工作階段不會改變。

#### 組織設定覆寫所有設定

您組織的受管設定將其設為 `true`。您在使用者、專案或本機設定中設定的任何內容都無法關閉提示，`--settings` 也無法。受管是最高層級。

您無法取回您的值。執行 `/status` 以查看套用的是哪個受管來源，並詢問您的管理員是否應變更該政策。

#### 命令列針對單一工作階段覆寫您的檔案

您使用 `claude --settings '{"spinnerTipsEnabled": true}'` 啟動了工作階段。命令列位於除了受管以外的所有檔案之上，因此即使您的檔案設定為 `false`，該工作階段仍會顯示提示。

您會在下一個工作階段取回您的值；`--settings` 僅持續一個工作階段，且不會寫入任何檔案。

#### 旗標或環境變數設定了相同的項目

有些鍵具有命令列旗標或環境變數，無論是哪個檔案設定了該值，都會覆寫設定值：`ANTHROPIC_MODEL` 會覆寫 [`model`](https://code.claude.com/docs/zh-TW/settings-reference#model) 設定，而 `--model` 會在工作階段中覆寫兩者。

您是否能取回您的值取決於該鍵：取消設定該變數或移除該旗標，並查看[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)中該鍵的條目以及[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)中該變數的列，以了解 Claude Code 會使用哪一個。

### 疑難排解未生效的設定

當您設定了某個鍵，但 Claude Code 的行為卻不像您已設定時，請先執行 `/status` 查看它載入了哪些檔案，然後在下方找出您的症狀。[偵錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)涵蓋了更廣泛的檢查，包括乾淨設定測試。

#### 您設定的值被忽略

有其他地方設定了相同的鍵、該檔案無法設定該值，或該檔案未載入：

* **較高層級設定了它。** 另一個設定檔、`--settings` 旗標或受管來源在您之上設定了該鍵；[堆疊](#settings-precedence)說明了是哪一個。旗標或環境變數也可以單獨覆寫該鍵，這是逐鍵決定的；[設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md)中該鍵的條目說明了 Claude Code 使用哪一個，而 [`env` 條目](https://code.claude.com/docs/zh-TW/settings-reference#env)涵蓋了受管 `env` 值與 shell 匯出的比較。
* **安全性鍵保留其嚴格值。** 對於少數鍵，Claude Code 會採用來自任何檔案的限制性值，因此專案中 [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/settings-reference#disableclaudeaiconnectors) 的 `true` 會持續生效；請參閱[受管設定優先順序的例外](#exceptions-to-managed-settings-precedence)。
* **該檔案無法設定該值。** [`permissions.defaultMode`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode) 的 `auto` 和 `bypassPermissions` 值從專案或本機設定中設定時不會生效；請改在使用者或受管設定中設定，或針對單一工作階段傳入 `--permission-mode`。在 v2.1.257 之前，`bypassPermissions` 從任何檔案設定都會生效。

  [`env`](https://code.claude.com/docs/zh-TW/settings-reference#env) 區塊中的遙測匯出變數從專案或本機設定中設定時同樣不會生效，少數關閉值除外。[Claude Code 在 `env` 中忽略的變數](https://code.claude.com/docs/zh-TW/settings-reference#variables-claude-code-ignores-in-env)列出了這些變數及其值。
* **該檔案已損壞。** 無效的 JSON 或被拒絕的值會使 Claude Code 略過該檔案或該條目；請參閱[修正損壞的設定檔](#fix-a-broken-settings-file)。

#### 您在 Claude Code 中所做的變更在新工作階段中遺失

當您在 Claude Code 內部儲存適用於新工作階段的選擇時（例如使用 `/model` 設定預設模型），Claude Code 會將其寫入您的使用者設定檔 `~/.claude/settings.json`。如果您無法寫入該檔案，例如因為另一個工具產生了它或將其連結到唯讀副本，則該變更只會套用於目前的工作階段，並在下一個工作階段中消失。請在產生該檔案的工具中設定該鍵，或以您可以寫入的檔案取代該檔案。

如果您可以寫入該檔案，但變更仍無法保留，請檢查該變更是否[僅適用於單一工作階段](#change-a-setting-for-one-session)，或是否[有較高層級設定了相同的鍵](#a-value-you-set-is-ignored)。對於 `model` 鍵，[新工作階段以與您所選不同的模型啟動](https://code.claude.com/docs/zh-TW/model-config.md#a-new-session-starts-on-a-different-model-than-you-picked)列出了更多原因。

#### 受管變更尚未套用到您

受管來源會依照[傳遞表](https://code.claude.com/docs/zh-TW/managed-settings.md#choose-a-delivery-mechanism)中的排程套用到執行中的工作階段，因此請先重新啟動工作階段。如果 `/status` 顯示的來源與您的管理員變更的來源不同，則表示套用的是優先順序較高的來源；[Claude Code 如何結合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明了其順序。

#### 已提交的鍵未套用到隊友

有兩種情況會使 `.claude/settings.json` 中的鍵無法套用到每位複製它的人：

* **Claude Code 忽略儲存庫檔案中的該鍵。** 在[設定索引](https://code.claude.com/docs/zh-TW/settings-reference.md#settings-index)的 Scope 欄中尋找 `User, local, or managed`、`User or managed`、`User`、`Managed` 或 `Global config`。這些鍵絕不會從共用檔案中生效，除了少數儲存庫檔案仍可關閉的鍵之外。每個這類條目都會在其 Scope 行中註明。`Global config` 鍵僅從 `~/.claude.json` 生效。

  在 `env` 鍵中，遙測匯出變數同樣絕不會從共用檔案中生效，少數關閉值除外；請參閱 [Claude Code 在 `env` 中忽略的變數](https://code.claude.com/docs/zh-TW/settings-reference#variables-claude-code-ignores-in-env)。
* **該鍵需等待信任。** `permissions.allow` 規則、`permissions.additionalDirectories`、`extraKnownMarketplaces` 和大多數 [`env`](https://code.claude.com/docs/zh-TW/settings-reference#env) 值，只有在每位隊友[信任該資料夾](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)之後才會生效。在此之前，他們仍會看到提示，且不會從該檔案宣告的市集取得外掛。`deny` 和 `ask` 規則會立即生效。

#### 權限規則的結合方式與您預期的不同

* **您在權限提示中選擇了「Yes, and don't ask again」，但同一個工具仍然會提示您。** 該選擇會將一條 `allow` 規則儲存到您的本機檔案，而該處的 `allow` 規則並不會優先於來自專案或受管檔案的 `ask` 規則；[權限規則如何結合](https://code.claude.com/docs/zh-TW/permissions.md#settings-precedence)說明了其順序。在 VS Code 擴充功能中，核准卡片可讓您選擇目標檔案，包括專案的共用檔案，這會為所有人變更該規則；在 CLI 中，Claude Code 只會寫入您的本機檔案。
* **您組織的允許規則仍與您的規則一起套用。** 這是預期的行為：Claude Code 會跨範圍合併 [`permissions.allow`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-allow)，除非您的組織設定了 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly)。

### 受管設定優先順序的例外

對於少數其值會限制工作階段的鍵，Claude Code 會採用來自原本無法覆寫受管設定之範圍的限制性值。在此表格中找到該鍵，即可查看它採用哪個值以及來自何處。

| 鍵 | Claude Code 採用的值 | 備註 |
| :- | :- | :- |
| [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/settings-reference#disableclaudeaiconnectors) | 來自任何範圍的 `true` | 即使受管來源設定為 `false` 也會採用 |
| [`enableArtifact`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact) | 來自任何範圍的 `false`，以及來自任何範圍的 `disableArtifact: true` | 即使受管來源設定為 `true` 也會採用；沒有任何設定能重新開啟 [Artifact 工具](https://code.claude.com/docs/zh-TW/artifacts.md#disable-artifacts)。需要 Claude Code v2.1.242 或更新版本 |
| [`isolatePeerMachines`](https://code.claude.com/docs/zh-TW/settings-reference#isolatepeermachines) | 來自任何範圍的 `true` | 即使受管來源設定為 `false` 也會採用 |
| [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) | 來自任何範圍的 `true` | 即使受管來源設定為 `false` 也會採用。需要 Claude Code v2.1.257 或更新版本 |
| [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) | 來自任何範圍的 `true` | 即使受管來源設定為 `false` 也會採用。需要 Claude Code v2.1.314 或更新版本 |
| [`autoMode.classifyAllShell`](https://code.claude.com/docs/zh-TW/settings-reference#automode-classifyallshell) | 來自 `~/.claude/settings.json` 或 `--settings` 的 `true` | 即使受管來源設定為 `false` 也會採用 |
| [`remoteControlAtStartup`](https://code.claude.com/docs/zh-TW/settings-reference#remotecontrolatstartup) | 來自 `.claude/settings.json` 或 `.claude/settings.local.json` 的 `false` | 即使受管來源設定為 `true` 也會採用；專案或本機的 `true` 會被忽略 |
| [`crossSessionInbound`](https://code.claude.com/docs/zh-TW/settings-reference#crosssessioninbound) | 來自 `.claude/settings.json` 或 `.claude/settings.local.json` 的較嚴格值，依 `accept` \< `hold` \< `refuse` 的等級排序 | 優先於受管、`--settings` 和使用者的值；不較嚴格的專案或本機值會被忽略 |
| [`useAutoModeDuringPlan`](https://code.claude.com/docs/zh-TW/settings-reference#useautomodeduringplan) | 來自任何受管來源、`--settings`、`~/.claude/settings.json` 或 `.claude/settings.local.json` 的 `false` | 即使勝出的受管來源設定為 `true` 也會採用；`.claude/settings.json` 中的 `false` 會被忽略。關於啟動時省略的檔案，請參閱[該鍵的條目](https://code.claude.com/docs/zh-TW/settings-reference.md#useautomodeduringplan) |
| [`syncClaudeAiSkills`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiskills) | 來自任何受管來源、`--settings`、`~/.claude/settings.json` 或 `.claude/settings.local.json` 的 `false` | 即使勝出的受管來源設定為 `true` 也會採用；`.claude/settings.json` 中的 `false` 會被忽略 |
| [`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiplugins) | 來自任何受管來源、`--settings`、`~/.claude/settings.json` 或 `.claude/settings.local.json` 的 `false` | 即使勝出的受管來源設定為 `true` 也會採用；`.claude/settings.json` 中的 `false` 會被忽略 |
| [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) | 來自任何範圍（包括 `--settings`）的較低上限 | 即使 Claude Code 套用的受管設定設定了較高的上限也會採用；以最低的上限為準。需要 Claude Code v2.1.267 或更新版本 |

在自身內部執行 Claude Code 並設定了 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的應用程式也是一個例外。Claude Code 會採用該應用程式的模型設定，優先於來自每個受管來源的 `model`、`fallbackModel`、`modelPicker` 和 `modelOverrides` 鍵，以及受管 `env` 區塊中的模型選擇變數，例如 `ANTHROPIC_MODEL` 和 `ANTHROPIC_DEFAULT_*_MODEL` 系列。除非該應用程式提供自己的允許清單，否則 Claude Code 會讓受管的 [`availableModels`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodels) 允許清單持續生效。

## 雲端工作階段中的設定

[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)在[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)中執行，在您儲存庫的新複製上，而不是在您的機器上。這改變了哪些設定到達它：

* **專案中的雲端執行緒**：在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)中的雲端執行緒裡，無論專案有多少個儲存庫，儲存庫 `.claude/settings.json` 中的權限規則、hook 或 `env` 都不會套用。[執行緒從您的儲存庫取得哪些內容](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)列出了可改用的方式。
* **共享專案設定**（`.claude/settings.json`）：在專案執行緒之外具有一個儲存庫的工作階段中讀取，因為檔案是複製的一部分，且工作階段在其內部啟動。在那裡提交設定以在這些工作階段中套用它。
* **具有多個儲存庫的共享專案設定**：在 Anthropic 託管的環境中，具有多個儲存庫的工作階段在複製上方啟動，並從每個儲存庫的 `.claude/settings.json` 只讀取 `enabledPlugins` 和 `extraKnownMarketplaces` 設定鍵，而不是權限規則、hook、`env` 或其他設定鍵。這兩個設定鍵宣告的市集和外掛仍然[不會在雲端工作階段中載入](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)。若為自託管環境，請參閱[適用哪個儲存庫的設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#repository-settings-in-sessions-with-several-repositories)。
* **使用者和專案本機設定**（`~/.claude/settings.json` 和 `.claude/settings.local.json`）：未讀取。兩者都保留在您的機器上，本機檔案不在複製中。
* **受管設定**：您組織的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)會到達雲端工作階段；您裝置上的 `managed-settings.json` 檔案或 MDM 設定檔不會。[表面涵蓋範圍](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)列出哪些雲端工作階段接收它們。[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)也讀取其執行器映像中的受管設定檔案。[Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明該檔案何時適用。
* **`/config`**：在您的瀏覽器中的 claude.ai/code，會開啟您的 claude.ai **Code** 或 **Claude Code** 設定頁面，而不是變更值。若要為雲端工作階段變更設定，請在環境上設定[環境變數](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)。在專案執行緒之外具有一個儲存庫的工作階段中，您也可以改為將設定鍵提交到該儲存庫的 `.claude/settings.json`。

[從您的設定進行的內容](https://code.claude.com/docs/zh-TW/cloud-environments.md#what-carries-over-from-your-setup)列出其餘部分：`CLAUDE.md`、skills、MCP 伺服器、plugins 和認證。

## 下一步

* [所有設定](https://code.claude.com/docs/zh-TW/settings-reference.md)：每個金鑰，及其設定位置和範例
* [範例設定檔案](https://code.claude.com/docs/zh-TW/settings-example.md)：個人檔案、團隊檔案和組織的受管檔案
* [設定權限](https://code.claude.com/docs/zh-TW/permissions.md)：allow、ask 和 deny 規則，以及 Claude Code 在不詢問的情況下執行的內容
* [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)：Claude Code 讀取的變數和 `env` 區塊
* [除錯您的設定](https://code.claude.com/docs/zh-TW/debug-your-config.md)：當設定不適用時
* [Claude 目錄參考](https://code.claude.com/docs/zh-TW/claude-directory.md)：Claude Code 讀取的每個檔案，包括 subagents、MCP 伺服器、plugins 和 `CLAUDE.md`
