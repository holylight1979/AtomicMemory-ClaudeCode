<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w29 | lastmod: 2026-09-09 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w29（官方 zh-TW，lastmod 2026-09-09）｜分類：What's New › What's New｜EN 摘要：Pull live data into published artifacts through MCP connectors, and use Claude Code with a screen reader in the new screen reader mode.

# 第 29 週 · 2026 年 7 月 13–17 日

> 透過 MCP 連接器將即時資料拉入已發佈的成品中，並在新的螢幕閱讀器模式中使用 Claude Code 搭配螢幕閱讀器。

版本 [v2.1.207 → v2.1.212](https://code.claude.com/docs/en/changelog.md#2-1-207)
2 項功能 · 7 月 13–17 日

成品呼叫您的 MCP 連接器
web

已發佈的成品現在可以在每次有人檢視時呼叫 MCP 連接器，因此儀表板會顯示即時資料，並可按需執行動作，而不是建立該成品的工作階段中的快照。每次呼叫都會透過檢視帳戶自己的連線執行，檢視者在頁面首次連接器呼叫前會核准存取。本週還新增了公開分享連結、Team 和 Enterprise 方案上的編輯者角色，以及從 Claude Tag 工作階段建立的成品。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/ItzF3QVI6L0QypjJ/images/whats-new/artifacts-mcp.mp4?fit=max&auto=format&n=ItzF3QVI6L0QypjJ&q=85&s=ff8b81ed52b26c773899dc28cec959e6" />

在您的提示中命名連接器和您想要的資料：

```text title="Claude Code" wrap theme={null}
Build a dashboard artifact of open pull requests that pulls the live list through my GitHub connector when the page loads.
```

[使用 MCP 連接器拉取即時資料](https://code.claude.com/docs/zh-TW/artifacts.md#pull-live-data-with-mcp-connectors)

螢幕閱讀器模式
CLI

螢幕閱讀器模式將視覺終端介面替換為純文字、線性文字：不使用方框、旋轉器和就地重繪，Claude Code 會列印標籤行，螢幕閱讀器（例如 VoiceOver 或 NVDA）會依序讀取，因此您可以核准權限並從頭到尾檢視輸出。使用旗標按工作階段開啟、使用 `CLAUDE_AX_SCREEN_READER` 環境變數按 shell 開啟，或使用 `axScreenReader` 設定在所有地方開啟。

在螢幕閱讀器模式中啟動工作階段：

```bash terminal theme={null}
claude --ax-screen-reader
```

[開啟螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md#turn-on-screen-reader-mode)

其他改進

`/fork` 現在會將您的對話複製到新的背景工作階段中，在 `claude agents` 中有自己的列，同時您可以繼續工作；它過去啟動的工作階段內分叉子代理現在是 `/subtask`[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry)在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上不再需要 `CLAUDE_CODE_ENABLE_AUTO_MODE` 選擇加入；管理員可以使用 `disableAutoMode` 將其關閉執行時間超過兩分鐘的 MCP 工具呼叫現在會自動移至背景，以便工作階段保持可用；使用 `CLAUDE_CODE_MCP_AUTO_BACKGROUND_MS` 調整或停用閾值新的 `claude auto-mode reset` 會還原預設自動模式設定，`--yes` 會略過確認提示新的 [企業啟動器](https://code.claude.com/docs/zh-TW/corporate-launcher.md)支援：`CLAUDE_CODE_PROCESS_WRAPPER` 或 `processWrapper` 設定會透過必要的包裝器可執行檔執行 Claude Code 從其自己的二進位檔啟動的程序，例如背景服務和代理檢視工作階段`vimInsertModeRemaps` 設定會將兩鍵插入模式序列（例如 `jj`）對應到 vim 模式中的 Escape`--forward-subagent-text` 和 `CLAUDE_CODE_FORWARD_SUBAGENT_TEXT` 在 [stream-json 輸出](https://code.claude.com/docs/zh-TW/headless.md)中包含子代理文字和思考區塊工作階段範圍的上限會停止失控迴圈：WebSearch 呼叫和子代理生成各預設為 200，可使用 `CLAUDE_CODE_MAX_WEB_SEARCHES_PER_SESSION` 和 `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` 調整「一律允許」權限規則會儲存在存放庫根目錄，因此在 git worktree 中授予的核准會在工作階段和 worktree 中持續Amazon Bedrock、Google Cloud 的 Agent Platform 和 AWS 上的 Claude Platform 現在預設為 Claude Opus 4.8摺疊的工具摘要行會顯示即時經過時間計數器，因此長時間執行的工具呼叫會明顯計時，而不是看起來卡住

[v2.1.207–v2.1.212 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-207)
