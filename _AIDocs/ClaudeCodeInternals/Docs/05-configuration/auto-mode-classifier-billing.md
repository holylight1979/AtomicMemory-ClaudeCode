<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing | lastmod: 2026-10-30 | section: Configuration / Permissions and sandboxing -->
> 來源：https://code.claude.com/docs/zh-TW/auto-mode-classifier-billing（官方 zh-TW，lastmod 2026-10-30）｜分類：Configuration › Permissions and sandboxing｜EN 摘要：Resolve the Claude Code notice saying this session isn't eligible for auto mode's no-charge classifier requests: what it means, why it appears, and what to do.

# 自動模式分類器請求費用

> 解決 Claude Code 通知說此工作階段不符合自動模式免費分類器請求資格的問題：它的含義、為什麼會出現，以及該怎麼辦。

在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 中，分類器會在 shell 命令和網路請求等動作執行前檢查它們。在 [伺服器端檢查開啟](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review) 的地方，伺服器會將這些檢查作為工作階段自身模型請求的一部分執行，不收費。此通知表示伺服器的檢查無法到達您的工作階段，因此 Claude Code 改為進行自己的分類器請求，在您的帳戶上這些請求會計入您的權杖使用量：

```text theme={null}
We're changing auto mode to no longer charge for classifier requests in Claude Code. However, this session isn't eligible.
```

在提示處，Claude Code 會暫停它要以這種方式檢查的第一個動作，直到您回答。自動模式會繼續運作，其分類器請求會像以前一樣被計費。

最常見的原因是 Claude Code 和 API 之間有 LLM 閘道或代理伺服器，當 Claude Code 能夠識別出來時，通知會指出其名稱。按下 **Enter** 繼續，或參閱[使工作階段符合資格](#make-the-session-eligible)以防止它在新工作階段中出現。

## 回應通知

通知會保留該動作，直到您回答為止：

* **Enter** 繼續：保留的動作和工作階段的其餘部分使用 Claude Code 自己的分類器請求，按照之前的方式計費為代幣使用量，且該通知在該工作階段中不會再出現。當通知命名了閘道時，確認它會防止它在此機器上的 24 小時內再次出現。當它沒有時，通知會在下次工作階段回退時返回。
* **Esc** 或 **Ctrl+C** 取消：保留的動作不會執行，目前的回合停止，工作階段仍處於自動模式。沒有任何內容被記住，所以通知會在下一個檢查的動作之前再次出現。

若要停止使用自動模式，請在您回答後使用 `Shift+Tab` 切換權限模式。

在無法等待答案的地方，Claude Code 會報告相同的文字，工作階段會繼續以自動模式執行，除非此機器上過去 24 小時內的閘道確認已將其關閉。在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `-p` 時，它會將文字列印到 stderr，在 `stream-json` 輸出中，它會發出 `system` 警告訊息，Agent SDK 應用程式可以從訊息流中讀取。

## 使工作階段符合資格

如果閘道是原因，請要求您公司的管理員或您的閘道提供者讓請求和回覆保持不變地通過。這表示轉發請求標頭和本文欄位時保持原樣，包括閘道不識別的欄位，例如 `safeguards` 請求欄位，以及返回回應和串流事件時不刪除金鑰，例如 `safeguard_results` 欄位或重寫工具使用 ID，如[閘道相容性指南](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through)所述。以這種方式通過流量的閘道可繼續與此功能和未來功能搭配運作。新工作階段隨後會再次使用伺服器的檢查。

如果您已經知道您的閘道無法提供伺服器的檢查，請在啟動工作階段之前，在您的 shell 或 [`env` 設定金鑰](https://code.claude.com/docs/zh-TW/settings-reference#env)中將 `CLAUDE_CODE_AUTO_MODE_SERVER` 設定為 `0`，以告訴 Claude Code 不要在該處要求檢查：

```bash theme={null}
export CLAUDE_CODE_AUTO_MODE_SERVER=0
```

分類器請求隨後始終是 Claude Code 自己的，以相同方式計費，通知不會出現。在直接連線到 Anthropic API 時，該變數需要 Claude Code v2.1.281 或更新版本。在 `CLAUDE_CODE_AUTO_MODE_SERVER` 未設定的情況下設定 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` 也會關閉伺服器的檢查，除了[停用發行前功能](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#disable-pre-release-capabilities)所述的情況。

`CLAUDE_CODE_AUTO_MODE_SERVER` 是暫時設定，可能會在更新版本中移除。

## 為什麼會出現通知

使用 Pro、Max、Ultra 或 Team 方案時，您永遠不會看到此通知。若要了解哪些工作階段會向伺服器請求分類器檢查，請參閱[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)。如果您看到此通知，請檢查以下常見原因：

* **路徑中有 LLM 閘道或代理**：一個會刪除或重寫請求標頭、丟棄它不認識的請求欄位，或編輯回應的閘道。伺服器隨後永遠不會收到檢查請求，或 Claude Code 永遠不會收到結果。當您的設定或回應識別出閘道時，通知會將其命名。
* **伺服器端檢查尚未到達您的平台、區域或認證**：平台或區域是否執行檢查取決於該平台的推出。如果您看到通知且路徑中沒有閘道或代理，並且它持續出現，這是可能的原因。若要確認，請聯絡支援或您公司的管理員，或使用 `/feedback` 報告。

若要檢查處於自動模式的工作階段，請在 Claude Code 提示符處執行 `/status`：其 **Auto mode server** 列在伺服器的檢查決定工作階段的動作時讀取 `Enabled`，在工作階段已回退時讀取 `Disabled`。

當閘道截斷回應或將結果重寫成 Claude Code 無法讀取的形式時，您會收到沒有判決的拒絕，而不是此通知；請參閱[伺服器端 classifier 審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)。

## 相關資源

* [Auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)：什麼是 auto mode 以及它預設會阻止什麼
* [Server-side classifier review](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)：哪些工作階段要求伺服器檢查動作，以及每個工作階段所需的 Claude Code 版本
* [Gateway compatibility guide](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#feature-pass-through)：當閘道移除標頭或主體欄位時會發生什麼
* [The server returned no safety verdict](https://code.claude.com/docs/zh-TW/errors.md#the-server-returned-no-safety-verdict)：當伺服器對某個動作未提供判決時您看到的拒絕
* [Manage costs effectively](https://code.claude.com/docs/zh-TW/costs.md)：追蹤權杖使用量並降低 Claude Code 成本
