<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/settings-example | lastmod: 2026-10-22 | section: Configuration / Settings -->
> 來源：https://code.claude.com/docs/zh-TW/settings-example（官方 zh-TW，lastmod 2026-10-22）｜分類：Configuration › Settings｜EN 摘要：Realistic settings.json files for a developer, a team, and an organization: copy one, keep the keys you want, and change the values.

# 設定檔範例

> 開發者、團隊和組織的實際 settings.json 檔案：複製其中一個，保留您想要的鍵，並變更數值。

本頁面包含三個 `settings.json` 檔案範例，每個對應一個您儲存設定的位置：

* 開發者的 `~/.claude/settings.json`
* 團隊的 `.claude/settings.json`，提交到版本庫
* 組織的 `managed-settings.json`

每個檔案都是該讀者的合理檔案，因此您可以看到結構並複製您想要的部分。它們都不是建議的基準。每個數值都來自 [設定參考](https://code.claude.com/docs/zh-TW/settings-reference.md) 上的鍵項目，其中包含其類型、預設值和可以設定的位置。

每個範例有兩個標籤。**可複製的設定檔** 是您儲存的檔案。**每個鍵的作用** 是相同的檔案，每個鍵上方有註解；Claude Code 不接受設定檔中的註解，因此請從第一個標籤複製。

## 您自己的設定

一位開發者的個人設定。它選擇一個模型和努力程度，調整終端機，並預先批准一個唯讀命令和一個檔案讀取。未列出的所有內容都保持其預設值。這樣的檔案放在 `~/.claude/settings.json` 中，適用於您開啟的每個專案。

> [tab] 可複製的設定檔
>
> 將此儲存為 `~/.claude/settings.json`。這是有效的 JSON，沒有註解，因此您可以直接貼上並刪除您不想要的鍵。
>
> ```json ~/.claude/settings.json theme={null}
> {
>   "model": "claude-sonnet-5",
>   "modelSettings": {
>     "claude-sonnet-5": { "effortLevel": "xhigh" }
>   },
>   "editorMode": "vim",
>   "theme": "light-daltonized",
>   "statusLine": {
>     "type": "command",
>     "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% context\"'",
>     "padding": 2
>   },
>   "spinnerTipsEnabled": false,
>   "preferredNotifChannel": "terminal_bell",
>   "permissions": {
>     "allow": [
>       "Bash(git diff *)",
>       "Read(~/.zshrc)"
>     ]
>   },
>   "autoUpdatesChannel": "stable",
>   "cleanupPeriodDays": 20
> }
> ```

> [tab] 每個鍵的作用
>
> 相同的檔案，每個鍵上方有註解。在此閱讀；從另一個標籤複製，因為 Claude Code 不接受設定檔中的註解。
>
> ```jsonc ~/.claude/settings.json theme={null}
> {
>   // 在 Sonnet 5 上開始每個工作階段
>   "model": "claude-sonnet-5",
>   // 在 Sonnet 5 上執行高於其預設高級別的推理；/effort 為每個模型儲存一個級別，--effort 為單個工作階段設定一個級別
>   "modelSettings": {
>     "claude-sonnet-5": { "effortLevel": "xhigh" }
>   },
>   // 提示中的 Vim 快捷鍵
>   "editorMode": "vim",
>   // 色盲友善的淺色主題
>   "theme": "light-daltonized",
>   // 提示下方的狀態列：模型名稱和已使用的內容
>   "statusLine": {
>     "type": "command",
>     "command": "jq -r '\"[\\(.model.display_name)] \\(.context_window.used_percentage // 0)% context\"'",
>     "padding": 2
>   },
>   // 隱藏在微調器下旋轉的提示
>   "spinnerTipsEnabled": false,
>   // 為通知（例如完成的任務或等待的權限提示）響鈴終端機鈴聲
>   "preferredNotifChannel": "terminal_bell",
>   // 讓 Claude Code 執行 git diff 並讀取您的 .zshrc，無需詢問
>   "permissions": {
>     "allow": [
>       "Bash(git diff *)",
>       "Read(~/.zshrc)"
>     ]
>   },
>   // 從穩定通道取得更新
>   "autoUpdatesChannel": "stable",
>   // 刪除超過 20 天的工作階段記錄和其他本機工作階段資料
>   "cleanupPeriodDays": 20
> }
> ```

## 團隊的共享設定

一個團隊的共享設定，提交到版本庫，以便每個複製它的人都獲得相同的權限、hooks 和外掛程式市集。在版本庫的頂部將這樣的檔案儲存在 `.claude/settings.json`。提交之前需要了解的事項：

* **[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串以外的雲端工作階段也會讀取它。** 包含一個儲存庫的[雲端工作階段](https://code.claude.com/docs/zh-TW/settings.md#settings-in-cloud-sessions)會在複製內部啟動，因此提交的檔案也適用於此。
* **遙測進入受管理或個人設定。** Claude Code 會忽略版本庫設定檔案中的 [OpenTelemetry 匯出器變數](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)，除了一些關閉遙測的值。在 [受管理設定](https://code.claude.com/docs/zh-TW/monitoring-usage.md#administrator-configuration) 中為您的組織設定它們，或在每個人的 `~/.claude/settings.json` 中設定。
* **允許規則等待信任。** 允許規則和 `extraKnownMarketplaces` 項目在每個人 [信任此資料夾本身](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust) 後生效，不僅是父資料夾；拒絕和詢問規則在每個工作階段中適用，無論是否信任。
* **hook 是版本庫中的指令碼。** 此檔案的 hook 執行 `.claude/hooks/block-rm.sh`；[hook 如何解析](https://code.claude.com/docs/zh-TW/hooks.md#how-a-hook-resolves) 說明如何編寫它。
* **規則匹配所寫的命令和路徑。** `Bash(git push *)` 不匹配 [`git -C . push`](https://code.claude.com/docs/zh-TW/permissions#bash-rule-limits)。`Read(./.env)` 本身會停止檔案工具和命名檔案的命令，例如 `cat .env`，但不會停止 [`grep -r` 在目錄上執行](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)；此檔案中的 `sandbox` 區塊關閉了該間隙，因為沙箱 [新增您的 `Read` 拒絕路徑](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-denyread) 到每個沙箱化命令無法讀取的內容。

> [tab] 可複製的設定檔
>
> 將此儲存為版本庫頂部的 `.claude/settings.json` 並提交。這是有效的 JSON，沒有註解，因此您可以直接貼上並刪除您不想要的鍵。
>
> ```json .claude/settings.json theme={null}
> {
>   "permissions": {
>     "allow": [
>       "Bash(npm run *)"
>     ],
>     "ask": [
>       "Bash(git push *)"
>     ],
>     "deny": [
>       "Read(./.env)",
>       "Read(./.env.*)",
>       "Read(./secrets/**)"
>     ]
>   },
>   "hooks": {
>     "PreToolUse": [
>       {
>         "matcher": "Bash",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh"
>           }
>         ]
>       }
>     ]
>   },
>   "extraKnownMarketplaces": {
>     "acme-tools": {
>       "source": {
>         "source": "github",
>         "repo": "acme-corp/claude-plugins"
>       }
>     }
>   },
>   "enabledPlugins": {
>     "code-formatter@acme-tools": true
>   },
>   "sandbox": {
>     "enabled": true,
>     "filesystem": {
>       "allowWrite": [
>         "/tmp/build"
>       ]
>     },
>     "network": {
>       "allowedDomains": [
>         "registry.npmjs.org",
>         "*.example.com"
>       ]
>     }
>   },
>   "plansDirectory": "./plans"
> }
> ```

> [tab] 每個鍵的作用
>
> 相同的檔案，每個鍵上方有註解。在此閱讀；從另一個標籤複製，因為 Claude Code 不接受設定檔中的註解。
>
> ```jsonc .claude/settings.json theme={null}
> {
>   "permissions": {
>     // 執行 npm 指令碼，無需詢問
>     "allow": [
>       "Bash(npm run *)"
>     ],
>     // 在 git push 命令前確認
>     "ask": [
>       "Bash(git push *)"
>     ],
>     // 拒絕檔案工具和檔案讀取命令讀取環境檔案和 secrets 資料夾
>     "deny": [
>       "Read(./.env)",
>       "Read(./.env.*)",
>       "Read(./secrets/**)"
>     ]
>   },
>   // 在每個 Bash 命令前，執行儲存庫中可以阻止它的指令碼
>   "hooks": {
>     "PreToolUse": [
>       {
>         "matcher": "Bash",
>         "hooks": [
>           {
>             "type": "command",
>             "command": "${CLAUDE_PROJECT_DIR}/.claude/hooks/block-rm.sh"
>           }
>         ]
>       }
>     ]
>   },
>   // 在每個複製上註冊團隊的外掛程式市集
>   "extraKnownMarketplaces": {
>     "acme-tools": {
>       "source": {
>         "source": "github",
>         "repo": "acme-corp/claude-plugins"
>       }
>     }
>   },
>   // 啟用該市集中的一個外掛程式；來自外部來源（例如 GitHub 儲存庫）的外掛程式仍需要每個人安裝一次
>   "enabledPlugins": {
>     "code-formatter@acme-tools": true
>   },
>   // 沙箱命令：可寫的建置目錄；npm 和 example.com 預先允許
>   "sandbox": {
>     "enabled": true,
>     "filesystem": {
>       "allowWrite": [
>         "/tmp/build"
>       ]
>     },
>     "network": {
>       "allowedDomains": [
>         "registry.npmjs.org",
>         "*.example.com"
>       ]
>     }
>   },
>   // 將計畫檔案保留在儲存庫內
>   "plansDirectory": "./plans"
> }
> ```

## 組織的受管設定

一個 `managed-settings.json` 檔案，顯示受管鍵的形狀，每個都有一個合理的數值。這不是建議的政策：選擇符合您自己要求的鍵並設定您自己的數值。該範例設定這些鍵：

* `forceLoginMethod` 和 `forceLoginOrgUUID` 固定登入方法和組織
* `availableModels` 和 `enforceAvailableModels` 限制工作階段可以使用的模型
* `permissions.deny` 拒絕兩個檔案讀取和 `curl` 命令 [如 Claude 所寫](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)，`disableBypassPermissionsMode` 移除繞過權限模式
* [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) 和 [`allowManagedMcpServersOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedmcpserversonly) 使受管權限和 MCP 允許清單成為唯一適用的清單
* `allowedMcpServers` 透過 URL 固定 MCP 伺服器
* `strictKnownMarketplaces` 允許一個外掛程式市集
* `sandbox` 沙箱化命令，具有固定的網路允許清單且無沙箱外重試。其 `failIfUnavailable` 鍵會[在沙箱無法執行的環境中阻止 Claude Code 啟動](https://code.claude.com/docs/zh-TW/sandboxing.md#enforce-sandboxing-with-managed-settings)
* `requiredMinimumVersion` 設定最低 Claude Code 版本
* `cleanupPeriodDays` 將工作階段記錄和其他本機資料的保留期縮短至七天
* `companyAnnouncements` 在啟動時顯示訊息

管理員將這樣的檔案部署為 `managed-settings.json`，或透過 MDM 或 [伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) 部署相同的 JSON。一個部署的檔案適用於它到達的每台機器或帳戶。要為一個群組提供不同的數值，請將不同的檔案或設定檔部署到該群組，因為 [伺服器受管設定尚不支援每個群組的政策](https://code.claude.com/docs/zh-TW/server-managed-settings.md#current-limitations)。

> [tab] 可複製的設定檔
>
> 將此部署為 `managed-settings.json`，或透過 MDM 或 claude.ai 主控台部署相同的 JSON。這是有效的 JSON，沒有註解；將範例組織 UUID、伺服器 URL 和市集替換為您自己的，並刪除您不想要的鍵。
>
> ```json managed-settings.json theme={null}
> {
>   "forceLoginMethod": "claudeai",
>   "forceLoginOrgUUID": [
>     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
>   ],
>   "availableModels": [
>     "opus",
>     "sonnet"
>   ],
>   "enforceAvailableModels": true,
>   "permissions": {
>     "deny": [
>       "Bash(curl *)",
>       "Read(./.env)",
>       "Read(./secrets/**)"
>     ],
>     "disableBypassPermissionsMode": "disable"
>   },
>   "allowManagedPermissionRulesOnly": true,
>   "allowedMcpServers": [
>     {
>       "serverUrl": "https://api.githubcopilot.com/*"
>     }
>   ],
>   "allowManagedMcpServersOnly": true,
>   "strictKnownMarketplaces": [
>     {
>       "source": "github",
>       "repo": "acme-corp/approved-plugins"
>     }
>   ],
>   "sandbox": {
>     "enabled": true,
>     "failIfUnavailable": true,
>     "allowUnsandboxedCommands": false,
>     "network": {
>       "allowedDomains": [
>         "registry.npmjs.org",
>         "github.com"
>       ],
>       "allowManagedDomainsOnly": true
>     }
>   },
>   "requiredMinimumVersion": "2.1.150",
>   "cleanupPeriodDays": 7,
>   "companyAnnouncements": [
>     "Welcome to Acme Corp! Review our code guidelines at docs.example.com"
>   ]
> }
> ```

> [tab] 每個鍵的作用
>
> 相同的檔案，每個鍵上方有註解。在此閱讀；從另一個標籤複製，因為 Claude Code 不接受設定檔中的註解。
>
> ```jsonc managed-settings.json theme={null}
> {
>   // 僅 claude.ai 登入，且僅在此組織中
>   "forceLoginMethod": "claudeai",
>   "forceLoginOrgUUID": [
>     "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
>   ],
>   // 僅 Opus 和 Sonnet 模型；使用 enforceAvailableModels，預設選項也遵守清單
>   "availableModels": [
>     "opus",
>     "sonnet"
>   ],
>   "enforceAvailableModels": true,
>   "permissions": {
>     // 在每台機器上拒絕 curl 命令和讀取專案的 .env 檔案和 secrets 資料夾
>     "deny": [
>       "Bash(curl *)",
>       "Read(./.env)",
>       "Read(./secrets/**)"
>     ],
>     // 從每個工作階段移除繞過權限模式
>     "disableBypassPermissionsMode": "disable"
>   },
>   // 忽略來自使用者、專案和本機設定的權限規則
>   "allowManagedPermissionRulesOnly": true,
>   // 僅 GitHub MCP 伺服器，透過 URL 而非名稱匹配，因為使用者可以
>   // 將任何伺服器命名為 "github"。不匹配的使用者新增伺服器不會載入，包括
>   // 當清單僅有 URL 項目時的每個 stdio 伺服器。下面的 allowManagedMcpServersOnly
>   // 鍵使此受管清單成為唯一適用的允許清單
>   "allowedMcpServers": [
>     {
>       "serverUrl": "https://api.githubcopilot.com/*"
>     }
>   ],
>   "allowManagedMcpServersOnly": true,
>   // 外掛程式只能來自此市集
>   "strictKnownMarketplaces": [
>     {
>       "source": "github",
>       "repo": "acme-corp/approved-plugins"
>     }
>   ],
>   // 沙箱化 Claude 執行的每個命令，如果無法設定沙箱則拒絕啟動，
>   // 並且永遠不讓被阻止的命令在沙箱外重試；網路
>   // 限制為 npm 和 GitHub，使用者無法新增網域
>   "sandbox": {
>     "enabled": true,
>     "failIfUnavailable": true,
>     "allowUnsandboxedCommands": false,
>     "network": {
>       "allowedDomains": [
>         "registry.npmjs.org",
>         "github.com"
>       ],
>       "allowManagedDomainsOnly": true
>     }
>   },
>   // 拒絕在 2.1.150 之前的版本上啟動
>   "requiredMinimumVersion": "2.1.150",
>   // 在 7 天後刪除工作階段記錄和其他本機工作階段資料
>   "cleanupPeriodDays": 7,
>   // 每個使用者在啟動時看到的訊息
>   "companyAnnouncements": [
>     "Welcome to Acme Corp! Review our code guidelines at docs.example.com"
>   ]
> }
> ```
