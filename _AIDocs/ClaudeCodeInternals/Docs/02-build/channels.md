<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/channels | lastmod: 2026-10-30 | section: Build with Claude Code / Automation -->
> 來源：https://code.claude.com/docs/zh-TW/channels（官方 zh-TW，lastmod 2026-10-30）｜分類：Build with Claude Code › Automation｜EN 摘要：Use channels to push messages, alerts, and webhooks into your Claude Code session from an MCP server. Forward CI results, chat messages, and monitoring events so Claude can react while you're away.

# 使用 channels 將事件推送到執行中的工作階段

> 使用 channels 從 MCP 伺服器將訊息、警報和 webhooks 推送到您的 Claude Code 工作階段。轉發 CI 結果、聊天訊息和監控事件，讓 Claude 在您不在時做出反應。

> [!NOTE]
>
> Channels 處於[研究預覽](#research-preview)階段。它們需要透過 claude.ai 或 Console API 金鑰進行 Anthropic 驗證，且在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上不可用。Team 和 Enterprise 組織必須[明確啟用它們](#enterprise-controls)。

Channel 是一個 MCP 伺服器，可將事件推送到您執行中的 Claude Code 工作階段，讓 Claude 能對您不在終端時發生的事情做出反應。Channels 可以是雙向的：Claude 讀取事件並通過同一 channel 回覆，就像聊天橋接一樣。事件只在工作階段開啟時到達，因此對於始終開啟的設定，您可以在背景程序或持久終端中執行 Claude。

與產生新鮮雲端工作階段或等待輪詢的整合不同，事件到達您已開啟的工作階段：請參閱 [channels 如何比較](#how-channels-compare)。

您將 channel 安裝為外掛程式，並使用您自己的認證進行設定。Telegram、Discord 和 iMessage 包含在研究預覽中。

當 Claude 通過 channel 回覆時，您會在終端中看到入站訊息，但看不到回覆文字。終端顯示工具呼叫和確認（如「已傳送」），實際回覆會出現在另一個平台上。

如果您管理 Team、Enterprise 或 Console 組織，請參閱[為您的組織啟用 channels](#enterprise-controls)。若要建立您自己的 channel，請參閱 [Channels 參考](https://code.claude.com/docs/zh-TW/channels-reference.md)。

## 支援的頻道

每個支援的頻道都是需要 [Bun](https://bun.sh) 的外掛程式。如需在連接真實平台之前親身體驗外掛程式流程的演示，請嘗試 [fakechat 快速入門](#quickstart)。

> [tab] Telegram
>
> 檢視完整的 [Telegram 外掛程式原始碼](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram)。
>
> **1. 建立 Telegram 機器人**
>
> 在 Telegram 中開啟 [BotFather](https://t.me/BotFather) 並傳送 `/newbot`。給它一個顯示名稱和一個以 `bot` 結尾的唯一使用者名稱。複製 BotFather 返回的權杖。
>
> **2. 安裝外掛程式**
>
> 在終端機中執行 `claude` 以啟動 Claude Code，然後在其提示字元輸入以下內容：
>
> ```
> /plugin install telegram@claude-plugins-official
> ```
>
> 如果安裝失敗，請對照 Claude Code 報告的訊息：
>
> * `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市集，然後重試安裝。
> * `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過時。使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱[在市集中找不到外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。
>
> 當安裝要求安裝範圍時，選擇使用者範圍選項，以便外掛程式在所有專案中可用。檢查安裝摘要：如果報告 `Run /reload-plugins to apply.`，請參閱[在不重新啟動的情況下套用外掛程式變更](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins)以使外掛程式的設定命令可用。
>
> **3. 設定您的權杖**
>
> 使用來自 BotFather 的權杖執行設定命令：
>
> ```
> /telegram:configure <token>
> ```
>
> 這會將其儲存到 `~/.claude/channels/telegram/.env`。您也可以在啟動 Claude Code 之前在 shell 環境中設定 `TELEGRAM_BOT_TOKEN`。
>
> **4. 在啟用頻道的情況下重新啟動**
>
> 退出 Claude Code 並使用頻道旗標重新啟動。這會啟動 Telegram 外掛程式，開始輪詢來自您機器人的訊息：
>
> ```bash theme={null}
> claude --channels plugin:telegram@claude-plugins-official
> ```
>
> **5. 配對您的帳戶**
>
> 開啟 Telegram 並向您的機器人傳送任何訊息。機器人會回覆配對代碼。
>
> > [!NOTE]
> >
> > 如果您的機器人沒有回應，請確保 Claude Code 使用上一步的 `--channels` 執行。機器人只能在頻道處於啟用狀態時回覆。
>
> 回到 Claude Code，執行：
>
> ```
> /telegram:access pair <code>
> ```
>
> 然後鎖定存取權，使只有您的帳戶可以傳送訊息：
>
> ```
> /telegram:access policy allowlist
> ```

> [tab] Discord
>
> 檢視完整的 [Discord 外掛程式原始碼](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/discord)。
>
> **1. 建立 Discord 機器人**
>
> 前往 [Discord 開發者入口網站](https://discord.com/developers/applications)，按一下**新應用程式**，並為其命名。在**機器人**部分中，建立使用者名稱，然後按一下**重設權杖**並複製權杖。
>
> **2. 啟用訊息內容意圖**
>
> 在您的機器人設定中，向下捲動至**特權閘道意圖**並啟用**訊息內容意圖**。
>
> **3. 邀請機器人加入您的伺服器**
>
> 前往 **OAuth2 > URL 產生器**。選擇 `bot` 範圍並啟用這些權限：
>
> * 檢視頻道
> * 傳送訊息
> * 在執行緒中傳送訊息
> * 讀取訊息歷史記錄
> * 附加檔案
> * 新增反應
>
> 開啟產生的 URL 以將機器人新增到您的伺服器。
>
> **4. 安裝外掛程式**
>
> 在終端機中執行 `claude` 以啟動 Claude Code，然後在其提示字元輸入以下內容：
>
> ```
> /plugin install discord@claude-plugins-official
> ```
>
> 如果安裝失敗，請對照 Claude Code 報告的訊息：
>
> * `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市集，然後重試安裝。
> * `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過時。使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱[在市集中找不到外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。
>
> 當安裝要求安裝範圍時，選擇使用者範圍選項，以便外掛程式在所有專案中可用。檢查安裝摘要：如果報告 `Run /reload-plugins to apply.`，請參閱[在不重新啟動的情況下套用外掛程式變更](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins)以使外掛程式的設定命令可用。
>
> **5. 設定您的權杖**
>
> 使用您複製的機器人權杖執行設定命令：
>
> ```
> /discord:configure <token>
> ```
>
> 這會將其儲存到 `~/.claude/channels/discord/.env`。您也可以在啟動 Claude Code 之前在 shell 環境中設定 `DISCORD_BOT_TOKEN`。
>
> **6. 在啟用頻道的情況下重新啟動**
>
> 退出 Claude Code 並使用頻道旗標重新啟動。這會連接 Discord 外掛程式，讓您的機器人可以接收和回應訊息：
>
> ```bash theme={null}
> claude --channels plugin:discord@claude-plugins-official
> ```
>
> **7. 配對您的帳戶**
>
> 在 Discord 上直接訊息您的機器人。機器人會回覆配對代碼。
>
> > [!NOTE]
> >
> > 如果您的機器人沒有回應，請確保 Claude Code 使用上一步的 `--channels` 執行。機器人只能在頻道處於啟用狀態時回覆。
>
> 回到 Claude Code，執行：
>
> ```
> /discord:access pair <code>
> ```
>
> 然後鎖定存取權，使只有您的帳戶可以傳送訊息：
>
> ```
> /discord:access policy allowlist
> ```

> [tab] iMessage
>
> 檢視完整的 [iMessage 外掛程式原始碼](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/imessage)。
>
> iMessage 頻道直接讀取您的訊息資料庫，並透過 AppleScript 傳送回覆。它需要 macOS，不需要機器人權杖或外部服務。
>
> **1. 授予完整磁碟存取權**
>
> 位於 `~/Library/Messages/chat.db` 的訊息資料庫受 macOS 保護。伺服器第一次讀取它時，macOS 會提示存取：按一下**允許**。提示會命名啟動 Bun 的任何應用程式，例如終端機、iTerm 或您的 IDE。
>
> 如果提示未出現或您按一下「不允許」，請在**系統設定 > 隱私與安全 > 完整磁碟存取**下手動授予存取權，並新增您的終端機。沒有這個，伺服器會立即退出，並顯示 `authorization denied`。
>
> **2. 安裝外掛程式**
>
> 在終端機中執行 `claude` 以啟動 Claude Code，然後在其提示字元輸入以下內容：
>
> ```
> /plugin install imessage@claude-plugins-official
> ```
>
> 如果安裝失敗，請對照 Claude Code 報告的訊息：
>
> * `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市集，然後重試安裝。
> * `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過時。使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱[在市集中找不到外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。
>
> 當安裝要求安裝範圍時，選擇使用者範圍選項，以便外掛程式在所有專案中可用。
>
> 如果安裝摘要報告 `Run /reload-plugins to apply.`，您不需要在此處理，因為下一步中的重新啟動會載入外掛程式。
>
> **3. 在啟用頻道的情況下重新啟動**
>
> 退出 Claude Code 並使用頻道旗標重新啟動：
>
> ```bash theme={null}
> claude --channels plugin:imessage@claude-plugins-official
> ```
>
> **4. 傳送訊息給自己**
>
> 在任何登入您 Apple ID 的裝置上開啟訊息，並向自己傳送訊息。它會立即到達 Claude：自聊天繞過存取控制，無需設定。
>
> > [!NOTE]
> >
> > Claude 傳送的第一個回覆會觸發 macOS 自動化提示，詢問您的終端機是否可以控制訊息。按一下 **OK**。
>
> **5. 允許其他寄件者**
>
> 預設情況下，只有您自己的訊息會通過。若要讓另一個聯絡人到達 Claude，請新增其控制代碼：
>
> ```
> /imessage:access allow +15551234567
> ```
>
> 控制代碼是 `+country` 格式的電話號碼或 Apple ID 電子郵件，例如 `user@example.com`。

## 快速入門

Fakechat 是一個官方支援的演示頻道，在 localhost 上執行聊天 UI，無需驗證，也無需設定外部服務。

安裝並啟用 fakechat 後，您可以在瀏覽器中輸入，訊息會到達您的 Claude Code 工作階段。Claude 回覆，回覆會顯示在瀏覽器中。測試 fakechat 介面後，嘗試 [Telegram](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/telegram)、[Discord](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/discord) 或 [iMessage](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/imessage)。

若要嘗試 fakechat 演示，您需要：

* Claude Code [已安裝並使用 claude.ai 帳戶或 Claude Console API 金鑰進行驗證](https://code.claude.com/docs/zh-TW/quickstart.md#step-1-install-claude-code)
* [Bun](https://bun.sh) 已安裝。預先建立的頻道外掛程式是 Bun 指令碼。使用 `bun --version` 檢查；如果失敗，[安裝 Bun](https://bun.sh/docs/installation)。
* **Team、Enterprise 或受管 Console 組織**：您的管理員必須在受管設定中[啟用頻道](#enterprise-controls)

**1. 安裝 fakechat 頻道外掛程式**

在終端機中執行 `claude` 以啟動 Claude Code，然後在其提示字元中輸入安裝命令：

```text theme={null}
/plugin install fakechat@claude-plugins-official
```

如果安裝失敗，請對照 Claude Code 報告的訊息：

* `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 新增市集，然後重試安裝。
* `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過期。使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試時顯示相同的訊息，請參閱[在市集中找不到外掛程式](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。

當安裝要求選擇安裝範圍時，選擇使用者範圍選項，以便外掛程式在您的所有專案中可用。

如果安裝摘要報告 `Run /reload-plugins to apply.`，您無需在此處理，因為下一步中的重新啟動會載入外掛程式。

**2. 在啟用頻道的情況下重新啟動**

退出 Claude Code，然後使用 `--channels` 重新啟動並傳遞您安裝的 fakechat 外掛程式：

```bash theme={null}
claude --channels plugin:fakechat@claude-plugins-official
```

fakechat 伺服器會自動啟動。啟動畫面顯示頻道通知，指出來自 `plugin:fakechat@claude-plugins-official` 的訊息直接注入此工作階段。如果外掛程式未安裝或不在核准的允許清單上，警告行會在該通知下方顯示問題名稱。

> [!TIP]
>
> 您可以將多個外掛程式傳遞到 `--channels`，以空格分隔。

**3. 推送訊息進去**

在 [http://localhost:8787](http://localhost:8787) 開啟 fakechat UI 並輸入訊息：

```text theme={null}
what's in my working directory?
```

訊息到達您的 Claude Code 工作階段。終端機將其顯示為入站頻道行，例如 `← fakechat · web: what's in my working directory?`，而模型將其接收為 `<channel source="plugin:fakechat:fakechat">` 事件，使用外掛程式的範圍伺服器名稱。Claude 讀取它，完成工作，並呼叫 fakechat 的 `reply` 工具。如果 Claude Code 要求第一次回覆的權限，請核准它。答案會顯示在聊天 UI 中。

如果 Claude 在您不在終端機前時遇到權限提示，工作階段會暫停，直到您回應。宣告[權限中繼功能](https://code.claude.com/docs/zh-TW/channels-reference.md#relay-permission-prompts)的頻道伺服器可以將這些提示轉發給您，以便您可以遠端核准或拒絕。對於無人值守使用，[`--dangerously-skip-permissions`](https://code.claude.com/docs/zh-TW/permission-modes#skip-all-checks-with-bypasspermissions-mode) 會略過大多數提示，但僅在您信任的環境中使用。即使如此，[任何模式都不會自動核准的操作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)仍然適用。

當您以非互動模式使用 `-p` 執行頻道時，需要終端機輸入的工具（例如多選題和 plan mode 核准）會被停用，因此工作階段永遠不會因等待輸入而停滯。

## 安全性

每個已批准的 channel 外掛程式都維護寄件者允許清單：只有您新增的 ID 可以推送訊息，其他所有人都會被無聲地丟棄。

Telegram 和 Discord 通過配對啟動清單：

1. 在 Telegram 或 Discord 中找到您的機器人並向其傳送任何訊息
2. 機器人回覆配對代碼
3. 在您的 Claude Code 工作階段中，在提示時批准代碼
4. 您的寄件者 ID 會新增到允許清單

iMessage 的工作方式不同：向自己傳送訊息會自動繞過閘道，您可以使用 `/imessage:access allow` 按控制代碼新增其他聯絡人。

除此之外，您可以使用 `--channels` 控制每個工作階段啟用哪些伺服器，您的組織可以使用 [`channelsEnabled`](#enterprise-controls) 在 claude.ai Team 和 Enterprise 計畫以及部署受管設定的 Console 組織上控制可用性。

在 `.mcp.json` 中還不足以推送訊息：伺服器也必須在 `--channels` 中命名。

允許清單也會閘道[權限中繼](https://code.claude.com/docs/zh-TW/channels-reference.md#relay-permission-prompts)（如果 channel 宣告它）。任何可以通過 channel 回覆的人都可以批准或拒絕您工作階段中的工具使用，因此只允許清單您信任具有該權限的寄件者。

## Enterprise 控制

管理員通過兩個[受管設定](https://code.claude.com/docs/zh-TW/settings.md)控制可用性，使用者無法覆蓋。預設值取決於您如何驗證：

* **claude.ai Team 和 Enterprise**：channels 被阻止，直到擁有者[啟用它們](#enable-channels-for-your-organization)。
* **Anthropic Console 與 API 金鑰驗證**：channels 預設被允許。只有在您的組織部署受管設定時才需要此設定。

在所有情況下，在使用者使用 `--channels` 為工作階段選擇加入之前，沒有 channel 會執行。

| 設定 | 目的 | 未設定時 |
| :- | :- | :- |
| `channelsEnabled` | 主開關。必須為 `true` 才能讓任何 channel 傳遞訊息。關閉時會阻止所有 channels，包括開發旗標。請參閱[為您的組織啟用 channels](#enable-channels-for-your-organization)。 | claude.ai Team 和 Enterprise：channels 被阻止。Console：channels 被允許，除非您的組織部署受管設定，在這種情況下 channels 被阻止，直到設定此金鑰 |
| `allowedChannelPlugins` | 啟用 channels 後可以註冊哪些外掛程式。設定時替換 Anthropic 維護的清單。 | 應用 Anthropic 預設清單 |

沒有組織的 Pro、Max 和 Ultra 使用者完全跳過這些檢查：channels 可用，使用者按工作階段選擇加入 `--channels`。

### 為您的組織啟用 channels

可以從 [**組織設定 > Claude Code > Channels**](https://claude.ai/admin-settings/claude-code) 為您的組織啟用頻道（需要擁有者角色），或通過在受管設定中將 `channelsEnabled` 設定為 `true`。

啟用後，您組織中的使用者可以使用 `--channels` 將 channel 伺服器選擇加入個別工作階段。如果設定已停用或未設定，MCP 伺服器仍會連接，其工具可以工作，但 channel 訊息不會到達。啟動警告會告訴使用者讓管理員啟用該設定。

### 限制可以執行哪些 channel 外掛程式

預設情況下，Anthropic 維護的允許清單上的任何外掛程式都可以註冊為 channel。Team 和 Enterprise 計畫上的管理員可以通過在受管設定中設定 `allowedChannelPlugins` 來用自己的清單替換該允許清單。使用此功能來限制允許哪些官方外掛程式、批准來自您自己的內部市場的 channels，或兩者。每個條目命名一個外掛程式及其來自的市場：

```json theme={null}
{
  "channelsEnabled": true,
  "allowedChannelPlugins": [
    { "marketplace": "claude-plugins-official", "plugin": "telegram" },
    { "marketplace": "claude-plugins-official", "plugin": "discord" },
    { "marketplace": "acme-corp-plugins", "plugin": "internal-alerts" }
  ]
}
```

如果您設定空陣列，您會阻止允許清單中的所有 channel 外掛程式，但 `--dangerously-load-development-channels` 仍可以為本地測試繞過該阻止。若要完全阻止 channels，包括開發旗標，請改為保持 `channelsEnabled` 未設定。

此設定需要 `channelsEnabled: true`。如果使用者傳遞一個不在您清單上的外掛程式到 `--channels`，Claude Code 會正常啟動，但 channel 不會註冊，啟動通知會解釋該外掛程式不在組織的已批准清單上。在 v2 MCP 用戶端執行階段上，channel 也可能無法註冊，因為 Claude Code [不會註冊協商協議修訂版本 2026-07-28 的 channel 伺服器](https://code.claude.com/docs/zh-TW/mcp.md#push-messages-with-channels)。

## 研究預覽

Channels 是研究預覽功能。可用性正在逐步推出，`--channels` 旗標語法和協議合約可能會根據回饋而改變。

在預覽期間，`--channels` 和 `--dangerously-load-development-channels` 都不會出現在 `claude --help` 中。這些旗標即使未列出也能運作。

在預覽期間，`--channels` 只接受來自 Anthropic 維護的允許清單的外掛程式，或來自您組織的允許清單（如果管理員已設定 [`allowedChannelPlugins`](#restrict-which-channel-plugins-can-run)）。[claude-plugins-official](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins) 中的 channel 外掛程式是預設已批准的集合。如果您傳遞不在有效允許清單上的東西，Claude Code 會正常啟動，但 channel 不會註冊，啟動通知會告訴您原因。

若要測試您正在建立的 channel，請將其傳遞至 `plugin:<name>@<marketplace>` 或 `server:<name>` 形式的 `--dangerously-load-development-channels`。請參閱[在研究預覽期間測試](https://code.claude.com/docs/zh-TW/channels-reference.md#test-during-the-research-preview)，以取得有關測試您建立的自訂 channels 的資訊。

在 [Claude Code GitHub 儲存庫](https://github.com/anthropics/claude-code/issues)上報告問題或回饋。

## Channels 如何比較

Claude Code 的多個功能連接到終端外的系統，每個都適合不同類型的工作：

| 功能 | 它的作用 | 適合 |
| - | - | - |
| [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) | 在新鮮雲端沙箱中執行任務，從 GitHub 複製 | 委派您稍後檢查的自包含非同步工作 |
| [Slack 中的 Claude](https://code.claude.com/docs/zh-TW/slack.md) | 從頻道或執行緒中的 `@Claude` 提及產生雲端工作階段 | 直接從團隊對話內容啟動任務 |
| 標準 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) | Claude 在任務期間查詢它；沒有任何東西被推送到工作階段 | 讓 Claude 按需存取讀取或查詢系統 |
| [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) | 您從 claude.ai 或 Claude 行動應用程式驅動您的本地工作階段 | 在遠離您的桌子時引導進行中的工作階段 |

Channels 通過將來自非 Claude 來源的事件推送到您已執行的本地工作階段，填補該清單中的空白。

* **聊天橋接**：通過 Telegram、Discord 或 iMessage 從您的手機詢問 Claude 一些事情，答案會在同一聊天中返回，而工作在您的機器上針對您的真實檔案執行。
* **[Webhook 接收器](https://code.claude.com/docs/zh-TW/channels-reference.md#example-build-a-webhook-receiver)**：來自 CI、您的錯誤追蹤器、部署管道或其他外部服務的 webhook 到達 Claude 已開啟您的檔案並記得您正在調試的地方。

## 後續步驟

一旦您有 channel 執行，請探索這些相關功能：

* [建立您自己的 channel](https://code.claude.com/docs/zh-TW/channels-reference.md)，用於尚未有外掛程式的系統
* [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)，從您的手機驅動本地工作階段，而不是將事件轉發到其中
* [工作階段範圍的排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)，按計時器輪詢，而不是對推送事件做出反應
