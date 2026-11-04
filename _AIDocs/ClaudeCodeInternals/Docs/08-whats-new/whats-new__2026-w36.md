<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w36 | lastmod: 2026-09-17 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w36（官方 zh-TW，lastmod 2026-09-17）｜分類：What's New › What's New｜EN 摘要：Switch to Claude Fable 5.1, let computer use run in the background on Desktop, and watch Claude's edits in a live /diff panel.

# 第 36 週 · 8 月 31 日 – 9 月 4 日，2026 年

> 切換至 Claude Fable 5.1，讓電腦使用在 Desktop 上於背景執行，並在即時 /diff 面板中觀看 Claude 的編輯。

版本 [v2.1.251 → v2.1.261](https://code.claude.com/docs/en/changelog.md#2-1-251)
4 項功能 · 8 月 31 日 – 9 月 4 日

Claude Fable 5.1
新模型

Claude Fable 5.1 在 Claude Code 中提供，具有 1M 權杖的內容視窗，而 `fable` 別名現在會選擇它。在 Claude 應用程式閘道工作階段中，`fable` 仍會選擇 Fable 5。如果您的閘道提供 Fable 5.1，請執行 `/model claude-fable-5-1`。需要 v2.1.257 或更新版本。

將目前工作階段切換至 Fable 5.1 並將其儲存為您的預設值：

```text Claude Code theme={null}
> /model fable
```

在 Anthropic API 上，選擇器只有在伺服器報告您的組織可用時才會列出 Fable，但輸入 `/model fable` 會直接與伺服器檢查。

[使用 Fable](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable)

電腦使用在 Desktop 上於背景執行
Desktop

在 macOS 上，Claude Code Desktop 應用程式中的電腦使用現在可在背景執行：Claude 會在您已核准的應用程式中看到並執行動作，同時您可以繼續工作。背景電腦使用在 Pro 和 Max 方案上處於測試版。

![Claude Code Desktop 工作階段，其中 Claude 要求使用 Xcode，旁邊有一張電腦使用權限卡，上面寫著「讓 Claude 在您核准的應用程式中看到並執行動作，在背景或完全控制您的螢幕」，以及一個「啟用」按鈕](https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/background-computer-use.jpg?fit=max\&auto=format\&n=f9HTZGyMtxIFOUgt\&q=85\&s=a599a6c6fa544cb8d1b426b93706caf4)

[讓 Claude 使用您的電腦](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)

全螢幕轉譯中的即時 diff 面板
v2.1.260

在全螢幕轉譯中，`/diff` 現在會在對話旁邊開啟一個面板，而不是您必須關閉的檢視器。該面板列出已變更的檔案及其新增和移除的行數，並在每次 Claude 編輯檔案或執行 shell 命令時重新整理。在面板中使用滑鼠選擇行，以將其附加到您的下一個提示。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/diff-panel.mp4?fit=max&auto=format&n=f9HTZGyMtxIFOUgt&q=85&s=9d7553c19e7f227891cd95f1f59d796d" />

啟用全螢幕轉譯、在 git 儲存庫中，以及在至少 110 欄寬的終端機中，切換面板：

```text Claude Code theme={null}
> /diff
```

再次執行 `/diff` 或按一下其標題中的 `✕` 以關閉它。

[Diff 面板](https://code.claude.com/docs/zh-TW/interactive-mode.md#diff-panel)

使用 /skill-doctor 尋找未使用的 skills
CLI

`/skill-doctor` 顯示您的每個 skill 在內容中的成本以及它被使用的頻率，因此您可以決定要關閉哪些。[skill 列表](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)中的每個 skill 都會在每個回合中新增到您的內容中，無論 Claude 是否使用它。需要 v2.1.252 或更新版本，且在跳過[功能旗標擷取](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中不可用。

在互動式工作階段中執行它，以在 `/plugin` 管理員的**統計資料**標籤中開啟報告：

```text Claude Code theme={null}
> /skill-doctor
```

在非互動式模式下使用 `-p`，Claude Code 會改為將報告列印為文字。

[尋找未使用的 skills](https://code.claude.com/docs/zh-TW/skills.md#find-unused-skills)

其他成果

[`PreModelSwitch`](https://code.claude.com/docs/zh-TW/hooks#premodelswitch) hook 可以阻止您要求的模型切換，而 [`PostModelSwitch`](https://code.claude.com/docs/zh-TW/hooks#postmodelswitch) hook 可以在工作階段的模型變更後為 Claude 新增內容[`/cost`](https://code.claude.com/docs/zh-TW/costs#prompt-cache-statistics) 新增了一行 `Prompt cache (main)`：從快取提供的輸入權杖份額、快取遺漏、快取是否預熱，以及當 Claude Code 可以命名時最後一次遺漏的可能原因。狀態行指令碼會取得相符的 `prompt_cache` 物件組織可以在 [`managedMcpServers`](https://code.claude.com/docs/zh-TW/managed-mcp#provide-servers-through-managed-settings) 受管設定下列出 HTTP 和 SSE MCP 伺服器，以將其提供給每個使用者，除了使用者自行新增的伺服器外`/effort` 和 `/model` 選擇器現在[為每個模型儲存個別的努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)；按 `s` 而不是 `Enter` 以僅將等級套用到目前工作階段根據預設，自動模式分類器[現在也會阻止](https://code.claude.com/docs/zh-TW/permission-modes.md#what-the-classifier-blocks-by-default)諸如從雲端執行個體中繼資料端點要求認證或連接到 Claude 未啟動的同層容器等動作在自動模式中，Claude Code 會在 Claude [首次讀取工作目錄外的檔案](https://code.claude.com/docs/zh-TW/permission-modes.md#first-read-outside-the-working-directories)前詢問您，並提供一個選項以從此後阻止此類讀取提高 [`bashOutputMaxChars`](https://code.claude.com/docs/zh-TW/settings-reference#bashoutputmaxchars) 和 [`taskOutputMaxChars`](https://code.claude.com/docs/zh-TW/settings-reference#taskoutputmaxchars)，最多 128,000 個字元，以便 Claude 內聯接收來自成功命令或背景工作的更多輸出提示的[字詞編輯快捷鍵遵循 readline](https://code.claude.com/docs/zh-TW/interactive-mode.md#make-ctrl-w-delete-back-to-whitespace)，適用於所有人，而 `keybindingFlavor` 設定不再有任何效果。`Ctrl+W` 刪除回到前一個空白字元，而 `Alt+B`、`Alt+F` 和 `Alt+D` 將標點符號（例如 `/` 和 `.`）視為字詞分隔符如果您在專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中將 `defaultMode` 設定為 `"bypassPermissions"`，它[不再生效](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)，工作階段會以手動模式啟動；改為在使用者或受管設定中設定 `"bypassPermissions"`，或傳遞 `--permission-mode`基於座位的企業方案現在[預設為 Opus 5](https://code.claude.com/docs/zh-TW/model-config.md#default-model-setting)在 VS Code 擴充功能中，按一下提示框底部的模型名稱以[開啟模型選擇器](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)在 VS Code 擴充功能中，在命令選單的自訂部分中選擇**輸出樣式**以[選擇輸出樣式](https://code.claude.com/docs/zh-TW/vs-code.md#use-the-prompt-box)，包括您的自訂樣式

[v2.1.251–v2.1.261 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-251)
