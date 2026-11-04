<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/errors | lastmod: 2026-11-04 | section: Build with Claude Code / Troubleshooting -->
> 來源：https://code.claude.com/docs/zh-TW/errors（官方 zh-TW，lastmod 2026-11-04）｜分類：Build with Claude Code › Troubleshooting｜EN 摘要：Look up Claude Code runtime error messages with what each one means and how to fix it.

# 錯誤參考

> 查詢 Claude Code 執行時錯誤訊息，了解每個錯誤的含義及修復方法。

本頁列出 Claude Code 顯示的執行時錯誤及如何從每個錯誤中復原，以及當回應似乎有問題但沒有錯誤時要檢查的內容。如需安裝錯誤（例如 `command not found` 或設定期間的 TLS 失敗），請參閱[疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md)。

除了[包裝程式和 IDE 錯誤](#wrapper-and-ide-errors)（由啟動程式列印而非 Claude Code 本身列印）外，這些錯誤和復原命令適用於 CLI、[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)和[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，因為這三者都包裝相同的 Claude Code CLI。如需其他使用介面特定的問題，請參閱該使用介面頁面上的疑難排解部分。

> [!NOTE]
>
> Claude Code 呼叫 Claude API 以取得模型回應，因此大多數執行時錯誤對應到基礎 API 錯誤代碼。本頁涵蓋每個錯誤在 Claude Code 中的含義及如何復原。如需原始 HTTP 狀態代碼定義，請參閱 [Claude Platform 錯誤參考](https://platform.claude.com/docs/en/api/errors)。

## 找到您的錯誤

將您看到的訊息與下面的部分進行比對。

| 訊息 | 部分 |
| :- | :- |
| `API Error: 500 Internal server error` | [伺服器錯誤](#api-error-500-internal-server-error) |
| `API Error: Repeated 529 Overloaded errors` | [伺服器錯誤](#api-error-repeated-529-overloaded-errors) |
| `Opus is experiencing high load` / `Fable is experiencing high load` | [伺服器錯誤](#api-error-repeated-529-overloaded-errors) |
| `Request timed out` | [伺服器錯誤](#request-timed-out)，或如果訊息提及您的網路連線，則為[網路](#unable-to-connect-to-api) |
| `API Error: No response from API` | [伺服器錯誤](#no-response-from-api) |
| `API Error: Stream idle timeout - no chunks received` | [串流閒置監控](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)，或在 Claude apps gateway 後方時為[長時間思考導致代理伺服器逾時](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#long-thinking-ends-in-proxy-timeouts) |
| `Server error mid-response. The response above may be incomplete.` | [伺服器錯誤](#the-response-above-may-be-incomplete) |
| `Connection lost mid-response` / `Your computer went to sleep mid-response` / `The response stopped arriving` | [伺服器錯誤](#the-response-above-may-be-incomplete) |
| `Connection closed mid-response` / `Response stalled mid-stream` | [伺服器錯誤](#the-response-above-may-be-incomplete) |
| `Part of the response never arrived` / `The response stream was malformed` | [伺服器錯誤](#the-response-above-may-be-incomplete) |
| `API Error: Content block not found` / `API Error: Content block already closed` / `API Error: Stream event unreadable` | [伺服器錯誤](#the-response-above-may-be-incomplete) |
| `Connection lost before a response was produced` / `Your computer went to sleep before a response was produced` / `The response stalled before a response was produced` | [自動重試](#automatic-retries) |
| `Connection closed while thinking` / `Response stalled while thinking` | [自動重試](#automatic-retries) |
| `Connection lost while your computer was asleep` | [自動重試](#automatic-retries) |
| `The model's tool call could not be parsed (retry also failed).` | [自動重試](#automatic-retries) |
| `<model> is temporarily unavailable, so auto mode cannot determine the safety of...` | [伺服器錯誤](#auto-mode-cannot-determine-the-safety-of-an-action) |
| `Auto mode could not evaluate this action and is blocking it for safety` | [伺服器錯誤](#auto-mode-cannot-determine-the-safety-of-an-action) |
| `Not run · auto mode's check had no usable answer` | [伺服器錯誤](#auto-mode-cannot-determine-the-safety-of-an-action) |
| `Auto mode classifier transcript exceeded context window` | [伺服器錯誤](#auto-mode-cannot-determine-the-safety-of-an-action) |
| `Agent aborted: auto mode classifier request refused by the safety safeguard` | [伺服器錯誤](#auto-mode-cannot-determine-the-safety-of-an-action) |
| `The server-side auto mode classifier gave no verdict` | [伺服器錯誤](#the-server-returned-no-safety-verdict) |
| `<tool> was not reviewed and did not run: the conversation is too long for auto mode's classifier` | [伺服器錯誤](#was-not-reviewed-and-did-not-run) |
| `Auto mode is unavailable — the server returned no safety verdict for the last 10 responses` | [伺服器錯誤](#the-server-returned-no-safety-verdict) |
| `Agent terminated early due to an API error` | [伺服器錯誤](#agent-terminated-early-due-to-an-api-error) |
| `You've hit your session limit` / `You've hit your weekly limit` / `You've hit your Opus limit` / `You've hit your Sonnet limit` | [用量上限](#youve-hit-your-session-limit) |
| `Usage credits required for 1M context` | [用量上限](#usage-credits-required-for-1m-context) |
| `the prompt to confirm went unanswered — nothing was sent` | [用量上限](#the-prompt-to-confirm-went-unanswered) |
| `Server is temporarily limiting requests` | [用量上限](#server-is-temporarily-limiting-requests) |
| `Request rejected (429)` | [用量上限](#request-rejected-429) |
| `Credit balance is too low` | [用量上限](#credit-balance-is-too-low) |
| `You've hit your monthly spend limit` / `You've hit your individual spend limit` / `You've hit your org's monthly spend limit` / `You've hit your channel's monthly spend limit` / `You've hit your team's shared budget` / `You've hit your individual usage limit` | [用量上限](#youve-hit-your-monthly-spend-limit) |
| `Could not update your spend limit` | [用量上限](#could-not-update-your-spend-limit) |
| `spend limit reached` / `spend limit unavailable` | [用量上限](#spend-limit-reached) |
| `Not logged in · Please run /login` | [身分驗證](#not-logged-in) |
| `Couldn't save your login` | [身分驗證](#couldnt-save-your-login) |
| `Authentication required · Sign in again to continue` | [身分驗證](#not-logged-in) |
| `Could not resolve authentication method` | [身分驗證](#could-not-resolve-authentication-method) |
| `Invalid API key` | [身分驗證](#invalid-api-key) |
| `Your apiKeyHelper script is failing` | [身分驗證](#your-apikeyhelper-script-is-failing) |
| `Claude Code didn't send your claude.ai login, because the API key helper your administrator set isn't in effect` | [身分驗證](#claude-code-didnt-send-your-claude-ai-login) |
| `Invalid auth token · Fix external auth token` | [身分驗證](#invalid-request-header-value) |
| `Invalid ANTHROPIC_CUSTOM_HEADERS · Fix the environment variable` | [身分驗證](#invalid-request-header-value) |
| `Invalid request header from the environment · Fix the environment variable` | [身分驗證](#invalid-request-header-value) |
| `This organization has been disabled` | [身分驗證](#this-organization-has-been-disabled) |
| `Your organization has disabled API key authentication` | [身分驗證](#your-organization-has-disabled-api-key-authentication) |
| `Your organization has disabled Claude subscription access` | [身分驗證](#your-organization-has-disabled-claude-subscription-access) |
| `Scheduled tasks are off for your organization` | [身分驗證](#routines-are-disabled-by-your-organizations-policy) |
| `Routines are off for your organization` | [身分驗證](#routines-are-disabled-by-your-organizations-policy) |
| `Remote Control is only available when using Claude via api.anthropic.com` | [身分驗證](#remote-control-requires-the-anthropic-api) |
| `OAuth token refresh failed — run /login to re-authenticate` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `JWT refresh failed: no OAuth token — run /login` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `Claude.ai login expired` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `Claude.ai login was rejected — run /login, then /remote-control` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `OAuth token unavailable — run /login to restore Remote Control` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `Signed out of Claude — run /login, then /remote-control` | [身分驗證](#remote-control-couldnt-refresh-your-login) |
| `Remote Control could not renew this computer's connection` | [身分驗證](#remote-control-could-not-renew-this-computers-connection) |
| `signed-in claude.ai account or organization changed on this machine` | [身分驗證](#remote-control-stopped-because-the-signed-in-account-changed) |
| `Remote Control stopped — the app running this session is now signed in to a different Claude account` | [身分驗證](#remote-control-stopped-because-the-app-running-the-session-signed-out-or-switched-accounts) |
| `Remote Control stopped — the app running this session is signed out of Claude` | [身分驗證](#remote-control-stopped-because-the-app-running-the-session-signed-out-or-switched-accounts) |
| `Couldn't verify your organization's policy for remote control` | [疑難排解 Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#couldnt-verify-your-organizations-policy-for-remote-control) |
| `Remote Control is disabled by your organization's policy` | [疑難排解 Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#remote-control-is-disabled-by-your-organizations-policy) |
| `Remote Control was turned off by your organization's policy` | [疑難排解 Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#remote-control-was-turned-off-by-your-organizations-policy) |
| `OAuth token revoked` / `OAuth token has expired` | [身分驗證](#oauth-token-revoked-or-expired) |
| `Failed to authenticate: OAuth token revoked` | [身分驗證](#oauth-token-revoked-or-expired) |
| `Your account does not have access to Claude. Please login again or contact your administrator.` | [身分驗證](#oauth-token-revoked-or-expired) |
| `API Error: 401 Invalid authentication credentials` | [身分驗證](#api-error-401-invalid-authentication-credentials) |
| `Login expired · Please run /login` | [身分驗證](#login-expired) |
| `The browser can't return the sign-in to Claude Code automatically` | [身分驗證](#couldnt-start-the-local-sign-in-listener) |
| `Couldn't start the local listener that receives the browser sign-in. Try again.` | [身分驗證](#couldnt-start-the-local-sign-in-listener) |
| `Failed to start OAuth callback server` | [身分驗證](#failed-to-start-oauth-callback-server) |
| `Claude login not accepted · Run /login, then try again` | [身分驗證](#claude-login-not-accepted) |
| `Artifacts need a claude.ai login` | [身分驗證](#artifacts-need-a-claude-ai-login) |
| `Not signed in to the Cloud gateway — run /login.` | [身分驗證](#administrator-policy-requires-a-cloud-gateway-sign-in) |
| `Administrator policy requires a Cloud gateway sign-in on this machine` | [身分驗證](#administrator-policy-requires-a-cloud-gateway-sign-in) |
| `Failed to authenticate: OAuth session expired and could not be refreshed` | [身分驗證](#login-expired) |
| `Could not refresh your login because another Claude Code process is refreshing it` | [身分驗證](#could-not-refresh-your-login) |
| `Failed to refresh OAuth token: another Claude Code process is refreshing it or exited mid-refresh` | [身分驗證](#could-not-refresh-your-login) |
| `Your account is on hold and can't use Claude Code. View details or appeal: https://claude.ai/restricted` | [身分驗證](#your-account-is-on-hold) |
| `Your account is on hold and can't sign in to Claude Code. View details or appeal: https://claude.ai/restricted` | [身分驗證](#your-account-is-on-hold) |
| `Anthropic profile login expired · Re-authenticate your Anthropic profile` | [身分驗證](#anthropic-profile-login-expired) |
| `Login expired · Run /login to sign in again, or re-authenticate your Anthropic profile` | [身分驗證](#anthropic-profile-login-expired) |
| `Anthropic profile login expired · Run /login to use your claude.ai account instead, or re-authenticate the profile` | [身分驗證](#anthropic-profile-login-expired) |
| `does not meet scope requirement user:profile` | [身分驗證](#oauth-scope-requirement) |
| `claude.ai rejected the session token` / `session token rejected` | [身分驗證](#claude-ai-rejected-the-session-token) |
| `MCP server "<name>" needs you to sign in again (run /mcp to re-authenticate)` | [身分驗證](#mcp-server-needs-you-to-sign-in-again) |
| `rejected the credential from its headersHelper` / `rejected the Authorization header in its config` | [身分驗證](#mcp-server-needs-you-to-sign-in-again) |
| `(check the helper, then start a new task or chat)` / `(update it, then start a new task or chat)` | [身分驗證](#mcp-credential-rejected-in-cowork) |
| `MCP server "<name>" needs additional permissions (scope: "<scope>") — run /mcp to re-authenticate` | [身分驗證](#mcp-server-needs-you-to-sign-in-again) |
| `MCP server "<name>" requires re-authorization (token expired)` | [身分驗證](#mcp-server-needs-you-to-sign-in-again) |
| `Couldn't read the stored credentials for MCP server "<name>", so the request didn't run` | [身分驗證](#couldnt-read-the-stored-credentials-for-mcp-server) |
| `A request to MCP server "<name>" was sent without your stored credentials` | [身分驗證](#couldnt-read-the-stored-credentials-for-mcp-server) |
| `This server's URL is missing or not a valid URL, so sign-in can't start` | [身分驗證](#mcp-server-url-is-missing-or-not-a-valid-url) |
| `Issuer mismatch in authorization response (RFC 9207)` | [身分驗證](#issuer-mismatch-in-authorization-response) |
| `Refusing to send credentials to non-https token endpoint` / `<short-name> from the MCP SDK for <server-url>` | [身分驗證](#refusing-to-send-credentials-to-non-https-token-endpoint) |
| `Cloud gateway session expired — run /login to reconnect.` | [身分驗證](#cloud-gateway-session-expired) |
| `Cloud gateway <url> no longer accepts this session` | [身分驗證](#cloud-gateway-session-expired) |
| `Sign-in timed out while waiting for you to continue. Try again.` | [身分驗證](#sign-in-timed-out-while-waiting-for-you-to-continue) |
| `AWS credentials expired or invalid` | [身分驗證](#aws-credentials-expired-or-invalid) |
| `AWS authentication failed` | [身分驗證](#aws-authentication-failed) |
| `Google Cloud credentials expired or invalid` | [身分驗證](#google-cloud-credentials-expired-or-invalid) |
| `Google Cloud authentication failed` | [身分驗證](#google-cloud-authentication-failed) |
| `Microsoft Foundry authentication failed` | [身分驗證](#microsoft-foundry-authentication-failed) |
| `Gateway refused the request` | [身分驗證](#gateway-refused-the-request) |
| `Could not load AWS credentials` / `Could not load Google Cloud credentials` | [身分驗證](#could-not-load-aws-or-google-cloud-credentials) |
| `AWS default-chain credential resolve timed out` | [身分驗證](#aws-default-chain-credential-resolve-timed-out) |
| `Timed out after 60s waiting for AWS` | [身分驗證](#bedrock-setup-verification-timed-out-waiting-for-aws) |
| `A request to AWS timed out. Check your network and proxy settings, then try again.` | [身分驗證](#bedrock-setup-verification-timed-out-waiting-for-aws) |
| 在 Google Cloud 的 Agent Platform 上出現的 `Could not load the default credentials` | [身分驗證](#could-not-load-aws-or-google-cloud-credentials) |
| `Unable to connect to API` | [網路](#unable-to-connect-to-api) |
| `Connection refused —` / `Can't reach the API server —` / `No internet route —` / `Couldn't connect through your proxy` / `Connection dropped`，各以括號中的錯誤代碼結尾 | [網路](#unable-to-connect-to-api) |
| 設定期間出現的 `Unable to connect to Anthropic services` | [網路](#unable-to-connect-to-anthropic-services) |
| `Socket is closed` | [網路](#socket-is-closed) |
| `Waiting for API response · will retry in` | [自動重試](#automatic-retries)，或如果持續發生，則為[網路](#unable-to-connect-to-api) |
| `API returned an empty or malformed response` | [網路](#api-returned-an-empty-or-malformed-response) |
| `Streaming response ended before any complete data was received` | [網路](#streaming-response-ended-before-any-complete-data-was-received) |
| `Bedrock streaming response has content-type "..."; expected "application/vnd.amazon.eventstream"` | [網路](#bedrock-streaming-response-has-an-unexpected-content-type) |
| `SSL certificate verification failed` | [網路](#ssl-certificate-errors) |
| 登入或啟動期間出現的 `SSL certificate error (...)` | [網路](#ssl-certificate-errors) |
| `unable to get local issuer certificate` | [網路](#ssl-certificate-errors) |
| 在雲端工作階段或雲端排程任務中出現、帶有 `x-deny-reason: host_not_allowed` 的 `403` | [網路](#host-not-allowed-in-a-cloud-session) |
| `proxy refused the connection` | [網路](#the-proxy-refused-the-connection) |
| 在雲端工作階段中出現、帶有 `GitHub GraphQL is not available from Claude Code sessions` 的 `403` | [GitHub 代理伺服器](https://code.claude.com/docs/zh-TW/cloud-environments.md#github-proxy) |
| `The cloud environments service returned an empty response` / `The cloud environments service returned a response in an unexpected format` | [網路](#the-cloud-environments-service-returned-an-empty-or-unexpected-response) |
| `Failed to fetch session from Sessions API: Failed to fetch session logs` | [網路](#failed-to-fetch-session-from-sessions-api) |
| `Couldn't reconnect to your Remote Control session` | [網路](#couldnt-reconnect-to-your-remote-control-session) |
| `N sessions ended while this machine was offline — the environment was cleaned up on the server and can't be resumed.` | [網路](#sessions-ended-while-this-machine-was-offline) |
| `Couldn't share the transcript.` | [網路](#couldnt-share-the-transcript) |
| `Couldn't send feedback` | [網路](#couldnt-send-feedback) |
| `Feedback payload too large. Try again without the transcript, or shorten the details.` | [網路](#feedback-payload-too-large) |
| `MCP server "<name>" connection timed out. Your computer went to sleep or its clock changed while connecting.` | [網路](#mcp-server-connection-timed-out-during-a-sleep-or-clock-change) |
| `Prompt is too long` / `Input is too long for requested model` | [請求錯誤](#prompt-is-too-long) |
| `Prompt is too long · automatic compaction failed:` | [請求錯誤](#prompt-is-too-long) |
| `Prompt is too long · this conversation is a single exchange` / `A single-exchange conversation cannot be compacted` | [請求錯誤](#prompt-is-too-long) |
| `Context limit reached · /compact or /clear to continue` | [請求錯誤](#prompt-is-too-long) |
| `Context limit reached · /clear to continue` | [請求錯誤](#prompt-is-too-long) |
| 在 Claude apps gateway 工作階段中出現的 `capability_rejected: prompt_too_long` | [請求錯誤](#prompt-is-too-long) |
| 在 Claude apps gateway 工作階段中出現的 `upstream rejected the request` / `request too large for this upstream` | [上游錯誤訊息](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages) |
| 在 Claude apps gateway 工作階段中出現的 `upstream rate limit exceeded` | [上游錯誤訊息](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages) |
| 在 Claude apps gateway 工作階段中出現的 `all upstreams failed (N attempted)` | [上游錯誤訊息](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages) |
| 登入 Claude apps gateway 後出現的 `Claude Code may not be enabled for your organization` | [Claude apps gateway 疑難排解](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#troubleshooting) |
| `/context` 輸出中的 `Context exceeds the ...-token limit by ... tokens` | [請求錯誤](#context-exceeds-the-token-limit) |
| `Request too large` | [請求錯誤](#request-too-large) |
| `Request too large for the API's 32MB request limit` | [請求錯誤](#request-too-large) |
| `Image was too large` | [請求錯誤](#image-was-too-large) |
| `API Error: an image in the conversation could not be processed and was removed` | [請求錯誤](#image-was-too-large) |
| `Unable to resize image` | [請求錯誤](#unable-to-resize-image) |
| `Request rejected as unprocessable by the model` | [請求錯誤](#request-rejected-as-unprocessable-by-the-model) |
| `PDF too large` / `PDF is password protected` / `pdftoppm is not installed` | [請求錯誤](#pdf-errors) |
| `Extra inputs are not permitted` | [請求錯誤](#extra-inputs-are-not-permitted) |
| `API Error: 400 ... tools.N.custom.input_schema: JSON schema is invalid` / `Property keys should match pattern` | [請求錯誤](#tool-input-schema-is-invalid) |
| `Tool "mcp__<server>__<tool>" is not sent to Claude: its name has <N> characters and the API accepts at most 128` | [請求錯誤](#mcp-tool-name-over-128-characters) |
| `tools.N.custom.name: String should have at most 128 characters` | [請求錯誤](#mcp-tool-name-over-128-characters) |
| `tool_use.name: String should have at most 200 characters` | [請求錯誤](#tool-use-name-over-200-characters) |
| `There's an issue with the selected model` | [請求錯誤](#theres-an-issue-with-the-selected-model) |
| `Model ... is not a recognized model id` | [請求錯誤](#model-is-not-a-recognized-model-id) |
| `Model ... not found` | [請求錯誤](#model-not-found) |
| `Couldn't confirm model ... with the API` | [請求錯誤](#couldnt-confirm-model-with-the-api) |
| `API error: ... · model not changed` | [請求錯誤](#api-error-model-not-changed) |
| `Claude Opus is not available with the Claude Pro plan` | [請求錯誤](#claude-opus-is-not-available-with-the-claude-pro-plan) |
| `Claude Code ... does not support this model; version ... or newer is required` | [請求錯誤](#claude-code-does-not-support-this-model) |
| `Claude Code ... is older than the minimum version required by your organization's policy` | [請求錯誤](#claude-code-does-not-support-this-model) |
| `Model ... is restricted by your organization's settings` | [請求錯誤](#model-is-restricted-by-your-organizations-settings) |
| `Model ... is not available. Your organization restricts model selection.` | [請求錯誤](#model-is-restricted-by-your-organizations-settings) |
| `Can't switch to the default model` | [請求錯誤](#cant-switch-to-the-default-model) |
| `Model switch ... blocked by a PreModelSwitch hook` | [請求錯誤](#model-switch-was-blocked-by-a-premodelswitch-hook) |
| `couldn't save it as your default` / `couldn't confirm it was saved as your default` | [請求錯誤](#couldnt-save-it-as-your-default) |
| `is less capable than the current main model` / `Advisor will not activate on the main model` / `cannot advise` | [請求錯誤](#advisor-is-less-capable-than-the-current-main-model) |
| `thinking.type.enabled is not supported for this model` | [請求錯誤](#thinking-type-enabled-is-not-supported-for-this-model) |
| `Effort '<level>' isn't available with thinking turned off on this model` | [請求錯誤](#effort-isnt-available-with-thinking-turned-off) |
| `effort '<level>' is not supported when thinking is disabled` | [請求錯誤](#effort-isnt-available-with-thinking-turned-off) |
| `max_tokens must be greater than thinking.budget_tokens` | [請求錯誤](#thinking-budget-exceeds-output-limit) |
| `Claude's response exceeded the ... output token maximum` | [請求錯誤](#response-exceeded-the-output-token-maximum) |
| `API Error: 400 due to tool use concurrency issues` | [請求錯誤](#tool-use-or-thinking-block-mismatch) |
| `API Error: 400 orphaned tool_result in conversation history` | [請求錯誤](#tool-use-or-thinking-block-mismatch) |
| `API Error: 400 duplicate tool_use ID in conversation history` | [請求錯誤](#tool-use-or-thinking-block-mismatch) |
| `Invalid data in redacted_thinking block` | [請求錯誤](#invalid-data-in-redacted-thinking-block) |
| `[Unsupported tool content removed]` | [請求錯誤](#unsupported-tool-content-removed) |
| `role 'system' must precede an 'assistant' message` | [請求錯誤](#role-system-must-precede-an-assistant-message) |
| `Invalid encrypted_content in search_result block` / `Invalid encrypted_index in text block` / `Failed to decrypt web search result content` | [請求錯誤](#invalid-encrypted-content-in-search-result-block) |
| `Invalid encrypted_stdout in encrypted_code_execution_result block` | [請求錯誤](#invalid-encrypted-content-in-search-result-block) |
| 在恢復的工作階段中每個回合都出現的 `server_tool_use.name: Input should be` | [請求錯誤](#unsupported-tool-content-removed) |
| `<model> can't help with this. Start a new session to continue` | [請求錯誤](#usage-policy-refusal) |
| `Claude Code is unable to respond to this request, which appears to violate our Usage Policy` | [請求錯誤](#usage-policy-refusal) |
| `<model>'s safeguards flagged this message` | [請求錯誤](#safety-measures-flagged-a-cybersecurity-topic) |
| `<model>'s safeguards flagged this session` | [請求錯誤](#safety-measures-flagged-a-cybersecurity-topic) |
| `<model> has safety measures that flagged this message for a cybersecurity topic` | [請求錯誤](#safety-measures-flagged-a-cybersecurity-topic) |
| `` Details: `[reasoning_extraction]` `` | [請求錯誤](#safeguards-flagged-a-request-for-claudes-reasoning) |
| `API Error: Output blocked by content filtering policy` | [請求錯誤](#output-blocked-by-content-filtering-policy) |
| `Installation was killed before it could finish (exit code 137)` | [疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#installation-was-killed-before-it-could-finish) |
| `The connection dropped while downloading the update` | [疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#the-connection-dropped-while-downloading-the-update) |
| `Download timed out: exceeded the total deadline` | [疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#the-connection-dropped-while-downloading-the-update) |
| `Release verification failed for Claude Code <version> (<reason>). The update was not installed.` | [疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#release-verification-failed) |
| `Auto-update failed · Run claude doctor` | [疑難排解安裝和登入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#auto-update-failed) |
| `--bg and --print conflict` | [命令列錯誤](#conflict-between-bg-and-print) |
| `Couldn't tell whether --bg is a flag or text here, so nothing was started` | [命令列錯誤](#couldnt-tell-whether-bg-is-a-flag-or-text) |
| `Error: Cannot use both --append-subagent-system-prompt and --append-subagent-system-prompt-file. Please use only one.` | [命令列錯誤](#conflict-between-a-system-prompt-flag-and-its-file-form) |
| `Cloud sessions cannot be created from a --restricted session` | [命令列錯誤](#cloud-sessions-cannot-be-created-from-a-restricted-session) |
| `Cloud sessions are disabled by your organization's policy` | [命令列錯誤](#cloud-sessions-are-disabled-by-your-organizations-policy) |
| 出現在指明某項憑證的政策拒絕訊息結尾的 `Cloud sessions use your claude.ai login` | [命令列錯誤](#cloud-sessions-use-your-claude-ai-login) |
| `Couldn't verify your organization's policy for cloud sessions` | [命令列錯誤](#couldnt-verify-your-organizations-policy-for-cloud-sessions) |
| `Cloud sessions aren't available:`，後接無法載入您組織政策的原因 | [命令列錯誤](#couldnt-verify-your-organizations-policy-for-cloud-sessions) |
| `Cloud sessions aren't available with this Console sign-in. They need a claude.ai sign-in.` | [無法取得組織 UUID](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#unable-to-get-organization-uuid) |
| `Cloud sessions need a claude.ai sign-in` | [無法取得組織 UUID](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#unable-to-get-organization-uuid) |
| `Nothing was stashed: "<path>" is now a folder in place of a tracked file or link` / `are now folders in place of tracked files or links` | [命令列錯誤](#nothing-was-stashed-because-a-folder-replaced-a-tracked-file) |
| `Error: --json-schema is not a valid JSON Schema` | [命令列錯誤](#the-json-schema-value-is-not-a-valid-json-schema) |
| `Error: Invalid --agents configuration:` | [命令列錯誤](#invalid-agents-configuration) |
| `Error: --agents takes a JSON object, or a file path only with --print (-p)` | [命令列錯誤](#invalid-agents-configuration) |
| `Error: --agents file not found` | [命令列錯誤](#invalid-agents-configuration) |
| `Error: Settings file exceeds the 2MiB limit` | [命令列錯誤](#settings-file-exceeds-the-2mib-limit) |
| `The current directory no longer exists (it was deleted or moved)` / `Can't read the current directory` | [命令列錯誤](#the-current-directory-no-longer-exists) |
| `Temp directory <dir> ... Refusing to use it` / `Claude Code's temporary directory <dir> could not be created` | [命令列錯誤](#temp-directory-refused-or-cannot-be-created) |
| `ENOSPC: no space left on device, mkdir '<dir>'` | [命令列錯誤](#temp-directory-refused-or-cannot-be-created) |
| `couldn't be resolved to a real location, so its skills, commands, and agents weren't loaded` | [命令列錯誤](#directory-couldnt-be-resolved-to-a-real-location) |
| 啟動 Remote Control 時出現的 `Error: Workspace not trusted` | [命令列錯誤](#workspace-not-trusted-when-starting-remote-control) |
| 執行 `claude ultrareview` 時出現的 `Error: Workspace not trusted` | [命令列錯誤](#workspace-not-trusted-when-running-claude-ultrareview) |
| `Ultrareview did not start` | [命令列錯誤](#ultrareview-did-not-start) |
| `` `<flag>` before `remote-control` is not carried over to the sessions Remote Control starts `` | [命令列錯誤](#not-carried-over-to-the-sessions-remote-control-starts) |
| `--sandbox is not supported by claude remote-control` / `--no-sandbox is not supported by claude remote-control` | [命令列錯誤](#sandbox-is-not-supported-by-claude-remote-control) |
| `` `claude import` is not yet available in this build `` | [命令列錯誤](#claude-import-is-not-yet-available-in-this-build) |
| `Could not read Claude Code config` | [命令列錯誤](#could-not-read-claude-code-config) |
| `Could not import <server>: <reason>` | [命令列錯誤](#could-not-import-a-server-from-claude-desktop) |
| `Cannot add MCP server to scope: managed` | [命令列錯誤](#cannot-add-mcp-server-to-the-managed-scope) |
| `Cannot add MCP server: your organization's managed settings allow only MCP servers that plugins provide` | [命令列錯誤](#cannot-add-mcp-server-when-managed-settings-allow-only-plugin-servers) |
| `is Anthropic-hosted and doesn't support local OAuth` | [命令列錯誤](#anthropic-hosted-and-doesnt-support-local-oauth) |
| `Can't read .mcp.json: it isn't a regular file or is larger than 2097152 bytes` | [命令列錯誤](#cant-read-mcp-json) |
| `MCP server "<name>" was not saved to` / `was not removed from` | [命令列錯誤](#mcp-server-was-not-saved-or-removed) |
| `MCP server "<name>" may not have been saved` / `may not have been removed` | [命令列錯誤](#mcp-server-may-not-have-been-saved-or-removed) |
| `Server rejected the Authorization header minted by the configured headersHelper` | [命令列錯誤](#server-rejected-the-authorization-header-minted-by-the-configured-headershelper) |
| `This server (Java MCP SDK 0.17.0 or older) rejected Claude Code's elicitation capability` | [命令列錯誤](#mcp-server-rejected-the-elicitation-capability) |
| `Error: MCP tool <name> (passed via --permission-prompt-tool) not found` | [命令列錯誤](#mcp-permission-prompt-tool-not-found) |
| `OAuth callback port <port> is already in use — another process may be holding it` | [命令列錯誤](#oauth-callback-port-is-already-in-use) |
| `No available ports for OAuth redirect` | [命令列錯誤](#no-available-ports-for-oauth-redirect) |
| `Shell command failed for pattern "..."`，來自 `/security-review` 或任何注入動態上下文的 skill | [命令列錯誤](#security-review-fails-without-origin-head) |
| 來自注入動態上下文之 skill 的 `Shell command permission check failed for pattern "..."` | [命令列錯誤](#security-review-fails-without-origin-head) |
| ``Skill <name> requires bash (`shell: bash` in frontmatter) but Git Bash was not found`` | [命令列錯誤](#security-review-fails-without-origin-head) |
| `No shell command in <name> was run, because the <tool> tool does not accept one of them` | [命令列錯誤](#no-shell-command-was-run) |
| `Input must be provided either through stdin or as a prompt argument when using --print` | [命令列錯誤](#input-must-be-provided-when-using-print) |
| `Claude Code can't read the keyboard here: stdin is not a terminal` | [命令列錯誤](#claude-code-cant-read-the-keyboard-here) |
| `Error: Input contained only whitespace` | [命令列錯誤](#input-contained-only-whitespace) |
| `Blank prompt — the message was only whitespace, so nothing was sent to the model.` | [命令列錯誤](#input-contained-only-whitespace) |
| `Error: stream-json input carried over 256M characters with no newline` | [命令列錯誤](#stream-json-input-carried-over-256m-characters-with-no-newline) |
| `Unknown command: /<name>`，無論是否附有 `Did you mean` 建議 | [命令列錯誤](#unknown-command) |
| `Diff is too large for ultrareview` / `PR #<N> is too large for ultrareview` | [命令列錯誤](#diff-is-too-large-for-ultrareview) |
| `Could not find merge-base with <branch>` | [命令列錯誤](#could-not-find-merge-base-with-the-base-branch) |
| `Your checkout has no branches (detached HEAD only)` | [命令列錯誤](#your-checkout-has-no-branches) |
| `Ultrareview clones <owner>/<repo> in the cloud with the GitHub account connected to your Claude account, and none is connected` | [命令列錯誤](#no-github-account-is-connected-to-your-claude-account) |
| `Your connected GitHub account can't see <owner>/<repo>` | [命令列錯誤](#your-connected-github-account-cant-see-the-repository) |
| `The GitHub App preflight failed transiently (network or service hiccup) — retry in a moment to start from GitHub instead` | [命令列錯誤](#the-github-app-preflight-failed-transiently) |
| 帶有 `the upload cannot follow that setting` 的 `Not uploading this working tree` | [命令列錯誤](#the-repository-upload-cant-follow-a-git-setting) |
| `GitHub isn't connected to your Claude account, so this repository can't be cloned in the cloud` | [命令列錯誤](#github-isnt-connected-to-your-claude-account) |
| `Your GitHub organization has an IP allowlist that is blocking Claude` | [命令列錯誤](#a-github-organization-policy-is-blocking-claude) |
| `Your GitHub organization requires single sign-on` | [命令列錯誤](#a-github-organization-policy-is-blocking-claude) |
| `Your GitHub organization's identity provider (Microsoft Entra ID) has a Conditional Access policy that is blocking Claude` | [命令列錯誤](#a-github-organization-policy-is-blocking-claude) |
| `Single sign-on authorization needed` | [命令列錯誤](#single-sign-on-authorization-needed) |
| `Failed to resume the conversation` | [命令列錯誤](#failed-to-resume-the-conversation) |
| `No conversation found with session ID: <session-id>` | [命令列錯誤](#no-conversation-found-with-the-session-id) |
| `Windows reported an error (EBADF) when Claude Code read this session's transcript file` | [命令列錯誤](#windows-reported-an-error-ebadf) |
| `Cannot switch renderers in this session` | [命令列錯誤](#cannot-switch-renderers-in-this-session) |
| `Cannot switch renderers while work is running in the background` | [命令列錯誤](#cannot-switch-renderers-in-this-session) |
| `Can't restart while work is running in the background — wait for it to finish (or stop it via /tasks), then try again.` | [命令列錯誤](#cant-restart-while-work-is-running-or-remote-control-is-connected) |
| `Can't restart while Remote Control is connected. To use the installed version, exit and start Claude Code again, then run /resume.` | [命令列錯誤](#cant-restart-while-work-is-running-or-remote-control-is-connected) |
| `Claude Code couldn't restart` | [命令列錯誤](#claude-code-couldnt-restart) |
| `Couldn't open Claude Desktop` | [命令列錯誤](#couldnt-open-claude-desktop) |
| `Failed to open Claude Desktop. Please try opening it manually.` | [命令列錯誤](#couldnt-open-claude-desktop) |
| `Couldn't read your Zed keymap` / `Couldn't back up your Zed keymap` / `Couldn't update your Zed keymap` | [命令列錯誤](#terminal-setup-left-your-zed-keymap-unchanged) |
| `Your Zed keymap isn't a readable list of keybindings` | [命令列錯誤](#terminal-setup-left-your-zed-keymap-unchanged) |
| `Skill usage reports are not available on this connection.` | [命令列錯誤](#skill-usage-reports-are-not-available-on-this-connection) |
| `Custom output styles can't be selected over Remote Control or from a relayed message` | [命令列錯誤](#custom-output-styles-cant-be-selected-over-remote-control) |
| `Output styles are saved to local settings (.claude/settings.local.json), which this session doesn't load` | [命令列錯誤](#output-styles-are-saved-to-local-settings-which-this-session-doesnt-load) |
| `/recap only runs when you ask for it yourself in this session` | [命令列錯誤](#recap-only-runs-when-you-ask-for-it-yourself) |
| `/feedback is disabled by your organization's policy`，或 `/bug` 或 `/share` 的相同訊息 | [命令列錯誤](#feedback-is-disabled-by-your-organizations-policy) |
| `` `plugin eval` is currently in early access `` / `` `plugin eval` is currently unavailable `` | [外掛錯誤](#plugin-eval-is-currently-in-early-access) |
| `cannot be evaluated where sessions load it` | [使用 evals 測試外掛](https://code.claude.com/docs/zh-TW/plugin-evals.md#cannot-be-evaluated-where-sessions-load-it) |
| `Marketplace "<name>" is registered from an untrusted source` | [外掛錯誤](#marketplace-is-registered-from-an-untrusted-source) |
| `Claude Code refuses the marketplace name "<name>"` | [外掛錯誤](#claude-code-refuses-the-marketplace-name) |
| `Marketplace name impersonates an official Anthropic/Claude marketplace` | [外掛錯誤](#claude-code-refuses-the-marketplace-name) |
| `Marketplace "<name>" is already added from a different source` | [外掛錯誤](#marketplace-is-already-added-from-a-different-source) |
| `"<name>" is another spelling of "<reserved>", a reserved marketplace name` | [外掛錯誤](#marketplace-name-is-another-spelling-of-a-reserved-name) |
| `Cannot add marketplace "<name>": Claude Code cannot install plugins from a marketplace with this name` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#cannot-install-plugins-from-a-marketplace-with-this-name) |
| `Cannot add marketplace "<name>": Claude Code reserves this name and cannot register a marketplace under it` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#claude-code-reserves-this-name) |
| `Marketplace "<name>" is added but ignored` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#marketplace-is-added-but-ignored) |
| `Marketplace "<name>" is registered but was refused (see the debug log)` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#marketplace-is-added-but-ignored) |
| `references ${user_config.*} in a shell-form command` | [外掛錯誤](#plugin-command-references-user-config) |
| `Monitor "<name>" from plugin <plugin> references ${user_config.*} in its command` | [外掛錯誤](#plugin-command-references-user-config) |
| `headersHelper for MCP server '<name>' references ${user_config.*}` | [外掛錯誤](#plugin-command-references-user-config) |
| `Plugin archive integrity check failed` | [外掛錯誤](#plugin-archive-integrity-check-failed) |
| `An npm plugin source must name a registry package` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#an-npm-plugin-source-must-name-a-registry-package) |
| `The packages it lists are not installed` / `The packages it lists were not installed, because` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#the-packages-it-lists-are-not-installed) |
| `does not load (...), so Claude Code ignores the whole file` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#does-not-load-so-claude-code-ignores-the-whole-file) |
| `path escapes plugin directory` | [外掛錯誤](#path-escapes-plugin-directory) |
| `Plugin not loaded: its manifest <path> was not read` | [外掛錯誤](#plugin-not-loaded-its-manifest-was-not-read) |
| `path could not be checked` | [外掛錯誤](#path-could-not-be-checked) |
| `its marketplace entry path does not stay inside the marketplace directory` | [外掛錯誤](#marketplace-entry-path-does-not-stay-inside-the-marketplace-directory) |
| `Plugin source path refused` | [外掛錯誤](#marketplace-entry-path-does-not-stay-inside-the-marketplace-directory) |
| `Failed to load marketplace configuration` | [外掛錯誤](#failed-to-load-marketplace-configuration) |
| `Marketplace configuration file is corrupted` | [外掛錯誤](#failed-to-load-marketplace-configuration) |
| `Plugin "<name>@synced" is required by your organization and can't be disabled here` | [外掛錯誤](#plugin-is-required-by-your-organization) |
| `"<plugin>" was not uninstalled: it is still switched on in <file>` | [外掛錯誤](#plugin-was-not-uninstalled) |
| `"<plugin>" was not uninstalled: <file> is there and could not be read` | [外掛錯誤](#plugin-was-not-uninstalled) |
| `Plugin "<plugin>" was not uninstalled: installed_plugins.json` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#installed-plugins-json-holds-a-record-this-version-cannot-read) |
| `Plugin directory does not exist: <path>` | [外掛疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-directory-does-not-exist) |
| `Skipping connection (recent failure cached; retries automatically in 15 min, or edit the plugin config to retry now)` | [外掛錯誤](#skipping-connection-recent-failure-cached) |
| `Error: No such tool available: <tool name>` | [工具錯誤](#no-such-tool-available) |
| `MCP server "<name>" connection closed before the tool call was answered` | [工具錯誤](#connection-closed-before-the-tool-call-was-answered) |
| `MCP server "<name>" is disabled — re-enable it via /mcp to use its tools` | [工具錯誤](#mcp-server-is-disabled) |
| `MCP server "<name>" tool "<tool>" timed out after <N>s. The server asked the user a question, and no answer came before the time limit.` | [工具錯誤](#mcp-tool-call-timed-out-with-the-servers-question-unanswered) |
| `would be spawned with zero tools — refusing` | [工具錯誤](#agent-would-be-spawned-with-zero-tools) |
| `File is covered by a Read deny rule in your permission settings` | [工具錯誤](#file-is-covered-by-a-read-deny-rule) |
| `<path> is outside <dirs>; the permissions.blockWritesOutsideWorkingDirectories setting blocks writes outside the working directories` | [工具錯誤](#setting-blocks-writes-outside-the-working-directories) |
| `<path>: Writes outside the working directories are blocked (permissions.blockWritesOutsideWorkingDirectories)` | [工具錯誤](#setting-blocks-writes-outside-the-working-directories) |
| `Writes to Claude Code settings files are blocked while permissions.blockWritesOutsideWorkingDirectories is on` | [工具錯誤](#writes-to-claude-code-settings-files-are-blocked) |
| `cannot contain null bytes (\0)` | [工具錯誤](#path-cannot-contain-null-bytes) |
| `Path contains null bytes` | [工具錯誤](#path-cannot-contain-null-bytes) |
| `command contains the invisible character U+FEFF (byte order mark) or U+180E (Mongolian vowel separator), and was not run` | [工具錯誤](#command-contains-an-invisible-character) |
| `File is too large to read as an image (the limit is 128MB)` | [工具錯誤](#file-is-too-large-to-read-as-an-image) |
| `Cannot read this as an image: <path> is a pipe or a device` | [工具錯誤](#file-is-too-large-to-read-as-an-image) |
| `subagent_type is required: the general-purpose agent is not available in this session` | [工具錯誤](#subagent-type-is-required) |
| `Error: this write left the memory index at MEMORY.md at ..., over its ... read limit` | [工具錯誤](#memory-index-is-over-its-read-limit) |
| `Sandbox is required but failed to initialize: <reason>` | [沙箱機制疑難排解](https://code.claude.com/docs/zh-TW/sandboxing.md#commands-refused-with-sandbox-is-required) |
| `Sandbox is required (sandbox.failIfUnavailable) and stopped being available in this session: <reason>` | [沙箱機制疑難排解](https://code.claude.com/docs/zh-TW/sandboxing.md#commands-refused-with-sandbox-is-required) |
| `pkill: refusing to run` | [工具錯誤](#pkill-pattern-matches-the-claude-code-process) |
| `Failed to write to <name>'s inbox — nothing was sent` | [工具錯誤](#failed-to-write-to-a-teammate-inbox) |
| `Failed to write the plan approval request to the lead's inbox — plan not submitted` | [工具錯誤](#failed-to-write-to-a-teammate-inbox) |
| `Its agent definition was not restored: the folder its definition file came from is not trusted` | [工具錯誤](#teammate-agent-definition-not-restored) |
| `Only a teammate can approve a shutdown request` | [工具錯誤](#only-a-teammate-can-approve-a-shutdown-request) |
| `A command-line deny rule cannot be handed to a teammate intact` | [工具錯誤](#command-line-deny-rule-cannot-be-handed-to-a-teammate) |
| `Message too large for cross-session delivery` | [工具錯誤](#message-too-large-for-cross-session-delivery) |
| `Too many messages to this session just now` | [工具錯誤](#too-many-messages-to-this-session-just-now) |
| `Cross-session message was dropped at the recipient session's inbox` | [工具錯誤](#cross-session-message-dropped-at-the-inbox) |
| `Refusing to send: reply target is a symlink` / `Refusing to send: cannot vet reply target` | [工具錯誤](#refusing-to-send-a-cross-session-message) |
| `Refusing to read <path>: its symlink resolution changed after permission was checked (<reason>)` / `Refusing to search <path>: its symlink resolution changed after permission was checked` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `Refusing to write <path>: its parent-directory symlink resolution changed after permission was checked` / `Refusing to write <path>: it is a symbolic link. Write to the link's target path instead` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `Refusing to write through symlink: <path>` / `Refusing to write into symlinked directory: <path>` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `Refusing to write <path>: where it leads on disk could not be determined` / `Refusing to read <path>: where it leads on disk could not be determined` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `Refusing to search <path>: a path one of its Read deny rules is written through changed while the search was being prepared` / `Refusing to search <path>: it could not be opened` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `its permission check expired before it ran (too many concurrent file operations)` / `ripgrep was found only by name on PATH` | [工具錯誤](#refusing-after-a-symlink-changed) |
| `task output swap refused (tasks dir moved or linked)` | [工具錯誤](#task-output-swap-refused) |
| `Command killed: its output file was replaced or could no longer be verified` | [工具錯誤](#task-output-swap-refused) |
| `Disk full: this computer's volume holding <dir> (Claude Code's temporary directory) has <n> MB free` / `Nearly out of inodes: this computer's volume holding <dir>` | [工具錯誤](#disk-quota-or-temp-filesystem-is-full) |
| `Disk full: a test write beside this command's output file` / `Disk quota used up: a test write beside this command's output file` | [工具錯誤](#disk-quota-or-temp-filesystem-is-full) |
| `The command was not started: this computer's disk is full (ENOSPC)` / `the user's disk quota is used up (EDQUOT)` | [工具錯誤](#disk-quota-or-temp-filesystem-is-full) |
| `Your disk quota is full on the filesystem with Claude Code's temp directory <dir> (EDQUOT)` / `The filesystem with Claude Code's temp directory <dir>, or your disk quota on it, is full (ENOSPC)` | [工具錯誤](#disk-quota-or-temp-filesystem-is-full) |
| `Command output was lost: the temp filesystem at <dir> is full` / `is out of inodes` | [工具錯誤](#disk-quota-or-temp-filesystem-is-full) |
| `File is not valid UTF-8. It may use a legacy encoding such as Windows-1252, Shift-JIS or GBK, or be binary` | [工具錯誤](#file-is-not-valid-utf-8) |
| `git is not installed on this Mac. To install it, run xcode-select --install, then try again.` | [工具錯誤](#git-is-not-installed-on-this-mac) |
| `the source file is not valid UTF-8 text` / `the source file is not valid UTF-16 text` | [工具錯誤](#the-source-file-is-not-valid-utf-8-text) |
| `the source file has the replacement character U+FFFD` | [工具錯誤](#the-source-file-is-not-valid-utf-8-text) |
| `Not published: that file is on a network share` | [工具錯誤](#not-published-that-file-is-on-a-network-share) |
| `Not published: Claude sent the same content again after a newer version of the artifact turned it away` / `Not published: Claude sent its changes again over the same file after a newer version of the artifact turned them away` | [工具錯誤](#not-published-a-newer-version-of-the-artifact-turned-it-away) |
| `Reading a local file from outside this session's connected folders, or through a link, needs the approval card` | [工具錯誤](#reading-a-local-file-from-outside-the-connected-folders) |
| `cannot read file_path (...) — the file could not be examined, and no one can answer the approval card` | [工具錯誤](#reading-a-local-file-from-outside-the-connected-folders) |
| `WebFetch cannot fetch localhost or other hostnames without a dot` | [工具錯誤](#webfetch-cannot-fetch-localhost) |
| `The safety check for domain ... is rate-limited` | [工具錯誤](#webfetch-domain-safety-check-failed) |
| `The safety check for domain ... is temporarily rate-limited` | [工具錯誤](#webfetch-domain-safety-check-failed) |
| `Unable to verify if domain ... is safe to fetch` | [工具錯誤](#webfetch-domain-safety-check-failed) |
| `Can't open MCP settings while no terminal is attached to this background session` | [背景工作階段錯誤](#commands-refused-in-a-background-session) |
| `Can't open MCP settings in a background session` | [背景工作階段錯誤](#commands-refused-in-a-background-session) |
| `blocked because the path is spelled in a form that cannot be safely resolved` | [背景工作階段錯誤](#write-or-command-blocked-because-the-path-cannot-be-safely-resolved) |
| `blocked because the path is network-shaped` | [背景工作階段錯誤](#write-or-command-blocked-because-the-path-names-a-network-location) |
| `is isolated in the worktree <path>, but this command <reason>. Refusing to run it` | [背景工作階段錯誤](#command-blocked-by-the-worktree-isolation-checks) |
| `too complex to verify that it stays inside the worktree` | [背景工作階段錯誤](#command-blocked-by-the-worktree-isolation-checks) |
| `This session has no saved transcript` | [背景工作階段錯誤](#this-session-has-no-saved-transcript) |
| `Can't open — this session is running in another terminal` | [背景工作階段錯誤](#this-session-is-running-in-another-terminal) |
| `This conversation is already open in another running Claude session` | [背景工作階段錯誤](#this-session-is-running-in-another-terminal) |
| `This session's saved conversation is no longer on disk` | [背景工作階段錯誤](#this-sessions-saved-conversation-is-no-longer-on-disk) |
| `Bypass permissions was requested at launch and ignored` | [在背景工作階段中 Bypass permissions 遭到忽略](https://code.claude.com/docs/zh-TW/permission-modes.md#bypass-permissions-ignored-in-a-background-session) |
| `kept <id> — its worktree is still at <path>` | 若訊息的下一行提及未推送的提交，請參閱[背景工作階段錯誤](#worktree-has-commits-that-are-not-pushed-anywhere)，否則請參閱[刪除工作階段會移除哪些內容](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes) |
| `kept <id> — <n> unpushed commits on <branch>` | [背景工作階段錯誤](#worktree-has-commits-that-are-not-pushed-anywhere) |
| `kept <id> — worktree has commits that are not pushed anywhere` | [背景工作階段錯誤](#worktree-has-commits-that-are-not-pushed-anywhere) |
| `terminal host process died — press Enter to restart` / `This session's terminal host process died` | [背景工作階段錯誤](#terminal-host-process-died) |
| `Session isn't responding` / `Press enter again to restart this session — it isn't responding` | [背景工作階段錯誤](#session-isnt-responding) |
| `Session <id> was stopped while the respawn was in flight` | [背景工作階段錯誤](#session-was-stopped-while-the-respawn-was-in-flight) |
| `This session was running agent '<name>', which is no longer available` | [背景工作階段錯誤](#session-agent-no-longer-available) |
| `This session restarted <time> after its next /loop wakeup was due, so that wakeup will not fire` | [背景工作階段錯誤](#restarted-after-its-next-loop-wakeup-was-due) |
| `No LLM gateway: a gateway set in your shell isn't passed to a session opened from another folder` | [背景工作階段錯誤](#no-llm-gateway-opened-from-another-folder) |
| `No LLM gateway: opened from another folder · respawn from <folder>` | [背景工作階段錯誤](#no-llm-gateway-opened-from-another-folder) |
| `CLAUDE_CODE_PROCESS_WRAPPER: launcher ...` | [背景工作階段錯誤](#claude_code_process_wrapper-launcher-errors) |
| `EUNKNOWN: unknown error, uv_spawn` | [背景工作階段錯誤](#eunknown-when-starting-a-background-session) |
| `EACCES: permission denied, posix_spawn` | [背景工作階段錯誤](#eacces-when-starting-a-background-session) |
| `exited before it became reachable` | [背景工作階段錯誤](#background-service-exited-before-it-became-reachable) |
| `Couldn't start a background session (working directory no longer exists or is not accessible: ...)` | [背景工作階段錯誤](#working-directory-no-longer-exists-when-starting-a-background-session) |
| 啟動或重新啟動背景工作階段時出現的 `Workspace not trusted.` | [背景工作階段錯誤](#workspace-not-trusted-when-dispatching-a-background-session) |
| `Claude Code is being updated by npm on this machine (still not runnable after 2 min, ...)` | [背景工作階段錯誤](#eacces-when-starting-a-background-session) |
| `Claude Code process exited with code N` | [包裝程式和 IDE 錯誤](#claude-code-process-exited-with-code-n) |
| `The connection to Claude Code ended before this message completed` | [包裝程式和 IDE 錯誤](#the-connection-to-claude-code-ended-before-this-message-completed) |
| `Could not locate the Claude CLI on PATH` | [包裝程式和 IDE 錯誤](#could-not-locate-the-claude-cli-on-path) |
| `The Claude Code program for this computer, the <build> build, could not be found` | [包裝程式與 IDE 錯誤](#the-claude-code-program-for-this-computer-could-not-be-found) |
| `Restored the code, but skipped N files` | [Rewind 警告和錯誤](#restored-the-code-but-skipped-files) |
| `No files were restored: N files failed (backup missing, or the file could not be updated)` | [Rewind 警告和錯誤](#no-files-were-restored) |
| `Transcript writes are failing (...)` | [工作階段儲存警告](#transcript-writes-are-failing) |
| `Transcript saving is off — CLAUDE_CODE_SKIP_PROMPT_HISTORY is set` | [工作階段儲存警告](#transcript-saving-is-off-skip-prompt-history) |
| `Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker` | [工作階段儲存警告](#transcript-saving-is-off-child-session-marker) |
| `Claude Code's fullscreen renderer didn't finish starting last time on this machine` / `Claude Code's fullscreen renderer has repeatedly failed to start on this machine` | [全螢幕轉譯](https://code.claude.com/docs/zh-TW/fullscreen.md#fullscreen-renderer-didnt-finish-starting) |
| `Claude Code exited after an unrecoverable interface error (...)` | [設定警告](#exited-after-an-unrecoverable-interface-error) |
| `Agent descriptions are over the 15.0k-token limit` | [設定警告](#agent-descriptions-are-over-the-15000-token-limit) |
| `hook needs quotes around a path with a space` | [設定警告](#hook-needs-quotes-around-a-path-with-a-space) |
| `Instruction file not loaded` | [設定警告](#instruction-file-not-loaded) |
| `Not loaded: rename <path>, then restart — its name uses "<name>", a name reserved for the skills synced from your claude.ai account` | [設定警告](#a-skill-command-or-workflow-wasnt-loaded-because-its-name-is-reserved) |
| `N skill or command names refused: run with --debug to see which ([names]), rename, then restart` | [設定警告](#skill-or-command-name-refused) |
| `Ignoring N permissions.allow entries from ... this workspace has not been trusted` | [設定警告](#workspace-has-not-been-trusted) |
| `is a network path, which cannot be added as a working directory` | [設定警告](#working-directory-is-a-network-path) |
| `Remote managed settings failed to load (<cause>)` | [設定警告](#remote-managed-settings-failed-to-load) |
| `Your organization requires remote managed settings to load, but they could not be loaded` | [強制採用失敗即關閉的啟動方式](https://code.claude.com/docs/zh-TW/server-managed-settings.md#enforce-fail-closed-startup) |
| `Remote managed settings are still loading` | [設定警告](#remote-managed-settings-failed-to-load) |
| `Remote managed settings did not load` | [設定警告](#remote-managed-settings-failed-to-load) |
| `Managed settings were not approved; exiting without applying them.` | [設定警告](#managed-settings-were-not-approved) |
| `Your organization's managed settings need your approval, which couldn't be asked for here.` | [設定警告](#managed-settings-need-your-approval) |
| `Claude Code can't start: your organization's managed settings block the default model` / `Claude Code can't start: your organization allows only the models listed in "availableModels"` | [設定警告](#managed-settings-block-the-default-model) |
| `Your organization's managed settings allow Claude Code to use: <providers>` | [設定警告](#managed-settings-dont-allow-this-api-provider) |
| `Your organization's managed settings allow Claude Code to use no API provider at all` | [設定警告](#managed-settings-dont-allow-this-api-provider) |
| `MCP server <name> is blocked by enterprise managed policy` | [設定警告](#mcp-server-is-blocked-by-enterprise-managed-policy) |
| `"<name>" is a reserved MCP server name and was not loaded` | [設定警告](#mcp-server-name-is-reserved) |
| `Managed settings document could not be parsed as a JSON object; none of its settings are in effect. Fix or remove it.` | [設定警告](#managed-settings-document-could-not-be-parsed) |
| `Managed settings drop-in directory could not be read` | [設定警告](#managed-settings-document-could-not-be-parsed) |
| `Unable to read managed policy settings` | [設定警告](#unable-to-read-managed-policy-settings) |
| `Managed settings contain invalid entries, including PreToolUse/PermissionRequest hooks that are NOT loaded; fix or remove each entry:` | [設定警告](#managed-settings-hooks-not-loaded) |
| `otelHeadersHelper failed; telemetry is not being exported. See /status: ...` | [設定警告](#otelheadershelper-failed) |
| `"crossSessionInbound" must be one of "accept", "hold", "refuse"` | [設定警告](#crosssessioninbound-must-be-one-of-accept-hold-refuse) |
| `API Error: ANTHROPIC_FOUNDRY_RESOURCE must be a Foundry resource name` | [設定警告](#anthropic-foundry-resource-must-be-a-foundry-resource-name) |
| `headersHelper not run — this workspace has no persisted trust` | [設定警告](#headershelper-not-run) |
| `Invalid permission rule "..." was skipped: Malformed Tool(content) rule` | [設定警告](#malformed-tool-content-rule) |
| `matches no tool · check for typos` / `matches no known tool — check for typos` | [設定警告](#matches-no-tool) |
| `... is not matched by file permission checks` | [設定警告](#is-not-matched-by-file-permission-checks) |
| `Write(<path>) never matches · use Edit(<path>)` / `Glob(<path>) never matches · use Read(<path>)` | [設定警告](#is-not-matched-by-file-permission-checks) |
| `... has a wildcard before the rest of the command` | [設定警告](#has-a-wildcard-before-the-rest-of-the-command) |
| `allows any option at its * · use an exact value` | [設定警告](#has-a-wildcard-before-the-rest-of-the-command) |
| `Denying Bash also turns off the PowerShell tool, so Claude has neither` | [設定警告](#denying-bash-also-turns-off-the-powershell-tool) |
| `CLAUDE_CODE_DISABLE_1M_CONTEXT is set, but the 200K limit isn't enforced` | [設定警告](#the-200k-limit-isnt-enforced) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW="<value>" reads as <N> tokens, so Claude Code treats it as the 100k minimum` | [`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 的值與警告](https://code.claude.com/docs/zh-TW/model-config#claude_code_auto_compact_window-values) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW="<value>" is too large, so Claude Code treats it as the 1M maximum` | [`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 的值與警告](https://code.claude.com/docs/zh-TW/model-config#claude_code_auto_compact_window-values) |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW="<value>" isn't a usable size, so Claude Code ignores it` | [`CLAUDE_CODE_AUTO_COMPACT_WINDOW` 的值與警告](https://code.claude.com/docs/zh-TW/model-config#claude_code_auto_compact_window-values) |
| `Model "<model>" isn't recognized · context assumed to be 200k tokens` | [修正閘道或自訂模型 ID 的上下文視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id) |
| `Claude Code doesn't recognize the model "<model>", so it assumes a context window of 200k tokens` | [修正閘道或自訂模型 ID 的上下文視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id) |
| `[claude-code:unrecognized_model]` | [設定警告](#unrecognized-model-id-on-a-request) |
| `is ignored — managed settings set allowManagedReadPathsOnly` / `is ignored — managed settings set allowManagedDomainsOnly` | [設定警告](#sandbox-allow-entries-are-ignored-under-a-managed-lock) |
| `Sandbox mask files left behind at write-deny paths` | [設定警告](#stale-sandbox-mask-files-left-by-a-killed-session) |
| `Stale sandbox mask files left by a killed session` | [設定警告](#stale-sandbox-mask-files-left-by-a-killed-session) |
| `Ubuntu's AppArmor restriction on user namespaces stops bubblewrap here` | [沙箱機制疑難排解](https://code.claude.com/docs/zh-TW/sandboxing.md#apparmor-restriction-stops-bubblewrap) |
| `bwrap: setting up uid map: Permission denied` / `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` | [沙箱機制疑難排解](https://code.claude.com/docs/zh-TW/sandboxing.md#bwrap-uid-map-permission-denied) |
| 回應品質似乎比平常低 | [回應品質](#responses-seem-lower-quality-than-usual) |

## 自動重試

Claude Code 會在顯示錯誤之前，以指數退避方式重試暫時性故障最多 10 次。它不會總是重試在 Claude 回應中途出現的故障。當您看到本頁面上的其中一個錯誤時，Claude Code 已經對該故障進行了適用的重試。

Claude Code 會重試這些故障：

* 伺服器錯誤、過載回應，以及在 Claude 回應開始串流之前到達的請求逾時。
* 在 Claude 完成思考之後、但在開始任何文字或工具呼叫之前到達的伺服器錯誤或過載回應。Claude Code 會在該點重試伺服器錯誤最多兩次。在 v2.1.284 之前，Claude Code 會在該點以錯誤結束回合。
* 連線中斷。當連線在 Claude 完成其回應的任何部分（包括其思考）之前中途中斷時，Claude Code 會以相同的退避方式重新發出請求，並且回合會繼續，即使某些文字已經開始串流。當連線在 Claude 完成思考之後但在開始任何文字或工具呼叫之前中斷時，Claude Code 會改為快速連續重新發出請求最多兩次，如果連線在該點持續中斷，則以 `Connection lost before a response was produced` 結束回合。
* Claude Code 偵測到的連線在您的電腦進入睡眠狀態時在請求中途被中斷。Claude Code 將其計為上述規則下的連線中斷；一旦重試標籤命名了具體原因，它會讀作 `Connection lost while your computer was asleep`，如果回合在 Claude 完成思考但在任何文字或工具呼叫之前結束，訊息會讀作 `Your computer went to sleep before a response was produced`。
* 停滯的回應串流，當回應標頭已到達但 Claude 回應的任何部分都未到達，或當 Claude 完成思考但尚未開始任何文字或工具呼叫時：Claude Code 會中止停滯的連線，並最多再以串流方式發出一次請求。如果在 Claude 完成思考但在任何文字或工具呼叫之前回應停滯第二次，Claude Code 會以 `The response stalled before a response was produced` 結束回合。
* API 從未以回應標頭回答的串流請求，且該連線上有[首位元組截止時間生效](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)。到達截止時間時，Claude Code 會中止該請求，並在重試預算內重新發送。如果重新發送的請求也觸發截止時間，回合會以 [No response from API](#no-response-from-api) 結束。當您設定 `CLAUDE_CODE_RETRY_WATCHDOG` 時，Claude Code 會改為在預算內持續重新發送。
* 在 Claude 完成思考或開始任何文字或工具呼叫之前，被 API 輸出內容過濾器停止的串流回應。Claude Code 會在重試預算內重新發送請求一次，如果過濾器也停止了第二個回應，則顯示 [Output blocked by content filtering policy](#output-blocked-by-content-filtering-policy)。
* 暫時性 429 節流，但不是閘道的支出限制 `429`，這不是節流；請參閱 [Spend limit reached](#spend-limit-reached)。
  * 當您使用 claude.ai 訂閱登入時，這包括不帶有您方案配額標頭的 429 節流。在 v2.1.199 之前，Claude Code 僅針對 API 金鑰和 Enterprise 登入重試這些節流。
* 因為輸入加上 `max_tokens` 超過上下文限制而被拒絕的請求。以相同方式重新發送它會以相同方式失敗，所以 Claude Code 會以縮減的 `max_tokens` 重試，並在兩種情況下停止重試並改為壓縮：
  * 當沒有縮減可以容納時，例如當對話本身幾乎填滿上下文視窗時。
  * 當重試無法進一步縮減 `max_tokens` 時。在 v2.1.218 之前，Claude Code 可能會重新發送仍然無法容納的縮減請求，例如當延伸思考預算超過剩餘上下文時，直到重試預算用盡。
* 表示 Claude 正在呼叫工具、但未包含任何工具呼叫的回應。Claude Code 會透過要求 Claude 提供工具呼叫來重試，最多兩次。如果兩次重試都以相同方式失敗，您會看到 `The model's tool call could not be parsed (retry also failed).`，且回合結束。若要再試一次，請傳送另一則訊息。在 v2.1.307 之前，Claude Code 會在結束回合前重試一次。
* 在 [Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 上過期或遺失的 Google Cloud 憑證，或在您的機器上無法載入的 AWS 憑證。Claude Code 會捨棄其快取的憑證並重試最多兩次，然後報告錯誤，以便您可以立即重新驗證，如 [Could not load AWS or Google Cloud credentials](#could-not-load-aws-or-google-cloud-credentials) 下所述。在 v2.1.228 之前，Claude Code 會透過完整重試預算重試失敗的 Google Cloud 憑證，然後才顯示錯誤。
* 來自 Anthropic API 的 `401` 或 `403`，直接或透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，而 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼提供憑證。Claude Code 會重新執行指令碼並使用其新輸出重試，在完整重試預算內。當指令碼本身在重新執行時失敗時，Claude Code 會改為顯示 [Your apiKeyHelper script is failing](#your-apikeyhelper-script-is-failing)。

在 v2.1.227 之前，`Connection lost before a response was produced` 讀作 `Connection closed while thinking, before producing a response`，`The response stalled before a response was produced` 讀作 `Response stalled while thinking, before producing a response`。

Claude Code 不會重試這些故障：

* TLS 憑證驗證失敗，例如 TLS 檢查代理伺服器、遺失的 `NODE_EXTRA_CA_CERTS` 套件，或過期的憑證。Claude Code 在第一次嘗試時報告錯誤，以便您可以立即修正憑證設定；請參閱 [SSL certificate errors](#ssl-certificate-errors)。Claude Code 仍會重試暫時性 TLS 條件，例如握手逾時。在 v2.1.199 之前，Claude Code 會透過完整重試預算重試憑證失敗，然後才顯示錯誤。
* 伺服器錯誤、連線中斷，或停滯的串流在 Claude 完成文字區塊或工具呼叫之後到達，或在完成思考後開始一個但在完成回應之前。Claude Code 不會重新執行請求，因為這可能會執行相同的工具呼叫兩次。它會保留 Claude 完成的內容，執行 Claude 完成的任何工具呼叫，並從其結果繼續回合。關於您在互動式工作階段和非互動式工作階段中看到的內容，請閱讀 [The response above may be incomplete](#the-response-above-may-be-incomplete)。在 v2.1.199 之前，當伺服器錯誤在串流中途到達時，Claude Code 會捨棄部分輸出並將整個回合報告為錯誤。
* 在 Claude 完成回應之後到達的故障：不需要重試任何內容，所以 Claude Code 會保留完整回應並正常結束回合。
* [Amazon Bedrock 串流回應具有意外的 content-type](#bedrock-streaming-response-has-an-unexpected-content-type)，因為重寫回應的閘道或代理伺服器會以相同方式重寫重試。需要 Claude Code v2.1.208 或更新版本。
* 失敗的串流請求的非串流重試獲得成功狀態但 [body 中沒有 Claude API 訊息](#api-returned-an-empty-or-malformed-response)。Claude Code 以該錯誤結束回合。
* 您的組織的原則檢查拒絕的請求，其表現為帶有拒絕訊息的 `API Error:` 行。您的組織管理員使用 [Inference hooks](https://platform.claude.com/docs/en/manage-claude/inference-hooks)（Claude Enterprise 功能）設定檢查，訊息以他們設定的指示結尾，或預設告訴您聯絡他們。Claude Code 不會將被拒絕的請求重新發送到相同的模型或 [備援模型](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains)，因為拒絕是關於請求的內容而不是模型。在 v2.1.239 之前，Claude Code 可能會在向您顯示拒絕之前，以非串流方式或在設定的備援模型上重新發送被拒絕的請求。

### 當 Claude Code 重試或等待時您看到的內容

重試時，微調器在錯誤標籤後顯示 `Retrying in Ns · attempt x/y` 倒數計時。標籤命名第一次嘗試的具體原因，用於您可以立即採取行動的故障：網路已關閉、TLS 握手失敗，或您達到速率限制。對於其他錯誤，它最初讀作 `API error`。從 v2.1.198 開始，它會切換到第三次嘗試的具體原因，或當 `CLAUDE_CODE_MAX_RETRIES` 允許少於三次時在最後一次嘗試；較早的版本僅在最後一次嘗試時切換。

從 v2.1.198 開始，在重試期間會隱藏通常的微調器提示。一旦錯誤原因被揭示，如果故障是 529 過載，倒數計時下方的行也會命名檢查服務狀態的位置：Anthropic API 上的 `status.claude.com`，或其他設定上的訊息中命名的提供者或閘道主機。

#### Waiting for API response

`Waiting for API response · will retry in … · check your network` 橫幅表示 Claude Code 已等待至少 20 秒，仍未收到某個請求的任何資料。請求尚未失敗：倒數計時執行到 Claude Code 中止停滯連線的點。如果發生中止：

* 在 Claude 完成文字區塊或工具呼叫之前，或在完成思考後開始一個之前，Claude Code 會重試請求或以錯誤結束回合。[Automatic retries](#automatic-retries) 說明它重試哪些停滯以及重試多少次。
* 在 Claude 完成文字區塊或工具呼叫之後，或在完成思考後開始一個之後，但在 Claude 完成回應之前，Claude Code 會保留 Claude 完成的內容，從 Claude 完成的任何工具呼叫繼續回合，並顯示 [The response above may be incomplete](#the-response-above-may-be-incomplete)。在非互動式工作階段中，以及在任何工作階段中的 subagent 回應，Claude Code 可能會先提示 Claude 繼續回應；該項目說明何時執行以及何時您仍在那裡看到通知。
* 在 Claude 完成回應之後，Claude Code 正常結束回合。

一旦資料恢復或重試成功，橫幅會自動清除。如果它在每次嘗試時重新出現，請將其視為 [network issue](#unable-to-connect-to-api)。如果您透過閘道連線，請參閱[透過閘道連線時，等待橫幅時隱時現](#waiting-banner-behind-a-gateway)。在 v2.1.185 之前，橫幅在 10 秒後出現，措辭不同。

#### 透過閘道連線時，等待橫幅時隱時現

如果在 Claude 思考時 `Waiting for API response` 橫幅時隱時現，且您透過閘道連線，請將 [Claude Code 更新](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)至 v2.1.309 或更新版本。在這些連線上，橫幅會在 45 秒無資料後出現：

* [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 設定為 Anthropic API 以外的主機，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)
* [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段
* 已設定 `ANTHROPIC_AWS_BASE_URL` 的 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)

在 v2.1.309 之前，這些連線上的橫幅會在 20 秒後出現。

### 調整重試行為

您可以使用這些環境變數調整重試行為：

| 變數 | 預設 | 效果 |
| :- | :- | :- |
| [`CLAUDE_CODE_MAX_RETRIES`](https://code.claude.com/docs/zh-TW/env-vars) | 10 | 重試嘗試次數。從 v2.1.186 開始上限為 15；從 v2.1.199 開始 `CLAUDE_CODE_RETRY_WATCHDOG` 會提高預設值並移除上限。降低它以在指令碼中更快地顯示故障。 |
| [`CLAUDE_CODE_RETRY_WATCHDOG`](https://code.claude.com/docs/zh-TW/env-vars) | 未設定 | 在無人值守的工作階段（例如 CI 工作）中設定為 `1`，以無限期重試 `429` 和 `529` 容量錯誤，而不是在 `CLAUDE_CODE_MAX_RETRIES` 次嘗試後失敗。當標準速度的請求收到報告支出限制或用量點數耗盡的 `429` 時，Claude Code 會立即失敗，即使該 `429` 來自按排程重設的 [gateway spend cap](#spend-limit-reached)。在 v2.1.239 之前，看門狗會無限期重試這些錯誤。如需快速模式請求，請參閱 [Handle rate limits](https://code.claude.com/docs/zh-TW/fast-mode.md#handle-rate-limits)。在 v2.1.199 或更新版本上，它也會將其他暫時性錯誤（例如伺服器錯誤、逾時和連線中斷）的預設重試次數提高至 300，大約三小時的退避，並在您明確設定 `CLAUDE_CODE_MAX_RETRIES` 時移除其上限 15。 |
| [`CLAUDE_CODE_RETRY_WATCHDOG_MAX_WAIT_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 未設定 | 設定 `CLAUDE_CODE_RETRY_WATCHDOG` 時，每個 API 請求等待 `429` 和 `529` 錯誤所花費的最長時間（毫秒）。未設定時，等待時間沒有限制。需要 Claude Code v2.1.295 或更新版本。 |
| [`CLAUDE_CODE_RETRY_WATCHDOG_USAGE_LIMIT_RECHECK_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 未設定 | 設定 `CLAUDE_CODE_RETRY_WATCHDOG` 時，在請求等待[用量上限](#youve-hit-your-session-limit)重設期間，檢查該上限是否已解除的最短間隔（毫秒）。當檢查發現上限已解除時，請求會立即送出。請提供 `60000` 到 `10800000` 之間的純數字。未設定或超出該範圍時，不會進行任何檢查。關於 Claude Code 何時略過這些檢查，請參閱[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)。需要 Claude Code v2.1.305 或更新版本。 |
| [`CLAUDE_CODE_OVERLOADED_RETRY_BASE_DELAY_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 500 | API 以 `529` 過載錯誤拒絕的請求，其重試之間退避的起始延遲（毫秒）。當 API 容量已滿時，可提高此值（最高 32000），以將重試分散在較長的時間範圍內。當 `CLAUDE_CODE_RETRY_WATCHDOG` 設定為 `1`，或被拒絕的請求是以[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#handle-rate-limits)發送時，此設定無效。需要 Claude Code v2.1.292 或更新版本。 |
| [`CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 32000 | API 以 `529` 過載錯誤拒絕的請求，其重試之間退避的上限（毫秒）。當 API 容量已滿時，可提高此值（最高 64000），讓後續的重試間隔持續拉長。當 `CLAUDE_CODE_RETRY_WATCHDOG` 設定為 `1`，或被拒絕的請求是以[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#handle-rate-limits)發送時，此設定無效。需要 Claude Code v2.1.296 或更新版本。 |
| [`API_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 600000 | 每次請求嘗試接收其回應標頭的可用時間（毫秒）。它不會限制串流回應在此之後持續執行的時間。在慢速網路或代理伺服器上請提高此值。關於它如何限制首位元組截止時間，請參閱 [No response from API](#no-response-from-api)。 |
| [`CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES`](https://code.claude.com/docs/zh-TW/env-vars) | 未設定 | 逾時的[非串流請求](#streaming-response-ended-before-any-complete-data-was-received)重新發送次數上限。達到上限時，請求會失敗。Claude 產生時間超過逾時的回應在每次重新發送時都會再次逾時，因此請設定較低的數字（例如 `0`）以便更快失敗。在本機工作階段中，每次非串流嘗試會在 300 秒後逾時，或當您設定正值時在 `API_TIMEOUT_MS` 後逾時。需要 Claude Code v2.1.285 或更新版本。 |
| [`CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) | 未設定 | 串流請求的第一個回應位元組的截止時間（毫秒）。需要 Claude Code v2.1.242 或更新版本。關於當此未設定時 Claude Code 如何選擇截止時間，請參閱 [No response from API](#no-response-from-api)。 |

## 伺服器錯誤

這些錯誤大多來自推論供應商：在 Anthropic API 上是 Anthropic 的服務；在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或自訂閘道上，則是該供應商端點背後的服務。[Auto mode cannot determine the safety of an action](#auto-mode-cannot-determine-the-safety-of-an-action) 與 [Agent terminated early due to an API error](#agent-terminated-early-due-to-an-api-error) 也涵蓋了您這一端的原因，例如無法呼叫分類器模型的 Amazon Bedrock 帳戶，或達到用量上限的 subagent。

### API Error: 500 Internal server error

對於任何 5xx 回應，Claude Code 都會顯示狀態碼與 API 的錯誤訊息。以下範例顯示 Anthropic API 上的 500 回應：

```text theme={null}
API Error: 500 Internal server error. This is a server-side issue, usually temporary — try again in a moment. If it persists, check https://status.claude.com.
```

結尾的句子會指出可在何處查看服務健康狀態，內容因供應商而異。Amazon Bedrock、Google Cloud 的 Agent Platform 與 Microsoft Foundry 的設定會指出該供應商的服務狀態。自訂的 `ANTHROPIC_BASE_URL` 則會指出閘道主機。

來自 API 本身的 5xx 表示 API 內部發生非預期的失敗。這並非由您的提示詞、設定或帳戶所造成。

當代理伺服器、負載平衡器或閘道以 HTML 錯誤頁面回應時，訊息會顯示狀態碼與該頁面的標題，例如 `API Error: 502 Bad Gateway`。若頁面沒有標題，訊息則會改為顯示狀態碼及其標準名稱。在 v2.1.281 之前，當頁面有標題時狀態碼會被省略，而頁面沒有標題時則會印出頁面的原始標記。

**處理方式：**

* 查看 [status.claude.com](https://status.claude.com)，或訊息中指出的供應商狀態頁面，確認是否有進行中的事件
* 等候一分鐘後再次傳送您的訊息。您原本的訊息仍在對話中，因此若提示詞很長，您可以輸入 `try again`，而不必貼上整段內容。
* 若 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，且每個請求都以此方式失敗，請檢查您的閘道及其上游是否接受[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#tool-search-through-a-gateway)欄位。根據預設，Claude Code 會傳送 `defer_loading` 工具欄位與 `tool_reference` 區塊，並附上啟用它們的 `anthropic-beta` 標頭。在 v2.1.304 之前，除非您使用 `ENABLE_TOOL_SEARCH` 將其開啟，否則在閘道後方工具搜尋是關閉的。
* 若錯誤持續發生且沒有公告的事件，請執行 `/feedback`，讓 Anthropic 能以您的請求詳細資料進行調查。若您的環境中無法使用 `/feedback`，請參閱[回報錯誤](#report-an-error)。

### API Error: Repeated 529 Overloaded errors

API 暫時對所有使用者都已達容量上限。Claude Code 在顯示此訊息之前已重試數次：

```text theme={null}
API Error: Repeated 529 Overloaded errors. The API is at capacity — this is usually temporary. Try again in a moment. If it persists, check https://status.claude.com.
```

結尾的句子會依供應商而有所不同，方式與上述 500 錯誤相同。

529 並非您的用量上限，也不會計入您的配額。

**處理方式：**

* 查看 [status.claude.com](https://status.claude.com)，或訊息中指出的供應商狀態頁面，確認是否有容量相關公告
* 幾分鐘後再試一次
* 執行 `/model` 並切換至其他模型以繼續工作，因為容量是依模型分別追蹤的。當某個模型負載特別高時，Claude Code 會提示您這麼做，例如 `Opus is experiencing high load, please use /model to switch to Sonnet`。在 Fable 模型上，訊息會指出 Fable。

  在 Claude Desktop 應用程式執行的工作階段中，例如 Code 分頁或 Cowork，訊息會顯示為 `Opus is experiencing high load. Switch to Sonnet.`，您可以使用應用程式的模型選擇器切換模型。

### Request timed out

API 未在連線期限內回應。

```text theme={null}
Request timed out
```

預設的請求逾時為 10 分鐘。若您將 [`API_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `0`，此請求逾時便會關閉。[首位元組期限](#no-response-from-api)與主體閒置逾時在您設定 `0` 時不會關閉，因此串流請求仍會受到[其中適用於您連線的那些](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)限制。非串流的嘗試在本機工作階段中會保留其 300 秒的限制，仍可能以此訊息結束。

**處理方式：**

* 若每個請求都以此訊息失敗，且您已將 `API_TIMEOUT_MS` 設為 `0`，請檢查 `claude --version`。若版本早於 v2.1.305，請更新 Claude Code 或設定一個正值。
* 重試該請求
* 若原因是網路或代理伺服器速度較慢，請依照[自動重試](#automatic-retries)的說明提高 `API_TIMEOUT_MS`
* 若逾時頻繁發生，而您的網路在其他方面都正常，請參閱下方的[網路與連線錯誤](#network-and-connection-errors)

### No response from API

Claude Code 傳送了串流請求，而 API 未在首位元組期限內傳回任何回應標頭。Claude Code 會中止此類請求，而不是等待完整的 `API_TIMEOUT_MS` 請求逾時，並在[重試預算](#tune-retry-behavior)允許時再次傳送。若重試也超過期限，該回合便會以此訊息結束，訊息中會顯示每次嘗試等待了多久。

若您設定了 [`CLAUDE_CODE_RETRY_WATCHDOG`](https://code.claude.com/docs/zh-TW/env-vars)，Claude Code 會依照[調整重試行為](#tune-retry-behavior)中所述的預算持續重試，而不會結束該回合。

```text theme={null}
API Error: No response from API (waited 3m, then 10m on the retry). If a proxy or gateway on your network holds responses until they complete, raise API_TIMEOUT_MS or CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS to wait longer.
```

Claude Code 會分別設定第一次嘗試等待回應標頭的時間與重試的等待時間：

* **第一次嘗試**：當您將 [`CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 1 或以上時使用該值，並限制在 10 秒到 30 分鐘之間。否則 Claude Code 會使用[串流閒置監控](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)中列出的位元組層級監控逾時，因此變更該逾時的變數也會變更此等待時間。無論哪種情況，Claude Code 都會依請求主體每 32KB 增加一秒。
* **重試**：比 `API_TIMEOUT_MS` 少一秒，預設略低於 10 分鐘，讓重試能撐過會保留回應直到生成完成的代理伺服器或閘道。在 Amazon Bedrock 上，重試使用與第一次嘗試相同的期限，訊息只會顯示一個時間長度，而非兩個。

  除了 Amazon Bedrock 之外，若您將 `API_TIMEOUT_MS` 設為 `0`，重試會等待 10 分鐘加上每 32KB 一秒，若第一次嘗試的時間更長則等待與其相同的時間。

兩種等待時間都不會超過比正值 `API_TIMEOUT_MS` 少一秒的時間，而低於 11 秒的正值 `API_TIMEOUT_MS` 會關閉此期限。位元組層級監控僅在回應標頭抵達後才會啟動，因此在那之後停止傳送位元組的回應會改依[串流停滯規則](#automatic-retries)處理，而非此期限。

在 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段中，只有當您將 `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS` 設為 `1` 或以上以[將其開啟](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#retry-an-unanswered-request-sooner-with-the-first-byte-deadline)時，此期限才會執行。

**處理方式：**

* 再次傳送您的訊息。您原本的訊息仍在對話中，因此若提示詞很長，您可以輸入 `try again`，而不必貼上整段內容。
* 若再次發生，請將其視為[網路或代理伺服器問題](#unable-to-connect-to-api)處理。
* 若您網路上的代理伺服器或閘道會保留回應直到完成，請提高 `API_TIMEOUT_MS`，讓重試等待更久。在 Amazon Bedrock 上，也請一併提高 `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`。
* 若第一次嘗試持續逾時而重試隨後成功，請提高 `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`，讓第一次嘗試也能等待足夠久。

在 v2.1.242 之前，Claude Code 會等待完整的 `API_TIMEOUT_MS` 請求逾時（預設 10 分鐘），才讓未獲回應的串流請求失敗。在 v2.1.261 之前，重試會等待與第一次嘗試相同的期限，且訊息不會顯示時間長度。在 v2.1.307 之前，Claude Code 在 Claude apps 閘道工作階段中會忽略 `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`。

### The response above may be incomplete

串流請求在回應仍在進行中時失敗，此時 Claude 已完成一段文字或一個工具呼叫，或在完成思考後已開始其中之一。重新傳送請求可能會讓相同的工具呼叫執行兩次，因此 Claude Code 會保留 Claude 已完成的輸出並附加此通知，而不是捨棄該回合。您看到的變體會指出原因：

```text theme={null}
API Error: Server error mid-response. The response above may be incomplete.
API Error: Connection lost mid-response. The response above may be incomplete.
API Error: Your computer went to sleep mid-response. The response above may be incomplete.
API Error: The response stopped arriving. The response above may be incomplete.
API Error: Part of the response never arrived. The response above may be incomplete.
API Error: The response stream was malformed. The response above may be incomplete.
```

* `Server error mid-response`：串流途中發生過載或 5xx 伺服器錯誤。此變體需要 Claude Code v2.1.199 或更新版本；在此之前，這種情況會捨棄部分輸出，並將整個回合回報為錯誤。
* `Connection lost mid-response`：連線中斷。當代理伺服器或閘道在回應完成之前就正常結束回應主體時，您也會看到此變體。
* `Your computer went to sleep mid-response`：Claude Code 偵測到您的電腦在回應串流期間進入睡眠。電腦喚醒後，Claude Code 會將連線視為已中斷並停止從中讀取。
* `Part of the response never arrived`：某個串流事件在 API 與 Claude Code 之間遺失，因此後續事件參照了從未抵達的內容。在 v2.1.281 之前，這種情況會以 `API Error: Content block not found` 結束該回合。
* `The response stream was malformed`：收到了一個針對已經結束之內容區塊的事件，或收到了一個已損壞的事件。已損壞的事件是指其資料不是有效的 JSON、內容遺失，或內容與事件類型不符的事件。在 v2.1.284 之前，當含有無效 JSON 的事件在 Claude 完成思考、一段文字或一個工具呼叫之後抵達時，會改為顯示剖析器的原始錯誤，例如以 `API Error: JSON Parse error` 開頭的錯誤。
* `The response stopped arriving`：連線保持開啟但停止傳送資料，因此串流閒置監控將其中止。在 v2.1.222 之前，對於透過 `ANTHROPIC_BASE_URL` 或 `ANTHROPIC_AWS_BASE_URL` 連線的[閘道](https://code.claude.com/docs/zh-TW/gateways.md)，即使伺服器的 keep-alive ping 仍持續抵達，Claude Code 也可能回報此失敗，因為在這些連線上它只計算已剖析的回應事件；升級後即可停止這些路由上的誤判逾時。透過供應商基礎 URL（例如 `ANTHROPIC_BEDROCK_BASE_URL`）連線的閘道不受位元組監控包覆；請參閱[串流閒置監控](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)。

在 v2.1.227 之前，`Connection lost mid-response` 顯示為 `Connection closed mid-response`，而 `The response stopped arriving` 顯示為 `Response stalled mid-stream`。

當遺失、重複或損壞的串流事件在 Claude 開始任何文字或工具呼叫之前抵達時，您不會看到此通知：

* 若 Claude 只完成了思考，Claude Code 會重新發出請求。當重新發出的串流以相同方式中斷時，該回合會以 `Part of the response never arrived and no response was produced. Try again.` 或 `The response stream was malformed and no response was produced. Try again.` 結束。
* 若尚未完成任何內容，Claude Code 會改以非串流方式重新傳送請求。若您已使用 [`CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK`](https://code.claude.com/docs/zh-TW/env-vars) 關閉該備援，對於遺失的事件，該回合會以 `API Error: Content block not found` 結束；對於重複的事件，則以 `API Error: Content block already closed` 結束。對於關閉備援時的損壞事件，該回合會以 `API Error: Stream event unreadable` 或剖析器的原始錯誤結束。

在四種情況下，Claude Code 處理失敗時不會立即顯示此通知：

* 在回應較早的階段，Claude Code 會重試該失敗，或以不同的錯誤結束該回合。請參閱[自動重試](#automatic-retries)。
* 當其中一種失敗在 Claude 完成回應之後才抵達時，Claude Code 會保留完整的回應並正常結束該回合，不顯示此通知。在 v2.1.222 之前，當連線在回應完成後中斷或停滯時，Claude Code 會顯示此通知，並將該回合回報為錯誤，即使回應是完整的。
* 在[非互動工作階段](https://code.claude.com/docs/zh-TW/headless.md)中，例如 `-p` 執行、[Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 執行或[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，當被截斷的回應位於主對話中且包含文字但沒有工具呼叫時，您不需要自行傳送 `continue`：Claude Code 會保留部分輸出，並提示 Claude 從停止處繼續，最多連續三次。只有在 Claude Code 用完這些繼續次數後，您才會看到此類回應的此通知。在 v2.1.246 之前，Claude Code 會在第一次截斷時就以此通知結束非互動回合。
* 在 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#api-errors-in-subagents) 中，無論工作階段是否為互動式：當其被截斷的回應包含文字但沒有工具呼叫時，Claude Code 會提示 subagent 繼續。只有在這些繼續次數用完之後，此通知才會成為 subagent 的最後一則訊息。在 v2.1.257 之前，subagent 會在第一次截斷時就顯示此通知。

**處理方式：**

* 在互動工作階段中，閱讀畫面上保留的回應：Claude Code 會保留 Claude 在錯誤發生前完成的每個區塊，但在回合結束時會捨棄被中斷的最後一個區塊，因此最後幾句話或工具呼叫可能會遺失。回覆 `continue` 讓 Claude 從其最後完成的區塊接續。
* 在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)（`-p`）中：
  * 使用預設文字輸出時，Claude Code 會印出它仍保有的、該回合較早產生的最後一段完成文字，接著印出此訊息。若它沒有保有任何文字，Claude Code 會只印出此訊息，例如因為 Claude Code 在回合中途壓縮了對話並清除了該文字。在 v2.1.219 之前，Claude Code 在 `-p` 文字輸出中只會印出此訊息，並捨棄已產生的回應。
  * 使用 `--output-format json` 或 `stream-json` 時，Claude Code 會在 `result` 欄位中回報此訊息。
  * 若要在連線穩定後繼續該回合，請依照[繼續對話](https://code.claude.com/docs/zh-TW/headless.md#continue-conversations)的說明恢復工作階段並傳送 `continue`。

### Auto mode cannot determine the safety of an action

[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)用來分類動作的模型無法做出決定，因此自動模式未自動核准該動作。您看到的訊息取決於分類器失敗的方式。

在您工作目錄內的讀取、搜尋與編輯會略過分類器，因此在所有這些情況下都能繼續運作。

當分類器模型無法使用時：

```text theme={null}
<model> is temporarily unavailable, so auto mode cannot determine the safety of <tool> right now. Wait a moment and then try this action again.
```

在互動工作階段中，工具呼叫下方會顯示一列暗色的 `Not run · auto mode's check had no usable answer`，而不是此訊息。此列也可能取代表示[伺服器未給出判定](#the-server-returned-no-safety-verdict)的訊息，或在遠端工作階段以外，取代以 `Auto mode could not evaluate` 開頭的訊息。按下 `Ctrl+O` 即可在[逐字稿檢視器](https://code.claude.com/docs/zh-TW/interactive-mode.md#transcript-viewer)中閱讀其訊息。在 v2.1.296 之前，該訊息會以紅色錯誤顯示。

當 Claude Code 能判斷失敗類別時，會在 `temporarily unavailable` 之後以括號標示類別，例如 `<model> is temporarily unavailable (rate-limited), so auto mode cannot determine the safety of <tool> right now`。類別包括 `(rate-limited)`、`(overloaded)`、`(server error)`、`(timed out)` 與 `(connection failed)`。若 `(timed out)` 或 `(connection failed)` 重複出現，請檢查您的連線；請參閱[無法連線至 API](#unable-to-connect-to-api)。在 v2.1.229 之前，訊息從不標示類別，且顯示為 `Wait briefly and then try this action again`。

當沒有合適的類別時，訊息會以不含括號類別的形式出現；多次失敗也會產生這種形式。在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 上，包括 [Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)，當您的 AWS 帳戶無法呼叫訊息中指出的模型時，也會出現此訊息，而且在您的帳戶獲得該模型的存取權之前，每次重試都會重複發生此失敗。

**處理方式：**

* 幾秒後重試；Claude 會看到相同的訊息，通常會自行重試。暫時性失敗與[自動模式資格](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)無關；您不需要變更設定
* 若重試持續失敗，請繼續進行唯讀工作，稍後再回到被封鎖的動作
* 在 Amazon Bedrock 上，若每次重試都出現此訊息，請確認您的帳戶能呼叫訊息中指出的模型：對於標準 Amazon Bedrock 模型，請確認您的 [IAM 政策](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#iam-configuration)允許呼叫該模型；對於 Mantle 模型 ID，請[聯絡您的 AWS 帳戶團隊](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#mantle-endpoint-errors)
* 若每次重試都出現此訊息，且訊息指出的是您在 [`CLAUDE_CODE_AUTO_MODE_MODEL`](https://code.claude.com/docs/zh-TW/permission-modes#choose-the-classifier-model) 中設定的模型，請確認您工作階段所使用的 API 或雲端供應商有提供該模型 ID。若沒有，請將該變數設為其有提供的模型 ID，或取消設定該變數以使用[預設分類器模型](https://code.claude.com/docs/zh-TW/permission-modes.md#default-classifier-model)。

當分類器請求因您的 OAuth token 過期或被另一個工作階段輪替而失敗時，Claude Code 會重新整理 token 並重試該請求一次，因此例行的 token 過期不會以此訊息呈現。在 v2.1.216 之前，過期或被輪替的 token 會使每個分類器請求失敗，而自動模式會以此訊息拒絕每個受檢查的動作，直到 token 重新整理為止。

當分類器傳回無法剖析的回應時：

```text theme={null}
Auto mode could not evaluate this action and is blocking it for safety — run with --debug for details
```

**處理方式：**

* 重試該動作；通常下一次嘗試就會成功
* 執行 `claude --debug` 並重複該動作，以在除錯日誌中查看詳細資料

當另一個 API 安全檢查因先前的對話內容而封鎖分類器請求時：

```text theme={null}
Auto mode could not evaluate this action and is blocking it for safety — a safety check separate from auto mode blocked this request because of earlier conversation content — it isn't about the action itself — run with --debug for details
```

Claude Code 會拒絕該動作，但會告知 Claude 這並不是判定該動作不安全，並請它繼續處理其他工作而非重試。這些拒絕不會計入[自動模式的暫停閾值](https://code.claude.com/docs/zh-TW/permission-modes.md#when-auto-mode-falls-back)。在[非互動](https://code.claude.com/docs/zh-TW/headless.md) `-p` 執行中，Claude Code 不會停止執行。Claude 收到的內容取決於它在何處請求該動作：

* 對於未使用 `--input-format stream-json` 的 `-p` 執行中的[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)，Claude Code 會傳回包含 `Agent aborted: auto mode classifier request refused by the safety safeguard in headless mode` 的錯誤結果
* 在其他所有地方，包括互動工作階段與 `-p` 執行的主對話，Claude Code 會將該拒絕傳回給 Claude

在 v2.1.225 之前，Claude Code 會將這些拒絕計入暫停閾值，並傳回與真正分類器封鎖相同的拒絕訊息。

**處理方式：**

* 這並非針對您的動作所做的決定。當自動模式將對話傳送給分類器時，您對話中既有的內容觸發了 API 上的安全篩選器
* 重試沒有幫助；相同的對話內容會再次觸發篩選器
* 在互動工作階段中，切換至其他[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)，以便在出現提示時核准該動作
* 開始一個不含觸發內容的新對話

當對話長度超出 Claude Code 分類器請求的容量，且 Claude Code 無法[自行壓縮](#was-not-reviewed-and-did-not-run)時：

```text theme={null}
Auto mode classifier transcript exceeded context window — falling back to manual approval (try /compact to reduce conversation size)
```

該動作的處理方式取決於 Claude 在何處請求它：

* 在互動工作階段中，自動模式會針對該動作改用一般的權限提示，讓您可以手動核准或拒絕
* 對於[非互動](https://code.claude.com/docs/zh-TW/headless.md) `-p` 執行中未使用 `--input-format stream-json` 的[背景 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)，Claude Code 會傳回包含 `Agent aborted: auto mode classifier transcript exceeded context window in headless mode` 的錯誤結果，且執行會繼續
* 在未使用 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 的 `-p` 執行中的其他地方，沒有可改用的提示，因此該動作不會執行，而執行會繼續

**處理方式：**

* 在互動工作階段中，於出現的提示中核准或拒絕該動作
* 在互動工作階段中，執行 `/compact` 以縮減對話大小，讓後續動作能再次容納於分類器視窗內

### The server returned no safety verdict

在[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)下，當伺服器未對某個動作給出判定時，自動模式會拒絕該動作。當 Claude Code 能判斷類別時，拒絕訊息會以括號標示類別，例如 `(timed out)`：

```text theme={null}
The server-side auto mode classifier gave no verdict (timed out), so auto mode cannot determine the safety of <tool>.
```

訊息的其餘部分會告知 Claude 重試一次是否有幫助。在其中某些拒絕之前，Claude Code 會等待，讓 Claude 的下一次嘗試不會立即接續。在互動工作階段的等待期間，旋轉指示器會顯示 `Auto mode check unavailable` 及倒數計時，按下 `Esc` 會中斷該回合。

連續十個回應都沒有判定之後，自動模式會停止該回合：

```text theme={null}
Auto mode is unavailable — the server returned no safety verdict for the last 10 responses, so Claude stopped. Send a message to try again, or switch out of auto mode.
```

某些拒絕不會計入這十次，包括[因 hook 或 mod 的變更而產生的拒絕](#hook-changed-input-after-review)。

停止訊息在不同類型的工作階段中出現的位置不同：

* 在互動工作階段中，訊息會以警告形式出現在逐字稿中，且該回合結束
* 在[非互動](https://code.claude.com/docs/zh-TW/headless.md) `-p` 執行中，執行會結束並回報執行錯誤。使用預設文字輸出時，訊息會印在 stderr 上。
* 當 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 達到此上限時，subagent 會在完成前停止，Claude 會收到它已產生的內容，並附上自動模式已將其停止的說明

**處理方式：**

* 在互動工作階段中，按下 `Ctrl+O` 以在[逐字稿檢視器](https://code.claude.com/docs/zh-TW/interactive-mode.md#transcript-viewer)中閱讀拒絕文字。
* 若拒絕訊息指出 `(the conversation is too long for the check)`，請在 Claude Code 提示字元中執行 `/compact` 以縮短對話。在對話縮短之前，再傳送訊息也會得到相同的拒絕。若您已關閉[自動壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#autocompactenabled)，請將其重新開啟，讓 Claude Code 下次能自行壓縮。
* 再傳送一則訊息讓 Claude 再試一次。回應計數會重新開始。
* 若停止情況重複發生，且您的請求會經過 [LLM 閘道或代理伺服器](https://code.claude.com/docs/zh-TW/llm-gateway)，請檢查它是否會提前截斷或改寫串流回應。[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)說明了哪些閘道行為會導致拒絕，而[閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through)列出了需要原樣傳遞的內容。
* 在啟動 Claude Code 之前設定 `CLAUDE_CODE_AUTO_MODE_SERVER=0`，改為使用其自身的分類器請求。在 v2.1.281 之前，Claude Code 在直接連線至 Anthropic API 時不會讀取此變數。
* 若要改為自行核准動作，請[切換離開自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)

在 v2.1.280 之前，Claude Code 會立即拒絕來自無判定回應的每個動作，且從不停止該回合。

在 v2.1.302 之前，在直接連線至 Anthropic API 時，Claude Code 不會壓縮已長到超出伺服器檢查容量的對話。

#### `a hook changed this call's input after auto mode reviewed it`

此拒絕表示某個 hook 或 mod 在伺服器審查之後[變更了該呼叫的輸入](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-updatedinput-in-auto-mode)，因此審查並未涵蓋實際將執行的內容。這並不是判定該動作不安全。

同一個 Claude 回應中的後續呼叫可能會以此原因遭到拒絕：

```text theme={null}
another call in this response was changed by a hook after auto mode reviewed it, or could not be confirmed unchanged
```

Claude 接著可以再次發出每個遭拒絕的呼叫，讓伺服器進行審查。若出現權限提示，請回應它。除非 Claude 在回覆中表示自動模式無法檢查該呼叫，否則您不需要做其他任何事。屆時，請停止該變更或自行核准該呼叫，並請 Claude 再試一次該呼叫：

* **停止變更**：關閉變更了該呼叫或同一個 Claude 回應中較早呼叫的 [hook](https://code.claude.com/docs/zh-TW/hooks.md#disable-or-remove-hooks) 或 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#turn-mods-on-or-off)，或請您的管理員將其關閉。若要尋找 hook，請在 Claude Code 提示字元中執行 [`/hooks`](https://code.claude.com/docs/zh-TW/hooks#the-%2Fhooks-menu)。在終端機工作階段中，執行 `/plugin` 以查看作用中的 mod。
* **自行核准該呼叫**：[切換至手動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)

### Was not reviewed and did not run

`was not reviewed and did not run` 拒絕表示對話太長，[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)分類器無法檢查該動作，因此該動作未執行。Claude Code 會將此訊息傳回給 Claude：

```text theme={null}
<tool> was not reviewed and did not run: the conversation is too long for auto mode's classifier. Claude Code will try to compact the conversation before the next request; if this action is still needed after that, issue it again and it will be reviewed normally.
```

若壓縮失敗，分類器無法檢查的後續動作會收到另外兩種訊息之一：

* [`gave no verdict (the conversation is too long for the check)`](#the-server-returned-no-safety-verdict) 拒絕
* [`Auto mode classifier transcript exceeded context window`](#auto-mode-cannot-determine-the-safety-of-an-action) 訊息

**處理方式：**

* 若訊息所宣告的壓縮成功，您不需要做任何事。
* 若您看到上述兩種訊息之一，請在 Claude Code 提示字元中執行 `/compact`，自行縮短對話。若您已關閉[自動壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#autocompactenabled)，請將其重新開啟，讓 Claude Code 下次能自行壓縮。

### Agent terminated early due to an API error

[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的 API 請求發生終止性失敗，例如因為達到用量上限或伺服器錯誤的重試次數用盡，因此 subagent 在完成其工作之前就停止了。此訊息需要 Claude Code v2.1.199 或更新版本；在此之前，API 錯誤文字會被當作 subagent 的結果傳回給 Claude。

```text theme={null}
Agent terminated early due to an API error: <error detail>
```

**處理方式：**

* 將冒號後的錯誤詳細資料對應到本頁上的相應章節，例如[用量上限](#usage-limits)或[伺服器錯誤](#server-errors)，並依照該章節的步驟處理
* 底層錯誤排除後，請 Claude 重試該工作，或[恢復 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents)

當速率限制、過載或伺服器錯誤中斷了已產生文字輸出的前景 subagent 時，Claude 會收到標示為不完整的部分輸出，而不是此錯誤。僅輸出工具呼叫的 subagent 也會收到此錯誤；在 v2.1.199 中，這種情形會改為傳回空的部分結果。請參閱 [subagent 中的 API 錯誤](https://code.claude.com/docs/zh-TW/sub-agents.md#api-errors-in-subagents)。

## 用量上限

本節中的大多數錯誤表示與您的帳戶或方案相關的配額已達到。其中三個的運作方式不同：[`Server is temporarily limiting requests`](#server-is-temporarily-limiting-requests) 是與您的方案配額無關的伺服器端節流，[`Usage credits required for 1M context`](#usage-credits-required-for-1m-context) 是權利檢查而非耗盡的配額，[`The prompt to confirm went unanswered`](#the-prompt-to-confirm-went-unanswered) 表示用量點數同意提示已在未獲回應的情況下關閉，無論是否達到配額。

### You've hit your session limit

訂閱方案包括滾動使用額度。當額度用完時，您會看到以下其中一條訊息：

```text theme={null}
You've hit your session limit · resets 3:45pm
You've hit your weekly limit · resets Mon 12:00am
You've hit your Opus limit · resets 3:45pm
You've hit your Sonnet limit · resets 3:45pm
```

Claude Code 會阻止進一步的請求，直到訊息中顯示的重設時間。工作階段和每週限制在所有模型中共享，因此切換模型不會恢復存取。Opus 和 Sonnet 限制各自僅適用於對該模型系列的請求，因此使用 `/model` 切換到該系列外的模型可讓您繼續工作。

在使用 claude.ai 訂閱登入的互動式工作階段中，Claude Code 也可以在開啟的工作階段中等待，並在重設後不久繼續中斷的任務。請參閱[等待用量上限重設](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset)以了解您看到的內容、如何開始或取消等待，以及如何關閉自動繼續。在 v2.1.234 之前，Claude Code 不提供此等待功能。

使用量同時計入工作階段和每週額度。單次大量活動突發（例如大型工作流程扇出）可能會在工作階段視窗重設之前耗盡每週額度。

**該怎麼做：**

* 等待錯誤中顯示的重設時間
* 在[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)的 Code 標籤中，工作階段限制卡片提供 **Auto-continue when limits reset** 核取方塊。每週限制卡片則不提供。勾選後，桌面應用程式會在重設後重試中斷的回合，並在卡片上顯示重試時間。桌面核取方塊和 CLI 在 `/config` 中的 **Continue automatically at usage limit** 設定是分開的，因此請分別關閉每一個。
* 對於 Opus 或 Sonnet 限制，執行 `/model` 並切換到該系列外的模型以繼續工作。每個模型都有自己的提示快取，因此下一個請求會重新讀取整個對話，沒有快取命中；請參閱[切換模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)
* 執行 `/usage` 以查看您的方案限制和重設時間
* 執行 `/usage-credits` 以在 Pro、Max 和 Ultra 上購買額外使用量，或在 Team 和 Enterprise 上向您的管理員請求。請參閱[付費方案的用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)以了解如何計費。
* 若要升級您的方案以獲得更高的基本限制，請參閱 [claude.com/pricing](https://claude.com/pricing)

在視窗用完之前，Claude Code 可以警告您已使用大部分額度，訊息例如 `You've used 85% of your session limit · resets 3:45pm`。若要持續監視您的剩餘額度，請將 `rate_limits` 欄位新增至[自訂狀態列](https://code.claude.com/docs/zh-TW/statusline.md#rate-limit-usage)，或在桌面應用程式中按一下[使用量環](https://code.claude.com/docs/zh-TW/desktop.md#check-usage)。

### Usage credits required for 1M context

選定的模型使用 1M token 擴展上下文視窗，而您的方案僅透過用量點數包括它。

```text theme={null}
API Error: Usage credits required for 1M context · run /usage-credits to turn them on (they take effect after you restart Claude Code), or /model to switch to standard context
```

在 Claude 桌面應用程式執行的工作階段中，提示不會命名任何命令：它指向 claude.ai 使用量設定頁面，或在 Team 和 Enterprise 方案上說在 claude.ai/admin-settings/usage 開啟用量點數，或請您的管理員處理。

這是權利檢查，而非配額耗盡。即使您的工作階段和每週額度有剩餘容量，它也會觸發。請參閱[擴展上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)以了解哪些方案直接包括 1M 上下文，哪些需要用量點數。

當此錯誤在對話中途出現，因為上下文增長超過 200K token 時，Claude Code 會自動將對話壓縮回標準上下文限制以下，並之後將工作階段保持在該限制，因此無需採取任何行動。在 v2.1.172 之前的版本上，錯誤會在每個後續請求（包括 `/compact`）上重複；在這些版本上執行 `/clear` 以恢復。以下步驟適用於您明確選擇 `[1m]` 模型的情況。

**該怎麼做：**

* 執行 `/model` 並選擇不帶 `[1m]` 後綴的變體以回退到標準上下文視窗
* 訊息提及 `/usage-credits` 的地方，執行它以在 Pro、Max 和 Ultra 上為 1M 變體開啟計量計費，或在 Team 和 Enterprise 上向您的管理員請求用量點數。一旦用量點數開啟，請依訊息所說重新啟動 Claude Code 或開始新的工作階段。在此之前，工作階段會保持在標準上下文限制。
* 如果 `/model` 後錯誤仍然存在，1M 模型 ID 可能在其他地方設定。請參閱[設定您的模型](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)以按優先順序檢查設定位置。
* 若要從模型選擇器中完全移除 1M 變體，請設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/env-vars)

在 v2.1.268 之前，訊息以 `run /usage-credits to turn them on, or /model to switch to standard context` 結尾，並未提及重新啟動。

### The prompt to confirm went unanswered

當 [Fable 用量點數同意提示](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)在無人回應的情況下關閉時，Claude Code 會以以下其中一條訊息結束回合：

```text theme={null}
Fable limit reached · continuing on Fable 5.1 uses usage credits, and the prompt to confirm went unanswered — nothing was sent · answer it where this session is running, or /model to change
Fable 5.1 now uses usage credits · the prompt to confirm went unanswered — nothing was sent · answer it where this session is running, or /model to change
```

訊息會命名工作階段的 Fable 模型，因此在 Fable 5 上它們會讀作 `continuing on Fable 5` 和 `Fable 5 now uses usage credits`。在 v2.1.257 之前，第一條訊息以 `Fable 5 limit reached` 開頭。

這發生在 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)、[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊友工作階段，以及另一個應用程式透過 Agent SDK 託管的工作階段中。如需 Claude Code 何時關閉提示，請參閱 [Fable 和用量點數](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)。

**該怎麼做：**

* 在工作階段執行所在的終端機或託管它的應用程式中，發送另一個提示詞，當同意提示重新出現時回答它。對於背景工作階段，請先從 [agents 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)附加到它。從 Remote Control 用戶端重新發送會再次顯示此訊息，因為用戶端無法顯示提示。
* 執行 `/model` 以切換到不計費用量點數的模型
* 若要給自己更多時間，請將 [`dialogExpiry`](https://code.claude.com/docs/zh-TW/settings-reference#dialogexpiry) 設定為更長的值或 `"never"`

在 v2.1.236 之前，此訊息不會出現：當 Remote Control 用戶端已連接時，Claude Code 會等待 60 秒以獲得答案，然後在您的預設模型上繼續回合。

### Server is temporarily limiting requests

API 應用了與您的方案配額無關的短期節流。

```text theme={null}
API Error: Server is temporarily limiting requests (not your usage limit)
```

Claude Code 透過真實限制回應所攜帶的統一配額標頭是否缺失來區分這些情況。自 v2.1.199 起，無論您如何驗證，這都會[自動重試](#automatic-retries)並進行退避，然後才顯示。在較早的版本上，使用 claude.ai 訂閱登入的工作階段在第一次出現時即讓回合失敗；只有 API 金鑰和 Enterprise 登入會重試它。

**該怎麼做：**

* 稍等片刻後重試
* 如果問題持續，請檢查 [status.claude.com](https://status.claude.com)

### Request rejected (429)

您已達到為您的 API 金鑰、Amazon Bedrock 專案或 Google Cloud 專案設定的速率限制。

```text theme={null}
API Error: Request rejected (429) · this may be a temporary capacity issue. If it persists, check https://status.claude.com.
```

結尾的句子指出檢查服務健康狀況的位置，並因提供者而異。Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 設定會指出該提供者的服務狀態，而不是 Anthropic 狀態頁面。自訂 `ANTHROPIC_BASE_URL` 會指出閘道主機。

當代理伺服器、負載平衡器或 Claude Code 與 API 之間的閘道以其自己的 HTML 429 頁面回應時，`·` 後面的文字是該頁面的標題（如果有的話），例如 `Too Many Requests`。在 v2.1.281 之前，整個頁面的標記會被列印在 `·` 後面。

**該怎麼做：**

* 執行 `/status` 並確認作用中的憑證是您預期的憑證。環境中殘留的 `ANTHROPIC_API_KEY` 可能會透過低階金鑰而不是您的訂閱路由請求。
* 檢查您的提供者主控台以了解作用中的限制，並在需要時請求更高的層級
* 對於 Anthropic API 金鑰，請參閱[速率限制參考](https://platform.claude.com/docs/en/api/rate-limits)以了解層級如何運作以及如何設定每個工作區的上限
* 降低並行性：避免執行許多平行 subagent，或使用 `/model` 切換到較小的模型以進行高容量指令碼執行

### You've hit your monthly spend limit

您的方案包含的使用量無法涵蓋此請求，而原本會為其付費的[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)已達到支出限制。這發生在您的方案的其中一個使用視窗已用完時，或當請求是僅由用量點數支付的請求時，例如對[計費至用量點數](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)的模型的請求。訊息會指出是誰的限制阻止了您。`·` 後面的文字說明如何提高該限制，並因您的方案和您是否管理計費而異：

```text theme={null}
You've hit your monthly spend limit · raise it at https://claude.ai/settings/usage?from=cc_cli_limit_message
You've hit your individual spend limit · ask your admin for a higher limit
You've hit your org's monthly spend limit · visit https://claude.ai/admin-settings/usage to raise it
You've hit your team's shared budget · ask your admin to raise it at https://claude.ai/admin-settings/usage
You've hit your channel's monthly spend limit · an org owner or channel manager can raise it in the channel's Claude settings
```

`team's shared budget` 是管理員分配給您所屬群組的集區預算；訊息不會命名該群組。`channel's monthly spend limit` 是工作階段執行所在的 Slack 頻道的預算，因此您的組織可能在其外仍有預算。

當您的方案的其中一個視窗是用完的視窗時，訊息也會說明該視窗何時重設，例如 `· your session limit resets 3:45pm`，存取會在那時恢復，無需任何人提高限制。在採用基於使用量計費的組織上，訊息會說 `usage limit` 而不是 `spend limit`，如 `You've hit your individual usage limit`。

如果您透過 Claude 應用程式閘道連接並看到小寫 `spend limit reached`，那是您的閘道營運者設定的上限；請參閱 [Spend limit reached](#spend-limit-reached)。

**該怎麼做：**

* 在 Pro、Max 和 Ultra 上，在 claude.ai 的[**設定 > 使用量**](https://claude.ai/settings/usage)中提高您的每月支出限制，或執行 `/usage-credits`
* 在 Team 和 Enterprise 上，如果您管理計費，請在[**組織設定 > 使用量**](https://claude.ai/admin-settings/usage)中提高限制，或請管理員提高。`/usage-credits` 會為您向管理員發送該請求
* 對於頻道的限制，請組織擁有者或頻道的管理員在 claude.ai 上提高它。請參閱 Claude Tag 文件中的[每頻道限制](https://claude.com/docs/claude-tag/admins/set-spend-limit#per-channel-limits)
* 如果訊息指出您的方案視窗的重設時間，您可以改為等待它
* 執行 `/usage` 以查看您的方案視窗和每個視窗何時重設

### Spend limit reached

您透過 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)連接，並已超過閘道營運者設定的[支出上限](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)。閘道會阻止您的請求，直到指定的期間重設或營運者提高上限。它將每個被阻止的 `429` 回應標記為 `x-should-retry: false`，因此 Claude Code 會顯示此訊息而不重試。

```text theme={null}
spend limit reached (daily; resets 2026-08-09 00:00 UTC)
```

訊息會指出上限的期間和重設時間，當營運者設定了 `blocked_message` 時，他們的指示會跟在後面。在 v2.1.225 之前，訊息只顯示 `spend limit reached`；較舊版本上的閘道仍會發送該較短的形式。

**該怎麼做：**

* 等待訊息指出的重設時間，或如果訊息包含營運者的指示，請遵循它們
* 如果您經常達到上限，請要求您的閘道營運者提高上限

相關訊息 `spend limit unavailable` 表示閘道無法讀取其支出記錄，並作為預防措施阻止了請求，而不是因為超過您的上限。它通常會自行解除；如果持續發生，請告知您的閘道營運者。

### Credit balance is too low

您的 Console 組織已用完預付點數，或 Claude Code 正在使用 Console API 金鑰發送您的請求，而您原本打算使用您的訂閱。

```text theme={null}
Credit balance is too low
```

**該怎麼做：**

* 如果您有 Pro、Max、Ultra、Team 或 Enterprise 方案並看到此訊息，執行 `/status` 並檢查 `API key` 列。環境中已核准的 `ANTHROPIC_API_KEY` 會透過該金鑰而不是您的訂閱路由請求。在目前的 shell 中取消設定它，並從您的 shell 設定檔中移除它，然後重新啟動 `claude`。如果您還沒有使用您的訂閱登入，請執行 `/login`。
* 在 [platform.claude.com/settings/billing](https://platform.claude.com/settings/billing) 新增點數，並考慮在那裡啟用自動儲值，以便在餘額歸零之前自動補充
* 在 Console 中設定每個工作區的支出上限，以防止單個專案耗盡組織餘額。請參閱[有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)。

### Could not update your spend limit

伺服器拒絕了您從達到支出限制時出現的提示中進行的支出限制變更。

```text theme={null}
Could not update your spend limit: <reason from the server>
```

當伺服器解釋拒絕原因時，訊息以該原因結尾，重試相同值會再次失敗。當失敗沒有伺服器提供的原因（例如連線中斷）時，訊息會顯示 `Could not update your spend limit. Press Enter to retry.`，重試可能會成功。在 v2.1.216 之前，Claude Code 對每個失敗都顯示通用形式。

**該怎麼做：**

* 如果訊息包含原因，請選擇滿足它的限制，例如較低的金額
* 如果訊息僅顯示通用形式，請重試；失敗可能是暫時的
* 如果變更持續失敗，請改為在瀏覽器中從您的 [claude.ai 計費設定](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)進行變更

## 身分驗證錯誤

這些錯誤表示 Claude Code 無法向 API 證明您的身分。隨時執行 `/status` 即可查看目前使用中的憑證。

### 未登入

此工作階段沒有可用的有效憑證。

```text theme={null}
Not logged in · Please run /login
```

在由 Claude Desktop 應用程式執行的工作階段中（例如 Code 分頁或 Cowork），訊息會顯示為 `Authentication required · Sign in again to continue`，您需要從應用程式重新登入。

如果您在另一個使用相同[設定目錄](https://code.claude.com/docs/zh-TW/claude-directory.md)的 Claude Code 視窗中以 claude.ai 帳戶登入，顯示此訊息的互動式工作階段會自動開始使用該登入，無需重新啟動。

在 macOS 上的 v2.1.286 之前，您從另一個視窗登入後，工作階段可能仍持續顯示此訊息。在這些版本上，請重新啟動顯示此訊息的工作階段。

**處理方式：**

* 執行 `/login`，以您的 Claude 訂閱或 Console 帳戶進行身分驗證
* 如果您預期由環境變數進行身分驗證，請確認 `ANTHROPIC_API_KEY` 已在您啟動 `claude` 的 shell 中設定並匯出
* 對於無法進行互動式登入的 CI 或自動化作業，請設定一個 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼，在啟動時取得金鑰
* 請參閱[身分驗證優先順序](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)，了解存在多個憑證時 Claude Code 會使用哪一個

如果您反覆被要求登入，請參閱[未登入或 token 已過期](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#not-logged-in-or-token-expired)，了解系統時鐘檢查與 macOS 憑證儲存的復原步驟。

### 無法解析身分驗證方式

工作階段在沒有任何憑證的情況下抵達了 API 用戶端。當 worker 在沒有憑證的情況下啟動時，[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)與雲端工作階段會顯示此訊息。互動式、`-p` 與 Agent SDK 執行會將相同狀況回報為[未登入](#not-logged-in)，並且只會將此字串寫入其偵錯日誌，因此若您是在日誌中看到它，請改為依照該項目處理。

```text theme={null}
Could not resolve authentication method. Expected one of apiKey, authToken, credentials, config, or profile to be set. Or for one of the "X-Api-Key" or "Authorization" headers to be explicitly omitted
```

在目前的版本中，此錯誤表示 worker 程序沒有可用的憑證。在 v2.1.174 之前，即使已設定有效的憑證，指派給閒置預先初始化 worker 的背景工作階段仍可能以此方式失敗。在 v2.1.176 之前，在被認領前閒置的雲端工作階段也可能如此。請升級以復原。

**處理方式：**

* 如果此訊息出現在背景或雲端工作階段中，而您的憑證已經設定好，請升級至 v2.1.176 或更新版本
* 確認 `ANTHROPIC_API_KEY`、`CLAUDE_CODE_OAUTH_TOKEN` 或您的雲端供應商憑證已在啟動 worker 的環境中設定，而不只是在您的互動式 shell 中
* 若使用 Agent SDK，請參閱[快速入門中的身分驗證設定](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md#setup)
* 在相同環境的互動式工作階段中執行 `/status`，確認實際解析到的是哪個憑證來源

### 無效的 API 金鑰

`ANTHROPIC_API_KEY` 環境變數或 `apiKeyHelper` 指令碼傳回了被 API 拒絕的金鑰，或是 Claude Code 在傳送前就封鎖了來自 `ANTHROPIC_API_KEY` 的金鑰。

```text theme={null}
Invalid API key · Fix external API key
```

當訊息在 `Fix external API key` 之後還接著一段描述，例如 `Invalid X-Api-Key header value from ANTHROPIC_API_KEY: it contains a line break at character 41 (120 characters on 2 lines).`，表示 API 從未收到該金鑰。Claude Code 發現了 HTTP 標頭無法承載的字元，並在傳送前停止了請求。請參閱[無效的請求標頭值](#invalid-request-header-value)，了解如何解讀該描述並修正值。

**處理方式：**

* 檢查是否有拼字錯誤，並在 [Console](https://platform.claude.com/settings/keys) 中確認金鑰未被撤銷
* 在同一個 shell 中執行 `env | grep ANTHROPIC`，或在 PowerShell 中執行 `Get-ChildItem Env:ANTHROPIC*`。direnv、dotenv shell 外掛以及 IDE 終端機等工具，可能會在您未明確設定的情況下，從專案中的 `.env` 檔案載入過時的金鑰。
* 取消設定 `ANTHROPIC_API_KEY` 並執行 `/login`，改用訂閱進行身分驗證
* 如果金鑰來自 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼，請直接執行該指令碼，確認它會在 stdout 輸出有效的金鑰
* 執行 `/status`，確認 Claude Code 實際使用的是哪個憑證來源

### 您的 apiKeyHelper 指令碼執行失敗

Claude Code 執行了您 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 設定中的命令，但沒有取得金鑰。沒有金鑰時，請求會帶著預留位置憑證抵達 API，API 會以 `401` 拒絕它。終端機中的 `Authentication` 面板會顯示發生的是下列哪一種情況：

* 命令以錯誤結束或逾時
* 命令沒有在 stdout 輸出任何內容
* 命令輸出了金鑰以外的內容，例如登入橫幅或日誌行。面板會顯示 `returned output that cannot be used as an API key` 並說明問題所在，但不會重複該輸出。在 v2.1.227 之前，Claude Code 會在去除前後空白後，直接傳送命令輸出的任何內容。

```text theme={null}
Your apiKeyHelper script is failing · This usually means you need to re-authenticate with your provider · Run /status to see the script's error output
```

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，stderr 也會帶有具體原因，並以 `apiKeyHelper failed:` 為前綴。

在顯示此訊息之前，Claude Code 會重新執行指令碼並最多再重試請求兩次，因此失敗會在三次嘗試內浮現。在 v2.1.208 之前，Claude Code 會用完整個[重試額度](#automatic-retries)，以預留位置憑證重新傳送請求，然後回報一般的 `401` 身分驗證錯誤，而不是指令碼失敗。

在此情況下執行 `/login` 沒有幫助：只要該設定存在，helper 的輸出就會[優先於](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)已儲存的登入。

**處理方式：**

* 直接在您的 shell 中執行 `apiKeyHelper` 中設定的命令，以重現失敗情況
* 如果命令回報工作階段已過期，請向您的憑證提供者重新進行身分驗證，例如重新登入您的 SSO 或密鑰保管庫
* 修正命令，使其只將金鑰輸出至 stdout，格式為單一可列印 ASCII token、最多 16,384 個字元，並以退出碼 0 結束。請參閱[使用 apiKeyHelper 輪替憑證](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#rotate-credentials-with-apikeyhelper)以取得可用的設定範例。
* 執行 `/status` 以查看失敗情況，並確認 `apiKeyHelper` 是使用中的憑證來源。`apiKeyHelper` 列會顯示 `Failing` 以及最近一次失敗的詳細資訊，例如退出碼與命令的錯誤輸出，並會在下一次成功執行後消失。在 v2.1.274 之前，`/status` 只會顯示憑證來源，不會顯示失敗情況。
* 每次命令失敗時，其退出碼與錯誤輸出也會出現在終端機中的 `Authentication` 面板中。在 v2.1.212 之前，該面板的標題為 `Cloud authentication`。

### Claude Code didn't send your claude.ai login

請將這則完整訊息傳送給您的管理員，其中列出了他們可以進行的變更。此訊息表示 Claude Code 拒絕了您的提示詞。只要您使用 claude.ai 登入，Claude Code 就會持續拒絕提示詞，重新啟動後亦然：

```text theme={null}
Claude Code didn't send your claude.ai login, because the API key helper your administrator set isn't in effect. Your organization's managed settings may be overriding it. Ask your administrator to keep the key helper and its API address in effect, to name Anthropic's API address in those managed settings, or to remove the key helper. Run /status to see your setting sources.
```

**處理方式：**

* 若要告知管理員您的電腦有哪些受管來源，請在 Claude Code 提示字元中執行 `/status`，並複製 [`Setting sources` 這一行](https://code.claude.com/docs/zh-TW/managed-settings#read-the-source-in-/status)。如果出現 `Skipped sources` 這一行，也一併複製
* 如果您是設定的管理者，請參閱[為何電腦的金鑰 helper 未生效](https://code.claude.com/docs/zh-TW/server-managed-settings.md#machine-apikeyhelper-not-in-effect)

### 無效的請求標頭值

Claude Code 即將作為請求標頭傳送的值，包含 HTTP 標頭無法承載的字元：換行、NUL 位元組，或高於 `U+00FF` 的字元，例如彎引號或零寬度空格。Claude Code 會在傳送任何內容之前停止請求，並指出需要修正的變數或設定。常見原因是從文件或聊天中貼上的憑證帶有不可見字元或多餘的換行。

當 Claude Code 直接或透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)向 Claude API 傳送請求時，會執行此檢查。在第三方雲端供應商（例如 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)）上，Claude Code 不會在傳送前執行此檢查。

```text theme={null}
Invalid auth token · Fix external auth token
Invalid ANTHROPIC_CUSTOM_HEADERS · Fix the environment variable
Invalid request header from the environment · Fix the environment variable
```

訊息的第一部分取決於錯誤值的來源：

* `Invalid auth token`：來自 [`ANTHROPIC_AUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 的 bearer token
* `Invalid ANTHROPIC_CUSTOM_HEADERS`：您在 [`ANTHROPIC_CUSTOM_HEADERS`](https://code.claude.com/docs/zh-TW/env-vars) 中設定的標頭名稱或值。描述會指出是第幾個 `Name: Value` 組合有問題，例如 `distinct header 2 of 3 parsed from ANTHROPIC_CUSTOM_HEADERS`，但不會重複名稱或值，因為兩者都是您自行選擇的。
* `Invalid request header from the environment`：Claude Code 從另一個環境變數複製到請求標頭中的值，例如 `CLAUDE_AGENT_SDK_CLIENT_APP`。描述會指出需要修正的變數。

Claude Code 會將此檢查攔截到的錯誤 `ANTHROPIC_API_KEY` 回報為[無效的 API 金鑰](#invalid-api-key)，並附上相同的結尾描述。對於已儲存的錯誤 `/login` 憑證，則會回報為[未登入](#not-logged-in)；請執行 `/login` 儲存新的憑證。[`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼的輸出永遠不會經過此檢查：Claude Code 會在指令碼執行時驗證它，HTTP 標頭無法承載的輸出會以[您的 apiKeyHelper 指令碼執行失敗](#your-apikeyhelper-script-is-failing)失敗。

在第二個 `·` 之後，訊息會描述問題，如以下完整範例所示：

```text theme={null}
Invalid auth token · Fix external auth token · Invalid Authorization header value from ANTHROPIC_AUTH_TOKEN: it contains a line break at character 41 (120 characters on 2 lines).
```

位置從一開始計算字元。描述由固定片語與字元數組成，因此絕不會包含值本身。只有在問題字元是知名的不可見或排版字元時（例如位元組順序標記、零寬度空格或彎引號），描述才會指名該字元，其他字元一律回報為 `a non-ASCII character`。

**處理方式：**

* 重新設定訊息所指的變數或設定，重新輸入回報位置附近的字元，而不是再次從相同來源貼上
* 對於 `ANTHROPIC_CUSTOM_HEADERS`，每行保留一組 `Name: Value`，並重新撰寫訊息所指出的那一組
* 執行 `/status`，確認使用中的是哪個憑證來源

### 此組織已被停用

Claude Code 正在使用來自已停用 Console 組織的過時 `ANTHROPIC_API_KEY`。當您有已儲存的訂閱登入時，該金鑰會覆寫它。

```text theme={null}
Your ANTHROPIC_API_KEY belongs to a disabled organization · Unset the environment variable to use your subscription instead
Your ANTHROPIC_API_KEY belongs to a disabled organization · Update or unset the environment variable
API Error: 400 ... This organization has been disabled.
```

`·` 之後的提示取決於您已儲存的憑證：當您取消設定金鑰後有已儲存的 `/login` 可接手時，會出現第一種形式；當金鑰是您唯一的憑證時，會出現第二種形式。

如果您在 shell 設定檔中匯出金鑰，或從 `.env` 載入金鑰，即使您擁有可正常使用的 Pro、Max 或 Ultra 訂閱，Claude Code 仍會使用該金鑰，而非 `/login`。在非互動模式（`-p`）中，只要金鑰存在就一律會使用。

**處理方式：**

* 在目前的 shell 中取消設定 `ANTHROPIC_API_KEY`，並從您的 shell 設定檔中移除它，然後重新啟動 `claude`
* 如果訊息顯示 `Update or unset`，表示您沒有可退回使用的已儲存登入。請取消設定金鑰並執行 `/login`，或將金鑰替換為來自使用中 Console 組織的金鑰。
* 之後執行 `/status`，確認使用中的憑證是您的訂閱
* 如果沒有設定任何環境變數而錯誤仍然存在，請聯絡支援團隊或以其他帳戶登入。

### 您的組織已停用 API 金鑰身分驗證

此訊息需要 Claude Code v2.1.169 或更新版本。您 Console 組織的管理員已關閉 API 金鑰身分驗證，因此 API 會拒絕 Claude Code 傳送的金鑰。`·` 之後的復原提示會依金鑰來源而不同：

```text theme={null}
Your organization has disabled API key authentication · Run /login to sign in with your claude.ai account
Your organization has disabled API key authentication · Unset ANTHROPIC_API_KEY to use your claude.ai account instead
Your organization has disabled API key authentication · Unset ANTHROPIC_API_KEY and run /login to sign in with your claude.ai account
Your organization has disabled API key authentication · Unset the apiKeyHelper setting and run /login to sign in with your claude.ai account
Your organization has disabled API key authentication · Sign in again with your claude.ai account
```

最後一種形式出現在由 Claude Desktop 應用程式執行的工作階段中（例如 Code 分頁或 Cowork），您需要從應用程式重新登入。

環境變數與 `apiKeyHelper` 優先於 `/login`，因此只要其中任一項仍在提供金鑰，單獨執行 `/login` 並無幫助。請參閱[身分驗證優先順序](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)。

**處理方式：**

* 如果訊息指名 `ANTHROPIC_API_KEY`，請在目前的 shell 中取消設定它，並從您的 shell 設定檔或 `.env` 檔案中移除，然後重新啟動 `claude`
* 如果訊息指名 `apiKeyHelper`，請從您的 `settings.json` 中移除 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 設定
* 執行 `/login`，以您的 claude.ai 帳戶登入
* 之後執行 `/status`，確認使用中的憑證是您的訂閱而非 API 金鑰
* 如果您的自動化作業需要 API 金鑰身分驗證，請要求組織管理員在 Console 中重新啟用

### 您的組織已停用 Claude 訂閱存取

您的 Claude 組織不允許以訂閱登入方式登入 Claude Code。以相同帳戶再次執行 `/login` 會傳回相同的錯誤。

```text theme={null}
Your organization has disabled Claude subscription access for Claude Code · Use an Anthropic API key instead, or ask your admin to enable access
```

這是伺服器端的組織設定，因此無法透過本機設定、環境變數或 CLI 旗標覆寫。

Agent SDK 與 `-p` 非互動模式會將此回報為 `oauth_org_not_allowed` 錯誤代碼。

**處理方式：**

* 請您的管理員為您的組織啟用 Claude Code 存取
* 改用 Console API 金鑰而非訂閱進行身分驗證。設定方式請參閱 [Claude Console 身分驗證](https://code.claude.com/docs/zh-TW/authentication.md#claude-console-authentication)。
* 如果您是管理員卻看不到啟用存取的選項，請聯絡 [Anthropic 支援](https://support.claude.com)

### Scheduled tasks are off for your organization

您的組織已關閉[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)，因此您無法建立或執行它們。來自 claude.ai 的訊息會稱之為 scheduled tasks 或 routines，並在後面附上一句關於您管理員的說明：

```text theme={null}
Scheduled tasks are off for your organization. …
Routines are off for your organization. …
```

您無法透過本機設定、環境變數或 CLI 旗標開啟它們。

**處理方式：**

* 詢問您的 Team 或 Enterprise 擁有者，是否能在 [**Organization settings > Capabilities > Remote sessions**](https://claude.ai/admin-settings/capabilities) 開啟標示為 **Scheduled tasks (Was Routines)** 或 **Routines** 的切換開關

### Remote Control 需要 Anthropic API

此工作階段並未直接與 Anthropic API 通訊，而這是 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 所必需的。

```text theme={null}
Remote Control is only available when using Claude via api.anthropic.com. CLAUDE_CODE_USE_BEDROCK is set, so this session is using Amazon Bedrock — unset it (or run in a shell without it) to use Remote Control.
```

第二句說明了是什麼讓工作階段繞離了 Anthropic API；在 v2.1.219 之前，訊息只有第一句。視原因而定，訊息會指出：

* `CLAUDE_CODE_USE_*` 供應商變數，例如 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 的 `CLAUDE_CODE_USE_BEDROCK` 或 [Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 的 `CLAUDE_CODE_USE_VERTEX`
* [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 `api.anthropic.com` 以外的主機，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或代理伺服器，即使您以 claude.ai 登入亦然；在 v2.1.196 之前，自訂的 base URL 不會封鎖 Remote Control
* 已設定 `ANTHROPIC_UNIX_SOCKET`，因此工作階段會透過本機 socket 傳送請求，而不是傳送至 `api.anthropic.com`
* 透過 `/login` 進行的企業[雲端閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入，此方式不支援 Remote Control，且沒有可取消設定的變數

**處理方式：**

* 取消設定訊息所指的變數（例如 `CLAUDE_CODE_USE_BEDROCK` 或 `ANTHROPIC_BASE_URL`）並重新啟動工作階段，或從直接與 Anthropic API 通訊的工作階段啟動 Remote Control
* 如果該變數未在您的 shell 中設定，請檢查[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中的 `env` 鍵，它會將環境變數套用至每個工作階段
* 關於此訊息及其他 Remote Control 啟動訊息，請參閱 [Remote Control 疑難排解](https://code.claude.com/docs/zh-TW/remote-control.md#troubleshooting)

### Remote Control 無法重新整理您的登入

Claude Code 以短期憑證執行即時的 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線，這些憑證是使用您已儲存的 claude.ai 登入取得並更新的。當 claude.ai 不再接受該登入，或 Claude Code 已沒有已儲存的登入時，Claude Code 會停止 Remote Control，並需要您重新登入。這兩種失敗都可能發生在 Claude Code 仍在連線時，或之後更新憑證時。

當 Claude Code 要求登入服務重新整理您已儲存的登入卻沒有得到回應時，它會讓 Remote Control 繼續執行，並在連線目前的憑證仍有效期間再次嘗試重新整理。當 Claude Code 無法連上登入服務、請求逾時，或服務失敗但未拒絕您的登入時，重新整理就會得不到回應。如果在該憑證到期時登入服務仍未回應，Claude Code 會停止 Remote Control 並回報 `OAuth token refresh failed`。

當 Claude Code 停止 Remote Control 時，會在警告以及以 `Remote Control disconnected` 開頭的逐字稿行中顯示原因。您的本機工作階段會在沒有 Remote Control 的情況下繼續執行。本節涵蓋以下幾行：

```text theme={null}
Remote Control disconnected — Claude.ai login expired — run /login to restore Remote Control
Remote Control disconnected — Claude.ai login expired — run /login, then /remote-control
Remote Control disconnected — Claude.ai login was rejected — run /login, then /remote-control
Remote Control disconnected — OAuth token unavailable — run /login to restore Remote Control
Remote Control disconnected — OAuth token refresh failed — run /login to re-authenticate
Remote Control disconnected — JWT refresh failed: no OAuth token — run /login
Remote Control disconnected — Signed out of Claude — run /login, then /remote-control
```

Claude Code 會在訊息中間指出原因：

* `Claude.ai login expired` 與 `Claude.ai login was rejected`：claude.ai 不再接受您已儲存的登入 token，因為它已過期或被撤銷
* `OAuth token unavailable`：當連線的憑證到期需要更新時，Claude Code 沒有已儲存的登入 token
* `OAuth token refresh failed`：Claude Code 重新連線時，claude.ai 拒絕了您已儲存的登入 token，且重新整理 token 未產生新的 token
* `JWT refresh failed: no OAuth token`：Claude Code 找不到可用於更新的已儲存登入 token
* `Signed out of Claude`：您在這台機器上登出了，例如在另一個終端機中執行 `/logout`，因此 Claude Code 沒有剩餘的已儲存登入可用來更新連線

**處理方式：**

* 執行 `/login` 重新登入
* 執行 `/remote-control` 重新連線工作階段。以 `run /login to restore Remote Control` 結尾的訊息不需要此步驟：您登入後 Claude Code 會自動重新連線。

在 v2.1.224 之前，`OAuth token refresh failed — run /login to re-authenticate` 顯示為 `OAuth token refresh failed — re-authenticate, then re-enable Remote Control`，而 `JWT refresh failed: no OAuth token — run /login` 顯示為 `no OAuth token available for recovery (code <N>)`。`Claude.ai login expired`、`Claude.ai login was rejected` 與 `OAuth token unavailable` 訊息是在 v2.1.225 新增的。

在 v2.1.238 之前，Claude Code 會將現在顯示為 `Signed out of Claude` 的情況回報為 `JWT refresh failed: no OAuth token — run /login`，並且只要有一次登入重新整理沒有得到回應，就會以 `Claude.ai login expired — run /login to restore Remote Control` 停止 Remote Control。

### Remote Control could not renew this computer's connection

當伺服器無法在連線的憑證到期前使用您的 claude.ai 登入為其續期時，此警告會出現在執行 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) 的終端機中。警告的最後一句會說明目前的憑證還能使用多久，或說明它已經過期：

```text theme={null}
Remote Control could not renew this computer's connection: claude.ai did not accept the sign-in it uses. Run `claude /login` to sign in again. The connection keeps working for about 26 hours; if it still cannot sign in then, it stops.
```

**處理方式：**

* 如果警告要求您執行 `claude /login`，請在執行伺服器的機器上開啟另一個終端機，在其中執行 `claude /login`，並以您的 claude.ai 帳戶登入
* 如果在連線的憑證過期後伺服器仍無法登入，它會輸出包含 `Poll: Authentication failed (401)` 的錯誤並停止。請依警告第二句的說明重新登入，然後在伺服器停止的終端機中再次執行 `claude remote-control`。

### 由於登入的帳戶已變更，Remote Control 已停止

在 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段期間，當您在這台機器上登入不同的 claude.ai 帳戶或組織時，Claude Code 會顯示此行。您是在 Claude Code 工作階段之外進行切換的，例如在另一個終端機中執行 `/login`。

您透過 `/login` 登入時啟動的 Remote Control 工作階段，屬於當時已登入的 claude.ai 帳戶與組織。

```text theme={null}
Remote Control disconnected — signed-in claude.ai account or organization changed on this machine — run /remote-control to start a session for the current account, or /login to switch back, then /remote-control
```

一旦 claude.ai 確認帳戶或組織已變更，Claude Code 就會停止 Remote Control 工作階段。您的本機工作階段會在沒有 Remote Control 的情況下繼續執行。

**處理方式：**

* 執行 `/remote-control`，在目前的帳戶或組織下啟動新的 Remote Control 工作階段
* 若要切換回去，請執行 `/login` 並重新登入先前的帳戶或組織，然後執行 `/remote-control`。

在 v2.1.234 之前，當您在 Claude Code 工作階段之外切換到不同的帳戶或組織時，Claude Code 不會察覺。Claude Code 會讓 Remote Control 工作階段保持連線，直到之後對 Remote Control 伺服器的請求以 `Remote Control server rejected the request (HTTP 404)` 失敗為止。該失敗可能在切換後數小時才出現。

### 由於執行工作階段的應用程式已登出或切換帳戶，Remote Control 已停止

當 Claude 桌面應用程式或 IDE 託管您的工作階段時，Claude Code 會從該應用程式取得登入 token，而不是從 `/login`。當 claude.ai 拒絕該 token 時，Claude Code 會向應用程式要求新的 token。如果應用程式回應它已登出，或現在已登入不同的 Claude 帳戶，Claude Code 會結束 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段，並向應用程式傳送下列其中一行：

```text theme={null}
Remote Control stopped — the app running this session is now signed in to a different Claude account
Remote Control stopped — the app running this session is signed out of Claude. Sign in there, then turn Remote Control back on
```

您的本機工作階段會在沒有 Remote Control 的情況下繼續執行。

**處理方式：**

* 如果應用程式已登出，請重新登入，然後在應用程式中重新開啟 Remote Control
* 如果應用程式切換了帳戶，Claude Code 無法在新帳戶下繼續已結束的工作階段。請在該帳戶下啟動新的 Remote Control 工作階段。

在 v2.1.238 之前，這兩種情況下 Claude Code 都會向應用程式傳送列於 [Remote Control 無法重新整理您的登入](#remote-control-couldnt-refresh-your-login)中的 `run /login` 訊息。

### OAuth token 已撤銷或已過期

您已儲存的登入不再有效。token 被撤銷表示您已在所有地方登出，或管理員移除了存取權；token 過期則表示自動重新整理在工作階段中途失敗。

這兩種訊息都是回報 API 針對 Claude Code 所傳送請求的拒絕。當已儲存的登入在重新整理失敗後已被清除時，您會改為看到[登入已過期](#login-expired)。如果您以 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 中的長期 token 進行身分驗證，當該 token 過期或被撤銷時，您會看到相同的訊息。

```text theme={null}
OAuth token revoked · Please run /login
Please run /login · API Error: 401 OAuth token has expired ...
```

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)（`-p`）與 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，訊息如下，結構化錯誤代碼為 `authentication_failed`：

```text theme={null}
Failed to authenticate: OAuth token revoked. Please log in again or contact your administrator.
Failed to authenticate. API Error: 401 OAuth token has expired ...
```

在 v2.1.287 之前，在非互動模式與 Agent SDK 中，撤銷訊息顯示為 `Your account does not have access to Claude. Please login again or contact your administrator.`

**處理方式：**

* 在 Claude Code 提示字元執行 `/login` 重新登入
* 如果您的 `-p` 命令或 Agent SDK 程式使用已儲存的登入，請在相同環境中執行 `claude`，完成 `/login`，然後重新執行命令或程式。對於無法互動式登入的自動化作業，請以 [`ANTHROPIC_API_KEY`](https://code.claude.com/docs/zh-TW/env-vars) 進行身分驗證，或[使用 `claude setup-token` 產生長期 token](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token)。
* 如果您以 `CLAUDE_CODE_OAUTH_TOKEN` 環境變數進行身分驗證，在請求以 401 失敗後，Claude Code 會持續傳送您設定的值，而不會切換為已儲存登入的 token。[`/status`](https://code.claude.com/docs/zh-TW/commands) 會將此憑證顯示為一列內容為 `CLAUDE_CODE_OAUTH_TOKEN` 的 `Auth token`。請使用 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token) 產生新的 token 並以其重新啟動，或取消設定該變數並執行 `/login`。在 v2.1.225 之前，Claude Code 可能會在工作階段中途以已儲存登入的短期存取 token 取代該變數的值，而當該 token 過期後，工作階段會再次以 401 錯誤失敗。
* 若每次啟動都反覆要求登入，請參閱[疑難排解](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#not-logged-in-or-token-expired)中的系統時鐘檢查與 macOS 憑證儲存復原步驟
* 其他失敗（包括 `403 Forbidden` 與 OAuth 瀏覽器問題），請參閱[登入與身分驗證](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#login-and-authentication)

### API Error: 401 Invalid authentication credentials

API 辨識了您憑證的格式，但拒絕了其背後的帳戶或組織。當憑證最近被撤銷、組織已被停用或移除了您的存取權，或帳戶本身已被停用時，Anthropic 會傳回此訊息，因此原因並非 token 過期。該憑證可能是您已儲存的登入，也可能是已核准的 `ANTHROPIC_API_KEY`，而修正方式有所不同，因此請先執行 `/status` 查看使用中的是哪一個。

```text theme={null}
Please run /login · API Error: 401 Invalid authentication credentials
```

**處理方式：**

* 如果 `/status` 顯示一列未標記為未使用的 `API key`，則已核准的 [`ANTHROPIC_API_KEY`](https://code.claude.com/docs/zh-TW/authentication#authentication-precedence) 是使用中的憑證且優先於您的登入，因此 `/login` 不會取代它。請在 Claude Console 中輪替金鑰，或執行 `unset ANTHROPIC_API_KEY`（在 PowerShell 中為 `Remove-Item Env:ANTHROPIC_API_KEY`）退回使用您的訂閱。
* 如果 `/status` 只顯示您的登入，請執行一次 `/login`。如果憑證已被撤銷，新的登入會取代它。
* 如果相同的登入帳戶再次出現相同訊息，表示該帳戶或組織已不再有效。請檢查 `/status` 所回報的帳戶與組織，並請您的組織管理員恢復存取權。
* 如果 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，`401` 之後的文字是您閘道的訊息而非 Anthropic 的訊息，`/login` 無法改變它。請改為修正您閘道所預期的憑證。
* 如果閘道已取得其預期的憑證，但每個請求仍以 `401` 失敗，請檢查閘道及其上游是否接受 [tool search](https://code.claude.com/docs/zh-TW/mcp.md#tool-search-through-a-gateway) 欄位。預設情況下，Claude Code 會傳送 `defer_loading` 工具欄位與 `tool_reference` 區塊，並附上啟用它們的 `anthropic-beta` 標頭。在 v2.1.304 之前，位於閘道之後時 tool search 預設為關閉，除非您以 `ENABLE_TOOL_SEARCH` 開啟。

### 登入已過期

Claude Code 嘗試更新您已儲存的 claude.ai 登入，但 OAuth 服務拒絕了已儲存的重新整理 token，因此 Claude Code 清除了已儲存的憑證。之後，每個模型請求都會在抵達 API 之前於本機以此訊息停止，因為只有 `/login` 能建立新的憑證。

在 v2.1.206 之前，Claude Code 仍會使用環境中剩餘的任何憑證傳送模型請求，結果每個模型都以[所選模型有問題](#theres-an-issue-with-the-selected-model)或 401 失敗，而不是提示您登入。

```text theme={null}
Login expired · Please run /login
```

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)（`-p`）與 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，訊息如下，結構化錯誤代碼為 `authentication_failed`：

```text theme={null}
Failed to authenticate: OAuth session expired and could not be refreshed
```

若 `Login expired` 訊息以 `or re-authenticate your Anthropic profile` 結尾，請參閱 [Anthropic profile login expired](#anthropic-profile-login-expired)。

這與 [OAuth token 已撤銷或已過期](#oauth-token-revoked-or-expired)並非相同狀態。那些訊息回報的是 API 傳回的拒絕。`Login expired` 是 Claude Code 本身針對已無法更新的登入所產生的訊息，因此不會傳送任何請求。當更新失敗是因為帳戶本身遭到停權而非登入過時，Claude Code 會改為顯示[您的帳戶已遭暫停](#your-account-is-on-hold)。

以 API 金鑰、[`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 或第三方供應商進行身分驗證的工作階段不使用已儲存的登入，永遠不會看到此訊息。

您可以在請求失敗之前檢查此狀態：[`/status`](https://code.claude.com/docs/zh-TW/commands) 會顯示一列內容為 `Expired — log in again` 的 `Login`，以及它為過期登入所儲存的組織與電子郵件。只有當已儲存的登入是您使用中的憑證且已無法重新整理時，才會出現該列。以其他方式進行身分驗證的工作階段不會顯示該列，即使仍有已過期的登入被儲存。在 v2.1.210 之前，`/status` 在此狀態下不會顯示任何曾經存在登入的跡象，因為被清除的憑證讓它沒有可回報的內容。

**處理方式：**

* 執行 `/login` 重新登入。未登入就重試，每次請求都會顯示相同的訊息。
* 如果您在另一個 Claude Code 視窗中以 claude.ai 帳戶登入，請參閱[未登入](#not-logged-in)，了解此工作階段何時會自動開始使用該登入。
* 在非互動模式中，請在相同環境中執行 `claude`，完成 `/login`，然後重新執行您的命令。對於無法互動式登入的自動化作業，請以 `ANTHROPIC_API_KEY` 進行身分驗證，或[使用 `claude setup-token` 產生長期 token](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token)。
* 如果登入持續失敗，請參閱[登入與身分驗證](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#login-and-authentication)

### 由於另一個 Claude Code 程序正在重新整理，無法重新整理您的登入

此訊息並不表示您的登入被拒絕。您已儲存的 claude.ai 登入已過期且需要更新。同一台機器上的另一個 Claude Code 程序持有共用的重新整理鎖，或是已結束並遺留該鎖，而在此工作階段等待期間重新整理沒有任何進展。Claude Code 會在傳送前停止請求：

```text theme={null}
Could not refresh your login because another Claude Code process is refreshing it (or exited mid-refresh) · Try again in a minute; if it keeps happening, close other Claude Code windows or sign in again with /login
```

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)（`-p`）與 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，訊息如下，結構化錯誤代碼為 `server_error`：

```text theme={null}
Failed to refresh OAuth token: another Claude Code process is refreshing it or exited mid-refresh. This is usually transient; retry in a minute, and if it persists close other Claude Code processes or sign in again
```

以 API 金鑰、[`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 或第三方供應商進行身分驗證的工作階段不使用已儲存的登入，永遠不會看到此訊息。

**處理方式：**

* 一分鐘後再試一次。如果另一個程序先完成了重新整理，此工作階段就會使用更新後的登入。
* 如果訊息持續出現，請關閉其他 Claude Code 視窗與程序，然後重試。
* 如果在沒有其他 Claude Code 程序執行的情況下仍出現此訊息，請執行 `/login`。重新登入不需要等待重新整理鎖。

### 無法儲存您的登入

您已使用 claude.ai 登入，但 Claude Code 無法將登入儲存至其憑證儲存區，因此登入未完成。在 macOS 上，如果 Claude Code 在同一個工作階段中已經讀取或儲存過登入鑰匙圈中的憑證，之後鑰匙圈被鎖定（例如在睡眠或閒置時），就可能發生這種情況。

```text theme={null}
Couldn't save your login. If your Mac's keychain is locked, unlock it and log in again.
Couldn't save your login. Try logging in again.
```

第一種形式出現在 macOS 上，第二種則出現在其他所有平台上。暫時性的憑證儲存區失敗（例如逾時或儲存區無法讀取）也會產生相同的訊息。

**處理方式：**

* 在 macOS 上，解鎖登入鑰匙圈，然後再次執行 `/login`
* 在其他平台上，再次執行 `/login`
* 如果登入仍無法儲存，請參閱[未登入或 token 已過期](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#not-logged-in-or-token-expired)，了解鑰匙圈解鎖命令及其他憑證儲存復原步驟

### Couldn't start the local listener that receives the browser sign-in

來自 `/login`、`claude auth login` 或 `claude setup-token` 的這些訊息，都表示 Claude Code 無法開啟 `127.0.0.1` 上讓瀏覽器傳回登入結果的連接埠。

若出現以 `The browser can't return the sign-in to Claude Code automatically` 開頭的通知，登入會在不使用該連接埠的情況下繼續進行。不會開啟瀏覽器，而通知會顯示在一個 URL 上方，請改從該 URL 登入：

```text wrap theme={null}
The browser can't return the sign-in to Claude Code automatically. After you sign in, paste the code shown.
```

若出現包含 `Couldn't start the local listener` 的訊息，表示登入已停止。例如，當您將輸入以管線傳入 `claude auth login` 時就會發生這種情況：

```text theme={null}
Couldn't start the local listener that receives the browser sign-in. Try again.
```

**處理方式：**

* **`The browser can't return the sign-in to Claude Code automatically`**：您不需要先修正任何東西。在瀏覽器中開啟通知下方顯示的 URL 並登入。瀏覽器接著會顯示一組代碼：在 `Paste code here >` 提示字元處將其貼到 Claude Code 中，登入就會從那裡繼續。
* **`Couldn't start the local listener that receives the browser sign-in`**：再次執行相同的命令。如果仍以相同方式停止，請改用 token 或 API 金鑰登入，而非透過瀏覽器。或者，如果您是以管線將輸入傳入 `claude auth login`，請在終端機中執行它，使其可以接受貼上的代碼。
* **改用 token 或 API 金鑰登入，而非透過瀏覽器**：如果您使用 claude.ai 訂閱，請在可以正常登入的機器上執行 [`claude setup-token`](https://code.claude.com/docs/zh-TW/authentication#generate-a-long-lived-token)，然後在這台機器上將它輸出的 token 設定為 [`CLAUDE_CODE_OAUTH_TOKEN`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數。否則，請將 `ANTHROPIC_API_KEY` 環境變數設定為來自 [Claude Console](https://platform.claude.com/settings/keys) 的金鑰。[身分驗證優先順序](https://code.claude.com/docs/zh-TW/authentication.md#authentication-precedence)說明了 Claude Code 如何在多個憑證之間做選擇。
* **恢復自動的瀏覽器回傳**：Claude Code 必須能夠在 `127.0.0.1` 上監聽。如果它在沙箱中執行，請確認沙箱的政策允許監聽本機連接埠，然後重新登入。如果在該環境中監聽應可正常運作而通知仍然出現，請執行 `/feedback`，讓回報內容包含您的環境詳細資訊。

在 v2.1.305 之前，一旦無法開啟連接埠，登入就會立即停止，且不會顯示可供登入的 URL。訊息內容例如 `Failed to start OAuth callback server: Failed to start server. Is port 0 in use?`。在這些版本中，請更新 Claude Code 並重新登入，或改用 token 或 API 金鑰登入，而非透過瀏覽器。

### 不接受 Claude 登入

您嘗試啟動[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，但伺服器以 401 拒絕建立它：伺服器不接受這台機器所傳送的 Claude 登入，通常是因為登入已過期或被撤銷。

如果伺服器有提供原因，該行的第一部分會是伺服器本身的原因。否則該行顯示為：

```text theme={null}
Claude login not accepted · Run /login, then try again
```

**處理方式：**

* 執行 `/login`，完成登入後再次啟動工作階段

### Artifact 需要 claude.ai 登入

Claude Code 拒絕了 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 的發布或讀取，因為此工作階段沒有可用於 artifact 的 claude.ai 登入。

每種形式的訊息都以相同的文字開頭，後面接著依您工作階段的身分驗證方式而定的補救方法。在沒有競爭憑證的情況下，訊息顯示為：

```text theme={null}
Artifacts need a claude.ai login. Run /login and select "Claude account with subscription", then retry — the "Anthropic Console account" option does not provide claude.ai credentials.
```

**處理方式：**

* 執行 `/login` 並選擇 **Claude account with subscription**。**Anthropic Console account** 選項不提供 claude.ai 憑證。
* 當訊息指名某個具有優先權的憑證（例如 `ANTHROPIC_API_KEY`、`apiKeyHelper` 設定，或先前 `/login` 所儲存的 Console 金鑰）時，請依訊息所述的方式移除它，然後執行 `/login`
* 當訊息表示此遠端工作階段是透過啟動它的機器進行身分驗證時，請在該機器上登入 claude.ai，然後重新連線工作階段
* 當訊息表示憑證是由工作階段的主機環境注入時，您無法在該工作階段中變更它；請啟動一個已登入 claude.ai 的工作階段
* 請參閱[可用性](https://code.claude.com/docs/zh-TW/artifacts.md#availability)，了解 artifact 的其他需求，例如方案、模型供應商與組織政策

### 管理員政策要求使用 Cloud 閘道登入

管理員在這台機器上的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)將 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 設定為 `"gateway"`，或設定了 [`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl)。除非您透過 `CLAUDE_CODE_USE_BEDROCK` 等變數選擇雲端供應商，否則 Claude Code 只會接受 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入。您會看到下列兩種訊息之一：

```text theme={null}
Not signed in to the Cloud gateway — run /login.
```

當工作階段沒有閘道登入時，模型請求會以此訊息失敗，例如因為在政策套用到這台機器之後您尚未執行 `/login`。

如果這台機器還持有 Anthropic 核發的憑證，且受管設定設定了 `forceLoginMethod` 或 `forceLoginOrgUUID`，Claude Code 會改為在啟動時結束。該憑證可能是 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN` 變數、`apiKeyHelper` 設定，或先前 Claude Console 登入所儲存的 API 金鑰。

啟動訊息會指出工作階段所設定的憑證、其設定位置，以及移除它的步驟。例如，若您在 shell 中設定了 `ANTHROPIC_API_KEY` 變數，訊息會顯示為：

```text theme={null}
Administrator policy requires a Cloud gateway sign-in on this machine, but this session is configured with an API key from ANTHROPIC_API_KEY, which a gateway machine does not accept.

To continue: unset ANTHROPIC_API_KEY (or run in a shell without it), then run claude and sign in with /login.
```

**處理方式：**

* 對於 `Not signed in to the Cloud gateway`，請執行 `/login` 並在 **Cloud gateway** 畫面上完成登入
* 對於啟動訊息，請依照訊息結尾的步驟移除該憑證
* 如果您認為這台機器不應要求使用閘道，請要求管理該機器的管理員從其受管設定中移除 `forceLoginMethod` 與 `forceLoginGatewayUrl`

在 v2.1.284 之前，啟動訊息會列出可能的憑證，而不是指出所設定的那一個。訊息開頭為 `Administrator policy requires a Cloud gateway sign-in on this machine; the Anthropic-issued credential configured here (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or apiKeyHelper) is not used.`。如果您看到這段文字且無法判斷要移除哪個憑證，請更新至 v2.1.284 或更新版本，然後再次啟動 `claude`。

在 v2.1.265 上，一個迴歸問題也會在某些以 API 金鑰、`apiKeyHelper` 或自訂標頭進行身分驗證的 LLM 閘道與代理伺服器設定中顯示第一則訊息，即使這台機器上沒有任何管理員要求亦然。請更新至 v2.1.266 或更新版本。您不需要變更設定。

在 v2.1.261 之前，在將 `forceLoginMethod` 設定為 `"gateway"` 的機器上，Claude Code 會使用遺留的已儲存登入，而不是讓模型請求失敗，並以 `This machine's managed settings require a first-party login` 回報已設定的環境憑證，而不是顯示啟動訊息。

### 您的帳戶已遭暫停

您登入所使用的 Claude 帳戶已被停權。當 Claude Code 嘗試更新您已儲存的登入並得知暫停狀態時，會顯示第一則訊息；當您在瀏覽器中完成的登入回報此狀態時，會顯示第二則訊息：

```text theme={null}
Your account is on hold and can't use Claude Code. View details or appeal: https://claude.ai/restricted
Your account is on hold and can't sign in to Claude Code. View details or appeal: https://claude.ai/restricted
```

以相同帳戶重新登入不會清除此訊息，因為暫停是針對帳戶而非登入。在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)（`-p`）與 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，結構化錯誤代碼為 `account_on_hold`。在 v2.1.235 之前，Claude Code 會將遭暫停的帳戶回報為 [Login expired · Please run /login](#login-expired)，而其復原步驟無法解除暫停。

**處理方式：**

* 開啟訊息中的連結，查看暫停的詳細資訊或提出申訴
* 如果您有另一個不受暫停影響的 Claude 帳戶或 API 金鑰，可以在暫停解決期間繼續工作：以該帳戶執行 `/login`，或以 `ANTHROPIC_API_KEY` 設定金鑰

### Anthropic 設定檔登入已過期

Claude Code 正透過 Anthropic 憑證設定檔進行身分驗證，但該設定檔已儲存的登入憑證已過期，且設定檔中沒有 Claude Code 可用來更新它的重新整理憑證。Claude Code 會在本機停止每個請求，且不會重試。

```text theme={null}
Anthropic profile login expired · Re-authenticate your Anthropic profile
Login expired · Run /login to sign in again, or re-authenticate your Anthropic profile
```

**處理方式：**

* 如果訊息以 `Login expired` 開頭，請執行 `/login` 重新登入
* 若要更新由無金鑰 Console 登入或 Claude Platform CLI 的 `ant auth login` 所寫入的設定檔，請在[提供無金鑰登入](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)的機器上執行 `/login`。選擇 Anthropic Console 帳戶，然後選擇 **Sign in with your Console account**。Claude Code 會取代該設定檔中已過期的憑證
* 若要更新由其他工具建立的設定檔，請使用該工具重新登入。如果您改在 `/login` 選擇 **Sign in with your Console account**，Claude Code 會保持該設定檔不變，並建立一個 API 金鑰
* 如果設定檔的憑證是由管理員佈建的，請要求他們核發新的憑證
* 執行 `/status`，確認使用中的憑證來源與設定檔名稱
* 若要停止使用該設定檔，請在您有設定的情況下取消設定 `ANTHROPIC_PROFILE`，然後以其他方式進行身分驗證，例如 `/login` 或 `ANTHROPIC_API_KEY`

訊息的開頭會告訴您 Claude Code 是如何找到該設定檔的：

* 當 Claude Code 從您的設定目錄中探索到該設定檔，且其驗證模式為 `user_oauth` 時，訊息會以 `Login expired` 開頭，並優先建議 `/login`。Claude Code 會讓可正常運作的 `/login` 優先於探索到的設定檔，然後改以您的 claude.ai 帳戶進行身分驗證。從 v2.1.234 到 v2.1.277 之前，此形式顯示為 `Anthropic profile login expired · Run /login to use your claude.ai account instead, or re-authenticate the profile`。在 v2.1.234 之前，Claude Code 在此情況下也會顯示 `Re-authenticate your Anthropic profile` 形式。
* 當您使用 `ANTHROPIC_PROFILE` 選擇該設定檔時，訊息會以 `Anthropic profile login expired` 開頭。

只有當使用中的憑證來自 Anthropic 憑證設定檔時才會出現此訊息，該設定檔可能是您以 `ANTHROPIC_PROFILE` 環境變數選擇的、Claude Code 在您的 Anthropic 設定目錄中探索到的使用中設定檔，或是您[在不使用 API 金鑰的情況下登入](https://code.claude.com/docs/zh-TW/authentication.md#sign-in-without-an-api-key)時 Claude Code 寫入的設定檔。以 API 金鑰、`ANTHROPIC_AUTH_TOKEN` 等 bearer token 或第三方供應商進行身分驗證的工作階段，永遠不會看到此訊息。

### OAuth 範圍需求

已儲存的 token 早於某個較新功能所需的權限範圍：

```text theme={null}
OAuth token does not meet scope requirement: user:profile
```

**處理方式：**

* 執行 `/login` 以取得具有目前範圍的新 token。您不需要先登出。

### claude.ai 拒絕了工作階段 token

[claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)請求失敗，因為 claude.ai 拒絕了來自您 Claude Code 登入的 token。被拒絕的 token 是您的登入，而不是連接器本身在 claude.ai 中的授權，因此重新授權連接器無法解決此問題。在 `/mcp` 中，該連接器會顯示為 `session token rejected`，其詳細資訊檢視顯示：

```text theme={null}
claude.ai rejected the session token. Run /login, then reconnect.
```

**處理方式：**

* 執行 `/login` 重新登入
* 從 `/mcp` 重新連線連接器，或執行 `/mcp reconnect <server>`。在重新登入之前重新連線，連接器會維持相同狀態。`/mcp` 面板的 **Reconnect** 選項會回報 `your claude.ai session token was rejected`；而輸入的 `/mcp reconnect <server>` 形式即使 token 仍被拒絕，也會回報重新連線成功。

在 v2.1.222 之前，Claude Code 會改將連接器標記為需要身分驗證，引導您前往連接器的授權流程，即使完成該流程也無法解決此狀態。

### MCP 伺服器需要您重新登入

遠端 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)在工作階段中途的工具呼叫時拒絕了憑證，通常是因為登入或 token 已過期，或是 token 缺少工具所需的權限。工具呼叫會失敗，且 `/mcp` 會將該伺服器標記為[需要身分驗證](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)。

對於您從 Claude Code 登入的伺服器（包括 claude.ai 連接器），表示登入已過期或被撤銷：

```text theme={null}
MCP server "<name>" needs you to sign in again (run /mcp to re-authenticate)
```

執行 `/mcp`，選擇該伺服器，並從其選單重新登入。

對於以 [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication) 指令碼設定的伺服器，Claude Code 在顯示此訊息之前已經重新執行過 helper 並重試過一次呼叫：

```text theme={null}
MCP server "<name>" rejected the credential from its headersHelper (check the helper and run /mcp to reconnect, or to authenticate if the server also uses OAuth)
```

請確認 helper 傳回的憑證是伺服器所接受的，然後從 `/mcp` 重新連線，這會再次執行 helper。

對於設定中帶有靜態 `Authorization` 標頭的伺服器：

```text theme={null}
MCP server "<name>" rejected the Authorization header in its config (update it, then run /mcp to reconnect)
```

在設定該伺服器的位置更新標頭值，然後從 `/mcp` 重新連線。

在您電腦上 Claude Desktop 應用程式中的 [Cowork](https://claude.com/docs/cowork/overview) 工作階段裡，這些訊息表示 MCP 伺服器拒絕了提供給它的憑證。請修正訊息所指出的那一項，然後在 Cowork 中開始新的任務或聊天：

```text theme={null}
MCP server "<name>" rejected the credential from its headersHelper (check the helper, then start a new task or chat)
MCP server "<name>" rejected the Authorization header in its config (update it, then start a new task or chat)
```

* **`headersHelper` 憑證遭拒絕**：確認 helper 傳回的是伺服器可接受的憑證，然後在 Cowork 中開始新的任務或聊天
* **`Authorization` 標頭遭拒絕**：更新該伺服器設定中 `headers` 底下的 `Authorization` 值，然後在 Cowork 中開始新的任務或聊天

在 v2.1.302 之前，Cowork 工作階段會改為顯示 `run /mcp to reconnect` 結尾，儘管那裡無法使用 `/mcp`。如果您在 Cowork 中看到此類結尾，仍請檢查 helper 或更新標頭，然後開始新的任務或聊天。在 v2.1.273 之前，登入過期、`headersHelper` 和 `Authorization` 標頭的情況都會顯示 `MCP server "<name>" requires re-authorization (token expired)`。

伺服器也可能以 HTTP 403 `insufficient_scope` 拒絕工具呼叫，要求您授權某個範圍，有時是您的 token 已列出的範圍。訊息會指出該範圍：

```text theme={null}
MCP server "<name>" needs additional permissions (scope: "<scope>") — run /mcp to re-authenticate
```

執行 `/mcp`，選擇該伺服器，並從其選單重新進行身分驗證。

當伺服器的設定既未設定 [`oauth.scopes`](https://code.claude.com/docs/zh-TW/mcp#restrict-oauth-scopes) 也未設定 [`authServerMetadataUrl`](https://code.claude.com/docs/zh-TW/mcp#override-oauth-metadata-discovery) 時，Claude Code 會請求伺服器所指出的範圍。若有設定其中任一項，Claude Code 會改為請求該設定的範圍。如果您固定了 `oauth.scopes`，請在重新進行身分驗證之前，將缺少的範圍加入該清單。

在 v2.1.274 之前，此情況會顯示 `needs you to sign in again` 訊息，而在 v2.1.273 之前，它會像其他情況一樣顯示 `requires re-authorization (token expired)`。

### Couldn't read the stored credentials for MCP server

Claude Code 會將您對 OAuth [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)的登入保存在憑證存放區中。此訊息表示 Claude Code 無法讀取該存放區，因此對伺服器的請求沒有執行：

```text theme={null}
Couldn't read the stored credentials for MCP server "<name>", so the request didn't run. If your Mac's keychain is locked, unlock it, then try again.
Couldn't read the stored credentials for MCP server "<name>", so the request didn't run. Try again.
```

您已儲存的登入並未變更：待存放區可讀取後再試一次，且只有在伺服器要求時才需要重新登入。

在 macOS 上的 [`claude -p`](https://code.claude.com/docs/zh-TW/headless) 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 執行中，鑰匙圈可能在請求已經在沒有已儲存登入的情況下送出之後才變得可讀取。該請求會以下列訊息失敗：

```text theme={null}
A request to MCP server "<name>" was sent without your stored credentials, so the server rejected it. The credentials are available now. Try again.
```

**處理方式：**

* 如果訊息要求您解鎖 Mac 的鑰匙圈，請在您執行 Claude Code 的 shell 工作階段中執行 [`claude doctor`](https://code.claude.com/docs/zh-TW/cli-reference#cli-commands)，並檢查其報告中是否有鑰匙圈警告：
  * 如果報告列出以 `macOS Keychain is not writable` 開頭的警告，或您的 shell 中沒有 `claude` 命令，請在該 shell 工作階段中執行此解鎖命令：

    ```bash theme={null}
    security unlock-keychain ~/Library/Keychains/login.keychain-db
    ```

  * 如果報告沒有列出鑰匙圈警告，請略過解鎖命令

* 在您看到訊息之處再試一次：
  * 對於 `claude -p`，再次執行該命令
  * 在互動式工作階段中，如果伺服器在 `/mcp` 中顯示為失敗，請從那裡重新連線該伺服器，然後請 Claude 再試一次
  * 在持續執行的 Agent SDK 應用程式中，請在 TypeScript 中呼叫 [`reconnectMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#methods)，或在 Python 中呼叫 [`ClaudeSDKClient.reconnect_mcp_server()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)，或啟動新的工作階段

* 如果伺服器接著回報需要身分驗證，表示 Claude Code 找不到可用於該伺服器的登入。請以互動方式登入：在 Claude Code 工作階段中執行 `/mcp`，或在 shell 中執行 [`claude mcp login <name>`](https://code.claude.com/docs/zh-TW/mcp#authenticate-from-the-command-line)。在 Agent SDK 應用程式中，請參閱 [Agent SDK 中的 OAuth2 身分驗證](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#oauth2-authentication)。

在 v2.1.307 之前，在登入鑰匙圈已鎖定的 Mac 上執行的 `claude -p` 或 Agent SDK，會將伺服器回報為需要身分驗證，而不是顯示上述任一訊息。

### MCP 伺服器 URL 遺失或不是有效的 URL

Claude Code 拒絕為遠端 MCP 伺服器啟動 OAuth 登入，因為該伺服器所設定的 `url` 無法解析為 URL。除非 Claude Code 有更具體的伺服器設定問題要回報，否則在您的 shell 中執行 [`claude mcp login <name>`](https://code.claude.com/docs/zh-TW/mcp#authenticate-from-the-command-line) 會將此拒絕顯示為：

```text theme={null}
Couldn't complete authentication for "<name>": This server's URL is missing or not a valid URL, so sign-in can't start. Fix the URL in its MCP config (or set the environment variable it uses) and try again.
```

**處理方式：**

* 在設定該伺服器的位置將該項目的 `url` 設定為伺服器的實際端點，或設定其 [`${VAR}` 參照](https://code.claude.com/docs/zh-TW/mcp#environment-variable-expansion-in-mcp-json)所指名的環境變數，然後再次執行登入。

### 授權回應中的 issuer 不符

在 [MCP OAuth 登入](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers)期間，授權伺服器重新導向回 Claude Code 時所帶的 `iss` 參數，並非 Claude Code 根據伺服器 OAuth 中繼資料所預期的 issuer。此步驟出現錯誤的 issuer 正是授權伺服器混淆攻擊的樣貌，因此 Claude Code 會讓登入失敗，而不是交換授權碼。Claude Code 會在瀏覽器登入後於 `/mcp` 伺服器選單中顯示此錯誤：

```text theme={null}
Issuer mismatch in authorization response (RFC 9207): expected "https://auth.example.com", received "https://other.example.com"
```

`expected` 是伺服器 OAuth 中繼資料中的 issuer，`received` 是重新導向所帶的 `iss` 值。重新導向未帶 `iss` 參數的登入會通過檢查，除非伺服器的中繼資料設定了 `authorization_response_iss_parameter_supported`，此時 Claude Code 會讓登入失敗。

**處理方式：**

* 從 `/mcp` 再次嘗試登入
* 如果錯誤重複出現，請回報給伺服器營運者。修正需在伺服器端進行：授權伺服器必須在 `iss` 參數中傳回與其中繼資料所公告相同的 issuer
* 若要在伺服器修正期間連線，請以 [`MCP_SDK_GENERATION=v1`](https://code.claude.com/docs/zh-TW/env-vars) 啟動 Claude Code，其[執行階段](https://code.claude.com/docs/zh-TW/mcp.md#mcp-client-runtimes)不會執行此檢查。這會移除對混淆攻擊的防護，因此建議優先採用伺服器端修正

在 v2.1.232 之前，Claude Code 只在逐步推出時或您設定 `MCP_SDK_GENERATION=v2` 時才使用 v2 執行階段。

### 拒絕將憑證傳送至非 https 的 token 端點

在 [v2 執行階段](https://code.claude.com/docs/zh-TW/mcp.md#mcp-client-runtimes)上，Claude Code 只會將 [MCP OAuth](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers) token 請求傳送至透過 HTTPS 提供，或位於 `localhost`、`127.0.0.1` 或 `::1` 的 token 端點。此訊息表示伺服器的 token 端點兩者皆非，因此 Claude Code 在傳送請求之前停止了。這發生在瀏覽器登入之後，因此瀏覽器步驟會先成功，之後每當 Claude Code 重新整理該伺服器的 token 時也會再次發生。

完整形式的訊息來自 MCP SDK，並會引用它所拒絕的 token 端點。在偵錯日誌中，它會接在登入的 `Error during auth completion:` 或重新整理的 `Token refresh failed:` 之後。在您的 shell 中，`claude mcp login <name>` 會在 `Couldn't complete authentication for "<name>":` 之後輸出它；在工作階段中，`/mcp` 會在伺服器的選單下顯示它：

```text theme={null}
Refusing to send credentials to non-https token endpoint 'http://192.168.1.50:8123/oauth/token'. OAuth token requests MUST use TLS (localhost / 127.0.0.1 / ::1 are exempt).
```

Claude Code 會將帶有查詢字串或冗長隨機路徑區段的伺服器 URL 視為可能是機密。對於此類伺服器，它會在顯示或記錄 MCP SDK 引發的登入錯誤之前將其遮蔽。此時這個錯誤會顯示為一個可能隨版本變動的簡短名稱（例如 `io`），後面接著 `from the MCP SDK for` 以及遮蔽後的伺服器 URL。其他來自 MCP SDK 的錯誤在該處也採用相同形式。只有當伺服器的 token 端點是位於 `localhost`、`127.0.0.1` 或 `::1` 以外位址的純 `http://` 時，遮蔽後的訊息才可能是此錯誤。

**處理方式：**

* 透過 HTTPS 提供該 token 端點，例如將伺服器放在終止 TLS 的反向代理伺服器或通道後方，並設定伺服器公告 `https://` 位址
* 若要在不變更伺服器的情況下連線，請以 [`MCP_SDK_GENERATION=v1`](https://code.claude.com/docs/zh-TW/env-vars) 啟動 Claude Code，其[執行階段](https://code.claude.com/docs/zh-TW/mcp.md#mcp-client-runtimes)不套用此規則，並會透過純 HTTP 傳送 token 請求。此選擇會持續到您結束為止，並套用至每個伺服器。v1 執行階段也會略過 [issuer 檢查](#issuer-mismatch-in-authorization-response)，因此建議優先透過 HTTPS 提供端點

### AWS 憑證已過期或無效

您的 AWS 工作階段 token 已過期或被拒絕。當 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 或 [Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)傳回 401 時會出現此訊息，這是這些供應商回報安全 token 過期的方式。

中間的動作提示會依您的設定而不同。固定不變的部分是開頭的 `AWS credentials expired or invalid`：

```text theme={null}
AWS credentials expired or invalid · run /login and select "Claude Platform on AWS · refresh credentials", or run `aws sso login --profile myprofile` in another terminal · API Error: 401 ...
```

在 v2.1.273 之前，只有在設定了 `awsAuthRefresh` 時才會出現此訊息。

**處理方式：**

* 如果提示表示憑證由此環境管理，則啟動 Claude Code 的應用程式擁有該憑證，此處的其他步驟並不適用：請重試，或聯絡您的管理員
* 如果設定了 [`awsAuthRefresh`](https://code.claude.com/docs/zh-TW/amazon-bedrock#advanced-credential-configuration)，請在另一個終端機中執行訊息所指的命令（例如 `aws sso login --profile myprofile`）並完成瀏覽器登入，然後重試。否則，請自行重新整理您所使用的 AWS 憑證：您的 SSO 登入、存取金鑰、API 金鑰或代理伺服器 token
* 在設定了 `awsAuthRefresh` 的互動式工作階段中，您也可以改為執行 `/login`，選擇 **3rd-party platform**，然後在 **Using 3rd-party platforms** 下選擇 **Claude Platform on AWS · refresh credentials**，即可在不重新啟動 Claude Code 的情況下執行相同的命令。請參閱[設定 AWS 憑證](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md#1-configure-aws-credentials)
* 如果重新整理命令成功後錯誤仍重複出現，請在相同的 shell 與設定檔中執行 `aws sts get-caller-identity`，確認該身分在 Claude Code 之外是有效的

### AWS 身分驗證失敗

您的 AWS 供應商傳回了 403，或 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 傳回了 401。

Amazon Bedrock 會將安全 token 過期回報為 403，但 403 也是它回報授權遭拒的方式，例如因缺少 IAM 權限而產生的 `AccessDeniedException`。Claude Code 無法區分這兩種原因。

來自 Amazon Bedrock 的 401 也會歸到此處，而不是 [AWS 憑證已過期或無效](#aws-credentials-expired-or-invalid)，因為 Amazon Bedrock 不會將 token 過期回報為 401。來自該端點的 401 通常源自請求路徑中的其他元件，例如公司的代理伺服器。

重新整理憑證可以修正過期的 token，但無法修正其他原因，因此訊息會同時提供兩者：

```text theme={null}
AWS authentication failed · run /login and select "Claude Platform on AWS · refresh credentials", or run `aws sso login --profile myprofile` in another terminal · if credentials are current, check AWS permissions and model access · API Error: 403 ...
```

中間的動作提示會依您的設定而不同。固定不變的部分是開頭的 `AWS authentication failed`。

當 403 是 Amazon Bedrock 表示您無權存取指定模型 ID 之模型的回應時，提示會改為要求您在 Amazon Bedrock 主控台中為您的帳戶與區域啟用該模型。

在 v2.1.273 之前，只有在設定了 `awsAuthRefresh` 時才會出現此訊息。

**處理方式：**

* 如果提示表示憑證由此環境管理，則啟動 Claude Code 的應用程式擁有該憑證，此處的其他步驟並不適用：請重試，或聯絡您的管理員
* 重新整理您的 AWS 憑證，以防原因是憑證過期：若有設定，請執行訊息所指的 [`awsAuthRefresh`](https://code.claude.com/docs/zh-TW/amazon-bedrock#advanced-credential-configuration) 命令，或自行重新整理您的 SSO 登入、存取金鑰、API 金鑰或代理伺服器 token
* 如果您的憑證是最新的，請確認 [IAM 設定](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#iam-configuration)中的 IAM 權限已附加至您所使用的身分，且所選模型已為您的帳戶與區域啟用
* 執行 `aws sts get-caller-identity`，確認您的請求使用的是哪個身分

### Google Cloud 憑證已過期或無效

您用於 [Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 的 Google Cloud 憑證已過期或被拒絕：請求傳回了 401，這是 Agent Platform 回報憑證過期的方式。

中間的動作提示會依您的設定而不同。固定不變的部分是開頭的 `Google Cloud credentials expired or invalid`：

```text theme={null}
Google Cloud credentials expired or invalid · refresh your Google Cloud credentials (application default sign-in, or the key file in GOOGLE_APPLICATION_CREDENTIALS) and retry · API Error: 401 ...
```

**處理方式：**

* 如果提示表示憑證由此環境管理，則啟動 Claude Code 的應用程式擁有該憑證，此處的其他步驟並不適用：請重試，或聯絡您的管理員
* 如果您以應用程式預設憑證進行身分驗證，請執行訊息所指的 [`gcpAuthRefresh`](https://code.claude.com/docs/zh-TW/google-vertex-ai#advanced-credential-configuration) 命令，或 `gcloud auth application-default login`，完成登入後重試
* 如果您在設定了 `CLAUDE_CODE_SKIP_VERTEX_AUTH` 的情況下透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)進行路由，請重新整理 `ANTHROPIC_AUTH_TOKEN` 或 `ANTHROPIC_CUSTOM_HEADERS` 中的閘道 token，然後重試
* 如果您以服務帳戶金鑰檔案進行身分驗證，請確認 `GOOGLE_APPLICATION_CREDENTIALS` 指向有效的金鑰。請參閱[設定 GCP 憑證](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#3-configure-gcp-credentials)
* 如果重新整理後錯誤仍重複出現，請在相同的 shell 中執行 `gcloud auth application-default print-access-token`，確認該身分在 Claude Code 之外可正常運作

在 v2.1.273 之前，來自 Agent Platform 的 401 會改為顯示一般的 `Please run /login` 或 `Failed to authenticate` 訊息，而這些訊息無法重新整理 Google Cloud 憑證。

### Google Cloud 身分驗證失敗

[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 傳回了 403，它使用此狀態碼表示授權遭拒，而非憑證過期。通常是您用來進行身分驗證的身分缺少 IAM 權限，或模型尚未在您的專案中啟用。

中間的操作提示會依您的設定而有所不同。固定不變的部分是開頭的 `Google Cloud authentication failed`：

```text theme={null}
Google Cloud authentication failed · refresh your Google Cloud credentials (application default sign-in, or the key file in GOOGLE_APPLICATION_CREDENTIALS) and retry · if credentials are current, check GCP IAM permissions and Vertex AI model access · API Error: 403 ...
```

**處理方式：**

* 如果提示指出憑證由此環境管理，表示啟動 Claude Code 的應用程式擁有該憑證，此處的其他步驟不適用：請重試，或聯絡您的管理員
* 確認 [IAM 設定](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#iam-configuration)中的角色已授予您用來進行身分驗證的身分
* 確認模型已在您的專案中啟用。請參閱[請求模型存取權](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#2-request-model-access)

在 v2.1.273 之前，來自 Agent Platform 的 403 會改為顯示通用的 `Please run /login` 或 `Failed to authenticate` 訊息，而這無法重新整理 Google Cloud 憑證。

### Microsoft Foundry 身分驗證失敗

[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 傳回了 401 或 403：請求上的 Azure 憑證遭到拒絕，或其背後的身分沒有 Foundry 資源的存取權。`/login` 無法產生 Azure 憑證。中間的操作提示會依您的設定而有所不同。固定不變的部分是開頭的 `Microsoft Foundry authentication failed`：

```text theme={null}
Microsoft Foundry authentication failed · refresh your Foundry credential (ANTHROPIC_FOUNDRY_AUTH_TOKEN, ANTHROPIC_FOUNDRY_API_KEY, Azure sign-in for Entra, or your proxy token) and retry · if credentials are current, check access to the Foundry resource · API Error: 401 ...
```

**處理方式：**

* 如果提示指出憑證由此環境管理，表示啟動 Claude Code 的應用程式擁有該憑證，此處的其他步驟不適用：請重試，或聯絡您的管理員
* 重新整理您在[設定 Azure 憑證](https://code.claude.com/docs/zh-TW/microsoft-foundry.md#2-configure-azure-credentials)中設定的憑證：輪替 `ANTHROPIC_FOUNDRY_API_KEY`、產生新的 `ANTHROPIC_FOUNDRY_AUTH_TOKEN`，或執行 `az login`，讓預設的 Microsoft Entra 憑證鏈能再次登入
* 如果憑證仍有效，請確認該身分具有 Foundry 資源的存取權。請參閱 [Azure RBAC 設定](https://code.claude.com/docs/zh-TW/microsoft-foundry.md#azure-rbac-configuration)

在 v2.1.273 之前，來自 Microsoft Foundry 的 401 或 403 會改為顯示通用的 `Please run /login` 或 `Failed to authenticate` 訊息，而這無法重新整理 Azure 憑證。

### 無法載入 AWS 或 Google Cloud 憑證

Claude Code 無法在其執行的機器上，從 AWS 憑證提供者鏈或您的 Google 應用程式預設憑證取得可用的憑證，因此沒有任何請求送達您的雲端供應商。`·` 之後的詳細資訊會指出具體原因，例如 SSO 工作階段已過期、缺少應用程式預設憑證（回報為 `Could not load the default credentials`），或登入已被撤銷（回報為 `invalid_grant`）：

```text theme={null}
API Error: Could not load AWS credentials · Could not load credentials from any providers. Check or refresh your AWS credentials and try again.
API Error: Could not load Google Cloud credentials · invalid_grant. Check or refresh your Google Cloud credentials and try again.
```

在使用 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)以及 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，結構化錯誤代碼為 `cloud_credential_error`。在 v2.1.267 之前，訊息只會顯示 `API Error:` 之後的詳細文字，且結構化代碼為 `server_error` 或 `unknown`。

**處理方式：**

* 執行您供應商的登入命令，例如 `aws sso login --profile myprofile` 或 `gcloud auth application-default login`，然後重試。[Bedrock、Agent Platform 或 Foundry 憑證無法載入](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#bedrock-agent-platform-or-foundry-credentials-not-loading)說明如何在 Claude Code 之外確認憑證
* 如果詳細資訊顯示 `AWS default-chain credential resolve timed out`，表示憑證鏈是停滯而非失敗，請改為依照 [AWS 預設憑證鏈解析逾時](#aws-default-chain-credential-resolve-timed-out)處理

### AWS 預設憑證鏈解析逾時

AWS 預設憑證提供者鏈未在 60 秒內產生憑證，因此 Claude Code 停止解析並使請求失敗。此逾時是[無法載入 AWS 或 Google Cloud 憑證](#could-not-load-aws-or-google-cloud-credentials)的原因之一。失敗發生在本機憑證解析階段：請求從未送達 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 或 [Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)。Claude Code 會在此錯誤出現之前清除其[憑證快取](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#credential-caching-and-resolution-timeout)並重試，因此當您看到此錯誤時，憑證鏈已在多次嘗試中停滯。

```text theme={null}
API Error: Could not load AWS credentials · AWS default-chain credential resolve timed out. Check or refresh your AWS credentials and try again.
```

常見原因包括：AWS 設定檔中的 `credential_process` 命令正在等待它無法接收的輸入，以及容器或虛擬機器的執行個體中繼資料服務（IMDS）始終未回應憑證鏈的探測。

在 v2.1.267 之前，訊息為 `API Error: AWS default-chain credential resolve timed out`。
在 v2.1.207 之前，停滯的憑證鏈會讓請求無限期等待，而不會失敗。

**處理方式：**

* 在同一個 shell 中使用相同的 `AWS_PROFILE` 執行 `aws sts get-caller-identity`。如果它也停滯，請修正設定檔；以互動方式提示輸入的 `credential_process` 命令是常見原因。
* 在啟動 Claude Code 之前完成登入步驟，例如 `aws sso login --profile myprofile`
* 如果您的憑證鏈執行的互動式登入確實需要超過 60 秒，例如透過 `aws-vault` 等包裝工具進行的 SSO 加 MFA，請使用 [`CLAUDE_CODE_AWS_CHAIN_RESOLVE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 以毫秒為單位提高上限

### Bedrock 設定驗證在等待 AWS 時逾時

在 [Bedrock 設定精靈](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#sign-in-with-bedrock)的憑證驗證期間，對 AWS 的某個呼叫（例如憑證查詢或身分檢查）未在 60 秒上限內完成。精靈會停止等待，並使驗證步驟失敗：

```text theme={null}
Timed out after 60s waiting for AWS. Check your network and proxy settings; if a credential helper needs longer to prompt you, raise CLAUDE_CODE_AWS_CHAIN_RESOLVE_TIMEOUT_MS.
```

數字反映的是您的上限：預設為 60 秒，或是您在 [`CLAUDE_CODE_AWS_CHAIN_RESOLVE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 中設定的值。

常見原因包括：網路或代理伺服器使對 AWS 的請求（包括 SSO token 重新整理）停滯，以及憑證輔助程式仍在等待您看不到的輸入。只有在輔助程式確實需要更多時間時才提高上限。

單一對 AWS 的停滯請求也可能因其自身的單次請求逾時而失敗，這會在同一步驟顯示較短的訊息：

```text theme={null}
A request to AWS timed out. Check your network and proxy settings, then try again.
```

當相同的逾時發生在模型固定步驟時，精靈會將模型標記為 `unreachable`，而不會顯示上述任一訊息。

**處理方式：**

* 在同一個 shell 中執行 `aws sts get-caller-identity`。如果它也停滯，表示停滯發生在 Claude Code 之外，位於您的網路、代理伺服器或 AWS 設定檔中的憑證輔助程式；請先修正該問題。
* 在開啟精靈之前完成任何互動式登入，例如 `aws sso login --profile myprofile`
* 如果 AWS 設定檔中的憑證輔助程式確實需要超過 60 秒來提示您，請使用 [`CLAUDE_CODE_AWS_CHAIN_RESOLVE_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars) 以毫秒為單位提高上限

### 雲端閘道工作階段已過期

您是透過 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入的，而儲存在此機器上的閘道工作階段已過期且無法續期，或閘道已不再接受它，例如在閘道的 [JWT 密鑰被替換](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#jwt-secret-rotation)之後。如果您在以互動方式啟動 `claude` 時看到這一行，表示工作階段已在未登入閘道的狀態下開啟：

```text theme={null}
Cloud gateway session expired — run /login to reconnect.
```

當閘道憑證過期且 Claude Code 無法續期時，同一行也可能在工作階段進行中出現。

在[非互動](https://code.claude.com/docs/zh-TW/headless.md)執行、背景或其他無人值守的工作階段，或 `claude auth` 以外的 `claude` 子命令中，當閘道不再接受該工作階段時，Claude Code 會改為以此訊息結束：

```text theme={null}
Cloud gateway <url> no longer accepts this session. Start `claude` and sign in again with /login.
```

**處理方式：**

* 在工作階段中執行 `/login` 並完成瀏覽器登入
* 若為非互動式啟動，請在相同環境中啟動 `claude`，執行 `/login`，然後重新執行您的命令

### 等待您繼續時登入逾時

在 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入期間，閘道指出了登入的帳戶，而 Claude Code 要求您在儲存憑證之前確認該帳戶。您讓確認畫面停留超過了登入本身的有效期限，且閘道未核發可用來續期的 refresh token，因此當您繼續時，Claude Code 沒有儲存任何內容：

```text theme={null}
Sign-in timed out while waiting for you to continue. Try again.
```

**處理方式：**

* 再次執行 `/login`，並在登入過期之前確認帳戶

### 閘道拒絕了請求

您是透過 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)登入的，而某個請求傳回了 403：閘道或其背後的上游拒絕了該請求。重新登入無法改變拒絕結果，因此訊息會指向您的閘道管理員：

```text theme={null}
Gateway refused the request · signing in again won't change this — check with your gateway administrator · API Error: 403 ...
```

**處理方式：**

* 請您的閘道管理員查詢該請求。`API Error:` 後面的內容包含閘道傳回的拒絕資訊
* 對管理員而言：閘道上的[存取控制規則](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#http-tuning)會傳回 403，並由[稽核日誌](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#logs)記錄其原因；上游的授權拒絕則會依照[上游錯誤訊息](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages)的方式傳遞

在 v2.1.273 之前，閘道工作階段上的 403 會改為顯示通用的 `Please run /login` 或 `Failed to authenticate` 訊息，且重新登入也無法解除該拒絕。

## 網路和連線錯誤

大多數這些錯誤表示來自 Claude Code 的網路請求無法到達其目的地，或 Claude Code 和 API 之間的某些東西在回程中改變了回應；如果條目也有本機原因（例如失敗的封存寫入），其內容會說明。它們通常源自您的本機網路、代理伺服器或防火牆，或雲端環境的網路原則。

### Unable to connect to API

到 API 的 TCP 連線失敗或從未完成。對於常見的連線錯誤代碼，訊息會命名失敗的類型並在括號中保留代碼：

```text theme={null}
Unable to connect to API. Check your internet connection
Connection refused — a firewall or proxy may be blocking it (ConnectionRefused)
Can't reach the API server — check your internet or DNS (ENOTFOUND)
No internet route — check your connection or VPN (EHOSTUNREACH)
Couldn't connect through your proxy (ERR_PROXY_TUNNEL) — the proxy refused the tunnel: check its credentials and that it allows this host
Connection dropped (ECONNRESET)
Request timed out. Check your internet connection and proxy settings
```

Claude Code 無法識別的代碼會顯示為 `Unable to connect to API` 後跟括號中的代碼。某些這些訊息可以顯示多個代碼：例如 `Connection refused` 可以顯示 `ConnectionRefused` 或 `ECONNREFUSED`，而 `Can't reach the API server` 可以顯示 `ENOTFOUND` 或 `FailedToOpenSocket`。

在 v2.1.227 之前，這些編碼訊息中的每一個都讀作 `Unable to connect to API` 後跟代碼，例如 `Unable to connect to API (ECONNREFUSED)`。

常見原因包括沒有網際網路存取、阻止 `api.anthropic.com` 的 VPN，或未設定的必需公司代理伺服器。

**該怎麼做：**

* 透過從同一個 shell 執行 `curl -I https://api.anthropic.com` 來確認您可以到達 API 主機。在 Windows PowerShell 上使用 `curl.exe -I https://api.anthropic.com`，以便不使用內建的 `Invoke-WebRequest` 別名。
* 如果您在公司代理伺服器後面，在啟動 Claude Code 之前設定 `HTTPS_PROXY` 並查看[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)
* 如果您透過 LLM 閘道或中繼路由，將 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 設定為其位址。請參閱[將 Claude Code 連線到 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)以進行設定。
* 如果 `ANTHROPIC_BASE_URL` 已指向您的閘道，且每個請求都以 `Connection dropped` 結束，請檢查您的閘道及其上游是否接受[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#tool-search-through-a-gateway)欄位。根據預設，Claude Code 會傳送 `defer_loading` 工具欄位和 `tool_reference` 區塊，並附帶啟用它們的 `anthropic-beta` 標頭。在 v2.1.304 之前，在閘道後面工具搜尋為關閉狀態，除非您使用 `ENABLE_TOOL_SEARCH` 將其開啟。
* 確保您的防火牆允許[網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)中列出的主機
* 間歇性故障會[自動重試](#automatic-retries)

如果 `curl` 成功但 Claude Code 仍然失敗，原因通常是執行時和網路之間的某些東西，而不是網路本身：

* 透過執行 `echo $ANTHROPIC_BASE_URL` 檢查 `ANTHROPIC_BASE_URL` 是否已設定，或在 PowerShell 中執行 `echo $env:ANTHROPIC_BASE_URL`，並在您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md)的 `env` 區塊中查找它。當它被設定時，Claude Code 會將模型請求傳送到該位址而不是 `api.anthropic.com`，因此指向不再執行的本機代理伺服器或閘道的過時值會產生 `Connection refused`，即使 `curl` 到達 API。從您的 shell 設定檔或設定中移除它，並從新終端機啟動 Claude Code。
* 在 Linux 和 WSL 上，檢查 `/etc/resolv.conf` 是否有無法到達的名稱伺服器。特別是 WSL 可以從主機繼承損壞的解析器。
* 在 macOS 上，已斷開連線或卸載的 VPN 用戶端可能會留下隧道介面或路由規則。檢查 `ifconfig` 是否有過時的 `utun` 介面，並在系統設定中移除 VPN 的網路擴充功能。
* Docker Desktop 和類似的容器執行時可以攔截出站流量。退出它們並重試以排除這種可能性。

### Unable to connect to Anthropic services

在首次執行設定期間，Claude Code 會檢查它是否可以到達 `api.anthropic.com` 和 `platform.claude.com`，然後才顯示登入步驟。當任一檢查失敗時，Claude Code 會列印原因並退出。

```text theme={null}
Unable to connect to Anthropic services
Failed to connect to api.anthropic.com: ECONNREFUSED
Connection to api.anthropic.com timed out after 10 seconds
A proxy is configured via HTTPS_PROXY. Check that it allows connections to the host above.
```

Claude Code 透過與 API 請求相同的[代理伺服器設定](https://code.claude.com/docs/zh-TW/network-config.md)發送檢查，並給每個探測 10 秒。當失敗的探測通過代理伺服器時，訊息會命名設定它的環境變數，例如 `HTTPS_PROXY`。在 v2.1.222 之前，檢查使用不同的代理伺服器傳輸，沒有逾時：在具有 `https://` 方案的代理伺服器 URL 後面，它可能會在 `Checking connectivity...` 上無限期停滯，然後即使透過同一代理伺服器的 API 請求成功也會失敗。

當[受管設定檔、MDM 原則或原則協助程式](https://code.claude.com/docs/zh-TW/managed-settings.md)將 [`forceLoginMethod`](https://code.claude.com/docs/zh-TW/settings-reference#forceloginmethod) 設定為 `"gateway"`，或設定 [`forceLoginGatewayUrl`](https://code.claude.com/docs/zh-TW/settings-reference#forcelogingatewayurl) 而不設定 `forceLoginMethod` 時，Claude Code 會跳過此檢查。使用任一設定，Claude Code 會在 **Cloud gateway** 畫面上開啟登入步驟，而不是 Anthropic 登入方法。當機器上存在受管設定來源但無法讀取時，Claude Code 也會跳過檢查，因為該來源可能保有閘道設定。在 v2.1.247 之前，Claude Code 在此設定下也執行檢查，當 Anthropic 的端點無法到達時以此錯誤退出。

在沒有受管設定的機器上，當您自己的 `~/.claude/settings.json` 以 `forceLoginMethod` 和 `forceLoginGatewayUrl` [指定閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#set-the-gateway-url-in-user-settings)時，Claude Code 也會跳過此檢查。在 v2.1.295 之前，Claude Code 在這種情況下會執行檢查。

**該怎麼做：**

* 如果訊息命名代理伺服器變數，檢查其值是否指向正確的代理伺服器，並要求您的網路團隊允許透過它到訊息中主機的 HTTPS 連線。請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)。
* 完成 [Unable to connect to API](#unable-to-connect-to-api) 中的檢查。那裡的 `curl` 測試和防火牆指導也適用於此檢查。
* 如果您的網路是開放的，故障仍然存在，Claude Code 可能在您的國家[無法使用](https://www.anthropic.com/supported-countries)

### Socket is closed

`Socket is closed` 表示承載串流回應的連線在回應仍在到達時被關閉。最常見的原因是 Windows 上的公司代理伺服器在回應中途丟棄已建立的隧道。

根據回應進行的距離，Claude Code 會重試請求、保留 Claude 產生的內容，或結束回合。請參閱[自動重試](#automatic-retries)。

在 v2.1.214 之前，Claude Code 不會重試此故障，回合會停止並出現包含 `Socket is closed` 的錯誤。

**該怎麼做：**

* 如果您看到此錯誤，請使用 `claude update` 更新到 v2.1.214 或更新版本，然後再次傳送您的訊息
* 如果在更新後回合在同一代理伺服器後面持續失敗，請完成 [Unable to connect to API](#unable-to-connect-to-api) 並檢查[網路設定](https://code.claude.com/docs/zh-TW/network-config.md)中的代理伺服器設定

### API returned an empty or malformed response

當 Claude Code 對失敗的串流請求進行非串流重試時，如果獲得 HTTP 成功狀態但主體不是 Claude API 訊息，Claude Code 會顯示此錯誤：通常是 HTML 錯誤或登入頁面、空主體或其他格式的 JSON。代理伺服器、閘道或網路登入頁面代替 API 回答是常見來源。Claude Code 不會重試請求，回合以此錯誤結束。

```text theme={null}
API returned an empty or malformed response (HTTP 200) — check for a proxy or gateway intercepting the request.
```

在該開頭之後，訊息會報告返回的內容以及哪個請求失敗：

* 一個 `Response:` 子句，包含內容類型、主體類型（例如 `body is an HTML page` 或 `empty body`）、其大小（以位元組為單位），以及回應是否攜帶 Anthropic 請求 id。當回應命名可識別的伺服器（例如 `nginx` 或 `cloudflare`）或攜帶中介標頭（例如 `cf-ray` 或 `via`）時，子句也會列出這些。
* 一個句子，命名失敗的串流請求的 id 和觸發重試的故障。當串流在故障前開啟時，它也會報告有多少串流事件到達，以及如果有的話，當嘗試失敗時串流已沉默多長時間。

在 v2.1.234 之前，訊息在 `intercepting the request` 後結束。

在 v2.1.271 之前，在非 JSON 內容類型（例如 `text/plain`）下攜帶有效 API 訊息的回覆也會以此錯誤結束回合。某些 LLM 閘道對非串流回覆使用該內容類型。

**該怎麼做：**

* 閱讀 `Response:` 子句以查看哪個系統回答。HTML 主體、沒有 Anthropic 請求 id 或命名的伺服器（例如 `nginx` 或 `cloudflare`）表示 Claude Code 和 API 之間的某些東西代替它回答
* 如果您透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#troubleshoot-gateway-errors)路由，使用直接請求測試路由，並修復返回非 API 回應的跳躍
* 在具有登入頁面的網路上（例如訪客 Wi-Fi），在瀏覽器中完成登入，然後重試
* 如果只有透過您的閘道的非串流路由損壞，設定 [`CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 以關閉此備援，除非串流端點本身傳回 `404`，此時 Claude Code 仍然會改用非串流

### Streaming response ended before any complete data was received

來自您的模型提供者的串流回應完成，但未傳遞任何可用資料，因此 Claude Code 重新傳送請求而不進行串流以完成回合。Claude Code 每個工作階段顯示一次警告，僅在互動式工作階段中。在 v2.1.239 之前，Claude Code 無聲地重試而不進行串流。

```text theme={null}
Streaming response ended before any complete data was received. Retrying without streaming. If this keeps happening, check any proxy or gateway between Claude Code and your model provider.
```

Claude Code 傳送每個受影響的請求兩次：空串流嘗試和重試。常見原因是在回程中消耗或轉換串流回應主體的代理伺服器或閘道。

**該怎麼做：**

* 設定 Claude Code 和您的模型提供者之間的任何代理伺服器或閘道，以未修改的方式傳遞串流回應主體及其標頭
* 在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 上，請參閱[閘道或代理伺服器後面的串流錯誤](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#streaming-errors-behind-a-gateway-or-proxy)以了解標頭和主體要求

### Bedrock 串流回應具有意外的 content-type

Claude Code 和 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 之間的閘道或代理伺服器正在轉換串流回應主體或其 `Content-Type` 標頭。Amazon Bedrock 將回應串流為 `application/vnd.amazon.eventstream`。Claude Code 不會解碼無法讀取的主體，而是拒絕報告不同 content-type 的成功串流回應。Claude Code 不會重試請求。

```text theme={null}
Bedrock streaming response has content-type "text/event-stream"; expected "application/vnd.amazon.eventstream". A gateway or proxy between Claude Code and Bedrock is likely transforming the response body — Bedrock's binary event-stream format must be passed through unmodified. Set CLAUDE_CODE_DISABLE_BEDROCK_CONTENT_TYPE_GUARD=1 to suppress this check while the gateway is being fixed.
```

在 v2.1.208 之前，相同的設定錯誤在整個回應被緩衝後顯示為 `API Error: Truncated event message received`。

**該怎麼做：**

* 設定閘道以未修改的方式傳遞 `InvokeModelWithResponseStream` 回應主體及其 `Content-Type` 標頭。重新發出串流為伺服器傳送事件的中介是常見原因。
* 設定 [`CLAUDE_CODE_DISABLE_BEDROCK_CONTENT_TYPE_GUARD=1`](https://code.claude.com/docs/zh-TW/env-vars) 會隱藏此錯誤，但 Claude Code 不會在重寫的標頭下解碼二進位主體，因此這些請求會改用較慢的非串流路徑。請參閱[閘道或代理伺服器後面的串流錯誤](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#streaming-errors-behind-a-gateway-or-proxy)。

### SSL 憑證錯誤

您網路上的代理伺服器或安全設備正在使用自己的憑證攔截 TLS 流量，Claude Code 不信任它。

```text theme={null}
Unable to connect to API: SSL certificate verification failed (UNABLE_TO_GET_ISSUER_CERT_LOCALLY). The certificate comes from an authority Claude Code doesn't trust, usually a TLS-inspecting corporate proxy or a gateway signed by a private CA: set NODE_EXTRA_CA_CERTS to that CA bundle, or add it to the system certificate store · see https://code.claude.com/docs/en/network-config
Unable to connect to API: Self-signed certificate detected (SELF_SIGNED_CERT_IN_CHAIN). The certificate comes from an authority Claude Code doesn't trust, usually a TLS-inspecting corporate proxy or a gateway signed by a private CA: set NODE_EXTRA_CA_CERTS to that CA bundle, or add it to the system certificate store · see https://code.claude.com/docs/en/network-config
```

在 v2.1.273 之前，兩個訊息都在 `Check your proxy or corporate SSL certificates` 結束，沒有 OpenSSL 代碼或 `NODE_EXTRA_CA_CERTS` 提示。

從 v2.1.199 開始，憑證驗證失敗不會重試，因此此錯誤會在第一次嘗試時出現，而不是在完整[重試預算](#automatic-retries)後出現。較早的版本在顯示它之前花費幾分鐘重試。暫時性 TLS 條件（例如握手逾時）仍然會重試。

在 `/login` 和啟動連線檢查期間，相同的故障會產生不同的訊息：

```text theme={null}
SSL certificate error (UNABLE_TO_GET_ISSUER_CERT_LOCALLY). If you are behind a corporate proxy or TLS-intercepting firewall, set NODE_EXTRA_CA_CERTS to your CA bundle path, or ask IT to allowlist *.anthropic.com. Run `claude doctor` for details.
```

在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 上，Claude Code 本身發送給 AWS 的請求（例如 STS 和 SSO 角色憑證呼叫、模型發現和設定精靈的檢查）取決於相同的憑證設定。請參閱[TLS 檢查代理伺服器後面的憑證錯誤](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#certificate-errors-behind-a-tls-inspecting-proxy)。

**該怎麼做：**

* 匯出您組織的 CA 套件，並使用 `NODE_EXTRA_CA_CERTS=/path/to/ca-bundle.pem` 將 Claude Code 指向它
* 請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md#custom-ca-certificates)以了解完整設定說明
* 不要設定 `NODE_TLS_REJECT_UNAUTHORIZED=0`，這會完全停用憑證驗證

### 雲端工作階段中不允許主機

來自雲端工作階段或雲端排程任務的出站 HTTP 請求被環境的網路原則阻止。

```text theme={null}
HTTP 403
x-deny-reason: host_not_allowed
```

您也可能看到與目的地的真實憑證不符的 TLS 憑證。雲端工作階段透過代理伺服器路由出站流量，該代理伺服器強制執行網路原則，因此不符的憑證表示代理伺服器終止了連線，而不是目的地。

此錯誤不是用戶端網路問題。雲端工作階段和[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)在沙箱 VM 內執行，其透過工作階段網路的出站流量被過濾到[雲端環境的](https://code.claude.com/docs/zh-TW/cloud-environments.md)允許清單：

* **GitHub 和連接器流量**：[GitHub 操作](https://code.claude.com/docs/zh-TW/cloud-environments.md#github-proxy)和 MCP 連接器流量使用單獨的通道，這就是為什麼它們可以在其他主機被阻止時繼續工作
* **預設環境**：**預設**環境使用**信任**存取，允許[預設允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)的套件登錄、雲端提供者 API、容器登錄和常見開發網域，並阻止該路徑上的其他網域

**該怎麼做：**

這些步驟會變更您自己的環境之一。[組織共享環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)在選擇器中以唯讀方式開啟，因此請要求擁有者從[管理設定](https://claude.ai/admin-settings)中的**雲端環境**頁面變更其網路存取。

* 開啟您的環境進行編輯，可從[雲端排程任務的表單](https://code.claude.com/docs/zh-TW/routines.md#environments-and-network-access)，或從您啟動雲端工作階段的[環境選擇器](https://code.claude.com/docs/zh-TW/cloud-environments.md#configure-your-environment)開啟。
* 在**編輯雲端環境**對話方塊中，將**網路存取**從**信任**變更為**自訂**，然後將被阻止的網域新增到**允許的網域**。每行輸入一個網域。勾選**也包括常見套件管理員的預設清單**以在您的自訂網域旁邊保留[預設允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#default-allowed-domains)。如果您想要不受限制的存取，請改為選擇**完整**。
* 按一下**儲存變更**。下一次執行使用更新的允許清單。對於已開啟的雲端工作階段，請參閱[網路存取變更何時到達現有工作階段](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)。

請參閱[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)以了解存取層級和預設允許清單。本機 CLI 工作階段不受此原則影響。

### The proxy refused the connection

當 Claude 透過您在 `HTTPS_PROXY` 或相關[代理伺服器變數](https://code.claude.com/docs/zh-TW/network-config.md#environment-variables)中設定的代理伺服器讀取 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 時，您會看到此訊息。Artifact 內容來自 `*.frame.claudeusercontent.com`，因此 Claude Code 首先向代理伺服器傳送 `CONNECT` 請求，要求它開啟到該主機的隧道。當代理伺服器拒絕時，沒有任何東西到達主機，訊息攜帶代理伺服器的 HTTP 狀態：

```text theme={null}
artifact content fetch failed (proxy refused the connection: HTTP 407)
artifact content fetch failed (proxy refused the connection: HTTP 403)
the proxy refused the connection to the artifact's content host (HTTP 502)
```

狀態是代理伺服器對 `CONNECT` 的回答。主機從未回答，因此每個狀態指向不同的修復：

* `HTTP 407`：代理伺服器需要它沒有獲得的憑證。將它們放在代理伺服器 URL 中，如[基本身分驗證](https://code.claude.com/docs/zh-TW/network-config.md#basic-authentication)所示。
* `HTTP 403`：代理伺服器拒絕建立到 `*.frame.claudeusercontent.com` 的隧道。要求管理代理伺服器的人允許該主機，[網路存取要求](https://code.claude.com/docs/zh-TW/network-config.md#network-access-requirements)會列出該主機。
* 任何其他狀態，例如 `HTTP 502`：代理伺服器因其自身原因未開啟隧道，例如無法到達主機。在代理伺服器的日誌中查詢狀態。
* `unreadable reply` 代替狀態：代理伺服器位址上的任何東西都沒有用 HTTP 狀態列回答。檢查位址是否為 HTTP 代理伺服器。

**該怎麼做：**

* 檢查代理伺服器變數中的位址和憑證，如[代理伺服器設定](https://code.claude.com/docs/zh-TW/network-config.md#proxy-configuration)所述，然後從啟動 Claude Code 的 shell 執行 `curl -x http://proxy.example.com:8080 -I https://api.anthropic.com`，使用您自己的代理伺服器 URL。在 Windows PowerShell 上，執行 `curl.exe`。如果此探測以相同方式失敗，請先修復代理伺服器設定。如果成功，拒絕特定於 artifact 主機。
* 如果您的網路讓 Claude Code 直接到達 artifact 主機，將 `.frame.claudeusercontent.com` 新增到 [`NO_PROXY`](https://code.claude.com/docs/zh-TW/network-config#environment-variables)。保持條目狹窄：更廣泛的 `.claudeusercontent.com` 條目也會讓 `bridge.claudeusercontent.com` 繞過代理伺服器，而具有 [IP 允許清單](https://code.claude.com/docs/zh-TW/network-config.md#organization-ip-allowlists-and-proxy-egress)的組織需要將其保留在代理伺服器上。

在 v2.1.238 之前，Claude Code 將拒絕的隧道報告為通用網路錯誤。

### 雲端環境服務傳回空的或意外的回應

Claude Code 在多個點請求您的[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)清單，例如當您從 CLI 建立雲端工作階段或執行 [`/remote-env`](https://code.claude.com/docs/zh-TW/cloud-environments#select-an-environment-from-the-cli) 時。當它無法讀取伺服器的回答時，它會顯示以下其中一個訊息：

```text theme={null}
The cloud environments service returned an empty response (HTTP 200 with no body). This is usually temporary — try again in a moment.
The cloud environments service returned a response in an unexpected format (HTTP 200 with a non-JSON body). This is usually temporary — try again in a moment.
The cloud environments service returned a response in an unexpected format (HTTP 200 without a usable environments list). This is usually temporary — try again in a moment.
```

伺服器接受了請求，但用不是環境清單的主體回答：空、不是 JSON 或沒有清單的 JSON。這通常伴隨服務端中斷，並自行清除。根據請求清單的使用介面，Claude Code 可能會新增前綴，例如 `/remote-env` 對話方塊中的 `couldn't list environments:`。

**該怎麼做：**

* 重試該操作。Claude Code 每次都會再次請求清單
* 如果訊息持續出現，請檢查 [status.claude.com](https://status.claude.com) 以了解活躍的事件

在 v2.1.236 之前，Claude Code 顯示原始 JavaScript TypeError 而不是這些訊息。

### Failed to fetch session from Sessions API

此訊息表示 Claude Code 找到了[您要求拉取到終端機的雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-cloud-to-terminal)，但無法從 Anthropic 的伺服器讀取其對話記錄，因此沒有開啟它：

```text theme={null}
Failed to fetch session from Sessions API: Failed to fetch session logs
```

您會在執行 `claude --teleport`、`/teleport`，或在 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 清單中選擇該工作階段後看到它。`claude --teleport <session-id>` 會列印它並以代碼 1 退出。

**該怎麼做：**

* 再次執行相同的 teleport。如果以相同方式失敗，請[回報問題](#report-an-error)

在 v2.1.296 之前，Claude Code 不會重試失敗的讀取，並且在讀取失敗後可能會以空白對話開啟該工作階段並回報成功，而不是列印此訊息。

### Couldn't reconnect to your Remote Control session

```text theme={null}
Couldn't reconnect to your Remote Control session. Retry, or start a fresh session without --resume.
```

使用 `claude --resume` 或 `claude --continue` 恢復會重新連線到該對話中記錄的 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 工作階段。此訊息表示重新連線因可能是暫時的原因（例如網路中斷或伺服器錯誤）而失敗，因此 Claude Code 無法確認遠端工作階段是否仍然存在。您的本機工作階段在沒有 Remote Control 的情況下繼續執行。

**該怎麼做：**

* 執行 `/remote-control` 以重試連線
* 使用 `claude --remote-control` 啟動新工作階段以建立新的 Remote Control 工作階段
* 對於其他 Remote Control 啟動訊息，請參閱[Remote Control 疑難排解](https://code.claude.com/docs/zh-TW/remote-control.md#troubleshooting)

如果伺服器改為報告前一個工作階段已消失，您不會看到此訊息。Claude Code 會在其位置啟動新工作階段或顯示 [`Previous session is unavailable — run /remote-control to start a new one`](https://code.claude.com/docs/zh-TW/remote-control#previous-session-is-unavailable)。

### Sessions ended while this machine was offline

Claude Code 在執行 [`claude remote-control`](https://code.claude.com/docs/zh-TW/remote-control#start-a-remote-control-session) 的終端機中顯示此訊息，在您的機器離線足夠長的時間後，伺服器清理了您的機器正在提供的 Remote Control 環境。該環境中的工作階段已結束，您無法恢復它們。計數是已結束的工作階段數。

```text theme={null}
2 sessions ended while this machine was offline — the environment was cleaned up on the server and can't be resumed.
```

**該怎麼做：**

* 當 Claude Code 在此訊息下列出保留的 worktree 時，從它們中取回任何未提交的工作
* 執行 `claude remote-control` 以啟動新環境

### Couldn't share the transcript

在您同意從調查提示（例如[工作階段品質調查](https://code.claude.com/docs/zh-TW/data-usage.md#session-quality-surveys)）共享您的工作階段逐字稿後，Claude Code 將其上傳到 Anthropic，或在第三方提供者上、[Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段上以及當沒有 Anthropic 憑證可用時改為儲存本機封存。此訊息表示共享未完成。

```text theme={null}
Couldn't share the transcript.
```

上傳必須符合 8 MiB 限制。在長工作階段上，Claude Code 逐步丟棄共享的部分，最後一個請求的模型設定優先，然後是結構化對話和 subagent 逐字稿，並在無法傳送任何縮減版本或網路或伺服器錯誤停止上傳時顯示此訊息。當 Claude Code 改為儲存本機封存時，訊息表示它無法寫入封存。

**該怎麼做：**

* 執行 `/feedback` 以傳送逐字稿並描述發生了什麼。如果您的環境中無法使用 `/feedback`，請參閱[報告錯誤](#report-an-error)
* 如果其他請求也失敗，請檢查您的網路連線並查看 [Unable to connect to API](#unable-to-connect-to-api)

### Couldn't send feedback

以 `Couldn't send feedback` 開頭的訊息表示意見反應服務未確認收到您從 [`/feedback`、`/bug` 或 `/share` 對話方塊](https://code.claude.com/docs/zh-TW/commands#all-commands)提交的報告，或佇列中的[意見反應草稿](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)。請將其視為未收到。當冒號後面接著一句關於您組織的說明時，表示您的組織拒絕接收意見反應，同一份報告會得到相同的回應。

以下兩個範例中，第二個是組織的拒絕：

```text wrap theme={null}
Couldn't send feedback (couldn't reach the service). If it keeps failing, you can file at https://github.com/anthropics/claude-code/issues instead.

Couldn't send feedback: Feedback has not been enabled for your organization. To report a bug, open an issue at https://github.com/anthropics/claude-code/issues. Issues are public, so leave out anything confidential.
```

**該怎麼做：**

* **未登入**：訊息接著顯示 `: not signed in. Run /login, then retry.`。執行 `/login`，然後再次傳送
* **您組織的拒絕**：例如 `: Feedback has not been enabled for your organization.` 或 `: Feedback collection is not available for organizations with custom data retention policies.`。如果訊息附加 `To report a bug, open an issue`，請在 [github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues) 提交 issue。佇列中的草稿會保留在佇列中，您可以[捨棄它](https://code.claude.com/docs/zh-TW/tools-reference.md#discard-or-keep-a-draft)
* **憑證遭拒**：訊息接著顯示 `: the sign-in this session uses is not allowed to send feedback` 或 `: the server did not accept the credentials this session uses`。在 Claude Code 提示字元執行 `/status`，以查看此工作階段傳送的是哪個登入、token 或 API 金鑰
* **`Couldn't send feedback` 後緊接著 `(request timed out)` 或 `(couldn't reach the service)`**：再次傳送報告或佇列中的草稿。對話方塊會保留您的文字，而佇列中草稿的訊息會顯示 `The draft is still queued.`。如果其他請求也失敗，請檢查您的網路連線並查看 [Unable to connect to API](#unable-to-connect-to-api)。如果持續失敗，請在 [github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues) 提交報告
* **`Couldn't send feedback` 後緊接著 `(server returned <status>)`，或沒有任何原因**：狀態是服務的回應代碼。當服務有傳送自己的訊息時，該訊息會接在狀態之後，例如 `(server returned 403: Access Forbidden)`。如果持續失敗，請在 [github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues) 提交報告

github.com/anthropics/claude-code 上的 issue 是公開的，因此在提交時請省略程式碼、逐字稿以及任何其他機密內容。

在 v2.1.281 之前，一旦在對話方塊開啟期間收到 Remote Control **Stop** 或緊急跨工作階段訊息，之後每次傳送都會失敗並出現此訊息。在這些版本上，關閉對話方塊，重新開啟它，然後再次傳送。

### Feedback payload too large

[意見反應草稿](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)的[檢閱畫面](https://code.claude.com/docs/zh-TW/tools-reference.md#review-and-edit-a-draft)中出現此訊息，表示 Claude Code 沒有收到服務已接受該草稿的確認。請將其視為未收到。草稿會保留在您的 `/feedback` 佇列中，因此您可以再次傳送。

```text wrap theme={null}
Feedback payload too large. Try again without the transcript, or shorten the details.
```

**該怎麼做：**

* 在檢閱畫面中，將 **Send transcript** 設定為 `no`，然後再次傳送草稿。縮短詳細資訊最多只能移除 10 KB 的文字，這也是草稿詳細資訊所能容納的全部內容。

### 睡眠或時鐘變更期間 MCP 伺服器連線逾時

此訊息表示與 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)的連線逾時，且 Claude Code 發現您的系統時鐘在嘗試期間向前跳動：

```text theme={null}
MCP server "<name>" connection timed out. Your computer went to sleep or its clock changed while connecting.
```

Claude Code 無法判斷您的電腦是進入睡眠還是時鐘被調快，因此訊息會同時提及兩者。

**該怎麼做：**

再次連線到該伺服器，並讓您的電腦保持喚醒直到嘗試完成。如果伺服器連線成功，就無需修復任何問題。

* **在互動式工作階段中**：執行 `/mcp`，選擇該伺服器，然後選擇 **Reconnect**
* **在您的 shell 中**：再次執行 [`claude -p`](https://code.claude.com/docs/zh-TW/headless)、[`claude mcp list`](https://code.claude.com/docs/zh-TW/mcp#managing-your-servers) 或 `claude mcp get` 命令。如果伺服器接著失敗並出現以 `Skipping connection (recent failure cached` 開頭的訊息，請等待 15 分鐘後再次執行該命令。
* **在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式中**：在 TypeScript 中呼叫 [`reconnectMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#methods)，或在 Python 中呼叫 [`ClaudeSDKClient.reconnect_mcp_server()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)
* **如果伺服器再次失敗**：如果訊息與此訊息不同，請參閱 [MCP 伺服器無法連線時要檢查的項目](https://code.claude.com/docs/zh-TW/mcp-quickstart.md#troubleshooting)。如果您的電腦保持喚醒且沒有任何東西變更其時鐘，此訊息卻仍再次出現，請參閱[報告錯誤](#report-an-error)。

在 v2.1.307 之前，Claude Code 顯示的是 `MCP server "<name>" connection timed out after <N>ms` 之類的逾時訊息，而不是此訊息。

## 請求錯誤

這些錯誤與您的請求內容有關。大多數來自 API 在拒絕請求後的回應；少數是由 Claude Code 在發送任何請求之前在本地產生的。

### Prompt is too long

對話加上附加檔案超過了模型的上下文視窗。

```text theme={null}
Prompt is too long
```

在互動式工作階段中，Claude Code 將此錯誤顯示為：

```text theme={null}
Context limit reached · /compact or /clear to continue
```

當設定了 [`DISABLE_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 時，該行僅命名 `/clear`。較長形式的錯誤（例如下面的壓縮失敗形式）保留 `Prompt is too long ·` 的措辭。在 `-p` 輸出和逐字稿中，文字保持為 `Prompt is too long`。

當您在[使用者設定](https://code.claude.com/docs/zh-TW/settings-reference.md#autocompactenabled)中關閉自動壓縮時，該行也會說明這一點：

```text theme={null}
Context limit reached · /compact or /clear to continue · auto-compact is off · /config to turn it on
```

`/config` 中的**自動壓縮**切換會將 `autoCompactEnabled` 寫入使用者設定。該提示僅在 `/config` 變更會生效時出現。例如，當 [`DISABLE_AUTO_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`DISABLE_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 關閉自動壓縮時，它不會出現。當更高優先級的範圍（例如專案或受管設定）將 `autoCompactEnabled` 設定為 `false` 時，它也不會出現。在 v2.1.235 之前，該行沒有自動壓縮提示。

Amazon Bedrock 將此狀況報告為 `Input is too long for requested model.`，Claude Code 以相同方式處理。在 v2.1.217 之前，Claude Code 沒有識別 Bedrock 的措辭，因此自動壓縮從未在其上觸發，`/compact` 失敗並出現相同錯誤。

[Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages)在雲端上游以提供者自己的錯誤形狀拒絕請求時，將此狀況報告為 `capability_rejected: prompt_too_long`。Claude Code 將該 token 視為與 `Prompt is too long` 相同。在 v2.1.228 之前，Claude Code 沒有識別該 token，因此自動壓縮沒有在其上觸發。

當自動壓縮在此回合上執行並因基礎錯誤（例如不可用的模型或身分驗證失敗）而失敗時，該訊息在分隔符後命名該錯誤：

```text theme={null}
Prompt is too long · automatic compaction failed: <the underlying error>
```

首先解決命名的錯誤；在您這樣做之前，`/compact` 會因相同錯誤而失敗。在 v2.1.229 之前，失敗的自動壓縮會顯示 `Prompt is too long` 而不顯示原因。

當自動壓縮在此錯誤上執行時，它通常會總結您最舊的交換並保留最新的。作為最後手段，Claude Code 會以不同方式進行總結：

* 當它無法總結任何完整交換時，Claude Code 會逐字保留您最新的提示詞，並總結其前面的所有內容。
* 在這種情況下，當對話不以您的提示詞結尾時，Claude Code 會改為總結整個對話。

當它要轉發的內容不包含模型回覆且您自己的文字少於約 1,000 個 token（例如在超大貼上後發送的簡短重試）時，Claude Code 會跳過此恢復。執行 `/clear` 以重新開始。在 v2.1.269 之前，每當壓縮無法總結完整交換時，壓縮就會失敗，因此處於該狀態的工作階段在每個回合都會再次遇到此錯誤。

單一交換對話沒有更早的回合可以總結。當自動壓縮會在其上執行時，Claude Code 會跳過嘗試並解釋請求中填充的內容。當 API 在其錯誤中不報告 token 計數時，訊息讀取為：

```text theme={null}
Prompt is too long · this conversation is a single exchange and cannot be compacted — the request size comes mostly from system prompt, tool definitions, or attachments.
```

當 API 在其錯誤中報告 token 計數時，Claude Code 會將其與自己對對話大小的估計進行比較，以判斷請求的大部分是什麼：對話自己的內容，或 Claude Code 與其一起發送的系統提示詞、工具定義和附加內容。當對話自己的內容是請求的大部分時，訊息讀取為：

```text theme={null}
Prompt is too long · the request is ~<request tokens> tokens (limit <limit>) and this conversation's own content is most of it. A single-exchange conversation cannot be compacted; start with less content (smaller files or pasted text).
```

當請求的大部分在對話之外時，訊息讀取為：

```text theme={null}
Prompt is too long · the request is ~<request tokens> tokens (limit <limit>) but this conversation is only ~<conversation tokens> tokens — the rest is system prompt, tool definitions, and attachment content. A single-exchange conversation cannot be compacted; reduce attached files/tools or start with less context.
```

在 v2.1.162 之前，Claude Code 無論如何都嘗試壓縮，並在失敗時顯示裸露的 `Prompt is too long`。

**該怎麼辦：**

* 執行 `/compact` 以總結較早的回合並釋放空間，或執行 `/clear` 以重新開始。如果 `/compact` 回答 `Not enough messages to compact.`，對話是單一交換，沒有更早的內容可以總結，因此空間由該單一提示詞和 Claude Code 與每個請求一起發送的內容佔用：執行 `/clear` 並使用較少的貼上文字或較小的附加檔案重新發送，或使用下面的步驟減少工具定義和記憶檔案
* 執行 `/context` 以查看視窗中消耗的內容的細目：系統提示詞、工具、記憶檔案和訊息
* 使用 `/mcp disable <name>` 禁用您未使用的 MCP 伺服器，以從上下文中移除其工具定義
* 修剪大型 `CLAUDE.md` 記憶檔案，或將指示移至[路徑範圍規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)，這些規則僅在相關時載入
* 自動壓縮預設為開啟，通常可防止此錯誤。如果您在 `/config` 中或使用 [`DISABLE_AUTO_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 關閉了它，請將其重新開啟。如果您保持關閉，請在視窗填滿之前自己執行 `/compact`。
* 如果在可接受更多 token 的模型上，錯誤出現在接近 200K token 時，原因之一是 Claude Code 無法辨識該模型 ID。Claude Code 會為這類 ID 假設 200K 的視窗，因此若要在超過該點後繼續工作，請[提供模型實際的上下文視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)。
  * 如果您使用自訂的 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars)，且錯誤以 `Prompt is too long · automatic compaction failed` 開頭，請[設定模型的上下文視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)或[更新](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)至 v2.1.299 或更新版本。在 v2.1.299 之前，Claude Code 會在接近假設的 200K 視窗時以該訊息結束回合，而不是傳送請求。
* 如果錯誤是在您於 Claude 壓縮對話期間停止它之後立即出現，您的對話並未變更，且仍大到需要壓縮。請執行 `/compact` 並再次送出您的訊息。若要避免此錯誤再次發生，請將 Claude Code [更新](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)至 v2.1.304 或更新版本。在 v2.1.304 之前，在那個時間點停止可能會使該回合以此錯誤結束。
* 在 v2.1.305 上，若有許多 MCP 工具且直接連線至 Anthropic API，此錯誤可能會掩蓋來自 API 的無關 400 或 422 錯誤。請將 [Claude Code 更新](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)至 v2.1.306 或更新版本，以查看原始錯誤。

請參閱[探索上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)以獲得上下文如何填滿的互動式檢視。

### 上下文超過 token 限制

`/context` 顯示此警告在其輸出頂部，當對話超過模型的上下文視窗時。在您釋放空間之前，請求會因 [`Prompt is too long`](#prompt-is-too-long) 而失敗。互動式工作階段將該錯誤顯示為 `Context limit reached` 行。

```text theme={null}
Context exceeds the 200k-token limit by 94k tokens — run /compact or /clear to continue.
```

當您超過的限制是壓縮視窗（例如 1M 上下文模型上的 200K 邊界）時，警告的讀取方式不同。壓縮視窗可以位於模型的上下文視窗下方，因此超過它的請求仍然可以成功。

```text theme={null}
Context is 94k tokens past the 200k-token compaction window — run /compact to reduce usage.
```

當您設定了 [`DISABLE_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars) 時，兩種形式都命名 `/clear` 而不是 `/compact`。

**該怎麼辦：**

* 在多回合對話中，執行 `/compact` 以總結較早的回合並釋放空間。若要改為重新開始，請執行 `/clear`
* 有關減少使用的更多方式，請參閱 [Prompt is too long](#prompt-is-too-long)

在 v2.1.216 之前，`/context` 顯示超過 100% 的使用情況，沒有警告行解釋這意味著什麼或如何恢復。

### Request too large

原始請求正文在 token 化之前超過了 API 的 32MB 限制，通常是因為大型貼上內容、工具結果或附加檔案。此限制與[上下文視窗](#prompt-is-too-long)分開。

```text theme={null}
Request too large (max 32MB). Accumulated images and attachments in the conversation pushed the request over the limit. Run /compact, or double press esc to go back and remove attachments.
```

當請求直接進入 Claude API 且 API 本身拒絕它時，Claude Code 會測量對話並根據恢復是否可行來措辭訊息。通過代理伺服器、閘道或雲端提供者，您會收到一般訊息。測量的形式：

* `Request too large (max 32MB; 20.1MB of about 33.4MB is images or documents).`：影像或文件將請求推過限制。Claude Code 會在去除它們後重試。
* `Request too large for the API's 32MB request limit`：訊息本身超過限制，因此訊息說 `compacting cannot make it fit`，Claude Code 不會重試。在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，訊息告訴您減少輸入或改為開始新工作階段。

在 v2.1.212 之前，具有足夠累積影像的對話在每個回合都因 `Request too large (max 32MB). Double press esc to go back and try with a smaller file.` 而失敗。在 v2.1.229 之前，Claude Code 對每個拒絕都顯示附加建議，即使壓縮無法幫助。

**該怎麼辦：**

* 如果訊息說 `compacting cannot make it fit`，按 Esc 兩次以回到添加大型內容的回合之前，或執行 `/clear` 以重新開始
* 否則，執行 `/compact`，它會刪除累積的影像和附加檔案
* 按路徑參考大型檔案而不是貼上其內容，以便 Claude 可以分塊讀取它們
* 對於影像，請參閱下面的 [Image was too large](#image-was-too-large)

### Image was too large

貼上或附加的影像超過了 API 的大小或尺寸限制。

```text theme={null}
Image was too large. Double press esc to go back and try again with a smaller image.
API Error: 400 ... image dimensions exceed max allowed size
API Error: an image in the conversation could not be processed and was removed.
```

`could not be processed and was removed` 這一行表示 API 拒絕了對話中的某張圖片，例如超過大小或尺寸上限的圖片。

若其中某個錯誤持續出現，請更新 Claude Code。在較舊的版本中，圖片錯誤可能因下列原因重複出現：

* 在 v2.1.299 之前，在含有許多圖片的長對話中，Claude Code 可能會移除您最後附加的圖片，而非超過上限的那張。接著 `was removed` 這一行會在每個回合重複出現，且 Claude 看不到您的新圖片。
* 在 v2.1.299 之前，在 VS Code、Desktop 應用程式和 Agent SDK 中，您在 Claude 工作期間附加的圖片不會像其他附加圖片一樣經過縮放。它們以原始大小送達 API，導致長對話中重複出現圖片錯誤。
* 在 v2.1.166 之前，貼上的圖片可能會留在對話中，導致之後的每則訊息都重複出現相同錯誤

**該怎麼辦：**

* 在貼上之前調整影像大小。API 接受單個影像最長邊最多 8000 像素的影像，或當上下文中有超過 20 張影像時最多 3000 像素。
* 拍攝相關區域的更緊密螢幕截圖，而不是整個螢幕

### Unable to resize image

Claude Code 無法在將附加影像發送到 API 之前將其縮小。

```text theme={null}
Unable to resize image — image processing is unavailable and dimensions could not be read from the file header. Please convert the image to PNG, JPEG, GIF, or WebP.
Unable to resize image — dimensions exceed the 2000x2000px limit and image processing failed. Please resize the image to reduce its pixel dimensions.
Unable to resize image (… raw, … base64). The image exceeds the … API limit and compression failed. Please resize the image manually or use a smaller image.
Unable to resize image — could not verify image dimensions are within the 2000x2000px API limit.
Unable to resize image — it is a CMYK JPEG, which Claude Code cannot decode, and at …px it is over the 2000x2000px limit, so it cannot be sent. Re-save it as an RGB PNG or JPEG and try again.
Unable to resize image — it is an animated WebP whose first frame Claude Code cannot decode, and at …px it is over the 2000x2000px limit, so it cannot be sent. Save its first frame as a PNG or JPEG and try again.
Unable to resize image — its pixels could not be decoded (the file may be damaged, or use an encoding Claude Code cannot read), and it is over the … API limit (… raw, … base64), so it cannot be sent. Re-save it as a PNG or JPEG and try again.
```

Claude Code 通常會自動調整大型影像的大小。這些錯誤意味著影像無法解碼或調整大小以符合 API 限制。

**該怎麼辦：**

* 如果訊息要求您轉換影像，請將其轉換為 PNG、JPEG、GIF 或 WebP 並再次附加。Claude Code 可以從檔案標頭驗證這些格式的尺寸，而無需解碼影像。
* 如果訊息報告尺寸或大小限制，請在附加之前將影像調整大小或重新壓縮到該限制以下。
* 如果訊息命名原因（例如 CMYK JPEG、動畫 WebP 或可能損壞的檔案），請以訊息建議的格式重新保存影像並再次附加。

### Request rejected as unprocessable by the model

API 拒絕了該請求，認為模型無法處理。此訊息來自 API 本身。

```text theme={null}
API Error: 400 Request rejected as unprocessable by the model (too many or oversized images, or unsupported parameters)
```

Claude Code 可以從被拒絕的請求中移除最舊的圖片和文件，然後重新傳送。在 v2.1.290 之前，Claude Code 遇到此拒絕時不會移除圖片，因此累積了數百張圖片的長時間工作階段可能每個回合都會以此錯誤失敗。

**處理方式：**

* 如果此訊息在含有圖片或文件的對話中持續出現，請自行將其移除。按兩次 Esc 回到加入它們的回合之前，或執行 `/clear` 重新開始。

### PDF 錯誤

您附加的 PDF 無法處理。訊息在此以非互動形式顯示；在互動式工作階段中，它們會提示您按 Esc 兩次並重試。

```text theme={null}
PDF too large (max 100 pages, 20MB). Try reading the file a different way (e.g., extract text with pdftotext).
PDF is password protected. Try using a CLI tool to extract or convert the PDF.
The PDF file was not valid. Try converting it to text first (e.g., pdftotext).
```

**該怎麼辦：**

* 對於超大 PDF，要求 Claude 使用 Read 工具讀取頁面範圍而不是附加整個檔案，或使用 `pdftotext` 之類的工具提取文字並按路徑參考輸出檔案
* 對於受保護或無效的 PDF，移除密碼或從其來源應用程式重新匯出檔案，然後重試

當 Claude 使用 Read 工具從 PDF 讀取頁面範圍時，讀取可能因不同訊息而失敗：

```text theme={null}
pdftoppm is not installed. Install poppler-utils (e.g. `brew install poppler` or `apt-get install poppler-utils`) to enable PDF page rendering.
```

頁面範圍讀取使用 `pdftoppm` 呈現頁面。使用訊息提供的命令安裝 poppler-utils，或在其他平台上安裝將 `pdftoppm` 放在您的 `PATH` 上的 poppler 建置。請參閱[Read 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#read-tool-behavior)以了解哪些 PDF 按頁面範圍讀取。

### Extra inputs are not permitted

接收請求的端點將請求中的某個欄位視為其不接受的輸入而拒絕，且端點的訊息會指出該欄位。

```text theme={null}
API Error: 400 ... context_management: Extra inputs are not permitted
```

Claude Code 會傳送僅限 beta 的欄位，例如 `context_management` 和工具搜尋的 `defer_loading`，並一同傳送啟用它們的 `anthropic-beta` 標頭。當閘道轉送主體但捨棄了標頭時，API 會看到它無法辨識的欄位。當閘道將 Anthropic 格式的主體轉送至具有不同 schema 的上游時，該上游會拒絕這類欄位。[Beta 標頭與主體欄位配對](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#beta-header-and-body-field-pairs)涵蓋了這兩種情況。

**該怎麼辦：**

* 如果訊息包含 `context_management: Extra inputs are not permitted`，請[更新 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code) 至 v2.1.304 或更新版本。更新後，Claude Code 會在遇到此拒絕時，不帶該欄位再傳送一次請求。在 v2.1.304 之前，Claude Code 不會針對此拒絕進行重試。
* 若訊息列出 `defer_loading` 或 `tool_reference`，請將 [Claude Code 更新](https://code.claude.com/docs/zh-TW/setup.md#update-claude-code)至 v2.1.305 或更新版本。之後 Claude Code 會在遇到此拒絕時，[移除工具搜尋欄位後再傳送一次請求](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#retry-without-tool-search)。
* 如果您的閘道捨棄了標頭，請將其設定為轉送 `anthropic-beta` 標頭。如需閘道必須轉送的內容，請參閱[功能傳遞](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through)。
* 作為備援，在啟動前設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](https://code.claude.com/docs/zh-TW/env-vars)。[禁用預發行功能](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#disable-pre-release-capabilities)涵蓋確切範圍。

在 v2.1.302 之前，即使不涉及閘道，此錯誤也可能列出欄位 `diagnostics`。當已使用 Anthropic API 的工作階段在未重新啟動的情況下移至 Amazon Bedrock 或 Google Cloud's Agent Platform 時，就會出現此錯誤。例如，當您在另一個 Claude Code 視窗中執行 [`/setup-bedrock`](https://code.claude.com/docs/zh-TW/commands) 時，您保持開啟的工作階段會移至 Bedrock。在這些版本中，請在該工作階段中執行 `/clear` 或重新啟動它。

### 工具輸入 schema 無效

請求中的工具聲明了 `input_schema`，該 schema 未通過 API 的 JSON Schema 驗證，因此 API 拒絕了整個請求。`tools.` 後面的數字是失敗工具在請求的工具列表中的位置，而不是您可以查找的名稱。

```text theme={null}
API Error: 400 ... tools.N.custom.input_schema: JSON schema is invalid
API Error: 400 ... tools.N.custom.input_schema.properties: Property keys should match pattern '^[a-zA-Z0-9_.-]{1,64}$'
```

第一種形式意味著 schema 不是有效的 JSON Schema draft 2020-12。第二種意味著頂級屬性名稱與訊息引用的模式不匹配。

Claude Code [在載入伺服器的工具時排除輸入 schema 會失敗此驗證的 MCP 工具](https://code.claude.com/docs/zh-TW/mcp.md#tools-with-invalid-input-schemas)，因此請求通常永遠不會包含一個。

在[旗標擷取關閉的部署](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)上，或在旗標從未到達的機器上，Claude Code 在伺服器的日誌中記錄哪個工具會被拒絕，但無論如何都會發送它，因此此錯誤仍然可能發生。

該錯誤也可能發生在工具的 schema 在 `$schema` 中聲明 JSON Schema 方言而不是 draft 2020-12 的情況下。Claude Code 不會根據 JSON Schema 元 schema 檢查這些 schema，儘管頂級屬性名稱檢查仍然適用。

在 v2.1.216 之前，沒有部署執行排除檢查。

**該怎麼辦：**

* 如果您的 Claude Code 版本早於 v2.1.300，請在 shell 中執行 [`claude update`](https://code.claude.com/docs/zh-TW/setup#update-claude-code)。在 v2.1.300 之前，Claude Code 不會[在移除被拒絕工具的參數後重試請求](https://code.claude.com/docs/zh-TW/mcp.md#tools-whose-input-schema-the-api-refuses)，因此此錯誤會在每個包含該工具的請求中重複出現。
* 移除或[禁用](https://code.claude.com/docs/zh-TW/mcp.md#disable-a-server-without-removing-it)聲明無效 schema 的 MCP 伺服器。該錯誤僅按位置命名工具。在 v2.1.216 或更高版本上，檢查每個伺服器的日誌以查找命名輸入 schema 會被拒絕的工具的行。如果沒有日誌命名一個，請一次禁用一個伺服器。
* 如果您維護伺服器，請修復工具的 `input_schema`。schema 必須是有效的 JSON Schema，頂級屬性名稱必須是 1 到 64 個字元長，並且只使用 ASCII 字母和數字、`_`、`.` 和 `-`。請參閱[輸入 schema 無效的工具](https://code.claude.com/docs/zh-TW/mcp.md#tools-with-invalid-input-schemas)。

### MCP 工具名稱超過 128 個字元

MCP 伺服器列出的工具完整名稱（例如 `mcp__<server>__<tool>`）超過 API 接受的 128 個字元。Claude Code [會將該工具排除在傳送給 Claude 的工具之外](https://code.claude.com/docs/zh-TW/mcp.md#tools-with-names-longer-than-128-characters)，而該伺服器的其他工具仍可正常運作。在您從 shell 以 `claude --debug` 啟動的工作階段中，Claude Code 會將此訊息寫入位於 `~/.claude/debug/<session-id>.txt` 的偵錯日誌：

```text theme={null}
Tool "mcp__<server>__<tool>" is not sent to Claude: its name has <N> characters and the API accepts at most 128
```

**該怎麼辦：**

* 如果您維護該伺服器，請縮短工具的名稱。
* 如果該伺服器位於您的 [MCP 設定](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)中，請在該處為其指定較短的名稱，例如以 `db` 取代 `analytics-database`。然後更新以舊名稱參照該伺服器或其工具的項目，例如[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#mcp)和 [hook matcher](https://code.claude.com/docs/zh-TW/hooks.md#match-mcp-tools)。
* 如果[外掛捆綁了該伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，工具的完整名稱也會包含外掛名稱。請要求外掛的維護者縮短伺服器或工具名稱。

在 v2.1.292 之前，Claude Code 仍會傳送該工具，而 API 會以 `API Error: 400 ... tools.N.custom.name: String should have at most 128 characters` 拒絕包含它的每個請求。

### tool\_use.name 超過 200 個字元

對話記錄中的工具呼叫攜帶的名稱長度超過 API 在請求中接受的 200 個字元：

```text theme={null}
API Error: 400 ... tool_use.name: String should have at most 200 characters
```

Claude Code 在回應到達時以及載入已保存的對話時將此類名稱切割為 200 個字元，因此呼叫失敗並出現 [`No such tool available`](#no-such-tool-available) 工具錯誤，對話繼續而不出現此 API 錯誤。

**該怎麼辦：**

* 執行 `claude update`，然後繼續對話。更新的版本在載入逐字稿時修復超長名稱，因此卡住的對話再次工作。

在 v2.1.281 之前，超長名稱保留在對話記錄中，API 拒絕了重新發送對話的每個請求，包括 `/compact` 和 `--resume`，因此此錯誤重複出現，對話被卡住。

### There's an issue with the selected model

設定的模型名稱未被識別，或您的帳戶缺少對其的存取權限。從 v2.1.160 開始，尾部提示（此處以其互動形式顯示）因使用介面而異。

```text theme={null}
There's an issue with the selected model (claude-...). It may not exist or you may not have access to it. Run /model to pick a different model.
```

**該怎麼辦：**

* **互動式 CLI**：執行 `/model` 以從您帳戶可用的模型中選擇。
* **非互動模式 (`-p`)**：使用有效的別名或 ID 傳遞 `--model`，或設定 [`ANTHROPIC_MODEL`](https://code.claude.com/docs/zh-TW/env-vars)。錯誤文字在此使用介面上顯示 `Run --model`。
* **Agent SDK**：錯誤文字省略提示，因為模型是以程式設計方式設定的。在 TypeScript 中的 [`Options` 上設定 `model`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)，或在 Python 中設定 [`ClaudeAgentOptions(model=...)`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions)，並處理結構化的 `model_not_found` 錯誤以顯示您自己的重試或模型選擇器。
* 使用別名（例如 `sonnet` 或 `opus`）而不是完整的版本化 ID。別名解析為維護的預設值，因此它們不會過時。請參閱[模型設定](https://code.claude.com/docs/zh-TW/model-config.md)。
* 如果錯誤的模型在 CLI 中不斷出現，則某處設定了過時的 ID。按[優先順序](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)檢查您可以設定模型的位置，並移除過時的值。
* Claude Code 將過期的 claude.ai 登入報告為 [Login expired](#login-expired)，而不是此錯誤。在 v2.1.206 之前，無法再刷新的過期登入對每個模型都失敗，並出現此錯誤；如果您在較舊版本上看到此錯誤，請執行 `/login`。
* 若 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 指向 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，且每個模型都以此方式失敗，請檢查您的閘道及其上游是否接受[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#tool-search-through-a-gateway)欄位。根據預設，Claude Code 會傳送 `defer_loading` 工具欄位與 `tool_reference` 區塊，並附帶啟用它們的 `anthropic-beta` 標頭。在 v2.1.304 之前，除非您以 `ENABLE_TOOL_SEARCH` 開啟，否則在閘道後方的工具搜尋為關閉狀態。
* 對於 Google Cloud 的 Agent Platform 部署，請參閱 [Google Cloud 的 Agent Platform 疑難排解](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#troubleshooting)。

### Model is not a recognized model id

您傳遞給模型切換的字串不是 Claude Code 可以用作模型的字串，因此它拒絕了切換而不發送請求，工作階段保留其目前模型。當模型通過 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) `setModel()` 方法設定時，您可能會收到此錯誤，由為您執行 Claude Code CLI 的應用程式（例如[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)），或當您從通過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連接的裝置選擇模型時。在 v2.1.200 之前，Claude Code 保存了字串並在下一個請求時因 [There's an issue with the selected model](#theres-an-issue-with-the-selected-model) 而失敗。

```text theme={null}
Model "Sonnet5" is not a recognized model id. Did you mean 'claude-sonnet-5'?
```

在此範例中，應用程式發送了顯示名稱 `Sonnet 5`，訊息重複時沒有其空格。尾部提示命名最接近的匹配別名或模型 ID。當沒有足夠接近的內容時，它讀取 `Run /model to see available models.` 代替。在[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)為您啟動的工作階段中，無匹配提示讀取 `Switch to a different model.`

當您通過 Agent SDK 或在 Anthropic API 上的應用程式切換時，只有無法成為模型 ID 的字串（例如顯示名稱或空字串）會收到此錯誤。

當您從 Remote Control 裝置選擇模型時，Claude Code 在本地檢查字串。任何不是模型別名、Claude Code 列出或您設定的模型，或以 `claude-` 開頭的 ID 的字串都會收到此錯誤，包括拼寫錯誤的 ID（例如 `claud-sonnet-5`）。在 v2.1.260 之前，此檢查不涵蓋 Remote Control 選擇，因此無法識別的字串被應用，並在下一個請求時失敗。

**該怎麼辦：**

* 執行 `/model` 而不帶引數以開啟選擇器並從您帳戶可用的模型中選擇，然後傳遞那裡顯示的別名或 ID
* 如果您使用了較新 Claude Code 版本支援的別名，請執行 `claude update`，或傳遞模型的完整 ID 代替。伺服器仍然可以要求該模型的最低 Claude Code 版本；請參閱 [Claude Code does not support this model](#claude-code-does-not-support-this-model)。
* v2.1.200 之前保存的模型不會被此檢查修復。如果過時的值不斷出現，請從[設定您的模型](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)下列出的位置移除它。
* 在 Anthropic API 以外的任何提供者上，或在閘道或自訂 `ANTHROPIC_BASE_URL` 後面，只有空字串會收到此錯誤。Claude Code 仍然可以在請求時寫入[無法識別的模型診斷行](#unrecognized-model-id-on-a-request)，在每個提供者上。

### Model not found

您使用名稱切換到模型，Claude Code 無法確認存在具有該名稱的模型。當名稱不是[模型別名](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)或 Claude Code 在本地接受的其他拼寫時，Claude Code 使用最小 API 請求驗證它，此錯誤通常是您的 API 端點的答案。使用 `/model <name>` 時，無法成為模型 ID 的名稱（例如包含空格的名稱）會收到相同訊息。

```text theme={null}
Model 'claude-opus-9' not found
```

在具有提供者特定模型 ID 的提供者上，訊息可能會添加 `Try '...' instead` 建議，該建議命名您提供者的備援模型 ID。

**該怎麼辦：**

* 執行 `/model` 而不帶引數並從您帳戶可用的模型中選擇，或使用[模型別名](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)（例如 `sonnet`），該別名解析為維護的預設值
* 如果您輸入了完整 ID，請根據您提供者的模型目錄檢查它。新推出的模型可能在 Anthropic API 上可用，然後您的提供者或地區才提供它。
* 在 Agent SDK 中，`setModel()` 因此訊息而失敗，工作階段在其先前的模型上繼續執行。在 TypeScript SDK 中，呼叫 [`supportedModels()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object) 以列出您可以切換到的模型。
* 在 v2.1.265 之前，`/model` 也以此錯誤拒絕了 `opusplan[1m]` 別名拼寫。在這些版本上，更新 Claude Code，或在[設定](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)中或使用 `--model` 代替設定模型。

### Couldn't confirm model with the API

您透過 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) 的 `setModel()` 方法或替您執行 Claude Code CLI 的應用程式（例如 [Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)）切換模型，而向您的 API 端點確認模型 ID 的請求在 15 秒內未收到回應。工作階段會保留目前的模型。

```text theme={null}
Couldn't confirm model "claude-sonnet-5" with the API. Try again, or run /model to see available models.
```

在[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)為您啟動的工作階段中，訊息在 `Try again.` 結尾。

**該怎麼辦：**

* 再次切換到模型
* 如果切換不斷失敗，請檢查 Claude Code 是否可以到達您的 API 端點；請參閱[網路和連接錯誤](#network-and-connection-errors)

### 檢查選定模型時出現 API 錯誤

您使用 `/model <name>` 選擇了模型，或連接到工作階段的應用程式請求了切換。API 拒絕了 Claude Code 發送以驗證模型的最小請求，原因沒有自己的條目，例如速率限制或伺服器錯誤。工作階段保留其目前模型，訊息以說明這一點結尾：

```text theme={null}
API error: 429 <the server's explanation> · model not changed
```

訊息的中間是 HTTP 狀態和伺服器自己的解釋。

**該怎麼辦：**

* 根據伺服器的解釋採取行動；對於速率限制或 5xx 狀態，等待並再次選擇模型
* 具有自己措辭的拒絕由周圍條目涵蓋，例如 [Model not found](#model-not-found) 和 [Model is restricted by your organization's settings](#model-is-restricted-by-your-organizations-settings)

### Claude Opus is not available with the Claude Pro plan

您的有效訂閱計畫不包括您選擇的模型。

```text theme={null}
Claude Opus is not available with the Claude Pro plan. If you have updated your subscription plan recently, run /logout and /login for the plan to take effect.
```

在 Claude 桌面應用程式執行的工作階段中，訊息說改為 `sign out and sign in again` 而不是命名命令。

**該怎麼辦：**

* 執行 `/model` 並選擇您的計畫包括的模型
* 如果您最近升級了計畫但仍然看到此訊息，請執行 `/logout` 然後 `/login`。儲存的 token 反映您登入時的計畫，因此在現有工作階段中在 claude.ai 上升級不會生效，直到您重新驗證。
* 請參閱 [claude.com/pricing](https://claude.com/pricing) 以了解每個計畫包括哪些模型

### Claude Code does not support this model

API 因為您的 Claude Code 版本低於所需的最低版本而拒絕了請求，並返回 400。您選擇的模型需要較新版本（伺服器按模型檢查），或您組織的政策需要一個。400 攜帶錯誤代碼 `claude_code_version_too_old`，訊息說明適用的最低版本。

```text theme={null}
API Error: 400 Claude Code 2.1.219 does not support this model; version 2.1.255 or newer is required. Run 'claude update', or update the Claude desktop app, then try again.
```

組織政策措辭讀取為：

```text theme={null}
API Error: 400 Claude Code 2.1.240 is older than the minimum version required by your organization's policy. Run 'claude update', or update the Claude desktop app, to continue.
```

發送請求的 Claude Code 二進位檔案報告的版本是 API 檢查的版本。

**該怎麼辦：**

更新該二進位檔案，然後啟動新工作階段。二進位檔案的來源決定了如何，除了在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#pin-the-version)中：

| 發送請求的二進位檔案 | 如何更新它 |
| :- | :- |
| 您安裝的 Claude Code | 執行 `claude update` |
| Claude 桌面應用程式 | 更新應用程式 |
| [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)組合的二進位檔案 | 更新擴充功能 |
| Agent SDK 套件組合的二進位檔案 | [升級 SDK 套件](https://code.claude.com/docs/zh-TW/agent-sdk/hosting.md#runtime-dependencies)，然後重新啟動您的應用程式。在[編譯的單檔案可執行檔](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#compile-to-a-single-executable)中，重建它 |

* 如果您在[穩定版發布通道](https://code.claude.com/docs/zh-TW/setup.md#configure-release-channel)上執行 `claude update`，它不會讓您超過最新的穩定版本，而該版本仍可能低於所需的最低版本。請切換到最新版通道，然後再次更新。如果您的組織透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)固定您的通道或版本，請要求您的管理員變更它
* 對於按模型措辭，您可以通過切換到另一個模型來在目前工作階段中繼續工作：在 CLI 中執行 `/model`，在 TypeScript SDK 的 `Query` 物件上呼叫 [`setModel()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object)（在串流輸入模式中），或在 Python SDK 的 `ClaudeSDKClient` 上呼叫 [`set_model()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient)
* 對於組織政策措辭，在繼續之前更新

### Model is restricted by your organization's settings

您的組織管理員在 claude.ai 管理控制台中禁用了此模型，或受管設定通過 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單或 [`deniedModels`](https://code.claude.com/docs/zh-TW/model-config#block-specific-models-or-versions) 清單排除了它。當 `--model`、`ANTHROPIC_MODEL` 或 `model` 設定命名受限制的模型時，通知在啟動時出現，並命名工作階段改為使用的模型。如果受管設定沒有為工作階段留下允許的模型，請參閱[受管設定阻止預設模型](#managed-settings-block-the-default-model)。替換通知也可能在工作階段中期出現，在管理員在 claude.ai 管理控制台中禁用工作階段執行的模型之後。

```text theme={null}
Model "claude-opus-4-8" is restricted by your organization's settings. Using claude-sonnet-4-6 instead.
```

為受限制的模型輸入 `/model <name>` 會被拒絕，工作階段保留其目前模型。對於在管理控制台中禁用的模型，拒絕讀取 `Model '<name>' is restricted by your organization's settings. Run /model to choose a different model.` 對於受管設定排除的模型，它讀取 `Model '<name>' is not available. Your organization restricts model selection.`

前綴為 agent、skill 或命令名稱的通知意味著限制適用於該 [subagent 的請求模型](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)：subagent 在替換模型上執行，您的工作階段模型保持不變。在 v2.1.223 之前，Claude Code 僅對使用 Agent 工具啟動的 subagent 顯示通知。

Claude Code 將模型系列別名（`opus`、`sonnet`、`haiku` 或 `fable` 之一）視為對該系列的請求，而不是對其最新版本的請求。在 Anthropic API 和[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上，受限制的系列別名解析為您組織的設定允許的系列的最新版本，替換通知命名該版本。Claude Code 僅當系列的每個版本都受限制時才拒絕 `/model <alias>`。在 v2.1.205 之前，系列別名基於其最新版本單獨被替換或拒絕，即使允許同一系列的較舊版本。

**該怎麼辦：**

* 執行 `/model` 以從您組織允許的模型中選擇。受限制的模型在選擇器中隱藏。
* 如果受限制的模型是在 `--model`、`ANTHROPIC_MODEL`、設定檔的 `model` 欄位或 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)、skill 或命令的 `model` frontmatter 中設定的，請移除或更新該值，以便通知不會再次出現
* 如果您需要存取受限制的模型，請要求您的組織管理員啟用它。請參閱[組織模型限制](https://code.claude.com/docs/zh-TW/model-config.md#organization-model-restrictions)。

### Can't switch to the default model

您選擇了預設模型，例如通過在 `/model` 選擇器中選擇預設行或輸入 `/model default`。Claude Code 拒絕了切換，因此工作階段保留其目前模型。

```text theme={null}
Can't switch to the default model: your organization's managed settings block it (claude-opus-4-6) in "deniedModels", and none of the models they allow can be used as the default instead. Ask your administrator to update "deniedModels" or "availableModels".
```

冒號後的措辭命名阻止切換的內容：

* **`your organization's managed settings block it ... in "deniedModels"`**：受管拒絕清單阻止預設選項解析為的模型
* **`your organization allows only the models listed in "availableModels"`**：受管 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單，其中 [`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch) 設定為 `"exact"` 遺漏了預設選項解析為的模型
* **`Claude Code couldn't read your organization's managed settings to check which models they allow`**：[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)無法讀取，Claude Code 拒絕切換而不是應用未檢查的切換

**該怎麼辦：**

* 對於 [`deniedModels`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmodels) 和 `availableModels` 措辭，執行 `/model` 並按名稱選擇您的組織允許的模型
* 要求您的管理員更新訊息命名的受管設定
* 對於 `couldn't read` 措辭，重新啟動 Claude Code；如果它繼續發生，要求您的管理員檢查受管設定

如果工作階段改為因這些受管設定而無法啟動，並出現 `Claude Code can't start` 訊息，請參閱[受管設定阻止預設模型](#managed-settings-block-the-default-model)。

### Model switch was blocked by a PreModelSwitch hook

[PreModelSwitch hook](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch) 沒有核准您或用戶端請求的模型切換，因此工作階段保留其目前模型。當切換來自 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 主機或 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 而不是您輸入的命令時，訊息讀取 `Model switch blocked by a PreModelSwitch hook` 而不命名目標模型。

```text theme={null}
Model switch to Opus 4.6 was blocked by a PreModelSwitch hook: Opus 4.6 is retired for this project. Use a newer model.
```

冒號後的原因說明拒絕切換的原因：

* **hook 寫入的原因**：PreModelSwitch hook 在[拒絕切換或要求確認](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch-decision-control)時提供了該原因。解決它要求的內容，或選擇您的 hook 允許的模型。
* **`PreModelSwitch hook <name> did not respond before its timeout`**：在其[逾時](https://code.claude.com/docs/zh-TW/hooks.md#timeouts)之前沒有回答的 hook 會阻止切換。修復掛起的命令或提高該 hook 的 `timeout`，然後再次切換。
* **`confirmation required, and this session cannot ask`**：hook 回答了 `ask` 而沒有原因，控制請求無法顯示確認提示。[`-p` 執行](https://code.claude.com/docs/zh-TW/headless)中的 `/model` 命令以 `(run /model interactively to confirm)` 報告相同狀況在原因之後。從互動式工作階段進行切換，或更改 hook 對此模型的決定。
* **`so organization-managed PreModelSwitch hooks could not be checked`**：Claude Code 無法判斷您組織的[受管外掛](https://code.claude.com/docs/zh-TW/settings-reference.md#enabledplugins)提供哪些 PreModelSwitch hook，例如因為受管外掛無法載入。其中一個 hook 可能會阻止切換，因此 Claude Code 拒絕而不是應用未檢查的切換。原因的開始命名失敗的內容。Claude Code 在每次切換嘗試時重新檢查，因此已清除的失敗停止阻止；如果它繼續失敗，請執行 `claude --debug` 並再次切換以捕獲詳細資訊，然後修復外掛或要求您的管理員修復它。
* **`a PreModelSwitch hook failed before answering`** 或 **`PreModelSwitch hooks were cancelled (the control stream closed) before answering`**：hook 執行在沒有判決的情況下結束，Claude Code 不將其視為核准。執行 `claude --debug` 以查看失敗的內容，然後再次切換。

在 v2.1.260 之前，受管外掛拒絕讀取 `plugin hooks could not be loaded, so PreModelSwitch hooks could not be checked; see the debug log`。Claude Code 重試外掛載入一次，然後在工作階段中拒絕後續切換，即使您的組織沒有受管外掛。在這些版本上重新啟動工作階段以再次執行外掛載入。

### Couldn't save it as your default

您選擇了模型以保存為預設值，例如使用 `/model <name>` 或 `/model` 選擇器中的 `Enter`，Claude Code 無法將選擇寫入您的使用者設定檔 `~/.claude/settings.json`。切換本身已應用，因此目前工作階段在您選擇的模型上執行，但您的預設值保持不變，下一個工作階段在舊值上啟動。

```text theme={null}
Set model to Fable 5.1 for this session only · couldn't save it as your default: ~/.claude/settings.json can't be written (EROFS)
```

檔案路徑後的原因說明失敗的內容：

* **`can't be written (<code>)`**：寫入因作業系統錯誤代碼（括號中）失敗，例如當檔案或它連結到的檔案位於拒絕寫入的檔案系統上時的 `EROFS`。使檔案可寫入並再次切換。如果另一個工具生成檔案，請在該工具中設定 `model` 鍵；請參閱[您在 Claude Code 中所做的變更在新工作階段中丟失](https://code.claude.com/docs/zh-TW/settings.md#a-change-you-made-in-claude-code-is-lost-in-new-sessions)。
* **`isn't valid JSON`**：磁碟上的檔案不解析，Claude Code 保持不動而不是覆蓋它無法讀回的內容。修復語法錯誤，然後再次切換；請參閱[修復損壞的設定檔](https://code.claude.com/docs/zh-TW/settings.md#fix-a-broken-settings-file)。

以 `couldn't confirm it was saved as your default (~/.claude/settings.json is still being written)` 結尾的通知意味著寫入在三秒後未完成。它在背景中繼續，因此預設值仍然可能被保存；檢查您的下一個工作階段啟動的模型，或再次執行 `/model <name>`。

在 v2.1.265 之前，通知說模型是 `saved as your default for new sessions` 即使寫入失敗。

### Advisor is less capable than the current main model

您的 [advisor 模型](https://code.claude.com/docs/zh-TW/advisor.md)排名低於工作階段的主要模型，因此 Claude Code 會保留該選擇，但不會將 advisor 附加到主要模型的請求。

```text theme={null}
Advisor set to Opus 4.8
Note: Opus 4.8 is less capable than the current main model (Sonnet 5.5), so the advisor will not activate. Choose a more capable advisor, or switch to a smaller main model.
```

其他訊息也會報告相同狀況：

* 在互動式工作階段中，通知讀取 `Advisor will not activate on the main model (advisor is less capable); subagents may still use it and may use more tokens · /advisor`。
* 當您在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中以 `--advisor` 旗標啟動，且該執行不是[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)時，警告會輸出至 stderr，而執行仍會開始。警告內容為 `"<advisor>" cannot advise "<main model>" (the advisor must be at least as capable as the main model). The advisor will not be used for the main model.`。互動式工作階段只會將該警告寫入[偵錯日誌](#configuration-warnings)。

**該怎麼辦：**

* 選擇排名較高的 advisor 或排名較低的主要模型。[選擇 advisor 模型](https://code.claude.com/docs/zh-TW/advisor.md#choose-an-advisor-model)顯示排名，並列出每個主要模型可接受的 advisor。
* 如果您希望該 advisor 能為其模型提供建議的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 繼續使用它，請保留 advisor 設定

在 v2.1.287 之前，Claude Code 對數種配對的排名不同。它會對搭配 Opus 4.7 或 Opus 4.8 主要模型的 Sonnet 5.5 advisor 顯示此提示，而它現在接受這種配對。它也會附加某些現在會產生此提示的 advisor，例如搭配 Sonnet 5.5 主要模型的 Opus 4.8 advisor。

### thinking.type.enabled is not supported for this model

您的 Claude Code 版本早於所選模型的最低版本。CLI 發送了模型不再接受的思考設定。

```text theme={null}
API Error: 400 ... "thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.
```

**該怎麼辦：**

* 執行 `claude update` 並重新啟動 Claude Code。Opus 4.7 需要 v2.1.111 或更高版本。Opus 4.8 需要 v2.1.154 或更高版本。Sonnet 5 需要 v2.1.197 或更高版本。Opus 5 需要 v2.1.219 或更高版本。Opus 5.5 需要 v2.1.280 或更高版本。Sonnet 5.5 需要 v2.1.284 或更高版本
* 在[穩定版發布通道](https://code.claude.com/docs/zh-TW/setup.md#configure-release-channel)上，更新不會讓您超過最新的穩定版本，而該版本仍可能早於這些版本。請切換到最新版通道，然後更新
* 如果您無法升級，請執行 `/model` 並改為選擇 Opus 4.6 或 Sonnet 4.6
* 如果您在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中遇到此問題，請改為升級 SDK 套件。Opus 4.8 需要 TypeScript SDK v0.3.154 或更高版本和 Python SDK v0.2.88 或更高版本。Sonnet 5 需要 TypeScript SDK v0.3.197 或更高版本。Opus 5 需要 TypeScript SDK v0.3.219 或更高版本。Opus 5.5 需要 TypeScript SDK v0.3.280 或更高版本。Sonnet 5.5 需要 TypeScript SDK v0.3.284 或更高版本

### Effort isn't available with thinking turned off

您關閉了[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)並以 `high` 以上的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)執行。模型不接受該組合，因此 API 拒絕了請求。

```text theme={null}
API Error: Effort 'xhigh' isn't available with thinking turned off on this model · run /effort high to continue, or turn thinking back on (unset MAX_THINKING_TOKENS=0)
```

`·` 後的提示因工作階段而異：在非互動式工作階段中，它讀取 `use --effort high (or the effortLevel setting)`，在 Claude 桌面應用程式執行的工作階段中，它讀取 `you can lower effort to High`。

**該怎麼辦：**

* [降低 effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#set-the-effort-level)至 `high` 或以下。
* 打開思考，例如通過取消設定 [`MAX_THINKING_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 或從您的設定中移除 [`"alwaysThinkingEnabled": false`](https://code.claude.com/docs/zh-TW/settings-reference#alwaysthinkingenabled)。

在 v2.1.242 之前，Claude Code 顯示 API 自己的訊息：`API Error: 400 output_config.effort 'xhigh' is not supported when thinking is disabled on this model. Use effort 'high' or below, or enable thinking.` 在 v2.1.251 之前，Claude Code 以您設定的 effort 等級發送請求，因此 Opus 5 拒絕了關閉思考時 `high` 以上的每個請求。Claude Code 現在改為向它知道拒絕該組合的模型（例如 Opus 5）發送 effort `high`。

### 思考預算超過輸出限制

設定的延伸思考預算超過最大回應長度，因此沒有空間留給實際答案。

```text theme={null}
API Error: 400 ... max_tokens must be greater than thinking.budget_tokens
```

**該怎麼辦：**

* 將 [`CLAUDE_CODE_MAX_OUTPUT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 提高到思考預算以上
* 請參閱[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)以了解預算如何與輸出長度互動

### Response exceeded the output token maximum

Claude 的回覆達到了請求所允許的最大輸出 token 數，並在該處被截斷：

```text theme={null}
API Error: Claude's response exceeded the ... output token maximum. To configure this behavior, set the CLAUDE_CODE_MAX_OUTPUT_TOKENS environment variable.
API Error: Claude's response exceeded the 64000 output token maximum for a request sent without streaming. The CLAUDE_CODE_MAX_OUTPUT_TOKENS environment variable cannot raise this limit.
```

列出 `a request sent without streaming` 的形式，表示某個串流請求失敗，而 Claude Code 以非串流方式重新送出，這會將回覆限制在 64,000 個輸出 token。在 v2.1.299 之前，在這類重新送出的請求中被截斷的回覆會結束該回合，且不顯示此訊息，就好像回覆已完成一樣。

**處理方式：**

* 若 Claude 在回覆被截斷之前已寫出部分文字，請在互動式工作階段中回覆 `continue` 以要求其餘內容。該文字會保留在對話中。
* 若訊息要求設定 `CLAUDE_CODE_MAX_OUTPUT_TOKENS`，請參閱 [`CLAUDE_CODE_MAX_OUTPUT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 了解該值的上限，並參閱[設定環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#set-environment-variables)了解設定位置
* 若要讓每則回覆都在上限之內，請要求 Claude 以較小的片段輸出，例如每則回覆一個檔案或一個章節

### 工具使用或思考區塊不匹配

對話記錄以不一致的狀態到達 API。

```text theme={null}
API Error: 400 due to tool use concurrency issues. Run /rewind to recover the conversation.
API Error: 400 orphaned tool_result in conversation history. Run /rewind to recover the conversation.
API Error: 400 duplicate tool_use ID in conversation history. Run /rewind to recover the conversation.
API Error: 400 ... unexpected `tool_use_id` found in `tool_result` blocks
API Error: 400 ... thinking blocks ... cannot be modified
```

所有變體意味著相同的事情：記錄中 `tool_use`、`tool_result` 和 `thinking` 區塊的序列不再與 API 期望的相符。

**該怎麼辦：**

* 如果您使用 Opus 4.7 或 Opus 4.8，請先執行 `claude update`。v2.1.156 之前的版本可以在正常工具使用期間觸發此錯誤，`/rewind` 不會清除它。
* 執行 `/rewind` 或按 Esc 兩次，以回到損壞回合之前的檢查點並從那裡繼續。請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)以了解檢查點如何建立和恢復。

### Invalid data in redacted\_thinking block

API 因為它無法接受對話記錄中較早回合攜帶的 `redacted_thinking` 區塊而拒絕了請求，並返回 400。

```text theme={null}
API Error: 400 ... Invalid `data` in `redacted_thinking` block
```

Claude Code 將對話的較早思考排除在請求之外並重試一次，因此工作階段繼續而不顯示錯誤。在 v2.1.282 之前，Claude Code 保留了被拒絕的區塊，每個後續回合都因相同錯誤而失敗。

**該怎麼辦：**

* 如果您在 v2.1.281 或更早版本上，每個回合都因此錯誤而失敗，請執行 `claude update` 並繼續工作階段
* 如果錯誤持續，請執行 `/clear` 以啟動不攜帶該區塊的對話

### Unsupported tool content removed

當 Claude Code 直接連接到 Anthropic API 並載入或預覽已保存的工作階段時，它會移除 Anthropic API 不接受的工具內容，並在移除的內容位於兩個思考區塊之間的位置留下此行：

```text theme={null}
[Unsupported tool content removed]
```

當 Anthropic API 以外的東西以 API 的格式回答時，此類內容會到達工作階段檔案，通常是通過 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 設定的第三方代理伺服器，它轉譯另一個提供者的工具呼叫。Claude Code 僅在工作階段直接連接到 Anthropic API 時移除它，並在工作階段通過代理伺服器或在另一個提供者上執行時按原樣載入已保存的記錄。在 v2.1.246 之前，Claude Code 將工具使用及其結果發送回 API，已繼續工作階段的每個回合都因 400 錯誤（例如 `messages.1.content.0.server_tool_use.name: Input should be 'web_search', 'web_fetch', ...`）而失敗。

**該怎麼辦：**

* 當您看到佔位符行時，無需採取任何行動。工作階段繼續而不包含移除的內容。
* 如果已繼續工作階段的每個回合都因 400 錯誤而失敗，請執行 `claude update` 並再次繼續工作階段。v2.1.246 之前的版本不會移除內容。

### role 'system' must precede an 'assistant' message

API 因為系統訊息位於它不接受的對話位置而拒絕了請求，並返回 400：

```text theme={null}
API Error: 400 messages.6: role 'system' must precede an 'assistant' message or end the array; ...
```

Claude Code 將其某些提醒和附加文字作為系統訊息在對話內發送。當 API 拒絕一個的位置時，Claude Code 重試請求一次，將該文字作為普通使用者訊息發送。API 的同級放置措辭（例如 `use the top-level 'system' parameter for the initial system prompt`）獲得相同的恢復。

當錯誤確實出現時，被拒絕的系統訊息不是 Claude Code 可以移除的。這通常意味著 Claude Code 和 API 之間的代理伺服器或 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)添加了自己的系統訊息。

**該怎麼辦：**

* 如果錯誤在通過 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 設定的代理伺服器或閘道後面的每個回合上重複，請連接而不使用代理伺服器以確認來源，並向操作它的人報告錯誤
* 執行 `/clear` 以啟動新對話。如果錯誤也在那裡返回，原因在請求路徑上，而不是在已保存的對話中。

在 v2.1.280 之前，Claude Code 沒有識別此措辭，因此當被拒絕的系統訊息是 Claude Code 本身發送的時，錯誤也出現，對話的每個後續回合都以相同方式失敗。

### Invalid encrypted\_content in search\_result block

API 因為對話記錄包含它無法解密的託管網路搜尋內容而拒絕了請求，並返回 400。措辭命名它無法讀取的欄位：

```text theme={null}
API Error: 400 ... Invalid `encrypted_content` in `search_result` block
API Error: 400 ... Invalid `encrypted_index` in `text` block
API Error: 400 ... Failed to decrypt web search result content
API Error: 400 ... Invalid `encrypted_stdout` in `encrypted_code_execution_result` block
```

來自 API 的託管[網路搜尋工具](https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool)的結果攜帶只有 API 可以讀取的加密欄位。`encrypted_stdout` 措辭命名讀取此類結果的託管程式碼執行程式的輸出，API 也會加密。API 拒絕重播它無法解密的內容的請求，例如為不同組織生成的內容。

Claude Code 自己的 [WebSearch 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)將搜尋結果記錄為純文字，因此這些區塊通常通過執行託管網路搜尋本身的代理伺服器或 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)到達對話。

對於三個網路搜尋措辭，Claude Code 將搜尋呼叫、結果和引用排除在它發送的內容之外並重試請求一次，因此工作階段繼續而不顯示錯誤。`encrypted_stdout` 措辭沒有此類恢復，因此該訊息仍然到達您。在 v2.1.282 之前，Claude Code 也保留了被拒絕的網路搜尋區塊，每個後續回合和 `/compact` 都因相同方式失敗。

**該怎麼辦：**

* 如果您在 v2.1.281 或更早版本上，每個回合都因其中一個網路搜尋措辭而失敗，請執行 `claude update` 並繼續工作階段
* 如果錯誤持續，或訊息命名 `encrypted_stdout`，請執行 `/rewind` 以回到添加內容的回合之前的檢查點，或執行 `/clear` 以啟動不攜帶它的對話
* 如果您在代理伺服器或閘道後面執行 Claude Code，請向操作它的人報告錯誤

### 使用政策拒絕

API 拒絕回應，因為對話中的內容觸發了[使用政策](https://www.anthropic.com/legal/aup)檢查。

如果訊息包含 `` Details: `[reasoning_extraction]` `` 這一行，請參閱[安全措施標記了要求提供 Claude 推理過程的請求](#safeguards-flagged-a-request-for-claudes-reasoning)。

訊息包括您可以引用給支援的請求 ID 和訊息 ID，如果您認為拒絕不正確。

```text theme={null}
API Error: Opus 4.6 can't help with this. Start a new session to continue.

Send feedback with /feedback or learn more: https://www.anthropic.com/legal/aup
```

訊息命名拒絕的模型，或當沒有記錄模型時命名 `Claude`。

檢查評估完整對話，而不僅是您的最新提示詞，因此在同一工作階段中發送新訊息通常會重新觸發相同的拒絕。使用 `--continue` 或 `--resume` 退出並重新開啟工作階段時也是如此，因為磁碟上的逐字稿仍然包含觸發內容。在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 和 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上，此訊息也涵蓋模型的安全措施標記為網路安全主題的請求。請參閱[安全措施標記了網路安全主題](#safety-measures-flagged-a-cybersecurity-topic)。

在 v2.1.219 之前，訊息讀取 `Claude Code is unable to respond to this request, which appears to violate our Usage Policy (https://www.anthropic.com/legal/aup). Please double press esc to edit your last message or start a new session for Claude Code to assist with a different task.`

**該怎麼辦：**

* 按 Esc 兩次或執行 `/rewind` 以回到觸發拒絕的回合之前的檢查點，然後重新措辭或採取不同的方法。請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)。
* 如果您無法識別哪個回合導致了它，請執行 `/clear` 以在同一專案中啟動新對話。您之前的對話保存在磁碟上，並在 `/resume` 中保持可用。
* 在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)(`-p`) 中，其中無法進行倒帶，請在沒有 `--continue` 的新工作階段中使用重新措辭的提示詞重試。政策檢查因模型而異，因此使用 `--model` 切換到不同的模型也可能在某些情況下解決拒絕。

### 安全措施標記了網路安全主題

模型的安全措施將對話中的內容標記為網路安全主題。訊息命名標記請求的模型：

```text theme={null}
API Error: Opus 4.8's safeguards flagged this message. Our intentionally broad safeguards allow us to deliver more capabilities faster, but can sometimes flag legitimate cybersecurity work. Send feedback with /feedback or learn more: https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude
```

如果訊息包含 `` Details: `[reasoning_extraction]` `` 這一行，請參閱[安全措施標記了要求提供 Claude 推理過程的請求](#safeguards-flagged-a-request-for-claudes-reasoning)。

此訊息連結到[網路安全驗證計畫](https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude)，該計畫為合法網路安全工作授予存取權限。具有[自動模型備援](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)的模型會印出不含此連結的不同訊息；在 Opus 5.5 和 Sonnet 5.5 上，該訊息以 `<model>'s safeguards flagged this session` 開頭。該章節也說明了 Claude Code 何時改為切換模型。

在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 和 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上，網路安全標記會產生[使用政策拒絕](#usage-policy-refusal)訊息。

**該怎麼辦：**

* 如果您的工作需要此內容，請通過[網路安全驗證計畫](https://support.claude.com/en/articles/14604842-real-time-cyber-safeguards-on-claude)申請存取權限
* 如果您的請求不是關於網路安全主題，請執行 `/feedback` 以報告誤報
* 若要在同一工作階段中繼續工作，請按 Esc 兩次或執行 `/rewind` 以回到觸發標記的回合之前的檢查點，然後採取不同的方法。請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)。

如果您看到的訊息措辭與下列其中之一相同，則為較早版本 Claude Code 上的相同旗標：

* 從 v2.1.219 到 v2.1.296，訊息也可能在結尾句之前包含 `Apply to the Cyber Verification Program to reduce these interruptions.`
* 從 v2.1.203 到 v2.1.218，訊息內容為 `<model> has safety measures that flagged this message for a cybersecurity topic. To learn about the Cyber Verification Program and apply for access, visit our help center:`，後接相同的說明中心連結。在互動式工作階段中，訊息會接著顯示 `If you were not engaging in a cybersecurity topic, please send feedback via /feedback.`
* 在 v2.1.203 之前，訊息內容為 `<model>'s safeguards flagged this message for a cybersecurity topic. If your work requires this access, you can apply for an exemption:`，後接豁免表單連結

### 安全措施標記了要求提供 Claude 推理過程的請求

API 拒絕了該請求，因為安全措施將其標記為要求模型在回應中重現其內部推理。API 將此[拒絕類別](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback#refusal-response)命名為 `reasoning_extraction`，拒絕訊息會包含這一行：

```text theme={null}
Details: `[reasoning_extraction]`
```

在 v2.1.234 之前，拒絕訊息不包含 `Details` 行。

**該怎麼辦：**

* 移除或改寫任何要求 Claude 逐字或以固定格式寫出其思考或推理的指示，例如 `<thinking>` 區段、草稿區段，或 JSON 輸出中的 `reasoning` 欄位。該指示可能位於您的提示詞中，或位於 Claude Code 隨之載入的自訂內容中，例如 CLAUDE.md、skill、subagent 提示詞、輸出風格或 MCP 工具描述。
* 若要檢查自訂內容是否為觸發原因，請在終端機中執行 [`claude --safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，以停用自訂內容的狀態啟動工作階段，然後發送相同的提示詞
* 變更自訂內容後，請啟動新的工作階段
* 若要改寫已發送的提示詞，請參閱[倒回並摘要](https://code.claude.com/docs/zh-TW/checkpointing.md#rewind-and-summarize)
* 您仍然可以要求 Claude 解釋其答案。請要求簡短的解釋、結果背後的依據，或其所採取動作的摘要。若要閱讀 Claude 思考的摘要，請參閱 [`showThinkingSummaries`](https://code.claude.com/docs/zh-TW/settings-reference#showthinkingsummaries)。
* 如需更多範例，以及改寫後的請求仍被拒絕時該怎麼辦，請參閱[將推理保留在思考區塊中](https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback#keep-reasoning-in-thinking-blocks)

### Output blocked by content filtering policy

API 的輸出內容篩選器停止了 Claude 正在產生的回應。訊息文字來自 API：

```text theme={null}
API Error: Output blocked by content filtering policy
```

**該怎麼辦：**

* 重新措辭您的最後一則訊息，或採取不同的方法
* 若要回到觸發封鎖的回合之前的檢查點，請按 Esc 兩次或執行 `/rewind`。請參閱[檢查點功能](https://code.claude.com/docs/zh-TW/checkpointing.md)

## 命令列錯誤

這些錯誤來自 `claude` 命令列及其子命令、您在輸入提示處提交的命令名稱，以及像 `/security-review` 這類會在其提示詞執行前先執行 shell 命令以收集脈絡的命令。它們也可能來自會重新啟動 CLI 的 `/tui`。

### `--bg` 與 `--print` 衝突

此訊息需要 Claude Code v2.1.198 或更新版本。您在同一次 `claude` 呼叫中將 `--bg` 與 `-p` 或 `--print` 合併使用。`--bg` 會啟動一個[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#from-your-shell)，您之後可以使用 `claude agents` 附加到該工作階段；而 `--print` 則以[非互動方式](https://code.claude.com/docs/zh-TW/headless.md)執行，永遠不會啟動 `claude agents` 所附加的互動式工作階段。在 v2.1.198 之前，此組合會默默建立一個永遠無法附加的背景工作。

```text theme={null}
--bg and --print conflict: --print never starts the interactive session that `claude agents` attaches to, so the job would be unattachable. The prompt is the positional — drop --print: `claude --bg '<task>'`.
```

**處理方式：**

* 移除 `-p` 或 `--print`。`--bg` 會將提示詞作為其位置引數，因此 `claude --bg "<task>"` 就是完整的命令。請參閱[從 shell 分派新的 agent](https://code.claude.com/docs/zh-TW/agent-view.md#from-your-shell)。
* 若要以非互動方式執行提示詞並列印結果，而不是建立背景工作階段，請移除 `--bg` 並執行 `claude -p "<task>"`

### Couldn't tell whether `--bg` is a flag or text

您執行 `claude` 時，將 `--bg` 或 `--background` 放在 Claude Code 無法判斷您是要將其作為背景旗標還是文字的位置。該命令沒有啟動任何東西，僅列印這一行，並以退出碼 1 結束：

```text theme={null}
Couldn't tell whether --bg is a flag or text here, so nothing was started. To start a background session put it first: claude --bg <prompt>
```

如果您輸入的是 `--background`，該行會改為列出 `--background`。

**處理方式：**

* 若要啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#from-your-shell)，請在 shell 中將旗標放在最前面再次執行命令：`claude --bg --name nightly-audit "<task>"`

### 系統提示詞旗標與其檔案形式衝突

您在同一次 `claude` 呼叫中同時傳入了 [`--append-subagent-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 與 `--append-subagent-system-prompt-file`，因此 `claude` 會以退出碼 1 結束，而不會啟動工作階段：

```text theme={null}
Error: Cannot use both --append-subagent-system-prompt and --append-subagent-system-prompt-file. Please use only one.
```

在 v2.1.283 之前，當您將 `--system-prompt` 與 `--system-prompt-file` 一起傳入，或將 `--append-system-prompt` 與 `--append-system-prompt-file` 一起傳入時，`claude` 也會以相同方式結束，因為這些成對的旗標會相互衝突，而不是[合併使用](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags)。在這些版本中，訊息會指出您合併使用的那一對旗標。

**處理方式：**

* 保留旗標的其中一種形式，並移除另一種。若要將固定的提示詞檔案與每次執行的文字結合，請在啟動前將文字合併到檔案中，而不是同時傳入兩個旗標

### 無效的 `--agents` 設定

您傳給 `--agents` 的值無效，因此 `claude` 會以退出碼 1 結束，而不會啟動工作階段。當您傳入 `--safe-mode` 或設定 [`CLAUDE_CODE_SAFE_MODE`](https://code.claude.com/docs/zh-TW/env-vars#variables) 時，Claude Code 會完全忽略 `--agents`。搭配 `--resume` 或 `--continue` 時，內嵌的 JSON 值不會被檢查，工作階段會照常啟動；從檔案讀取的值則會在每次啟動時檢查。在 v2.1.242 之前，Claude Code 仍會照樣啟動工作階段。

```text theme={null}
Error: Invalid --agents configuration:
<what failed>
```

第一行之後的內容取決於該值失敗的方式。Claude Code 會依序執行以下檢查，並在第一個失敗的檢查處停止。如果您的值有兩類問題，您要在修正第一類之後才會看到第二類：

1. 當值以 `{` 開頭但無法解析為 JSON，或 `--agents` 檔案的內容無法解析時，Claude Code 會列印一行 `invalid JSON:`，其中包含 JSON 剖析器本身的訊息
2. 當值可以解析，但某個 agent 定義不符合 [CLI 定義的 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope) 的 schema 時，Claude Code 會針對每個問題列印一行
3. 當 agent 名稱以 `-` 開頭時，Claude Code 會列印 `<name>: agent names must not start with '-'`

當問題行超過 20 行時，Claude Code 會列印前 20 行，並將其餘部分替換為 `…and N more`。

搭配 `--print` 時，`--agents` 也接受以[JSON 檔案的路徑](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)取代內嵌物件。在 v2.1.281 之前，`--agents` 只接受內嵌 JSON，並將檔案路徑視為無效的 JSON。檔案形式有其自己的拒絕訊息，會取代此訊息列印出來，包括以下幾種：

* **`Error: --agents takes a JSON object, or a file path only with --print (-p)`**：Claude Code 在互動式工作階段中將該值讀取為檔案路徑。請以內嵌 JSON 傳入定義，或加上 `-p` 以從檔案讀取。
* **`Error: --agents file not found: <path>`**：該路徑上沒有檔案。不以 `{` 開頭且不是有效 JSON 的值會被讀取為路徑，因此被 shell 弄亂的內嵌 JSON 也可能以此方式失敗。請檢查路徑或引號，然後再次執行命令。

**處理方式：**

* 修正訊息列出的每個問題，然後再次執行命令。請參閱 [CLI 定義的 subagent 所接受的欄位](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)。

### 無法從 `--restricted` 工作階段建立雲端工作階段

當您以 [`--restricted`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動工作階段時，Claude Code 會拒絕從中建立[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-terminal-to-cloud)，因為新的工作階段會在受限程序之外執行，而且不會強制執行受限模式。Claude Code 會在用戶端、聯絡伺服器之前就拒絕，因此不會建立任何雲端工作階段：

```text theme={null}
Cloud sessions cannot be created from a --restricted session: they would not enforce it.
```

**處理方式：**

* 在受限工作階段中於本機執行該任務
* 如果您能控制工作階段的啟動方式，請啟動一個不帶 `--restricted` 的新 `claude` 工作階段，並從那裡建立雲端工作階段

在 v2.1.248 之前，Claude Code 沒有 `--restricted` 旗標；較早的版本會以未知選項錯誤拒絕該旗標本身。

### 雲端工作階段已被您組織的政策停用

您組織的 `allow_remote_sessions` 政策已關閉，因此無法使用[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)以及使用它們的命令：

```text theme={null}
Cloud sessions are disabled by your organization's policy. Contact your organization admin to enable them.
```

此訊息會在您[從終端機建立雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-terminal-to-cloud)時出現，也會在您提交需要雲端工作階段的命令（例如 `/teleport`、`/remote-env` 或 `/web-setup`）時出現。在 v2.1.268 之前，提交這些命令之一會改為傳回 [`Unknown command`](#unknown-command)。

如果訊息改為指出此工作階段正在使用的某個憑證，並以 `Cloud sessions use your claude.ai login.` 結尾，請參閱 [Cloud sessions use your claude.ai login](#cloud-sessions-use-your-claude-ai-login)。如果 Claude Code 完全無法載入您組織的政策，您會看到[另一則訊息](#couldnt-verify-your-organizations-policy-for-cloud-sessions)。

**處理方式：**

* 請您組織中的 [Owner](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control) 在 [claude.ai/admin-settings/claude-code](https://claude.ai/admin-settings/claude-code) 的 Claude Code 管理設定中啟用雲端工作階段

### Cloud sessions use your claude.ai login

當[政策拒絕訊息](#cloud-sessions-are-disabled-by-your-organizations-policy)指出此工作階段正在使用的某個憑證並以這句話結尾時，表示 Claude Code 檢查的是核發該憑證之組織的雲端工作階段政策。該組織可能與您的 claude.ai 登入所屬的組織不同：

```text theme={null}
Cloud sessions are disabled by your organization's policy. This session is using ANTHROPIC_API_KEY, so Claude Code checked the policy for the organization that key belongs to. Cloud sessions use your claude.ai login.
```

最後一句話表示雲端工作階段是在您的 claude.ai 登入上執行，而不是在該憑證上執行。當您從 shell 啟動、恢復雲端工作階段或傳送訊息給雲端工作階段時（例如使用 `--cloud` 或 `--teleport`），就會出現此形式。在 v2.1.296 之前，Claude Code 在這種情況下也會輸出要求您聯絡組織管理員的形式。

### Couldn't verify your organization's policy for cloud sessions

這些訊息表示 Claude Code 無法載入您組織的政策，而它會在建立、恢復[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)或傳送訊息給雲端工作階段之前檢查該政策。當政策請求尚未完成時，訊息為：

```text theme={null}
Couldn't verify your organization's policy for cloud sessions. Check your network connection and try again.
```

在工作階段中，需要雲端工作階段的命令（例如 `/teleport` 或 `/web-setup`）也會顯示此訊息。即使在您的 shell 會輸出 `Cloud sessions aren't available:` 形式的情況下也是如此，且其第二句為 `Check your network connection, then restart Claude Code and try again.`

一旦政策請求失敗，訊息就會說明失敗的原因。這適用於您使用 `--cloud` 或 `--teleport` 等旗標從 shell 啟動、恢復雲端工作階段或傳送訊息給雲端工作階段的情況。在無法連到 API 時，訊息為：

```text theme={null}
Cloud sessions aren't available: couldn't reach api.anthropic.com to load your organization's policy. Check your network or proxy.
```

其他失敗會使用相同的開頭並附上各自的原因，例如代理伺服器以 HTTP 403 拒絕請求、伺服器錯誤，或 API 不接受的憑證。當 API 不接受此工作階段用來取代您 claude.ai 登入的憑證（例如 `ANTHROPIC_API_KEY` 環境變數）時，訊息也可能指出該憑證並要求您取消設定它：

```text theme={null}
Cloud sessions aren't available: api.anthropic.com didn't accept this session's credentials when Claude Code asked for your organization's policy. Cloud sessions use your claude.ai login. ANTHROPIC_API_KEY is set, so this session is using API-key auth — unset it (or run in a shell without it) to use cloud sessions.
```

在 v2.1.296 之前，這些失敗也會輸出 `Couldn't verify` 訊息。

**處理方式：**

* 對於 `Couldn't verify` 訊息，請檢查網路連線後再試一次。若在工作階段中，請先重新啟動 Claude Code
* 對於 `Cloud sessions aren't available:` 訊息，請依其原因採取對應措施，例如檢查代理伺服器或取消設定訊息指出的憑證，然後再次執行命令

### 由於資料夾取代了受追蹤的檔案，未暫存任何內容

此訊息表示您的檢出目錄中，現在有一個資料夾位於原本由 git 追蹤的檔案或連結所在的位置。當您將[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#from-cloud-to-terminal)拉取到終端機（例如使用 `claude --teleport` 或 `/teleport`）並選擇暫存（stash）選項之後，就會出現此訊息。暫存這種狀態可能會刪除資料夾內的檔案，因此 Claude Code 會拒絕暫存，並讓您的檢出目錄與索引保持不變：

```text wrap theme={null}
Error: Nothing was stashed: "f" is now a folder in place of a tracked file or link, and stashing could delete what's in it for good. Commit the change or move the folder somewhere else, then try again.
```

**處理方式：**

* 依照訊息所述，提交變更或將資料夾移到其他位置，然後再次執行 teleport

### `--json-schema` 的值不是有效的 JSON Schema

您在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md#get-structured-output)中傳給 [`--json-schema`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 的 schema 未能通過 JSON Schema 編譯，因此 `claude` 會以退出碼 1 結束，而不會執行提示詞。在 v2.1.205 之前，無效的 schema 會產生非結構化輸出且不報錯，而且任何使用 `format` 關鍵字的 schema 都會被視為無效。

```text theme={null}
Error: --json-schema is not a valid JSON Schema: data/type must be equal to one of the allowed values
```

第二個冒號之後的文字是驗證器的診斷訊息，會指出失敗的關鍵字或位置。使用 `format` 關鍵字的 schema（例如 `"format": "email"`）是有效的：Claude Code 將 `format` 視為註解接受，而不會強制執行它。

Claude Code 在 schema 編譯之前會執行兩項檢查：對於無法解析的 JSON 值，會以 `Error: --json-schema is not valid JSON` 拒絕；對於有效但不是物件的 JSON，會以 `Error: --json-schema must be a JSON object` 拒絕。

**處理方式：**

* 修正診斷訊息指出的 schema 部分，然後重新執行命令
* 請參閱[取得結構化輸出](https://code.claude.com/docs/zh-TW/headless.md#get-structured-output)，了解可運作的 schema 與命令

### 設定檔超過 2MiB 上限

您傳給 [`--settings`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 的檔案大於 2 MiB，因此 `claude` 會在啟動時以退出碼 1 結束，而不會載入它。在 v2.1.214 之前，Claude Code 讀取該檔案時不做大小檢查，數 GB 的檔案或像 `/dev/zero` 這樣的裝置檔案會使記憶體無限制地增長。

```text theme={null}
Error: Settings file exceeds the 2MiB limit: /path/to/settings.json
```

Claude Code 也會以相同方式拒絕不是一般檔案的 `--settings` 路徑：裝置、FIFO 或 socket 會回報 `Error: Cannot use settings file (Not a regular file (device, FIFO, or socket))`，後面接著路徑；而目錄則會回報 `EISDIR` 原因。

**處理方式：**

* 將 `--settings` 指向小於 2 MiB 的一般 JSON 設定檔。格式請參閱[設定](https://code.claude.com/docs/zh-TW/settings.md)。

### 目前的目錄已不存在

您從一個在 shell 進入後被刪除或移動的目錄啟動了 `claude`，例如被另一個 shell 移除的 worktree 或暫存目錄。Claude Code 無法讀取其工作目錄，因此在啟動工作階段之前就會以退出碼 1 結束，互動模式與[非互動](https://code.claude.com/docs/zh-TW/headless.md)模式皆然。在 v2.1.239 之前，Claude Code 會當機，並在 stderr 上輸出壓縮過的 bundle 原始碼與原始的 `ENOENT ... uv_cwd` 堆疊，而不是此訊息。

```text theme={null}
The current directory no longer exists (it was deleted or moved). Start Claude Code from an existing directory.
error: The current working directory was deleted, so that command didn't work. Please cd into a different directory and try again.
```

兩種形式的原因與修正方式相同。

當 Claude Code 因其他原因（例如權限變更）無法讀取工作目錄時，訊息會改為指出錯誤代碼：`Can't read the current directory (EACCES). Start Claude Code from a different directory.`

在 macOS 上，若 `~/Desktop`、`~/Documents`、`~/Downloads` 或 iCloud Drive 中的目錄出現 `EPERM`，通常表示 macOS 正在阻擋您的終端機應用程式存取該資料夾。讀取該資料夾的其他命令也會以相同方式失敗：在那裡執行 `ls` 會回報 `Operation not permitted`，即使使用 `sudo` 也一樣。

**處理方式：**

* 切換到存在的目錄，例如您的家目錄或專案目錄，然後再次執行 `claude`
* 如果該目錄已在相同路徑重新建立，您的 shell 仍持有已刪除的那一個。請執行 `cd "$PWD"`，或離開後重新進入該目錄，然後再次執行 `claude`
* 對於 macOS 上的 `EPERM`，請以 Cmd+Q 結束您的終端機應用程式，再次開啟它，回到該資料夾，然後執行 `claude`。如果在該資料夾中執行 `ls` 仍然失敗，請開啟 **系統設定 > 隱私權與安全性 > 檔案與檔案夾**，為您的終端機應用程式開啟該資料夾，然後重新開啟終端機

### 暫存目錄被拒絕使用或無法建立

在 macOS 與 Linux 上，Claude Code 會在啟動時建立一個私人暫存目錄 `claude-<uid>`，位於系統暫存目錄或 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 覆寫值之下。當該目錄無法建立，或該路徑上已存在的項目未通過安全檢查時，Claude Code 會將失敗原因列印到 stderr，並以退出碼 1 結束，而不會啟動工作階段：

```text wrap theme={null}
Claude Code's temporary directory /tmp/claude-501 could not be created: the volume holding /tmp is full (ENOSPC). Free space on that volume, or set CLAUDE_CODE_TMPDIR to a directory on another one, then try again.

Temp directory /tmp/claude-501 is not a directory (may be an attacker-planted symlink). Refusing to use it. Set CLAUDE_CODE_TMPDIR to a directory you control, or ask an administrator to remove it.

Temp directory /tmp/claude-501 is owned by uid 502, expected 501. Refusing to use it — another user may have pre-created it. Set CLAUDE_CODE_TMPDIR to a directory you control, or ask an administrator to remove it.

Temp directory /tmp/claude-501 is not readable (its mode may have been altered, or a path component denies search). Refusing to use it — restore its permissions (chmod 0700) or remove it. Set CLAUDE_CODE_TMPDIR to a directory you control, or ask an administrator to remove it.
```

**處理方式：**

* 對於 `could not be created` 後接 `is full (ENOSPC)` 的情況，請釋放訊息所指出磁碟區上的磁碟空間。當訊息改為 `your disk quota on the volume holding /tmp is used up (EDQUOT)` 時，請刪除您在該磁碟區上不再需要的自有檔案
* 對於 `Refusing to use it` 形式，請移除所指名的項目本身（而不是連結所指向的目標），然後再次啟動 Claude Code；對於 `owned by uid` 形式，只有管理員或該使用者能夠移除它
* 對於 `is not readable`，請對所指名的目錄執行 `chmod 0700`，或移除它後再次啟動
* 在上述任何情況下，您都可以將 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 設為您能控制的目錄，然後再次啟動 Claude Code，而不去動被拒絕的路徑

在 v2.1.309 之前，當磁碟區已滿或您的配額已用完時，Claude Code 只會印出作業系統的錯誤文字。例如 `ENOSPC: no space left on device, mkdir '/tmp/claude-501'`，處理步驟相同。

### 目錄無法解析為實際位置

您對工作目錄的子目錄執行了 `/add-dir`，而 Claude Code 無法將該目錄解析為其實際位置。

您本來就擁有工作目錄之子目錄的檔案存取權，因此 `/add-dir` 只會載入其 skill、命令與 agent。在載入之前，Claude Code 會檢查該目錄的實際位置（解析所有符號連結後）是否位於工作目錄內。當 Claude Code 無法解析該位置時，它不會載入任何內容，並顯示此訊息：

```text theme={null}
packages/app couldn't be resolved to a real location, so its skills, commands, and agents weren't loaded. Check that it is a directory inside the working directory and try again.
```

**處理方式：**

* 確認該路徑指向工作目錄內的一個實際目錄，然後再次執行 `/add-dir`
* 此訊息不會變更您的檔案存取權；它只是回報該目錄的 `.claude/` 內容未被載入

在 v2.1.261 之前，當工作目錄位於 `/net/<host>` 自動掛載點時，每次執行 `/add-dir <subdirectory>` 也都會出現此訊息，因為 Claude Code 在設計上不會解析該處的路徑；該目錄本身沒有問題，重試也無濟於事。

### 啟動 Remote Control 時工作區未受信任

> [!NOTE]
>
> 如果 `claude ultrareview` 印出了 `Error: Workspace not trusted`，請改為參閱[執行 claude ultrareview 時出現 Workspace not trusted](#workspace-not-trusted-when-running-claude-ultrareview)。

您在尚未信任的目錄中，以 `claude remote-control` 或其別名 `claude rc` 啟動了 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 伺服器模式，而該命令無法詢問您是否信任該目錄。例如，該命令的標準輸入或標準輸出不是終端機，因為其中之一被重新導向或透過管線傳送。該命令會以退出碼 1 結束：

```text theme={null}
Error: Workspace not trusted. Please run `claude` in /Users/you/project first to review and accept the workspace trust dialog.
```

另有兩種同樣以 `Error: Workspace not trusted.` 開頭的變體，會出現在太小而無法顯示信任該目錄會啟用哪些功能的終端機中，或未回報其大小的終端機中。請放大視窗或切換到一般終端機視窗，然後再次執行 `claude rc`。

在您的家目錄中，訊息會有所不同，因為工作區信任對話框永遠不會儲存對家目錄的信任，所以在那裡接受信任無法滿足此檢查。在 v2.1.214 之前，家目錄會顯示上述訊息，但其建議在那裡無法奏效。

```text theme={null}
Error: Workspace not trusted. /Users/you is your home directory, and for security home-directory trust is never saved, so running `claude` here first won't help. Run `claude rc` from a project directory instead (run `claude` there once to accept the trust dialog).
```

如果您在 [`Trust <directory>?` 問題](https://code.claude.com/docs/zh-TW/remote-control#requirements)回答 `n` 或按下 Enter，該命令會列印一則指出該目錄的 `Remote Control did not start` 訊息，並以退出碼 1 結束。請再次執行 `claude rc` 並回答 `y`。

**處理方式：**

* 先從終端機信任該目錄：在該處執行 `claude rc` 並回答 `y`，或在該處執行 `claude` 並接受[工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，然後再次執行您原本的命令
* 在您的家目錄中，請切換到專案目錄，並在那裡啟動 Remote Control

在 v2.1.284 之前，即使在終端機中，該命令也從不詢問。

### 執行 claude ultrareview 時出現 Workspace not trusted

在您尚未信任的資料夾中，當 [`claude ultrareview`](https://code.claude.com/docs/zh-TW/ultrareview#trust-the-folder-before-the-review-runs) 無法詢問您是否信任它時，該次執行會在審查開始前以退出碼 1 結束：

```text theme={null}
Error: Workspace not trusted. Please run `claude` in /Users/you/project first to review and accept the workspace trust dialog. Or, in a script or CI job, pass `--trust-workspace` to trust the folder for this run only.
```

例如，當子命令的標準輸入或標準輸出不是終端機時，它就無法詢問。將輸出傳送到檔案（如 `claude ultrareview --json > findings.json`）就表示標準輸出不是終端機。

**處理方式：**

* 在指令碼或 CI 工作中，附加 `--trust-workspace` 以僅在該次執行中信任該資料夾：`claude ultrareview --trust-workspace`。請僅對您信任的程式碼附加此旗標，因為 git 與 Claude Code 之後可能會執行該資料夾的 git 設定與專案設定中所指定的程式。對於您不信任其程式碼的 pull request，請[從您信任的分支執行審查](https://code.claude.com/docs/zh-TW/ultrareview.md#trust-the-folder-before-the-review-runs)。
* 在您自己的電腦上，於該資料夾中執行 `claude` 並接受[工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)，然後再次執行原本的命令

`claude ultrareview` 的下列每則訊息都表示沒有啟動任何審查，且退出碼為 1：

* **`Error: Workspace not trusted. This terminal ...`**：終端機未回報列數與欄數，或無法容納信任問題及其警告。請放大終端機或使用會回報其大小的終端機，然後再次執行 `claude ultrareview`。在家目錄以外，您也可以在該資料夾中執行一次 `claude` 並接受信任對話框，之後在那裡的執行就不會再詢問。
* **`Error: Workspace not trusted. <folder> is your home directory`**：由於對家目錄的信任永遠不會被儲存，先在那裡執行 `claude` 並沒有幫助。請改從專案目錄執行 `claude ultrareview`（事先在那裡執行一次 `claude` 以接受信任對話框），或附加 `--trust-workspace`。
* **`No answer in time.` 後接 `Error: Workspace not trusted`**：`Trust <folder>? [y/N]` 問題在 5 分鐘內未獲回答。請再次執行 `claude ultrareview` 並回答它。
* **`Ultrareview did not start: <folder> is not trusted`**：您在 `Trust <folder>? [y/N]` 問題中拒絕了，例如回答 `n` 或按下 Enter。若要啟動審查，請再次執行 `claude ultrareview` 並回答 `y`。
* **``Ultrareview did not start: `--trust-workspace` takes no value``**：`--trust-workspace` 後面接了非旗標的內容，例如 PR 編號或 `false`。如果您不信任該資料夾，請省略此旗標。若要在本次執行中信任它，請將 PR 編號或基底分支放在旗標之前：`claude ultrareview 1234 --trust-workspace`。

在 v2.1.309 之前，`claude ultrareview` 不接受 `--trust-workspace`。

### 不會傳遞到 Remote Control 所啟動的工作階段

您在 `remote-control` 動詞之前加上了全域 `claude` 旗標來啟動 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)，而該旗標會限制或設定 Remote Control 所啟動的工作階段，例如 `--settings`、`--setting-sources`、`--permission-mode`、`--disallowed-tools` 或 `--mcp-config`。放在動詞之前的旗標永遠不會傳到這些工作階段。Claude Code 會改為拒絕啟動，並指出該旗標：

```text theme={null}
Error: `--settings` before `remote-control` is not carried over to the sessions Remote Control starts, so Remote Control refuses to start rather than drop it — remove it, and give Remote Control's own options after the verb (see `claude remote-control --help`).
```

對於捨棄後無害的全域旗標，例如 `--verbose`、`--model`，或由包裝程式注入的 `--session-id` 或 `--plugin-dir`，Claude Code 不會拒絕：它會忽略這些旗標，Remote Control 會照常啟動。

對於尚未被認定為無害的全域旗標，Claude Code 也會拒絕啟動，因此在較新版本中新增的旗標可能會出現在此訊息中，直到之後的版本將其標記為無害為止。

**處理方式：**

* 將該旗標從動詞之前移除，並在動詞之後傳入 [Remote Control 自身的選項](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session)；`claude remote-control --help` 會列出這些選項
* 當被拒絕的旗標是 `--permission-mode` 時，請執行 `claude remote-control --permission-mode <mode>`，為 Remote Control 所啟動的工作階段設定權限模式

在 v2.1.248 之前，當全域旗標在前時，`claude remote-control` 不接受其自身的旗標，該命令會以 `unknown option` 錯誤失敗。

### `--sandbox` or `--no-sandbox` is not supported by claude remote-control

此錯誤表示啟動您 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 伺服器的命令在 `remote-control` 之後傳入了 `--sandbox` 或 `--no-sandbox`，而 `claude remote-control` 兩者皆不接受。伺服器會以退出碼 1 結束，而不會啟動：

```text theme={null}
Error: --sandbox is not supported by claude remote-control. The flag had no effect and was removed. To sandbox sessions, set sandbox.enabled to true in settings.
Error: --no-sandbox is not supported by claude remote-control. The flag had no effect and was removed. Remove it from the command.
```

**處理方式：**

* 從命令中移除該旗標（包括在替您啟動伺服器的指令碼或服務定義中），然後再次執行
* 若要對伺服器所啟動的工作階段使用沙箱，請在[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中將 [`sandbox.enabled`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enabled) 設為 `true`，以開啟[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)

這兩個旗標已在 v2.1.300 中從 `claude remote-control` 移除，因此為較早版本撰寫的命令可能仍帶有其中之一。

### 此建置中尚無法使用 claude import

您執行了 [`claude import`](https://code.claude.com/docs/zh-TW/cli-reference#cli-commands)，而 Claude Code 發現匯入流程已關閉，因此該命令會以退出碼 1 結束，而不會開始匯入。在 v2.1.222 之前，匯入流程關閉的建置會將 `import` 視為提示詞，並啟動互動式工作階段，而不是列印此訊息。

```text theme={null}
`claude import` is not yet available in this build. Run `claude` and use /mcp or edit ~/.claude/settings.json directly.
```

Claude Code 透過從 Anthropic 擷取並快取在磁碟上的功能旗標來開啟 `claude import`。此訊息表示快取的值為關閉。原因通常是以下其中之一：

* 您在安裝後尚未啟動過工作階段，因此 Claude Code 尚未擷取該旗標。即使您可以使用此功能，第一次執行 `claude import` 時也可能列印此訊息。
* 您透過 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 Claude Platform on AWS 使用 Claude Code，或透過 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway#availability-and-limitations)使用。Claude Code 在這些工作階段中不會擷取功能旗標，因此 `claude import` 會一直無法使用。
* 您設定了 `DISABLE_TELEMETRY`、`DO_NOT_TRACK`、`DISABLE_GROWTHBOOK` 或 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars)，這些會關閉功能旗標的擷取，因此 `claude import` 會一直無法使用。

**處理方式：**

* 在全新安裝中，啟動 `claude`，等待工作階段載入後結束，然後再次執行 `claude import`
* 在功能旗標擷取持續關閉的環境中，請自行完成設定：使用 [`claude mcp add`](https://code.claude.com/docs/zh-TW/mcp#installing-mcp-servers) 新增 MCP 伺服器，並建立您想沿用的 [`CLAUDE.md` 檔案](https://code.claude.com/docs/zh-TW/memory#how-claude-md-files-load)、[skill 與命令](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live)，以及 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-the-subagent-scope)。訊息中也提到了 `~/.claude/settings.json`。在 `claude import` 所沿用的設定中，該檔案只保存[權限模式](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)；Claude Code 不會從中讀取 MCP 伺服器。

### 無法讀取 Claude Code 設定

您在 Claude Code 無法剖析 `~/.claude.json`（它儲存您帳戶詳細資料與各專案狀態的檔案）時執行了 [`claude import`](https://code.claude.com/docs/zh-TW/cli-reference#cli-commands)。該子命令會讀取此檔案以檢查可用性，但不會顯示互動式工作階段所顯示的復原對話框，因此會以退出碼 1 結束。在 v2.1.222 之前，設定檔無法讀取時執行 `claude import` 會啟動互動式工作階段，並由其復原對話框處理該檔案。

```text theme={null}
Could not read Claude Code config — run `claude` with no arguments to recover it.
```

**處理方式：**

* 不帶引數執行 `claude`。Claude Code 會偵測到無效的檔案並提供重設選項。然後再次執行 `claude import`。
* 若要保留您手動做過的編輯，請改為在編輯器中修正 `~/.claude.json` 的 JSON 語法，然後重新執行 `claude import`

### 無法從 Claude Desktop 匯入伺服器

Claude Code 無法新增您在 `claude mcp add-from-claude-desktop` 中選取的其中一個伺服器。該命令仍會匯入其他選取的伺服器，並針對每個無法新增的伺服器列印一行。在 v2.1.205 之前，第一個失敗的伺服器會中止匯入。

```text theme={null}
Could not import my server: Invalid name my server. Names can only contain letters, numbers, hyphens, and underscores.
```

伺服器名稱之後的文字是原因。最常見的是名稱檢查：Claude Desktop 允許伺服器名稱中包含空格與句點等字元，而 `claude mcp` 將其限制為字母、數字、連字號與底線。其他原因包括伺服器設定未通過驗證，以及伺服器被您組織的 [MCP 政策](https://code.claude.com/docs/zh-TW/managed-mcp.md)封鎖。

**處理方式：**

* 在 `claude_desktop_config.json` 中將該伺服器重新命名為只使用字母、數字、連字號與底線，然後再次執行 `claude mcp add-from-claude-desktop`
* 使用 `claude mcp add` 或 `claude mcp add-json` 以有效的名稱直接新增該伺服器。請參閱[從 Claude Desktop 匯入 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#import-mcp-servers-from-claude-desktop)。

### 無法將 MCP 伺服器新增到受管範圍

您以 `--scope managed` 執行了 `claude mcp add` 或 `claude mcp add-json`。該範圍保存的是您的組織透過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 受管設定提供的伺服器。Claude Code 只從受管設定讀取它們，因此該命令無法將伺服器寫入該範圍。

```text theme={null}
Cannot add MCP server to scope: managed
```

**處理方式：**

* 將伺服器新增到您可寫入的範圍：`local`、`user` 或 `project`。若不指定 `--scope`，該命令會使用 `local`。請參閱 [MCP 安裝範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)
* 若要將伺服器提供給組織中的每位使用者，請將其新增到您部署的受管設定中的 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers)

### 受管設定只允許外掛伺服器時無法新增 MCP 伺服器

您在組織的受管設定將 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization) 設為 `true` 或設為包含 `mcp` 的清單時，執行了 `claude mcp add` 或 `claude mcp add-json`。在該設定下，Claude Code 不會從 `~/.claude.json` 或 `.mcp.json` 載入 MCP 伺服器，因此該命令會以退出碼 1 結束，而不是儲存一個永遠不會載入的伺服器：

```text theme={null}
Cannot add MCP server: your organization's managed settings allow only MCP servers that plugins provide. Install a plugin that provides this server, or ask your administrator to make it available.
```

`claude mcp add-from-claude-desktop` 會將您選取的每個伺服器回報為未匯入，並以此訊息作為原因。[`/import`](https://code.claude.com/docs/zh-TW/commands#all-commands) 會針對它嘗試新增的每個 MCP 伺服器回報此訊息，但仍會匯入它找到的其他項目。

在 v2.1.284 之前，這些命令會儲存伺服器並回報成功，但該伺服器永遠不會載入。

**處理方式：**

* 安裝提供該伺服器的[外掛](https://code.claude.com/docs/zh-TW/plugins/install.md)
* 請您的管理員在[外掛](https://code.claude.com/docs/zh-TW/plugins/org.md)中發布該伺服器，或者若它是遠端 HTTP 或 SSE 伺服器，則透過 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#managedmcpservers) 提供

### 無法讀取 .mcp.json

讀取專案 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp#project-scope) 的命令（例如搭配 `--scope project` 的 `claude mcp add` 或 `claude mcp add-json`，或 `claude mcp remove`）發現目前目錄中的該檔案不是一般檔案，或大於 2 MiB，因此會以此錯誤結束，而不會讀取該檔案。

```text theme={null}
Can't read .mcp.json: it isn't a regular file or is larger than 2097152 bytes. Fix or remove it, then run the command again.
```

在 v2.1.257 之前，位於 `.mcp.json` 的 FIFO 會讓命令無限期等待且沒有任何輸出，而指向 `/dev/zero` 等裝置檔案的符號連結則會讓記憶體持續增長，直到程序被終止。

**處理方式：**

* 檢查目前目錄中 `.mcp.json` 是什麼。將其替換為[專案範圍格式](https://code.claude.com/docs/zh-TW/mcp.md#project-scope)的一般 JSON 檔案，或將其刪除，然後再次執行命令。

### MCP 伺服器未被儲存或移除

您針對 `user` 或 `local` [範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)中的伺服器執行了 `claude mcp add`、`claude mcp add-json` 或 `claude mcp remove`。這兩個範圍都儲存在 `~/.claude.json` 中，而 Claude Code 在寫入後讀回該檔案時，變更並不在其中。該命令會以此錯誤結束，而不是顯示其成功訊息。

```text theme={null}
MCP server "example" was not saved to /home/user/.claude.json. If that file is read-only or protected by a sandbox, make it writable or run the command outside the sandbox, then add the server again.
```

移除之後，訊息會顯示為 `was not removed from`，並以 `then remove the server again` 結尾。對於 `local` 範圍的伺服器，路徑後面會接著該項目所屬的專案目錄，格式為 `(local scope for /path/to/project)`。

在 v2.1.283 之前，即使變更沒有寫入檔案，`claude mcp add`、`claude mcp add-json` 與 `claude mcp remove` 也會回報成功。

**處理方式：**

* 讓訊息所指名的檔案變為可寫入，或在沙箱之外執行命令，然後再次執行相同的新增或移除命令。

### MCP 伺服器可能未被儲存或移除

您針對 `user` 或 `local` [範圍](https://code.claude.com/docs/zh-TW/mcp.md#mcp-installation-scopes)中的伺服器執行了 `claude mcp add`、`claude mcp add-json` 或 `claude mcp remove`，而 Claude Code 無法讀回 `~/.claude.json` 來確認變更。變更可能已寫入磁碟，也可能沒有。括號中的文字是該次讀取的錯誤。

```text theme={null}
MCP server "example" may not have been saved: /home/user/.claude.json could not be read to confirm the change (EACCES: permission denied, open '/home/user/.claude.json'). Run `claude mcp get example` to check, then add the server again if it is missing.
```

移除之後，訊息會顯示為 `may not have been removed`，並以 `then remove the server again if it is still listed` 結尾。

在 v2.1.283 之前，即使無法確認變更，這些命令也會回報成功。

**處理方式：**

* 執行 `claude mcp get <name>` 以檢查變更是否已寫入磁碟。對於 `local` 範圍的伺服器，請從該伺服器所屬的專案目錄執行，因為 local 範圍是以專案為單位。
* 如果在新增後伺服器不存在，或在移除後仍被列出，請再次執行相同的新增或移除命令。

### 伺服器由 Anthropic 託管，不支援本機 OAuth

您為某個 MCP 伺服器啟動了登入，而其 URL 指向透過第三方身分識別提供者進行身分驗證、由 Anthropic 託管的連接器主機。這些主機包括 `microsoft365.mcp.claude.com`、`gmail.mcp.claude.com` 與 `gcal.mcp.claude.com`。Claude Code 會拒絕從 `/mcp` 面板與 `claude mcp login` 為這些主機啟動本機 OAuth 流程，因為[它們的登入只能透過 claude.ai 進行](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)。

```text theme={null}
"gmail" is Anthropic-hosted and doesn't support local OAuth. Connect it via Settings → Connectors on claude.ai (requires `claude login`), then it'll be available here automatically.
```

**處理方式：**

* 使用 `claude mcp remove <name>` 移除您的項目，以免它遮蔽相同 URL 的 claude.ai 連接器
* 移除後，在登入您於 Claude Code 中使用的帳戶的情況下，於 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 連接該服務。連接後，如果您目前使用的身分驗證方式是 claude.ai 訂閱登入，[該連接器會自動出現在 Claude Code 中](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)

### 伺服器拒絕了設定的 headersHelper 所產生的 Authorization 標頭

某個由 [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication) 提供 `Authorization` 標頭的 MCP 伺服器以 HTTP 401 或 403 回應連線，因此 Claude Code 將該連線回報為失敗。由於 helper 提供了 `Authorization` 標頭，Claude Code [不會改用 OAuth](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers) 連線該伺服器：

```text theme={null}
Server rejected the Authorization header minted by the configured headersHelper (HTTP 401). Check that the helper command returns a valid credential for this MCP endpoint — OAuth fallback is disabled when the helper supplies Authorization.
```

Claude Code 在每次嘗試連線時都會重新執行 helper，因此在暫時性拒絕（例如權杖輪替競爭）之後重試，可能會以新的憑證成功。

**處理方式：**

* 以 Claude Code 執行它的方式自行執行 `headersHelper` 命令：從 [Claude Code 執行它的目錄](https://code.claude.com/docs/zh-TW/mcp.md#where-the-helper-runs)執行，帶上 [Claude Code 為它設定的環境變數](https://code.claude.com/docs/zh-TW/mcp.md#use-dynamic-headers-for-custom-authentication)，並且對於來自專案 `.mcp.json`、外掛或專案 agent 檔案的伺服器，不帶 [Claude Code 移除的憑證變數](https://code.claude.com/docs/zh-TW/mcp.md#which-variables-a-helper-can-read)。確認它輸出的 `Authorization` 值能被該伺服器的端點接受
* 修正 helper 或其憑證來源後，在 `/mcp` 中選取該伺服器並選擇 **Reconnect**

在 v2.1.248 之前，對於 helper 提供 `Authorization` 標頭的伺服器，Claude Code 仍會執行 OAuth 探索。該探索可能會以 `Incompatible auth server: does not support dynamic client registration` 失敗，而不是回報被拒絕的憑證。

### MCP 伺服器拒絕了 elicitation 功能

以 Java MCP SDK 0.11.0 至 0.17.0 建置的 MCP 伺服器拒絕了連線。這些 SDK 版本無法剖析 Claude Code 在交握中宣告的 `form` 與 `url` [elicitation 模式](https://code.claude.com/docs/zh-TW/mcp.md#elicitation-modes-claude-code-declares)。訊息如下：

```text theme={null}
This server (Java MCP SDK 0.17.0 or older) rejected Claude Code's elicitation capability. Set "bareElicitationCapability": true for it, or upgrade to Java MCP SDK 0.17.1+ (Spring AI 1.0.7+ or 1.1.6+).
```

**處理方式：**

* 將伺服器升級至 Java MCP SDK 0.17.1 或更新版本，或升級至訊息所指名的其中一個 Spring AI 版本
* 或者，在您的 MCP 設定中將 `"bareElicitationCapability": true` 新增到該伺服器的項目，然後重新啟動 Claude Code。此欄位適用於 stdio、`sse`、`http` 和 `ws` 項目，且需要 Claude Code v2.1.281 或更新版本

以下 `.mcp.json` 項目為一個 HTTP 伺服器設定此欄位：

```json theme={null}
{
  "mcpServers": {
    "inventory": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "bareElicitationCapability": true
    }
  }
}
```

重新啟動後，`/mcp` 會將該伺服器顯示為已連線。Claude Code 只會對該伺服器宣告 form 模式，因此在升級伺服器後請移除此欄位。

伺服器也可能以其本身的錯誤文字失敗，例如包含 `Unrecognized field "form"` 的錯誤。適用相同的修正方式。

### 找不到 MCP 權限提示工具

您傳給 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 的工具在執行首次需要權限決定時，不在已連線的 MCP 工具之中，原因可能是其伺服器從未連線，或沒有任何已連線的伺服器提供該名稱的工具。Claude Code 仍會傳送您的提示詞：[非互動](https://code.claude.com/docs/zh-TW/headless.md)執行會在第一次工具呼叫時以此錯誤與退出碼 1 結束，因此即使已發出請求，也不會產生任何回答。在第一次提示之前，Claude Code 會等待該伺服器連線，最長等待由 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 設定的每個伺服器 30 秒連線逾時。在 v2.1.206 之前，啟動時不會等待伺服器完成連線，因此啟動緩慢但正常的伺服器也會產生此錯誤。

```text theme={null}
Error: MCP tool mcp__permissions__approve (passed via --permission-prompt-tool) not found. Available MCP tools: none
```

`Available MCP tools:` 之後的清單列出已連線的 MCP 工具。

**處理方式：**

* 確認伺服器能啟動並保持連線：在相同目錄中執行 `claude mcp list`，並確認該伺服器被列為已連線
* 確認工具名稱與伺服器所提供的 `mcp__<server>__<tool>` 名稱相符
* 如果伺服器需要超過 30 秒才能啟動，請調高 [`MCP_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars)

### OAuth 回呼連接埠已被使用

當您以 OAuth 登入遠端 MCP 伺服器時，Claude Code 會啟動本機監聽器來接收登入回呼。如果該監聽器所需的連接埠被其他程序佔用，登入就會以此訊息失敗。這大多發生在透過 [`MCP_OAUTH_CALLBACK_PORT`](https://code.claude.com/docs/zh-TW/env-vars) 變數或 `--callback-port` 設定了[固定回呼連接埠](https://code.claude.com/docs/zh-TW/mcp.md#use-a-fixed-oauth-callback-port)時，因為若未設定，Claude Code 會挑選一個可用的連接埠。

```text theme={null}
OAuth callback port <port> is already in use — another process may be holding it. Run `lsof -ti:<port> -sTCP:LISTEN` to find it.
```

在 Windows 上，建議的命令改為 `netstat -ano | findstr :<port>`。

**處理方式：**

* 執行訊息中的命令以找出佔用該連接埠的程序，然後停止它或等待它結束
* 如果另一個程式需要永久使用該連接埠，請向伺服器註冊不同的重新導向 URI，並以 `MCP_OAUTH_CALLBACK_PORT` 或 `--callback-port`（視您使用哪一個而定）設定其連接埠
* 然後再次開始登入，例如在 `/mcp` 中選取該伺服器

### 沒有可用於 OAuth 重新導向的連接埠

當您以 [OAuth](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-with-remote-mcp-servers) 登入遠端 MCP 伺服器時，Claude Code 會啟動本機監聽器來接收登入回呼。當 Claude Code 無法為其繫結本機連接埠時，登入就會以此訊息失敗。機器上有某些東西阻止它在 `127.0.0.1` 上監聽，例如安全性軟體或拒絕本機監聽器的沙箱政策。

```text theme={null}
No available ports for OAuth redirect
```

在 v2.1.268 之前，Claude Code 不會改用作業系統指派的連接埠，因此當只有它自行挑選的連接埠無法繫結時，也會出現此訊息。這可能發生在 Hyper-V 保留的連接埠範圍涵蓋 Claude Code 挑選範圍的 Windows 主機上。

**處理方式：**

* 檢查是否有安全性軟體或沙箱政策阻止程序在 `127.0.0.1` 上監聽，並允許 Claude Code 繫結本機連接埠
* 然後再次開始登入，例如在 `/mcp` 中選取該伺服器

### 沒有 origin/HEAD 時 /security-review 失敗

[`/security-review`](https://code.claude.com/docs/zh-TW/commands#all-commands) 會將您的分支與 `origin/HEAD`（記錄您 `origin` 遠端上哪個分支為預設分支的本機 ref）進行差異比對，以建立其審查上下文。當該 ref 不存在時，收集差異的 git 命令會失敗，審查會在開始前就停止。

```text theme={null}
Error: Shell command failed for pattern "!`git diff --name-only origin/HEAD...`": [stderr]
fatal: ambiguous argument 'origin/HEAD...': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'
```

訊息可能會改為引用 `git log` 或其他 `git diff`。只有當遠端公告了預設分支，且您的 fetch refspec 涵蓋它時，Git 才會建立 `origin/HEAD`；對含有提交的遠端執行完整的 `git clone` 就會如此。在以下設定中，該參照會不存在：

* 單一分支或 CI 的 checkout，其擷取的 refspec 範圍過窄
* 伺服器端 HEAD 指向無人推送過之分支的遠端
* 沒有 `origin` 遠端的儲存庫，或您從未擷取過的遠端

對於任何[注入動態上下文](https://code.claude.com/docs/zh-TW/skills.md#when-an-injected-command-fails)的 skill，Claude Code 都會顯示相同的錯誤，而注入的命令失敗會中止該 skill 的呼叫。

以下同類字串會在命令執行之前就觸發：

* `Shell command permission check failed for pattern "..."`：該命令的權限檢查不允許它執行。[注入命令的權限檢查](https://code.claude.com/docs/zh-TW/skills.md#permission-checks-on-injected-commands)說明了在各權限模式下哪些結果會中止，以及如何使用 `allowed-tools` 預先核准命令
* ``Skill <name> requires bash (`shell: bash` in frontmatter) but Git Bash was not found``：該 skill 的 frontmatter 要求 bash，但電腦上沒有 bash。請安裝 Git for Windows，或將 frontmatter 改為 `shell: powershell`。請參閱[注入命令的執行方式](https://code.claude.com/docs/zh-TW/skills.md#how-injected-commands-run)

**處理方式：**

* 指定遠端的預設分支來建立該參照：`git remote set-head origin <default-branch>`。只要本機追蹤參照 `origin/<default-branch>` 存在，這就能運作。如果它不存在（例如在單一分支複製中），請先擷取該分支：執行 `git remote set-branches --add origin <branch>`，接著執行 `git fetch origin`，然後重新執行 set-head 命令。再重新執行 `/security-review`。
* 如果您不想指定分支名稱，請執行 `git fetch origin`，然後執行 `git remote set-head origin --auto`，它會詢問遠端哪個分支是預設分支。當遠端沒有公告預設分支（因為它是空的，或其 HEAD 指向無人推送的分支）時，它會以 `error: Cannot determine remote HEAD` 失敗；此時請明確指定分支。當您的複製不擷取該分支時，它會以 `error: Not a valid ref` 失敗；請先如上所述擴大 refspec。
* 如果儲存庫沒有遠端，請使用 `git remote add origin <url>` 新增一個，並在建立參照前先擷取。如果遠端是空的，請先使用 `git push -u origin HEAD` 推送您的分支，並在 set-head 命令中指定該分支；之後 `origin/HEAD` 會指向您剛推送的分支，因此在您的分支與其分歧之前，`/security-review` 看到的差異都會是空的。

### No shell command in a skill or command was run

`No shell command in <name> was run` 表示該 skill 或命令檔案中的某個 `` !`<command>` `` [動態上下文命令](https://code.claude.com/docs/zh-TW/skills.md#inject-dynamic-context)包含 Bash 或 PowerShell 工具會拒絕的字元：

* **任一工具**：除 tab 或換行以外的原始控制字元
* **PowerShell 工具**：另外還有 U+FEFF 或 U+180E

訊息會以被拒絕的命令結尾，並將每個被拒絕的字元顯示為 `�`，如以下 Bash 工具的範例：

```text theme={null}
No shell command in /my-skill was run, because the Bash tool does not accept one of them: command contains control characters that would be hidden in the approval dialog. Unprintable characters are shown as � below: remove them from the skill or command file, or from the arguments or options substituted into it.
build.sh --target�dist
```

**處理方式：**

* 在訊息結尾引用的命令中找出每個 `�`。從 [skill 或命令檔案](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live)中，或從代入該檔案的引數或[選項](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#user-configuration)中，移除它所代表的字元。

### 使用 `--print` 時必須提供輸入

單獨執行 `claude` 需要 stdout 是終端機，才能啟動互動式 UI。當 stdout 被重新導向，或主控台不是真正的終端機（例如 PowerShell ISE 與某些 IDE 輸出窗格）時，`claude` 會改以[非互動方式](https://code.claude.com/docs/zh-TW/headless.md)執行。這與 `claude -p` 是相同的模式，而該模式需要提示詞，因此即使您沒有傳入該旗標，訊息也會提到 `--print`。在任何地方傳入 `-p`/`--print` 卻沒有提示詞、stdin 也沒有透過管線傳入任何內容，都會產生相同的錯誤。

```text theme={null}
Error: Input must be provided either through stdin or as a prompt argument when using --print
```

**處理方式：**

* 若要互動使用，請在真正的終端機中執行 `claude`：使用 Windows Terminal 或 PowerShell 主控台而非 ISE，並使用 IDE 的整合式終端機而非輸出窗格
* 若要單次使用，請傳入提示詞：`claude -p "your question"`，或以 `echo "your question" | claude -p` 透過管線傳入

### Claude Code 無法在此讀取鍵盤

您在不帶 [`-p`](https://code.claude.com/docs/zh-TW/headless) 的情況下執行了 `claude`，這會啟動[互動式工作階段](https://code.claude.com/docs/zh-TW/interactive-mode.md)，但其標準輸入不是終端機。有東西透過管線傳送或重新導向了它，或是啟動 `claude` 的程式提供了它自己的輸入串流。

互動式工作階段需要從終端機讀取您的按鍵，而沒有終端機時 Claude Code 的行為取決於您的平台：

* **Windows**：Claude Code 會將訊息列印到 stderr 並以退出碼 1 結束，而不會啟動介面
* **macOS 與 Linux**：Claude Code 會從 `/dev/tty` 讀取您的按鍵並啟動工作階段，並以任何透過管線傳入的文字作為您的第一個提示詞。當 `/dev/tty` 無法開啟時，您會看到此訊息，其第一行會以 `/dev/tty` 取代 Windows 的措辭。

在 Windows 上，訊息內容如下：

```text theme={null}
Claude Code can't read the keyboard here: stdin is not a terminal (it is piped, redirected, or supplied by the program that launched claude), and on Windows it can't fall back to the console for input yet.
Run claude directly in Windows Terminal, PowerShell, or Command Prompt, without piping or redirecting its input.
To send text as a prompt and print the reply instead, add -p; it also works with --continue and --resume <session-id> (for example: type notes.md | claude -p --continue).
```

**處理方式：**

* 若要互動工作，請直接在終端機中執行 `claude`，不要透過管線傳送或重新導向其輸入
* 若要在沒有互動式介面的情況下取得回覆（例如從指令碼），請加上 `-p`，並以引數或透過 stdin 提供提示詞，例如 `claude -p "your question"` 或 `echo "your question" | claude -p`。這也適用於 `--continue` 與 `--resume <session-id>`。

在 v2.1.287 之前，Claude Code 會啟動介面而不是列印此訊息，然後要嘛畫面上什麼都不顯示，要嘛以包含 `Raw mode is not supported` 的錯誤失敗。

如果您是在執行 `claude install` 時看到 `Raw mode is not supported`，請參閱[安裝期間出現 `Raw mode is not supported`](https://code.claude.com/docs/zh-TW/troubleshoot-install#raw-mode-is-not-supported-during-install)。

### 輸入只包含空白字元

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，Claude Code 會拒絕完全由空格、定位字元或換行組成的提示詞，而不會傳送它，因為 API 會拒絕沒有可見文字的訊息。您看到哪則訊息取決於空白提示詞的來源：

* **`claude -p` 的提示詞引數或透過管線傳入的 stdin**：`claude` 會以 `Error: Input contained only whitespace. Provide a prompt with text through stdin or as a prompt argument when using --print` 結束
* **提交到執行中的 `--input-format stream-json` 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 工作階段的訊息**：Claude Code 會在不呼叫模型的情況下結束該回合，工作階段仍可繼續使用。拒絕會以資訊訊息以及該回合的結果文字送達：`Blank prompt — the message was only whitespace, so nothing was sent to the model.`

在 v2.1.229 之前，Claude Code 會將只含空白的訊息傳送給 API，而 API 會以 400 錯誤拒絕該請求。

**處理方式：**

* 在提示詞中加入可見的文字。如果指令碼是從變數或檔案建立提示詞，請在呼叫 Claude Code 之前確認來源不是空的。

### stream-json 輸入超過 256M 個字元且沒有換行

您的程式在 stdin 上向 `claude -p --input-format stream-json` 執行傳送了超過 268,435,456 個字元且沒有換行，因此 Claude Code 會將此錯誤列印到 stderr 並以退出碼 1 結束，而不會繼續緩衝更多輸入。訊息中將此上限表示為 `256M`。在 v2.1.257 之前，Claude Code 會無限制地緩衝此類輸入，使記憶體持續增長，直到程序當機或被終止。

```text theme={null}
Error: stream-json input carried over 256M characters with no newline. Each stream-json message must be a single newline-terminated JSON line: either the producer is not newline-terminating its messages, or one message exceeded this budget.
```

這麼長卻沒有換行的輸入，通常表示產生者根本不是 stream-json 產生者，例如意外透過管線傳入的二進位檔案或純文字日誌輸出。單一訊息超過此上限也會未通過相同的檢查。

**處理方式：**

* 檢查透過管線傳入 stdin 的內容。使用 [`--input-format stream-json`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 時，每則訊息都必須是以換行結尾的一行 JSON
* 若要改為傳送純文字，請移除 `--input-format stream-json`；`claude -p` 預設會從 stdin 讀取純文字提示詞

### 未知的命令

在互動式終端機工作階段中，您提交了一個與此工作階段中任何命令都不相符的 `/` 名稱，因此 Claude Code 會回報該名稱，而不會執行任何動作：

```text theme={null}
Unknown command: /hepl. Did you mean /help?
```

Claude Code 會建議選單在此工作階段中列出的最接近的命令名稱或別名。當沒有相近的名稱時，訊息會在名稱之後結束。原因通常是以下其中之一：

* 打字錯誤，例如將 `/help` 打成 `/hepl`。[命令選單如何比對您輸入的內容](https://code.claude.com/docs/zh-TW/commands.md#how-the-command-menu-matches-what-you-type)說明了如何在提交前挑選相近的符合項目
* 命令存在，但由於未滿足某項要求（例如您的平台、方案或身分驗證方式），在此工作階段中無法使用。請參閱 [`/web-setup`](https://code.claude.com/docs/zh-TW/web-quickstart#web-setup-shows-no-commands-match-or-unknown-command)、[`/schedule`](https://code.claude.com/docs/zh-TW/routines#schedule-returns-unknown-command) 或 [`/auto-mode-setup`](https://code.claude.com/docs/zh-TW/auto-mode-config#auto-mode-setup-returns-unknown-command) 的相關項目。某些命令在您組織的政策停用它們時，會以自己的訊息回應，例如 [`Cloud sessions are disabled by your organization's policy`](#cloud-sessions-are-disabled-by-your-organizations-policy)
* 來自[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)或 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands)的命令，但該外掛或伺服器在此工作階段中未安裝或未連線

只有在互動式終端機工作階段中，Claude Code 才會以這種方式回應不相符的 `/` 名稱。在其他所有工作階段中，它會改將提示詞作為一般訊息傳送給 Claude，並附上一則說明該命令未執行的備註，以及 Claude 在該工作階段中可執行的命令清單。這些工作階段包括：

* `-p` 執行
* [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式
* [Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)的 Code 分頁
* [VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)的聊天面板
* [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)與[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)

對於無法在這些工作階段之一中執行的內建命令，Claude Code 仍會回應該命令無法使用，而不是將其傳送給 Claude。在 v2.1.274 之前，只有雲端工作階段與雲端排程任務會將不相符的名稱傳送給 Claude。在 v2.1.273 之前，它們也會回應 `Unknown command`。

Claude Code 不會將每個以 `/` 開頭的提示詞都視為命令。當 `/` 之後的第一個字以標點符號開頭（例如開啟 Lean 文件註解的 `/--`），或是像 `/var/log/syslog` 這樣的路徑時，它會將提示詞作為一般訊息傳送給 Claude。

在 v2.1.236 之前，如果您在命令選單列出與您輸入的名稱相近的符合項目時按下 `Enter`，Claude Code 會執行該符合項目，因此像 `/hepl` 這樣的打字錯誤會執行 `/help`，而不是產生此訊息。

**處理方式：**

* 執行建議的名稱，或輸入 `/` 加上名稱的一部分，以查看此工作階段中可用的命令
* 如果 Claude Code 將文件中記載的命令回報為未知，請查看[命令參考](https://code.claude.com/docs/zh-TW/commands.md)中該命令的列，了解它所指出的需求

### 差異對 ultrareview 而言過大

您的分支與基底分支之間的差異（包括未提交與已暫存的變更）超過了 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md) 的大小上限，因此 `/code-review ultra` 與 `claude ultrareview` 子命令會在雲端工作階段啟動前拒絕該審查。被拒絕的審查不會使用免費執行次數，也不會收取用量點數。訊息會指出生效的上限、您的差異大小，以及貢獻最多變更行數的檔案。在 v2.1.216 之前，訊息只顯示原始的差異統計資料。

```text theme={null}
Diff is too large for ultrareview: 812 files, 96,410 lines changed (limits: 500 files, 8,000 lines). Largest files: package-lock.json (41,904 lines), dist/bundle.js (18,210 lines), src/generated/api.ts (9,876 lines). Pass a closer base branch (`/code-review ultra <branch>`) to narrow the scope, or split the change.
```

審查 pull request 時也適用相同的上限；該形式的訊息以 `PR #<N> is too large for ultrareview` 開頭，並指出該 PR 的檔案數與行數。

**處理方式：**

* 傳入更接近您工作的基底分支，例如 `/code-review ultra develop`，讓審查只涵蓋與該分支之間的差異
* 將變更拆分為較小的分支並逐一審查。訊息所指名的檔案貢獻了最多的變更行數，因此請先將它們移到各自的分支。

### 找不到與基底分支的 merge-base

`/code-review ultra` 與 `claude ultrareview` 子命令會審查您的分支與基底分支之間的差異，這需要兩者共同擁有的提交。當 `git merge-base` 找不到任何共同提交時，Claude Code 會在雲端工作階段啟動前拒絕該審查。在 Claude Code 能驗證為完整、且至少有一個分支的複製上，它會改為[審查每個被追蹤的檔案](https://code.claude.com/docs/zh-TW/ultrareview.md#diff-limits-and-fallbacks)，而不是拒絕。當完全找不到基底分支、Claude Code 無法驗證您的複製是否完整，或在無法進行整棵樹差異比對的少數儲存庫中（例如 SHA-256 物件格式），您會看到此拒絕訊息。

```text theme={null}
Could not find merge-base with main. Pass the base branch explicitly (e.g. `/code-review ultra develop`) or make sure you're in a git repo with a main branch.
```

第一句之後的提示取決於 Claude Code 觀察到的情況：

* **您沒有傳入基底分支**：Claude Code 與儲存庫的預設分支進行比較，並建議您明確傳入基底分支，如上例所示
* **您傳入的基底分支已存在於您的複製中**：提示內容為 ``Make sure <branch> exists locally or on origin (try `git fetch origin <branch>`)``
* **您傳入的基礎分支不在您的複製中**：Claude Code 在比較前會先從 origin 擷取該分支。提示內容為 ``<branch> was fetched from origin but shares no history with HEAD. If another branch is your real base, pass it explicitly (`/code-review ultra <branch>`)``；當 Claude Code 無法判斷您的複製是否為淺層複製時，則會改為建議 `git fetch --unshallow origin`。在 v2.1.221 之前，提示會對每個擷取的基礎分支都建議 `git fetch --unshallow origin`，而在完整的複製上，該命令會失敗並顯示 `fatal: --unshallow on a complete repository does not make sense`。

**處理方式：**

* 如果另一個分支才是您真正的基底，請明確傳入它：`/code-review ultra <branch>`
* 如果您的複製可能沒有完整歷史，請執行 `git fetch --unshallow origin` 並重新執行審查

### 您的 checkout 沒有任何分支

checkout 可能有提交卻沒有分支：如果您執行 `git init`，接著執行 `git fetch <url>` 與 `git checkout FETCH_HEAD`，就會得到一個沒有任何參照的分離 HEAD。Claude Code 會將您的儲存庫打包為 git bundle 以上傳進行 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)，而它無法打包沒有分支或其他參照的儲存庫，因此 `/code-review ultra` 與 `claude ultrareview` 子命令會在雲端工作階段啟動前拒絕該審查。

```text theme={null}
Your checkout has no branches (detached HEAD only), which cloud review can't bundle. Create one first — `git checkout -b <name>` — then rerun /code-review ultra.
```

在 v2.1.221 之前，Claude Code 會嘗試審查此 checkout 中每個被追蹤的檔案，而上傳會失敗。

**處理方式：**

* 使用 `git checkout -b <name>` 在目前的提交上建立分支，然後重新執行審查

### 沒有 GitHub 帳戶連結到您的 Claude 帳戶

您執行了 `/code-review ultra <PR#>` 或 `claude ultrareview <PR#>`，而在建立雲端工作階段之前，Claude Code 會詢問伺服器[連結到您 Claude 帳戶的 GitHub 帳戶](https://code.claude.com/docs/zh-TW/ultrareview.md#review-a-pull-request)是否能存取該 PR 的儲存庫。由於沒有連結任何帳戶，或連結已過期，雲端複製將會失敗，因此 Claude Code 會拒絕啟動。對於被拒絕的啟動，Claude Code 不會耗用免費執行次數，也不會收取用量點數。

```text theme={null}
Ultrareview clones <owner>/<repo> in the cloud with the GitHub account connected to your Claude account, and none is connected (or the connection expired). To fix: run /web-setup to reuse your GitHub CLI login, or connect an account at https://claude.ai/connect-github — then re-run /code-review ultra 1234 (allow a minute after connecting).
```

當 [`/web-setup`](https://code.claude.com/docs/zh-TW/web-quickstart#connect-from-your-terminal) 在您的工作階段中無法使用時，訊息只會提到 claude.ai 連結。

**處理方式：**

* 執行 `/web-setup` 將您的 GitHub CLI 登入連結到您的 Claude 帳戶，或在 [claude.ai/connect-github](https://claude.ai/connect-github) 連結帳戶
* 連結後約一分鐘再重新執行審查

在 v2.1.248 之前，Claude Code 不會在啟動前檢查此項目。

### 您連結的 GitHub 帳戶無法看到該儲存庫

您執行了 `/code-review ultra <PR#>` 或 `claude ultrareview <PR#>`，而[連結到您 Claude 帳戶的 GitHub 帳戶](https://code.claude.com/docs/zh-TW/ultrareview.md#review-a-pull-request)無法讀取該 PR 的儲存庫，因此雲端複製將會失敗，Claude Code 會拒絕啟動。對於被拒絕的啟動，Claude Code 不會耗用免費執行次數，也不會收取用量點數。

```text theme={null}
Your connected GitHub account can't see <owner>/<repo> — usually the Claude GitHub app isn't installed on <owner> or wasn't granted this repo (web-connected accounts need it for private repos), or a different GitHub account is connected. To fix: run /web-setup to reuse your GitHub CLI login, or install the app at https://github.com/apps/claude/installations/new — then re-run /code-review ultra 1234.
```

當 [`/web-setup`](https://code.claude.com/docs/zh-TW/web-quickstart#connect-from-your-terminal) 在您的工作階段中無法使用時，訊息只會提到安裝應用程式。

**處理方式：**

* 如果您本機的 `gh` CLI 能夠讀取該儲存庫，請執行 `/web-setup` 將該登入連結到您的 Claude 帳戶
* 完成變更後重新執行審查

在 v2.1.248 之前，Claude Code 不會在啟動前檢查此項目。

### GitHub App 預檢暫時性失敗

您從本機儲存庫啟動了[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，而有兩個步驟同時失敗。Claude Code 無法建置或上傳您儲存庫的 bundle。在上傳之前，它檢查了雲端服務是否能從 GitHub 複製該儲存庫，而該檢查並未得到明確的答案，而是以重試可能排除的錯誤結束，例如網路錯誤、逾時或暫時性的伺服器錯誤。完整訊息會以阻止 bundle 的原因開頭，例如 `Could not upload repo bundle (<error>)`，並以預檢的句子結尾：

```text theme={null}
Could not upload repo bundle (<error>). The GitHub App preflight failed transiently (network or service hiccup) — retry in a moment to start from GitHub instead
```

**處理方式：**

* 稍後重新執行命令。當 GitHub 檢查通過時，Claude Code 可以從 GitHub 複製啟動工作階段，因此失敗的上傳不再阻擋啟動
* 如果重試持續失敗，訊息開頭會指出阻止上傳的原因。當該原因是您可以修正的問題時，請加以修正，讓工作階段能改從您的本機儲存庫啟動

在 v2.1.251 之前，即使 GitHub 檢查只是暫時性失敗，Claude Code 也會以 `Please set up GitHub on https://claude.ai/code` 結束訊息，而設定建議無法排除暫時性失敗。

### 儲存庫上傳無法遵循某項 git 設定

您啟動了[上傳本機儲存庫的雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-local-repositories-without-github)，或對某個分支進行 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)，而上傳無法遵循決定哪些屬性規則適用於您檔案的某項 git 設定。如果上傳照常進行並漏掉某條規則，那麼 git 在儲存前會轉換的檔案（例如由 clean 過濾器加密的檔案）可能會以磁碟上的原樣傳到雲端。Claude Code 會改為拒絕上傳，不會上傳任何內容：

```text theme={null}
Not uploading this working tree: core.ignoreCase (which decides whether .gitattributes patterns match file names regardless of letter case) is set in <file>, and the upload cannot follow that setting, so a file git would change before storing it (to encrypt it, for example) could be uploaded as it is on disk. Move the core.ignoreCase line into this repository’s .git/config or directly into your ~/.gitconfig, then retry.
```

訊息會指出該設定及其設定位置，並以針對您所遇情況的修正方式結尾。`core.attributesFile` 與 `attr.tree` 也會出現相同的拒絕訊息，各自附有其修正方式。

訊息可能會指出您的 git 設定透過 `include` 或 `includeIf` 指示引入的設定檔，即使該指示的條件並不適用於此儲存庫。

**處理方式：**

* 套用訊息最後一句中的修正方式

### GitHub 未連結到您的 Claude 帳戶

您從本機儲存庫啟動了[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)，例如使用 `/autofix-pr`。沒有 GitHub 帳戶連結到您的 Claude 帳戶，或連結已過期，因此 Claude Code 會拒絕啟動：

```text theme={null}
GitHub isn't connected to your Claude account, so this repository can't be cloned in the cloud. Run /web-setup to connect with your GitHub CLI login, or connect on the web at https://claude.ai/connect-github
```

當您使用 [`/schedule`](https://code.claude.com/docs/zh-TW/routines) 建立雲端排程任務時，相同的訊息會以列出儲存庫的設定提示形式出現；該提示不會阻擋任務的建立。

**處理方式：**

* 執行 `/web-setup` 將您的 GitHub CLI 登入連結到您的 Claude 帳戶，或在 [claude.ai/connect-github](https://claude.ai/connect-github) 連結帳戶。關於兩者的差異，請參閱 [GitHub 身分驗證選項](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#github-authentication-options)。
* 連結後約一分鐘再重新執行命令

在 v2.1.268 之前，Claude Code 會將此情況回報為 Claude GitHub App 檢查的暫時性失敗，並建議重試或安裝該應用程式；但這兩者都無法連結 GitHub 帳戶。

### GitHub 組織政策正在封鎖 Claude

您在 Claude Code 提示字元執行了會啟動雲端工作階段的命令，例如 [`/autofix-pr`](https://code.claude.com/docs/zh-TW/claude-code-on-the-web#auto-fix-pull-requests)。在建立工作階段之前，Claude Code 會在 GitHub 上檢查 Claude 對儲存庫的存取權，而 GitHub 拒絕了，因為您的 GitHub 組織有一項封鎖 Claude 的政策。Claude Code 會在此停止，並顯示一則指出該政策的訊息。

當封鎖存取的是 IP 允許清單時，訊息內容為：

```text theme={null}
Your GitHub organization has an IP allowlist that is blocking Claude. Add Claude's IP ranges to your GitHub allowlist.
```

當封鎖存取的是單一登入時，訊息內容為：

```text theme={null}
Your GitHub organization requires single sign-on. Disconnect and reconnect GitHub on the Connectors page in Claude on the web, click Authorize next to your organization when GitHub asks, then try again.
```

當封鎖存取的是 Microsoft Entra ID 條件式存取政策時，訊息內容為：

```text theme={null}
Your GitHub organization's identity provider (Microsoft Entra ID) has a Conditional Access policy that is blocking Claude. Ask your GitHub Enterprise or Entra ID admin to allow Claude in that policy.
```

**處理方式：**

* **IP 允許清單**：請 GitHub 組織或企業的擁有者允許 Anthropic 的對外 IP 位址。請參閱 [GitHub 允許清單與防火牆](https://code.claude.com/docs/zh-TW/network-config.md#github-allow-lists-and-firewalls)，了解相關位址以及需要變更的 GitHub 設定。
* **單一登入**：在 [claude.ai/customize/connectors](https://claude.ai/customize/connectors) 中中斷 GitHub 的連接，然後再次連接。當 GitHub 詢問時，按一下組織旁的 **Authorize**，讓新連線獲得該組織單一登入的授權。
* **條件式存取政策**：請您的 GitHub Enterprise 或 Microsoft Entra ID 管理員在該政策中允許 Claude
* 完成變更後，再次執行該命令

### 需要單一登入授權

您執行了 [`/install-github-app`](https://code.claude.com/docs/zh-TW/github-actions#quick-setup)，並選擇了一個其組織強制使用 SAML 單一登入的儲存庫。在設定之前，Claude Code 會使用 GitHub CLI 檢查您對該儲存庫的存取權，而 GitHub 拒絕了該檢查，因為您的 `gh` token 尚未獲得該組織的授權。精靈會顯示警告以及授權步驟：

```text theme={null}
Single sign-on authorization needed
<owner>/<repo> belongs to an organization that enforces SAML single sign-on, and your GitHub CLI token isn't authorized for it yet.
```

**處理方式：**

* 執行 `gh auth refresh -h github.com -s repo,workflow`，以 `repo` 和 `workflow` 範圍重新授權您的 GitHub CLI 登入，並在 GitHub 提示單一登入時授權該組織
* 如果您使用 `GH_TOKEN` 中的個人存取 token 進行驗證，請開啟 [github.com/settings/tokens](https://github.com/settings/tokens)，在該 token 上選擇 **Configure SSO**，並授權該組織
* 再次執行 `/install-github-app`

在 v2.1.273 之前，Claude Code 在此情況下會改為顯示 `Admin permissions required` 警告。

### 無法繼續對話

Claude Code 無法讀取或處理您從 [`claude --resume` 選擇器](https://code.claude.com/docs/zh-TW/sessions#use-the-session-picker)中選取之工作階段的已儲存逐字稿，因此它會結束程序，而不是在部分載入的狀態下繼續。訊息中包含重試用的命令：

```text theme={null}
Failed to resume the conversation.
Run claude --resume <session-id> to retry, or claude to start a new session.
```

Claude Code 在顯示訊息後會以代碼 1 結束。在執行中的工作階段內使用 `/resume` 選擇器時，則會在對話中回報 `Failed to resume conversation`，而您目前的工作階段會繼續執行。在 v2.1.216 之前，從 `claude --resume` 選擇器繼續失敗時，會無限期停留在 `Resuming conversation…` 載入動畫上，而不會顯示此訊息。

**處理方式：**

* 使用訊息中的工作階段 ID 執行 `claude --resume <session-id>` 以重試
* 在 v2.1.285 之前的版本上，如果重試以相同方式失敗，請執行 `claude update` 後再次繼續。當已儲存的逐字稿包含這些版本無法讀取的項目時，這些版本會讓繼續操作失敗。
* 如果重試再次失敗，請執行 `claude` 以開始新的工作階段

### 找不到具有該工作階段 ID 的對話

您將工作階段 ID 傳給 `claude --resume <session-id>`，但沒有任何已儲存的逐字稿與之相符：

```text theme={null}
No conversation found with session ID: <session-id>
```

Claude Code 顯示訊息後會以代碼 1 結束。Claude Code 會[先搜尋目前的專案，再搜尋這台機器上的所有其他專案](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)來尋找該 ID。在 v2.1.223 之前，查找只會涵蓋目前的專案目錄及其 git worktree，因此請從該工作階段最後工作的目錄進行恢復。

常見原因：

* **ID 輸入錯誤**：對於非互動式執行，ID 是 [`--output-format json` 輸出](https://code.claude.com/docs/zh-TW/headless#get-structured-output)中的 `session_id` 欄位
* **逐字稿已刪除**：Claude Code 會依照[保留清理規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)，在[保留期限](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)（預設為 30 天）後移除逐字稿
* **不同的機器**：Claude Code 將逐字稿儲存在本機，因此請在執行該工作階段的機器上繼續
* **重複的副本**：如果您複製了 `~/.claude/projects` 下的專案目錄，導致兩份逐字稿帶有相同的 ID，Claude Code 會回報此訊息，而不會任意繼續其中一份副本

**處理方式：**

* 對於互動式工作階段，請使用 `claude --resume` 開啟[工作階段選擇器](https://code.claude.com/docs/zh-TW/sessions.md#use-the-session-picker)，並按 `Ctrl+A` 將範圍擴大到這台機器上的所有專案，然後選取該工作階段
* 使用 `claude -p` 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 建立的工作階段不會出現在選擇器中，因此請對照原始執行所輸出的 `session_id` 再次檢查 ID

### Claude Code 讀取此工作階段的逐字稿檔案時，Windows 回報錯誤（EBADF）

您在 Windows 上繼續一個工作階段，其已儲存的[逐字稿檔案](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)正常開啟，但接著讀取時發生系統錯誤 EBADF。此系統錯誤並未說明讀取失敗的原因，因此訊息會提出可能的原因以及可以嘗試的做法：

```text theme={null}
Windows reported an error (EBADF) when Claude Code read this session's transcript file, although the file had opened normally. This can happen when other software intercepts file reads — security, encryption or endpoint-management tools, for example. If it keeps happening for this conversation, try excluding the folder that holds Claude Code's session transcripts from such software (the .claude folder in your user profile, unless the app or CLAUDE_CONFIG_DIR points Claude Code elsewhere), or adding Claude Code to its allowed applications, then resume again.
```

此訊息會接在命令本身的失敗行之後，例如 `Failed to resume session <session-id>`。`claude --resume` 或 [`claude -p`](https://code.claude.com/docs/zh-TW/headless) 命令在顯示此訊息後會以代碼 1 結束。在工作階段內使用 `/resume` 後，您目前的工作階段會繼續執行。

**處理方式：**

* 將存放工作階段逐字稿的資料夾從會掃描或攔截檔案讀取的軟體（例如安全性、加密或端點管理工具）中排除。逐字稿預設位於 `%USERPROFILE%\.claude\projects` 下，或位於 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 所指定的目錄下
* 如果無法新增排除項目，請改為將 Claude Code 加入該軟體的允許應用程式
* 再次繼續該工作階段

在 v2.1.282 之前，此失敗不附帶任何說明：`claude --resume <session-id>` 會停在 `Failed to resume session <session-id>`，而 `-p` 執行只會輸出系統錯誤文字，例如 `Failed to resume session: EBADF: bad file descriptor, read`。

### 無法在此工作階段中切換渲染器

切換渲染器時，Claude Code 會重新啟動其程序。您在一個 Claude Code 拒絕重新啟動的工作階段中執行了 [`/tui`](https://code.claude.com/docs/zh-TW/fullscreen#enable-fullscreen-rendering)，因此它不會切換，也不會儲存任何內容。您看到的訊息會指出原因：

* `Cannot switch renderers while work is running in the background`：您有正在背景執行、重新啟動會將其捨棄的工作，例如背景 shell 或 subagent。請等待工作完成，或使用 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 將其停止，然後再次執行 `/tui fullscreen` 或 `/tui default`
* `Cannot switch renderers in this session`：該工作階段有 Claude Code 無法傳遞給重新啟動後程序的限制。在 v2.1.234 之前，Claude Code 仍會重新啟動，而重新啟動後的工作階段會在沒有這些限制的情況下執行

在限制訊息中，括號內的部分會指出 Claude Code 找到的限制：

```text theme={null}
Cannot switch renderers in this session — it has restrictions a restart can't carry over (permission rules set for this session only). Nothing was changed. Running /tui fullscreen in a session started without them switches every later session too.
```

訊息括號內可能顯示的各項原因：

* `launch flags: a custom system prompt, a tool allowlist, or restricted settings`：您使用了 Claude Code 不會傳回給重新啟動後程序的旗標來啟動工作階段。這些旗標包括 [`--system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)、`--system-prompt-file`、`--append-system-prompt-file`、[`--tools`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 允許清單、[`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 以及 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)
* `permission rules set for this session only`：來自 hook 或 SDK 呼叫端的[權限更新](https://code.claude.com/docs/zh-TW/hooks.md#permission-update-entries)以 `session` 目的地新增了拒絕或詢問規則。限於工作階段範圍的允許規則不會觸發拒絕。重新啟動會捨棄這些規則，而 Claude Code 會改為再次提示
* `ask-before-running rules with no command-line form`：來自 hook 或 SDK 呼叫端的權限更新，在 Claude Code 以 `--allowed-tools` 和 `--disallowed-tools` 傳回的規則之外新增了詢問規則。詢問規則沒有對應的旗標
* `permission rules a command line cannot carry intact` 和 `added directories a command line cannot carry intact`：權限更新在工作階段中途新增了規則或目錄路徑。重新啟動後程序的命令列無法以相同的值攜帶其文字

**處理方式：**

* 在未帶有這些限制而啟動的工作階段中，執行 `/tui fullscreen`，或執行 `/tui default` 切換回來。Claude Code 會在該處儲存 [`tui` 設定](https://code.claude.com/docs/zh-TW/settings-reference#tui)

### Can't restart while work is running or Remote Control is connected

Claude Code 沒有重新啟動，您的工作階段會維持原狀繼續執行。請依照訊息中的修正方式處理。

### Claude Code couldn't restart

當此訊息表示您的對話已儲存時，代表對話已寫入磁碟，您可以從中斷處繼續。Claude Code 當時正在自行重新啟動，例如在您執行 [`/tui`](https://code.claude.com/docs/zh-TW/fullscreen#enable-fullscreen-rendering) 後切換至或切換出全螢幕渲染，但無法啟動新程序，因此以狀態 1 結束：

```text theme={null}
Claude Code couldn't restart. Your conversation is saved. Start Claude Code again and run /resume to pick it up.
```

當重新啟動時沒有可重新開啟的對話，例如因為 `/tui` 是您在新工作階段中的第一個輸入，訊息內容為 `Claude Code couldn't restart. Start Claude Code again.`

**處理方式：**

* 在您的 shell 中再次執行 `claude`。如果訊息表示您的對話已儲存，請在新工作階段中執行 [`/resume`](https://code.claude.com/docs/zh-TW/sessions#resume-a-session) 並選取該對話。如果對話不在清單中，請[擴大工作階段選擇器的範圍](https://code.claude.com/docs/zh-TW/sessions.md#where-the-session-picker-looks)
* 若重新啟動持續失敗，請在 shell 中使用 [`claude --debug-file claude-debug.log`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 啟動 Claude Code。若從該工作階段重新啟動失敗，您啟動所在目錄中的 `claude-debug.log` 會記錄一行包含作業系統錯誤的 `Failed to relaunch:`。在您[回報問題](#report-an-error)時請附上該行

### 無法開啟 Claude Desktop

您在工作階段中執行了 [`/desktop`](https://code.claude.com/docs/zh-TW/desktop#coming-from-the-cli) 或其別名 `/app`，或在 shell 中執行了 [`claude --desktop`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，而 Claude Code 用來開啟 Claude Desktop 的系統命令失敗了。執行 `/desktop` 後，工作階段會留在終端機中；`claude --desktop` 會輸出不含 `Error:` 前綴的訊息，並以狀態 1 結束。

括號內的文字會指出失敗的命令，以及其結束狀態和錯誤輸出的第一行（若有產生）。在 macOS 上該命令為 `open`，如此範例所示；在 Windows 上則為 `rundll32`：

```text theme={null}
Error: Couldn't open Claude Desktop (`open` exited 1: LSOpenURLsWithRole() failed for the URL claude://resume?session=<session-id> with error -10814). Open Claude Desktop and try again.
```

**處理方式：**

* 自行開啟 Claude Desktop，然後再次執行 `/desktop` 或 `claude --desktop`
* 若要閱讀失敗命令的完整錯誤輸出，請使用 `/debug` 開啟偵錯日誌並再次執行 `/desktop`，或執行 `claude --desktop --debug-file <path>`，然後查看偵錯日誌

在 v2.1.285 之前，訊息的結尾為 `Open Claude Desktop and run /desktop again.`。在 v2.1.275 之前，訊息為 `Failed to open Claude Desktop. Please try opening it manually.`，且未說明失敗的內容。

### /terminal-setup 未變更您的 Zed 按鍵對應

您在 Zed 中執行了 [`/terminal-setup`](https://code.claude.com/docs/zh-TW/terminal-config#enter-multiline-prompts)，而 Claude Code 無法完成對您 Zed `keymap.json` 的更新，因此維持該檔案原狀。

每則訊息都會指出您按鍵對應檔的路徑，並在結尾附上供您自行新增的快捷鍵區塊：

```text theme={null}
Couldn't update your Zed keymap, so it was left unchanged.
To add the binding yourself, add this block to the keymap array in <path to keymap.json>:
{ "context": "Terminal", "bindings": { "shift-enter": ["terminal::SendText", "\u001b\r"] } }
```

訊息的第一行會指出原因：

* `Couldn't read your Zed keymap, so it was left unchanged.`：Claude Code 無法讀取該檔案，例如因為檔案權限
* `Your Zed keymap isn't a readable list of keybindings, so it was left unchanged.`：檔案可以正常讀取，但即使允許 `//` 註解和結尾逗號，仍無法解析為快捷鍵區塊的陣列
* `Couldn't back up your Zed keymap; not modifying it.`：Claude Code 無法將檔案複製為其旁邊的 `.bak` 備份，因此未做任何變更
* `Couldn't update your Zed keymap, so it was left unchanged.`：合併後的結果無法驗證為帶有該快捷鍵的有效按鍵對應，因此 Claude Code 將其捨棄而未寫入。帶有重複鍵的快捷鍵區塊可能導致此情況

**處理方式：**

* 將訊息中的區塊複製到訊息所指路徑上 `keymap.json` 的頂層陣列中
* 對於 `isn't a readable list of keybindings`，請修正語法錯誤，或讓檔案的頂層值成為陣列，然後再次執行 `/terminal-setup`

在 v2.1.247 之前，`/terminal-setup` 無法解析使用 `//` 註解或結尾逗號的 Zed 按鍵對應，並會以僅包含其自身快捷鍵的內容取代整個檔案，同時回報快捷鍵已安裝。若要還原被較早版本取代的按鍵對應，請使用[輸入多行提示詞](https://code.claude.com/docs/zh-TW/terminal-config.md#enter-multiline-prompts)中所述的 `.bak` 備份檔案。

### 此連線無法使用 skill 使用情況報告

您透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)，從手機或瀏覽器執行了 [`/skill-doctor`](https://code.claude.com/docs/zh-TW/skills#find-unused-skills)。Claude Code 不會透過 Remote Control 傳送 skill 使用情況報告，而是改為回覆此訊息：

```text theme={null}
Skill usage reports are not available on this connection.
```

**處理方式：**

* 在執行該工作階段之機器的終端機中執行 `/skill-doctor`，或在該處執行 `claude -p "/skill-doctor"`

### 無法透過 Remote Control 選擇自訂輸出風格

您透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 從行動應用程式或網頁執行了 [`/output-style`](https://code.claude.com/docs/zh-TW/output-styles#change-your-output-style)，或者該命令是在轉送至工作階段的訊息中送達。由於這樣的回合可能並非來自帳戶擁有者，Claude Code 在其中只會列出並選擇[內建風格](https://code.claude.com/docs/zh-TW/output-styles.md#built-in-output-styles)，並在命令列出風格或無法辨識您提供的名稱時加上此通知。[自訂風格](https://code.claude.com/docs/zh-TW/output-styles.md#create-a-custom-output-style)名稱會得到與不存在之名稱相同的回覆：

```text theme={null}
Custom output styles can't be selected over Remote Control or from a relayed message. Select one in the session itself, or pick a built-in style here.
```

**處理方式：**

* 選擇內建風格，例如 `/output-style concise`
* 若要使用自訂風格，請在專案的 `.claude/settings.local.json` 中設定 [`outputStyle`](https://code.claude.com/docs/zh-TW/settings-reference#outputstyle)，或在工作階段本身的終端機（若有）執行 `/output-style <style>`

### 輸出風格會儲存到此工作階段不會載入的本機設定

您在設定來源排除 `local` 的工作階段中，嘗試以 `/output-style <style>` 或 `/config outputStyle=<style>` 切換[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)。例如 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 未包含 `"local"` 的 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) 工作階段，以及以未包含 `local` 的 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 值啟動的 CLI 工作階段。這兩個命令都會將風格儲存到 `.claude/settings.local.json`，而這類工作階段永遠不會讀回該檔案，因此 Claude Code 會拒絕，而不是寫入一個不會生效的設定：

```text theme={null}
Output styles are saved to local settings (.claude/settings.local.json), which this session doesn't load, so the style can't be changed here.
```

**處理方式：**

* 將 `local` 加入工作階段的設定來源，然後再次切換
* 在工作階段會載入的設定檔中設定 [`outputStyle`](https://code.claude.com/docs/zh-TW/settings-reference#outputstyle) 鍵，例如專案中的 `.claude/settings.json` 或 `~/.claude/settings.json`。在 TypeScript SDK 中，請改為在內嵌的 `settings` 物件中設定 `outputStyle`；請參閱[啟用輸出風格](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#activate-an-output-style)

### /recap 只在您親自要求時執行

[`/recap`](https://code.claude.com/docs/zh-TW/interactive-mode#session-recap) 請求並非來自您自己的輸入。它出現在從 Slack、Teams 或[專案](https://code.claude.com/docs/zh-TW/claude-projects.md)討論串轉傳至工作階段的訊息中，或出現在[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)或其他程式傳送的提示詞中。

即使轉送的訊息是您自己撰寫的，也會收到此通知。Claude Code 無法判斷轉送或自動化的訊息是否來自執行該工作階段之帳戶的本人，因此會以此通知回覆，而不是提供摘要：

```text theme={null}
/recap only runs when you ask for it yourself in this session: from the terminal, the Claude app or claude.ai/code, or over Remote Control. A message relayed from Slack, Teams or a project thread, or sent by a routine or another program, can't request it.
```

您傳給 `claude -p` 的 `/recap`，或您自己的 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式傳送給其所啟動之工作階段的 `/recap`，都算是您自己的輸入。

**處理方式：**

* 親自開啟該工作階段並在其中執行 `/recap`：在其終端機中、在 [Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)或[行動應用程式](https://code.claude.com/docs/zh-TW/mobile.md)中、在 [claude.ai/code](https://claude.ai/code)，或透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)
* 如果是雲端排程任務或其他程式傳送的，請從該提示詞中移除 `/recap`

### /feedback is disabled by your organization's policy

此訊息表示您組織的政策不允許從 Claude Code 提供產品意見回饋，因此 `/feedback`、`/bug` 與 `/share` 不會開啟意見回饋對話框。訊息會指出您在 Claude Code 提示字元輸入的命令：

```text wrap theme={null}
/feedback is disabled by your organization's policy. To report a bug, open an issue at https://github.com/anthropics/claude-code/issues. Issues are public, so leave out anything confidential.
```

訊息也可能只有第一句。

**處理方式：**

* 若要回報錯誤，請在 [github.com/anthropics/claude-code/issues](https://github.com/anthropics/claude-code/issues) 建立 issue。任何人都可以閱讀該處的 issue，因此請勿包含程式碼、逐字稿及任何其他機密內容。

在 v2.1.302 之前，完整訊息為 `/feedback is disabled by your organization's policy. Contact your organization admin to enable it.`

## Plugin 錯誤

這些錯誤來自 [plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md) 和 [marketplace](https://code.claude.com/docs/zh-TW/plugins/overview.md) 設定。對於不會產生此頁面上其中一則訊息的 plugin 問題，例如無法載入的 marketplace URL 或已安裝但未出現的 plugin，請參閱 [Plugin 疑難排解](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md)。

### plugin eval 目前處於早期存取階段

您執行了 [`claude plugin eval`](https://code.claude.com/docs/zh-TW/plugin-evals) 或 `claude plugin eval init`，它在執行任何操作之前以退出代碼 1 和以下其中一則訊息結束：

```text theme={null}
`plugin eval` is currently in early access
```

```text theme={null}
`plugin eval` is currently unavailable
```

第一則訊息表示您的建置版本早於 v2.1.269，這是該命令正式推出的第一個版本。第二則訊息表示 Anthropic 已在伺服器端關閉該命令；您的機器上沒有任何設定可以將其重新開啟。

**該怎麼做：**

* 執行 `claude --version`，然後執行 `claude update`，並在新的工作階段中再次執行該命令。請參閱 [plugin evals 的需求](https://code.claude.com/docs/zh-TW/plugin-evals.md#requirements)
* 如果您在目前的建置版本上看到第二則訊息，請在執行另一個 `claude update` 後稍後再試一次

### Marketplace 是從不受信任的來源註冊的

Marketplace 是以 [為官方 Anthropic marketplace 保留的名稱](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#marketplace-file) 註冊的，但其註冊的來源不是 `anthropics` GitHub 儲存庫。Claude Code 每次載入或重新整理 marketplace 時都會重新檢查保留的名稱，因此 marketplace 及從中安裝的 plugin 會停止載入。在 v2.1.205 之前，在其名稱變成保留名稱之前註冊的項目會繼續載入。

```text theme={null}
Marketplace "claude-community" is registered from an untrusted source: The name 'claude-community' is reserved for official Anthropic marketplaces. Only repositories from 'github.com/anthropics/' can use this name. To fix it, remove the marketplace and re-add it from the official source.
```

對於來源不是 GitHub 儲存庫或 Git URL 的 marketplace（例如本機目錄），中間句子改為 `can only be used with GitHub sources from the 'anthropics' organization`。`claude plugin marketplace add` 執行相同的檢查，並以 `Failed to add marketplace:` 後跟相同的保留名稱句子拒絕保留的名稱。

**該怎麼做：**

* 如果 marketplace 已經註冊，執行 `claude plugin marketplace remove <name>`，然後從官方 `github.com/anthropics` 儲存庫重新新增它
* 如果您發佈了在其名稱變成保留名稱之前使用該名稱的第三方 marketplace，請重新命名它並要求使用者從您的來源重新新增它
* 請參閱 [Marketplace schema](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#marketplace-file) 下的保留名稱清單

### Marketplace 名稱是保留名稱的另一種拼寫

Marketplace 的名稱本身不是保留名稱，但 Claude Code 將其視為某個保留名稱的另一種拼寫。[保留名稱](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#reserved-name-spellings) 列出哪些拼寫算作保留名稱。Claude Code 在您新增 marketplace 時拒絕這樣的名稱：

```text theme={null}
Failed to add marketplace: "claude.code.plugins" is another spelling of "claude-code-plugins", a reserved marketplace name.
```

當 marketplace 已經以這樣的名稱註冊時，其項目停止載入，而 `/plugin`、`claude plugin install` 和 `claude plugin update` 警告：

```text wrap theme={null}
known_marketplaces.json has an entry named "claude.code.plugins", another spelling of the reserved marketplace name "claude-code-plugins", so it is ignored. Remove it with: claude plugin marketplace remove claude.code.plugins
```

當名稱需要 shell 引用時，新增時的拒絕讀作 `This marketplace's name is another spelling of "<reserved>", a reserved marketplace name. It is not exactly the reserved name it appears to be.`

**該怎麼做：**

* 將 marketplace 重新命名為不拼寫保留名稱的名稱，然後重新新增它
* 對於忽略的項目警告，執行它給出的 `claude plugin marketplace remove` 命令，或從 `~/.claude/plugins/known_marketplaces.json` 移除項目

### Claude Code 拒絕 marketplace 名稱

已註冊的 marketplace 名稱 [冒充官方 Anthropic marketplace](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#reserved-names)，根據該部分列出的規則。

如果 marketplace 是在檢查阻止它之前以這樣的名稱註冊的，marketplace 及從中安裝的 plugin 會停止載入，因為 Claude Code 每次讀取 marketplace 的目錄時都會檢查名稱。當名稱模仿官方名稱時，`claude plugin list` 和 `/plugin` **Errors** 標籤會報告每個受影響的 plugin，訊息開頭為：

```text theme={null}
Claude Code refuses the marketplace name "anthropic-plugins-v2"
```

對於模仿名稱，marketplace 自己的錯誤讀作 `Claude Code refuses this marketplace's name: it looks like one of Anthropic's own`。`claude plugin marketplace add` 拒絕任何冒充名稱，並顯示 `Marketplace name impersonates an official Anthropic/Claude marketplace`。

在 v2.1.282 之前，`claude plugin list` 和 `/plugin` 報告模仿名稱的 plugin 也失敗載入，而沒有將 marketplace 名稱命名為原因。

**該怎麼做：**

* 若要保留由設定檔以 `"source": "settings"` 內嵌宣告的 marketplace，請在移除舊名稱之前先重新命名它，因為移除 marketplace 也會從您的設定檔中刪除其項目。Claude Code v2.1.292 或更新版本會在訊息中列出這些步驟：
  1. 在每個於 `extraKnownMarketplaces` 下列出該 marketplace 的設定檔中，為該項目的鍵及其 `source.name` 設定同一個新的純 ASCII 名稱，且該名稱看起來不像官方名稱。如果管理員透過您組織的受管設定新增該 marketplace，則由管理員執行此步驟
  2. 執行 `claude plugin marketplace remove <old-name>`，或在 `/plugin` 的 **Marketplaces** 標籤中移除舊名稱。這也會卸載其 plugin，並刪除其資料、選項和機密
  3. 再次啟動 Claude Code；如果該檔案是專案的設定檔，請在專案的資料夾中啟動。然後從重新命名後的 marketplace 安裝 plugin
* 若要保留任何其他 marketplace，請等待其維護者重新命名它，然後執行 `claude plugin marketplace update <name>`
* 若要移除 marketplace，請執行 `claude plugin marketplace remove <name>`。這也會卸載從 marketplace 安裝的 plugin，並刪除其資料、選項和機密
* 如果您發佈 marketplace，請在您的 `marketplace.json` 中重新命名它；使用者然後更新 marketplace 而不是移除它

### Marketplace 已從不同的來源新增

您在工作階段中或從 shell 使用 [安裝命令上的 `--marketplace <source>`](https://code.claude.com/docs/zh-TW/plugins/install#add-a-marketplace-and-install-in-one-command) 指定了新的 marketplace 來源。Claude Code 從該來源擷取的目錄，與您已從不同來源新增的 marketplace 名稱相同。Claude Code 保留現有的 marketplace 而不是替換它，plugin 不會被安裝。

```text theme={null}
Marketplace "acme-tools" is already added from a different source (github:acme/plugins). To use this source instead, remove that marketplace first with /plugin marketplace remove acme-tools.
```

**該怎麼做：**

* 如果您已新增的 marketplace 是您想要的，請按名稱從中安裝：`/plugin install <plugin>@<name>`
* 若要切換到新的來源，執行 `/plugin marketplace remove <name>`，然後重試安裝

### Plugin 命令在 shell 命令中參考 user\_config

Plugin hook、[monitor](https://code.claude.com/docs/zh-TW/plugins/components.md#monitors) 或 MCP [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication) 命令參考 `${user_config.KEY}` [plugin 選項](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#user-configuration)，而替換後的字串會被傳遞到 shell。設定的值包含 `$(...)` 、反引號或 `;` 會在該處作為程式碼執行，因此 Claude Code 拒絕啟動該元件而不是替換該值。檢查在命令範本上執行，因此即使尚未設定任何值，錯誤也會出現。在 v2.1.207 之前，該值被替換到 shell 命令中。

措辭取決於哪個介面參考了該選項。Shell 形式的 hook 報告：

```text theme={null}
Hook from plugin formatter@acme-tools references ${user_config.*} in a shell-form command. The substituted value would be re-parsed by the shell. Use exec form instead — {"command": "<executable>", "args": ["${user_config.KEY}", ...]} — or read $CLAUDE_PLUGIN_OPTION_<KEY> from the hook's environment. Command: ./scripts/notify.sh ${user_config.webhook_url}
```

Monitor 報告：

```text theme={null}
Monitor "deploy-status" from plugin deploy-tools references ${user_config.*} in its command. The substituted value would be passed to a shell. Monitor commands cannot safely reference ${user_config.*}; have the monitor script read the value from a config file or prompt instead.
```

MCP `headersHelper` 報告：

```text theme={null}
headersHelper for MCP server 'internal-api' references ${user_config.*}. The substituted value would be passed to a shell; read the value inside the helper script instead (e.g. from an env var set in the server's "env" block).
```

**該怎麼做：**

* 對於 hook，新增 `args` 陣列使其以 [exec 形式](https://code.claude.com/docs/zh-TW/hooks.md#exec-form-and-shell-form) 執行，其中每個 `${user_config.KEY}` 變成一個沒有 shell 的單一引數。或者移除參考並在指令碼內讀取 `$CLAUDE_PLUGIN_OPTION_<KEY>` 環境變數
* 對於 monitor，移除參考並讓 monitor 指令碼從設定檔讀取該值
* 對於 `headersHelper`，將 `${user_config.KEY}` 移到伺服器的 `headers` 欄位（不會進行 shell 解析），或在 helper 指令碼內讀取該值

### Plugin 封存完整性檢查失敗

Plugin 的 marketplace 項目使用具有 `sha256` 釘選的 [`archive` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#archive-plugin-source)，而下載檔案的摘要與釘選不符。Claude Code 拒絕安裝，因此 plugin 快取中沒有任何變更。不符有三個可能的原因：

* 作者計算釘選後，URL 上的檔案已變更
* 作者在 marketplace 項目中輸入了錯誤的摘要
* URL 提供的檔案與作者釘選的檔案不同

```text theme={null}
Plugin archive integrity check failed for https://artifacts.example.com/claude-plugins/my-plugin.zip: expected sha256 6bfa50e3d2e00c052b46abe51fff89346ac803e45771f76dcf6df1ab74cca5e1, got ac52220c0914ef8ca6a602e4a7362f88d30fb021110f72a6d15b68c3fe7df2b7. The archive was not installed. Verify the sha256 in the marketplace entry, or that the URL serves the intended file.
```

**該怎麼做：**

* 如果您發佈 plugin，使用 `shasum -a 256 my-plugin.zip` 或在 PowerShell 中使用 `Get-FileHash -Algorithm SHA256 my-plugin.zip` 重新計算 URL 提供的確切檔案的摘要，並更新 marketplace 項目中的 `sha256`
* 如果您安裝 plugin，執行 `/plugin marketplace update <name>` 以重新整理目錄以防項目已更正，然後重試安裝
* 如果在重新整理後摘要仍然不符，請在安裝前詢問 marketplace 擁有者他們釘選了哪個檔案

### 路徑逃逸 plugin 目錄

Plugin 的其中一個元件路徑導向 plugin 目錄之外，或無法確認其位於 plugin 目錄內，因此 Claude Code 捨棄該路徑並載入 plugin 的其餘部分。對於 plugin 在 `plugin.json` 或其 [marketplace 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries) 中宣告的路徑，訊息中的元件名稱（例如 `commands` 或 `hooks`）命名了宣告該路徑的欄位。

```text theme={null}
commands path escapes plugin directory: ./../shared.md
```

在 `claude plugin` 命令輸出中，相同的錯誤讀作 `Path escapes plugin directory: ./../shared.md (commands)`。

Claude Code 會拒絕字面上指向 plugin 外部的路徑（例如 `../shared-utils`），以及導向 plugin 外部且不屬於 [marketplace 符號連結規則](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#share-files-within-a-marketplace-with-symlinks) 所允許的符號連結。對於符號連結，訊息也會說明路徑解析的位置：

```text theme={null}
commands path escapes plugin directory: ./commands/deploy.md — it resolves to /home/user/shared/deploy.md, outside the plugin directory
```

如果訊息提供了 marketplace plugin 自身檔案之一（例如 `hooks/hooks.json`）的完整路徑，表示 Claude Code 略過了該檔案。當 Claude Code 無法確認該檔案位於 plugin 內，或者對於 [本機 marketplace](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins) 中的 plugin，無法確認該檔案位於該 marketplace 內時，就會發生這種情況。訊息會以下列所示的元件名稱回報這些檔案：

* `hooks/hooks.json`：`hooks`
* `monitors/monitors.json`：`monitors`
* `settings.json`：`settings`
* plugin 根目錄的 `SKILL.md`：`skills`

例如，以下訊息針對的是解析到 plugin 及其本機 marketplace 兩者之外的 `hooks/hooks.json`：

```text theme={null}
hooks path escapes plugin directory: /home/user/my-marketplace/my-plugin/hooks/hooks.json — it resolves to /home/user/dotfiles/hooks.json, outside the plugin directory and its marketplace directory
```

在 macOS 和 Linux 上，Claude Code 也拒絕任何位置包含反斜線的元件路徑，即使路徑保持在 plugin 內。使用 Windows 風格分隔符的元件路徑的 plugin 在 Windows 上載入並在其他平台上觸發此拒絕：

```text theme={null}
commands path escapes plugin directory: ./commands\deploy.md — its path contains a backslash, which is not resolved reliably on this platform
```

在 v2.1.251 之前，Claude Code 載入在 marketplace 項目中宣告的 `commands` 路徑，即使它指向 plugin 目錄外。

在 v2.1.257 之前，對 plugin 宣告之路徑的檢查只查看路徑的拼寫，而不是符號連結導向的位置。

**該怎麼做：**

* 如果您安裝了該 plugin 但並未維護它，請將訊息回報給其作者
* 對於 plugin 宣告的路徑，將參考的檔案移到 plugin 目錄內，並使用 `./` 相對路徑指向它
* 如果該路徑，或 plugin 內位於其上層的資料夾，是導向 plugin 外部的符號連結，請用其所指向內容的副本替換該符號連結
* 如果訊息說 plugin 宣告的路徑包含反斜線，請使用正斜線寫入路徑，例如 `./commands/deploy.md`
* 如果訊息以 `EACCES` 結尾，請恢復您在通往該路徑所指檔案或資料夾的每個目錄上的執行權限。檢查該路徑上方的目錄，然後追蹤您遇到的每個符號連結，並檢查通往其指向位置的目錄。對於任何其他錯誤代碼，請在 [無法檢查之路徑的原因與步驟](#path-could-not-be-checked) 中查詢。
* 若要與同一 marketplace 中的其他 plugin 共享檔案，請使用 plugin 目錄內的符號連結連結它們，遵循 [符號連結規則](https://code.claude.com/docs/zh-TW/plugins/host-marketplace.md#share-files-within-a-marketplace-with-symlinks)

### Plugin 未載入：未讀取其 manifest

Claude Code 無法確認 marketplace plugin 位於 `.claude-plugin/plugin.json` 的 [manifest](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md) 在 plugin 內，因此不會從該 plugin 載入任何內容。對於 [本機 marketplace](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins) 中的 plugin，Claude Code 也無法確認該 manifest 位於該 marketplace 內。此訊息會出現在 `/plugin` **Errors** 標籤中，而訊息結尾的原因說明了 Claude Code 發現的情況。

例如，以下訊息針對的是本機 marketplace 中的 plugin，其 `.claude-plugin` 資料夾是導向 marketplace 外部的符號連結：

```text theme={null}
Plugin not loaded: its manifest /home/user/my-marketplace/my-plugin/.claude-plugin/plugin.json was not read, because it resolves to /home/user/dotfiles/my-plugin/.claude-plugin/plugin.json, outside the plugin directory and its marketplace directory
```

**該怎麼做：**

* 如果原因以 `EACCES` 結尾，請恢復您在通往 manifest 的每個目錄上的執行權限。檢查 manifest 上方的目錄，然後追蹤您遇到的每個符號連結，並檢查通往其指向位置的目錄。對於任何其他錯誤代碼，請在 [無法檢查之路徑的原因與步驟](#path-could-not-be-checked) 中查詢。
* 如果您維護該 plugin，且原因說明了 manifest 解析到的位置，表示 `.claude-plugin` 資料夾或 `plugin.json` 本身是導向該處的符號連結。請用其所指向內容的副本替換該連結。
* 如果您安裝了該 plugin 但並未維護它，請將訊息回報給其作者

### 無法檢查路徑

Claude Code 詢問作業系統 plugin 路徑是否存在，並收到除「找不到」以外的錯誤，因此它不會載入路徑命名的內容。plugin 的多少部分載入取決於哪個路徑失敗：

* Plugin 的其中一個 [預設元件位置](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#standard-layout)（例如 `skills/` 資料夾、`monitors/monitors.json` 檔案或 plugin 根目錄的 [`SKILL.md`](https://code.claude.com/docs/zh-TW/plugins/components#skills)）：plugin 的其他元件仍會載入
* Plugin 自己的目錄：該 plugin 中沒有任何內容載入

對於根本不存在的路徑，您看不到此錯誤。在 `/plugin` 中，錯誤出現在 plugin 下方，並命名路徑和作業系統傳回的程式碼：

```text theme={null}
skills path could not be checked: /home/user/my-plugin/skills (ELOOP)
```

在 `claude plugin list` 中，相同的錯誤讀作 `Path not found: /home/user/my-plugin/skills (skills, ELOOP)`。

產生此錯誤的原因包括：

* `ELOOP`：路徑中的符號連結指向自己或形成迴圈
* `EIO` 或 `ESTALE`：路徑在損壞或陳舊的網路掛載上
* `EACCES`：路徑上方的其中一個目錄拒絕您遍歷它的權限

**該怎麼做：**

* 用真實資料夾替換指向自己的符號連結，或刪除它
* 如果路徑在網路掛載上，重新掛載共享
* 如果程式碼是 `EACCES`，恢復您在路徑上方目錄上的執行權限
* 修復路徑後執行 `/reload-plugins`，或重新啟動 Claude Code，以載入 plugin 或元件

在 v2.1.265 之前，Claude Code 將無法檢查的預設元件資料夾視為不存在，並在沒有錯誤的情況下載入 plugin 而不包含該元件。

### Marketplace 項目路徑不保持在 marketplace 目錄內

Plugin 的 [marketplace 項目](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-entries) 宣告了一個來源路徑，Claude Code 無法將其解析到 marketplace 自己的目錄內的位置，因此 plugin 不會安裝或載入。拒絕涵蓋：

* 絕對的項目路徑、使用 `..` 爬出 marketplace 或拼寫成網路路徑的項目路徑
* 在 macOS 和 Linux 上，項目路徑在前導 `./` 之後的任何地方包含反斜線
* 從遠端來源（例如 git 或 URL）擷取的 marketplace 中的項目，通過解析到 marketplace 目錄外的符號連結到達其目標
* 相對項目在從直接 URL 新增到其 `marketplace.json` 的 marketplace 中：Claude Code 只下載該檔案，因此路徑命名的本機 plugin 檔案不存在。請參閱 [相對路徑的 Plugin 在基於 URL 的 marketplace 中失敗](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugins-with-relative-paths-fail-in-url-based-marketplaces)

`claude plugin install` 報告拒絕如下：

```text theme={null}
Cannot install my-plugin@my-marketplace: its marketplace entry path does not stay inside the marketplace directory (an absolute, climbing, network-shaped, backslash-containing or link-traversing entry, an entry of a fetched marketplace that resolves or opens outside its tree — or a relative entry in a url-catalog marketplace, which has no local directory)
```

當已安裝的 plugin 的項目失敗相同的檢查時，`claude plugin list` 將 plugin 顯示為 `failed to load`，並顯示：

```text theme={null}
Plugin source path refused: ./my-plugin does not stay inside its marketplace directory. Check that the marketplace entry has a plain relative path.
```

**該怎麼做：**

* 如果您維護 marketplace，將項目的 `source` 寫成使用正斜線的純相對路徑（例如 `./plugins/my-plugin`），並保持它跨越的任何符號連結指向 marketplace 目錄內
* 如果您從直接 URL 新增了 marketplace，相對項目無法解析。要求 marketplace 作者使用 [另一個 plugin 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#plugin-sources)，或改為從其 git 儲存庫新增 marketplace

### 無法載入 marketplace 設定

Claude Code 將您新增的 plugin marketplace 保留在 `~/.claude/plugins/known_marketplaces.json` 的登錄檔案中。當 Claude Code 無法使用該檔案時，需要登錄的 plugin 命令（例如 `claude plugin install`）會失敗，並顯示以下兩則訊息之一：

* `Failed to load marketplace configuration`：檔案存在，但不是有效的 JSON，或無法讀取。空檔案也會以這種方式失敗。
* `Marketplace configuration file is corrupted`：檔案是有效的 JSON，但其內容與登錄 schema 不符。

使用空檔案時，`claude plugin install` 報告：

```text theme={null}
✘ Failed to install plugin "my-plugin": Failed to load marketplace configuration: JSON Parse error: Unexpected EOF
```

在 v2.1.246 之前，`claude plugin install` 沒有報告此失敗。

**該怎麼做：**

* 開啟 `~/.claude/plugins/known_marketplaces.json` 並修復 JSON，或修復訊息命名為與登錄 schema 不符的項目
* 如果您無法修復它，刪除檔案或用 `{}` 替換其內容，然後使用 `claude plugin marketplace add <source>` 重新新增每個 marketplace。Claude Code 在您下次在已信任的資料夾中啟動它時，重新註冊您的使用者或受管設定在 [`extraKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#extraknownmarketplaces) 中宣告的 marketplace。

### Plugin 是您的組織所需的

您執行了 `claude plugin disable`，或使用 `/plugin` **Installed** 標籤，以關閉您的組織標記為必需的 [從 claude.ai 同步的 plugin](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)：

```text theme={null}
Plugin "<name>@synced" is required by your organization and can't be disabled here. Contact your admin to change it.
```

Claude Code 不會儲存任何內容，plugin 保持啟用。

當您嘗試停用必需 plugin 所依賴的 plugin 時，Claude Code 以相同的方式拒絕，並顯示命名需要它的必需 plugin 的訊息。

**該怎麼做：**

* 詢問您的 claude.ai 組織的管理員以變更 plugin 在 claude.ai 上的必需狀態

### Plugin 未被卸載

您執行了 [`claude plugin uninstall`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-uninstall)，或在 `/plugin` **Installed** 標籤中選擇了 **Uninstall**，而卸載停止並顯示以 `"<plugin>" was not uninstalled:` 開頭的訊息。如果該冒號之後的文字以 `installed_plugins.json` 開頭而不是命名設定檔案，原因是 `installed_plugins.json` 中的內容此版本的 Claude Code 無法讀取。對於該形式，請參閱 [`installed_plugins.json` 保存此版本無法讀取的記錄](https://code.claude.com/docs/zh-TW/plugins/troubleshooting#installed-plugins-json-holds-a-record-this-version-cannot-read)。

當 Claude Code 從 `enabledPlugins` 移除 plugin 的項目並讀回該範圍的設定檔案時，要麼 plugin 仍在該處被開啟，要麼可以開啟它的檔案無法被讀取或檢查。在設定項目可以將其重新開啟時刪除 plugin 的已儲存選項、機密和資料會遺失它們，因此卸載會停止：plugin 保持安裝，它儲存的任何內容都不會被刪除。

```text theme={null}
✘ Failed to uninstall plugin "formatter": "formatter" was not uninstalled: it is still switched on in /home/user/project/.claude/settings.local.json, although the settings change reported no error. It is still installed. Take it out of "enabledPlugins" in that file yourself, then uninstall it again.
```

訊息的中間部分命名了檔案和原因：

* `it is still switched on in <file>, although the settings change reported no error`：設定寫入報告成功但項目在讀回檔案時仍在那裡
* `it is still switched on in <file>, and the settings change failed (<error>)`：檔案無法被儲存，原因在括號中
* `<file> is there and could not be read`：檔案存在但無法作為設定讀取，例如因為它不是有效的 JSON，所以它可能仍然啟用 plugin
* `<file> (not read: it is on a network path or is a link to one, or could not be checked)`：Claude Code 沒有讀取專案或本機設定檔案，因為檔案或保存它的 `.claude` 資料夾是指向網路位置的連結，或因為它無法檢查該路徑

`claude plugin uninstall` 以退出代碼 1 結束，使用 `--json` 時結果帶有 `failureCode: "settings_still_on"`。`/plugin` 顯示相同的訊息。

**該怎麼做：**

* 遵循訊息的最後一句：修復或替換它命名的設定檔案，或自己從該檔案中的 `enabledPlugins` 移除 plugin 的項目，然後再次執行卸載

### Skipping connection (recent failure cached; retries automatically in 15 min, or edit the plugin config to retry now)

此訊息表示 Claude Code 沒有啟動某個 stdio [由 plugin 提供的 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#plugin-provided-mcp-servers)，因為與該伺服器的連線在不到 15 分鐘前失敗：

```text theme={null}
Skipping connection (recent failure cached; retries automatically in 15 min, or edit the plugin config to retry now)
```

工作階段會在沒有該伺服器工具的情況下繼續，且 15 分鐘結束時，Claude Code 不會在該工作階段中再次嘗試該伺服器。當您在最近一次連線失敗至少 15 分鐘後啟動新的工作階段或 [`claude -p`](https://code.claude.com/docs/zh-TW/headless) 執行時，Claude Code 會再次嘗試該伺服器。

**該怎麼做：**

若要讓 Claude Code 不必等待即再次嘗試該伺服器：

* **在互動式工作階段中**：執行 `/mcp`，選取該伺服器，然後選取 **Reconnect**
* **在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式中**：以伺服器名稱呼叫 TypeScript 中的 [`reconnectMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#methods) 或 Python 中的 [`ClaudeSDKClient.reconnect_mcp_server()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#methods)
* **在 `claude -p` 中**：在與您的執行相同的機器上，以相同的作業系統帳戶及相同的 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 值，啟動載入相同 plugin 的互動式工作階段。在該處從 `/mcp` 重新連線該伺服器。連線成功後，Claude Code 會在您的下一次執行中嘗試連線。
* **如果您正在開發該 plugin**：變更 plugin 的 `.mcp.json` 或 `plugin.json` 中伺服器的 `command`、`args` 或 `env`。Claude Code 會在下一個載入已變更項目的工作階段或 `claude -p` 執行中嘗試連線。

此訊息會取代失敗連線的錯誤。如果新的嘗試也失敗，Claude Code 會回報該次嘗試的錯誤，而不是此訊息。

## 工具錯誤

這些錯誤來自 Claude 的工具呼叫。Claude 會自行修正大多數工具錯誤。當某個錯誤需要您進行變更時，該錯誤的 **處理方式** 清單會說明需要變更的內容。

### No such tool available

Claude 以不在工作階段工具清單中的名稱呼叫了工具。Claude Code 會將錯誤作為該工具呼叫的結果傳回給 Claude，回合則會繼續進行。當 Claude Code 能判斷工具缺少的原因時，它會在工具名稱後面加上一句話，說明原因或指出應改為呼叫的工具，如第二行所示：

```text theme={null}
Error: No such tool available: <tool name>
Error: No such tool available: read. Tool names are case-sensitive: call Read instead.
```

在您恢復工作階段後不久，當 Claude 呼叫某個 MCP 伺服器的工具時，該伺服器可能仍在進行第一次連線嘗試。Claude Code 接著會 [等待該伺服器](https://code.claude.com/docs/zh-TW/mcp.md#tool-availability)，若等待結束時工具仍無法使用，便會傳回此錯誤。在 v2.1.284 之前，這類呼叫會立即失敗，而不會等待。

工具名稱被 Claude Code [截斷至 200 個字元](#tool-use-name-over-200-characters) 的呼叫也會以此錯誤失敗。

**處理方式：**

* 如果只發生一次，您無需採取任何動作。Claude 會讀取錯誤，回合會繼續進行。
* 如果對某個 MCP 伺服器工具的呼叫持續以此錯誤失敗，請在工作階段中執行 `/mcp`，或在 shell 中執行 `claude mcp list`，以檢查該伺服器的 [狀態](https://code.claude.com/docs/zh-TW/mcp.md#server-status)，並從 `/mcp` 重新連線失敗的伺服器。在 Agent SDK 中，請參閱 [錯誤處理](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#error-handling)。

### MCP server connection closed before the tool call was answered

對 HTTP [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) 或 [claude.ai 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai) 的工具呼叫，在伺服器回應之前就失去了連線，因此 Claude Code 無法判斷該工具是否已執行：

```text theme={null}
MCP server "<name>" connection closed before the tool call was answered. The tool may have run: check whether it did before running it again.
```

重複呼叫可能會重複該工具的動作，例如建立第二個 issue。因此，只有在伺服器將該工具標記為可安全重複時，Claude Code 才會自行重複該呼叫一次。

**處理方式：**

* 在該工具所操作的服務中檢查動作是否已發生，例如該工具原本要建立的 issue 或記錄是否存在
* 如果動作已發生，請勿再次執行該工具。Claude 收到的是此訊息而非該工具的結果，因此請告知 Claude 實際結果。
* 如果動作未發生，請要求 Claude 再次執行該工具。您不需要先重新連線伺服器，因為 Claude Code 會在下一次呼叫該伺服器的任一工具時再次連線。如果該連線也失敗，請參閱 [遠端伺服器在工作階段中途斷線](https://code.claude.com/docs/zh-TW/mcp.md#mid-session-drops-of-a-remote-server)。
* 如果您是該伺服器的開發者，且該工具可安全呼叫兩次，請 [將其標記為可安全重複](https://code.claude.com/docs/zh-TW/mcp.md#tool-calls-pending-when-a-connection-closes)，讓 Claude Code 能重複遺失的呼叫

### MCP server is disabled

工具結果中出現此訊息，表示 Claude 呼叫了一個已 [停用](https://code.claude.com/docs/zh-TW/mcp.md#disable-a-server-without-removing-it) 之 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) 上的工具。Claude Code 沒有連線至該伺服器，因此該工具未執行，Claude 收到的是此文字而非結果：

```text wrap theme={null}
MCP server "<name>" is disabled — re-enable it via /mcp to use its tools
```

**處理方式：**

* 如果您原本就打算停用該伺服器，則無需任何動作
* 如果 Claude 需要該伺服器的工具，請在 Claude Code 提示詞輸入框中透過 `/mcp` 將其重新啟用
* 在 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式中，若要重新啟用該伺服器，請在 TypeScript 中呼叫 [`toggleMcpServer()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#togglemcpserver) 並將 `enabled` 設為 `true`，或在 Python 中呼叫 [`toggle_mcp_server()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient) 並將 `enabled` 設為 `True`

### MCP tool call timed out with the server's question unanswered

在 [非互動模式](https://code.claude.com/docs/zh-TW/headless.md) 中，某個 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) 在工具呼叫期間透過 [elicitation](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests) 要求輸入，而該呼叫的時間限制在收到回答之前就已用盡：

```text theme={null}
MCP server "<name>" tool "<tool>" timed out after <N>s. The server asked the user a question, and no answer came before the time limit. Do not call this tool again in this turn. Tell the user that the server's question got no answer, and wait for their reply.
```

在 v2.1.310 之前，結果會以 `timed out after <N>s` 結束，且未提及該問題。

**處理方式：**

* 設定一個會回答伺服器請求的 [`Elicitation` hook](https://code.claude.com/docs/zh-TW/hooks#elicitation)
* 在 TypeScript Agent SDK 應用程式中，讓您的 [`onElicitation`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 回呼在時間限制用盡之前傳回其回答
* 若要給予回答更多時間，請在伺服器的設定項目中以毫秒為單位設定較長的 [`timeout`](https://code.claude.com/docs/zh-TW/mcp#time-limits-on-mcp-tool-calls)，例如 `"timeout": 600000` 代表 10 分鐘
* 改為在互動式工作階段中執行該任務，並自行回答伺服器的 [對話框](https://code.claude.com/docs/zh-TW/mcp.md#respond-to-mcp-elicitation-requests)

### Agent would be spawned with zero tools

subagent 的 [`tools` 清單](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields) 中的每個項目都無法比對到可用的工具，因此 Claude Code 拒絕啟動該 subagent：沒有任何工具，它就無法執行動作。訊息會依問題類型將您的項目分組：

* **Unrecognized**：該項目不符合任何工具名稱，通常是拼字錯誤，例如將 `Grep` 寫成 `Grpe`。
* **Not available to subagents**：該項目指定的是實際存在、但 [subagent 無法使用](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools) 的工具。背景 subagent 保留的內建工具集較小，因此當 subagent 會在背景執行時（這是預設行為），只有前景 subagent 能使用的項目就會歸入此組。如果您列出 `Agent`，訊息會改將其歸入下一組。
* **Matched no tools in this session**：該項目有效，但目前工作階段中沒有任何工具與其相符，例如未連線 GitHub MCP 伺服器時的 `mcp__github__*`，或是已達 [深度上限](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents) 的 subagent 所列的 `Agent`。

省略 `tools` 欄位永遠不會觸發此拒絕。如果您將 `tools` 清單留空，或 `disallowedTools` 移除了其中的每個項目，Claude Code 也會略過此拒絕，並在沒有工具的情況下啟動 subagent。

在 v2.1.208 之前，subagent 會在沒有工具的情況下啟動，並可能傳回空白或令人困惑的結果。

```text theme={null}
Agent 'code-reviewer' would be spawned with zero tools — refusing. Its tools list resolved to nothing: unrecognized [Grpe]. Fix the agent's tools frontmatter or pass a different subagent_type.
```

**處理方式：**

* 對照 [subagent 可用的工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)，修正錯誤中列出的每個項目
* 移除工作階段中不存在之工具的項目，例如來自未連線伺服器的 MCP 工具
* 如果該項目指定的是已連線的 MCP 伺服器，請將該項目與該伺服器 [工具名稱](https://code.claude.com/docs/zh-TW/permissions.md#mcp) 中所拼寫的伺服器名稱進行比對，例如 `mcp__reports__v2__get_totals` 中的 `reports__v2`。對於該伺服器，請寫成 `mcp__reports__v2__*`，也就是 `mcp__` 後接完整名稱再加上 `__*`。若使用較短的 `mcp__reports`（其指定的是名為 `reports` 的伺服器），subagent 將無法取得任何 `reports__v2` 工具
* 對於 [背景 subagent 會捨棄](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools) 的工具（例如 `CronCreate`），請移除該項目
* 若要改為保留 `CronCreate` 這類工具，請 [讓 Claude 等待該 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#let-claude-wait-for-a-subagent)，因為 Claude 等待的 subagent 會在前景執行並保留該工具。如果定義中設定了 `background: true`，請先移除該欄位，因為它會讓 subagent 保持在背景執行
* 刪除 `tools` 欄位而不列出工具，即可讓 subagent 取得每個 [subagent 可用的工具](https://code.claude.com/docs/zh-TW/sub-agents.md#available-tools)
* 對於只包含 `Agent` 的 `tools` 清單，請提高 [深度上限](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents)，或至少再給該 agent 一個其他工具：Claude Code 會在達到該上限時保留 `Agent` 不提供，因此除了 `Agent` 之外沒有任何其他項目的清單會解析為沒有工具

### File is covered by a Read deny rule

Edit 或 Write 工具被呼叫來操作符合 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit) 的路徑，包括在該路徑建立新檔案。這兩個工具都會變更 Claude 必須能夠讀回的內容，因此 Claude Code 會在存取任何檔案之前拒絕該呼叫。NotebookEdit 不受 `Read` 拒絕規則涵蓋。在 v2.1.228 之前，該規則只會封鎖 Edit 工具；在 v2.1.208 之前，只有 `Edit` 拒絕規則會封鎖編輯。

```text theme={null}
File is covered by a Read deny rule in your permission settings and cannot be edited.
```

當 Claude Code 拒絕 Write 工具時，訊息的結尾會改為 `and cannot be written`。

**處理方式：**

* 如果 Claude 應該能夠變更該檔案，請在 `/permissions` 或 [設定](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings) 中移除或縮小該 `Read` 拒絕規則
* 如果該檔案必須保持不變，請保留該規則，並為相同路徑新增 `Edit` 拒絕規則，以同時封鎖 NotebookEdit 工具

### Setting blocks writes outside the working directories

當 Claude 嘗試寫入檔案，而工具呼叫以此訊息失敗時，表示該路徑位於工作階段的 [工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories) 之外，且 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) 已開啟：

```text wrap theme={null}
<path> is outside <dirs>; the permissions.blockWritesOutsideWorkingDirectories setting blocks writes outside the working directories. Ask the user to add the directory with /add-dir, or to remove that setting.
```

Claude Code 在每種權限模式下都會拒絕該寫入。拒絕訊息也可能是：

```text wrap theme={null}
<path>: Writes outside the working directories are blocked (permissions.blockWritesOutsideWorkingDirectories). Add the directory with /add-dir, or remove that setting.
```

**處理方式：**

* 如果 Claude 不應寫入該處，則無需任何動作
* 若要讓 Claude 寫入包含該路徑的現有目錄，請在 Claude Code 提示詞輸入框中執行 `/add-dir <directory>`，或在啟動 Claude Code 時傳入 `--add-dir <directory>`
* 如果該路徑是 Claude Code 設定檔，例如 `~/.claude/settings.json`，請自行編輯。使用 `/add-dir` 新增其目錄並無幫助，因為 Claude Code 接著會 [將其視為設定檔](#writes-to-claude-code-settings-files-are-blocked) 而拒絕寫入。
* 若要讓某個目錄在每個工作階段中都保持可寫入，請在您的使用者設定或受管設定中，將其列於 [`permissions.additionalDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-additionaldirectories) 之下
* 若要關閉 `permissions.blockWritesOutsideWorkingDirectories`，請從每個設定了它的設定檔中將其移除，然後重新啟動 Claude Code
* 如果您的設定檔中都沒有 `permissions.blockWritesOutsideWorkingDirectories`，它可能來自 `--settings` 或主機應用程式。當 Claude Code 無法讀取您 [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#keys-that-fail-closed) 中的 `permissions` 時，也會拒絕這些寫入。請詢問啟動或管理該工作階段的人員。

### Writes to Claude Code settings files are blocked

當 Claude 嘗試寫入檔案，而工具呼叫以此訊息失敗時，表示 Claude Code 將該檔案視為其設定檔之一，且 [`permissions.blockWritesOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockwritesoutsideworkingdirectories) 已開啟：

```text wrap theme={null}
<path>: Writes to Claude Code settings files are blocked while permissions.blockWritesOutsideWorkingDirectories is on, because a settings file can lift that block. While a managed settings folder cannot be resolved, any .json file counts as one.
```

**處理方式：**

* 若要變更設定，請自行編輯該設定檔
* 若要再次讓 Claude 編輯設定檔，請從每個設定了 `permissions.blockWritesOutsideWorkingDirectories` 的設定檔中將其移除，然後重新啟動 Claude Code
* 如果該檔案不是您的設定檔之一，請在 Claude Code 視為設定檔的其他檔案中找出它：
  * **您傳給 `--agents` 或 `--mcp-config` 的檔案**：請自行編輯
  * **[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-considerations) 的儲存副本及與其一同保存的檔案**：請要求 [Owner](https://code.claude.com/docs/zh-TW/server-managed-settings.md#access-control) 在伺服器受管設定中變更該設定。
  * **當 Claude Code 無法判斷 [`managed-settings.d/`](https://code.claude.com/docs/zh-TW/managed-settings#split-a-file-based-policy-across-teams) 資料夾指向何處時的任何 `.json` 檔案**：請要求您的管理員檢查該資料夾

### Path cannot contain null bytes

檔案工具呼叫的路徑或模式引數包含 null 位元組，而檔案系統和搜尋工具無法接受這種字元。Read、Write、Edit、NotebookEdit、Glob 和 Grep 會檢查這一點，訊息會指出工具和引數：

```text theme={null}
Read file_path cannot contain null bytes (\0). Remove the null byte and try again.
```

該工具呼叫會失敗，Claude 會看到錯誤，回合則會繼續進行。

**處理方式：**

* 您無需採取任何動作：錯誤會作為工具的結果傳回給 Claude，而訊息本身會告知 Claude 移除 null 位元組並重試

在 v2.1.281 之前，Read、Write、Edit 或 NotebookEdit 路徑中的 null 位元組會以指出 `Path contains null bytes` 的錯誤結束整個回合，且工具從未執行。

### Command contains an invisible character

[PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool) 拒絕執行包含 U+FEFF 或 U+180E 的命令：

```text theme={null}
Error: command contains the invisible character U+FEFF (byte order mark) or U+180E (Mongolian vowel separator), and was not run. Remove the character, keep the text that needs it in a file that the command reads, or write it as $([char]0xFEFF) or $([char]0x180E) inside a double-quoted string
```

**處理方式：**

* **對於 Claude 撰寫的命令**：您無需修正任何內容。訊息會告知 Claude 如何改寫該命令。
* **對於 skill 或命令檔案**：訊息會接在 `No shell command in <name> was run` 之後。請參閱 [在何處找到該字元並將其移除](#no-shell-command-was-run)。

### File is too large to read as an image

Claude 嘗試使用 [Read 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#read-tool-behavior) 將檔案作為圖片讀取，而該檔案大於 128 MB，也就是 Read 從圖片檔案載入的上限。沒有讀取任何內容，Claude 會收到此錯誤作為工具結果：

```text wrap theme={null}
File is too large to read as an image (the limit is 128MB): <path>. If it is an image, resize it or export a smaller copy, then read that.
```

當路徑是管道或裝置而非一般檔案時，Read 會在收到超過 128 MB 後停止，並改為傳回此錯誤：

```text wrap theme={null}
Cannot read this as an image: <path> is a pipe or a device, not a regular file, and it sent more than 128MB without ending.
```

**處理方式：**

* 如果 Claude 依照 `File is too large` 訊息，接著調整了圖片大小或讀取了較小的副本，則無需任何動作
* 如果 Claude 在錯誤處停止，請自行匯出小於 128 MB 的副本（例如使用較低的解析度），然後讓 Claude 改讀該檔案
* 如果路徑是管道或裝置，請改為讓 Claude 讀取一般的圖片檔案

### subagent\_type is required

```text theme={null}
subagent_type is required: the general-purpose agent is not available in this session. Available agents: ...
```

Claude 在未指定 `subagent_type` 的情況下呼叫了 [Agent 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#agent-tool-behavior)，而此工作階段沒有可供後備使用的 [general-purpose subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#built-in-subagents)。這會發生在兩種設定中：

* 在非互動模式中設定了 [`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1`](https://code.claude.com/docs/zh-TW/env-vars)，這會移除所有內建 subagent
* 工作階段的主執行緒 agent 具有排除了 `general-purpose` 的 [`tools: Agent(...)` 允許清單](https://code.claude.com/docs/zh-TW/sub-agents#restrict-which-subagents-can-be-spawned)

**處理方式：**

* 通常無需任何動作：訊息會列出工作階段中確實存在的 subagent，因此 Claude 可以使用其中之一重試
* 如果 Claude 持續失敗，請將 `general-purpose` 加入 `tools: Agent(...)` 允許清單，或取消設定 `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS`

在 v2.1.235 之前，相同的呼叫會以 `Agent type 'general-purpose' not found` 失敗。

### Memory index is over its read limit

Claude 寫入了 [自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) 索引 `MEMORY.md`，並使其超過其中一項讀取上限：200 行或 25KB。寫入已成功，但在工作階段開始時只會載入前 200 行或 25KB（以先達到者為準），因此每次讀取索引時，超出上限的所有內容都會被捨棄。在 v2.1.210 之前，超過上限的索引會在下次載入時被無聲截斷，且在寫入時不會有任何提示。

```text theme={null}
Error: this write left the memory index at MEMORY.md at 214 lines, over its 200-line read limit. The write succeeded, but everything past the limit is silently dropped each time the index is loaded — entries at the end are already invisible to readers. Rewrite it to under 140 lines now: keep one line per entry, move detail into topic files, and merge or drop stale entries.
```

只有會被載入的內容才會計入上限。YAML frontmatter 和區塊層級的 HTML 註解會在載入索引前被移除，因此不計入測量。在 v2.1.211 之前，Claude Code 會測量原始檔案，即使載入的內容符合上限，frontmatter 或註解也可能觸發此錯誤。

Claude Code 會在寫入後將錯誤傳遞給 Claude，而不是在您的終端機中以橫幅形式顯示，因此您可能只會在逐字稿中注意到它。

當 Claude 的寫入使檔案接近上限但未超過時，Claude Code 會傳回較溫和的提醒，要求壓縮索引，而非此錯誤。

**處理方式：**

* 讓 Claude 重寫 `MEMORY.md`，或要求它這麼做：每個項目保留一行，將細節移至主題檔案，並合併或刪除過時的項目
* 若要自行精簡索引，請參閱 [稽核與編輯您的記憶](https://code.claude.com/docs/zh-TW/memory.md#audit-and-edit-your-memory)

### pkill pattern matches the Claude Code process

Bash 工具呼叫中的 `pkill` 命令使用了符合 Claude Code 程序本身的模式（通常搭配 `-f`），因此 Claude Code 會拒絕該命令，而不是讓它結束工作階段。Claude Code 會在執行 `pkill` 之前以 `pgrep` 測試該模式，若結果中包含其自身的程序 ID 便會拒絕。此檢查僅在 Linux 上執行；在 macOS 上，`pkill` 會原封不動地執行。在 v2.1.214 之前，該命令會執行，且符合的模式會在回合進行中終止 Claude Code 工作階段。

```text theme={null}
pkill: refusing to run — this pattern matches the Claude CLI process (PID 12345). Narrow the pattern, or target your own children with `pkill -P $$ ...`.
```

拒絕訊息會出現在 Bash 工具結果中，而不是以橫幅形式出現在您的終端機中，Claude 通常會自行調整命令。

**處理方式：**

* 縮小模式範圍，使其只符合預期的程序，例如使用目標二進位檔的完整路徑，而非簡短的子字串
* 若要停止由目前 shell 啟動的程序，請將 `pkill -P $$` 與模式搭配使用，這會將比對範圍限制在該 shell 自身的子程序

### Failed to write to a teammate's inbox

Claude Code 無法將訊息寫入 `~/.claude/teams/{team-name}/inboxes/` 下隊員的信箱檔案，因此收件者沒有收到任何內容。當 Claude Code 無法建立或更新該檔案時，寫入就會失敗，例如磁碟已滿、目錄不可寫入，或另一個 agent 持有收件匣鎖定過久。在 v2.1.224 之前，即使寫入失敗，Claude Code 仍會回報訊息已傳送。

錯誤會出現在傳送端 agent 的工具結果中，而不是以橫幅形式出現在您的終端機中，其文字會告知 Claude 重試：

```text theme={null}
Failed to write to researcher's inbox — nothing was sent. Try again, or message the lead.
```

結構化的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 協定訊息也會以相同方式失敗，且錯誤會指出未送達的訊息：當 Claude Code 無法寫入計畫核准、計畫駁回、關閉請求或關閉拒絕時，錯誤內容為 `Failed to write the <message> to <name>'s inbox — nothing was sent`。該清單中的 `plan approval` 是組長核准隊員計畫的決定；隊員提交的計畫則是另一則 `plan approval request` 訊息。該訊息與另外兩則協定訊息有各自的訊息文字與後果：

* `Failed to write the plan approval request to the lead's inbox — plan not submitted; try again`：隊員的計畫從未送達組長，且隊員會停留在 plan mode，直到重新提交成功為止
* `The permission request could not be delivered to the team lead (mailbox write failed)`：隊員的權限請求從未送達組長，因此沒有人核准該工具呼叫
* `The confirmation could not be written to team-lead's inbox.`：關閉核准本身已生效，隊員會結束；只是缺少給組長的確認

當您自行傳訊息給隊員時（在組長工作階段中輸入 `@name` 後接訊息），相同的失敗會以通知形式出現，即 `Couldn't write to @name's inbox — message not sent. Try again.`，且 Claude Code 會將您的文字保留在提示詞輸入框中，以便您再次傳送。

**處理方式：**

* 請傳送者重新傳送訊息；收件匣鎖定的爭用是暫時性的，重試時便會解除
* 檢查可用磁碟空間，並確認 `~/.claude/teams` 及其下的檔案可由您的使用者寫入

### Teammate's agent definition was not restored

Claude 傳訊息給一位已停止的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員，Claude Code 將其恢復，但沒有重新套用它最初據以產生的 [subagent 定義](https://code.claude.com/docs/zh-TW/agent-teams.md#use-subagent-definitions-for-teammates)。此通知會接在傳送端 agent 工具結果中的恢復報告之後，並指出原因。當定義檔案來自沒有已儲存信任的資料夾時，內容如下：

```text wrap theme={null}
Its agent definition was not restored: the folder its definition file came from is not trusted (source: projectSettings), so the teammate is running with the team-essential tools and no custom instructions. To restore it, the user needs to run Claude Code in that folder once and accept the trust dialog (the --debug log names the folder); do not change trust settings on the user's behalf.
```

此檢查適用於專案或 `--add-dir` 目錄之 `.claude/agents/` 目錄中的定義，而接受上層資料夾的信任對話框並不能滿足此檢查。

**處理方式：**

* 在 [除錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md) 指出的資料夾中執行 `claude`，並接受信任對話框。下次 Claude Code 恢復該隊員時，便會重新套用定義；您不需要重新啟動組長工作階段
* 或者，在 `~/.claude.json` 中將 `hasTrustDialogAccepted` 項目設為 `true`，並使用除錯日誌印出的確切 `projects["<path>"]` 鍵

### Only a teammate can approve a shutdown request

Claude Code 拒絕了一項 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 關閉核准，因為傳送它的工作階段並非以隊員身分執行。沒有傳送任何內容，也沒有任何項目被關閉。拒絕訊息會出現在傳送端工作階段的工具結果中：

```text wrap theme={null}
Only a teammate can approve a shutdown request, and this session is not running as one. Nothing was sent. To shut down a teammate, send that teammate a shutdown_request message. The teammate is the one that approves it.
```

**處理方式：**

* 如果拒絕訊息出現在您的組長工作階段中，請先檢查該隊員是否已在此後關閉。拒絕會連同改為傳送 `shutdown_request` 的指示傳回給 Claude，回合則會繼續進行。在互動式組長工作階段中，當隊員核准關閉請求時，會出現 `<name> has shut down.`。
* 如果該隊員仍在執行，請在組長的提示詞輸入框中要求組長關閉該隊員，例如 `Ask the researcher teammate to shut down`。請參閱 [關閉隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#shut-down-teammates)。
* 如果是您自己以 `claude --resume` 恢復的前隊員收到此拒絕，則沒有傳送任何內容。若要結束該工作階段，請在其提示詞輸入框中執行 `/exit`。

### A command-line deny rule cannot be handed to a teammate intact

此訊息表示 Claude Code 沒有在您的 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 中啟動 [分割窗格](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode) 隊員。Claude Code 會透過分割窗格隊員自己的命令列，將組長的命令列拒絕規則傳遞給該隊員，而當隊員會以不同方式解讀其中某條規則時，便會停止：

```text wrap theme={null}
A command-line deny rule cannot be handed to a teammate intact, so the teammate would not enforce it — spawn aborted
```

**處理方式：**

* 在組長工作階段中執行 `/config`，並將 **Teammate mode** 設為 `in-process`，然後要求 Claude 再次啟動該隊員。您不需要找出該規則或重新啟動組長。in-process 隊員會 [在組長即時生效的拒絕規則下執行](https://code.claude.com/docs/zh-TW/agent-teams.md#permissions)。
* 之後從您的使用者設定中取得 [`teammateMode`](https://code.claude.com/docs/zh-TW/settings-reference#teammatemode) 的工作階段也會以 in-process 方式啟動隊員，因為 `/config` 會將此選擇儲存在該處。若要在之後的工作階段中改回分割窗格，請將 **Teammate mode** 設為 `auto`、`tmux` 或 `iterm2`，也就是您先前使用的值。

### Message too large for cross-session delivery

Claude 傳送給您在此機器上另一個工作階段的 [跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 過長，無法傳送。Claude Code 拒絕了它，接收端工作階段沒有收到任何內容。拒絕訊息會出現在傳送端工作階段的工具結果中，而不是以橫幅形式出現在您的終端機中。它會指出兩個大小以及如何讓訊息符合限制：

```text wrap theme={null}
Failed to send to api-worker: Message too large for cross-session delivery: the serialized message is 1,203,844 characters and the limit is 1,048,576. Shorten the message text — put bulk content in a file the recipient can read rather than in the message — or split it into smaller messages.
```

重新傳送相同的文字也會以相同方式失敗。

**處理方式：**

* 要求 Claude 摘要該訊息，或將大量內容放入檔案並傳送該檔案的路徑
* 要求 Claude 將內容拆分成數則較短的訊息

在 v2.1.235 之前，Claude Code 會將過大的訊息回報為已傳送。接收端工作階段會在未讀取的情況下將其捨棄。

### Too many messages to this session just now

Claude 向您在此機器上的某個工作階段快速連續傳送了大量 [跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，而這一連串訊息已達該工作階段收件匣所能接受的量。Claude Code 拒絕了下一次傳送，接收端工作階段沒有從中收到任何內容。拒絕訊息會出現在傳送端工作階段的工具結果中，而不是以橫幅形式出現在您的終端機中：

```text wrap theme={null}
Failed to send to api-worker: Too many messages to this session just now: 30 were sent recently and more would be dropped by its rate limit, so this one was not sent. Batch what remains into one message, or wait a little before sending more.
```

**處理方式：**

* 通常無需任何動作：Claude 會將剩餘內容合併成一則訊息，或在傳送更多訊息前稍候
* 如果是您自己促成了這一連串訊息，請要求 Claude 將剩餘內容合併成單一訊息

在 v2.1.236 之前，Claude Code 會將這些傳送回報為已傳送。接收端工作階段會在未讀取的情況下將其捨棄。

### Cross-session message was dropped at the recipient session's inbox

Claude 傳送了一則 [跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 給您在此機器上的另一個工作階段，而該工作階段的收件匣在該工作階段中的 Claude 讀取之前就將其捨棄。這一行會指出收件者的位址，若收件者提供了原因，則會在破折號後附上原因：

```text wrap theme={null}
Cross-session message was dropped at the recipient session's inbox (recipient: uds:/tmp/cc-socks/13605.sock) and not delivered — its queue of undelivered peer messages was full. Claude was told not to resend right away.
```

一行可以涵蓋數則被捨棄的訊息，此時開頭會使用複數形式，例如 `Cross-session messages (12) were dropped`。若要找出某個位址屬於哪個工作階段，請將其與每個工作階段中 `/status` 顯示的 [`Peer address` 列](https://code.claude.com/docs/zh-TW/cross-session-messaging#the-sessions-inbox-socket) 進行比對。

在破折號之後，這一行會提供下列一個或多個原因：

* `its queue of undelivered peer messages was full`：收件者已持有其佇列所允許的最大數量、來自其他工作階段的未送達訊息
* `you sent faster than that session accepts`：傳送端工作階段的訊息抵達速度，超過收件者從單一傳送者所接受的速度
* `it repeated your previous message`：該訊息與傳送端工作階段不久前傳送給此收件者的訊息完全相同
* `a relay loop between sessions was cut`：該訊息延續了工作階段之間互相傳訊的鏈結，而該鏈結經過收件者的次數過多或長度過長

**處理方式：**

* 假設收件者從未看到被捨棄的訊息。Claude Code 也會如此告知 Claude，並告訴它將仍然重要的內容納入稍後的一則訊息中，而不是立即重新傳送
* 如果您的工作階段會頻繁地互相傳送更新，請要求 Claude 傳送較少但較大的訊息，例如在某個工作階段完成工作時傳送一份報告
* 對於 `a relay loop between sessions was cut`，請自行在其中一個工作階段中輸入下一個指令。Claude 為回應您自己的提示詞而傳送的訊息會開始一條新的鏈結

在 v2.1.238 之前，當收件者的收件匣捨棄訊息時，傳送端工作階段不會收到任何報告。

### Refusing to send a cross-session message

在 Claude Code 將 [跨工作階段訊息](https://code.claude.com/docs/zh-TW/cross-session-messaging.md) 寫入您在此機器上的另一個工作階段之前，它會檢查目標工作階段的收件匣 socket 是否就是該訊息所指定的端點。當檢查失敗時，Claude Code 會在傳送端工作階段中拒絕傳送，目標工作階段不會收到任何內容。對於 Claude 傳送的訊息，拒絕訊息會出現在傳送端工作階段的工具結果中：

```text theme={null}
Failed to send to api-worker: Refusing to send: reply target is a symlink
```

`Refusing to send:` 之後的文字會指出失敗的檢查：

* `reply target is a symlink`：目標工作階段的 socket 路徑上有一個符號連結。Claude Code 不會透過它傳遞，因為該處的連結可能會將訊息重新導向至非目標工作階段建立的端點。
* `cannot vet reply target`：Claude Code 完全無法檢查目標路徑，例如讀取時因權限錯誤而失敗。

**處理方式：**

* 通常無需任何動作：這些檢查可防止訊息送達其所指定工作階段以外的端點，且沒有傳送任何內容
* 如果 `reply target is a symlink` 在某個工作階段重複出現，請檢查是什麼在該工作階段的 socket 路徑上建立了連結，該路徑會顯示在其 `/status` 的 `Peer address` 下

### Refusing to read, write, or search a path

Claude Code 會檢查檔案路徑的 [權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)，然後在工具開啟檔案或開始搜尋時再次確認該解析結果。當它無法確認該路徑仍通往檢查所核准的位置時，Claude Code 會拒絕該操作，而不是跟隨它。拒絕訊息會出現在工具結果中：

```text wrap theme={null}
Refusing to read /path/to/file: its symlink resolution changed after permission was checked (a link on the way now leads somewhere the check did not see). If a link in the working directory is being rewritten concurrently, stop that and retry.
```

每個拒絕都會指出其原因：

* `its symlink resolution changed after permission was checked`：路徑上或 Grep、Glob 搜尋根目錄上的符號連結，在權限檢查與操作之間遭到替換。在讀取拒絕中，括號內的文字會指出哪一項比對失敗。
* `its parent-directory symlink resolution changed after permission was checked`：寫入路徑所經過的某個目錄不再解析至已核准的位置
* `where it leads on disk could not be determined (a link on the way could not be examined, or the links do not resolve)`：Claude Code 無法沿著路徑找到磁碟上的最終位置，例如因為路徑上的符號連結形成迴圈
* `it is a symbolic link. Write to the link's target path instead`：要求的寫入位置本身就是符號連結，例如作為指向 `AGENTS.md` 之符號連結的 `CLAUDE.md`；訊息會引導 Claude 改用該連結的目標
* `Refusing to write through symlink: <path>. Resolve the symlink and pass the real target path explicitly.`：在另一個寫入器開啟檔案時偵測到的相同情況，例如寫入作為符號連結的 `.mcp.json`
* `Refusing to write into symlinked directory: <path>`：存放該檔案的目錄本身就是符號連結，例如連結至其他位置的專案 `.claude/` 目錄
* `a path one of its Read deny rules is written through changed while the search was being prepared. Retry.`：搜尋所適用的某條 `Read` 拒絕規則指定了一個經過符號連結的路徑，而該連結在 Claude Code 準備搜尋時發生了變更
* `it could not be opened (EACCES) — it is unreadable, or is being replaced concurrently.`：搜尋根目錄存在，但無法開啟；括號內的代碼是作業系統錯誤
* `its permission check expired before it ran (too many concurrent file operations). Retry.`：在大量同時進行的檔案操作下，Claude Code 在工具使用核准記錄之前就將其逐出；重試會執行新的權限檢查
* `ripgrep was found only by name on PATH, and a search outside the working directory cannot apply your Read deny rules in that configuration`：Claude Code 無法將 `rg` 二進位檔解析為絕對路徑，因此會拒絕工作目錄以外的搜尋，而不是執行一個您的拒絕規則無法涵蓋的搜尋

**處理方式：**

* 通常無需任何動作：拒絕會作為工具結果傳遞給 Claude，被拒絕的操作不會執行
* 如果符號連結拒絕在某個路徑上重複出現，請找出持續改寫該處連結的來源，例如建置工具或檔案監看程式，或要求 Claude 使用檔案的解析後路徑，而非連結路徑
* 如果 Claude Code 在 Windows 上於 AppContainer 或受限權杖沙箱中執行時，每個檔案都出現此拒絕，請升級至 v2.1.265 或更新版本
* 如果在 macOS 上，對於沒有任何程式在改寫的檔案（例如拖曳到提示詞中的螢幕截圖）出現讀取拒絕，請升級至 v2.1.273 或更新版本
* 對於 ripgrep 拒絕，請使用您的套件管理員安裝 ripgrep，使 `rg` 能在 `PATH` 上解析為絕對路徑，或將搜尋保持在工作目錄之下

在 v2.1.251 之前，Claude Code 只會針對檔案寫入重新檢查路徑的解析結果，因此在權限檢查後遭替換的連結可能會在沒有任何訊息的情況下，將讀取或搜尋重新導向至不同的位置。在這些拒絕中，只有上層目錄、透過符號連結寫入，以及符號連結目錄這幾種寫入拒絕會出現在較早的版本中。

在 v2.1.280 之前，`where it leads on disk could not be determined` 拒絕不會出現。

### Task output swap refused

Claude Code 會將每個 Bash 命令的輸出儲存到其暫存目錄下的檔案中。每次開啟這些檔案時，它都會檢查路徑是否仍通往它所建立的檔案，且沒有符號連結、額外的硬連結或被移動的目錄將其重新導向。此訊息表示該檢查失敗，因此 Claude Code 拒絕了該操作，而不是透過該路徑寫入或讀取輸出。訊息會出現在 Bash 工具結果中：

```text wrap theme={null}
task output swap refused (tasks dir moved or linked): /private/tmp/claude-501/-Users-you-my-project/1f0e62dc-4b0a-4f5e-9c2d-8a7b6c5d4e3f/tasks/b7k2f9m3q.output. To recover: restart Claude Code with CLAUDE_CODE_TMPDIR set to a fresh directory; or, if /private/tmp/claude-501/-Users-you-my-project is a stray directory or a symbolic link that should not be there, remove that entry itself (not what it points to) and restart.
```

括號內的文字會指出失敗的檢查。`output symlink was re-pointed`、`output file identity changed` 和 `not a regular file` 等原因都回報相同的情況：輸出路徑上或沿途的某個東西已不再是 Claude Code 所建立的檔案。只有部分原因會附帶 `To recover:` 句子。

如果檢查在命令仍在執行時失敗，Claude Code 會停止該命令，其結果會回報：

```text theme={null}
Command killed: its output file was replaced or could no longer be verified
```

**處理方式：**

* 升級至 v2.1.260 或更新版本。較早的版本有時會在沒有連結或被移動目錄的情況下顯示此訊息
* 將 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 設為全新的目錄，然後重新啟動 Claude Code
* 或者，檢查 Claude Code 暫存目錄下您專案的目錄，也就是範例訊息中的 `/private/tmp/claude-501/-Users-you-my-project`。如果該路徑是符號連結，或是不應存在的目錄，請移除該連結或目錄本身，而非連結的目標，然後重新啟動 Claude Code
* 如果拒絕重複出現，表示有某個程序在工作階段執行期間，替換、連結或移除 Claude Code 暫存目錄下的項目。請將 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 設為沒有其他程式管理的目錄，然後重新啟動

### Disk full or disk quota used up

請在存放 Claude Code 暫存目錄的磁碟區上釋放空間、inode 或磁碟配額。命令結果中以 `Disk full:`、`Disk quota used up:` 或 `Nearly out of inodes:` 開頭的一行會指出該目錄。

Claude Code 會將每個 Bash 和 PowerShell 命令的輸出儲存到該目錄下的檔案中。如果它因為磁碟區或您在其上的配額已滿而無法建立該檔案，您的命令就不會啟動，Claude 讀到的結果內容如下：

```text wrap theme={null}
The command was not started: this computer's disk is full (ENOSPC) on the volume holding /tmp/claude-501 (Claude Code's temporary directory), so the file that captures command output could not be created there and nothing ran. Free space on that volume, or restart Claude Code with CLAUDE_CODE_TMPDIR set to a directory on another one, then retry. If this is the user's own computer, tell them before deleting anything to make room.
```

`Disk full:`、`Disk quota used up:` 和 `Nearly out of inodes:` 訊息會出現在已執行並以非零代碼結束的命令之後。例如：

```text wrap theme={null}
Disk full: this computer's volume holding /tmp/claude-501 (Claude Code's temporary directory) has 3 MB free, so whatever this command printed was lost and its own writes may have failed with "No space left on device". Free space on that volume, or restart Claude Code with CLAUDE_CODE_TMPDIR set to a directory on another one, then retry. If this is the user's own computer, tell them before deleting anything to make room.
```

**處理方式：**

* 在 macOS 和 Linux 上，於 shell 中執行 `df -h <dir>`，以查看存放該目錄的是哪個磁碟區以及其使用量。`df -i <dir>` 會顯示可用的 inode 數量。`<dir>` 是您的訊息所指出的目錄，例如 `df -i /tmp/claude-501`
* **`Disk full: this computer's volume` 或 `disk is full (ENOSPC)`**：刪除該磁碟區上任何位置中不需要的檔案
* **`Disk quota used up:`、`disk quota is used up (EDQUOT)` 或 `Disk full: a test write`**：刪除您自己在該磁碟區上的檔案，即使該磁碟區仍顯示有可用空間
* **`Nearly out of inodes:`**：刪除該磁碟區上大量的檔案。無論大小，每個檔案都會佔用一個 inode，因此重要的是檔案數量，而非檔案大小
* 或者，將 [`CLAUDE_CODE_TMPDIR`](https://code.claude.com/docs/zh-TW/env-vars) 設為位於有空間之磁碟區上的目錄，然後重新啟動 Claude Code
* 接著讓 Claude 再次執行該命令

在 v2.1.309 之前，訊息內容如下，且適用相同的步驟：

* `Your disk quota is full on the filesystem with Claude Code's temp directory <dir> (EDQUOT)`
* `The filesystem with Claude Code's temp directory <dir>, or your disk quota on it, is full (ENOSPC)`
* `Command output was lost: the temp filesystem at <dir> is full` 或 `... is out of inodes`
* `The command was not started: this computer's disk is full (ENOSPC), so the file that captures command output could not be created. Nothing ran.`，或是帶有 `(EDQUOT)` 的相同訊息。此形式不會指出任何目錄：請查看存放系統暫存目錄（例如 `/tmp`）的磁碟區，或 `CLAUDE_CODE_TMPDIR` 中設定的目錄

在 v2.1.305 之前，Claude Code 因磁碟已滿而無法啟動的命令，只會傳回作業系統的錯誤文字。該文字的內容例如 `ENOSPC: no space left on device, open <path>.output`。

### git is not installed on this Mac

此訊息表示 Claude Code 中的某個步驟需要 git，而它找到的 git 是 Apple 位於 `/usr/bin/git` 的替代程式。提供 git 的開發者工具尚未安裝。

Claude Code 不會啟動該替代程式，而是改為顯示此文字，例如出現在較長的訊息中：

```text wrap theme={null}
git is not installed on this Mac. To install it, run xcode-select --install, then try again.
```

**處理方式：**

* 在 Terminal 中執行 `xcode-select --install`，完成它所啟動的安裝，然後在 Claude Code 中重試您原本在做的事

### File is not valid UTF-8

Claude 對一個位元組無法解碼為 UTF-8 的檔案使用了 Edit 或 NotebookEdit 工具，而 Claude Code 拒絕了該變更。沒有寫入任何內容，因此檔案維持原狀。這些工具會將整個檔案以 UTF-8 存回，這會把它們無法解碼的每個位元組都變成替代字元 `U+FFFD`。訊息會出現在工具結果中：

```text wrap theme={null}
File is not valid UTF-8. It may use a legacy encoding such as Windows-1252, Shift-JIS or GBK, or be binary. This tool saves the whole file as UTF-8, which would replace every byte it cannot decode with U+FFFD. Nothing was written. Make the change with a shell command that reads and writes the file in its own encoding, or ask the user whether to convert the file to UTF-8 first.
```

原本應為 UTF-8 的檔案，只要包含即使一個無效的位元組序列，也會出現此訊息，因為檢查涵蓋的是檔案的整體位元組。

**處理方式：**

* 若要保留檔案目前的編碼，請讓 Claude 依照訊息的指示，使用以該編碼讀取和寫入檔案的 shell 命令進行變更
* 若要繼續使用 Edit 工具編輯該檔案，請將其轉換為 UTF-8，或修正原本應為 UTF-8 之檔案中的無效位元組，然後要求 Claude 再次進行編輯

在 v2.1.296 之前，Edit 和 NotebookEdit 會套用這類編輯，並將無法解碼的每個位元組儲存為 `U+FFFD`。若您使用的是這些版本，請更新 Claude Code。

### The source file is not valid UTF-8 text

Claude 嘗試從一個位元組無法解碼為文字、或其文字已包含替代字元 `U+FFFD` 的檔案發佈 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)，因此 Claude Code 在上傳任何內容之前就拒絕了發佈。訊息會出現在 Artifact 工具結果中，並指出第一個需要修正的位置：

```text wrap theme={null}
file_path: the source file is not valid UTF-8 text (first invalid byte at line 12, column 40). It may be saved in another encoding or contain binary data. Rewrite it as UTF-8, then publish again. Nothing was published.

file_path: the source file has the replacement character U+FFFD at line 12, column 40, usually left where an earlier edit or paste lost a character. Replace it with the intended text (in HTML, write an intended U+FFFD as &#xFFFD;), then publish again. Nothing was published.
```

Claude Code 會將檔案解碼為 UTF-8，若檔案以小端序 UTF-16 位元組順序標記開頭，則解碼為 UTF-16。當這類 UTF-16 檔案無法解碼時，第一則訊息會指出 `UTF-16`，但仍會告知您將檔案重寫為 UTF-8。當指出的位置之後還有更多位置時，訊息會在位置後加上計數，例如 `(+2 more)`。

**處理方式：**

* 通常無需任何動作：Claude 會重寫檔案並再次發佈
* 如果該檔案是您撰寫或匯出的，請將其重新儲存為 UTF-8，並將每個 `U+FFFD` 替換為先前的編輯、貼上或轉換所遺失的字元
* 若要在頁面上顯示刻意使用的 `U+FFFD`，請在 HTML 中將其寫成 `&#xFFFD;`，而不是使用該字元本身

在 v2.1.267 之前，Claude Code 會在未檢查的情況下上傳這類檔案，改由伺服器拒絕發佈。

### Not published: that file is on a network share

Claude 嘗試從路徑指向網路主機的檔案發佈 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md)：

* 在 Windows 上，不位於您啟動時以 [`--add-dir`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 傳入之對應網路磁碟機下的 `\\server\share` 路徑
* 在 macOS 或 Linux 上，自動掛載路徑，例如 `/net/<host>/page.html`

查詢這類路徑會聯繫其所指定的主機，而在 Windows 上，這種聯繫可能會將您的憑證傳送給該主機。Claude Code 會拒絕發佈該檔案，且不會讀取它。拒絕訊息會出現在 Artifact 工具結果中：

```text theme={null}
Not published: that file is on a network share. Publish a file from this session's folders instead.
```

**處理方式：**

* 如果您不需要該檔案本身，則無需任何動作：訊息會告知 Claude 改為從工作階段自己的資料夾發佈檔案
* 若要發佈該檔案本身，請將其複製到本機磁碟上的資料夾，然後再次提出要求
* 在 Windows 上，若要讓 Claude 直接從共用資料夾發佈，請將其對應至磁碟機代號，並在啟動 Claude Code 時傳入該磁碟機。例如在 PowerShell 中，執行 `net use Z: \\server\share`，然後執行 `claude --add-dir Z:\`。Claude 便可以從該磁碟機發佈檔案。在工作階段進行中以 `/add-dir` 新增該磁碟機是不夠的。
* 在 macOS 或 Linux 上，將共用資料夾掛載至某個目錄，例如 `/mnt` 或 `/Volumes` 下的目錄，並從該路徑發佈，而非從自動掛載路徑發佈

### Not published: Claude sent the same content again after a newer version of the artifact turned it away

Artifact 呼叫下方的這行紅字表示 Claude Code 阻止了一次重複的發佈：[artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 並未更新，Claude 用來發佈的檔案也沒有寫入任何內容。除非 Claude 在未發佈的情況下停止，否則您無需採取任何動作。

在工作階段稍早，Claude Code 因為該 artifact 有較新的版本而拒絕了一次發佈，例如由 [編輯者](https://code.claude.com/docs/zh-TW/artifacts.md#let-someone-edit-with-you) 或您的另一個工作階段所發佈的版本。這一行的結尾會說明 Claude 接下來必須做什麼：

```text wrap theme={null}
Not published: Claude sent the same content again after a newer version of the artifact turned it away. Claude needs to work from that newer version first.
Not published: Claude sent the same content again after a newer version of the artifact turned it away. The artifact hasn't changed since, so publishing it once more should go through.
Not published: Claude sent its changes again over the same file after a newer version of the artifact turned them away. Claude needs to work from that newer version first.
Not published: Claude sent its changes again over the same file after a newer version of the artifact turned them away. The artifact hasn't changed since, so publishing once more should go through.
```

**處理方式：**

* **結尾為 `Claude needs to work from that newer version first`**：如果 Claude 在此停止，請要求它擷取該 artifact 的目前版本、將其變更合併進去，然後再次發佈
* **結尾為 `should go through`**：如果 Claude 在此停止，請要求它再次發佈

### Reading a local file from outside the connected folders in a Cowork session

在 Claude Desktop 應用程式中於您的機器上執行的 [Cowork](https://claude.com/docs/cowork/overview) 工作階段裡，Claude 為 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 指定了一個本機檔案。Claude Code 無法確認該檔案是位於工作階段已連接資料夾內的一般檔案：該路徑位於這些資料夾之外、經過符號連結，或其寫法可能指向與表面上不同的檔案。讀取這類檔案需要您的核准，而在無法向您顯示核准卡片的工作階段中（例如設定為略過所有核准的工作階段），Claude Code 會拒絕該讀取。

拒絕訊息會出現在 Artifact 工具結果中；當檔案完全無法被檢查時，則會改為指出該失敗：

```text wrap theme={null}
Reading a local file from outside this session's connected folders, or through a link, needs the approval card, and no one can answer it in this Cowork session. Use a plain file inside the connected folders; do not retry this file in this session.

cannot read file_path (ENOENT) — the file could not be examined, and no one can answer the approval card in this Cowork session. Check that the file exists as a plain file inside the connected folders, then retry with that path.
```

**處理方式：**

* 通常無需任何動作：訊息會告知 Claude 改用已連接資料夾內的一般檔案
* 若要將該檔案原樣放入 artifact，請將其以一般檔案（而非符號連結）的形式複製到工作階段的其中一個已連接資料夾中，然後再次提出要求

### WebFetch cannot fetch localhost

Claude 使用主機名稱不含點的 URL 呼叫了 [WebFetch](https://code.claude.com/docs/zh-TW/tools-reference.md#webfetch-tool-behavior)，例如 `http://localhost:3000` 或像 `http://wiki/` 這樣的純內部網路名稱。WebFetch 會在發出任何請求之前拒絕這些 URL：

```text wrap theme={null}
WebFetch cannot fetch localhost or other hostnames without a dot. To reach a local server, use Bash with curl instead.
```

**處理方式：**

* 通常無需任何動作：訊息會引導 Claude 透過 Bash 工具使用 `curl`，它可以連線至本機與內部網路伺服器

在 v2.1.268 之前，WebFetch 會以通用的 `Invalid URL` 錯誤回報這些 URL。

### WebFetch domain safety check failed

在擷取 URL 之前，WebFetch 會將 URL 的主機名稱傳送至 `api.anthropic.com`，以對照 Anthropic 的 [網域安全封鎖清單](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check) 進行檢查。如果檢查無法完成，WebFetch 就無法確認該網域是安全的，因此不會擷取該頁面，工具結果會改為包含下列其中一則訊息：

```text wrap theme={null}
The safety check for domain example.com is rate-limited (too many domain checks from this network; the limit is shared and can stay exhausted for minutes). Do not retry WebFetch in a loop or sleep to wait it out; continue without this page and report that its safety check was rate-limited. A single later attempt is fine; if that is rate-limited too, stop.

Unable to verify if domain example.com is safe to fetch. This may be due to network restrictions or enterprise security policies blocking claude.ai.
```

* `rate-limited`：檢查端點以 HTTP `429` 回應。訊息會告知 Claude 在沒有該頁面的情況下繼續，且稍後最多只重試一次。Claude Code 不會快取失敗的檢查，因此稍後擷取該網域時會再次執行檢查。如果您網路上的工作階段經常遇到此情況，可以在設定中使用 [`skipWebFetchPreflight: true`](https://code.claude.com/docs/zh-TW/settings-reference#skipwebfetchpreflight) 略過檢查。
* `Unable to verify`：檢查請求失敗、逾時或收到其他錯誤狀態。如果您的網路封鎖了 `api.anthropic.com`，請將該網域加入允許清單，或在設定中使用 [`skipWebFetchPreflight: true`](https://code.claude.com/docs/zh-TW/settings-reference#skipwebfetchpreflight) 略過檢查。

在 v2.1.286 之前，速率限制訊息的內容為 `The safety check for domain example.com is temporarily rate-limited (too many domain checks from this network). Retry after about a minute; retrying sooner will fail the same way.`。
在 v2.1.285 之前，受速率限制的檢查會改以 `Unable to verify` 訊息回報。

## 背景工作階段錯誤

[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)在沒有自己的互動式終端機的情況下執行，因此需要終端機的命令在那裡的行為會有所不同。這些訊息會出現在背景工作階段的逐字稿中、附加到背景工作階段的終端機中、您分派的工作階段或 shell 中，或者對於下面的[worktree-guard 項目](#write-or-command-blocked-because-the-path-cannot-be-safely-resolved)，會出現在任何在 worktree 中隔離或執行 worktree 隔離 subagent 的工作階段中；當訊息特定於某個使用介面時，其項目會說明。

### 在背景工作階段中拒絕的命令

開啟互動式對話框的命令在沒有終端機附加到背景工作階段時無法執行。`/install-github-app`、`/mcp` 設定清單和 MCP 伺服器選單中的身分驗證動作會回應一則訊息。對於 `/install-github-app` 和 `/mcp` 設定清單，工作階段也會在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中的 **Needs input** 下出現，以便您可以找到它、附加並再次執行命令。當終端機附加時，這些命令正常運作。

在 v2.1.216 之前，工作階段在 `/install-github-app` 或 `/mcp` 設定清單被拒絕後不會在 **Needs input** 下出現。在 v2.1.213 到 v2.1.215 中，命令在附加終端機時仍然有效，拒絕訊息告訴您附加並再次執行命令。從 v2.1.208 到 v2.1.212，Claude Code 即使在附加終端機時也拒絕它們，訊息如 `Can't open MCP settings in a background session`；在這些版本上，改為從一般的 `claude` 工作階段執行命令，或升級。在 v2.1.208 之前，它們在背景工作階段內開啟其對話框。僅在 v2.1.208 中，Claude Code 也拒絕了背景工作階段中的 `/model` 選擇器，且 `/upgrade` 列印升級 URL 而不是開啟瀏覽器。

措辭會命名該命令。`/mcp` 設定清單報告：

```text theme={null}
Can't open MCP settings while no terminal is attached to this background session. This session now shows "needs input" in agent view — open it and run /mcp to manage servers, or use `/mcp enable|disable|reconnect <server>` to steer without the panel.
```

**該怎麼做：**

* 從 agent 檢視附加到工作階段並再次執行命令
* 或使用訊息命名的形式，例如 `/mcp reconnect <server>`、`/mcp enable` 或 `/mcp disable`，這些在不附加的情況下有效

### 寫入或命令被阻止，因為路徑無法安全解析

Claude 透過 [worktree 隔離防護](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated)無法解析為一個可驗證位置的拼寫來定址檔案或工作目錄。防護會檢查[任何在 worktree 中隔離的工作階段](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)（無論互動式或背景）以及 [worktree 隔離 subagent](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees) 中的寫入和命令工作目錄。它在檢查操作不會到達共享簽出之前解析符號連結，當解析失敗時，它會阻止操作而不是讓它落在那裡。訊息命名它拒絕的路徑形式以及如何重試：

```text theme={null}
This write was blocked because the path is spelled in a form that cannot be safely resolved (for example through a symlink storing a raw dot segment, a network-share or device-namespace shape, or an unreadable ancestor directory). If the file is inside the worktree /path/to/worktree, address it by its direct symlink-free path instead.
```

被阻止的命令報告其工作目錄的相同原因，並以 `re-run the command from its direct symlink-free path` 結尾。在 v2.1.217 之前，防護比較路徑拼寫而不解析符號連結，因此這些拼寫未被阻止，透過符號連結路由的寫入可能會落在共享簽出中。

**該怎麼做：**

* 通常什麼都不做：完整訊息作為工具錯誤傳遞給 Claude，Claude 使用它命名的直接路徑重試。對於被阻止的檔案編輯，對話檢視只顯示簡短的 `Error editing file` 行；完整訊息出現在逐字稿檢視中，您可以使用 `Ctrl+O` 開啟。被阻止的命令在其命令輸出中列印它。
* 如果同一檔案上的阻止重複，路徑可能透過已提交的符號連結執行，其目標包含 `..`，例如 `docs/current -> ../README.md`；要求 Claude 透過其真實路徑編輯目標檔案，而不是透過連結

### 寫入或命令被阻止，因為路徑命名網路位置

Claude 透過命名不在您機器上的磁碟機、UNC 共享（例如 `\\server\share\file`）或 `/net` 自動掛載路徑的路徑來定址檔案或工作目錄，而工作階段的簽出在本機磁碟上。相同的 [worktree 隔離防護](#write-or-command-blocked-because-the-path-cannot-be-safely-resolved)無法驗證這樣的路徑保持在共享簽出之外，因此它會阻止操作。在 worktree 中隔離工作階段不會解除阻止。訊息命名要改用的路徑形式：

```text theme={null}
This write was blocked because the path is network-shaped (a UNC share or /net automount spelling) while this session's checkout is local. Isolating cannot unblock it. If the file is genuinely inside the worktree /path/to/worktree, address it by its local, plainly-spelled path instead.
```

被阻止的命令報告其工作目錄的相同原因，並以 `re-run the command from its local, plainly-spelled path` 結尾。在 v2.1.217 之前，防護只比較路徑文字，因此透過 UNC 或 `/net` 路徑定址簽出內的檔案未被阻止。

**該怎麼做：**

* 通常什麼都不做：Claude 使用訊息要求的本機拼寫重試

### 命令被 worktree 隔離檢查阻止

Claude 在[在 worktree 中隔離的工作階段](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)中執行了 Bash、[PowerShell](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool) 或 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 命令，Claude Code 因以下原因之一拒絕了它：

* 命令將在主簽出或另一個 worktree 中執行。訊息會說明其工作目錄 `resolved to the shared checkout` 或 `is in a different worktree`。
* Bash 或 Monitor 命令將 git 指向主簽出。
* Claude Code 無法從 Bash 或 Monitor 命令的文字驗證命令執行的任何 git 保持在 worktree 內。從未提及 git 的命令仍然可能因此原因被拒絕，因為展開變數間接參照（例如 `${!name}`）或執行 Bash 函數替換（例如 `${ command; }`）會產生在執行時本身可能是命令的值。

訊息會顯示 `is isolated in the worktree <path>, but this command`，後接原因，例如 Claude Code 無法驗證其文字的命令：

```text wrap theme={null}
This session is isolated in the worktree /path/to/worktree, but this command evaluates ${!x@P} arithmetically inside a construct too complex to verify, which can run a command hidden in a variable's value. Refusing to run it — a worktree-isolated session's git operations must target its own worktree. Split it into plain, separate commands and run them from /path/to/worktree.
```

**該怎麼做：**

* **Git 指向主簽出，或無法驗證的命令文字**：什麼都不做。Claude 讀取訊息並按其最後一句要求的方式重寫命令。如果您要求的命令因其文字中的展開而持續被拒絕，請按字面拼寫標記的值，並從 worktree 內將 git 作為獨立的純命令執行
* 要刻意作用於主簽出，請在工作階段外的終端機中自己執行命令

### This session has no saved transcript

您附加到一個您以 `←` 或 `/background` [移至背景](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)、且在執行自己的任何一個回合之前就已停止的工作階段。Claude Code 找不到您將其移出的那個對話，因此該工作階段沒有可繼續的內容。訊息以此工作階段的 `claude respawn` 命令結尾：

```text theme={null}
This session has no saved transcript — it was stopped before its first response finished. If it was backgrounded from another conversation, that one is still intact; `claude respawn <id>` starts this one fresh.
```

在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中開啟相同工作階段的列，會改為在清單下方顯示 `Press enter again to restart this session fresh`，在該列上第二次按 `Enter` 會使用空白對話重新啟動工作階段。

**該怎麼做：**

* 若要全新重新啟動已停止的工作階段，請使用訊息中的 ID 執行 `claude respawn <id>`，或在 agent 檢視中的其列上按 `Enter` 兩次
* 如果工作階段確實完成了回應，而您在 v2.1.214 之前的版本上仍看到此拒絕，`~/.claude/projects` 中的不可讀資料夾可能會使逐字稿掃描遺漏已儲存的對話；請更新到 v2.1.214 或更新版本，其在掃描期間容許不可讀資料夾

### This session is running in another terminal

您在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中開啟了已停止工作階段的列，而其已儲存的對話已在此機器上的另一個執行中 Claude Code 程序中開啟，因此 Claude Code 拒絕啟動將寫入相同逐字稿的第二個程序。您看到的訊息取決於[持有該對話的是什麼](https://code.claude.com/docs/zh-TW/agent-view.md#opening-a-session-says-the-conversation-is-already-open)：

```text theme={null}
Can't open — this session is running in another terminal
This conversation is already open in another running Claude session — use that one, or close it and try again
```

* **`running in another terminal`**：終端機持有該對話，例如您使用 `claude --resume` 或 `/resume` 繼續它的終端機。列也會顯示 `Open in a terminal`。
* **`already open in another running Claude session`**：另一個非互動式 Claude Code 程序持有它，例如相同對話中尚未退出的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)程序。

**該怎麼做：**

* 在開啟該對話的程序中繼續對話，或退出該程序並再次開啟列

在 v2.1.248 之前，只有 `already open in another running Claude session` 拒絕存在：在終端機中繼續的對話不計為開啟，開啟列會啟動寫入相同對話的第二個 Claude Code 程序。

### This session's saved conversation is no longer on disk

您開啟了在背景服務關閉時結束的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，而[逐字稿清理](https://code.claude.com/docs/zh-TW/settings-reference.md#cleanupperioddays)已移除其已儲存的對話，例如在機器關閉數週後。通常開啟這樣的列會[繼續其已儲存的對話](https://code.claude.com/docs/zh-TW/agent-view.md#sessions-show-as-failed-after-shutdown)。由於沒有可繼續的內容，Claude Code 會拒絕，而不是在不詢問的情況下重新執行工作階段的原始提示詞：

```text theme={null}
This session's saved conversation is no longer on disk (it ended while the background service was off, and old transcripts are cleaned up), so there is nothing to resume. `claude rm 7c5dcf5d` deletes the row; `claude respawn 7c5dcf5d` runs its original prompt again instead.
```

`claude attach <id>` 列印此文字。在 agent 檢視中，頁腳較短，以 `ctrl+x deletes the row` 結尾。

**該怎麼做：**

* 執行 `claude rm <id>` 刪除列。當其中一個[保留案例](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes)適用時，`claude rm` 會改為保留列和 worktree，並說明原因
* 要將工作階段的原始提示詞作為新對話再次執行，請執行 `claude respawn <id>`

在 v2.1.248 之前，開啟這樣的列會重新執行工作階段的原始提示詞，而不是拒絕，將數週前的任務拉回前景。

### Worktree 有未推送到任何地方的提交

您嘗試刪除[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#what-deleting-a-session-removes)，其 worktree 包含 Claude Code 無法確認已在其他地方儲存的提交。Claude Code 保留 worktree 和工作階段列，而不是在您未察覺的情況下銷毀提交。`claude rm` 命名分支和未推送的提交，並說明如何進行：

```text theme={null}
kept 7c5dcf5d — its worktree is still at “/home/you/project/.claude/worktrees/fix-login”
  2 unpushed commits on “claude/fix-login”: a1b2c3d “Fix login flow” and 1 more. They exist on no remote, so deleting the worktree would lose them.
  push them and run 'claude rm 7c5dcf5d' again, or discard the worktree and its commits: claude rm 7c5dcf5d --discard-unpushed a1b2c3d000000000000000000000000000000000@0123456789abcdef0123456789abcdef
```

當 Claude Code 無法總結提交時，詳細行改為顯示 `The worktree has unpushed commits`。在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)中，工作階段的列顯示 `not deleted`，原因相同。

遠端上的提交不會阻止刪除。您的 `origin` 遠端預設分支的本機副本上的提交也不會，只要該分支在您的主簽出（即儲存庫目錄本身而不是 worktree）中簽出。

**該怎麼做：**

* 要保留提交，推送 worktree 的分支，或將其合併到在主簽出中簽出的預設分支，然後再次刪除工作階段
* 要捨棄提交，執行訊息列印的 `claude rm <id> --discard-unpushed` 命令，或在 agent 檢視中的工作階段列上再次按 `Ctrl+X` 兩次。這會移除工作階段和 worktree 以及其分支、未推送的提交和任何未提交的變更。如果刪除再次被拒絕，請依照新的訊息操作。
* 當訊息說 worktree 也由另一個已完成的工作階段記錄時，再次刪除不會捨棄它：推送提交，然後再次刪除工作階段

在 v2.1.268 之前，`claude rm` 將提交摘要放在 `kept` 行本身上。當 `claude rm` 無法總結提交時，`kept` 行會以 `worktree has commits that are not pushed anywhere` 代替摘要。

在 v2.1.260 之前，訊息未命名分支或提交，也沒有捨棄的途徑。您仍然可以刪除工作階段，這會遺失未提交的變更，但會保留分支和提交。使用拒絕訊息列印的路徑執行 `git worktree remove --force --force <path>`，然後執行 `claude rm <id>`。對於已鎖定的 worktree，Git 需要兩次 `--force`。

在 v2.1.248 之前，在主簽出中簽出的預設分支不計算在內：您已經合併到那裡的分支仍然會觸發此拒絕，直到其提交到達遠端。

### Terminal host process died

每個[背景工作階段的](https://code.claude.com/docs/zh-TW/agent-view.md)終端機在背景服務下的主機程序中執行，該程序在服務仍保持其連線時死亡，因此無法連線到工作階段。

在 Linux 和 WSL 上，背景服務每隔幾秒檢查每個主機程序，當程序已退出但其與服務的連線從未關閉時，將工作階段標記為失敗，並在 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md#read-session-state)中的其列上顯示原因：

```text theme={null}
terminal host process died — press Enter to restart
```

從 shell，`claude attach <id>` 會重新啟動已因主機死亡而標記為失敗的工作階段，否則列印原因並退出：

```text theme={null}
Couldn't attach to <id> — This session's terminal host process died (the conversation is saved) — run `claude attach <id>` again to restart it on a fresh host.
```

無論哪種情況，對話都會儲存。

執行 [shell 命令](https://code.claude.com/docs/zh-TW/agent-view.md#run-a-shell-command)的列改為顯示 `terminal host process died — its output is gone; the command was not run again`，`claude attach` 列印 `This command's terminal host process died — its output is gone and the command was not run again`。Claude Code 永遠不會為您重新執行命令。

**該怎麼做：**

* 在 agent 檢視中，在失敗的列上按 `Enter`；工作階段在新主機程序上重新啟動，對話繼續
* 從 shell，再次執行 `claude attach <id>`。Claude Code 列印 `Session <id>'s terminal host died — restarting it on a fresh one…` 並重新開啟工作階段
* 您無法以這種方式重新啟動 shell 命令列；再次分派命令以重新執行它

在 v2.1.247 之前，已死亡的主機程序可能通過背景服務執行的每個活躍性檢查，因此開啟工作階段會無限期地顯示 `opening… · esc to cancel`，而 `claude attach <id>` 會等待而不報告錯誤。

### Session isn't responding

您開啟了[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，背景服務接受了開啟，但約十秒內沒有輸出到達，因此 Claude Code 判定中繼工作階段終端機的程序無法傳遞輸出，並結束嘗試而不是繼續等待。

在 agent 檢視中，Claude Code 在頁腳中提供重新啟動：

```text theme={null}
Press enter again to restart this session — it isn't responding (its conversation is saved and resumes).
```

從 shell，`claude attach <id>` 列印原因並退出：

```text theme={null}
Couldn't attach to <id> — Session isn't responding — `claude stop <id>`, then `claude attach <id>` restarts it (the conversation is saved).
```

Claude Code 永遠不會為您重新啟動執行 [shell 命令](https://code.claude.com/docs/zh-TW/agent-view.md#run-a-shell-command)的列，因為重新啟動會再次執行命令。

**該怎麼做：**

* 在 agent 檢視中，在相同列上再次按 `Enter`。Claude Code 停止無回應的程序並重新啟動工作階段，對話繼續。沒有第二次按下，什麼都不會停止
* 從 shell，執行 `claude stop <id>`，然後 `claude attach <id>`
* 對於 shell 命令列，在 agent 檢視中按 `Ctrl+X` 或執行 `claude stop <id>` 停止它；再次分派命令以重新執行它

### Session was stopped while the respawn was in flight

您開啟了[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，其程序未執行，而當 Claude Code 重新啟動它時，另一個 Claude Code 程序停止了它，例如在另一個終端機中的 `claude stop`。Claude Code 保持工作階段停止：

```text theme={null}
Session <id> was stopped while the respawn was in flight
```

開啟您剛分派、其程序仍在啟動中的工作階段時，會改為等待該程序。在 v2.1.246 之前，在那一刻開啟它可能會停止它並顯示此訊息。

**該怎麼做：**

* 如果您沒有停止工作階段，在 agent 檢視中再次開啟其列或執行 `claude respawn <id>` 重新啟動它
* 如果您自己停止了它，就不需要再做任何事：工作階段保持停止

### 工作階段 agent 不再可用

您繼續了一個執行[自訂 agent](https://code.claude.com/docs/zh-TW/sub-agents.md#invoke-subagents-explicitly) 的工作階段（使用 `--agent` 或 `agent` 設定啟動），而 Claude Code 未找到該名稱的 agent。當您已[信任該工作區](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)時，它會先搜尋工作階段的原始目錄，然後搜尋您繼續時所在的目錄。工作階段仍然會繼續，但使用預設工具，因此 agent 的工具限制不再適用：

```text theme={null}
This session was running agent 'code-reviewer', which is no longer available (no agent by that name in /home/you/project). Continuing with the default tools and system prompt — the agent's tool restrictions no longer apply. To restore it, re-create the agent, or resume with an explicit --agent <name>.
```

警告只列出 Claude Code 搜尋過的目錄，無論您是喚醒[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)、執行 `/resume` 或 `claude --resume`，還是在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中繼續，它都會出現在繼續的對話中；在非互動模式中它也會輸出到 stderr。使用 `--input-format stream-json` 的工作階段不會顯示它，因為 Agent SDK 在啟動後才提供 agent。

Claude Code 不會將此備援儲存到工作階段，因此警告會在每次繼續時重複出現，直到您採取行動。內建 `claude` agent 不會觸發警告，因為改用預設工具集對它沒有任何變化。在 v2.1.216 之前，Claude Code 會無聲地以預設 agent 繼續，且查詢僅涵蓋您繼續時所在的目錄，因此從另一個目錄繼續時，專案範圍的 agent 就會遺失。

**該怎麼做：**

* 在工作階段專案中的 `.claude/agents/<name>.md`，或針對個人 agent 在 `~/.claude/agents/<name>.md` 重新建立 agent 檔案，然後再次繼續
* 或使用 `--agent <name>` 繼續，指定確實存在的 agent，以改為作為該 agent 執行工作階段
* 如果 agent 是專案範圍的，而您尚未信任工作階段的原始目錄，請在那裡執行 Claude Code 一次，接受信任對話框，然後再次繼續

### This session restarted after its next /loop wakeup was due

[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中的[自行調節步調的 `/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#let-claude-choose-the-interval) 已停止。工作階段的程序在迴圈等待下一次喚醒時結束，而該次喚醒在工作階段的[下一個程序](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)啟動之前就已到期。錯過的喚醒不會延遲觸發。通知會說明工作階段重新啟動時該次喚醒已逾期多久：

```text theme={null}
This session restarted 12m after its next /loop wakeup was due, so that wakeup will not fire. The loop stays stopped until Claude schedules it again: reply to continue it.
```

在 v2.1.295 之前，迴圈在此情況下會停止而不顯示通知。

**該怎麼做：**

* 若要繼續迴圈，請[回覆該工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#peek-and-reply)並如此說明，例如 `keep the loop running`。Claude 會連同您的回覆一起讀取通知，並可以排程下一次喚醒
* 如果您已不需要該迴圈，則什麼都不用做。它已經停止

### No LLM gateway: a gateway set in your shell isn't passed to a session opened from another folder

顯示此訊息的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)並未使用您的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)：它沒有取得閘道的位址，因此其請求會失敗。此訊息會出現在對話中取代 Claude 的回覆，並填入您工作階段的 ID 和資料夾：

```text wrap theme={null}
No LLM gateway: a gateway set in your shell isn't passed to a session opened from another folder. To fix, run `claude respawn abc12345` from ~/project in another terminal where your gateway is set, or set ANTHROPIC_BASE_URL and its API key or token in a settings file's env block.
```

當您附加到該工作階段時，其提示字元下方的通知會顯示簡短形式 `No LLM gateway: opened from another folder · respawn from ~/project`。

您在 `ANTHROPIC_BASE_URL` 設定為您的閘道時，從訊息所指資料夾以外的資料夾分派、喚醒或重新啟動了該工作階段。關於在 shell 中匯出的閘道確實會傳遞到背景工作階段的情況，請參閱 [LLM 閘道](https://code.claude.com/docs/zh-TW/agent-view.md#llm-gateway)。

**該怎麼做：**

* **您在設定檔中設定了閘道的專案中使用 agent 檢視**：將 `ANTHROPIC_BASE_URL` 及其 API 金鑰或 token 放入[設定檔的 `env` 區塊](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-in-a-settings-file)。請使用 `~/.claude/settings.json`，或工作階段自身專案中的 `.claude/settings.local.json`，重新產生的工作階段都會讀取這兩者。然後從任何資料夾在您的 shell 中執行 `claude respawn <id>`。
* **您在終端機中匯出了閘道**：在已匯出閘道變數的終端機中，`cd` 到訊息所指的資料夾，並執行訊息中的 `claude respawn <id>` 命令。工作階段會從其已儲存的對話重新啟動。
  * 只有當 [supervisor](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process) 本身是從匯出了相同閘道的 shell 啟動時，閘道才會傳遞到工作階段。如果 supervisor 不是如此，請依照 [Dispatch fails with `Could not resolve authentication method`](https://code.claude.com/docs/zh-TW/agent-view#dispatch-fails-with-could-not-resolve-authentication-method) 所述，從該終端機重新啟動它，然後再次執行 respawn 命令。

在 v2.1.302 之前，處於此情況的背景工作階段會改為顯示登入錯誤，例如 [`Not logged in · Please run /login`](#not-logged-in)，且不會指出資料夾。

### CLAUDE\_CODE\_PROCESS\_WRAPPER 啟動器錯誤

[`CLAUDE_CODE_PROCESS_WRAPPER`](https://code.claude.com/docs/zh-TW/corporate-launcher) 已設定，但其值無法使用，因此 Claude Code 拒絕啟動受影響的程序，而不是在沒有啟動器的情況下執行它。設定問題會以變數名稱開頭並說明原因的訊息報告，例如：

```text theme={null}
CLAUDE_CODE_PROCESS_WRAPPER: launcher `/opt/corp/launcher` is not an executable regular file
```

啟動後未以 Claude Code 替換自己就退出的啟動器，會使其正在啟動的工作階段失敗，該工作階段在 agent 檢視中的列會報告啟動器 `must exec, not daemonize`，後接啟動器列印的任何內容。因啟動器而無法啟動或無法連線到背景服務的工作階段，會將啟動器問題作為 `Couldn't reach the background service (...)` 內的原因報告。

**該怎麼做：**

* 將變數設定為以呼叫 `exec "$@"` 結尾的可執行檔的絕對路徑。有關完整合約，請參閱[啟動器合約](https://code.claude.com/docs/zh-TW/corporate-launcher.md#the-launcher-contract)
* 檢查 `/status`，其在 Self-exec 項目中顯示已解析的啟動命令，並在執行中的背景服務不符合時發出警告，或從 shell 執行 `claude daemon status`
* 在[設定](https://code.claude.com/docs/zh-TW/corporate-launcher.md#set-up-the-launcher)的 `env` 區塊中修正值後，使用 `claude daemon stop --any` 重新啟動背景服務，以便下次分派時啟動經過包裝的服務

### 啟動背景工作階段時 EUNKNOWN

Windows 以沒有標準名稱的錯誤代碼拒絕啟動程式，因此失敗表現為 `EUNKNOWN`。通常的觸發原因是軟體限制原則（例如群組原則或 AppLocker）阻止正在啟動的程式。當您使用 `/background` 或 `claude --bg` 啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)時，會出現此錯誤：

```text theme={null}
Couldn't reach the background service (spawn background service: EUNKNOWN: unknown error, uv_spawn) — run 'claude daemon status'
```

在某些帳戶上，訊息會以 `daemon` 取代 `background service`。

在 npm 安裝上，在 `npm install -g @anthropic-ai/claude-code` 替換二進位檔案時出現的 `EUNKNOWN` 與[重新安裝期間的 `EACCES`](#eacces-when-starting-a-background-session) 有相同的原因，並會在安裝完成後重試時消除。

Claude Code 透過 PowerShell 啟動背景服務，以便服務在關閉終端機後仍能存活；已安裝 PowerShell 7 時使用它，否則使用 Windows PowerShell 5.1。當兩個 PowerShell 都無法執行時，Claude Code 改為直接啟動服務，因此只阻止 PowerShell 的原則不會導致此錯誤。

在 v2.1.212 之前，Claude Code 僅使用 Windows PowerShell 5.1 啟動服務，因此任何群組原則阻止 PowerShell 5.1 的機器都會失敗，訊息為 `Couldn't start the session — EUNKNOWN: unknown error, uv_spawn`，即使已安裝 PowerShell 7 也是如此。

**該怎麼做：**

* 如果訊息顯示 `Couldn't start the session`，請升級到 v2.1.212 或更新版本。在較早的版本上，您也可以先在另一個終端機中執行 `claude daemon run`，然後再次啟動背景工作階段。該命令在終端機的前景中執行背景服務，因此服務僅在該終端機保持開啟時持續運作。
* 如果 npm 安裝正在替換二進位檔案，請等待它完成，然後再次啟動背景工作階段
* 如果錯誤在 v2.1.212 或更新版本上出現，且沒有 npm 安裝正在執行，請向您的 Windows 管理員確認是否有限制原則阻止 Claude Code 可執行檔
* 如果關閉終端機時背景服務停止，表示 Claude Code 是在沒有 PowerShell 的情況下啟動它的。請安裝 PowerShell 7，或要求您的管理員解除對 PowerShell 的阻止，以便服務可以在終端機關閉後繼續運作。

### 啟動背景工作階段時 EACCES

Claude Code 無法執行其自己的二進位檔案來啟動託管背景工作階段的[背景服務](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)。在 npm 安裝上，這通常意味著 `npm install -g @anthropic-ai/claude-code` 在那一刻正在替換二進位檔案，無論是您執行的還是[自動更新程式](https://code.claude.com/docs/zh-TW/setup.md#auto-updates)執行的。當您從 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)開啟工作階段時，會出現此錯誤：

```text theme={null}
Couldn't start the background service — spawn background service: EACCES: permission denied, posix_spawn '/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude'
```

當您使用 `/background` 或 `claude --bg` 啟動工作階段時，相同的原因出現在 `Couldn't reach the background service (...)` 內。在相同的重新安裝期間，錯誤可能改為顯示另一個代碼，例如 `ENOENT` 或 `ENOEXEC`，或 Windows 上的 `EUNKNOWN` 或 `EPERM`；在多次重試後仍持續的 `EUNKNOWN` 有[不同的原因](#eunknown-when-starting-a-background-session)。

在 npm 安裝上，Claude Code 會等待重新安裝完成並自動重試：最多十秒，而當機器上明顯仍有 Claude Code 的 npm 安裝在執行時最多兩分鐘，這涵蓋了另一個 Claude Code 程序正在下載更新的情況。當安裝超過該等待時間時，失敗訊息會提及更新，而不是單純的錯誤代碼：

```text theme={null}
Claude Code is being updated by npm on this machine (still not runnable after 2 min, EACCES) — try again when the update finishes
```

在 v2.1.257 之前，等待在所有情況下都在十秒停止，因此此錯誤會在另一個 Claude Code 程序仍在下載更新時出現。在 v2.1.246 之前，Claude Code 會立即失敗，不會等待。

**該怎麼做：**

* 等待幾秒，然後開啟工作階段或再次分派。當訊息說 Claude Code 正在更新時，請在更新完成後重試。
* 如果錯誤在沒有 npm 安裝執行時持續，表示您的使用者無法執行已安裝的二進位檔案。請檢查其權限及其目錄的權限，或重新安裝 Claude Code。

### 背景服務在可連線之前退出

Claude Code 作為[背景服務](https://code.claude.com/docs/zh-TW/agent-view.md#the-supervisor-process)啟動的程序在接受連線之前就退出了，因此 Claude Code 無法開啟您的工作階段。當服務在退出前列印了錯誤時，括號中的原因會提供退出碼或訊號以及服務列印的第一行，該行指出使其停止的原因：

```text theme={null}
Couldn't reach the background service (background service exited before it became reachable (exit code N): <the service's first error line>) — run 'claude daemon status'
```

當您從 [agent 檢視](https://code.claude.com/docs/zh-TW/agent-view.md)開啟工作階段時，相同的原因接在 `Couldn't start the background service —` 之後。當服務在退出前未列印任何內容時，訊息改為顯示 `nothing on stderr`。

Claude Code 會連同服務的錯誤行一起報告失敗。在 v2.1.246 之前，失敗僅在等待 45 秒後才以 `background service did not become reachable within 45s` 的形式出現，且不含服務的錯誤行。

兩種引用的原因有已知的成因：

* `Error: claude native binary not installed.`：npm 安裝在那一刻正在替換 Claude Code 二進位檔案，因此服務執行了 npm 的佔位檔。請在安裝完成後重試；如果在沒有安裝執行時該行仍持續出現，請[完成 npm 安裝](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#native-binary-not-found-after-npm-install)。在 v2.1.257 之前，macOS 上的 npm 自我更新會在安裝期間的每次啟動時產生此失敗。
* Windows 上每次啟動時都出現 `nothing on stderr` 且退出碼為 1：`daemon.lock` 指向一個 Claude Code 既無法傳送訊號、也無法證明已消失的程序，因此每個新服務都判定另一個服務持有鎖定並退出。Claude Code 能證明其寫入者已消失的鎖定會自動被替換，不會產生此失敗。當失敗在每次啟動時重複出現時，請刪除 `~/.claude/daemon.lock`，然後開啟工作階段或再次分派。在 v2.1.257 之前，這樣的鎖定會阻止每次啟動，直到您刪除該檔案。

**該怎麼做：**

* 如果訊息引用了一行，請修正其指出的問題，然後開啟工作階段或再次分派。下次嘗試會再次啟動服務
* 執行 `claude daemon status` 檢查現在是否有服務正在執行

### 啟動背景工作階段時工作目錄不再存在

您啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)時所在的目錄在工作階段啟動期間被移除。Claude Code 不會啟動工作階段，訊息會指出遺失的目錄：

```text theme={null}
Couldn't start a background session (working directory no longer exists or is not accessible: /tmp/demo)
```

在 v2.1.257 之前，工作階段看似已啟動，然後在 agent 檢視中顯示為失敗列，原因相同。

在 v2.1.281 之前，當目錄在您啟動工作階段之前就已消失時，也會出現此訊息。該情況會報告 [`could not be resolved on disk`](#workspace-not-trusted-when-dispatching-a-background-session)。

**該怎麼做：**

* 重新建立訊息指出的目錄，或從存在的目錄分派，然後再試一次

### 分派背景工作階段時工作區未信任

您在尚未[信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)的目錄中啟動或重新啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，而工作區信任對話框無法出現來詢問您。Claude Code 不會啟動工作階段：

```text theme={null}
Workspace not trusted. Run `claude` in /path/to/project once and accept the trust prompt, then retry.
```

若從工作階段自己目錄中的終端機執行，相同的命令會改為顯示信任對話框，並在您接受後啟動工作階段。此訊息出現在無法顯示對話框的地方，例如在指令碼中，或當您從非其自身的目錄重新啟動工作階段時。

兩種變體指出不同的原因：

* **`The home directory is trusted one session at a time`**：工作階段的目錄是您的家目錄。Claude Code 永遠不會儲存家目錄的信任，因此在較早的工作階段中於該處接受對話框並不算數。
* **`<path> could not be resolved on disk`**：Claude Code 無法在磁碟上找到工作階段的目錄。

在 v2.1.286 之前，在 Windows 上，如果信任記錄儲存時路徑的大小寫不同，此訊息也可能出現在您已信任的目錄中。請更新到 v2.1.286 或更新版本。

**該怎麼做：**

* 在訊息指出的目錄中執行 `claude` 並接受信任對話框，然後再次執行命令
* 對於家目錄訊息，請從家目錄中的終端機執行命令，以便對話框可以出現，或改為從專案目錄啟動工作階段
* 對於 `could not be resolved on disk` 訊息，請重新建立目錄，或從存在的目錄啟動新工作階段

## 包裝程式和 IDE 錯誤

這些錯誤來自啟動 Claude Code 的程式，例如 IDE 擴充功能或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 應用程式，而不是來自 Claude Code 本身。

### Claude Code 程序以代碼 N 結束

底層 `claude` 程序以非零代碼結束。結束代碼本身不會說明失敗的原因：真正的錯誤在於程序自己的輸出，包裝程式會在捕獲時附加該輸出，否則將其保留在日誌中。

```text theme={null}
Error: Claude Code process exited with code 1
```

在 Windows 上，原生組建可能在轉換完成後立即以代碼 `4294967295` 結束。當該結束發生在轉換邊界，沒有訊息等待且沒有背景工作執行時，[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)會安靜地關閉工作階段，而不是顯示此錯誤。您的下一條訊息會繼續對話。

在 v2.1.273 之前，擴充功能在每個轉換邊界都會顯示該結束的錯誤，即使沒有任何內容遺失。

**該怎麼做：**

* 在 VS Code 中，按照錯誤顯示的**檢視輸出日誌**連結查看底層失敗
* 在 Agent SDK 應用程式中，在訊息迴圈周圍捕獲錯誤。[CLI 程序結束](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md#cli-process-exit)下的項目涵蓋了您的程式碼在每個 SDK 語言中接收的內容。
* 在終端機中的同一專案中執行 `claude`。失敗通常會在那裡重現，並顯示其真實錯誤訊息，您可以在此頁面上查詢。
* 在終端機中執行 `claude doctor` 以檢查安裝和設定

### 無法在 PATH 上找到 Claude CLI

當您在整合終端機中開啟 Claude Code、終端機的殼層是 PowerShell，且擴充功能無法在 PATH 上找到已安裝的 `claude` 可執行檔時，[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)會在 Windows 上顯示此錯誤。擴充功能拒絕啟動 Claude Code，直到它在 PATH 上找到已安裝的 `claude`。

```text theme={null}
Failed to run Claude Code: Error: Could not locate the Claude CLI on PATH. Launching by name in a PowerShell terminal would run a 'claude' from the open folder instead of the installed CLI, so the launch was blocked. Make sure the Claude CLI's install directory is on your system PATH (not only your PowerShell profile), then restart VS Code and try again. VS Code reads PATH when it starts, so PATH changes take effect only after a restart.
```

**該怎麼做：**

* 在 VS Code 外開啟新的 PowerShell 視窗並執行 `where.exe claude`。如果它沒有列印路徑，CLI 不在您的 PATH 上：按照[驗證您的 PATH](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#verify-your-path)新增其安裝目錄。如果它列印了路徑，該項目來自您的 PowerShell 設定檔或來自 VS Code 尚未取得的 PATH 變更；接下來的兩個步驟涵蓋了這些情況。
* 將 PATH 項目設定為使用者或系統環境變數，而不是在您的 PowerShell 設定檔中。擴充功能不執行您的設定檔，因此只存在於那裡的 PATH 編輯永遠無法到達它。
* 變更 PATH 後重新啟動 VS Code。擴充功能檢查 VS Code 在啟動時捕獲的 PATH，因此 PATH 變更只有在重新啟動後才會生效。

### The Claude Code program for this computer could not be found

[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)尋找其內部隨附的 Claude Code 副本，但找不到為您的電腦建置的版本。訊息會指出您的電腦所需的建置：

```text theme={null}
The Claude Code program for this computer, the Linux (linux-x64) build, could not be found.
```

**該怎麼做：**

* 如果訊息說明了擴充功能所包含的建置，表示您安裝的是其他平台的擴充功能套件：請安裝為訊息中指出的建置所製作的套件
* 如果訊息沒有說明擴充功能所包含的建置，請從編輯器的 Extensions 檢視重新安裝 Claude Code 擴充功能
* 或者，在上述任一情況下，將 [`claudeCode.claudeProcessWrapper`](https://code.claude.com/docs/zh-TW/vs-code#extension-settings) 設定為另外安裝的 `claude` 二進位檔

在 v2.1.290 之前，此錯誤顯示為 `Unsupported platform: <platform>-<arch>. No compatible Claude Code binary found.`

### Claude Code 的連線在此訊息完成前結束

[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)將您的訊息傳送到 `claude` 程序，連線在程序確認或完成訊息之前結束，且沒有錯誤。擴充功能無法判斷訊息是否已被處理，因此它要求您再次傳送訊息：

```text theme={null}
The connection to Claude Code ended before this message completed — it may not have been processed, so please send it again.
```

**該怎麼做：**

* 再次傳送訊息。下一條訊息會啟動一個新的 `claude` 程序，繼續對話。
* 如果它重複發生，在同一專案中的終端機中執行 `claude`。持續結束程序的失敗通常會在那裡重現，並顯示其真實錯誤訊息。

## Rewind 警告和錯誤

這些訊息來自 [`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing) 程式碼還原。`Restored the code, but skipped N files` 是一個警告，表示 Claude Code 跳過了某些路徑。`No files were restored` 是一個錯誤，表示它沒有還原任何內容。

### Restored the code, but skipped files

`/rewind` 程式碼還原跳過了一個或多個追蹤的路徑，而不是透過它們進行寫入或刪除。Claude Code 在以下情況下會跳過路徑：

* 它是或已成為符號連結、硬連結或其他非一般檔案
* 其目錄自檢查點以來已變更
* 其備份無法安全讀取

跳過的路徑保留其目前的內容。在 v2.1.216 之前，`/rewind` 會透過追蹤路徑上的連結進行寫入和刪除，並且不會報告部分還原。

```text theme={null}
Restored the code, but skipped 2 files: the tracked path is (or became) a link or other non-regular file, its directory changed since the checkpoint, or its backup could not be safely read. Skipped files were left untouched — run with --debug for the paths.
```

**該怎麼做：**

* 識別哪些檔案被跳過，以便您可以使用下面的步驟處理每個檔案。訊息只提供計數；位於 `~/.claude/debug/<session-id>.txt` 的偵錯日誌會在還原執行時列出每個跳過的路徑，因此在下次還原之前使用 `/debug` 開啟偵錯日誌。在 macOS 或 Linux 上，您可以改為直接找到連結：`find . -type l` 用於符號連結，`find . -type f -links +1` 用於硬連結檔案。
* 如果跳過的檔案是您有意建立的連結，例如由 dotfile 管理器管理的設定檔或由 pnpm 等工具硬連結的檔案，rewind 會保留其內容不變。若要復原工作階段對其所做的變更，請要求 Claude 反轉編輯或自行編輯檔案
* 如果您沒有建立連結，請在信任其內容之前檢查路徑

### No files were restored

當您使用 [`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing) 還原程式碼，且無法還原該檢查點中的任何檔案時，Claude Code 會顯示此訊息。對於每個檔案，Claude Code 在編輯前儲存的備份遺失，或 Claude Code 無法寫入或刪除該檔案。

```text theme={null}
Failed to restore the code:
No files were restored: 1 file failed (backup missing, or the file could not be updated)
```

Claude Code 在[保留掃描](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)中刪除工作階段的備份，預設情況下約在工作階段最後一次儲存後 30 天。如果您在之後恢復工作階段，`/rewind` 仍會列出其檢查點，但還原到其中一個可能會因此錯誤而失敗。如果訊息還說 `N paths were skipped for link safety`，請參閱[Restored the code, but skipped files](#restored-the-code-but-skipped-files) 以了解這些路徑。

當您分支工作階段時，例如使用 [`--fork-session`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 或 [`/branch`](https://code.claude.com/docs/zh-TW/sessions#branch-a-session)，Claude Code 會將原始工作階段的備份複製到分支中。當 Claude Code 無法複製備份時，例如因為磁碟已滿，該備份在分支中遺失。還原到需要它的檢查點可能會因此錯誤而失敗。

**該怎麼做：**

* 以其他方式復原變更：要求 Claude 反轉其編輯，或從版本控制還原檔案。當備份消失時，再次執行 `/rewind` 會以相同方式失敗。
* 如果 Claude Code 無法寫入或刪除檔案，請修復阻止寫入的問題，例如檔案權限，然後再次執行 `/rewind`。
* 若要在未來的工作階段中保留備份更長時間，請提高 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays)。

在 v2.1.260 之前，Claude Code 會無聲地跳過備份遺失的檔案，還原似乎成功。

## 工作階段儲存警告

Claude Code 在輸入框下方的持續行上顯示這些警告，當它未儲存您的工作階段文字記錄時。無論哪種方式，工作階段都會繼續運作；警告告訴您工作階段稍後可能會在 [`--resume`](https://code.claude.com/docs/zh-TW/sessions) 中遺失。

### 文字記錄寫入失敗

Claude Code 在您工作時將文字記錄儲存到磁碟，其對[文字記錄檔案](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)的寫入失敗。該訊息以基礎錯誤代碼命名原因，例如磁碟已滿：

```text theme={null}
Transcript writes are failing (disk full — ENOSPC) · recent messages may not be saved for resume
```

警告根據錯誤在不同時間點出現：

* 在不會自行清除的條件首次失敗時：磁碟已滿、超過磁碟配額、檔案系統唯讀、路徑超過檔案系統長度限制，或在 macOS 和 Linux 上，權限錯誤
* 在至少跨越一分鐘的重複失敗後，包括 Windows 上的權限錯誤，其中防毒軟體掃描可能會導致單次寫入失敗，然後在重試時成功

在 v2.1.217 之前，Claude Code 會在沒有警告的情況下放棄失敗的寫入，稍後 `--resume` 遺失最近訊息是第一個跡象。

**該怎麼做：**

* 修復錯誤代碼命名的條件：為 `ENOSPC` 釋放磁碟空間；為 `EDQUOT` 提高或清除配額；為 `EACCES`、`EPERM` 或 `EROFS` 恢復文字記錄位置的寫入存取
* 警告在下一次成功寫入時自動清除；不需要重新啟動
* 在警告顯示時傳送的訊息稍後恢復工作階段時可能仍會遺失

### 因為設定了 CLAUDE\_CODE\_SKIP\_PROMPT\_HISTORY 所以文字記錄儲存已關閉

此工作階段啟動時設定了 [`CLAUDE_CODE_SKIP_PROMPT_HISTORY`](https://code.claude.com/docs/zh-TW/env-vars)，因此 Claude Code 不會為其寫入文字記錄或提示歷史記錄：

```text theme={null}
Transcript saving is off — CLAUDE_CODE_SKIP_PROMPT_HISTORY is set · --resume will not find this session; if unintended, unset it and restart
```

該變數是針對暫時性指令碼工作階段的有意選擇退出，但它也可以透過殼層設定檔、包裝指令碼或匯出它的父程序到達工作階段。

**該怎麼做：**

* 如果您有意設定該變數，不需要採取任何行動；該通知確認工作階段不會出現在 `--resume`、`--continue` 或向上箭頭歷史記錄中
* 如果您沒有，請從啟動 `claude` 的殼層或指令碼中移除該變數，然後啟動新工作階段。目前工作階段的訊息不會被追溯儲存。

### 因為繼承了 CLAUDE\_CODE\_CHILD\_SESSION 標記所以文字記錄儲存已關閉

Claude Code 在它產生的子程序中設定 [`CLAUDE_CODE_CHILD_SESSION`](https://code.claude.com/docs/zh-TW/env-vars)，並將繼承它的互動式工作階段視為巢狀：Claude Code 不會為其儲存文字記錄，因此 Claude 本身啟動的工作階段不會填滿您的 `--resume` 清單。此通知表示您目前的工作階段繼承了該標記：

```text theme={null}
Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker · restart with CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1 to keep future transcripts
```

當您從另一個 Claude Code 工作階段內執行 `claude` 時，該通知是預期的；當標記透過長期存在的中介（例如終端機、`screen` 工作階段或 Claude Code 工作階段原本啟動的啟動器）洩漏時，它會發出誤分類的訊號。

在 tmux 內，Claude Code 會偵測透過 tmux 伺服器全域環境到達的標記，並繼續儲存，因此該通知不會出現在該情況下。

**該怎麼做：**

* 如果您有意從另一個 Claude Code 工作階段內啟動此工作階段，不需要採取任何行動
* 如果這是頂層工作階段，請結束並使用設定的 [`CLAUDE_CODE_FORCE_SESSION_PERSISTENCE=1`](https://code.claude.com/docs/zh-TW/env-vars) 重新啟動。儲存從重新啟動時開始套用，因此在此之前傳送的訊息不會被儲存。
* 若要修復從相同終端機或啟動器的未來啟動，請從其環境中移除 `CLAUDE_CODE_CHILD_SESSION`

## 設定警告

若要找出 Claude Code 在互動式工作階段啟動時發出的警告，請先查看啟動橫幅下方，再查看除錯日誌：

* **啟動橫幅下方的列**：部分關於[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)的警告，例如 [`⚠ Deny rule Bsh matches no tool · check for typos`](#matches-no-tool)
* **除錯日誌**：Claude Code 只會在除錯模式下保留此日誌。若要閱讀其中的警告，請從您的 shell 以 `claude --debug-file <path>` 啟動 Claude Code，然後開啟該路徑上的檔案。

在使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，且不在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中時，請在 stderr 上查看啟動警告。

在 v2.1.305 之前，互動式工作階段中也請查看 stderr，包括現在以橫幅下方列顯示的權限規則警告。

### Claude Code exited after an unrecoverable interface error

當 Claude Code 的終端機介面遇到無法復原的錯誤而結束時，無論使用哪一種渲染器，Claude Code 都會印出此訊息。只有在錯誤發生於 [fullscreen](https://code.claude.com/docs/zh-TW/fullscreen.md) 渲染器啟動期間時，才會出現第二句：

```text theme={null}
Claude Code exited after an unrecoverable interface error (<error>). It happened while the fullscreen renderer was starting, so the next launch will use the classic renderer (CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1 forces that any time).
```

**處理方式：**

* 重新啟動 Claude Code。若要接續先前的對話，請在相同目錄中執行 `claude --resume`。
* 若訊息提及 fullscreen 渲染器，[全螢幕渲染](https://code.claude.com/docs/zh-TW/fullscreen.md#fullscreen-renderer-didnt-finish-starting)說明了下次啟動時的行為（取決於您開啟全螢幕的方式），以及如何再次嘗試全螢幕或保留經典渲染器。

在 v2.1.236 之前，Claude Code 遇到這類錯誤後會直接結束，不會印出任何訊息。

### Agent descriptions are over the 15.0k-token limit

Claude Code 會在對話檢視中以啟動通知的形式顯示此警告，而非寫入 stderr。您的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)（內建的除外）合計的描述內容，依 Claude Code 的估算超過 15,000 個 token。每個 agent 計入的是其名稱加上其 `description` frontmatter。無論總量是否超過上限，Claude Code 都會載入每個 agent，因此此警告不會改變載入的內容。

```text theme={null}
Agent descriptions are over the 15.0k-token limit (~16.2k tokens) · ask Claude to trim agent descriptions in .claude/agents/
```

**處理方式：**

* 縮短您 agent 檔案中的 `description` frontmatter，或請 Claude 為您精簡。
* 移除您不再使用的 agent 檔案。

### Hook needs quotes around a path with a space

對話檢視中的此通知表示某個 hook 的腳本未執行，因為其路徑含有空格且未加上引號。該 hook 是 shell 形式的 [`asyncRewake`](https://code.claude.com/docs/zh-TW/hooks#run-hooks-in-the-background) hook。在其 `command` 中，`python3` 之類的直譯器後面接著未加引號的路徑預留位置，而解析後的路徑包含空格。

通知開頭為該 hook 的事件名稱，並指出腳本名稱：

```text theme={null}
Stop hook needs quotes around a path with a space (check.py)
```

**處理方式：**

* 在執行通知所指腳本之 hook 的 `command` 中，以雙引號包住路徑。在 JSON 檔案中，請寫成 `"command": "python3 \"${CLAUDE_PLUGIN_ROOT}/hooks/check.py\""`。

### Instruction file not loaded

互動式工作階段對話檢視中的此通知，表示某個存在的[記憶檔案](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)未被載入。有一項讀取限制正在生效。

```text theme={null}
Instruction file not loaded (a Read deny rule covers it):
path: .claude/rules/shared.md
```

括號內容會指出原因，例如：

* **`a Read deny rule covers it`**：某條 `Read` [拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)符合該檔案所寫的路徑，或其上的連結所指向的位置
* **`it's read from outside your working directories, where reads are blocked`**：在 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 開啟的情況下，該檔案解析到的位置在[工作目錄](https://code.claude.com/docs/zh-TW/settings-reference.md#permissions-blockreadsoutsideworkingdirectories)之外
* **`where it leads couldn't be worked out`**：例如，該檔案是直接或透過其他連結指回自身的連結

當 Claude 處理某個子目錄中的檔案，而該子目錄本身的記憶檔案無法載入時，相同的行會在該回合中出現在對話裡。當被保留的檔案多於這些行所列出的數量時，最後一行會計算其餘的數量，例如 `and 3 more instruction files not loaded`。

**處理方式：**

* 若此限制是刻意設定的，則無需處理：工作階段會在沒有該檔案指令的情況下執行。
* 若要載入因 `a Read deny rule covers it` 而被保留的檔案，請[移除或縮小該規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)。然後啟動新的工作階段。
* 若要載入因 `it's read from outside your working directories, where reads are blocked` 而被保留的檔案，請將該檔案或其連結目標移至工作目錄內。然後啟動新的工作階段。
* 若要載入因 `where it leads couldn't be worked out` 而被保留的檔案，請檢查該檔案是否為指回自身的連結。若是，請將連結指向存在的檔案，或以一般檔案取代它。然後啟動新的工作階段。

在 v2.1.292 之前，此通知會在同一行中、原因之後的結尾處列出該檔案。

### 某個 skill、命令或工作流程因名稱為保留名稱而未載入

某個 skill 資料夾、frontmatter 的 `name`、`.claude/commands/` 中的檔案或子資料夾，或某個[已儲存的工作流程](https://code.claude.com/docs/zh-TW/workflows.md#save-the-workflow-for-reuse)使用了 `anthropic-skills` 這個名稱，或以 `anthropic-skills:` 開頭的名稱。Claude Code [將該名稱保留給從 claude.ai 同步的 skill](https://code.claude.com/docs/zh-TW/skills.md#names-reserved-for-synced-skills)，因此不會載入該項目。

Claude Code 會在對話檢視中以啟動通知的形式顯示此警告，而非寫入 stderr：

```text theme={null}
Not loaded: rename .claude/skills/anthropic-skills, then restart — its name uses "anthropic-skills", a name reserved for the skills synced from your claude.ai account
```

此通知會針對第一個被拒絕的項目指出需要變更的內容：要重新命名的資料夾或檔案、要編輯的 `name:` 行，或要重新命名的工作流程。當有多個項目被拒絕時，通知結尾會附上數量，例如 `· 2 more`，而[除錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)會列出每一個項目。

**處理方式：**

* 重新命名通知所指的項目，或編輯其指向的 `name:` 行，然後重新啟動工作階段。

在 v2.1.282 之前，Claude Code 會載入使用這些名稱的 skill 和命令。

### Skill or command name refused

此啟動通知表示 Claude Code 拒絕了至少一個 [skill 或自訂命令](https://code.claude.com/docs/zh-TW/skills.md)的名稱，因此該項目未載入，或在未套用其 `name` 欄位的情況下載入：

```text theme={null}
1 skill or command name refused: run with --debug to see which ([names]), rename, then restart — a name may not hold hidden, direction-changing or blank-like characters, < or >, or be over 256 characters
```

* **未載入**：Claude Code 拒絕了 skill 或命令所使用的名稱，例如其目錄名稱，或命令檔案的名稱或子資料夾。該項目不會出現在 `/` 選單中，Claude 也無法呼叫它。其在除錯日誌中的行為 `<name> is not offered`。
* **忽略 `name` 欄位**：Claude Code 拒絕了某個 skill 的 frontmatter `name`。該 skill 仍會載入，但 `/` 選單不會顯示 `name` 的值，輸入該值也無法呼叫此 skill。其在除錯日誌中的行為 `<name value> is not shown for <skill>`。

**處理方式：**

* 從您的 shell 以 `claude --debug` 啟動 Claude Code，並在[除錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)中搜尋 `[names]`。通知所計入的每個名稱在那裡都有一行。該行會將部分隱藏字元以代碼形式寫出，例如以 `\u{200B}` 表示零寬度空格，讓您能看出它們的位置。
* 透過重新命名資料夾或檔案，或編輯 `name:` 行，移除 [skill 名稱不能包含的字元](https://code.claude.com/docs/zh-TW/skills.md#characters-a-skill-name-cant-hold)，或縮短超過 256 個字元的名稱。接著重新啟動工作階段，除非該檔案位於 Claude Code [會監看變更](https://code.claude.com/docs/zh-TW/skills.md#live-change-detection)的目錄中。若是來自非您撰寫之外掛的 skill，請請外掛作者重新命名。

### Workspace has not been trusted

Claude Code 在專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中找到 `permissions.allow` 規則或 `permissions.additionalDirectories` 項目，但未套用它們，因為[來自專案設定的允許規則需要工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)。訊息中的數量、設定名稱及所列出的檔案會因您的設定而有所不同。`deny` 和 `ask` 規則不受影響。

```text theme={null}
Ignoring 2 permissions.allow entries from .claude/settings.local.json: this workspace has not been trusted. Run Claude Code interactively here once and accept the trust dialog, or set projects["/Users/you/project"].hasTrustDialogAccepted: true in /Users/you/.claude.json.
```

**處理方式：**

* 在該目錄中執行 `claude` 並接受信任對話框。[專案允許規則與工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)說明了該次接受所涵蓋的資料夾。
* 在搭配 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下不會顯示對話框。請使用訊息所印出的確切 `projects` 鍵，在 `~/.claude.json` 中設定 `hasTrustDialogAccepted` 項目。
* 若訊息提及 `.claude/settings.local.json`，且您是在 git 儲存庫之外或在家目錄中啟動 Claude Code，請更新至 v2.1.200 或更新版本。2.1.196 至 2.1.199 版在這些工作區中會將您自己的 `.claude/settings.local.json` 視為由儲存庫提供。在 v2.1.207 及更新版本中，若您尚未信任該資料夾，僅更新並不足以解決 git 儲存庫之外的情況：判斷資料夾不在儲存庫內需要執行 git，而 Claude Code 只會在您接受信任對話框後才執行該檢查，因此請使用第一個步驟。您的家目錄及任何其他[設定主目錄](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)不受此限制，無需等待對話框。請參閱[專案允許規則與工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)。

### 工作目錄是網路路徑

Claude Code 不會將網路路徑加入為工作目錄。查詢網路路徑可能會連線到其所指定的主機，而在 Windows 上，該連線可能會將您的憑證傳送給該主機。因此 Claude Code 會在不查詢的情況下直接拒絕該路徑。

當您以網路路徑執行 `/add-dir` 時，會看到此訊息：

```text theme={null}
\\server\share is a network path, which cannot be added as a working directory. On Windows, map the share to a drive letter and pass it at launch with --add-dir (a drive letter added mid-session does not yet carry remote-read trust).
```

若您改為在啟動時傳入網路路徑（使用 `--add-dir` 或在 `permissions.additionalDirectories` 中），Claude Code 會在不包含該目錄的情況下啟動。在互動式工作階段中，您不會在啟動時看到此訊息，因為它會與其他[啟動警告](#configuration-warnings)一起寫入除錯日誌。

Claude Code 以此方式拒絕的路徑包括：

* UNC 共用，例如 `\\server\share`
* 自動掛載路徑，例如 `/net/<host>`，除非您是從該主機自動掛載下的目錄啟動 Claude Code。在該自動掛載下的讀取仍會經過[網路路徑檢查](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)。
* 透過符號連結或 junction 連到網路位置的本機路徑

對應的磁碟機代號和 `\\wsl$` 路徑不算網路路徑。

**處理方式：**

* 在 Windows 上，將共用對應到磁碟機代號，並在啟動時傳入該磁碟機。例如，在 PowerShell 中執行 `net use Z: \\server\share`，然後執行 `claude --add-dir Z:\`。
* 在 macOS 或 Linux 上，將共用掛載到本機路徑，改為加入該路徑。
* 若該路徑位於 `permissions.additionalDirectories` 中，請從列出它的設定檔中移除。

在 v2.1.257 之前，Claude Code 會接受可連線的網路路徑作為工作目錄。

### Remote managed settings failed to load

您的工作階段符合使用[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的資格，但 Claude Code 無法擷取這些設定，或無法套用伺服器回傳的內容，因此會在互動式工作階段及 Claude Desktop 的 Code 分頁中顯示此警告。

括號內的原因會指出失敗的項目，例如 `network error`、`request timed out` 或 `authentication rejected (401)`。原因 `no setting in the server response could be applied as written` 表示伺服器有回應，但其回傳的設定沒有任何一項通過[驗證](https://code.claude.com/docs/zh-TW/server-managed-settings.md#invalid-entries-in-delivered-settings)。在 v2.1.282 之前，此原因顯示為 `server returned invalid settings`。

該行其餘部分會說明工作階段所依循的政策：

* **有先前成功擷取時快取的設定**：Claude Code 會以該快取政策執行工作階段（[保留的環境變數](https://code.claude.com/docs/zh-TW/server-managed-settings.md#fetch-and-caching-behavior)除外），該行顯示 `using cached policy`。
* **沒有快取**：Claude Code 會在沒有伺服器管理設定的情況下執行工作階段，該行顯示 `no remote policy applied`。

在 Code 分頁中，當您傳送訊息時，警告會以對話中的一行出現，而當擷取的狀態改變時，會出現新的一行。三則相關訊息也會以相同方式出現：

* `Remote managed settings are still loading`：工作階段繼續進行時，擷取仍在執行中
* `Remote managed settings did not load`：擷取結束但沒有得到回應
* `Remote managed settings have now loaded`：設定在上述其中一則警告之後載入完成，該行其餘部分會說明是否套用了遠端政策

**處理方式：**

* 針對訊息所指的原因採取行動：若為網路原因，請確認此機器能連線到 `api.anthropic.com`；若為身分驗證原因，請以 `/status` 檢查您的登入狀態
* 若為 `no setting in the server response could be applied as written`，請請您的管理員修正伺服器上的設定
* 執行 `/status` 或 `claude doctor` 以取得完整診斷

在 v2.1.248 之前，Claude Code 只會在除錯日誌中回報設定擷取失敗。

### Managed settings were not approved

您組織的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)包含需要您核准的設定，而您拒絕了[安全性核准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)，因此 Claude Code 會在不套用這些設定的情況下結束：

```text theme={null}
Managed settings were not approved; exiting without applying them.
```

**處理方式：**

* 重新啟動 Claude Code 並核准對話框，以在組織的設定下繼續使用。被拒絕的對話框不會被記住，因此下次啟動時會再次出現。
* 若您不確定對話框中列出的某項設定，請在核准之前詢問負責維護組織受管設定的人員

### 受管設定需要您的核准

您組織的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)包含需要您在[安全性核准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)中核准的設定。您執行的 `claude plugin` 命令無法從鍵盤讀取輸入，因此無法顯示該對話框。當您以管線傳送或重新導向其輸入，且在 macOS 和 Linux 上它也無法開啟 `/dev/tty` 時，就會發生這種情況。該命令在做出任何變更之前就已停止：

```text theme={null}
Your organization's managed settings need your approval, which couldn't be asked for here. Run `claude` in a terminal and approve them, then run this command again.
```

**處理方式：**

* 在終端機中執行 `claude`，並在對話框出現時核准這些設定，然後再次執行相同的 `claude plugin` 命令。Claude Code 會將核准內容及已核准的設定保存在您的[設定目錄](https://code.claude.com/docs/zh-TW/server-managed-settings.md#approval-memory)中。若停止的命令是以另一個使用者身分執行，或設定了 `CLAUDE_CONFIG_DIR`，請以相同方式執行 `claude`，讓兩者使用相同的目錄。

### 受管設定封鎖了預設模型

您組織的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)封鎖了 Default 選項所解析到的模型，以及它可能降級使用的每一個模型。原本會以 Default 選項啟動的工作階段會在啟動時結束，而不會執行被封鎖的模型。您看到的訊息取決於封鎖它的設定。當 [`deniedModels`](https://code.claude.com/docs/zh-TW/model-config#block-specific-models-or-versions) 清單封鎖它時，訊息如下：

```text theme={null}
Claude Code can't start: your organization's managed settings block the default model (claude-opus-5-5) in "deniedModels", and none of the models they allow can be used as the default instead. Ask your administrator to update "deniedModels" or "availableModels".
```

當 [`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch) 設為 `"exact"` 的 `availableModels` 清單未包含它時，訊息如下：

```text theme={null}
Claude Code can't start: your organization allows only the models listed in "availableModels", and none of them can be used as the default model (claude-opus-5-5 isn't listed). Ask your administrator to update "availableModels".
```

**處理方式：**

* 若您負責管理這些設定，請將使用者可以執行的模型加入 `availableModels`，或縮小封鎖每一個備援模型的 `deniedModels` 項目。[封鎖特定模型或版本](https://code.claude.com/docs/zh-TW/model-config.md#block-specific-models-or-versions)說明了 Default 選項的降級方式
* 若您並未負責管理這些設定，請將訊息傳送給您的管理員。您自己的設定檔無法擴大受管的 `availableModels` 或 `deniedModels` 清單

### 受管設定不允許此 API 供應商

您組織的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)設定了 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 清單，而工作階段的 API 供應商不在清單中，或工作階段使用的端點未依該項目要求的方式固定。Claude Code 會在啟動時、登入前，或在工作階段下次連線 API 時拒絕執行。訊息開頭會列出允許的供應商：

```text theme={null}
Your organization's managed settings allow Claude Code to use: Anthropic API, Amazon Bedrock.
```

當清單為空時，訊息改為：

```text theme={null}
Your organization's managed settings allow Claude Code to use no API provider at all (allowedProviders is an empty list), so it cannot start on this machine.
```

當每個項目都無法辨識時，括號內容改為 `(allowedProviders lists only unrecognized entries)`。

**處理方式：**

* 依照訊息中 `To continue:` 的步驟操作
* 若您負責管理這些設定，訊息中以 `Admins:` 開頭的行會指出要加入的項目或要固定的值，而 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 項目說明了哪個來源的 `env` 區塊可以固定它

### MCP server is blocked by enterprise managed policy

您在 `/mcp` 中對某個伺服器選擇了 **Reconnect**，或在那裡重新開啟了已停用的伺服器，而某項[限制 MCP 伺服器](https://code.claude.com/docs/zh-TW/managed-mcp.md)的設定封鎖了該伺服器。Claude Code 會拒絕連線並顯示：

```text theme={null}
MCP server <name> is blocked by enterprise managed policy
```

以下任一設定都可能產生此訊息：

* 符合該伺服器的 [`deniedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists) 項目，包括您自己的 `~/.claude/settings.json` 或專案的 `.claude/settings.json` 中的項目
* 該伺服器不符合的 [`allowedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists) 清單
* 鎖定了 `mcp` 的 [`strictPluginOnlyCustomization`](https://code.claude.com/docs/zh-TW/settings-reference#strictpluginonlycustomization)，它會封鎖在 `~/.claude.json` 和 `.mcp.json` 中設定的伺服器
* [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/mcp#disable-claude-ai-connectors)，當該伺服器是 claude.ai 連接器時

**處理方式：**

* 檢查您自己的使用者與專案設定檔中是否有上述設定，並加以變更或移除
* 若您自己的設定都無法說明此封鎖，請詢問您的管理員是哪一項受管設定封鎖了該伺服器

在 v2.1.257 之前，`/mcp` 中的 **Reconnect** 和重新啟用可以連線到在工作階段中途因政策更新而被封鎖的伺服器。

### MCP 伺服器名稱為保留名稱

此訊息會指出您的某個 MCP 伺服器，其名稱屬於 Claude Code 保留的名稱，例如其內建伺服器的名稱：

```text theme={null}
"workspace" is a reserved MCP server name and was not loaded
```

**處理方式：**

* 在您定義該伺服器的位置重新命名，例如從 `workspace` 改為 `my-workspace`
* 關於其他應避免的保留名稱，請參閱 [MCP 設定警告](https://code.claude.com/docs/zh-TW/mcp.md#configuration-warnings)

### Managed settings document could not be parsed

您的組織部署了[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，而其中一份已部署的文件存在，但無法解析為 JSON 物件，因此 Claude Code 會在啟動時以代碼 1 結束，而不會在缺少該文件所含政策的情況下執行。該行會在訊息之前列出失敗的來源：

```text theme={null}
/Library/Application Support/ClaudeCode/managed-settings.json: Managed settings document could not be parsed as a JSON object; none of its settings are in effect. Fix or remove it.
```

來源為下列其中之一：

* `managed-settings.json` 檔案的路徑，或 `managed-settings.d` 下某個 drop-in 檔案的路徑
* macOS 受管偏好設定描述檔，`per-user managed preferences` 或 `device-level managed preferences`
* Windows 登錄值，`Registry: HKLM\SOFTWARE\Policies\ClaudeCode\Settings`

[找出 Claude Code 捨棄的項目](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)列出了導致各來源無法解析的原因。

即使另一個管理來源提供了有效的政策，Claude Code 仍會拒絕啟動。您會在互動式工作階段、`claude -p`、Agent SDK 工作階段、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)及大多數子命令（包括 `claude doctor`）中看到此錯誤。此拒絕刻意採取失敗即封閉的方式：Claude Code 無法解析之文件中的設定無法強制執行，若仍然啟動，工作階段將在缺少組織管控的情況下執行。

可解析文件中的 schema 問題不會產生此錯誤。[找出 Claude Code 捨棄的項目](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)說明了 Claude Code 對此類問題的處理方式。

當 `managed-settings.d/` 目錄存在但無法列出內容時，Claude Code 會改為回報 `Managed settings drop-in directory could not be read:`，後面接著底層錯誤。[找出 Claude Code 捨棄的項目](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)說明了讀取失敗何時會導致啟動時結束。

**處理方式：**

* 若您負責管理此機器，請修正所指的文件使其能解析為 JSON 物件，或移除該檔案、描述檔或登錄值。空的 `managed-settings.json` 會被視為 `{}`，不會阻擋啟動。
* 若您並未負責管理，請請您的管理員修正已部署的文件。您自己設定檔中的任何內容都不會導致或消除此錯誤。

### Unable to read managed policy settings

您的組織部署了[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，而其中一個已部署的來源存在但無法讀取，原因例如 I/O 錯誤，而非作業系統拒絕讀取。在沒有其他管理來源提供政策的情況下，Claude Code 會在啟動時結束，而不會在缺少該來源可能包含之政策的情況下執行：

```text theme={null}
Unable to read managed policy settings.
This machine may require organization login enforcement, but the policy file failed to load.
Contact your administrator.

Detail: <source>: <reason>
```

在相同狀態下，登入流程、來自已在執行中之工作階段的 API 請求，以及 [`claude gateway`](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 伺服器都會被拒絕，並顯示第一行的變體，其中會提及 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders)。

被作業系統拒絕的讀取（例如針對僅限 root 的檔案）不會導致此結束：[工作階段會在沒有該來源之政策的情況下啟動](https://code.claude.com/docs/zh-TW/managed-settings.md#find-entries-claude-code-dropped)。對於無法解析的來源，Claude Code 會以[另一則指出該來源的訊息](#managed-settings-document-could-not-be-parsed)結束。

**處理方式：**

* 若您負責管理此機器，請修正 `Detail:` 行所指的問題，使已部署的來源能夠讀取，或移除該來源
* 若您並未負責管理，請將訊息傳送給您的管理員。您自己設定檔中的任何內容都不會導致或消除此錯誤

在 v2.1.285 之前，只有以 claude.ai 或 Claude Console 憑證登入的工作階段會以此訊息結束，而被作業系統拒絕的讀取也會產生此訊息。

### Managed settings contain invalid entries, including PreToolUse/PermissionRequest hooks that are NOT loaded

`-p` 執行所輸出的這段 stderr 區塊，表示某個[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)來源包含 Claude Code 無法載入的 hook 項目。該 hook 不會執行；而當某一行將該來源的 `hooks` 欄位列為已忽略時，該來源的所有 hook 都不會執行。

每一行會列出來源、欄位（若有的話）以及問題，例如未知的 hook `type`，或在 `hooks` 鍵之外宣告的 hook：

```text theme={null}
Managed settings contain invalid entries, including PreToolUse/PermissionRequest hooks that are NOT loaded; fix or remove each entry:
  <source> (<field>): <message>
```

**處理方式：**

* 若您負責管理該來源，請修正或移除區塊中列出的每個項目。[Hook 設定](https://code.claude.com/docs/zh-TW/hooks.md#configuration)說明了 Claude Code 在 `hooks` 下預期的結構。
* 若某一行的來源是 `parent managed settings`，表示啟動 Claude Code 的應用程式將該項目作為[父層設定](https://code.claude.com/docs/zh-TW/managed-settings.md#parent-settings-from-embedding-hosts)傳入，因此請向該應用程式的開發者回報
* 否則，請將此區塊傳送給您的管理員

在 v2.1.300 之前，`-p` 執行會將此情況列在 `Managed settings failed to load; policies from the failed source are NOT in effect:` 標題下。

### otelHeadersHelper failed

當 [`otelHeadersHelper`](https://code.claude.com/docs/zh-TW/settings-reference#otelheadershelper) 腳本失敗，或印出不符合[腳本需求](https://code.claude.com/docs/zh-TW/monitoring-usage.md#script-requirements)的輸出時，Claude Code 會在終端機介面中以通知形式顯示此警告，每個互動式工作階段顯示一次。

在腳本持續失敗期間，匯出會失敗，您的遙測後端不會從該工作階段收到任何內容。

`See /status:` 之後的文字會說明失敗的內容，例如腳本的退出碼，後面接著其錯誤輸出：

```text theme={null}
otelHeadersHelper failed; telemetry is not being exported. See /status: exited 1: token service unreachable
```

**處理方式：**

* 執行 `/status` 以查看失敗詳細資訊。
* 修正腳本，使其在 30 秒內以 0 結束，並在 stdout 上印出由字串標頭值組成的 JSON 物件。請參閱[腳本需求](https://code.claude.com/docs/zh-TW/monitoring-usage.md#script-requirements)。
* 若您的組織透過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)部署此腳本，請請負責維護的人員加以修正。

在搭配 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，相同的失敗會改以 `otelHeadersHelper failed (OpenTelemetry export headers unavailable): <error>` 的形式出現在 stderr 上。

### headersHelper not run

Claude Code 僅以 MCP 伺服器的靜態 `headers` 連線該伺服器，並略過了該伺服器的 [`headersHelper`](https://code.claude.com/docs/zh-TW/mcp#use-dynamic-headers-for-custom-authentication)，因為 helper 是 shell 命令，而該資料夾沒有已儲存的信任。當您手動在 `~/.claude.json` 中設定資料夾的項目時，或（在家目錄以外的位置）在互動式工作階段中接受該資料夾的信任對話框時，該資料夾就會取得已儲存的信任。關於此檢查適用於哪些伺服器，請參閱[在執行 headersHelper 之前信任資料夾](https://code.claude.com/docs/zh-TW/mcp.md#trust-a-folder-before-its-headershelper-runs)。

Claude Code 只會在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下寫入此行，每個伺服器一次。在互動式工作階段中，它會改將相同的拒絕寫入除錯日誌。

```text theme={null}
MCP server 'internal-api': headersHelper not run — this workspace has no persisted trust; accept the trust dialog here once interactively, or set projects["/Users/you/project"].hasTrustDialogAccepted in /Users/you/.claude.json.
```

訊息所印出的 `projects` 鍵，就是[專案允許規則與工作區信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)中所說 Claude Code 用來作為信任依據的資料夾。接受上層資料夾的信任對話框並不能滿足此檢查，`-p` 或 SDK 工作階段也無法滿足。

**處理方式：**

* 在訊息所指的資料夾中執行 `claude`，接受信任對話框，然後再次執行您的 `-p` 或 SDK 命令
* 使用訊息所印出的確切 `projects` 鍵，自行在 `~/.claude.json` 中設定 `hasTrustDialogAccepted` 項目
* 若您是在家目錄中啟動工作階段，請改在您已信任的專案目錄中工作。當您在家目錄中接受信任對話框時，Claude Code 只會在目前的工作階段中保留該信任。

### Malformed Tool(content) rule

您某個設定檔中的[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#permission-rule-syntax)不符合 `Tool` 或 `Tool(content)` 的形式，例如右括號之後還有文字，或缺少其中一個括號。Claude Code 會略過該規則，並在互動式工作階段啟動時於無效設定對話框中列出，也會在 [`claude doctor`](https://code.claude.com/docs/zh-TW/debug-your-config#check-resolved-settings) 的輸出中列出：

```text theme={null}
Invalid permission rule "Bash(ls) x" was skipped: Malformed Tool(content) rule. Rules take the form Tool or Tool(content) and must end at the closing ")"; parentheses inside the content are literal
```

**處理方式：**

* 在訊息所列的設定檔中，改寫該規則使其在右括號處結束，例如以 `Bash(ls *)` 取代 `Bash(ls) x`
* 內容中的括號保持原樣即可。它們會被視為字面字元，因此像 `Edit(./Finance (2024)/**)` 這樣的規則無需跳脫即為有效

在 v2.1.260 之前，Claude Code 會將括號不成對的規則回報為 `Mismatched parentheses`。

### Matches no tool · check for typos

啟動橫幅下方的這一列會指出某條拒絕或詢問[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)，其工具名稱是 Claude Code 無法辨識的，因此該規則不會套用到您原本想指定的工具。寫成 `Bsh` 的拒絕規則不會套用到 Bash；使用工具在逐字稿中顯示的標籤、而非其正式名稱的規則也是如此。此列會重複顯示您所寫的規則：

```text theme={null}
⚠ Deny rule Bsh matches no tool · check for typos
```

在使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，Claude Code 會改為在 stderr 上印出較長形式的警告：

```text theme={null}
Permission deny rule "Bsh" matches no known tool — check for typos.
```

**處理方式：**

* 修正規則中的工具名稱，例如以 `Bash` 取代 `Bsh`。請在[工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md)中查詢正式名稱。
* 若要找出規則的定義位置，請在工作階段中執行 `/permissions` 並選取該規則。其詳細資訊會說明規則的來源，例如 `From project local settings`，或對於 `--disallowedTools` 值則為 `From CLI argument`。
* 若詳細資訊顯示 `From enterprise managed settings`，請將此列轉給負責維護您[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)的人員，因為您無法自行變更該規則。

在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，或使用 `--output-format json` 或 `stream-json` 時，Claude Code 會將警告寫入除錯日誌而非 stderr。使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它。

在 v2.1.305 之前，互動式工作階段會在啟動時於 stderr 上印出較長形式，而非顯示此列。

### Is not matched by file permission checks

Claude Code 在您的某個[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)、[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，或 `--allowedTools`、`--disallowedTools` 或 `--settings` 旗標值中，找到了帶有路徑的 `Write`、`NotebookEdit`、`MultiEdit` 或 `Glob` [權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。它只會依據 `Edit` 和 `Read` 規則檢查檔案權限，因此永遠不會參考指定其他檔案工具的路徑規則。它會保留該規則，不做其他變更。

* **互動式工作階段**：完整警告會寫入[除錯日誌](#configuration-warnings)，而此形式的拒絕或詢問規則也會以這一列顯示在啟動橫幅下方：

  ```text theme={null}
  ⚠ Deny rule Write(docs/**) never matches · use Edit(docs/**)
  ```

  此形式的允許規則不會顯示列。若要找出規則的定義位置，請在工作階段中執行 `/permissions` 並選取該規則。
* **使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)**：stderr 上的完整警告會列出該規則、括號中的來源，以及應改寫成的替代寫法：

  ```text theme={null}
  Permission deny rule (.claude/settings.json): Write(docs/**) is not matched by file permission checks — only Edit(path) rules are. Use Edit(docs/**) instead (Edit rules cover all file-editing tools).
  ```
* **[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，或使用 `--output-format json` 或 `stream-json` 時**：完整警告會寫入除錯日誌而非 stderr，以保持機器讀取的輸出乾淨。使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它。

**處理方式：**

* 將 `Write(path)`、`NotebookEdit(path)` 及舊版的 `MultiEdit(path)` 規則替換為 `Edit(path)`。`Edit` 規則涵蓋所有檔案編輯工具。
* 除了在 `--allowedTools` 中（Claude Code 在此接受 `Glob` 規則且不會發出警告）之外，請將 `Glob(path)` 規則替換為 `Read(path)`。
* 在完整警告括號中所指的來源修正規則：設定檔路徑，或對於 `--allowed-tools` 和 `--disallowed-tools` 則是旗標本身。磁碟上不存在的 `claude-settings-<hash>.json` 路徑代表的是內嵌的 `--settings` 值。請修正您傳給該旗標的 JSON。
* 像 `Write` 或 `Glob` 這類僅有工具名稱的規則保持不變即可。Claude Code 會在[工具層級](https://code.claude.com/docs/zh-TW/permissions.md#match-all-uses-of-a-tool)比對它們，且不會對其發出警告。
* 對於來自受管設定的規則，完整警告的括號內容會顯示 `managed policy settings`，而 `/permissions` 中該規則的詳細資訊會顯示 `From enterprise managed settings`。請將該警告轉給負責維護受管設定的人員，因為您無法自行消除它。

在 v2.1.210 之前，Claude Code 會接受這些規則而不發出警告。在 v2.1.305 之前，互動式工作階段會在 stderr 上印出完整警告。

### Has a wildcard before the rest of the command

Claude Code 在您的某個[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)、[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，或 `--allowedTools` 或 `--settings` 旗標值中，找到了一條 `Bash` 允許規則，其 `*` 出現在決定命令為何的後續字詞之前，例如 `Bash(git * main)` 或 `Bash(git -C * status *)`。`*` 會比對任何文字，包括插入在該位置的選項：`Bash(git * main)` 也會核准 `git -c core.fsmonitor=<script> diff main`，其中 `-c` 會讓 git 執行命令中所指定的程式。[萬用字元模式](https://code.claude.com/docs/zh-TW/permissions.md#wildcard-patterns)說明了比對規則。

此警告的目的是讓您能縮小萬用字元範圍比預期更廣的規則。Claude Code 會保留該規則，且不會改變其比對方式。在使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，stderr 上的警告會列出該規則及括號中的來源：

```text theme={null}
Permission allow rule (.claude/settings.json): Bash(git -C * status *) has a wildcard before the rest of the command, so it also matches any options inserted at that position and approves them without a prompt. For git, options such as -c and --exec-path can run arbitrary commands. Replace that * with the exact value you mean, or only use * after the subcommand (for example Bash(git status *)).
```

在互動式工作階段中，完整警告會寫入[除錯日誌](#configuration-warnings)，而該規則會以這一列顯示在啟動橫幅下方：

```text theme={null}
⚠ Allow rule Bash(git -C * status *) allows any option at its * · use an exact value
```

若要找出規則的定義位置，請在工作階段中執行 `/permissions` 並選取該規則。

**處理方式：**

* 將子命令之前的 `*` 替換為您所指的確切值：以 `Bash(git checkout main)` 取代 `Bash(git * main)`。
* 將每個 `*` 移到子命令之後：以 `Bash(git status *)` 取代 `Bash(git -C * status *)`。為每個您想允許的子命令各寫一條規則。
* 在完整警告括號中所指的來源修正規則：設定檔路徑，或 `--allowed-tools` 旗標本身。磁碟上不存在的 `claude-settings-<hash>.json` 路徑代表的是內嵌的 `--settings` 值。請修正您傳給該旗標的 JSON。
* 對於來自受管設定的規則，完整警告的括號內容會顯示 `managed policy settings`，而 `/permissions` 中該規則的詳細資訊會顯示 `From enterprise managed settings`。請將該警告轉給負責維護受管設定的人員，因為您無法自行消除它。

在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，或使用 `--output-format json` 或 `stream-json` 時，Claude Code 會將警告寫入除錯日誌而非 stderr，以保持機器讀取的輸出乾淨。使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它。在 v2.1.246 之前，Claude Code 會接受這些規則而不發出警告。

在 v2.1.305 之前，互動式工作階段會在 stderr 上印出完整警告，而非顯示列。

### Denying Bash also turns off the PowerShell tool

您移除了整個 Bash 工具，例如使用 `--disallowedTools Bash`，或在某個設定檔中使用僅有 `Bash` 或 `Bash(*)` 的[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#match-all-uses-of-a-tool)。在安裝了 Git Bash 的 Windows 上，[拒絕 Bash 也會關閉 PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#bash-deny-rules-also-turn-off-the-powershell-tool)，因此工作階段啟動時不會有任何 shell 工具。

在使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，Claude Code 會在啟動時於 stderr 上印出此警告，而互動式工作階段只會將其寫入[除錯日誌](#configuration-warnings)：

```text theme={null}
Denying Bash also turns off the PowerShell tool, so Claude has neither. To use PowerShell, set CLAUDE_CODE_USE_POWERSHELL_TOOL=1.
```

**處理方式：**

* 若要讓 Claude 使用 PowerShell，請依照[啟用 PowerShell 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#enable-the-powershell-tool)所示，在您的環境中或設定檔的 `env` 區塊中將 [`CLAUDE_CODE_USE_POWERSHELL_TOOL`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`。如此一來，PowerShell 工具會與您的 Bash 拒絕規則並存並保持開啟。
* 若要封鎖特定命令而非整個工具，請在同一個設定檔或旗標中，將僅有 `Bash` 的項目替換為有範圍限定的規則，例如 `Bash(git push *)`。Claude 會保留 Bash 工具，而 PowerShell 工具會保持關閉，直到您也設定該變數或加入有範圍限定的 [`PowerShell` 權限規則](https://code.claude.com/docs/zh-TW/permissions#powershell)。

在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，或使用 `--output-format json` 或 `stream-json` 時，Claude Code 會將警告寫入除錯日誌而非 stderr。使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它。在 v2.1.287 之前，Claude Code 會以相同方式關閉 PowerShell 工具，但不會印出警告。

在 v2.1.305 之前，互動式工作階段也會在啟動時於 stderr 上印出此警告。

### crossSessionInbound must be one of accept, hold, refuse

某個設定檔將 [`crossSessionInbound`](https://code.claude.com/docs/zh-TW/settings-reference#crosssessioninbound) 設為 Claude Code 無法辨識的值，例如拼錯的 `"reject"`。警告的第二句取決於哪個檔案包含該值；在使用者、專案、本機或 `--settings` 檔案中，內容如下：

```text theme={null}
"crossSessionInbound" must be one of "accept", "hold", "refuse"; received "reject". This value was ignored; while it is present, cross-session messages are held for your approval instead of being delivered. Set it to one of the values above.
```

在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中，Claude Code 會將無法辨識的值視為最嚴格的 `refuse`，而警告會說明跨工作階段訊息在管理員修正之前都會被拒絕。關於保留行為如何與您其他設定檔中的值結合，請參閱 [`crossSessionInbound`](https://code.claude.com/docs/zh-TW/settings-reference#crosssessioninbound)。

**處理方式：**

* 將該鍵設為 `"accept"`、`"hold"` 或 `"refuse"`，或將其移除
* 當警告提及受管設定時，請請管理員修正該值

在 v2.1.248 之前，Claude Code 會忽略無法辨識的值而不發出警告。

### ANTHROPIC\_FOUNDRY\_RESOURCE must be a Foundry resource name

您將 [`ANTHROPIC_FOUNDRY_RESOURCE`](https://code.claude.com/docs/zh-TW/env-vars) 設為非單純 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 資源名稱的值，例如端點 URL 或其主機名稱。Claude Code 在傳送請求之前就拒絕了該值。此訊息會出現在 Claude 回覆的位置，而非作為啟動警告：

```text theme={null}
API Error: ANTHROPIC_FOUNDRY_RESOURCE must be a Foundry resource name (2-64 letters, digits and hyphens, not starting or ending with a hyphen, such as my-resource), not a URL or host name. To use a full URL, set ANTHROPIC_FOUNDRY_BASE_URL instead.
```

**處理方式：**

* 將 `ANTHROPIC_FOUNDRY_RESOURCE` 僅設為資源名稱，然後重新啟動 Claude Code。對於端點 `https://my-resource.services.ai.azure.com/anthropic`，名稱為 `my-resource`。
* 若要改為提供完整的端點 URL，請將 [`ANTHROPIC_FOUNDRY_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars) 設為該 URL 並移除 `ANTHROPIC_FOUNDRY_RESOURCE`，然後重新啟動 Claude Code。Claude Code 只接受這兩個變數的其中一個。

### The 200K limit isn't enforced

您設定了 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/env-vars)，這通常會讓[自動壓縮](https://code.claude.com/docs/zh-TW/model-config.md#default-auto-compact-thresholds)將使用 1M 上下文模型的工作階段限制在 200K 視窗內，但沒有任何壓縮閾值將此工作階段限制在 200K 或以下，因此對話可能會超過該上限。

```text theme={null}
CLAUDE_CODE_DISABLE_1M_CONTEXT is set, but the 200K limit isn't enforced for <model>, so this session can grow past it. To enforce it, set CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000 (or the autoCompactWindow setting).
```

對於 Claude Code 辨識為具有原生 1M 視窗的每個模型，Claude Code 會自行強制執行 200K 上限；對於無法辨識的模型 ID，它會依其假設的視窗大小進行壓縮。當其他設定使該強制執行失效時，就會出現此警告：

* 模型 ID 不是 Claude Code 能辨識的，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)別名，而您設定了 [`CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1`](https://code.claude.com/docs/zh-TW/env-vars)，或以 [`CLAUDE_CODE_MAX_CONTEXT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 將假設的視窗提高到超過 200K。在此情況下，訊息還會提供 `or update to a Claude Code version that recognizes <model>` 作為補救方式。
* 透過 [`ANTHROPIC_BETAS`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`--betas`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 旗標請求的 `context-1m` beta，在接受該 beta 的模型上仍會向 API 要求 1M 視窗，而沒有任何機制在 200K 時壓縮工作階段

**處理方式：**

* 設定 [`CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000`](https://code.claude.com/docs/zh-TW/env-vars)，或將 [`autoCompactWindow`](https://code.claude.com/docs/zh-TW/settings-reference#autocompactwindow) 設定設為 `200000`，讓自動壓縮在 200K 邊界進行壓縮
* 若訊息提及此版本無法辨識的模型 ID，請執行 `claude update`。能將該 ID 辨識為 1M 上下文模型的版本，無需額外設定即可強制執行該上限。
* 若您希望工作階段改為使用模型的完整視窗，請取消設定 `CLAUDE_CODE_DISABLE_1M_CONTEXT`；此警告只是回報 200K 上限未被強制執行

在使用文字輸出的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，此警告會出現在 stderr 上。在互動式工作階段、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，或使用 `--output-format json` 或 `stream-json` 時，它會改為寫入除錯日誌。使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它。

在 v2.1.305 之前，互動式工作階段會在啟動時於 stderr 上印出此警告。

### 請求中包含無法辨識的模型 ID

Claude Code 傳送了一個請求，其模型 ID 是您的 Claude Code 版本無法辨識的，且找不到將該 ID 對應到可辨識模型的 [`modelOverrides`](https://code.claude.com/docs/zh-TW/model-config#override-model-ids-per-version) 項目。Claude Code 仍會以您所設定的 ID 傳送請求，不會結束或切換模型。

```text theme={null}
[claude-code:unrecognized_model] {"model":"my-proxy-model","query_source":"sdk"}
```

在讀取 stderr 的腳本或測試框架中，請比對 `[claude-code:unrecognized_model]` 前綴。在前綴和一個空格之後，Claude Code 會寫入一行 JSON 物件。Claude Code 可能會在之後的版本中新增欄位，因此請忽略任何您未預期的欄位。它至少會寫入以下兩個欄位：

* `model`：您所設定的模型字串
* `query_source`：使用該模型的請求路徑。例如，對於 `-p` 執行的主要對話，其值為 `sdk`；對於 subagent，其值以 `agent:` 開頭。

Claude Code 會依您的執行方式，將此行寫入以下兩處之一：

* 在搭配 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)下，無論 `--output-format` 為何，Claude Code 都會將其寫入 stderr，因此您可以直接解析 stdout 而無需過濾掉此行
* 在互動式工作階段或[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，Claude Code 會改將其寫入除錯日誌；使用 `--debug` 執行即可在 `~/.claude/debug/<session-id>.txt` 中擷取它

Claude Code 在每個程序中，對每個模型 ID 只寫入一次此行。對於其他每個無法辨識的 ID，例如 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model) 或[背景功能](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)所使用的 ID，它會另外寫入一行。

對於能解析為可辨識模型的供應商 ID，Claude Code 不會寫入此行，例如 Amazon Bedrock 的 `us.anthropic.claude-...` ID、帶有 `@` 版本後綴的 Google Cloud Agent Platform ID，以及包含 Claude 模型 ID 的 Microsoft Foundry 部署名稱。對於 Amazon Bedrock [應用程式推論設定檔 ARN](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#map-each-model-version-to-an-inference-profile)，Claude Code 會檢查其背後的模型，而非 ARN 本身。對於無法解析的 ARN（例如打錯的 ARN），它不會寫入任何行。

**處理方式：**

* 若您是刻意設定該 ID，例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)別名，請在您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中加入一個 [`modelOverrides`](https://code.claude.com/docs/zh-TW/model-config#override-model-ids-per-version) 項目，並以該 ID 作為其值。請使用 Anthropic 模型 ID 作為鍵，而非 `opus` 之類的系列別名。對於範例行中的 `my-proxy-model`，請加入以下項目：

  ```json theme={null}
  {
    "modelOverrides": {
      "claude-opus-4-6": "my-proxy-model"
    }
  }
  ```

  如此一來，Claude Code 會將 `my-proxy-model` 視為 `claude-opus-4-6`，並停止寫入此行。

* 若該 ID 指的是比您的 Claude Code 版本更新的模型，請執行 `claude update`

* 若該 ID 是拼寫錯誤，請在包含它的[可設定模型的位置](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)或[別名變數](https://code.claude.com/docs/zh-TW/model-config.md#environment-variables)中加以修正。若 `query_source` 以 `agent:` 開頭，請改在您設定 [subagent 模型](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)的位置修正。

在 v2.1.233 之前，Claude Code 在為無法辨識的模型 ID 傳送請求時不會寫入任何行。

### 在受管鎖定下會忽略沙箱允許項目

`/status` 和 `claude doctor` 中的此警告表示受管設定設定了 [`allowManagedReadPathsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-allowmanagedreadpathsonly) 或 [`allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly)，因此其所指檔案中的 [`allowRead`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-filesystem-allowread) 或 [`allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains) 項目不會套用：

```text wrap theme={null}
sandbox.filesystem.allowRead is ignored — managed settings set allowManagedReadPathsOnly, so only allowRead paths from managed settings are honored. The 3 entries in /home/you/.claude/settings.json will NOT apply (see https://code.claude.com/docs/en/settings#sandbox-settings).
```

對於網路鎖定，警告會提及 `sandbox.network.allowedDomains` 和 `allowManagedDomainsOnly`，並說明 `only allowed domains (and WebFetch domain rules) from managed settings are honored`。

**處理方式：**

* 您不必針對此警告採取行動
* 若您需要這些路徑或網域，且是組織的受管設定設定了該鎖定，請請您的管理員將它們加入這些設定。在您也從所指的檔案中移除這些項目之前，警告會持續存在。
* 若要消除警告，請從所指的檔案中移除這些項目。對於您共用的檔案，例如專案的 `.claude/settings.json`，您可以為沒有該鎖定的隊友保留這些項目，並讓警告繼續顯示。

### Sandbox mask files left behind at write-deny paths

`claude doctor` 和 `/status` 中的此警告會列出遮罩檔案：位於[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)拒絕寫入之路徑上的 0 位元組唯讀佔位檔案。當沙箱機制在啟用檔案系統隔離的情況下開啟時，此警告會出現在 Linux 和 WSL2 上。請在包含這些檔案的專案中已沒有任何開啟的 Claude Code 工作階段時，從您的 shell 刪除它們。

沙箱會在沙箱化命令執行期間建立佔位檔案，並在命令結束時將其移除。在下列情況下，佔位檔案會被留下：

* 工作階段在命令結束前被終止，例如被 SIGKILL
* 您在沙箱化命令仍在執行時結束工作階段，例如在背景執行的命令

在 `claude doctor` 中，警告內容如下：

```text theme={null}
- Sandbox mask files left behind at write-deny paths: /home/you/project/.claude/settings.local.json
  Fix: A session leaves one where it was killed, or where it exited while a sandboxed command was still running. Remove each with `rm <path>` while no other Claude Code session is running in that project — a 0-byte read-only file where a settings file belongs makes "Yes, and don't ask again" fail to save, and the sandbox binds it read-only again on every start
```

**處理方式：**

* 結束在包含所列檔案之專案中開啟的每個 Claude Code 工作階段（包括 `/status` 顯示此警告的工作階段），然後在您的 shell 中操作。另一個工作階段的沙箱仍在使用的佔位檔案，是該工作階段寫入保護中正在運作的一部分
* 在您的 shell 中，以 `rm` 刪除每個列出的檔案；若 `rm` 詢問是否刪除受寫入保護的檔案，請予以確認。警告最多會列出三個檔案並計算其餘數量，因此刪除後請重新執行 `claude doctor`，直到警告不再出現為止
* 若您以「Yes, and don't ask again」儲存的權限選擇沒有生效，請在刪除佔位檔案後再次儲存

在 v2.1.309 之前，此警告顯示為 `Stale sandbox mask files left by a killed session`。

在 v2.1.257 之前，`claude doctor` 不會標示這些檔案；較早的版本在工作階段被終止時也會留下相同的佔位檔案。

## 回應品質似乎低於預期

如果 Claude 的回答似乎不如您預期的那樣有能力，但沒有顯示錯誤，原因通常是對話狀態而非模型本身。Claude Code 不會無聲地更改模型版本。它只能在這些情況下切換到備用模型：

* 配置的 [`--fallback-model`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 在可用性錯誤後接管該輪次，並在文字記錄中顯示通知
* Amazon Bedrock 或 Google Cloud 的 Agent Platform 啟動檢查發現您的預設模型不可用，或您的帳戶[在工作階段中途失去對它的存取權](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#when-a-model-is-disabled-mid-session)
* [自動模型備用](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)在 Fable 5.1、Fable 5、Opus 5.5、Sonnet 5.5 和 Opus 5 上將工作階段移至標記類別的備用模型（當該類別有備用模型時），並在文字記錄中顯示通知

下面的模型選擇檢查可以捕捉第二和第三種情況；第一種情況顯示為文字記錄通知而非 `/model` 變更。[模型設定](https://code.claude.com/docs/zh-TW/model-config.md)說明每個備用何時適用。

首先檢查這些項目：

* **模型選擇**：執行 `/model` 以確認您在預期的模型上。先前的 `/model` 選擇或 `ANTHROPIC_MODEL` 環境變數可能使您在比預期更小的模型上。
* **努力程度**：執行 `/effort` 以檢查目前的推理程度，並為困難的除錯或設計工作提高它。預設值因模型而異，所以在假設您低於最大值之前請先檢查。請參閱[調整努力程度](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)以了解每個模型的預設值和 `ultrathink` 快捷方式。
* **上下文壓力**：執行 `/context` 以查看視窗有多滿。如果接近容量，請在自然斷點執行 `/compact` 或執行 `/clear` 以重新開始。請參閱[探索上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)以了解自動壓縮如何影響較早的輪次。
* **過時的指示**：大型或過時的 `CLAUDE.md` 檔案和 MCP 工具定義會消耗上下文並可能引導回應。`/doctor` 檢查會標記超大的記憶檔案和未使用的擴充功能，而 `/context` 會顯示 MCP 工具的權杖使用情況。在 v2.1.205 之前，`/doctor` 開啟了一個診斷畫面，標記超大的記憶檔案和子代理定義。

當回應出錯時，回溯通常比用更正回覆效果更好。按 Esc 兩次或執行 `/rewind` 以回到不良輪次之前，然後用更多細節重新表述提示。在執行緒中更正會將錯誤的嘗試保留在上下文中，這可能會將後來的答案錨定到它。請參閱[檢查點](https://code.claude.com/docs/zh-TW/checkpointing.md)。

如果在檢查上述項目後品質仍然似乎有問題，請執行 `/feedback` 並描述您預期的內容與您得到的內容。以這種方式提交的回饋包括對話文字記錄，這是 Anthropic 診斷真實迴歸的最快方式。如果 `/feedback` 在您的環境中不可用，請參閱[報告錯誤](#report-an-error)。

如果 Claude 警告懷疑提示注入，或因懷疑注入而拒絕請求，而警告命名的文字是 Claude Code 自動添加到對話中的上下文而非檔案或網路內容，請執行 `claude update` 並重試。如果更新後警告重複出現，請[報告它](#report-an-error)而不是將標記的內容貼回提示中。在 v2.1.201 之前，Sonnet 5 以相同方式拒絕了一些請求。

## 回報錯誤

如需了解此頁面未涵蓋的元件錯誤，請參閱相關指南：

* MCP 伺服器連線或驗證失敗：[MCP](https://code.claude.com/docs/zh-TW/mcp.md)
* Hook 指令碼失敗或阻止了工具：[Debug hooks](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)
* 安裝期間權限被拒或檔案系統錯誤：[Troubleshoot installation and login](https://code.claude.com/docs/zh-TW/troubleshoot-install.md)

如果此處未列出錯誤或建議的修正方法無法幫助：

* 在 Claude Code 內執行 `/feedback` 以將文字記錄和說明傳送給 Anthropic。該命令也提供開啟預先填入的 GitHub issue 的選項。傳送給 Anthropic 需要[驗證](https://code.claude.com/docs/zh-TW/authentication.md)。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和其他第三方提供者上，或當未設定 Anthropic 認證時，`/feedback` 會儲存本機封存，您可以改為傳送給您的 Anthropic 帳戶代表。
* 如果 `/feedback` 回應它已被您組織的政策停用，請參閱[該訊息的條目](#feedback-is-disabled-by-your-organizations-policy)
* 從您的 shell 執行 `claude doctor` 以進行安裝的唯讀診斷，或在 Claude Code 內執行 `/doctor` 檢查以尋找並修正設定問題
* 檢查 [status.claude.com](https://status.claude.com) 以了解活躍的事件
* 在 GitHub 上搜尋[現有 issue](https://github.com/anthropics/claude-code/issues)
