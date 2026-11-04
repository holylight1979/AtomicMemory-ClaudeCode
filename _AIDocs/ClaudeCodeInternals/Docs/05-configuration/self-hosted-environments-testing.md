<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/self-hosted-environments-testing | lastmod: 2026-10-10 | section: Configuration / Environments -->
> 來源：https://code.claude.com/docs/zh-TW/self-hosted-environments-testing（官方 zh-TW，lastmod 2026-10-10）｜分類：Configuration › Environments｜EN 摘要：Verify a self-hosted runner image from CI: dispatch a session with the CLI, read Claude's replies through a Stop hook, and script the full loop.

# 端對端測試自託管環境

> 從 CI 驗證自託管執行器映像：使用 CLI 分派工作階段、透過 Stop hook 讀取 Claude 的回覆，並編寫完整迴圈的指令碼。

> [!NOTE]
>
> 自託管環境在 Team 和 Enterprise 方案上處於公開測試版；[可用性和限制](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations)涵蓋啟用路徑。本頁面是 CI 測試配方；請參閱[快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md)以了解設定，以及[部署到生產環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md)以了解艦隊配方。

在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中，Claude Code [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)在您建置和維護的執行器映像上執行。在將新映像推出到生產環境之前，請從指令碼針對測試環境驅動完整工作階段：建立工作階段、讀取 Claude 的回覆、傳送後續追蹤，並讀取該回覆。這是 CI 煙霧測試的形式，可驗證您的執行器映像、git 存取和任何自訂工具，然後再推廣變更。

此配方假設您已經[設定環境和執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-an-environment-and-runner)，並且您的 CI 工作在與測試指令碼相同的主機上啟動執行器程序，這是測試新執行器映像的自然設定。您在執行器上安裝的 Stop hook 會將每個回合的最終回覆寫入本機檔案，指令碼從該處讀取它，因此對 Anthropic API 的唯一呼叫是兩個分派本身。如果您的測試執行器位於不同的基礎結構上，請參閱[遠端測試執行器](#remote-test-runners)。

## 在測試執行器上安裝擷取 hook

讀回透過 Claude Code [Stop hook](https://code.claude.com/docs/zh-TW/hooks.md#stop) 進行：當 Claude 完成一個回合時，hook 會在其 stdin JSON 中接收最終助手訊息作為 `last_assistant_message`，並將其附加到 `$E2E_REPLY_DIR/<session_id>.txt`。以與[commit-nudge Stop hook](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#prompt-sessions-to-push-their-work)相同的方式安裝它，在執行器主機的 `~/.claude/` 上，執行器會將其植入每個工作階段。

### 儲存 hook 檔案

在執行器主機上儲存以下兩個檔案：

* 設定區塊：合併到執行器主機上的 `~/.claude/settings.json`
* 指令碼：在執行器主機上儲存為 `~/.claude/hooks/e2e-stop-hook-capture.sh` 並使其可執行

```json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "timeout": 10,
            "command": "\"$CLAUDE_CONFIG_DIR/hooks/e2e-stop-hook-capture.sh\""
          }
        ]
      }
    ]
  }
}
```

```sh theme={null}
#!/bin/sh
# Stop hook for testing a self-hosted environment end to end: writes each
# turn's final assistant reply to $E2E_REPLY_DIR/<session_id>.txt so a
# co-located test driver can read it without calling the Anthropic API.
# Install on the TEST runner only. Requires jq.

# No-op unless the driver is listening. Never fail the turn.
[ -n "${E2E_REPLY_DIR:-}" ] && [ -d "$E2E_REPLY_DIR" ] || exit 0

# CLAUDE_CODE_REMOTE_SESSION_ID is exported in cse_... form; the session
# id the dispatch CLI prints is in session_... form. Same id, different
# prefix.
sid=$(printf '%s' "${CLAUDE_CODE_REMOTE_SESSION_ID:-}" | sed 's/^cse_/session_/')
[ -n "$sid" ] || exit 0

# last_assistant_message is absent when the final assistant turn had no
# text, such as a tool-use-only turn. The `// empty` filter makes that a
# zero-byte write rather than the literal string "null".
jq -r '.last_assistant_message // empty' >> "$E2E_REPLY_DIR/$sid.txt" 2>/dev/null
exit 0
```

### 在啟動執行器之前

hook 依賴的兩件事：

* 在啟動執行器之前安裝它。執行器在啟動時會快照 `~/.claude/`，因此添加到執行中執行器的 hook 只有在重新啟動後才會生效。
* 將 `E2E_REPLY_DIR` 匯出到執行器程序。當變數未設定或目錄不存在時，hook 是無操作的，因此在啟動執行器的任何地方設定它，例如 systemd 單位、pod 規格或 CI 步驟。下面的測試指令碼也需要它。

僅在為測試環境提供服務的執行器上安裝此 hook。每當 `E2E_REPLY_DIR` 存在時，它會將每個工作階段的最終回覆寫入磁碟，這在一次性 CI 執行器上是無害的，但不是要帶入生產環境執行器映像的東西，其中變數可能會被意外設定。

## 執行測試迴圈

The `--environment` 和 `--ref` 分派旗標需要執行指令碼的機器上的 Claude Code v2.1.224 或更新版本，與執行器本身的下限相同。安裝 hook 並在此主機上啟動執行器後，測試指令碼：

1. 使用 `claude -p "<prompt>" --environment <environment-id> --output-format json` 在測試環境上建立工作階段。請從 git 簽出中執行該命令，以便 CLI 可以從 `origin` 遠端自動偵測儲存庫。可選的 `--ref <branch>` 將工作階段的簽出基於命名的 ref，而不是本機 HEAD。該命令會在不等待 Claude 回覆的情況下退出。其列印的內容會告訴您的指令碼結果：
   * **工作階段已建立**：一行 JSON，例如 `{"ok":true,"session_id":"session_...","title":"...","url":"...","pool_id":"..."}`
   * **工作階段建立失敗**：`{"ok":false,"error":"..."}` 這一行，且命令以狀態 1 退出
   * **某些較早發生的錯誤**，例如您的組織無法使用雲端工作階段或缺少提示詞：錯誤會輸出到 stderr 且沒有 JSON 行，命令以狀態 1 退出
2. 等待回覆出現在 `$E2E_REPLY_DIR/<session_id>.txt` 中，由執行器上的 Stop hook 在回合完成後寫入。
3. 使用 `claude -p "<message>" --cloud <session_id> --output-format json` 傳送後續訊息（請參閱[傳送後續訊息到執行中的工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-follow-ups-from-the-cli)），它將使用者事件發佈到現有工作階段並退出。
4. 以與步驟 2 相同的方式等待後續訊息的回覆。

### `--environment` 分派行為

Claude Code 建立工作階段、列印工作階段 ID 和指向它的連結，然後退出。

該旗標優先於 [`remote.defaultEnvironmentId`](https://code.claude.com/docs/zh-TW/settings-reference#remote-defaultenvironmentid) 設定。它不支援 `--output-format stream-json`，並且不能與恢復、附加到或預先配置工作階段的旗標結合，例如 `--resume`、`--continue`、`--teleport`、`--session-id` 或 `--init-only`。`--cloud` 在使用工作階段 ID 或 URL 時被拒絕，在非互動式執行中當它帶有描述時。裸 `--cloud` 被視為不存在。從終端機，您可以傳遞任務作為 `--cloud` 描述，而不是位置提示。

## 範例指令碼

範例指令碼在與測試執行器相同的機器上執行。執行之前，請先準備好該機器：

* **儲存庫簽出**：從您希望工作階段在其中工作的儲存庫的 git 簽出執行指令碼。
* **執行器**：在此主機上啟動執行器，並安裝擷取 hook 及匯出 `E2E_REPLY_DIR`。
* **登入**：依照[從 CI 進行驗證](#authenticate-from-ci)中的說明，在執行指令碼的機器上使用 claude.ai 帳戶登入。
* **環境 ID**：將 `CLAUDE_TEST_ENVIRONMENT_ID` 設定為您的測試環境的 `ccpool_...` ID，該 ID 顯示在管理頁面上環境的詳細對話框中，或由[建立環境呼叫](#create-a-dedicated-test-environment)返回。

下面的指令碼針對 `$CLAUDE_TEST_ENVIRONMENT_ID` 執行完整迴圈，並在每個回覆中斷言哨兵短語。

```bash theme={null}
#!/usr/bin/env bash
# End-to-end test against a self-hosted environment, using Stop-hook read-back.
# Prereqs: `claude auth login` has been run on this machine (see "Authenticate
# from CI" below); jq is installed; CLAUDE_TEST_ENVIRONMENT_ID names an
# environment whose runner is the one on this host, with the capture hook
# installed and E2E_REPLY_DIR in its environment.

set -euo pipefail

: "${CLAUDE_TEST_ENVIRONMENT_ID:=${CLAUDE_TEST_POOL_ID:-}}"  # CLAUDE_TEST_POOL_ID is the legacy spelling
: "${CLAUDE_TEST_ENVIRONMENT_ID:?set CLAUDE_TEST_ENVIRONMENT_ID to a ccpool_... id served by a runner on this host}"
: "${E2E_REPLY_DIR:?set E2E_REPLY_DIR to the directory the Stop hook on your test runner writes to, and export it to the runner process}"
: "${TEST_REPO_REF:=main}"

[ -d "$E2E_REPLY_DIR" ] || {
  echo "FAIL: E2E_REPLY_DIR ($E2E_REPLY_DIR) does not exist. The Stop hook on the runner needs it." >&2
  exit 1
}

# Waits until $E2E_REPLY_DIR/<session_id>.txt contains $2, or fails after
# 90 seconds. Tune the timeout to your environment's cold-start time. The
# file is written by the Stop hook on the runner.
await_reply() {
  local expect="$2" f="$E2E_REPLY_DIR/$1.txt"
  local deadline=$(($(date +%s) + 90))
  while :; do
    if [ -f "$f" ] && grep -qF -- "$expect" "$f"; then
      return
    fi
    [ "$(date +%s)" -lt "$deadline" ] || {
      echo "FAIL: '$expect' not in $f within 90s. The Stop hook on the runner did not write it." >&2
      echo "-- $E2E_REPLY_DIR contents --" >&2; ls -la "$E2E_REPLY_DIR" >&2
      [ -f "$f" ] && { echo "-- $f --" >&2; cat "$f" >&2; }
      exit 1
    }
    sleep 1
  done
}

# 1. Create the session on the test environment. Run from a git checkout
# so the CLI can auto-detect the repo. --ref pins the checkout to a named
# ref regardless of local HEAD.
TURN1="e2e-probe-$(date +%s)-$$: say exactly 'ok: custom tools are reachable' and nothing else"
EXPECT1="ok: custom tools are reachable"
create_json=$(claude -p "$TURN1" --environment "$CLAUDE_TEST_ENVIRONMENT_ID" \
  --ref "$TEST_REPO_REF" --output-format json < /dev/null)
echo "create: $create_json"
SESSION_ID=$(jq -er '.session_id' <<<"$create_json")

# 2. Wait for the turn-1 reply.
await_reply "$SESSION_ID" "$EXPECT1"
echo "turn-1 reply ok"

# 3. Post a follow-up via the CLI.
TURN2="e2e-probe-followup-$(date +%s): say exactly 'ok: follow-up delivered' and nothing else"
EXPECT2="ok: follow-up delivered"
followup_json=$(claude -p "$TURN2" --cloud "$SESSION_ID" --output-format json < /dev/null)
echo "followup: $followup_json"
jq -e '.ok == true' <<<"$followup_json" >/dev/null

# 4. Wait for the turn-2 reply.
await_reply "$SESSION_ID" "$EXPECT2"
echo "turn-2 reply ok"

echo "PASS: test-environment round-trip (session $SESSION_ID)"
```

將 `TURN1`/`TURN2` 提示詞和 `EXPECT1`/`EXPECT2` 哨兵替換為任何能測試您的設定的內容，例如要求 Claude 執行您的自訂 MCP 工具之一並斷言其輸出。

## 遠端測試執行器

如果您的測試執行器位於不同的基礎結構上，例如您的 CI 工作無法與之共享檔案系統的持久 Kubernetes 艦隊，請將 Stop hook 中的檔案寫入交換為 POST 到您的驅動程式監聽的端點：

```sh theme={null}
#!/bin/sh
# Variant of the capture hook for runners on separate infrastructure.
# Set E2E_REPLY_URL on the runner to an endpoint the driver controls.
[ -n "${E2E_REPLY_URL:-}" ] || exit 0
sid=$(printf '%s' "${CLAUDE_CODE_REMOTE_SESSION_ID:-}" | sed 's/^cse_/session_/')
[ -n "$sid" ] || exit 0
jq -r '.last_assistant_message // empty' | \
  curl -fsS -X POST --data-binary @- "$E2E_REPLY_URL/$sid" >/dev/null 2>&1
exit 0
```

在驅動程式端，執行任何接受 POST 並保留回覆直到測試要求它的東西，例如 CI 工作內的小型 HTTP 監聽器或您已經執行的 webhook 接收器。hook 在您的基礎結構上執行，因此端點只需要可從您的執行器到達。

## 從 CI 進行驗證

`claude -p ... --environment` 和 `claude -p ... --cloud` 都使用 claude.ai OAuth 令牌進行驗證；API 金鑰（例如 `sk-ant-xxxxx`）不被接受用於任一呼叫。兩種方法使令牌在 CI 中可用。

### 長期 CI 主機

在執行指令碼的機器上使用專用自動化使用者帳戶以互動方式執行一次 `claude auth login`。Claude Code 在 macOS 上將令牌儲存在 OS 金鑰鏈中，或在 Linux 和 Windows 上儲存在 `~/.claude/.credentials.json` 中。在 macOS 主機上，其金鑰鏈無法寫入（如 SSH 工作階段中的典型情況，其中登入金鑰鏈保持鎖定），Claude Code 也會將令牌儲存在 `~/.claude/.credentials.json` 中。請參閱[認證管理](https://code.claude.com/docs/zh-TW/authentication.md#credential-management)。

CLI 在每次呼叫時自動重新整理短期存取令牌，但基礎重新整理令牌授予從初始登入起限制為 30 天，因此每 30 天在該主機上以互動方式重新執行一次 `claude auth login`。

### 短期 CI 執行器

目前沒有長期 CI 令牌。授予遠端工作階段控制的範圍 `user:sessions:claude_code` 在伺服器端限制為 30 天，因此 `claude setup-token`（它鑄造一年推論專用令牌）不涵蓋它。[環境祕密](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-an-environment-and-runner)也不被接受，因為它只授權執行器向環境註冊，而不是建立工作階段。

若要在短期執行器上佈建儲存的登入，請設定 [`CLAUDE_CODE_OAUTH_REFRESH_TOKEN` 和 `CLAUDE_CODE_OAUTH_SCOPES`](https://code.claude.com/docs/zh-TW/env-vars#variables)，以便 `claude auth login` 交換令牌而無需瀏覽器；相同的 30 天上限適用於重新整理授予。如果您需要不受人類帳戶約束的機器身份路徑，請聯絡您的 Anthropic 帳戶團隊。

## 建立專用測試環境

以程式設計方式建立和刪除環境，以便每個 CI 執行都獲得乾淨的環境；您的 CI 工作啟動的執行器註冊到新環境中。下面的建立和刪除呼叫是 claude.ai 上的**雲端環境**管理頁面使用的相同端點，它們需要 `anthropic-beta: ccr-byoc-2025-07-29` 標頭。

### 鑄造管理員令牌

`$ADMIN_TOKEN` 是持有 Owner 角色的帳戶的 claude.ai OAuth 存取令牌，以與[從 CI 進行驗證](#authenticate-from-ci)相同的方式鑄造：

* **鑄造它**：使用持有 Owner 角色的帳戶執行 `claude auth login`，然後從[長期 CI 主機](#long-lived-ci-host)說 Claude Code 儲存它的地方讀取目前的存取令牌。
* **每次執行時新鮮讀取它**：CLI 輪換存取令牌，相同的 30 天重新整理授予上限適用，因此不要儲存副本。
* **透過 stdin 傳遞它**：如範例所示，以便令牌永遠不會進入 curl 的引數清單或您的建置日誌。

### 建立環境

在不回顯的情況下擷取回應：`pool_secret` 是可以將執行器註冊到環境中的長期認證，因此將其儲存為遮罩 CI 祕密並僅列印環境 ID。保持令牌不在程序清單中的 `-H @-` 形式需要 curl 7.55 或更新版本；較舊的 curl 將 `@-` 視為文字標頭並在沒有授權的情況下傳送請求。

```bash theme={null}
create=$(curl -fsS -X POST -H @- \
  -H "anthropic-beta: ccr-byoc-2025-07-29" -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"name":"ci-test-environment"}' \
  https://api.anthropic.com/v1/code/runners/self-hosted/pools \
  <<<"Authorization: Bearer $ADMIN_TOKEN")
ENVIRONMENT_ID=$(jq -er .pool.pool_id <<<"$create")
ENVIRONMENT_SECRET=$(jq -er .pool_secret <<<"$create")
```

在[Owner 為組織開啟**允許自託管環境**](https://code.claude.com/docs/zh-TW/self-hosted-environments#availability-and-limitations)之前，呼叫失敗，出現 `403` `permission_error`，讀取 `self-hosted runners are disabled by your organization's policy`。

在此主機上啟動執行器，使用 `SELF_HOSTED_RUNNER_ENVIRONMENT_SECRET=$ENVIRONMENT_SECRET`，加上擷取 hook 和 `E2E_REPLY_DIR`，根據[在測試執行器上安裝擷取 hook](#install-the-capture-hook-on-your-test-runner)，然後執行測試指令碼。

### 刪除環境

執行完成時刪除環境，以便每個 CI 執行都從乾淨開始：

```bash theme={null}
curl -fsS -X DELETE -H @- \
  -H "anthropic-beta: ccr-byoc-2025-07-29" -H "anthropic-version: 2023-06-01" \
  "https://api.anthropic.com/v1/code/runners/self-hosted/pools/$ENVIRONMENT_ID" \
  <<<"Authorization: Bearer $ADMIN_TOKEN"
```
