<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration | lastmod: 2026-11-03 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Environments｜EN 摘要：Customize self-hosted environment sessions with wrapper scripts for per-session credentials, lifecycle hooks, and on-demand runner spawning.

# 在自託管環境中自訂工作階段

> 使用包裝指令碼在自託管環境工作階段中自訂每個工作階段的憑證、生命週期 hook 和按需執行器生成。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[擁有者](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)可以在[**雲端環境**管理頁面](https://claude.ai/admin-settings/cloud-environments)上開啟**允許自託管環境**來啟用它們。本頁面假設您已有一個可運作的執行器；請參閱[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)以了解設定，以及[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)以了解艦隊配方。

[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)在您自己的基礎設施上執行 Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，由您部署的執行器程序執行。在沒有設定的情況下，該執行器會複製工作階段的儲存庫、生成 Claude Code，然後進行清理。本頁面適用於操作執行器的平台工程師：它涵蓋了當預設值不適用時的擴展點，從每個工作階段的憑證佈建到完全替換簽出。包裝指令碼和 hook 在執行器主機上作為可執行檔案執行，該主機是 Linux 或 macOS，本頁面上的範例假設使用 POSIX shell。

本頁面上的一些 hook 環境變數仍然使用 `pool`，例如 `CLAUDE_RUNNER_POOL_ID`；CLI 旗標和環境變數名稱使用 `environment`，例如 `--environment-secret-file`。

## 包裝指令碼

當每個工作階段需要執行器無法自行完成的設定時，請使用包裝指令碼：

* 佈建限定於工作階段建立者的短期憑證
* 匯出環境特定的祕密
* 準備語言工具鏈
* 在子程序周圍套用資源限制

執行器每次啟動工作階段時（包括工作階段恢復或重新排入佇列時），都會啟動您的包裝指令碼，以取代 Claude Code 二進位檔案。透過 `exec` 進入 `$CLAUDE_RUNNER_CLAUDE_BIN`（執行器自己的二進位檔案）來結束包裝指令碼，以便訊號和退出碼正確傳播。

在啟動執行器時，將 `--exec-path` 或 `SELF_HOSTED_RUNNER_EXEC_PATH` 指向包裝指令碼，並依[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-manually)所述替換 `<writable-dir>`：

```bash theme={null}
claude self-hosted-runner --environment-secret-file /etc/claude/environment-secret --base-dir '<writable-dir>' --exec-path /etc/claude/session-wrapper.sh
```

執行器在包裝指令碼的環境中設定以下內容：

| 變數 | 說明 |
| :- | :- |
| `CLAUDE_CODE_SESSION_ACCESS_TOKEN` | 工作階段 JWT，前綴為 `sk-ant-cc-`。其 `act` 聲明識別工作階段建立者，並在建立的使用介面有記錄時包含建立者的電子郵件。該值是生成時的 token；重新整理會透過子程序的 stdin 到達，因此包裝指令碼只會看到初始值。請參閱[驗證工作階段身分](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)。 |
| `CCR_SESSION_ACCOUNT_EMAIL` | 工作階段建立者的電子郵件，由執行器從 token 的 `act.email` 聲明中預先提取，未經簽章驗證。適合用於標籤，例如提交尾註。當電子郵件限制憑證發行時，請改為驗證 token 並從中讀取聲明。請參閱[佈建限定於工作階段建立者的憑證](#provision-credentials-scoped-to-the-session-creator)。當 token 不包含建立者電子郵件時未設定，例如由您組織的服務身分建立的工作階段。請視為個人可識別資訊。 |
| `CLAUDE_RUNNER_CLIENT_PLATFORM` | 建立工作階段的用戶端使用介面，例如 `web_claude_ai`、`desktop_app`、`ios`、`claude_code_cli` 或 `scheduled_trigger`。Anthropic 在工作階段建立時記錄該值一次，因此包裝指令碼和每個生命週期 hook 都會看到相同的值。僅將其用於採用分析和標籤，不要用作授權訊號。當工作階段沒有已記錄或可識別的使用介面時未設定。需要 Claude Code v2.1.229 或更新版本。 |
| `CLAUDE_RUNNER_CLAUDE_BIN` | 執行器自己的 Claude Code 二進位檔案的絕對路徑。以 `exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@"` 結束您的包裝指令碼，以移交給固定的二進位檔案，而無需硬編碼安裝路徑。 |
| `CLAUDE_CODE_REMOTE_SESSION_ID` | 標記形式為 `cse_...` 的工作階段 ID。這與[生命週期 hook](#lifecycle-hooks) 以 `CLAUDE_RUNNER_SESSION_ID`（`session_...` 形式）看到的是相同工作階段；UUID 變數在兩者之間相符，將 `cse_` 前綴替換為 `session_` 會產生工作階段 URL 中顯示的 ID。 |
| `CLAUDE_CODE_REMOTE_SESSION_UUID` | 標準 UUID 形式的相同工作階段 ID，適用於以 UUID 為鍵的系統。 |
| `CLAUDE_CODE_REMOTE_SLACK_THREAD_URL` | 對於屬於某個 Slack 討論串的 [Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段，為該討論串的連結。其他工作階段不會設定此變數，討論串工作階段也可能未設定。 |
| `CLAUDE_CODE_REMOTE_SLACK_THREAD_TS` | 對於屬於某個 Slack 討論串的 Claude Tag 工作階段，為該討論串的 Slack 時間戳記，例如 `1700000000.000100`。可能未設定，且可能在 `CLAUDE_CODE_REMOTE_SLACK_THREAD_URL` 未設定時已設定，因此請分別檢查每個變數。 |
| `CLAUDE_CODE_REMOTE_SLACK_CHANNEL_ID` | 對於 Claude Tag 工作階段，為該工作階段所服務或其討論串所在之 Slack 頻道或私訊的 ID，例如 `C0123ABCDE`。Slack 時間戳記是在單一頻道內識別訊息，因此請將此 ID 與 `CLAUDE_CODE_REMOTE_SLACK_THREAD_TS` 一併記錄。其他工作階段不會設定此變數，Claude Tag 工作階段也可能未設定。 |
| `CLAUDE_SESSION_INGRESS_TOKEN_FILE` | 保存目前工作階段 JWT 的每個工作階段檔案的絕對路徑，在 token 重新整理時保持最新。Shell 子程序在下載使用者新增到工作階段的附件時從中讀取其 `Authorization` 標頭。`exec` 會自動保留該變數；重建子程序環境的包裝指令碼必須帶上該變數，否則附件下載會無聲地停止運作。 |
| `CLAUDE_CONFIG_DIR` | 每個工作階段的 Claude 設定目錄，在工作階段開始時從執行器在啟動時擷取的執行器主機設定快照中寫入；請參閱[權限和工具核准](#permissions-and-tool-approval)。此處的寫入隔離於此工作階段。工作階段結束後，該目錄會保留在 `<base-dir>/_sessions/` 下，除非您使用 [`--remove-session-state`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 啟動執行器；請參閱[重複使用預先準備的簽出](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#reuse-a-pre-warmed-checkout)。 |
| `CLAUDE_CODE_REMOTE_MCP_CONFIG` | `CLAUDE_CONFIG_DIR` 中某個檔案的路徑，該檔案保存 Anthropic 控制平面為此工作階段傳遞的 MCP 伺服器定義。如果您的包裝指令碼會重建子程序的環境，請帶上此變數。若缺少此變數，當控制平面更新所傳遞的伺服器時，子程序會關閉您的包裝指令碼以 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 新增、但不在該更新中的任何 stdio、HTTP 或 SSE 伺服器。需要 Claude Code v2.1.299 或更新版本。 |
| `ANTHROPIC_BASE_URL` | 子程序將使用的 API 基礎 URL，由控制平面按工作階段傳遞，通常為 `https://api.anthropic.com`。不要覆寫它：工作階段的推理憑證是 Anthropic 發行的 OAuth token，其他提供者不接受。 |
| `CLAUDE_CODE_OAUTH_TOKEN` | 子程序用於模型推理的短期 OAuth 存取 token，生命週期約為 30 分鐘。執行器在過期前重新鑄造它，並透過子程序的 stdin 傳遞輪換，因此未[保持 stdin 連接](#keep-stdin-and-file-descriptor-3-attached)的包裝指令碼只會看到初始值。不要依賴您組織的 IP 允許清單來限制此 token 的使用：請將其視為持有人憑證，如果洩露，大約 30 分鐘內仍可使用，不要將其寫入日誌、寫入磁碟或在工作階段容器外轉發它。 |
| `CLAUDE_RUNNER_ALIVE_EVERY_MS` | 執行器設定當[回合在子程序初始化之前開始](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#session-startup-timeout)時，子程序回報其仍存活的頻率（以毫秒為單位）。如果您的包裝指令碼會重建子程序的環境，請帶上此變數，否則執行器可能會在該回合期間釋放工作階段，並記錄 `no child output for <n> — releasing`。執行器和子程序都需要 v2.1.309 或更新版本。 |

包裝指令碼也會繼承子程序的其餘受管環境，包括任何伺服器提供的環境變數。`exec` 會自動傳播所有內容；如果您的包裝指令碼以另一種方式生成子程序，請轉發完整環境。

您可以在包裝指令碼或 [`command` hook](#command) 中，以及在工作階段執行的內容（例如 shell 命令、git hook 和 Claude Code hook）中讀取 `CLAUDE_CODE_REMOTE_SLACK_*` 變數。`checkout`、`post-session` 和 `spawn-runner` hook 不會收到它們。

### 為可能未設定的變數提供預設值

如果您的指令碼使用 `set -u`，請以預設值展開 `CCR_SESSION_ACCOUNT_EMAIL`、`CLAUDE_RUNNER_CLIENT_PLATFORM`、`CLAUDE_CODE_REMOTE_SLACK_THREAD_URL`、`CLAUDE_CODE_REMOTE_SLACK_THREAD_TS` 和 `CLAUDE_CODE_REMOTE_SLACK_CHANNEL_ID`，例如 `"${CCR_SESSION_ACCOUNT_EMAIL:-}"`。每個變數都可能未設定，而在 `set -u` 下，Bash 展開未設定的變數時會以 `unbound variable` 停止。

### 為指令碼展開的引數和變數加上引號

請為執行器傳遞給您的包裝指令碼或 [`command` hook](#command) 的每個引數和變數加上引號。有些值包含 shell 會處理的字元，因為它們保存的是 JSON、完整的句子，或是[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)，例如 `Bash(npm run test *)`。

* **引數**：以 `"$@"` 將它們傳遞下去
* **變數**：為每個變數加上引號，如 `"${CLAUDE_CODE_REMOTE_SLACK_THREAD_URL:-}"`。例如，Slack 討論串連結可能包含 `?` 和 `&`。
* **`eval` 和 `sh -c` 字串**：不要將值代入 `eval` 或 `sh -c` 執行的字串，即使在引號內也不行。請改為讓該字串參照變數。

### 保持 stdin 和檔案描述符 3 連接

子程序的 stdin 是執行器的控制通道。token 輪換和工作階段結束訊號會在其上到達。執行器也會在檔案描述符 3 上開啟一個管道，並從中讀取子程序的活動訊號以驅動閒置和啟動逾時。單純的 `exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@"` 會自動保留兩者。

如果您的包裝指令碼使用單獨的 `&` 在背景中執行子程序，它會切斷子程序的 stdin。工作階段看起來健康，直到初始 OAuth token 大約 30 分鐘的生命週期過期，然後每個使用該 token 的 API 呼叫都會失敗，並出現 `401 authentication_error`。如果您的包裝指令碼必須在背景中執行子程序，例如為了讓拆卸 trap 保持作用，請將 stdin 儲存在檔案描述符 9 上，並明確重新連接它：

```bash theme={null}
exec 9<&0   # the runner uses 3, and from v2.1.309 reserves 4 and 5
"$CLAUDE_RUNNER_CLAUDE_BIN" "$@" <&9 9<&- &
CHILD=$!
trap 'teardown' EXIT
wait "$CHILD"
```

您可以重新導向子程序的 stdout。請保持檔案描述符 3 和 stderr 連接到執行器：

* **檔案描述符 3**：將子程序的活動訊號傳送給執行器。不要在包裝指令碼中關閉或重複使用它。
* **檔案描述符 4 和 5**：Claude Code v2.1.309 或更新版本上的執行器會為子程序保留它們。不要在包裝指令碼中關閉或重複使用它們。如果您的包裝指令碼使用其中任一個，例如用於儲存 stdin，請將該用途移至 6 到 9 之間的描述符，較早的版本同樣不會佔用這些描述符。
* **stderr**：當包裝指令碼或子程序以非零狀態退出時，執行器會將 stderr 的最後幾行張貼到工作階段，並在自己的日誌中印出。工作階段的使用者會看到這些行，因此不要將祕密印到 stderr，並在部署包裝指令碼前移除 `set -x`。如果您重新導向 stderr，工作階段仍會執行，但執行器只會以退出碼回報失敗。

### 傳遞系統提示詞旗標

Anthropic 控制平面為工作階段傳送的系統提示詞和附加系統提示詞，會以檔案路徑而非內嵌文字的形式傳到您的包裝指令碼。執行器會將每個提示詞寫入工作階段設定目錄 `CLAUDE_CONFIG_DIR` 中的檔案，並在您的包裝指令碼接收的引數中傳遞其路徑，形式為 [`--system-prompt-file <path>` 或 `--append-system-prompt-file <path>`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags)。

Claude Code v2.1.281 或更新版本上的執行器會以檔案形式傳遞提示詞。在 v2.1.281 之前，執行器以 `--system-prompt <text>` 和 `--append-system-prompt <text>` 傳遞它們。

在您的包裝指令碼或 [`command` hook](#command) 中，請依下列方式處理這些旗標：

* **原樣傳遞它們**：以 `exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@"` 結束包裝指令碼，這會將檔案旗標連同其他所有引數一起轉發。不要捨棄或改寫它們。如果工作階段遺失了提示詞檔案旗標，它將在缺少控制平面為其傳送之指令的情況下執行。
* **在 v2.1.281 或更新版本的執行器上，您附加的檔案旗標會取代伺服器的旗標，而不會與其疊加**：每個提示詞檔案旗標只接受單一值，且 Claude Code 會保留最後一次出現的值，因此如果您在 `"$@"` 之後附加 `--append-system-prompt-file <path>`，您檔案的內容會取代伺服器的附加指令。若要在伺服器的指令之上新增指令，請將它們放入執行器映像的 `CLAUDE.md` 中，執行器會將其[植入每個工作階段的使用者層級設定](#how-each-session’s-config-is-assembled)。

#### 修正工作階段開始時的 `Argument list too long`

在 Linux 上，如果您將控制平面的提示詞與您自己的文字合併為單一 `--append-system-prompt` 引數，一旦該引數達到 128 KB，執行器就會記錄如下的一行：

```text theme={null}
Session <id> finished: failed — reason: child exited 126: /opt/wrapper.sh: line 9: /usr/local/bin/claude: Argument list too long
```

Linux 將每個單一引數限制為 32 個記憶體分頁，以常見的 4 KB 分頁計算即為 128 KB。`getconf ARG_MAX` 回報的數值（通常為 2 MB）是另一項限制，針對的是所有引數與環境的總和。

在 Claude Code v2.1.283 或更新版本上，請將檔案旗標保留在 `"$@"` 中，並僅將您自己的文字作為 `--append-system-prompt` 傳遞。Claude Code 會[同時使用兩者](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags)，先使用控制平面的提示詞，再使用您自己的文字：

```bash theme={null}
exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@" --append-system-prompt "$(cat /opt/team-instructions.md)"
```

在 Linux 上，如果您自己的文字達到 128 KB，請將其移至執行器映像的 `CLAUDE.md`，因為它仍然是單一引數。

在 v2.1.281 或 v2.1.282 上，該命令會以 `Cannot use both --append-system-prompt and --append-system-prompt-file` 退出。在更早的版本上，您的文字會在沒有任何錯誤的情況下取代控制平面的提示詞。在上述任一版本上，請先更新，或將您自己的文字移至 `CLAUDE.md`。

### 佈建限定於工作階段建立者的憑證

使用 `decode-token` 子命令從工作階段 JWT 讀取聲明。它依序從引數、`CLAUDE_CODE_SESSION_ACCESS_TOKEN` 或 stdin 讀取 token；請參閱[驗證工作階段內的 token](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md#verify-the-token-inside-the-session) 以了解它檢查的內容。下面的範例解碼建立者身分，將其交換為短期 AWS 憑證，並透過 exec 進入 Claude Code：

```bash theme={null}
#!/bin/bash
# Key on the stable Anthropic user ID and require a human creator.
CREATOR_SUB=$("$CLAUDE_RUNNER_CLAUDE_BIN" self-hosted-runner decode-token \
  | jq -re '.act.sub // "" | select(startswith("user:"))') \
  || { echo "decode-token: verification failed or no human creator" >&2; exit 1; }

creds=$(your-sts-helper assume-role --subject "$CREATOR_SUB") \
  || { echo "credential exchange failed" >&2; exit 1; }
eval "$creds"

exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@"
```

在提取的聲明限制授權決定時，使用 `jq -re` 而不是 `jq -r`，以便缺少的聲明以非零狀態退出，而不是將字面字串 `null` 傳遞到下游。由組織服務身分（例如機器人和 agent 工作階段）建立的工作階段帶有 `agent:` 主體而不是 `user:`，因此此範例會拒絕它們；如果您的環境服務這些工作階段，請明確決定包裝指令碼是否為它們回退到預設憑證，而不是退出。當您的憑證交換改為需要電子郵件時，請讀取 `.act.email` 並處理其缺失的情況：token 只在建立的使用介面有記錄時才帶有它，而 [CLI 分派的工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#run-the-test-loop)可能缺少它。有關完整的聲明參考以及從執行器外部服務進行的驗證，請參閱[驗證工作階段身分](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)。

## 生命週期掛鉤

生命週期掛鉤用您自己的指令碼替換執行器每個會話管道的階段。使用 `--hooks-dir <path>` 或 `SELF_HOSTED_RUNNER_HOOKS_DIR` 將執行器指向掛鉤目錄。執行器尋找具有眾所周知名稱的可執行檔案；任何不存在的掛鉤都會回退到內建行為，因此您只需編寫所需的掛鉤。掛鉤以執行器自己的權限執行，會話子程序共享該 UID，因此請將掛鉤目錄掛載為唯讀，或將其烘焙到映像中，以便會話代碼無法修改它；請參閱[強化部分](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)。

這些掛鉤不同於[Claude Code 掛鉤](https://code.claude.com/docs/zh-TW/hooks.md)，後者在會話內執行；生命週期掛鉤在執行器上執行，圍繞會話。

### checkout

每當執行器啟動工作階段時（包括工作階段恢復或重新排入佇列時），都會為每個儲存庫執行，取代執行器內建的複製與擷取。使用此 hook 從您透過 HTTPS 或 SSH 存取的直讀式鏡像複製、從封存檔植入工作樹，或套用每個工作階段的 git 身分驗證。

執行器會設定下列變數，也可能設定表格未列出的其他 `CLAUDE_RUNNER_` 變數：

| 變數 | 說明 |
| :- | :- |
| `CLAUDE_RUNNER_REPO_URL` | 要複製的儲存庫 URL，在應用任何 `--git-host-rewrite` 和 `--git-ssh-rewrite` 之後 |
| `CLAUDE_RUNNER_REPO_REF` | 要簽出的修訂版本，依工作階段的要求而定：分支、標籤、提交 SHA，或完整參照名稱，例如 `refs/heads/<branch>` 或 `refs/pull/<number>/head`。空值表示儲存庫的預設分支。 |
| `CLAUDE_RUNNER_CHECKOUT_PATH` | 工作樹必須留下的絕對路徑 |
| `CLAUDE_RUNNER_SESSION_ID` | 標記形式為 `session_...` 的會話 ID，用於記錄和相關性 |
| `CLAUDE_RUNNER_SESSION_UUID` | 規範 UUID 形式的相同會話 ID |
| `CLAUDE_RUNNER_API_BASE_URL` | 用於會話範圍呼叫的 Anthropic API 基礎 URL |
| `CLAUDE_RUNNER_CLIENT_PLATFORM` | 建立工作階段的用戶端使用介面，例如 `web_claude_ai`、`desktop_app` 或 `ios`。當工作階段沒有已記錄或可辨識的使用介面時不會設定，因此在 `set -u` 下請以 `"${CLAUDE_RUNNER_CLIENT_PLATFORM:-}"` 參照它。需要 Claude Code v2.1.229 或更新版本。 |
| `CLAUDE_CODE_SESSION_ACCESS_TOKEN` | 會話存取權杖，用於會話範圍的 API 呼叫 |
| `GIT_CONFIG_COUNT`、`GIT_CONFIG_KEY_n`、`GIT_CONFIG_VALUE_n` | 執行器為您的 hook 所執行之 git 固定的 Git 設定。[生命週期 hook 內的 Git 設定](#git-configuration-inside-lifecycle-hooks)說明了這些設定。需要 Claude Code v2.1.280 或更新版本。 |

指令碼必須在 `CLAUDE_RUNNER_CHECKOUT_PATH` 留下一個簽出於所要求修訂版本的工作樹。分離的 HEAD 也可以，因為執行器會在其上建立工作階段的工作分支。

在您的 hook 返回後，執行器會驗證 `CLAUDE_RUNNER_CHECKOUT_PATH` 包含 `.git`。如果您的 hook 具體化的是非 git 來源（例如 Perforce 或解開的 tarball），請在執行器的環境中設定 `CLAUDE_RUNNER_SKIP_GIT_VERIFY=1` 以略過該檢查。基於 Git 的流程（例如建立工作分支與推送結果）需要 git 簽出，因此請使用 [`post-session` hook](#post-session) 從非 git 樹匯出結果。

#### 在 hook 中取得 git 憑證

執行器不會將 git 憑證傳遞給 hook。`decode-token` 子命令在此也無法使用，因為 `CLAUDE_RUNNER_CLAUDE_BIN` 未在 checkout hook 環境中設定。請改為從工作階段的身分產生每個工作階段的複製憑證，或退而使用主機本身的 git 身分驗證：

* **每個工作階段的複製憑證**：依照[從您的服務驗證 token](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md#verify-the-token-from-your-service)所述，使用標準 JWT 函式庫，針對 `CLAUDE_RUNNER_API_BASE_URL` 下的 JWKS 端點驗證 `CLAUDE_CODE_SESSION_ACCESS_TOKEN`。接著讓您的憑證服務為 token 的 `act` 宣告中的身分核發短期複製憑證。請以 `act.sub` 作為該憑證的識別鍵，且不要要求 `act.email`。
* **主機 git 身分驗證**：使用主機已有的任何 git 身分驗證，例如 SSH agent、憑證輔助程式或 `.netrc`。

#### hook 失敗時

當 hook 以非零狀態結束，或以 0 結束卻未留下可用的簽出時，即視為 hook 失敗：

* **工作階段會推送結果的儲存庫**：執行器會使工作階段失敗，並在非零結束時將指令碼 stderr 的結尾部分呈現給使用者。請將原因以簡短的一行寫入 stderr，並放在最後輸出，然後以非零狀態結束。請勿將機密資訊輸出到 stderr，並在部署 hook 之前移除 `set -x`。

  如果 git 的 `couldn't find remote ref` 出現在 hook stderr 約最後 4 KB 內，執行器會改為回報分支已被刪除。此時工作階段的錯誤訊息會說明該分支已不存在於遠端，並請使用者將其還原。如果該分支確實存在，請參閱[工作階段因 `no longer exists on the remote` 或 `couldn't find remote ref` 而失敗](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#no-longer-exists-on-the-remote)。
* **工作階段只會讀取的儲存庫**，例如新增到執行中工作階段的儲存庫：執行器會略過它，並繼續處理其餘儲存庫。執行器會向工作階段發佈 `Skipped` 步驟，並移除 hook 在簽出路徑留下的任何內容。

  當 `Skipped` 步驟提及 checkout hook 時，請在執行器日誌中的 `[runner:warn] checkout hook failed` 這一行找到失敗詳細資訊。當該步驟指出某個來源參照 `no longer exists on remote` 時，請參閱[工作階段因 `no longer exists on the remote` 或 `couldn't find remote ref` 而失敗](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#no-longer-exists-on-the-remote)。如果略過後工作階段完全沒有任何儲存庫，執行器仍會使工作階段失敗。

當 hook 成功時，執行器會在工作階段結束後移除簽出路徑。

### post-session

在 Claude Code 子程序結束後、執行器拆除工作區之前執行。此 hook 是您保存未提交工作的唯一機會，因為未提交的已追蹤變更在以下任一路徑上都不會保留：

* **在 `--capacity` 高於 1 時**：執行器會在 hook 返回後立即刪除每個工作階段的 worktree
* **在 `--capacity 1` 時**：重複使用的[規範複製](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#reuse-a-pre-warmed-checkout)會在下一個工作階段開始時被硬重設

典型用途是推送未提交變更的快照分支、封存日誌，或向您自己的系統發出工作階段結束事件。

掛鉤在每個會話結束時觸發，其中生成了子程序，無論原因如何；下面的 `CLAUDE_RUNNER_EXIT_REASON` 值列舉了這些情況。當執行器突然終止時（例如 VM 搶佔或電源故障）無法觸發；如果您需要針對突然終止的保證，請改為使用 Claude Code `PostToolUse` 掛鉤從會話內定期快照。執行器設定：

| 變數 | 說明 |
| :- | :- |
| `CLAUDE_RUNNER_SESSION_ID` | 標記形式為 `session_...` 的會話 ID |
| `CLAUDE_RUNNER_SESSION_UUID` | 規範 UUID 形式的相同會話 ID |
| `CLAUDE_RUNNER_EXIT_REASON` | 會話如何結束；請參閱表格下方的值 |
| `CLAUDE_RUNNER_WORKSPACE_PATHS` | 會話工作樹的冒號分隔絕對路徑。零儲存庫會話為空。 |
| `CLAUDE_RUNNER_DEBUG_LOG_PATH` | 會話的偵錯日誌的路徑，在掛鉤執行時仍在磁碟上 |
| `CLAUDE_RUNNER_API_BASE_URL` | 用於會話範圍呼叫的 Anthropic API 基礎 URL |
| `CLAUDE_RUNNER_CLIENT_PLATFORM` | 建立工作階段的用戶端使用介面，例如 `web_claude_ai`、`desktop_app` 或 `ios`。當工作階段沒有已記錄或可辨識的使用介面時不會設定，因此在 `set -u` 下請以 `"${CLAUDE_RUNNER_CLIENT_PLATFORM:-}"` 參照它。需要 Claude Code v2.1.229 或更新版本。 |
| `CLAUDE_CODE_SESSION_ACCESS_TOKEN` | 會話存取權杖，用於會話範圍的 API 呼叫 |
| `GIT_CONFIG_COUNT`、`GIT_CONFIG_KEY_n`、`GIT_CONFIG_VALUE_n` | 執行器為您的 hook 所執行之 git 固定的 Git 設定。[生命週期 hook 內的 Git 設定](#git-configuration-inside-lifecycle-hooks)說明了這些設定。需要 Claude Code v2.1.280 或更新版本。 |

`CLAUDE_RUNNER_EXIT_REASON` 採用四個值之一：

* `completed`：工作階段正常結束。Claude Code 程序正常結束，或在工作階段被封存或刪除後自行結束。
* `failed`：Claude Code 程序崩潰，或在它啟動後設定失敗。
* `interrupted`：執行器停止了工作階段，屬於下列其中一種情況：
  * 執行器釋放工作階段以空出插槽。
  * 工作階段在啟動時逾時。
  * 伺服器將工作階段移出此執行器。
  * 執行器的輪詢在程序結束前察覺到封存或刪除。
  * 執行器正在排空。
  * 工作階段超過其 [`--kill-session-after-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 限制。
* `abandoned`：保留給另一個執行器聲稱的會話。掛鉤目前在該情況下不觸發。

如果您將 hook 收到的結果與[工作階段生命週期計數器](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#session-lifecycle-counter-semantics)進行比較，請預期部分 `interrupted` 結果在計數器中會被計為 `completed`。計數器會將釋放、啟動逾時、伺服器移動，以及由執行器輪詢先察覺到的封存或刪除計為 `completed`，因為執行器已乾淨地交回插槽。

掛鉤的結束狀態永遠不會影響會話結果；失敗被記錄並忽略。執行器在每個會話結束（包括執行器關閉）時等待最多 `--post-session-hook-timeout-sec`（預設 60 秒）。此範例將未提交的工作保存到救援分支：

```bash theme={null}
#!/usr/bin/env bash
set -u
export GIT_ALLOW_PROTOCOL=${GIT_ALLOW_PROTOCOL:-https:http:ssh}
IFS=':'
# -c overrides beat repo-local settings, blocking session-written fsmonitor,
# hook-path, and gpg-program config from executing code with the hook's
# privileges. -c commit.gpgsign=false also leaves these rescue commits
# unsigned under --configure-git.
# Repo-local credential.helper and pushurl still apply, and on a runner
# before v2.1.280 so does core.sshCommand; see the note below the script
# before you give this push a credential.
g() { git -c core.fsmonitor=false -c core.hooksPath=/dev/null \
        -c commit.gpgsign=false "$@"; }
for ws in $CLAUDE_RUNNER_WORKSPACE_PATHS; do
  cd "$ws" 2>/dev/null || continue
  [ -z "$(g status --porcelain 2>/dev/null)" ] && continue
  g add -A
  g commit -q -m "runner snapshot: $CLAUDE_RUNNER_SESSION_ID ($CLAUDE_RUNNER_EXIT_REASON)" || continue
  g push -q origin "HEAD:refs/heads/rescue/$CLAUDE_RUNNER_SESSION_ID" || true
done
```

指令碼中的 `GIT_ALLOW_PROTOCOL` 這一行將 git 限制為 HTTPS、HTTP 與 SSH 遠端。如果執行器的環境已自行設定非空的 `GIT_ALLOW_PROTOCOL` 清單，指令碼會保留該清單。

hook 會使用執行器主機上其自身環境中可用的任何 git 憑證進行推送。在[映像中不含憑證的做法](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)下，包括內建複製經由 Anthropic git 代理伺服器進行時，都不會有任何憑證，因此請在推送前於 hook 內產生短期推送憑證：將 hook 在 `CLAUDE_CODE_SESSION_ACCESS_TOKEN` 中收到的工作階段 token 與您自己的 token 服務交換，並依照[驗證工作階段身分](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)所述進行驗證。

請將您的 hook 提供給 git 的任何憑證都視為工作階段能夠取得的憑證，並在產生時將其權限限制為僅足以完成此次推送。您 hook 中的 git 會讀取工作階段可寫入的設定檔，而其中任一檔案所指定的憑證輔助程式或篩選驅動程式，會以您 hook 的權限執行。無論您指定哪個遠端，這些檔案中的設定也可能改變推送的目的地。關於執行器在您 hook 中固定的 git 設定，以及交由這些檔案決定的設定，請參閱[生命週期 hook 內的 Git 設定](#git-configuration-inside-lifecycle-hooks)。

#### 執行器釋放會話時的掛鉤計時

已釋放的會話可以在另一個執行器上恢復。在 v2.1.236 或更新版本的執行器上，會話在釋放時執行的操作決定了它是否可以在此掛鉤完成之前在另一個執行器上恢復：

* **在轉換後閒置，或在啟動時逾時**：執行器停止子程序並執行此掛鉤至完成。只有這樣它才會釋放會話。在掛鉤執行時發送的使用者訊息無法在掛鉤完成之前在另一個執行器上恢復會話。
* **等待使用者回答提示，例如權限提示**：執行器首先釋放會話，然後執行此掛鉤。在掛鉤執行時發送的使用者訊息可以在掛鉤完成之前在另一個執行器上恢復會話。

這適用於執行器釋放會話的任何時間：在閒置逾時、在 [`--retire-at`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 時間，以及 在 v2.1.260 或更新版本的執行器上，在會話的 [`--kill-session-after-min`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 限制。轉換已結束且僅持有背景任務的會話在此計為閒置。在 v2.1.236 之前，執行器在兩種情況下都首先釋放會話，然後執行此掛鉤。

在 `SIGTERM` 排水期間，執行器持有會話租約直到掛鉤完成；請參閱[關閉計時](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#shutdown-timing)。

### 生命週期 hook 內的 Git 設定

`checkout` 與 `post-session` hook 執行時，其環境中帶有工作階段的存取 token，而它們執行的 git 會讀取工作階段可寫入的設定檔，例如 `~/.gitconfig` 與簽出中的 `.git/config`。在任一 hook 執行前，執行器會在 hook 的環境中設定 git 設定（包括下列各項），形式為 `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` 配對以及 git 環境變數。Git 會將這些設定的優先順序排在所有設定檔之上，且它們只套用於您的 hook 所執行的 git，不套用於工作階段本身的 git。啟動時，執行器會印出一行 `[runner:git] lifecycle hooks:`，顯示目前生效的 hook 路徑、允許的協定、gpg 程式與簽署模式。需要 Claude Code v2.1.280 或更新版本。

* **Git hook**：除非您提供值，否則 `core.hooksPath` 為 `/dev/null`，因此 git 會略過儲存庫 `.git/hooks` 中的 hook，以及 `~/.gitconfig` 所指定的任何 hook 目錄。若要提供值，請在執行器的環境中將 `core.hooksPath` 匯出為 `GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` 配對。執行器也會從系統 git 設定讀取 `core.hooksPath`，但僅在執行器的使用者無法寫入該檔案、其指定的目錄或其中的 hook 檔案時才使用。當執行器忽略某個值時，啟動時會有一行 `[runner:warn]` 指出該值與原因。
* **檔案系統監視器**：`core.fsmonitor` 為空值，因此您 hook 中的 git 不會執行設定檔所指定的監視器程式。
* **遠端協定**：`GIT_ALLOW_PROTOCOL` 為 `https:http:ssh`。使用本機路徑、`file://` URL 或 `git://` URL 的複製、擷取或推送，會以 `fatal: transport 'file' not allowed` 或 `fatal: transport 'git' not allowed` 失敗。
* **SSH 命令與憑證提示**：您 hook 中的 git 會忽略設定檔中的 `core.sshCommand` 與 `core.askPass`。若要使用您自己的 SSH 命令，請在執行器的環境中設定 `GIT_SSH_COMMAND`。若要使用憑證提示程式，請在該處設定 `GIT_ASKPASS`。工作階段會繼承執行器的環境，因此這兩個變數也會傳到工作階段本身的 git。請勿在其中任一變數中放入憑證。
* **gpg 程式**：`gpg.program`、`gpg.openpgp.program`、`gpg.x509.program` 與 `gpg.ssh.program` 是執行器設定的路徑，絕不會取自設定檔中的值。
* **提交簽署**：使用 [`--configure-git`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#let-the-runner-configure-git) 時，您從 hook 建立的提交會以工作階段的身分簽署。未使用此旗標時，`commit.gpgsign` 與 `tag.gpgsign` 為 `false`。

若要變更其中某項設定，請使用執行器的環境，或在 hook 內使用 `git -c` 選項：

* **設定配對**：您在執行器環境中匯出的 `GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` 配對，會取代執行器對相同鍵的值。請從 `0` 開始為配對編號，並將 `GIT_CONFIG_COUNT` 設為配對數量。當計數所宣告的最後一個配對不存在時，執行器會忽略您所有的配對，並在啟動時記錄一行 `[runner:warn]`。
* **Git 環境變數**：執行器會保留您在其環境中設定的 `GIT_ALLOW_PROTOCOL`、`GIT_SSH_COMMAND` 與 `GIT_ASKPASS`。
* **`git -c` 選項**：hook 內的 `git -c` 選項會覆寫 `GIT_CONFIG_KEY_n` 配對，無論是執行器的還是您的。它不會變更 `GIT_ALLOW_PROTOCOL`、`GIT_SSH_COMMAND` 或 `GIT_ASKPASS`，因為 git 會先於任何設定讀取這些變數。

您 hook 中的 git 仍會從所有設定檔（包括工作階段可寫入的設定檔）讀取執行器未設定的每項設定，例如憑證輔助程式、`url.*.insteadOf` 重寫與篩選驅動程式。這些檔案之一所指定的憑證輔助程式或篩選驅動程式，會以您 hook 的權限作為程式執行，而這些檔案中的設定仍可改變您 hook 推送的目的地，包括推送到您在命令列上傳入的 URL。

在 v2.1.280 之前，執行器不會設定上述任何設定，且在 `--configure-git` 下，從 hook 建立的提交會失敗，除非 hook 傳入 `-c commit.gpgsign=false`。

### command

每當工作階段啟動或恢復時，於簽出之後執行，取代內建的子程序產生。此 hook 接收與[包裝指令碼](#wrapper-scripts)相同的環境，並應以相同方式 `exec` 進入 `"$CLAUDE_RUNNER_CLAUDE_BIN"`。使用 `command` hook 可將所有自訂內容集中在一個 hook 目錄中；當包裝指令碼位於其他位置時，請使用 `--exec-path`。如果同時設定了 `--exec-path`，則該旗標優先，`command` hook 會被忽略。

始終 `exec` 執行器自己的二進位檔案，而不是 PATH 解析的 `claude`；否則您會破壞[版本固定](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#pin-the-version)。

## 隨需 runner

您可以為每個工作階段啟動一個 runner，而不必執行固定的機群。orchestrator 是一個獨立、無狀態的子命令，它會向 Anthropic 輪詢產生請求（每個已排入佇列但沒有可用 runner 的工作階段各一個），並針對每個請求執行您的 `spawn-runner` hook。您的 hook 會向您的平台提交工作負載：Kubernetes Job、EC2 執行個體、Nomad dispatch。

隨需 runner 可改善憑證衛生。在固定機群上，環境密鑰存放在每一台 runner 主機上，而這些主機也正是執行使用者工作階段的主機。使用 orchestrator 時，環境密鑰只會留在 orchestrator 主機上，而該主機從不執行使用者程式碼；每個產生的 runner 會收到一份一次性的工作單，該工作單僅註冊恰好一個 runner，之後便會過期。

若要啟動 orchestrator，請傳入環境密鑰以及一個包含可執行 `spawn-runner` 指令碼的 hooks 目錄：

```bash theme={null}
claude self-hosted-runner orchestrator \
  --environment-secret-file /etc/claude/environment-secret \
  --hooks-dir /etc/claude/hooks
```

orchestrator 在輪詢之間不保留任何狀態，因此您可以針對同一個環境執行兩個或更多副本以提升可用性。每個產生請求在伺服器端只會由恰好一個副本認領。所有副本都必須使用相同的 `--expected-spawn-seconds` 值；請參閱 [hook 合約](#the-spawn-runner-hook)。

### spawn-runner hook

orchestrator 會針對每個產生請求執行一次 `${hooks-dir}/spawn-runner`。hook 必須以非同步方式提交工作，不等待 runner 啟動，並在 `--hook-timeout`（預設 60 秒）內返回。hook 會收到：

| 變數 | 說明 |
| :- | :- |
| `CLAUDE_RUNNER_WORK_ORDER_FILE` | 暫存檔案的路徑，內含新 runner 用於註冊的已簽署工作單 JWT。hook 結束後即會刪除。請勿記錄該檔案的內容。 |
| `CLAUDE_RUNNER_ORDER_ID` | 不透明的冪等性金鑰，每個產生請求皆唯一，且可安全用於 Kubernetes 資源名稱。請只將訂單 ID 作為您佈建工具的去重金鑰，不得使用其他值。 |
| `CLAUDE_RUNNER_SESSION_ID` | 此請求所屬的工作階段，即該工作階段 URL 中的 `session_...` ID。該工作階段的每次重新請求都會重複此值，因此請將其用於日誌與路由，而非作為去重金鑰。對於預熱請求則為空值；預熱請求會在設定 [`--min-idle`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags) 時，於任何特定工作階段之前先啟動一個待命 runner，因此請勿假設此變數一定已設定。 |
| `CLAUDE_RUNNER_SESSION_UUID` | 相同的工作階段 ID，採標準 UUID 格式。預熱請求時為空值。 |
| `CLAUDE_RUNNER_ATTEMPT` | 用於日誌的每工作階段計數器。它不是重試次數，也不是請求次數。預熱請求時為 `0`，但某個工作階段的請求也可能帶有 `0`。 |
| `CLAUDE_RUNNER_ORDER_SERVER_TIME` | 取自輪詢回應 HTTP `Date` 標頭的伺服器時間。當 hook 驗證工作單 JWT 的 `exp` 時，請與此值比較而非本機時鐘，以容忍時鐘偏差。若閘道省略了該標頭則為空值。 |
| `CLAUDE_RUNNER_POOL_ID` | 新 runner 應加入的環境 ID，格式為 `ccpool_...` |
| `CLAUDE_RUNNER_ACCOUNT_ID` | 將該工作階段排入佇列之帳戶的帶標籤 ID。請將其用於依帳戶路由、配額或成本分攤，而非作為去重金鑰。無法取得時為空值。 |
| `CLAUDE_RUNNER_ACCOUNT_EMAIL` | 將該工作階段排入佇列之帳戶的電子郵件。無法取得時為空值。請將此電子郵件視為個人識別資訊，不要記錄它。 |
| `CLAUDE_RUNNER_PRIMARY_REPO_URL` | 工作階段第一個 git 來源的 URL，用於路由到已預熱該儲存庫的 runner。工作階段沒有 git 來源時為空值。 |
| `CLAUDE_RUNNER_PRIMARY_REPO_REVISION` | 工作階段第一個 git 來源的修訂版本：分支、SHA、標籤或完整參照名稱。未指定時為空值。 |
| `CLAUDE_RUNNER_REPO_SOURCES` | 工作階段所有 git 來源的 `{url, revision}` JSON 陣列，供依次要儲存庫路由的 hook 使用。沒有來源時為空值。 |
| `CLAUDE_RUNNER_CORRELATION_ID` | 建立工作階段時提供的關聯 ID，會原樣回傳，讓 hook 可將此工作單對應到建立該工作階段的請求。工作階段沒有關聯 ID 時為空值。 |
| `CLAUDE_RUNNER_CLIENT_PLATFORM` | 建立該工作階段的用戶端使用介面，例如 `web_claude_ai`、`desktop_app`、`ios` 或 `scheduled_trigger`，用於採用情況分析。當工作階段沒有已記錄或可辨識的使用介面時，以及對於預熱請求，此變數不會設定；請使用 `[ -n "${CLAUDE_RUNNER_CLIENT_PLATFORM:-}" ]` 檢查，此寫法在 `set -u` 下仍然安全。 |

產生的 runner 會以工作單取代環境密鑰來進行註冊：

* **以工作單啟動它**：將 [`--environment-secret-file`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags) 指向包含工作單 JWT 的檔案，或將 `SELF_HOSTED_RUNNER_ENVIRONMENT_SECRET` 設為該 JWT 值。
* **在 hook 結束前複製 JWT**：orchestrator 會在 hook 結束後刪除工作單檔案，因此請將 JWT 複製到您提交的工作負載中（例如產生之 Job 上的 Kubernetes Secret），而不要只傳遞檔案路徑。
* **在產生的 runner 上使用 `--capacity 1`**：綁定工作階段的工作單只會註冊恰好一個綁定到該工作階段的 runner，因此較高的容量只會增加永遠不會收到工作的槽位，且 runner 會在啟動時記錄警告。
* **預熱工作單以未綁定方式註冊**：待命 runner 不會綁定到工作階段，並會像固定機群 runner 一樣認領佇列中的工作。

無論您的 hook 在哪個平台上佈建，此合約都有四條規則：

1. **以 `CLAUDE_RUNNER_ORDER_ID` 實現冪等。** 同一請求重新遞送時，最多只能產生一個 runner。請從訂單 ID 推導出確定性的資源名稱，並讓您的平台拒絕重複項目。請勿改用 `CLAUDE_RUNNER_SESSION_ID` 作為金鑰。某工作階段的每次重新請求都帶有相同的工作階段 ID 與新的訂單 ID。以工作階段 ID 命名或去重的工作負載，在第一個工作負載仍存在時不會再次建立。
2. **不要重試工作負載。** 一個訂單 ID 代表最多建立一個工作負載。若 runner 從未註冊，Anthropic 會在 `--expected-spawn-seconds` 之後以新的訂單 ID 重新請求。
3. **遵循退出碼合約。** 以符合結果的狀態結束：

   * **Exit 0**：已提交。
   * **Exit 1，或在 `--hook-timeout` 結束時仍在執行**：可重試的失敗。工作階段會退避並重新提供。連續 10 次請求失敗後，該工作階段會如同 exit 2 或更高時一樣被封鎖。
   * **Exit 2 或更高**：不可重試的失敗。該工作階段會被封鎖而無法再次產生，直到使用者向其傳送新訊息，或 [Owner](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments) 在環境的 **Activity** 分頁中對其選取 **Retry**。

   工作階段退避期間，它會在 **Activity** 分頁中顯示為 **Queued**，且沒有產生錯誤，因此請在 orchestrator 的日誌中查看 hook 的輸出。一旦被封鎖，工作階段會顯示為 **Failed**。展開它即可查看產生錯誤，其內容取自 hook stderr 的最後 512 個字元。請將可據以採取行動的錯誤寫入 stderr，且不要包含任何密鑰。在 shell hook 中，請[讓暫時性失敗保持可重試](#keep-transient-failures-retryable-in-a-shell-hook)。

   預熱請求沒有可失敗的工作階段：orchestrator 只會在本機記錄非零的結束狀態，而伺服器會在 `--expected-spawn-seconds` 租約到期後重新請求產生。
4. **將 `--expected-spawn-seconds` 設為至少等於您從產生請求到 runner 註冊的 p99 時間。** 請從 orchestrator 收到產生請求時開始計算，並將在您平台上等待容量的時間與啟動時間都納入。此值是伺服器端租約，工作單會隨之過期，因此工作負載耗時更久的 runner 將無法註冊。所有 orchestrator 副本都必須使用相同的值。

hook 寫入 stdout 或 stderr 的所有內容都會出現在 orchestrator 的日誌中，且憑證會自動遮蔽。若工作階段持續停留在佇列中，請檢查 orchestrator 的 `/healthz` 回應內容以取得佇列計數，然後在 [**Cloud environments** 管理頁面](https://claude.ai/admin-settings/cloud-environments)開啟您環境的 **Activity** 分頁：在該處展開失敗的工作階段以查看其產生錯誤，並選取 **Retry** 以重新請求。

#### 修正持續顯示 Queued 或顯示 Failed 的重新開啟工作階段

若重新開啟的工作階段持續顯示 **Queued** 或顯示 **Failed**，或您的 hook 在處理它們時逾時，原因之一可能是 hook 以工作階段 ID 命名或去重工作負載。當工作階段的 runner 已結束後，其使用者又向其傳送訊息時，該工作階段即會重新開啟。例如，假設有一個 hook 以如下方式建立每個工作負載的名稱：

```bash theme={null}
name="runner-${CLAUDE_RUNNER_SESSION_ID}"
```

1. 在工作階段的第一次產生請求時，hook 會以該名稱建立工作負載，並啟動一個 runner
2. runner 結束（例如在 [`--release-idle-session-min`](#make-on-demand-runners-exit-when-idle) 之後），之後使用者重新開啟該工作階段
3. 該工作階段的下一個產生請求帶有相同的工作階段 ID 與新的訂單 ID，因此 hook 會建立相同的名稱
4. 若您的平台仍保有第一次請求的工作負載（因為在其 runner 結束時沒有任何機制將其[移除](#make-on-demand-runners-exit-when-idle)），hook 不會建立新的工作負載，也不會啟動任何 runner
5. 該工作階段之後的每個產生請求都會以相同方式結束

請開啟您自己的 hook，查看當工作負載已存在時它會如何處理，例如當您的平台拒絕重複的名稱時。在第一欄中找到該行為，即可得知重新開啟的工作階段在 **Activity** 分頁中會顯示什麼：

| 當工作負載已存在時，您的 hook | **Queued** 變為 **Failed** 的時機 | 產生錯誤 |
| :- | :- | :- |
| 未建立任何內容即以 0 結束 | 連續 10 次此類請求之後 | `runner did not register within ETA after max attempts` |
| 以 1 結束 | 連續 10 次此類請求之後 | 您 hook 的 stderr 結尾；若其未寫入任何內容到 stderr，則為 `exit 1` |
| 以 2 或更高結束 | 立即 | 您 hook 的 stderr 結尾；若其未寫入任何內容到 stderr，則為 `exit` 加上代碼，例如 `exit 2` |
| 一直等待到 `--hook-timeout` 結束 | 連續 10 次此類請求之後 | 您 hook 的 stderr 結尾；若其未寫入任何內容到 stderr，則為 `spawn-runner hook timed out after 60000ms` |

在最後一列的產生錯誤中，`60000` 是以毫秒表示的 `--hook-timeout`。當 hook 一直等待到 `--hook-timeout` 結束時，orchestrator 的日誌也會出現一行 `timed out after`。

若要修正 hook，請依照 [hook 合約的規則 1](#the-spawn-runner-hook) 的要求，以 `CLAUDE_RUNNER_ORDER_ID` 建立每個名稱或金鑰。在此範例中，名稱會變成：

```bash theme={null}
name="runner-${CLAUDE_RUNNER_ORDER_ID}"
```

若您的 hook 會等待，也請讓它在提交工作負載後便結束，因為等待中的 hook 會[延遲其 orchestrator 的後續 hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#orchestrator-cli-flags)。變更 hook 後，請在 **Activity** 分頁中檢查每個卡住之工作階段的狀態：

* **Queued**：該工作階段會自行取得下一個產生請求
* **Failed**：以 Owner 身分對其選取 **Retry**，或請其使用者向其傳送新訊息

#### 讓隨需 runner 在閒置時結束

預設情況下，您的 hook 啟動的 runner 在其工作階段的回合結束時不會結束，因此您提交的工作負載會持續執行。若要讓 runner 結束，請讓您的 hook 傳入下列 [runner 旗標](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#runner-cli-flags)：

| 旗標（含範例值） | 傳給 | 作用 |
| :- | :- | :- |
| `--release-idle-session-min 30` | 您的 hook 啟動的每個 runner | runner 會在閒置達該分鐘數後釋放其工作階段，然後以 0 結束。該工作階段會在其使用者傳送下一則訊息時繼續，但[尚未推送的工作將會遺失](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#resumed-sessions-lose-unpushed-work)。對於工作階段留下仍在執行的程序，請[保留該工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#keep-an-idle-session-while-its-processes-run)。 |
| `--kill-session-after-min 480` | 您的 hook 啟動的每個 runner | 將每個工作階段限制在該分鐘數內，作為[不計為閒置之工作階段](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#some-sessions-don’t-count-as-idle)的防線，因此請將其設定為高於您預期最長的工作階段 |
| `--exit-if-unused-min 60` | 待命 runner，即您的 hook 為預熱請求所啟動的 runner | 從未接手工作階段的待命 runner 會在該分鐘數後結束。若您設定了 [`--min-idle`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags)，除非該待命 runner 屬於多餘，否則您會得到一個替代者，因此請使用遠高於啟動時間的值。 |

在 runner 結束時移除工作負載，例如在 Kubernetes Job 上設定 `ttlSecondsAfterFinished`，或讓 VM 的啟動指令碼在之後刪除該 VM。

#### 將背景程序的輸出傳送到檔案

若您的 `spawn-runner` hook 留下一個在背景執行的程序，請將該程序的輸出傳送到 hook 的使用者可以建立的檔案。例如，在啟動該程序的命令中、任何 `&` 之前附加 `>> "$HOME/claude-runner.log" 2>&1`。以下 hook 行顯示重新導向的位置，其中 `your-background-command` 代表您的 hook 放到背景執行的命令：

```bash theme={null}
your-background-command >> "$HOME/claude-runner.log" 2>&1 &
```

若沒有重新導向，該程序會寫入 hook 的 stdout 與 stderr：

* hook 結束約一秒後，orchestrator 會記錄 `exited, but a process it started still has the hook's stdout or stderr open`。從該行起，它會在 `[runner:hook:spawn-runner:after-exit jti=<order id>]` 下再記錄最多 64 KB 的該輸出，之後捨棄其餘部分。
* orchestrator 結束後，該程序寫入那裡的動作就會失敗。

由您的 hook 自行啟動的 runner 會在 orchestrator 主機上執行工作階段，而該主機持有[環境密鑰](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)。

在 v2.1.305 之前，已結束的 hook 若其啟動的程序仍開啟著 hook 的 stdout 或 stderr，仍會達到 [`--hook-timeout`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags)，顯示如下：

* **Activity 分頁**，在失敗工作階段的產生錯誤中：`spawn-runner hook timed out after 60000ms`，或 hook stderr 上的最後幾行。
* **orchestrator 日誌**：`timed out after 60000ms, sending SIGTERM to process tree`。

#### 結束 hook 而不等待 runner

若每個隨需 runner 都在其 hook 啟動約 60 秒後停止，且您的 hook 針對同一個工作階段再次執行，請檢查 hook 是否在等待 runner。這 60 秒是預設的 [`--hook-timeout`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags)，因此若您自行設定了該值，runner 會在 hook 啟動後經過該時間長度時停止。

在 orchestrator 主機上啟動 `claude self-hosted-runner` 並等待它（無論是在前景執行或使用 `wait`）的 hook，在 `--hook-timeout` 結束時仍在執行。orchestrator 接著會停止該 hook 及在其下執行的程序，包括該 runner 與工作階段的 Claude 程序，因此仍在執行的回合會被中斷。

* **若要確認是逾時導致您的 runner 停止**：在 orchestrator 的日誌中，查看每個產生請求是否都出現 `timed out after 60000ms, sending SIGTERM to process tree`。其中 `60000` 是以毫秒表示的 `--hook-timeout`。
* **若要修正**：讓 hook 將 runner 提交到您的平台並以 0 結束。若您改為提高 `--hook-timeout`，runner 只會較晚停止。

#### 在 shell hook 中讓暫時性失敗保持可重試

在使用 `set -e` 的 shell hook 中，原本透過重試即可排除的失敗可能會封鎖工作階段。hook 會在失敗的命令處停止，並以該命令本身的狀態結束，而 orchestrator 會對該狀態套用退出碼合約。許多失敗會回傳 2 或更高的狀態，例如命令未安裝時的 `127`，以及 `curl --fail` 遇到 HTTP 錯誤時的 `22`，因此它們會在第一次失敗時就封鎖工作階段。

已被 hook 封鎖的工作階段會保持封鎖，直到使用者向其傳送新訊息，或 [Owner](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments) 在環境的 **Activity** 分頁中對其選取 **Retry**。

若要改將此類失敗轉為 exit 1，請將下列幾行直接放在 hook 的 `#!` 行下方、任何可能失敗的內容之上：

```bash theme={null}
set -e
PERMANENT=; permanent() { printf '%s\n' "$*" >&2; PERMANENT=1; exit 2; }
trap 'rc=$?; [ "$rc" -eq 0 ] || [ -n "${PERMANENT:-}" ] || exit 1' EXIT
```

這幾行會改變 hook 其餘部分的行為，因此加入後請針對下列每種模式檢查 hook：

* **單純的 `exit 2` 或更高**：設定 trap 後，它會變成 exit 1。對於任何重試都無法修復的錯誤，請改為以原因呼叫 `permanent`，例如 `permanent "namespace claude-runners does not exist"`。請在主 shell 中呼叫，而不要在 `$( )`、`( )` 或管線中呼叫。
* **`exec`**：不要以 `exec` 開始 hook 的最後一個命令，因為 `exec` 會取代 shell，trap 將不會執行。
* **第二個 `EXIT` trap**：第二個 `trap ... EXIT` 會取代第一個，因此請將兩者合併為單一 trap。將您的清理命令直接放在 `rc=$?;` 之後，並在每個命令結尾加上 `|| true;`。如此一來，清理在失敗與成功時都會執行，且失敗的清理命令不會設定 hook 的結束狀態。以下合併後的 trap 展示其形式，其中 `your-cleanup-command` 代表您自己的命令：

  ```bash theme={null}
  trap 'rc=$?; your-cleanup-command || true; [ "$rc" -eq 0 ] || [ -n "${PERMANENT:-}" ] || exit 1' EXIT
  ```
* **允許失敗的命令**：若 hook 之前未使用 `set -e`，它現在會在第一個回傳非零值的命令處停止，例如找不到任何結果的查詢。若 hook 會依據結果採取動作，請將該命令作為 `if` 的條件。若 hook 忽略結果，請在該命令後加上 `|| true`。
* **提交工作負載的命令**：不要在其後加上 `|| true`。加上 `|| true` 時，即使您的平台拒絕提交（例如超出配額），hook 也會以 0 結束，而工作階段會等待一個從未啟動的 runner。

  請依照 [hook 的第一條規則](#the-spawn-runner-hook)，以 `CLAUDE_RUNNER_ORDER_ID` 命名工作負載。如此一來，「已存在」的回應即代表同一請求的重新遞送，因此請只將該回應視為成功。對於其他任何回應，請將該回應印到 stderr 並以 exit 1 結束，或在任何重試都無法修復時呼叫 `permanent`。此範例針對 `kubectl create` 執行上述處理，其中 `job.yaml` 僅包含工作負載：

  ```bash theme={null}
  if ! out=$(kubectl create -f job.yaml 2>&1); then
    case "$out" in
      *AlreadyExists*) ;;
      *) printf '%s\n' "${out:-kubectl create failed}" >&2; exit 1 ;;
    esac
  fi
  ```

  orchestrator 的日誌隨後便會顯示該訊息。若 hook 會建立其他物件，請以訂單 ID 為每個物件命名，為其提供各自的命令，並以相同方式將其「已存在」回應視為成功。對於持有密鑰的物件，請印出固定訊息，而非命令的輸出。

若要確認 trap 是否正常運作，請在 `trap` 行正下方加入一行呼叫不存在的命令，例如 `no-such-command`。從您的 shell 執行 hook 檔案，並確認 `echo $?` 印出 `1`，然後移除該行。

### 停止或重新啟動 orchestrator

若要停止或重新啟動 orchestrator 而不中斷正在執行的 `spawn-runner` hook，請以 [`--shutdown-drain-sec`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags) 啟動它。如此一來，收到 `SIGTERM` 時，它會給予正在執行的 hook 最多您所設定的秒數來完成。若要選擇該值並設定您的程序監管工具與之相符，請參閱[調整 `--shutdown-drain-sec` 與 orchestrator 的停止逾時](#size-shutdown-drain-sec-and-the-supervisors-stop-timeout-for-the-orchestrator)。

以下啟動命令允許 70 秒：

```bash theme={null}
claude self-hosted-runner orchestrator \
  --environment-secret-file /etc/claude/environment-secret \
  --hooks-dir /etc/claude/hooks \
  --shutdown-drain-sec 70
```

orchestrator 會在已送出的輪詢與每個 hook 都完成後結束。當 `--shutdown-drain-sec` 秒數用盡時，仍在執行的 hook 會收到 `SIGTERM`，且 orchestrator 會結束。第二個 `SIGTERM` 或任何 `SIGINT` 會執行相同動作而不等待。包含 `[runner:orchestrator] stop summary:` 的日誌行會依各自的結束方式統計 hook 與產生請求的數量。

若未使用 `--shutdown-drain-sec`，orchestrator 會在收到 `SIGTERM` 或 `SIGINT` 時立即停止。每個正在執行的 hook 都會收到 `SIGTERM`，且不會通知 Anthropic。如此一來，其 runner 從未啟動的工作階段可能會一直停留在佇列中，直到 Anthropic [重新請求它](#the-spawn-runner-hook)為止，這會在經過 `--expected-spawn-seconds`（預設 120 秒）後發生。

> [!NOTE]
>
> `--shutdown-drain-sec` 需要 Claude Code v2.1.299 或更新版本。較舊的版本會在啟動時以 `error: unknown flag --shutdown-drain-sec` 結束。

#### 調整 `--shutdown-drain-sec` 與 orchestrator 的停止逾時

在預設設定下，請使用 [`--shutdown-drain-sec 70`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#orchestrator-cli-flags)，並搭配 85 秒的停止逾時，也就是在 Kubernetes 上設定 `terminationGracePeriodSeconds: 85`，或在 systemd 下設定 `TimeoutStopSec=85`。若您變更了 `--hook-timeout`，請同步調整兩者：

* **`--shutdown-drain-sec`**：至少為 `--hook-timeout` 加 10 秒，讓在 `SIGTERM` 之前剛啟動的 hook 仍能完成
* **停止逾時**：至少為 `--shutdown-drain-sec` 加 15 秒。orchestrator 會在啟動時記錄此數值：請尋找包含 `shutdown drain:` 的日誌行。

請讓您的程序監管工具只傳送單一 `SIGTERM`，且只傳給 orchestrator 程序，因為第二個 `SIGTERM` 會提前中斷 `--shutdown-drain-sec` 的等待。若您保留 systemd 預設的 [`KillMode=control-group`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#what-reaches-a-running-post-session-hook)，hook 也會收到 `SIGTERM`，而 hook 可能在提交其工作負載之前就終止。在變更 `KillMode` 之前，請先檢查您的 `spawn-runner` hook 如何啟動 runner：

* **若您的 hook 將其工作負載提交到平台後即結束**：將 orchestrator 作為該 unit 的主程序執行，並設定 `KillMode=mixed`，這只會將 `SIGTERM` 傳送給該程序。
* **若您的 hook 將 runner 作為 orchestrator 自身 unit 中的程序啟動**：`KillMode=mixed` 不會傳送 `SIGTERM` 給這些 runner。systemd 反而會在稍後傳送 `SIGKILL` 給它們，因此它們會在未清空其工作階段、也未執行其 `post-session` hook 的情況下結束。

## 將模型請求傳送至 Bedrock 或 Agent Platform

如果您的組織需要讓模型請求經過自己的 AWS 或 Google Cloud 帳戶，請為 runner 設定 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 或 [Google Cloud 的 Agent Platform（前身為 Vertex AI）](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)。之後該 runner 啟動的每個工作階段都會以您的雲端憑證，在您的雲端帳戶中呼叫模型。若未進行此設定，工作階段會將模型請求傳送至 Anthropic API。

Runner 仍會向 Anthropic 輪詢工作階段，且每個工作階段仍會將其事件串流傳送至 `api.anthropic.com`。事件串流包含提示詞、回應和工具結果。[可用性與限制](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations)中的方案要求和 Zero Data Retention 排除條款仍然適用。

工作階段是路由至環境，而非路由至 runner，且重新排入佇列或恢復的工作階段可能會在不同的 runner 上執行。請以相同方式設定環境中的每個 runner。開始之前，請閱讀[這些供應商上有何不同](#what-differs-from-sessions-on-the-anthropic-api)。

**1. 準備雲端帳戶和輸出規則**

設定模型存取權、範圍嚴格限定的政策或角色，以及網路存取：

* **Amazon Bedrock**：[提交使用案例詳細資訊](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#1-submit-use-case-details)，然後建立 [IAM 設定](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#iam-configuration)中的政策，將 `bedrock:InvokeModel` 和 `bedrock:InvokeModelWithResponseStream` 限制為您的工作階段所使用的推論設定檔及其背後的基礎模型
* **Agent Platform**：[啟用 API](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#1-enable-agent-platform-api) 並[請求模型存取權](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#2-request-model-access)，然後建立 [IAM 設定](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#iam-configuration)所描述的自訂角色，僅包含 `aiplatform.endpoints.predict`
* **輸出**：在您的輸出規則中允許供應商的端點。請參閱[網路需求](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#network-requirements)。如果工作階段無法連線至這些端點，Claude Code 可能會持續重試數小時，工作階段才會顯示錯誤。

**2. 為工作階段提供範圍嚴格限定的憑證**

將步驟 1 中的政策或角色附加至一個無法執行其他任何操作的身分。關於 Claude Code 接受的方法，請參閱[設定 AWS 憑證](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#2-configure-aws-credentials)和[設定 GCP 憑證](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#3-configure-gcp-credentials)。

> [!WARNING]
>
> 任何能讓程式碼在工作階段中執行的人（包括透過提示詞注入），都能在憑證有效期間內使用這些憑證，費用由您承擔。Claude Code 在工作階段內執行，因此它用來呼叫模型的憑證必須能在該處讀取。
>
> Claude 執行的 shell 命令、您的 [Claude Code hook](https://code.claude.com/docs/zh-TW/hooks.md) 以及 stdio MCP 伺服器會繼承工作階段的環境，並以與 Claude Code 相同的使用者身分執行。因此，它們可以讀取憑證變數和憑證檔案。
>
> 當您[強化部署](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)時，可以讓主機憑證不進入工作階段，但無法讓此憑證不進入。請勿為其背後的身分授予步驟 1 的政策或角色以外的任何權限。

請根據以下 runner 行為檢查您選擇的方法：

* **中繼資料端點**：如果您完全拒絕工作階段存取[雲端中繼資料端點](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)，由其提供的憑證（例如執行個體設定檔）也不會傳達至 Claude Code。以檔案為基礎的 Web 身分，例如 Amazon EKS 上的 IAM Roles for Service Accounts (IRSA) 或 Workload Identity Federation 憑證檔案，則不依賴該端點。
* **續期**：工作階段的存續時間可能比憑證更長，因此請使用會自行續期的方法，例如以檔案為基礎的 Web 身分
* **包裝腳本**：您的[包裝腳本](#provision-credentials-scoped-to-the-session-creator)匯出的憑證值在 Claude Code 執行期間不會續期，因此對於長時間的工作階段，請使用會自行續期的方法。Claude Code 會從其環境讀取 AWS 憑證，因此如果您的包裝腳本已為其他工作匯出 AWS 憑證，Claude Code 可以使用這些憑證來簽署模型請求。

**3. 在 runner 的環境中設定單一供應商的變數**

在您設定 runner 其他環境變數的地方（例如容器規格或服務單元）設定恰好一個供應商的變數，然後重新啟動 runner。範例以 shell 匯出的形式呈現。若使用[隨需 runner](#on-demand-runners)，請在您的 `spawn-runner` hook 所啟動的工作負載上設定這些變數。

請使用 [`--confine-repo-settings enforce`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#harden-your-deployment) 啟動這些 runner。它會拒絕在已提交設定遭其標記的儲存庫上執行工作階段，因此請先以預設的 `warn` 模式執行，並清除它在日誌中記錄的項目。

> [tab] Amazon Bedrock
>
> 將區域替換為您自己的區域：
>
> ```bash theme={null}
> export CLAUDE_CODE_USE_BEDROCK=1
> export AWS_REGION=us-east-1
> ```
>
> 關於 Claude Code 如何解析區域，請參閱[設定 Claude Code](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#3-configure-claude-code)。關於 Claude Code 針對您的區域使用哪個推論設定檔前綴，請參閱[跨區域推論設定檔前綴](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#cross-region-inference-profile-prefixes)。

> [tab] Google Cloud's Agent Platform
>
> 將區域和專案 ID 替換為您自己的值：
>
> ```bash theme={null}
> export CLAUDE_CODE_USE_VERTEX=1
> export CLOUD_ML_REGION=global
> export ANTHROPIC_VERTEX_PROJECT_ID=YOUR-PROJECT-ID
> ```
>
> 若要選擇區域，請參閱[區域設定](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#region-configuration)。

**4. 檢查變數是否已傳達至工作階段**

您在主機上自己的 shell 是不同的程序，因此請從工作階段內部檢查。在該環境中啟動一個工作階段，並請 Claude 執行此命令：

```bash theme={null}
env | grep -E 'CLAUDE_CODE_USE_(BEDROCK|VERTEX)'
```

若有一行將 `CLAUDE_CODE_USE_BEDROCK` 或 `CLAUDE_CODE_USE_VERTEX` 設為 `1`，表示該變數已傳達至工作階段。如果兩者都出現，Claude Code 會使用 Amazon Bedrock。沒有輸出則表示兩者皆未傳達。

此命令顯示的是設定，而非流量。若要確認請求本身，請在您雲端帳戶自己的指標或請求日誌中查看。如果第一則訊息反而失敗，請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#troubleshooting) 或 [Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#troubleshooting) 的疑難排解。

### 與 Anthropic API 上的工作階段有何不同

將模型請求傳送至 Amazon Bedrock 或 Google Cloud 的 Agent Platform 的工作階段，與 Anthropic API 上的工作階段有以下差異：

* **來自 claude.ai 的政策**：[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)不會傳達至這些工作階段。Owner 在 Claude Code 管理設定中設定的組織政策也不會傳達，因此 Claude Code 不會在工作階段內強制執行這些政策。請將您所依賴的規則放入 runner 映像檔的[受管設定檔案](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)中。
* **帳戶 skill**：這些工作階段不會下載使用者的 claude.ai 帳戶所啟用的 skill。請參閱[每個工作階段的設定如何組成](#how-each-session’s-config-is-assembled)。
* **檔案**：使用者在 claude.ai 或行動裝置或桌面應用程式中附加至工作階段的檔案不會傳達至工作階段，且 Claude 無法使用 [`SendUserFile` 工具](https://code.claude.com/docs/zh-TW/tools-reference)回傳檔案。請改將輸入檔案放在儲存庫中或 runner 上。
* **模型選擇**：Anthropic 的控制平面會傳送每個工作階段的模型，當工作階段在沒有指定模型的情況下啟動時，Claude Code 會使用該供應商的預設模型。您無法透過 runner 環境中的 `ANTHROPIC_MODEL` 或 `ANTHROPIC_DEFAULT_MODEL` 選擇模型，但可以固定別名所解析的目標：
  * **`ANTHROPIC_MODEL` 和 `ANTHROPIC_DEFAULT_MODEL`**：即使供應商頁面的範例會設定 `ANTHROPIC_MODEL`，runner 仍會從其傳遞給工作階段的環境中移除這兩個變數。
  * **各模型系列的固定變數**：[Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#4-pin-model-versions) 和 [Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#5-pin-model-versions) 的「固定模型版本」中的變數確實會傳達至工作階段。這些變數決定的是 `opus` 等別名解析為哪個模型，而非完整模型 ID 解析為哪個模型。
* **您的帳戶未提供的模型**：工作階段可能會在某則訊息上失敗，並出現指出該模型名稱的錯誤。請啟用您的開發人員可以選擇的模型、「固定模型版本」中所述的背景模型，以及[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry)所使用的分類器模型。在 Amazon Bedrock 上，請在您的政策中允許其中每一個模型。
* **網路搜尋和快速模式**：[網路搜尋](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)在 Amazon Bedrock 上無法使用，而[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)在兩個供應商上都無法使用。關於其他因供應商而異的功能，請參閱[因供應商而異的 CLI 功能](https://code.claude.com/docs/zh-TW/feature-availability.md#cli-capabilities-that-vary-by-provider)。

## MCP 伺服器

若要讓 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)在每個工作階段中都可用，請在映像建置時使用與桌面安裝相同的 `claude mcp add` 命令加入它們。如果您的 runner 是裸程序而非容器，請以 runner 的使用者身分在主機上執行相同的命令，然後重新啟動 runner：它只會在啟動時讀取一次主機設定。`--scope user` 旗標是必要的；預設的 local 範圍會寫入以各目錄為鍵的位置，而 runner 不會將其植入工作階段。例如，在您的 Dockerfile 中：

```dockerfile theme={null}
RUN claude mcp add --scope user sidecar -- /usr/local/bin/mcp-sidecar
RUN claude mcp add --scope user --transport http internal http://mcp-gateway.svc.cluster.local:8080
```

runner 會在啟動時對主機的設定建立一次快照。快照會擷取主機 `.claude.json` 中的 `mcpServers` 鍵（該檔案位於 `~/.claude/` 旁邊，而非其內部），且 runner 只會將該鍵植入每個工作階段的隔離設定中；帳戶狀態和專案歷史記錄會被捨棄。若要確認伺服器已傳達到工作階段，請在該環境上啟動一個工作階段，並請 Claude 列出其 MCP 工具；對於任何 `type` 無法辨識的已擷取項目，runner 也會在啟動時記錄警告並捨棄該項目，讓您能看出該伺服器為何未出現在工作階段中。當設定了 `SELF_HOSTED_RUNNER_HOST_CONFIG_DIR` 時，runner 會改為從該目錄讀取 `.claude.json`，因此將該變數指向空目錄也會停用 MCP 植入。

Claude Code 也會從其他來源載入 MCP 伺服器：

* 位於標準系統路徑的企業範圍[受管 MCP 檔案](https://code.claude.com/docs/zh-TW/managed-mcp.md)：Linux runner 主機上為 `/etc/claude-code/managed-mcp.json`，macOS 主機上為 `/Library/Application Support/ClaudeCode/managed-mcp.json`。適用於僅允許載入管理員所列伺服器的鎖定機群。優先順序規則請參閱[使用 managed-mcp.json 進行獨占控制](https://code.claude.com/docs/zh-TW/managed-mcp.md#exclusive-control-with-managed-mcp-json)。當此檔案存在於 runner 主機上時，Claude Code 會略過 Anthropic 控制平面傳遞給工作階段的 MCP 伺服器（包括 claude.ai 連接器），並在工作階段子程序的 stderr 上以警告列出它們，runner 會以 `debug` 日誌層級記錄這些警告。在 v2.1.229 之前，這些工作階段會在啟動時以 `You cannot dynamically configure MCP servers when an enterprise MCP config is present` 結束。
* runner 主機上[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 鍵：提供 HTTP 和 SSE 伺服器而不取得獨占控制，因此來自其他來源的伺服器仍會載入。需要 Claude Code v2.1.259 或更新版本。
* `<repo>/.mcp.json`：專案範圍。在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)對話串之外，將此檔案提交到儲存庫，其伺服器在雲端工作階段中即會自動核准。在包含多個儲存庫的工作階段中，[最多只會載入一個儲存庫的檔案](#repository-settings-in-sessions-with-several-repositories)。
* 來自您包裝腳本的 [`--mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 檔案：將此旗標附加在 `"$@"` 之後，例如 `exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@" --mcp-config /etc/claude/mcp.json`。若要在工作階段所傳遞的伺服器於工作階段中途更新時，讓該檔案中的伺服器持續執行，請讓您的包裝腳本將[完整環境](#wrapper-scripts)傳遞給子程序，如同 `exec` 的做法。在 v2.1.299 之前，該檔案中的 stdio、HTTP 和 SSE 伺服器會在第一次未列出它們的此類更新時關閉。

當您的組織啟用連接器傳遞時，Anthropic 的控制平面會透過伺服器提供的 MCP 設定，將您在 claude.ai 上設定的連接器傳遞給以互動方式建立的工作階段，並經由 `api.anthropic.com` 路由。以程式化方式建立的工作階段（例如 [CLI 派送](https://code.claude.com/docs/zh-TW/self-hosted-environments-testing.md#run-the-test-loop)）不會接收連接器傳遞；請改為透過本節列出的任何其他來源為它們提供 MCP 伺服器。子程序的 OAuth token 不具備直接擷取連接器的範圍，因此子程序本身不會嘗試該擷取；傳遞是由伺服器驅動的。

> [!NOTE]
>
> 在已接收連接器的工作階段中，來自主機 `.claude.json` 或儲存庫 `.mcp.json` 的同名伺服器不會被連線。若要同時使用兩者，請為您的伺服器取不同的名稱。

`settings.json` 不包含 MCP 伺服器定義，且設定 schema 中沒有頂層的 `mcpServers` 欄位。在受管設定中，請改用 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 鍵來提供伺服器。

工作階段會繼承 runner 的環境，因此請在該處設定 [`ENABLE_TOOL_SEARCH`](https://code.claude.com/docs/zh-TW/mcp#scale-with-mcp-tool-search)，以控制 runner 產生的每個工作階段的 MCP 工具搜尋；各個值的說明請參閱 MCP 頁面。

### 在第一個回合前等待 MCP 伺服器

自架的工作階段會在兩個不同的時間點，短暫等待仍在連線中的 MCP 伺服器。錯過等待的伺服器，其工具在第一個回合開始時將不可用，之後無需您採取任何動作即會變為可用。這兩次等待如下：

* **工作階段啟動**：在首次取得工具清單之前，工作階段預設最多會等待 5 秒，等待項目中設定了 [`alwaysLoad: true`](https://code.claude.com/docs/zh-TW/mcp#exempt-a-server-from-deferral) 的 HTTP 或 SSE 伺服器；若您在 runner 的環境中設定了 [`MCP_CONNECTION_NONBLOCKING=0`](https://code.claude.com/docs/zh-TW/env-vars)，則會等待所有伺服器。否則，HTTP 和 SSE 伺服器會在背景中連線。工作階段在此等待期間，初始化速度會較慢。[`MCP_CONNECT_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 可變更 5 秒的預設值。
* **第一個回合**：在訊息抵達後，第一個回合最多會等待 2 秒，等待仍在連線中的 stdio 伺服器。工作階段在此等待期間，第一個回覆會較慢。若要變更此等待的時間長度，請在 runner 的環境中設定 [`CLAUDE_CODE_MCP_STARTUP_WAIT_MS`](https://code.claude.com/docs/zh-TW/env-vars)。它不會變更此等待涵蓋哪些伺服器。需要 Claude Code v2.1.274 或更新版本。

`claude mcp add` 沒有 `alwaysLoad` 旗標。若要設定此鍵，請改用 `claude mcp add-json` 加入伺服器，它會在伺服器的 JSON 中接受此鍵並將其寫入 `.claude.json`。在您的 Dockerfile 中：

```dockerfile theme={null}
RUN claude mcp add-json core '{"type":"http","url":"https://mcp.example.com/mcp","alwaysLoad":true}' --scope user
```

如果伺服器的工具在之後的回合中也沒有出現，請依照 [MCP 伺服器](#mcp-servers)中的說明，檢查該伺服器是否有傳達到工作階段。

### 關閉內建工作階段工具

Anthropic 的控制平面會將其自有的 MCP 伺服器（名為 Claude Code Remote）附加到雲端工作階段。Claude 使用該伺服器的工具來建立[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)、啟動並引導其他雲端工作階段、附加更多儲存庫，以及追蹤 pull request 活動。

若要關閉整個伺服器，請在您的設定中新增[伺服器層級的拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#mcp)。控制平面會依工作階段的建立方式，以三個名稱之一註冊該伺服器。Claude Code 會完全比對規則中的名稱（包括大小寫），因此請如下所示為每個名稱各寫一條規則：

```json theme={null}
{
  "permissions": {
    "deny": [
      "mcp__Claude_Code_Remote",
      "mcp__claude-code-remote",
      "mcp__bf7c680d-5fdc-5ef4-b4a0-abadb619bf0a"
    ]
  }
}
```

指名整個伺服器的規則也會涵蓋該伺服器日後新增的工具。若要關閉單一工具並保留其餘工具，請在每條規則後附加兩個底線和工具名稱，例如 `mcp__Claude_Code_Remote__add_repo`。若要完全阻止伺服器連線，而不只是移除其工具，請改為將這三個名稱（不含 `mcp__` 前綴）作為 `serverName` 項目加入 [`deniedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists) 下。

將規則放在[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中，即可在不變更 runner 的情況下套用到工作階段，或放在 runner 上的 `~/.claude/settings.json` 中。在[將模型請求傳送至 Bedrock 或 Agent Platform](#send-model-requests-to-bedrock-or-agent-platform) 的 runner 上，請使用該檔案，因為伺服器受管設定不會套用到這些工作階段。[權限與工具核准](#permissions-and-tool-approval)說明了 runner 上的設定如何套用到工作階段。

若要確認規則已生效，請在該環境上啟動一個工作階段，並請 Claude 列出其 MCP 工具。Claude Code 會從 Claude 的上下文中移除被拒絕的工具，因此被拒絕的工具不會出現在其回答中。

## 提示會話推送其工作

Anthropic 託管的會話執行 [`Stop` 掛鉤](https://code.claude.com/docs/zh-TW/hooks#stop)，Claude Code 掛鉤在 Claude 完成回應時執行，提示 Claude 提交並推送其工作。執行器不安裝一個。沒有它，以未提交變更結束的會話只在執行器的磁碟上留下該工作，claude.ai/code 中的**建立 PR** 按鈕保持非活動狀態，直到分支存在於遠端。

下面的參考實現有兩個部分。將設定塊合併到執行器主機上的 `~/.claude/settings.json` 中，執行器將其植入每個會話，並將指令碼保存為執行器主機上的 `~/.claude/hooks/stop-hook-nudge.sh` 並使其可執行：

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "timeout": 10,
            "command": "\"$CLAUDE_CONFIG_DIR/hooks/stop-hook-nudge.sh\""
          }
        ]
      }
    ]
  }
}
```

```sh theme={null}
#!/bin/sh
# Stop-hook reference implementation for self-hosted runners.
#
# Nudges Claude once per turn if the project directory has uncommitted
# changes OR unpushed commits, so work isn't lost when an idle session
# is released and so the "Create PR" button on claude.ai/code lights up.
#
# Runner-level (no repo changes): drop this file at ~/.claude/hooks/ on
# the runner host and merge the accompanying Stop-hook settings block
# into ~/.claude/settings.json — the runner seeds both into every session.
# Repo-level alternative: commit to <repo>/.claude/hooks/ and change the
# settings.json command path to $CLAUDE_PROJECT_DIR/.claude/hooks/.
#
# stdin: hook JSON payload (see https://code.claude.com/docs/en/hooks)
# stdout: {"decision":"block","reason":"..."} to nudge, or nothing to allow stop.

# Re-entry guard: the harness sets stop_hook_active=true when re-invoking
# the Stop hook after a block. Bail so we only nudge once per turn. The
# harness emits compact JSON (no space after the colon), which this
# pattern relies on; use jq if you need a whitespace-tolerant check.
in=$(cat)
case "$in" in *'"stop_hook_active":true'*) exit 0 ;; esac

d="$CLAUDE_PROJECT_DIR"

# Hardening: this script runs outside Claude Code's Bash sandbox, so its git
# calls skip some features that can start a program named in the checkout's
# git settings. They don't skip them all, so don't count on the sandbox alone.
GIT_OPTIONAL_LOCKS=0
export GIT_OPTIONAL_LOCKS
git() { command git -c core.fsmonitor= -c core.hooksPath=/dev/null "$@"; }

# Not a git repo → nothing to nudge.
git -C "$d" rev-parse --git-dir >/dev/null 2>&1 || exit 0

# No remote → "push to the remote" is unsatisfiable; bail.
[ -z "$(git -C "$d" remote 2>/dev/null)" ] && exit 0

# Uncommitted changes (staged, unstaged, or untracked). Exclude .claude/
# entirely — operator-seeded settings and CLI-written runtime state
# (scheduler lock, worktrees, routine state) live there and neither is
# "uncommitted work" the model needs to push.
s=$(git -C "$d" status --porcelain --ignore-submodules=dirty -- . ':(exclude).claude/' 2>/dev/null)
if [ -n "$s" ]; then
  printf '{"decision":"block","reason":"There are uncommitted changes in the repository. Please commit and push these changes to the remote branch."}'
  exit 0
fi

# Unpushed commits. Count commits on HEAD not reachable from any
# remote-tracking ref or FETCH_HEAD. This works uniformly for:
#   - init+fetch checkouts (runner default: only FETCH_HEAD exists)
#   - clone-based checkouts (origin/* exist)
#   - the runner default: the child starts on the session's outcome
#     branch, which the runner creates after checkout
#   - detached HEAD, when a custom setup skips that branch creation
# With no reference point at all (never fetched), stay silent rather
# than false-positive on a read-only turn.
base=""
git -C "$d" rev-parse --verify -q FETCH_HEAD >/dev/null && base="FETCH_HEAD"
if [ -z "$base" ] && [ -z "$(git -C "$d" for-each-ref --count=1 refs/remotes/origin 2>/dev/null)" ]; then
  exit 0
fi
# shellcheck disable=SC2086  # $base is either "" or "FETCH_HEAD", intentional word-split
unpushed=$(git -C "$d" rev-list HEAD --not $base --remotes=origin --count 2>/dev/null) || unpushed=0
if [ "$unpushed" -gt 0 ]; then
  branch=$(git -C "$d" symbolic-ref --short -q HEAD)
  if [ -n "$branch" ]; then
    # $branch is attacker-influenced — git-check-ref-format(1) allows `"`
    # in ref names. `\` is forbidden (rule 10) but escaped anyway as cheap
    # defense-in-depth.
    # Escape JSON metacharacters before interpolating into the hand-built
    # payload so a branch like x","continue":false can't inject keys into
    # the hook-output JSON the harness parses. $unpushed is safe — the
    # -gt guard above rejects anything that isn't a plain integer.
    branch_esc=$(printf '%s' "$branch" | sed 's/\\/\\\\/g; s/"/\\"/g')
    printf '{"decision":"block","reason":"There are %s unpushed commit(s) on branch '\''%s'\''. Please push these changes to the remote repository."}' "$unpushed" "$branch_esc"
  else
    printf '{"decision":"block","reason":"There are %s unpushed commit(s) on a detached HEAD. Please create a branch and push it to the remote repository."}' "$unpushed"
  fi
  exit 0
fi

exit 0
```

此 hook 會在工作階段結束前提示 Claude 提交並推送，並在目錄不是 git 儲存庫或沒有遠端時保持沉默。若工作階段包含多個儲存庫，請參閱 [`$CLAUDE_PROJECT_DIR` 所指的目錄](#repository-settings-in-sessions-with-several-repositories)。

Stop hook 只會提示 Claude。若要讓提交與推送順利完成，請設定：

* **git 身分**：在執行器映像中設定 `user.name` 與 `user.email`，或使用 [`--configure-git`](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#let-the-runner-configure-git) 啟動執行器
* **推送憑證**：使用 [Anthropic 管理的 git](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)，或依照[在映像中附帶 git 設定](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#ship-git-config-in-your-image)所述提供憑證
* **針對恢復的工作階段**：在環境中的每個執行器上設定 [`--push-outcome-on-release`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)。如此一來，恢復的工作階段便會從 Claude 推送到該工作階段分支的提交開始。關於此旗標的限制，請參閱[恢復的工作階段會遺失未推送的工作](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#resumed-sessions-lose-unpushed-work)。

Stop hook 每個回合最多只會提示一次。若提交或推送失敗，該回合仍會結束。請在工作階段中尋找 git 的錯誤訊息，並修正其指出的問題。

在大型 checkout 上，請提高 Stop hook 設定中的 `timeout`，並重新啟動執行器。指令碼的 `git status` 會略過 `core.fsmonitor`，因此耗時可能超過其中設定的 10 秒。逾時的 hook 會在不提示的情況下結束該回合。

### 子模組與 Stop hook

Stop hook 檢查的是每個子模組所在的提交，而非其中的檔案：

* **子模組中的新提交**：在父儲存庫記錄該提交之前，Claude 都會被提示，即使 `.gitmodules` 為該子模組設定了 `ignore = all` 也是如此
* **子模組中未提交的檔案**：Claude 不會被提示，因此該工作只會留在執行器的磁碟上
* **子模組中未推送的提交**：Stop hook 不會檢查這些提交是否已推送，因此父儲存庫可能會指向其他人都無法擷取的提交

### 替換較早版本的 Stop hook 指令碼

在您的 `stop-hook-nudge.sh` 副本中搜尋 `GIT_OPTIONAL_LOCKS`。若找不到，表示您使用的是較早的版本。請在所有安裝位置將其替換為[目前的指令碼](#prompt-sessions-to-push-their-work)，然後重新啟動執行器。請保留您的 Stop hook 設定，僅在大型 checkout 上提高 `timeout`。

* **時機**：若您的工作階段在啟用 [Bash 沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)的情況下執行，請立即替換。否則，請在下次建置映像或重新啟動執行器時替換。
* **變更內容**：子模組中未提交的檔案不再提示 Claude。而在 `.gitmodules` 中標記為 `ignore = all` 的子模組若有新提交，現在則會提示。

> [!WARNING]
>
> hook 在 Bash 沙箱之外執行，因此目前指令碼的 git 呼叫會略過某些可能啟動 checkout 之 git 設定中所指定程式的 git 功能。但並未全部略過。請勿僅依賴沙箱，並依照[強化您的部署](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)所述隔離工作階段。

## 權限和工具核准

自託管工作階段沒有連接的終端機，因此未回應的權限提示會使回合停滯，直到使用者在 UI 中回應。Anthropic 的控制平面會隨工作 payload 傳送每個工作階段的工具清單和權限規則；預設設定會預先核准例行的工具呼叫（包括 `Bash`），而雲端工作階段[無論模式為何都會預先核准檔案編輯](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)。未被任何規則預先核准的呼叫會透過工作階段 UI 提示。

> [!NOTE]
>
> 僅在工作階段容器以[預設拒絕網路出口](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#default-deny-egress)執行，且已套用[強化部分](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)其餘措施的環境上固定自動模式。無論是在預設預先核准的工具集還是自動模式下，例行工具呼叫（包括 `Bash` 網路請求）都會在無人工介入的情況下執行，因此網路邊界是限制這些呼叫可到達位置的關鍵。

若要無論控制平面傳送什麼都將提示降到最低，請從您的包裝指令碼或 [`command` hook](#command) 固定[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)。自動模式讓工作階段無需例行權限提示即可執行：一個獨立的分類器模型會在操作執行前進行審查，並阻擋其拒絕的操作，而明確的詢問規則仍會強制提示；權限模式頁面說明了分類器檢查的內容。執行器在呼叫包裝指令碼前會附加伺服器計算的旗標，而對於單值旗標（例如 `--permission-mode`），解析器會採用最後一次出現的值，因此您在 `"$@"` 之後附加的旗標會覆寫伺服器傳送的值：

```bash theme={null}
#!/bin/bash
exec "$CLAUDE_RUNNER_CLAUDE_BIN" "$@" --permission-mode auto
```

若要改為預先核准特定工具，請附加 `--allowed-tools` 及您的規則，例如 `--allowed-tools "Bash(bazel *) Bash(yarn *) mcp__internal__*"`。清單旗標（例如 `--allowed-tools` 和 `--disallowed-tools`）會在多次出現時累加，而非覆寫，因此您的規則會套用在控制平面傳送的任何規則之上。若要縮小範圍，請附加 `--disallowed-tools`，即使其他規則允許某工具，它也會拒絕該工具。

### 如何組合每個工作階段的設定

執行器為每個工作階段提供其專屬的設定目錄，並以執行器在啟動時擷取一次的主機 `~/.claude/` 快照植入：您執行器映像中的 `settings.json`、`CLAUDE.md`、hook、agent、命令和 skill 會作為使用者層級基準套用至每個工作階段。如果您在執行中的主機上變更設定，變更僅在您重新啟動執行器後生效。

設定 `SELF_HOSTED_RUNNER_HOST_CONFIG_DIR` 以從不同路徑植入，或將其指向空目錄以停用植入。

工作階段也會讀取以下設定檔：

* **專案設定**：在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串以外，儲存庫提交的 `.claude/settings.json` 會疊加於使用者層級基準之上。在包含多個儲存庫的工作階段中，[最多只有一個儲存庫的檔案會生效](#repository-settings-in-sessions-with-several-repositories)。
* **受管設定**：工作階段會從執行器映像中的標準系統路徑讀取 [`managed-settings.json`](https://code.claude.com/docs/zh-TW/settings#where-settings-live)。關於其設定鍵是否與[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)一併套用，請參閱 [Claude Code 如何組合受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)。

關於這些來源的套用順序，請參閱[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。

當 Anthropic 的控制平面為工作階段提供 [Claude Code hook](https://code.claude.com/docs/zh-TW/hooks.md) 時，執行器會將其與您自己的設定並存安裝，而非覆寫您的設定。需要 Claude Code v2.1.229 或更新版本；較舊的執行器會忽略提供的 hook。提供的 hook 會執行 `python3`，因此請在您的[執行器映像](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#build-the-runner-image)中安裝 `python3`。

* **放置位置**：執行器會將每個提供的 hook 指令碼寫入工作階段設定目錄中保留的 `hooks/.ccr-launcher/` 子目錄，並在一個獨立的設定檔中註冊這些指令碼，再透過 `--settings` 將該檔案傳遞給工作階段，而植入的 `settings.json` 和您位於 `hooks/<name>` 的指令碼則保持不變。執行器會為每個工作階段重新建立該保留子目錄，且不會將主機上 `~/.claude/hooks/.ccr-launcher/` 的內容植入工作階段。
* **撰寫者**：控制平面以其自身部署中的固定常數填入這些指令碼，絕不來自個別工作階段或第三方輸入。
* **仍受何者管控**：透過 `--settings` 傳遞的 hook 會進入一般的合併 hook 設定，而非受管層級，因此您的受管設定仍然適用。`disableAllHooks` 會停用它們，且它們不屬於 [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly) 保持載入的類別。

當使用者啟動自己的工作階段時，Claude Code 會將[其 claude.ai 帳戶已啟用的 skill](https://code.claude.com/docs/zh-TW/skills.md#skills-in-cowork-and-cloud-sessions) 下載至該工作階段的設定目錄。[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)的執行不會取得其擁有者的 skill，而[將模型請求傳送至 Bedrock 或 Agent Platform](#send-model-requests-to-bedrock-or-agent-platform) 的工作階段則不會下載任何 skill。若這些工作階段需要某個 skill，請將其加入您的執行器映像，或在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)討論串以外將其提交至儲存庫的 `.claude/skills/`。

在 [Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段以外，自託管環境中的工作階段預設會關閉[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)。若有應跨工作階段延續的指令，請使用執行器映像或儲存庫中的 `CLAUDE.md`。

執行器對主機 `~/.claude/` 的快照不包含 `projects/` 目錄。自動記憶的預設儲存位置就位於該目錄下。如果您將記憶檔案放在那裡，執行器不會將其植入工作階段，這些檔案也不會開啟自動記憶。

### 停止無法擷取伺服器受管設定的工作階段

若要讓擷取[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的工作階段在擷取失敗時不啟動，請在執行器映像中的 [`managed-settings.json`](https://code.claude.com/docs/zh-TW/settings#where-settings-live) 將 [`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh) 設為 `true`。若 Anthropic 的 API 回覆您的組織沒有伺服器受管設定，這也算作擷取成功。

在加入此設定鍵之前，請先確認該環境是否執行 Claude Tag 頻道工作階段，或是否將模型請求傳送至 Bedrock 或 Agent Platform：

* **Claude Tag 頻道工作階段**：對於擁有者[將 Claude Tag 頻道路由至](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-the-environment-a-claude-tag-channel-uses)的環境，請勿在其執行器上設定此設定鍵。Anthropic 的 API 會拒絕這些工作階段對伺服器受管設定的請求，因此設定此設定鍵後，這些工作階段將無法啟動。請將它們的規則放在執行器映像的 `managed-settings.json` 中，[它們仍會讀取該檔案](https://code.claude.com/docs/zh-TW/managed-settings.md#where-and-when-a-policy-applies)。若要為其他工作階段使用此設定鍵，請在另一個獨立的環境中執行那些工作階段。
* **Bedrock 或 Agent Platform**：使用這些提供者的工作階段[不會擷取伺服器受管設定](#what-differs-from-sessions-on-the-anthropic-api)，因此無論您是否設定此設定鍵，它們都會啟動。請改為從同一個 `managed-settings.json` 強制執行您的規則。

以下 `managed-settings.json` 設定了此設定鍵：

```json managed-settings.json theme={null}
{
  "forceRemoteSettingsRefresh": true
}
```

即使您也在 claude.ai 管理主控台中設定了此設定鍵，仍請在該檔案中設定。新的工作階段沒有您伺服器受管設定的[快取副本](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)，因此如果您只在主控台中設定此設定鍵，工作階段此時尚未取得它。若其擷取隨後失敗，工作階段會在沒有這些設定的情況下執行，直到之後的擷取成功為止。

若要確認工作階段未啟動是因為設定擷取失敗，請查看工作階段中 [Claude Code 的最後輸出](#keep-stdin-and-file-descriptor-3-attached)或執行器的日誌。其中會包含 `Your organization requires remote managed settings to load, but they could not be loaded.`

### 包含多個儲存庫之工作階段中的儲存庫設定

在[專案](https://code.claude.com/docs/zh-TW/claude-projects.md#what-threads-pick-up-from-your-repositories)中的討論串裡，無論討論串在何處啟動，都不會有任何儲存庫的 `.claude/settings.json` 作為專案設定生效，也不會載入任何儲存庫的 `.mcp.json` 或 skill。若要為這些討論串提供 skill，請將其加入您的執行器映像。

在其他任何包含多個儲存庫的工作階段中，Claude Code 會從工作階段啟動時所在的目錄讀取專案設定，因此最多只有一個儲存庫的 `.claude/settings.json` 會作為專案設定生效。在其他儲存庫檔案中定義的 hook 不會執行，其中的拒絕規則不會套用，其 `env` 也不會被設定。

* **`--capacity 1`（預設值）搭配內建簽出**：工作階段會在其儲存庫清單中的第一個儲存庫啟動。該儲存庫的 `.claude/settings.json` 會作為專案設定生效，其 `.mcp.json` 也會載入，其他儲存庫的則不會。
* **`--capacity` 大於一，或使用 [`checkout` hook](#checkout)**：工作階段會在包含各簽出內容的個別工作階段目錄中啟動。沒有任何儲存庫的 `.claude/settings.json` 會作為專案設定生效，沒有任何儲存庫的 `.mcp.json` 會載入，且 hook 命令中的 [`$CLAUDE_PROJECT_DIR`](https://code.claude.com/docs/zh-TW/hooks#reference-scripts-by-path) 為該目錄，而非某個簽出內容。

無論工作階段在何處啟動，每個儲存庫的 `CLAUDE.md` 都會載入。在專案討論串以外，其 skill 也會載入。執行器會將每個儲存庫作為[額外目錄](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)傳遞給 Claude Code，因此 Claude Code 也會從每個儲存庫的 `.claude/settings.json` 讀取 `enabledPlugins` 和 `extraKnownMarketplaces` 設定鍵。

若要在每個工作階段中執行 hook 或套用權限規則，請將其放在執行器主機上的 `~/.claude/settings.json` 中。無論工作階段在何處啟動，執行器都會[將主機檔案植入每個工作階段](#how-each-session’s-config-is-assembled)。在 `Read` 或 `Edit` 規則中，請將路徑寫成 `//` 絕對路徑或 `~/` 相對於家目錄的[模式](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)，因為其他模式會以設定來源或目前目錄為基準。

### 儲存庫提交的權限規則

請勿在儲存庫提交的 `permissions.allow` 中放入單獨的 `"Edit"`、`"Write"` 或 `"NotebookEdit"` 項目。單獨的檔案工具規則會不論路徑地比對該工具，授予主機上任何位置的寫入權，而不僅限於工作區，因此執行器的寫入範圍限制防護會對該工作階段發出警示；若使用 [`--confine-repo-settings enforce`](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference#runner-cli-flags)，它會拒絕啟動該工作階段，而非記錄後繼續。請參閱[強化部分](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#harden-your-deployment)。

儲存庫完全不需要檔案工具規則：雲端工作階段[無論模式為何都會預先核准檔案編輯](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)。如果您確實提交了規則，請將其範圍限定於工作區，例如 `"Edit(/**)"`；單一前導斜線是相對於專案根目錄，也就是工作階段的工作區。單獨的檔案工具規則可以放在操作員的主機層級 `settings.json` 中，因為該檔案並非由儲存庫提交。

`defaultMode` 為 `auto` 的設定僅在映像層級或使用者層級設定檔中才會生效，因此簽出的儲存庫無法自行授予自動模式。有關雲端工作階段接受的模式及完整規則語法，請參閱[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。

## 接下來

* [參考](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md)：每個 CLI 旗標、環境變數和度量
* [驗證會話身份](https://code.claude.com/docs/zh-TW/self-hosted-environments-identity.md)：驗證來自執行器外部服務的會話權杖
