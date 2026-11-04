<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w34 | lastmod: 2026-10-23 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w34（官方 zh-TW，lastmod 2026-10-23）｜分類：What's New › What's New｜EN 摘要：Draft editable UI artboards with the /design skill, set the Concise output style, and start a Claude Code session on your machine from your phone.

# 第 34 週 · 2026 年 8 月 17–21 日

> 使用 /design 技能草擬可編輯的 UI 畫板、設定簡潔輸出風格，以及從手機在您的機器上啟動 Claude Code 工作階段。

版本 [v2.1.234 → v2.1.239](https://code.claude.com/docs/en/changelog.md#2-1-234)
3 項功能 · 8 月 17–21 日

/design
研究預覽

`/design` 技能將 Claude Design 的畫板工作流程帶入 CLI 和 Claude Code Desktop，以成品為基礎。使用簡短說明執行它，Claude 會發佈一個可編輯畫板的畫布供您的 UI 使用。選擇一個、調整它，然後讓 Claude 實現它。適用於 Pro、Max、Team 和 Enterprise。需要 v2.1.234 或更新版本。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/2SnAdpL4dJ18nKb3/images/whats-new/design-skill.mp4?fit=max&auto=format&n=2SnAdpL4dJ18nKb3&q=85&s=0b376a94227c14a4204af89c4c9fd7ac" />

描述您想要設計的內容，讓 Claude 草擬選項：

```text Claude Code theme={null}
> /design redesign the composer based on what people actually use it for
```

Claude 列印已發佈畫布的連結。開啟它、選擇一個畫板，然後告訴 Claude 要實現哪個選項。

[成品可用的位置](https://code.claude.com/docs/zh-TW/artifacts.md#availability)

簡潔輸出風格
v2.1.237

簡潔是一種新的內建輸出風格。Claude 以結果開頭並跳過前言和敘述，同時以與預設風格相同的徹底方式進行工作。當您要求解釋或更多詳細資訊時，Claude 會完整回答。錯誤報告、安全警告和破壞性操作的確認保持其完整內容。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/2SnAdpL4dJ18nKb3/images/whats-new/concise-output-style.mp4?fit=max&auto=format&n=2SnAdpL4dJ18nKb3&q=85&s=dfb40ec8921ed1bc82eb629042a8ec17" />

在 `/config` 中的 **輸出風格** 下開啟它，或在您的設定檔中設定它：

```json ~/.claude/settings.json {2} theme={null}
{
  "outputStyle": "Concise"
}
```

執行 `/clear` 或啟動新工作階段，Claude 的回覆以結果開頭。

[內建輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md#built-in-output-styles)

從手機在您的機器上啟動工作階段
行動

任何執行 `claude remote-control` 的機器現在都會在 Claude 應用程式的 Code 標籤頂部顯示為裝置卡片。Remote Control 也已不再處於研究預覽。

![Claude 行動應用程式中的 Code 標籤，其中 Devices 部分在工作階段清單上方顯示連接的 MacBook 作為裝置卡片](https://mintcdn.com/claude-code/2SnAdpL4dJ18nKb3/images/whats-new/remote-control-phone-start.jpg?fit=max\&auto=format\&n=2SnAdpL4dJ18nKb3\&q=85\&s=9f0ebedab23aa0e1732cc37782573907)

在您想要連接的機器上啟動 Remote Control，然後在手機上開啟 Code 標籤：

```bash terminal theme={null}
claude remote-control
```

您的機器在 Code 標籤頂部顯示為裝置卡片。點擊它以選擇目錄並在該處啟動工作階段。

[啟動 Remote Control 工作階段](https://code.claude.com/docs/zh-TW/remote-control.md#start-a-remote-control-session)

其他成果

Claude Code 現在會在 claude.ai 用量上限重設時自動繼續您的工作階段；從 `/config` 中的 **Continue automatically at usage limit** 列關閉它選用的 [`spellcheck` 設定](https://code.claude.com/docs/zh-TW/interactive-mode#check-spelling-as-you-type) 在您輸入時在提示輸入中為拼寫錯誤的單字加上底線，使用您安裝的 `aspell`、`hunspell` 或 `ispell`在具有開啟 GitLab 合併請求的分支上，使用透過 `glab auth login` 驗證的 `glab` CLI，頁尾會顯示一個 [`MR !N` 徽章](https://code.claude.com/docs/zh-TW/interactive-mode#gitlab-merge-requests)，其顏色取決於合併請求是草稿、開啟還是可合併從手機或 claude.ai/code 變更工作量級別，它會 [套用到您機器上的工作階段](https://code.claude.com/docs/zh-TW/remote-control.md#what-connected-devices-see)；由 Desktop 或 VS Code 託管的 Remote Control 工作階段也會向連接的裝置顯示工作階段的目前權限模式您可以在 Claude 工作時開啟 [`/permissions`](https://code.claude.com/docs/zh-TW/permissions#manage-permissions) 或執行 `/add-dir <path>`；權限規則變更適用於目前回合的其餘部分當背景工作讓 [`/goal`](https://code.claude.com/docs/zh-TW/goal#background-work-defers-evaluation) 等待時，Claude 在 30 分鐘後檢查它們，而不是無限期等待，並持續檢查，在工作階段閒置時以更長的間隔檢查；設定 `CLAUDE_CODE_GOAL_CHECKIN_MINUTES=0` 以選擇退出您自己的提示現在在文字記錄中呈現 markdown，具有突出顯示的程式碼區塊、內嵌程式碼和清單，與回覆的方式相同新的 [`ANTHROPIC_DEFAULT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#set-a-default-model-for-new-sessions) 環境變數設定新工作階段啟動的模型；`/model` 選擇仍會覆蓋它並在重新啟動時保持使用 `SendMessage` 上的 `notify_when_idle` 輸入，Claude 可以要求同一機器上的另一個 Claude Code 工作階段 [在它下次閒置時傳送一個通知](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#get-a-notice-when-another-session-goes-idle)將 [`keybindingFlavor`](https://code.claude.com/docs/zh-TW/interactive-mode#make-ctrl-w-delete-back-to-whitespace) 設定為 `"readline"`，使提示中的 `Ctrl+W` 刪除回到前一個空白字元，如 Bash 所做的那樣，而不是在標點符號（例如 `/`）處停止在原生 Windows 上，您的 Claude Code 工作階段現在可以 [使用 `SendMessage` 相互傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging#availability) 並使用 `ListAgents` 相互尋找，如同在 macOS 和 Linux 上一樣自託管執行器接受 `--defer-shutdown-max-min`，它 [在 SIGTERM 後的設定分鐘數內繼續為附加工作階段提供服務](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#defer-the-drain-past-the-first-signal)自託管執行器接受 `--proxy-authorization-command` 或 `--proxy-authorization-file` 為 [需要一個的出口代理提供新的 `Proxy-Authorization` 標頭](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy#authenticate-to-an-egress-proxy)

[v2.1.234–v2.1.239 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-234)
