<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugins/cli-hints | lastmod: 2026-09-25 | section: Plugins / Create plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugins/cli-hints（官方 zh-TW，lastmod 2026-09-25）｜分類：Plugins › Create plugins｜EN 摘要：Prompt Claude Code users to install your official-marketplace plugin by emitting a claude-code-hint tag from your CLI or SDK.

# 從您的 CLI 推薦您的外掛程式

> 透過從您的 CLI 或 SDK 發出 claude-code-hint 標籤，提示 Claude Code 使用者安裝您的官方市場外掛程式。

如果您維護 CLI 或 SDK，您的工具可以提示 Claude Code 使用者安裝您的外掛程式。當您的 CLI 偵測到它在 Claude Code 內執行時，應該將一行 `<claude-code-hint />` 標籤寫入 stderr。Claude Code 會在模型看到輸出之前從 Bash 和 PowerShell 工具輸出中移除該行，然後向使用者顯示一次性安裝提示。

此頁面僅適用於您的外掛程式列在 `claude-plugins-official` 或其他具有 Anthropic [官方市場名稱](https://code.claude.com/docs/zh-TW/plugins/security.md#official-marketplace-names)的市場中的情況。社群市場 `claude-community` 不是其中之一。

> [!NOTE]
>
> 若要發佈外掛程式，請參閱[發佈和分發外掛程式](https://code.claude.com/docs/zh-TW/plugins/publish.md)。

## 發出提示

僅在設定 `CLAUDECODE` 或 `CLAUDE_CODE_CHILD_SESSION` 時發出標籤，以便在使用者直接執行您的 CLI 時不會出現。

Claude Code 在透過 Bash 和 PowerShell 工具執行的命令以及 hook 命令中設定 `CLAUDECODE=1`。在 v2.1.172 及更新版本上，它也在那裡設定 `CLAUDE_CODE_CHILD_SESSION=1`。這些變數在哪些程序中攜帶它們方面有所不同：

* **`CLAUDECODE`**：由每個 Claude Code 版本設定。IDE 擴充功能也在其整合終端中設定它，因此僅在 `CLAUDECODE` 上的閘道也會在使用者在其中一個終端中直接執行您的 CLI 時發出標籤
* **`CLAUDE_CODE_CHILD_SESSION`**：僅在 Claude Code 本身啟動的子程序中設定。當您可以要求 v2.1.172 或更新版本時使用它

[環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)有詳細資訊。

以下範例在 `CLAUDECODE` 上設定閘道以獲得最廣泛的覆蓋範圍，並為官方市場中名為 `example-cli` 的外掛程式發出提示：

```javascript Node.js theme={null}
if (process.env.CLAUDECODE) {
  process.stderr.write(
    '<claude-code-hint v="1" type="plugin" value="example-cli@claude-plugins-official" />\n',
  )
}
```

```python Python theme={null}
import os, sys

if os.environ.get("CLAUDECODE"):
    print(
        '<claude-code-hint v="1" type="plugin" value="example-cli@claude-plugins-official" />',
        file=sys.stderr,
    )
```

```go Go theme={null}
if os.Getenv("CLAUDECODE") != "" {
    fmt.Fprintln(os.Stderr,
        `<claude-code-hint v="1" type="plugin" value="example-cli@claude-plugins-official" />`)
}
```

```shell Shell theme={null}
if [ -n "$CLAUDECODE" ]; then
  printf '%s\n' '<claude-code-hint v="1" type="plugin" value="example-cli@claude-plugins-official" />' >&2
fi
```

將 `example-cli` 替換為您的外掛程式在官方市場中的名稱。

您可以在每次呼叫時發出提示，因為 Claude Code 會為每個外掛程式提示一次。

若要檢查發出器，請在終端中執行 `CLAUDECODE=1 example-cli` 並確認標籤行出現在 stderr 上，然後執行 `example-cli` 而不使用變數，並確認沒有額外的列印。

## 提示格式

標籤必須佔據自己的一行；Claude Code 會忽略嵌入在行中間的標籤。

標籤採用三個屬性，全部必需：

| 屬性 | 說明 |
| :- | :- |
| `v` | 協議版本。`1` 是唯一支援的值 |
| `type` | 提示類型。`plugin` 是唯一支援的值 |
| `value` | `name@marketplace` 形式的外掛程式識別碼 |

值可以是雙引號或不帶引號；不帶引號的值不能包含空格。

即使 `v` 或 `type` 無法識別，Claude Code 也會從輸出中移除該行。

## 檢查提示何時出現

提示僅在互動式終端工作階段中出現。在 `claude -p` 執行、子代理執行和 hook 命令輸出中，標籤會被移除，不會顯示提示。以下所有檢查也必須通過：

* **官方且可安裝**：`value` 命名一個 Claude Code 在其官方市場本機副本中找到的外掛程式，該外掛程式尚未安裝，且沒有原則阻止
* **分析開啟**：Claude Code 分析關閉的工作階段永遠不會提示，例如設定了 `DISABLE_TELEMETRY`、`DO_NOT_TRACK` 或 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` 的工作階段，或在第三方提供者（例如 Amazon Bedrock）上的工作階段，其中[自動遙測選擇退出](https://code.claude.com/docs/zh-TW/data-usage.md#default-behaviors-by-api-provider)適用
* **頻率限制**：每個工作階段一個提示，每個外掛程式一個提示（無論使用者的答案如何），以及在該機器上已提示 100 個外掛程式後沒有提示
* **未關閉**：使用者未選擇**否，且不再顯示外掛程式安裝提示**
* **本機、有人值守的工作階段**：工作階段的工作區是本機而不是在雲端或遠端機器上，且工作階段不是無人值守執行。例如，使用 `--cloud` 啟動的工作階段、提供遠端控制的工作階段或代理團隊隊友永遠不會提示

## 預覽使用者看到的內容

當[檢查提示何時出現](#check-when-the-prompt-appears)中的檢查通過時，Claude Code 會顯示一個**外掛程式推薦**對話框，如下所示：

```text theme={null}
─────────────────────────────────────────────────────────────
  外掛程式推薦

    example-cli 命令建議安裝外掛程式。

    外掛程式：example-cli
    市場：claude-plugins-official
    說明：example-cli 部署的官方整合

    您想要安裝它嗎？
    ❯ 1. 是，安裝
      2. 否
      3. 否，且不再顯示外掛程式安裝提示

─────────────────────────────────────────────────────────────
```

對話框命名 Claude 執行的 shell 命令的第一個單詞，以便使用者可以發現不匹配。每個答案都有一個效果：

* **是，安裝**：在[使用者範圍](https://code.claude.com/docs/zh-TW/plugins/install.md)安裝外掛程式
* **否，且不再顯示外掛程式安裝提示**：關閉該使用者的未來提示提示
* **30 秒內無答案**：計為**否**

## 後續步驟

* [發佈和分發外掛程式](https://code.claude.com/docs/zh-TW/plugins/publish.md)：進入每個市場的路由，包括提示所需的官方市場
* [外掛程式命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-install)：在工作階段外安裝相同外掛程式的 shell 命令
