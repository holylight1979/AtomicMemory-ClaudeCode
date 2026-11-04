<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-reference | lastmod: 2026-11-03 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-reference（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Environments｜EN 摘要：Complete reference for the self-hosted runner and orchestrator: CLI flags, environment variables, and Prometheus metrics.

# 自託管環境參考

> 自託管執行器和協調器的完整參考：CLI 旗標、環境變數和 Prometheus 指標。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)可以在 [**Cloud environments** 管理頁面](https://claude.ai/admin-settings/cloud-environments)上開啟 **Allow self-hosted environments** 來啟用它們。本頁面是旗標和指標參考；請參閱 [快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)以了解設定，以及 [部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)以了解艦隊配方。

本頁面是您在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中執行的兩個程序的參考：執行器在您的主機上執行 Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，以及可選的自動擴展協調器，它在工作階段佇列時啟動執行器。每個都有自己的旗標表。兩者都在 Linux 或 macOS 主機上執行，預設值如 `/workspace` 和 `~/.claude` 假設。執行 `claude self-hosted-runner --help` 以取得您已安裝版本上的權威清單。

指標序列和一些 API 欄位仍然使用 `pool` 來表示這些頁面所稱的環境；兩個術語都命名相同的東西。環境 ID 是 `pool_id` 欄位，形式為 `ccpool_...`：無論這些頁面在何處顯示 `pool` 識別碼，它都命名環境。CLI 旗標和環境變數將其拼寫為 `environment`，例如 `--environment-secret-file`；已棄用的 `pool` 拼寫仍然有效，如 [`--environment-secret-file` 列](#runner-cli-flags)所述。

## 執行器 CLI 旗標

大多數旗標都有對應的環境變數。當兩者都設定時，旗標優先。持續時間旗標在 CLI 上採用分鐘或秒，但配對的環境變數始終以毫秒為單位，由 `_MS` 後綴表示，預設列顯示旗標的單位：`--exit-if-unused-min 10` 等同於 `SELF_HOSTED_RUNNER_IDLE_SHUTDOWN_MS=600000`，而 Helm 值如 `SELF_HOSTED_RUNNER_STARTUP_TIMEOUT_MS: "15"` 表示 15 毫秒，而不是 15 分鐘的預設值。

| 旗標 | 環境變數 | 預設值 | 說明 |
| :- | :- | :- | :- |
| `--api-url <url>` | 無 | `https://api.anthropic.com` | API 基礎 URL。僅為測試覆蓋。 |
| `--base-dir <path>` | `SELF_HOSTED_RUNNER_BASE_DIR` | `/workspace`；Windows 上無 | 用於存放庫簽出和每個工作階段工作目錄的目錄。執行器需要對此路徑或其父目錄的寫入存取。執行器在啟動時建立目錄，當無法建立或寫入時以 `cannot create or write to base directory` 退出。在 v2.1.225 之前，執行器在第一個工作階段啟動時建立目錄，因此無法使用的路徑會導致工作階段失敗而不是啟動失敗。在 Windows 上（不是支援的執行器主機），沒有預設值：除非您傳遞旗標或設定變數，否則執行器在啟動時退出。在環境中的每個執行器上使用相同的值。請參閱[在執行器之間保持基礎目錄和容量相同](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#keep-the-base-directory-and-capacity-identical-across-runners)。 |
| `--capacity <n>` | 無 | `1` | 此執行器處理的最大並行工作階段。所有工作階段都屬於同一個鎖定的[擁有者](https://code.claude.com/docs/zh-TW/self-hosted-environments#key-concepts)。在環境中的每個執行器上使用相同的值；請參閱[在執行器之間保持基礎目錄和容量相同](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#keep-the-base-directory-and-capacity-identical-across-runners)。 |
| `--client-label <label>` | `SELF_HOSTED_RUNNER_CLIENT_LABEL` | 主機的主機名稱 | 執行器在註冊時傳送的標籤。執行器也將其報告為 [`claude_code_self_hosted_runner_info`](#prometheus-metrics) 的 `client_label` 標籤。需要 Claude Code v2.1.248 或更新版本。 |
| `--configure-git` | `SELF_HOSTED_RUNNER_CONFIGURE_GIT=1` | 關閉 | 在啟動時，寫入全域 git 身份、啟用 Anthropic 提交簽署、開啟 git push 協商，並安裝附加 `Co-authored-by:` 預告片的提交掛鉤。Push 協商需要 Claude Code v2.1.257 或更新版本。請參閱[配置 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)。 |
| `--confine-repo-settings <mode>` | `SELF_HOSTED_RUNNER_CONFINE_REPO_SETTINGS` | `warn` | 設定防護的模式，當存放庫的已提交設定嘗試授予對該工作階段自己的工作區之外的寫入或讀取存取、設定環境變數或覆蓋操作員的沙箱或掛鉤姿態時，該防護會標記工作階段，例如 `sandbox.enabled: false` 或 `disableAllHooks`。預設 `warn` 記錄違規並仍然啟動工作階段，`enforce` 拒絕工作階段，`off` 停用掃描。請參閱[強化您的部署](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)。 |
| `--debug-token-dir <path>` | `SELF_HOSTED_RUNNER_DEBUG_TOKEN_DIR` | 未設定 | 將即時權杖寫入磁碟以供檢查。僅用於偵錯；不要在生產環境中使用。 |
| `--defer-shutdown-max-min <n>` | `SELF_HOSTED_RUNNER_DEFER_SHUTDOWN_MAX_MS` | `0` | 在第一個 `SIGTERM` 或 `SIGINT` 上，繼續為已附加的工作階段提供服務而不是排空它們，然後在 N 分鐘後釋放仍然附加的任何內容並退出。在設定此項之前提高主機的停止逾時。請參閱[將排空延遲到第一個信號之後](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#defer-the-drain-past-the-first-signal)。`0` 停用。需要 Claude Code v2.1.238 或更新版本。 |
| `--drain-grace-sec <n>` | `SELF_HOSTED_RUNNER_DRAIN_GRACE_MS` | `0` | 在執行器接收到關閉信號或達到其退休時間之前，控制執行器在其活動工作階段完成後何時退出：`0` 立即退出而不輪詢更多內容，正值使執行器保持活動並首先重新輪詢鎖定擁有者的佇列該許多秒，代價是[強化部分](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)中描述的每個工作階段容器隔離。在您使用 [`--defer-shutdown-max-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#defer-the-drain-past-the-first-signal) 延遲的第一個信號之後，執行器在不持有任何工作階段時立即退出，無論您在此設定什麼。 |
| `--drain-marker-file <path>` | `SELF_HOSTED_RUNNER_DRAIN_MARKER_FILE` | 未設定 | 標記檔案，您的主機在傳送 `SIGTERM` 之前寫入以宣佈優雅排空。當檔案在排空開始時存在時，執行器將其退出報告給 Anthropic 為主機排空而不是純粹的關閉信號。排空本身（包括 `--drain-wait-sec` 保留）的執行方式與沒有旗標相同。在本地檔案系統上命名工作階段無法寫入的路徑。需要 Claude Code v2.1.271 或更新版本。 |
| `--drain-wait-sec <n>` | `SELF_HOSTED_RUNNER_DRAIN_WAIT_MS` | `0` | 排空開始後（除非您設定 [`--defer-shutdown-max-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#defer-the-drain-past-the-first-signal)，否則在 `SIGTERM` 上），等待最多 N 秒讓每個工作階段的進行中回合和背景任務完成，然後終止子程序。在此等待期間，執行器將剛完成的背景任務計為仍在執行，直到讀取其結果的後續回合開始，最多 [`SELF_HOSTED_RUNNER_BG_RESULT_GRACE_MS`](#environment-variable-only-settings) 視窗。[同時也請提高您的停止逾時](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#let-running-turns-finish-before-a-restart)。 |
| `--environment-secret-file <path>` | `SELF_HOSTED_RUNNER_ENVIRONMENT_SECRET` | 必需 | 包含環境祕密的檔案路徑，或對於由[協調器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)產生的執行器，單次使用工作訂單 JWT。`SELF_HOSTED_RUNNER_ENVIRONMENT_SECRET` 直接攜帶祕密值，而不是檔案路徑。較舊的 `--pool-secret-file` 旗標和 `SELF_HOSTED_RUNNER_POOL_SECRET` 變數仍然有效並列印棄用通知到 stderr；早於 2.1.216 的預覽程式執行器組建只識別那些較舊的名稱。 |
| `--exec-path <path>` | `SELF_HOSTED_RUNNER_EXEC_PATH` | 自己的二進位檔 | 為每個工作階段產生的二進位檔或包裝指令碼。請參閱[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)。 |
| `--exit-if-unused-min <n>` | `SELF_HOSTED_RUNNER_IDLE_SHUTDOWN_MS` | `0` | 在輪詢 N 分鐘且從未被指派任何工作後退出，用於自動擴展器縮小。`0` 停用。 |
| `--git-host-rewrite <from>=<to>` | 無 | 未設定 | 在複製之前將 `https://<from>/...` 來源 URL 重寫為 `https://<to>/...`，用於分割視界 DNS。可重複；僅旗標。 |
| `--git-ssh-rewrite <host>` | 無 | 未設定 | 在複製之前將 `https://<host>/...` 來源 URL 重寫為 `git@<host>:...`，用於僅限 SSH 的 git 主機。可重複；僅旗標。 |
| `--health-port <port>` | `SELF_HOSTED_RUNNER_HEALTH_PORT` | `8080` | `/healthz` 和 `/metrics` 接聽器的連接埠。設定 `0` 以停用。 |
| `--hold-idle-file <path>` | `SELF_HOSTED_RUNNER_HOLD_IDLE_FILE` | 未設定 | 您的主機持續變更的檔案，用以在執行器上保留閒置的工作階段。請參閱[在其程序執行期間保留閒置的工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#keep-an-idle-session-while-its-processes-run)。需要 Claude Code v2.1.311 或更新版本。 |
| `--hooks-dir <path>` | `SELF_HOSTED_RUNNER_HOOKS_DIR` | 未設定 | 生命週期掛鉤指令碼的目錄。請參閱[生命週期掛鉤](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#lifecycle-hooks)。 |
| `--host-config-snapshot <mode>` | `SELF_HOSTED_RUNNER_HOST_CONFIG_SNAPSHOT` | `disk` | 執行器保持[主機設定目錄](#environment-variable-only-settings)啟動快照的位置，它從中播種每個工作階段。`disk` 將快照複製到 `--base-dir` 下執行器擁有的目錄中，並在每個工作階段啟動時，驗證每個檔案對照記憶體內摘要。如果副本中的檔案已被修改，工作階段失敗，執行器拒絕工作階段，直到您重新啟動它。`memory` 在堆上保持整個快照，上限為 64 MiB；超過上限，工作階段啟動時沒有主機設定並顯示說明這一點的通知。當執行器無法寫入磁碟快照時，它記錄失敗並為該執行使用 `memory`。需要 Claude Code v2.1.271 或更新版本。 |
| `--kill-session-after-min <n>` | `SELF_HOSTED_RUNNER_MAX_LIFETIME_MS` | `0` | 將工作階段限制為 N 分鐘牆上時間，作為卡住工作階段的安全限制。在 v2.1.260 或更新版本上，執行器釋放達到限制的工作階段，以便它可以在其使用者的下一條訊息上繼續，並且只有在它在 [`SELF_HOSTED_RUNNER_MAX_LIFETIME_GRACE_MS`](#environment-variable-only-settings) 寬限期結束時仍在執行器上時才終止它。在 v2.1.260 之前，執行器在限制時終止工作階段。請參閱[某些工作階段不計為閒置](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#some-sessions-don%E2%80%99t-count-as-idle)以了解詳細資訊以及如何選擇值。`0` 停用。 |
| `--lock-to-account <id>` | `SELF_HOSTED_RUNNER_LOCK_TO_ACCOUNT` | 未設定 | 在啟動時預先將執行器鎖定到特定帳戶，而不是在第一個工作階段時鎖定。接受環境組織中的電子郵件地址或 `user_...` ID。預先鎖定的執行器永遠不會拾取 Claude Tag 頻道工作階段，這些工作階段沒有帳戶。 |
| `--log-file <path>` | `SELF_HOSTED_RUNNER_LOG_FILE` | 未設定 | 除了 stdout 和 stderr 外，還將執行器日誌鏡像到檔案，使用 `0600` 權限建立。`self-hosted-runner doctor` 在本地尾部日誌需要此項。 |
| `--log-level <level>` | 無 | `info` | `info` 或 `debug` |
| `--max-hold-min <n>` | `SELF_HOSTED_RUNNER_MAX_HOLD_MS` | `1440` | 搭配 `--hold-idle-file` 使用時，在保留的工作階段進入閒置 N 分鐘後，仍將其釋放。等於或低於 `--release-idle-session-min` 的值不會保留任何工作階段。`0` 會關閉保留。需要 Claude Code v2.1.311 或更新版本。 |
| `--post-session-hook-timeout-sec <n>` | `SELF_HOSTED_RUNNER_POST_SESSION_HOOK_TIMEOUT_MS` | `60` | [`post-session` 掛鉤](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session)在每個工作階段結束時的預算，包括執行器關閉 |
| `--proxy-authorization-command <command>` | `SELF_HOSTED_RUNNER_PROXY_AUTHORIZATION_COMMAND` | 未設定 | 執行器為每個到您的出口代理的連線執行的 Shell 命令，使用其修剪的 stdout 作為 `Proxy-Authorization` 標頭值。需要 `HTTPS_PROXY` 或 `HTTP_PROXY`，不能與 `--proxy-authorization-file` 結合。請參閱[驗證到出口代理](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#authenticate-to-an-egress-proxy)。需要 Claude Code v2.1.238 或更新版本。 |
| `--proxy-authorization-file <path>` | `SELF_HOSTED_RUNNER_PROXY_AUTHORIZATION_FILE` | 未設定 | 執行器為每個到您的出口代理的連線讀取的檔案，使用其修剪的內容作為 `Proxy-Authorization` 標頭值。對於另一個程序就地輪換的權杖，使用此旗標。與 `--proxy-authorization-command` 具有相同的要求，不能與其結合。請參閱[驗證到出口代理](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#authenticate-to-an-egress-proxy)。需要 Claude Code v2.1.238 或更新版本。 |
| `--push-outcome-on-release` | `SELF_HOSTED_RUNNER_PUSH_OUTCOME_ON_RELEASE` | 關閉 | 在執行器因排空或閒置釋放等原因主動結束工作階段時，執行器會在刪除工作區之前，將含有新提交的主要工作階段分支推送到 `origin`。盡力而為；將關閉預算增加 30 秒。需要 git 2.29 或更新版本才能從這些分支繼續。將推送存取限制在 `claude/*` 參考；請參閱[已繼續的工作階段會遺失未推送的工作](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#resumed-sessions-lose-unpushed-work)。`checkout` hook 的儲存庫不會被推送；請從 [`post-session` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session) 快照這些儲存庫。 |
| `--release-idle-session-min <n>` | `SELF_HOSTED_RUNNER_SESSION_IDLE_MS` | `0` | 在回合完成或工作階段等待使用者操作後，經過 N 分鐘的不活動即釋放工作階段槽。[某些工作階段不計為閒置](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#some-sessions-don’t-count-as-idle)，因此請與 `--kill-session-after-min` 搭配使用。已完成的背景任務最多會在 [`SELF_HOSTED_RUNNER_BG_RESULT_GRACE_MS`](#environment-variable-only-settings) 視窗內讓工作階段保持忙碌。若要延遲釋放，請設定 [`--hold-idle-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#keep-an-idle-session-while-its-processes-run)。`0` 停用。 |
| `--remove-session-state [bool]` | `SELF_HOSTED_RUNNER_REMOVE_SESSION_STATE` | 關閉 | 當工作階段在此執行器上結束時，移除 `<base-dir>/_sessions/` 下的工作階段的每個工作階段目錄，無論結果如何。[重複使用預先加熱的簽出](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#reuse-a-pre-warmed-checkout)描述它們持有的內容以及當它們保留時誰可以讀取它們。移除是盡力而為：當執行器被終止或在清理執行之前達到其排空期限時，每個工作階段目錄保留在原位。啟用旗標後，失敗或中斷的工作階段的偵錯日誌不會保留在磁碟上。需要 Claude Code v2.1.268 或更新版本。 |
| `--retire-at <epoch-seconds>` | `SELF_HOSTED_RUNNER_RETIRE_AT` | 未設定 | 在絕對 Unix 時間戳記（秒）時退休執行器，用於在已知時間終止執行器的基礎設施；[執行器生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)描述釋放序列以及如何調整邊距。2001 年之前或 5138 年之後的值被旗標拒絕，被環境變數忽略。 |
| `--server-auto-mode-lists <mode>` | `SELF_HOSTED_RUNNER_SERVER_AUTO_MODE_LISTS` | `no-allow` | 控制平面隨工作階段傳送的[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器規則清單中，哪些可以送達該工作階段：`all`、`no-allow` 或 `none`。請參閱[自動模式規則清單](#auto-mode-rule-lists)以了解每個值套用的內容。無效的值會使執行器在啟動時停止。需要 Claude Code v2.1.295 或更新版本。 |
| `--session-stop-grace-sec <n>` | `SELF_HOSTED_RUNNER_SESSION_STOP_GRACE_MS` | `5` | 在工作階段結束後，在強制終止之前等待 Claude 程序乾淨退出的時間。如果子程序自己的 `SessionEnd` 掛鉤需要更多時間，請提高該值。 |
| `--startup-timeout-min <n>` | `SELF_HOSTED_RUNNER_STARTUP_TIMEOUT_MS` | `15` | 在釋放工作階段槽之前，等待尚未完成初始化的子程序的時間。請參閱[工作階段啟動逾時](#session-startup-timeout)以了解計時從何時開始，以及哪些工作階段會繼續執行。`0` 停用逾時。 |
| `--trust-workspace [bool]` | `SELF_HOSTED_RUNNER_TRUST_WORKSPACE` | 開啟 | 為每個工作階段的存放庫路徑播種持久化信任，以便尊重存放庫提交的 `permissions.allow` 和 `additionalDirectories`。設定 `false` 以放棄存放庫提交的權限授予，並改為在主機設定的 `settings.json` 中配置允許規則；存放庫提交的 `sandbox.*` 設定無論如何仍然適用，這就是為什麼[存放庫設定防護](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)無論此旗標如何都掃描它們。 |
| `--use-anthropic-git-proxy` | `CLAUDE_RUNNER_USE_GIT_PROXY=1` | 關閉 | 透過 [Anthropic git proxy](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy) 複製 github.com 上的儲存庫，而不是使用客戶管理的 git 驗證。需要 `--capacity 1` 和 git 2.32 或更新版本；否則執行器拒絕啟動。取代重寫旗標。 |

大多數持續時間旗標都有最大值，選擇以將每個逾時保持在執行時間的 32 位元計時器上限內，大約 24.85 天。`--*-min` 旗標上限為 10080 分鐘，7 天；`--drain-grace-sec` 為 604800 秒，也是 7 天；`--drain-wait-sec` 為 86400 秒，24 小時。`--session-stop-grace-sec` 和 `--post-session-hook-timeout-sec` 無上限。超過上限的行為因表面而異：

* **旗標**：啟動失敗並出現錯誤。
* **環境變數**：執行器將值夾住到計時器上限，而不是拒絕它。

### 工作階段啟動逾時

如果工作階段在 `/code-review` 等回合期間失去了其槽，請將執行器和子程序的二進位檔更新至 v2.1.309 或更新版本。從 v2.1.299 到 v2.1.308，一旦啟動逾時經過而沒有出現 `user` 或 `assistant` 訊息，執行器就會釋放工作階段，即使在回合進行中也是如此。

使用 `--startup-timeout-min <n>` 時，如果子程序在複製後 `<n>` 分鐘內尚未完成初始化，執行器會釋放工作階段的槽。在子程序完成初始化之前開始的回合期間，工作階段會保留其槽，直到子程序的[活動頻道](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#keep-stdin-and-file-descriptor-3-attached)上經過 `<n>` 分鐘都沒有任何一行輸出為止。子程序完成初始化後，執行器會清除該計時，並改由 `--release-idle-session-min` 控制釋放。若要限制子程序仍存活但已卡住的工作階段，請設定 `--kill-session-after-min`。

### 自動模式規則清單

`--server-auto-mode-lists` 讓您決定哪些來自執行器外部的[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器規則可以送達您執行器上的工作階段。Anthropic 的控制平面可以隨工作階段傳送規則清單，並要求執行器套用它們。其中某些項目可能是您組織的管理員所撰寫的規則。這些清單為 `environment`、`soft_deny` 和 `allow`：

* **`environment`**：項目可以讓分類器允許更多，也可以允許更少。
* **`soft_deny`**：項目會封鎖某個動作，除非使用者明確要求該動作或適用某個 `allow` 例外。
* **`allow`**：`soft_deny` 項目的例外。

旗標的值決定執行器套用哪些清單：

* **`no-allow`**：預設值。套用 `environment` 和 `soft_deny`，並保留 `allow` 不套用。`environment` 項目仍然可以讓分類器允許更多，因此預設值並不會排除所有放寬。
* **`all`**：套用全部三個清單。
* **`none`**：一個都不套用。選擇 `none` 可排除來自這些清單的所有放寬。它也會捨棄 `soft_deny` 的限制。

沒有任何執行器設定能讓控制平面要求執行器套用這些清單。當控制平面未提出要求時，無論您如何設定，工作階段都不會收到任何清單。若要查看實際發生的情況，請使用 `--log-level debug` 啟動執行器。執行器接著會為每個工作階段記錄一行包含 `the server asked this runner to apply` 的日誌，或一行包含 `the server did not ask this runner to apply the auto mode lists it sends` 的日誌。

## 協調器 CLI 旗標

`self-hosted-runner orchestrator` 子命令（產生[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)）接受 `--api-url`、`--environment-secret-file`、`--hooks-dir`、`--health-port` 和 `--log-level`，具有與執行器相同的預設值，以及執行器旗標具有的相同環境變數，除了 `--hooks-dir` 是必需的且必須包含 `spawn-runner` 掛鉤。它也採用自己的旗標：

| 旗標 | 預設值 | 說明 |
| :- | :- | :- |
| `--hook-concurrency <n>` | `4` | 最大 `spawn-runner` hook 並行執行數。也限制每次輪詢聲稱多少個產生請求。協調器只有在其啟動的每個 hook 都完成後，才會檢查新的產生請求，因此一個緩慢的 hook 會延遲該協調器的後續 hook。 |
| `--hook-timeout <sec>` | `60` | 在此許多秒後終止掛鉤的程序樹。逾時加上其 5 秒終止寬限期必須保持在 `--expected-spawn-seconds` 以下；協調器在啟動時強制執行此項。 |
| `--expected-spawn-seconds <sec>` | `120` | 從協調器收到產生請求到執行器註冊為止的預期 p99 時間，包括在您的平台上等待容量的任何時間。伺服器強制的範圍為 10 到 3600。在每次輪詢時作為伺服器端租約發送：如果沒有執行器在其經過前註冊，工作階段會以新訂單 ID 重新提供。所有副本必須共享此值。 |
| `--min-idle <n>` | `0` | 通過主動產生待命執行器來保持至少 N 個閒置工作階段槽空閒。`0` 停用預熱。與執行器的 `--exit-if-unused-min` 配對，以便多餘的待命執行器回收自己。 |
| `--shutdown-drain-sec <n>` | `0` | 收到 `SIGTERM` 時，停止輪詢產生請求，並給予執行中的 `spawn-runner` hook 及任何尚未回應的輪詢最多此秒數來完成，之後再停止剩餘的項目。設為 `0` 時，立即停止。上限為 `3600`，協調器在啟動時強制執行此項。若要選擇值，請參閱[調整 `--shutdown-drain-sec` 和協調器的停止逾時](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#size-shutdown-drain-sec-and-the-supervisors-stop-timeout-for-the-orchestrator)。需要 Claude Code v2.1.299 或更新版本。 |
| `--debug-dir <path>` | 未設定 | 將每個產生請求的工作訂單和掛鉤 stderr 寫入磁碟。僅用於偵錯；永遠不要在生產環境中設定。 |

### SCM 連接器旗標

SCM 連接器無法使用，因此請將本節中的旗標保持未設定。如果您設定 `--scm-connector-host`，連線不會開啟，協調器會持續重試。執行器仍會以工作階段佇列的形式啟動。

連接器是從協調器到 Anthropic 控制平面的常設 WebSocket 連線。它的設計目的是讓託管的預工作階段流程（例如存放庫選擇器和分支或參考解析器）能夠到達只能從您的網路內部路由的 GitHub Enterprise Server 主機。請參閱 GitHub Enterprise Server 頁面上的[網路需求](https://code.claude.com/docs/zh-TW/github-enterprise-server.md#network-requirements)，了解這些流程需要什麼。

| 旗標 | 預設值 | 說明 |
| :- | :- | :- |
| `--scm-connector-host <host[:port]>` | 未設定 | GitHub Enterprise Server 主機名稱以轉發請求。連接埠預設為 `443`。 |
| `--scm-connector-id <n>` | 與 `--scm-connector-host` 必需 | 您組織的 GitHub Enterprise Server 連線的數字 ID。 |
| `--scm-connector-provider <slug>` | `ghe` | 識別提供者的路徑段，符合 `^[a-z0-9-]{1,32}$`。 |
| `--scm-connector-ca-file <path>` | 未設定 | 額外的 CA 套件（PEM 格式），用於到 GitHub Enterprise Server 主機的 TLS 連線。 |
| `--scm-connector-host-rewrite <from>=<to_host:to_port>` | 未設定 | 僅用於端到端測試：重定向 TCP 連線，同時將主機標頭和 TLS SNI 保持為 `--scm-connector-host`。 |

在每次連線嘗試時，協調器會發送其現有的環境祕密，並使用指數退避自動重試，上限為 30 秒加上抖動。

## 僅環境變數設定

這些執行器設定僅從環境讀取，涵蓋大多數部署保留在預設值的行為：

| 環境變數 | 預設值 | 說明 |
| :- | :- | :- |
| `SELF_HOSTED_RUNNER_BG_RESULT_GRACE_MS` | `30000` | 執行器在背景工作完成後考慮工作階段忙碌的時間，而讀取結果的後續轉向尚未開始。[`--drain-wait-sec` 和 `--release-idle-session-min` 列](#runner-cli-flags)描述排空和閒置釋放時保持適用的位置，[執行器生命週期](https://code.claude.com/docs/zh-TW/self-hosted-environments#runner-lifecycle)描述它在 `--retire-at` 退休時適用的位置。`0` 或無法使用的值回退到預設值，因此無法關閉保持。需要 Claude Code v2.1.228 或更新版本。 |
| `SELF_HOSTED_RUNNER_HOST_CONFIG_DIR` | `~/.claude` | 捕獲到執行器啟動快照中並播種到每個工作階段的 `CLAUDE_CONFIG_DIR` 的目錄；磁碟上的變更在執行器重新啟動後適用。設定變數也會移動執行器讀取 `.claude.json` 的位置以進行 [MCP 播種](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#mcp-servers)，因此設定它（包括其自己的預設值）會重新定位該查詢；指向空目錄以完全停用播種。 |
| `SELF_HOSTED_RUNNER_MAX_LIFETIME_GRACE_MS` | `900000` | 執行器在工作階段達到其 `--kill-session-after-min` 限制後等待的時間，以便執行中的轉向完成或釋放完成，然後才終止工作階段 |
| `SELF_HOSTED_RUNNER_POST_TURN_SETTLE_MS` | `7000` | 執行器在轉向完成後計算工作階段忙碌的上限時間，用於 `--drain-wait-sec` 排空，而工作階段的程序向 Anthropic 報告轉向的結束。`0` 或無法使用的值回退到預設值，因此無法關閉保持。需要 Claude Code v2.1.275 或更新版本。 |
| `SELF_HOSTED_RUNNER_SIGKILL_GRACE_MS` | `30000` | 執行器等待作業系統將 `SIGKILL` 傳遞到卡在不可中斷 I/O 中的子程序的時間，然後自己退出。下限為 `--post-session-hook-timeout-sec` 加 15 秒，以及設定 `--push-outcome-on-release` 時的 30 秒，因此有效最小值在預設值為 75 秒。 |
| `CLAUDE_RUNNER_FETCH_DEPTH` | `50` | 新複製的 git 提取深度。設定正整數，或 `full` 或 `0` 以進行完整提取。對於工作區中已存在的複製，請參閱[重複使用預熱的簽出](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#reuse-a-pre-warmed-checkout)。 |
| `CLAUDE_RUNNER_FETCH_SERVER_PROGRESS_CAP_MS` | `600000` | 每次嘗試中，當 git 伺服器本身的進度數字持續上升時（例如伺服器為大型儲存庫準備 pack 時），git 提取可等待第一筆資料的時間（以毫秒為單位）。`0` 或 `off` 會關閉此等待：此類提取在兩分鐘內沒有資料時即會被中斷。其他任何整數會被限制在 `120000` 到 `1800000` 之間，即 2 到 30 分鐘。需要 Claude Code v2.1.295 或更新版本。 |
| `CLAUDE_RUNNER_SKIP_GIT_VERIFY` | 未設定 | 當 `1` 時，在 `checkout` 掛鉤執行後跳過 `.git` 存在檢查。當您的掛鉤具體化非 git 來源時設定此項。 |
| `FORCE_AUTOUPDATE_PLUGINS` | 未設定 | 當 `1` 時，即使二進位檔被固定，也讓外掛程式市場自動更新 |
| `CLAUDE_CODE_DISABLE_ARTIFACT` | 未設定 | 當 `1` 時，無論組織的管理員設定如何，都在工作階段中停用 Artifact 工具，並放棄 `*.frame.claudeusercontent.com` 出口要求 |

## 遙測

工作階段子程序將操作遙測傳送給 Anthropic，除非您將其關閉。不會傳送任何程式碼或存放庫內容。在執行器程序上設定遙測變數；執行器在應用伺服器提供的環境變數後重新聲稱它們，因此操作員的設定始終優先。

一個控制項特定於自託管環境：`CLAUDE_CODE_BYOC_ENABLE_DATADOG=1` 選擇加入 Datadog 操作指標，在自託管環境中預設為關閉。一般 Claude Code 遙測控制項 `DISABLE_TELEMETRY`、`DO_NOT_TRACK`、`DISABLE_ERROR_REPORTING` 和 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 適用於工作階段子程序，如[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)中所述。`DISABLE_GROWTHBOOK` 相關但不同：設定 `DISABLE_GROWTHBOOK=1` 停用功能旗標提取，遙測保持開啟，除非也設定了 `DISABLE_TELEMETRY`。

`CLAUDE_CODE_ENABLE_TELEMETRY` 無關：它啟用 OpenTelemetry 匯出到您自己的收集器，如[監控](https://code.claude.com/docs/zh-TW/monitoring-usage.md)中所述，不控制 Anthropic 的分析。

## 健康端點

執行器在配置的健康連接埠上提供 `GET /healthz`。只要程序活著，無論輪詢迴圈處於什麼狀態，回應都是 `200 OK`，因此此端點上的 HTTP 探測只檢測死程序。JSON 主體描述當前狀態：

```json theme={null}
{
  "status": "ok",
  "runner_id": "ccrunner_...",
  "active_sessions": 2,
  "last_poll_at": "2026-03-31T18:04:11.220Z",
  "last_poll_age_ms": 842
}
```

請針對 `last_poll_age_ms` 設定警報，但不要在存活探測中使用它；存活探測應維持以 HTTP 狀態碼為依據。此值是自上次成功輪詢以來經過的時間，因此當執行器無法連線至 Anthropic 時，它也會持續上升。`last_poll_at` 和 `last_poll_age_ms` 在第一次輪詢成功之前都是 `null`。若要偵測從一開始就失敗的輪詢，也請針對 `claude_code_self_hosted_runner_poll_errors_total` 設定警報，該指標列於 [Prometheus 指標](#prometheus-metrics)中。

協調器自己的 `/healthz` 位於其健康連接埠上，始終返回 `200`。主體攜帶報告最近一次輪詢是否成功的 `connected` 欄位，以及 `queue_counts` 中依狀態分類的產生佇列計數。若要了解 `connected` 為何是 `false`，請讀取頂層的 `last_error` 欄位，每次輪詢成功時都會將其重設為 `null`。請根據 `connected` 而非狀態碼來判斷就緒狀態與觸發警報。

當配置[SCM 連接器](#scm-connector-flags)時，協調器的 `/healthz` 主體也攜帶 `scm_connector_connected` 和一個 `scm_connector` 物件，其中包含 `connected`、`last_connected_at`、`last_error`、`reconnects` 和 `requests_forwarded`。當未設定 `--scm-connector-host` 時，兩個欄位都是 `null`。

## Prometheus 指標

每個執行器在與 `/healthz` 相同的連接埠上的 `GET /metrics` 上提供 Prometheus 指標。關鍵序列：

| 序列 | 備註 |
| :- | :- |
| `claude_code_self_hosted_runner_info{runner_id,version,client_label}` | 始終 `1`；對艦隊清單和版本漂移檢測有用 |
| `claude_code_self_hosted_runner_capacity` | 配置的 `--capacity` |
| `claude_code_self_hosted_runner_active_sessions` | 目前執行的工作階段 |
| `claude_code_self_hosted_runner_locked_account{email}` | 一旦執行器鎖定到使用者並發出攜帶 `act.email` 聲稱的工作階段權杖，就會出現。該序列在鎖定到 Claude Tag 代理的執行器上不存在，其工作階段權杖不攜帶 `act.email`。標籤值是帳戶電子郵件；如果您的指標存放區可廣泛讀取，在抓取時放棄或雜湊標籤，例如使用 Prometheus `metric_relabel_configs`。 |
| `claude_code_self_hosted_runner_last_poll_age_seconds` | 自上次成功輪詢以來的秒數。如果超過 60，則發出警報。 |
| `claude_code_self_hosted_runner_poll_errors_total{error_kind}` | 按類型累積 PollWork 失敗：`transport`、`timeout`、`5xx`、`429` 或 `4xx`。所有五個序列都從程序啟動開始存在；在 `rate(...[5m]) > 0` 時發出警報。 |
| `claude_code_self_hosted_runner_sessions_started_total{client_platform}` | 在執行器的生命週期內產生的工作階段子程序，每個工作階段來源一個序列，例如 `web_claude_ai`、`ios`、`android`、`desktop_app` 或 `claude_code_cli`，或當伺服器未傳送時 `unknown`。Slack 工作階段根據哪個 Slack 整合建立它們而攜帶 `claude_in_slack` 或 `claude-in-slack`，因此使用正規表達式選擇器（例如 `{client_platform=~"claude[-_]in[-_]slack"}` 匹配兩者。使用 `sum()` 表示艦隊總計。 |
| `claude_code_self_hosted_runner_sessions_completed_total{client_platform}` | 乾淨結束的工作階段，標籤方式相同。比普通乾淨退出更廣泛：請參閱[工作階段生命週期計數器語義](#session-lifecycle-counter-semantics)以了解計數的內容。 |
| `claude_code_self_hosted_runner_sessions_failed_total{client_platform}` | 以失敗結束的工作階段，標籤方式相同。相同的警告：請參閱[工作階段生命週期計數器語義](#session-lifecycle-counter-semantics)。 |
| `claude_code_self_hosted_runner_sessions_interrupted_total{client_platform}` | 執行器因操作原因而不是工作階段結果終止的工作階段，標籤方式相同。請參閱[工作階段生命週期計數器語義](#session-lifecycle-counter-semantics)。 |
| `claude_code_self_hosted_runner_initializing_sessions` | 目前處於初始化階段的工作階段，從指派到子程序的初始化事件 |
| `claude_code_self_hosted_runner_session_init_duration_seconds` | 工作階段初始化持續時間的直方圖 |
| `claude_code_self_hosted_runner_session_init_errors_total` | 在達到初始化前失敗的工作階段：簽出掛鉤失敗、git 準備、權杖問題或初始化前子程序崩潰 |
| `claude_code_self_hosted_runner_session_start_hook_errors_total` | 報告錯誤結果的 `SessionStart` 掛鉤，每個失敗的掛鉤執行一個 |
| `claude_code_self_hosted_runner_session_idle_seconds{session_id,client_platform}` | 每個工作階段的工作階段閒置以來秒數的量表。對於終止卡在未回答權限提示上的工作階段很有用。 |

協調器在與其 `/healthz` 相同的連接埠上的 `GET /metrics` 上提供自己的序列：

| 序列 | 備註 |
| :- | :- |
| `claude_code_self_hosted_orchestrator_info{version,pool_id,orchestrator_uuid,hostname}` | 始終 `1` |
| `claude_code_self_hosted_orchestrator_connected` | 當最近輪詢成功時為 `1`；在任何失敗輪詢後下降到 `0`，無論失敗類型如何 |
| `claude_code_self_hosted_orchestrator_last_poll_age_seconds` | 自上次輪詢嘗試以來的秒數，成功或失敗，與執行器的同名指標不同，後者測量自上次成功以來；與 `connected` 配對以捕獲失敗的輪詢。協調器的輪詢迴圈等待掛鉤執行，因此在 `--hook-timeout` 加邊距（預設值約 90 秒）上方發出警報，而不是平面 60。 |
| `claude_code_self_hosted_orchestrator_poll_errors_total{error_kind}` | 按類型累積 PollSpawnHints 失敗：`transport`、`timeout`、`5xx`、`429` 或 `4xx`。所有五個序列都從程序啟動開始存在；在 `rate(...[5m]) > 0` 時發出警報。 |
| `claude_code_self_hosted_orchestrator_queue_pending_sessions` | 現在可聲稱的產生請求 |
| `claude_code_self_hosted_orchestrator_queue_backing_off_sessions` | 在可重試掛鉤失敗後退避重試的產生請求 |
| `claude_code_self_hosted_orchestrator_queue_circuit_broken_sessions` | 被阻止產生的工作階段。每個工作階段會持續被阻止，直到使用者傳送新訊息給它，或擁有者從環境的**活動**標籤重試它。修正原因後，計數可能仍維持在零以上。如果高於零則發出警報。 |
| `claude_code_self_hosted_orchestrator_pool_pending_sessions` | 等待此環境中執行器的總工作階段。環境範圍的聚合，在每個協調器實例上相同：在實例之間使用 `MAX` 而不是 `SUM`。 |
| `claude_code_self_hosted_orchestrator_pool_active_sessions` | 目前指派給此環境中活著執行器的工作階段。環境範圍的聚合，在每個協調器實例上相同：在實例之間使用 `MAX` 而不是 `SUM`。 |
| `claude_code_self_hosted_orchestrator_spawn_hooks_total{result}` | 累積 `spawn-runner` 掛鉤結果：`ok`、`retryable`、`non_retryable`。計數協調器掛鉤呼叫，而不是執行器產生的工作階段子程序：不可與 `sessions_started_total` 比較，因為容量高於 1、暖池和為同一工作階段再次產生的執行器都使兩者分歧。 |
| `claude_code_self_hosted_orchestrator_spawn_hook_duration_seconds` | 掛鉤持續時間的直方圖 |
| `claude_code_self_hosted_orchestrator_warm_hints_dispatched_total` | 自程序啟動以來分派的待命產生請求 |
| `claude_code_self_hosted_orchestrator_session_queue_wait_seconds` | 每個工作階段在佇列中等待的秒數的直方圖，然後協調器聲稱它進行產生，從控制平面與每個工作階段的產生請求一起傳送的佇列等待時間戳記記錄。用於 p50/p99 佇列時間警報。預熱產生不被取樣。 |
| `claude_code_self_hosted_orchestrator_clock_skew_seconds` | 本地減去伺服器時鐘偏差；診斷，一旦測量就存在 |
| `claude_code_self_hosted_orchestrator_scm_connector_connected` | 當 [SCM 連接器](#scm-connector-flags) 的 WebSocket 開啟時為 `1`；在撥號或退避時為 `0`。當未設定 `--scm-connector-host` 時不存在。 |
| `claude_code_self_hosted_orchestrator_scm_connector_requests_forwarded_total` | 自程序啟動以來代理到配置的 SCM 主機的累積 HTTP 請求。當未設定 `--scm-connector-host` 時不存在。 |

對於自動擴展，選擇與您的擴展風格相符的序列並在其進入擴展器之前閘它：

* **佇列深度擴展**：將 `claude_code_self_hosted_orchestrator_pool_pending_sessions` 饋送到您的 HPA 或 KEDA 擴展器，而不是 `queue_pending_sessions`。
* **容量擴展**：根據執行器的 `active_sessions` 與 `capacity` 的比率進行擴展。
* **在 `connected` 上閘**：使用 `claude_code_self_hosted_orchestrator_connected == 1` 每個實例過濾查詢，以便斷開連線副本的陳舊值不會饋送擴展器。

在完整輪詢中斷期間，每個副本都斷開連線，閘查詢返回無資料。HPA 在缺少指標時保持當前副本計數，但 KEDA 的 Prometheus 擴展器在其預設 `ignoreNullValues: "true"` 將空結果讀取為零並縮小；在 ScaledObject 上設定 `ignoreNullValues: "false"`，可選擇使用 `fallback` 副本下限。

以下 Prometheus Operator `PodMonitor` 涵蓋兩個程序。它通過 `app.kubernetes.io/part-of: claude-code-self-hosted-runner` 標籤和 [Kubernetes 配方](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#kubernetes)設定的命名 `health` 連接埠選擇 Pod；調整命名空間以符合您的部署：

```yaml theme={null}
# Claude Code 自託管執行器 + 協調器的範例 Prometheus Operator PodMonitor。
# 調整命名空間和標籤選擇器以符合您的部署。執行器和協調器都在其
# --health-port（預設 8080）上提供 /metrics。
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: claude-code-self-hosted-runner
  namespace: monitoring
spec:
  namespaceSelector:
    matchNames:
      - claude-runners
  selector:
    matchExpressions:
      # 符合 Kubernetes 配方中的執行器部署，加上任何
      # 按相同方式標籤的按需執行器工作和協調器 Pod
      # 並給予命名的 'health' containerPort。
      - key: app.kubernetes.io/part-of
        operator: In
        values: [claude-code-self-hosted-runner]
  podMetricsEndpoints:
    - port: health
      path: /metrics
      interval: 30s
```

### 範例警報規則

這些範例警報規則是起點；為您的艦隊大小調整閾值：

```yaml theme={null}
# Claude Code 自託管執行器 + 協調器的範例 Prometheus 警報規則。
# 為您的艦隊大小和 SLO 調整閾值。
groups:
  - name: claude-code-self-hosted-runner
    rules:
      - alert: ClaudeRunnerPollStale
        expr: claude_code_self_hosted_runner_last_poll_age_seconds > 60
        for: 2m
        labels: {severity: warning}
        annotations:
          summary: "執行器 {{ $labels.pod }} 已超過 60 秒未輪詢"
      - alert: ClaudeRunnerVersionDrift
        expr: count(count by (version) (claude_code_self_hosted_runner_info)) > 1
        for: 30m
        labels: {severity: info}
        annotations:
          summary: "執行器執行混合版本"
      - alert: ClaudeRunnerInitErrorsHigh
        expr: sum by (namespace) (increase(claude_code_self_hosted_runner_session_init_errors_total[10m])) > 3
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "工作階段在初始化前失敗（簽出 hook / git / 權杖 / 初始化前崩潰）"
      - alert: ClaudeRunnerPollErrors
        expr: sum by (pod) (rate(claude_code_self_hosted_runner_poll_errors_total[5m])) > 0
        for: 2m
        labels: {severity: warning}
        annotations:
          summary: "執行器 {{ $labels.pod }}：PollWork 失敗（5 分鐘內 {{ $value | humanize }}/s）"
      - alert: ClaudeRunnerSessionStartHookErrors
        expr: sum by (namespace) (increase(claude_code_self_hosted_runner_session_start_hook_errors_total[10m])) > 3
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "SessionStart hook 持續失敗"

  - name: claude-code-self-hosted-orchestrator
    rules:
      - alert: ClaudeOrchestratorDisconnected
        expr: claude_code_self_hosted_orchestrator_connected == 0
        for: 2m
        labels: {severity: critical}
        annotations:
          summary: "協調器 {{ $labels.pod }} 無法到達 Anthropic 控制平面"
      - alert: ClaudeOrchestratorPollStale
        expr: claude_code_self_hosted_orchestrator_last_poll_age_seconds > 90
        for: 2m
        labels: {severity: warning}
        annotations:
          summary: "協調器 {{ $labels.pod }} 已超過 90 秒未輪詢（輪詢迴圈等待 hook 執行）"
      - alert: ClaudeOrchestratorCircuitBroken
        expr: max by (namespace) (claude_code_self_hosted_orchestrator_queue_circuit_broken_sessions and on (instance) max_over_time(claude_code_self_hosted_orchestrator_connected[2m]) == 1) > 0
        for: 1m
        labels: {severity: critical}
        annotations:
          summary: "被阻止產生的工作階段：{{ $value }}。在活動標籤中閱讀每個工作階段的錯誤，修正原因，然後選取重試"
      - alert: ClaudeOrchestratorPollErrors
        expr: sum by (pod) (rate(claude_code_self_hosted_orchestrator_poll_errors_total[5m])) > 0
        for: 2m
        labels: {severity: warning}
        annotations:
          summary: "協調器 {{ $labels.pod }}：PollSpawnHints 失敗（5 分鐘內 {{ $value | humanize }}/s）"
      - alert: ClaudeOrchestratorSpawnHookFailing
        expr: sum by (pod) (increase(claude_code_self_hosted_orchestrator_spawn_hooks_total{result!="ok"}[5m])) > 3
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "協調器 {{ $labels.pod }}：5 分鐘內 >3 個 spawn-runner hook 失敗"
```

### 針對遺失的執行器與等待中的工作階段發出警報

若要在執行器遺失、工作階段等待或協調器停止運作時收到警報，請在[範例警報規則](#sample-alert-rules)之外一併載入這些 Prometheus 警報規則：

* **[固定艦隊](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#scale-the-fleet)**：`ClaudeRunnersBelowFloor`
* **[按需執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)**：`ClaudeOrchestratorSessionsWaiting`、`ClaudeOrchestratorQueueWaitHigh` 和 `ClaudeOrchestratorAbsent`

#### 固定艦隊遺失執行器時發出警報

`ClaudeRunnersBelowFloor` 會在剩餘的已註冊且已抓取執行器數量低於下限並持續 10 分鐘時觸發：

```yaml theme={null}
groups:
  # 僅限固定艦隊。使用按需執行器時，數量會隨需求變動，
  # 因此 ClaudeRunnersBelowFloor 會在需求低時觸發。
  - name: claude-code-self-hosted-fixed-fleet-capacity
    rules:
      - alert: ClaudeRunnersBelowFloor
        expr: (count(claude_code_self_hosted_runner_info{namespace="claude-runners"}) or vector(0)) < 2
        for: 10m
        labels: {severity: critical, namespace: claude-runners}
        annotations:
          summary: "已註冊且已抓取的執行器：{{ $value }}，低於下限。請先檢查執行器工作負載，若全部都在執行，再檢查抓取目標。"
```

* **下限**：將 `expr` 中的 `2` 設為約為副本數的一半，並無條件進位。有三個副本時保留 `2`，當只剩一個執行器或沒有執行器時，警報就會觸發。
* **命名空間**：取代 matcher 中和 `labels` 中的 `claude-runners`，並為每個額外的命名空間複製此警報。如果您的目標沒有 `namespace` 標籤，請移除 matcher 和該標籤，否則警報會讀取到 0 並觸發。
* **`ClaudeRunnerPollStale` 和 `ClaudeRunnerPollErrors`**：請保持從[範例警報規則](#sample-alert-rules)載入它們，因為 `ClaudeRunnersBelowFloor` 仍會計入無法輪詢的執行器

#### 工作階段等待按需執行器時發出警報

`ClaudeOrchestratorSessionsWaiting` 會在等待執行器的工作階段數量持續高於 0 達 10 分鐘時觸發。`ClaudeOrchestratorQueueWaitHigh` 會在過去 10 分鐘內超過 1% 的佇列等待超過 160 秒，且此情況持續 5 分鐘時觸發：

```yaml theme={null}
groups:
  # 僅限按需執行器。不需要針對命名空間進行編輯。
  - name: claude-code-self-hosted-on-demand-capacity
    rules:
      - alert: ClaudeOrchestratorSessionsWaiting
        expr: |
          max by (namespace) (
            claude_code_self_hosted_orchestrator_pool_pending_sessions
            and on (instance)
            max_over_time(claude_code_self_hosted_orchestrator_connected[2m]) == 1
          ) > 0
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: "等待執行器的工作階段：{{ $value }}，已高於閾值達 10 分鐘。請依結果檢查 claude_code_self_hosted_orchestrator_spawn_hooks_total，然後檢查未啟動的執行器工作負載。"
      - alert: ClaudeOrchestratorQueueWaitHigh
        expr: |
          histogram_quantile(0.99, sum by (namespace, le) (
            rate(claude_code_self_hosted_orchestrator_session_queue_wait_seconds_bucket[10m])
          )) > 160
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "過去 10 分鐘內超過 1% 的佇列等待超過 160 秒。請檢查 ClaudeOrchestratorDisconnected 是否正在觸發，然後依結果檢查 claude_code_self_hosted_orchestrator_spawn_hooks_total 以及 claude_code_self_hosted_orchestrator_spawn_hook_duration_seconds。"
```

* **閾值**：如果總是有某個工作階段在等待，請將 `ClaudeOrchestratorSessionsWaiting` 中的 `> 0` 提高到高於您通常看到的數字
* **`ClaudeOrchestratorDisconnected`**：請保持從[範例警報規則](#sample-alert-rules)載入它，因為 `ClaudeOrchestratorSessionsWaiting` 會在命名空間中最後一個協調器斷開連線約 2 分鐘後停止觸發

#### 協調器停止運作時發出警報

若要得知[協調器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)本身已停止運作，請載入 `ClaudeOrchestratorAbsent`。當命名空間中沒有任何協調器被抓取達 5 分鐘時，它就會觸發：

```yaml theme={null}
groups:
  # 僅限按需執行器。請將 claude-runners 取代為協調器的命名空間。
  - name: claude-code-self-hosted-on-demand-orchestrator
    rules:
      - alert: ClaudeOrchestratorAbsent
        expr: absent(claude_code_self_hosted_orchestrator_connected{namespace="claude-runners"})
        for: 5m
        labels: {severity: critical}
        annotations:
          summary: "已有 5 分鐘沒有抓取到任何協調器。如果它已停止運作，就不會啟動任何按需執行器，工作階段會持續等待。請先檢查協調器工作負載，若它正在執行，再檢查其抓取目標。"
```

* **命名空間**：將 `claude-runners` 取代為協調器的命名空間，並為每個執行協調器的額外命名空間複製此警報。如果您的目標沒有 `namespace` 標籤，請移除 matcher，否則警報會在 5 分鐘後觸發並持續維持。
* **未抓取協調器的 Prometheus 伺服器**：請勿將此警報放入其規則檔，因為在這類伺服器上，它會在 5 分鐘後觸發並持續維持
* **不要依賴協調器的其他警報**：它們讀取的是協調器本身提供的指標。`ClaudeOrchestratorSessionsWaiting`、`ClaudeOrchestratorQueueWaitHigh` 以及協調器的[範例警報規則](#sample-alert-rules)，都會在協調器停止運作後約 10 分鐘內停止觸發。

### 傳遞工作階段子程序指標

每個工作階段在其自己的子程序中執行，具有自己的 OpenTelemetry 指標；在 `--capacity` 高於 1 時，執行器重寫這些子程序指標的公開方式。在執行器主機上設定 `OTEL_METRICS_EXPORTER=prometheus` 並在工作階段的環境中設定 `CLAUDE_CODE_ENABLE_TELEMETRY=1`（例如從您的[包裝指令碼](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#wrapper-scripts)或執行器自己的環境，工作階段繼承），重新公開每個子程序的計數器和量表工具在執行器自己的 `/metrics` 端點上，與執行器的序列一起。執行器將子程序的匯出器重寫為通過 OTLP 推送到健康連接埠上的僅環回接收器，使用 `session_id` 和 `client_platform` 標籤標記每個序列，並在該工作階段結束時驅逐工作階段的序列。直方圖不傳遞，子程序指標的名稱會與執行器自己的前綴衝突被放棄。

在預設 `--capacity 1` 時，重寫不適用：工作階段的子程序如常在連接埠 9464 上綁定自己的 Prometheus 端點。

#### 將工作階段的指標與執行器的指標聯結

若要查看閒置工作階段的成本，請依 `ccr_session_id` 將執行器的 `claude_code_self_hosted_runner_session_idle_seconds` 與 Claude Code 的成本指標聯結。執行器的指標不帶有該標籤，因此請使用 `label_replace` 為其加上該標籤，如以下查詢所示：

```text theme={null}
sum by (ccr_session_id) (claude_code_cost_usage_total)
and on (ccr_session_id)
label_replace(
  claude_code_self_hosted_runner_session_idle_seconds > 600,
  "ccr_session_id", "cse_$1", "session_id", "session_(.*)"
)
```

此查詢會為每個閒置超過十分鐘的工作階段傳回一個結果：其 Claude Code 程序到目前為止計算的成本（以美元計）。若要聯結其他 Claude Code 指標，請取代查詢中的 `claude_code_cost_usage_total`。此查詢在任何 `--capacity` 下皆可運作。

* **`session_id`**：在連接埠 9464 上，Claude Code 指標上的該標籤包含 Claude Code 自己的 [`session.id`](https://code.claude.com/docs/zh-TW/monitoring-usage#standard-attributes)，不符合任何執行器序列。依此標籤聯結不會傳回任何結果，因此請依 `ccr_session_id` 聯結。
* **Claude Code 指標沒有 `ccr_session_id`**：請確認 [`OTEL_METRICS_INCLUDE_SESSION_ID`](https://code.claude.com/docs/zh-TW/monitoring-usage#metrics-cardinality-control) 未設定為 `false`

### 工作階段生命週期計數器語義

`sessions_started_total`、`sessions_completed_total`、`sessions_failed_total` 和 `sessions_interrupted_total` 計數器按工作階段如何結束對其進行分類。每個產生的工作階段子程序在產生時增加 `sessions_started_total`，並在退出時恰好增加其他三個中的一個，因此 `sessions_started_total` 減去其他三個的總和等於目前執行的工作階段子程序數。

* `completed`：工作階段乾淨結束。這涵蓋子程序以代碼 `0` 自行退出、工作階段在子程序仍連線時被存檔或刪除，以及執行器乾淨地交回槽：在閒置逾時、退休時間或 `--kill-session-after-min` 限制時釋放工作階段；啟動逾時；或輪詢迴圈在子程序退出前注意到的伺服器端取消指派。增加 `sessions_completed_total`。
* `failed`：子程序以非零代碼自行退出，要麼是崩潰，要麼是產生後的設定失敗。增加 `sessions_failed_total`。
* `interrupted`：執行器因既不是工作階段成功也不是執行器故障的操作原因終止子程序，例如排空，或終止在 [`SELF_HOSTED_RUNNER_MAX_LIFETIME_GRACE_MS`](#environment-variable-only-settings) 寬限期結束後其 `--kill-session-after-min` 限制仍在執行器上的工作階段。Kubernetes 滾動重新啟動傳送 `SIGTERM` 是排空的一個範例。增加 `sessions_interrupted_total`。

在 v2.1.260 之前，執行器終止達到其 `--kill-session-after-min` 限制的每個工作階段並在 `sessions_interrupted_total` 中計數。

[`post-session` hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session)的 `CLAUDE_RUNNER_EXIT_REASON` 以不同方式分類乾淨交接。hook 將這些情況報告為 `interrupted`，因為執行器停止了子程序：釋放、啟動逾時、伺服器取消指派，以及輪詢先注意到的存檔或刪除。這些計數器記錄與 `completed` 相同的事件，因為槽被乾淨地交回。

如果您直接根據 `sessions_completed_total` 協調掛鉤收據，您會低估完成。使用掛鉤以獲得每個工作階段的保證，並使用計數器以獲得聚合速率。

在一次性環境上，`--capacity 1` 與預設 `--drain-grace-sec 0`，每個執行器程序在其一個工作階段結束後片刻退出。`sessions_completed_total`、`sessions_failed_total` 和 `sessions_interrupted_total` 僅在工作階段結束時增加，就在該退出之前，因此每 15 到 60 秒進行一次 Prometheus 抓取很少在執行器的序列消失前捕獲增加；這三個工作階段結束計數器是本部分其餘部分所指的終端計數器。`sessions_started_total` 在產生時增加並在工作階段的生命週期內保持可見，因此它可靠地顯示，但在一次性環境上它讀取更接近「目前執行的工作階段」而不是累積計數。

改為使用此表中的序列以達到相應的目標，而不是終端計數器：

| 目標 | 使用 |
| :- | :- |
| 吞吐量 | `claude_code_self_hosted_orchestrator_spawn_hooks_total{result="ok"}`，長期協調器上的計數器，每個成功的 `spawn-runner` 掛鉤增加一次並在 `rate()` 下保持有意義。它計數掛鉤呼叫而不是工作階段，因此預熱和為同一工作階段重複產生使其與工作階段計數分歧。 |
| 利用率 | `sum(claude_code_self_hosted_runner_active_sessions)` 對 `sum(claude_code_self_hosted_runner_capacity)`，兩個量表在每次抓取時有效，無論執行器生命週期如何 |
| 待辦項 | `claude_code_self_hosted_orchestrator_pool_pending_sessions` 用於佇列深度，以及 `claude_code_self_hosted_orchestrator_queue_circuit_broken_sessions`，如果高於零則發出警報 |
| 失敗 | `claude_code_self_hosted_runner_sessions_failed_total`，盡力而為：產生後的真實崩潰確實增加它，`rate()` 在執行器上有意義，這些執行器以 `--drain-grace-sec` 高於 `0` 的方式超越其工作階段。一次性環境與其他終端計數器具有相同的抓取視窗問題，因此將您看到的任何非零值視為值得調查。產生前的失敗，例如簽出掛鉤失敗、git 準備或權杖問題，僅出現在 `session_init_errors_total` 中。 |

`orchestrator_*` 列僅存在於執行[按需協調器](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#on-demand-runners)的環境上。在固定艦隊上，其執行器以 `--drain-grace-sec` 高於 `0` 的方式超越其工作階段，使用 `sum(rate(claude_code_self_hosted_runner_sessions_started_total[5m]))` 表示吞吐量；在一次性艦隊上，該序列與終端計數器具有相同的抓取視窗問題，因此改為依賴佇列工作階段計數。在環境的**活動**標籤上檢查待辦項，在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上：執行器不匯出佇列深度序列。

對於每個工作階段結果報告，改為使用 [`post-session` 掛鉤](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration#post-session)：它在每個工作階段結束時觸發，其中產生了子程序，除了突然執行器終止（例如 VM 搶佔），根據[掛鉤自己的合約](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#post-session)。

## 下一步

* [自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)：環境、執行器和工作階段模型；[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)和[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)保持設定和操作
* [自訂工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md)：包裝指令碼、生命週期掛鉤和按需執行器
* [驗證工作階段身份](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)：工作階段權杖、其聲稱以及如何驗證它
