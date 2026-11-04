<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/quickstart | lastmod: 2026-10-30 | section: Getting started / Getting started -->
> 來源：https://code.claude.com/docs/zh-TW/quickstart（官方 zh-TW，lastmod 2026-10-30）｜分類：Getting started › Getting started｜EN 摘要：Install Claude Code in your terminal, sign in, and use the CLI to explore your codebase and make your first code change.

# 快速入門

> 在終端機中安裝 Claude Code、登入，並使用 CLI 探索您的程式碼庫及進行第一次程式碼變更。

本快速入門介紹在終端機中使用 Claude Code：安裝 CLI、從第一個工作階段登入，以及在您自己的專案中將其用於常見的開發任務。

## 開始前

確保您擁有：

* 已開啟的終端機或命令提示字元
* 一個可以使用的程式碼專案
* 一個 [Claude 訂閱](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=quickstart_prereq)（Pro、Max、Ultra、Team 或 Enterprise）、[Claude Console](https://platform.claude.com/) 帳戶，或透過[支援的雲端提供商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)存取

> [!NOTE]
>
> 以下情況在其他頁面中說明：
>
> * **從未使用過終端機**：請從[終端機指南](https://code.claude.com/docs/zh-TW/terminal-guide)開始
> * **想在終端機以外的地方使用 Claude Code**：Claude Code 也可在[網頁](https://claude.ai/code)、[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md)、[VS Code](https://code.claude.com/docs/zh-TW/vs-code.md) 和 [JetBrains IDE](https://code.claude.com/docs/zh-TW/jetbrains.md)、[Slack](https://code.claude.com/docs/zh-TW/slack.md) 中使用，以及透過 [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) 和 [GitLab](https://code.claude.com/docs/zh-TW/gitlab-ci-cd.md) 在 CI/CD 中使用。請參閱[所有介面](https://code.claude.com/docs/zh-TW/overview.md#use-claude-code-everywhere)。

## 步驟 1：安裝 Claude Code

若要安裝 Claude Code，請開啟終端機並執行適用於您系統的命令。如果您之前未使用過終端機，[終端機指南](https://code.claude.com/docs/zh-TW/terminal-guide)會說明如何開啟終端機並貼上命令。

> [tab] 原生安裝（建議）
>
> **macOS、Linux、WSL：**
>
> ```bash theme={null}
> curl -fsSL https://claude.ai/install.sh | bash
> ```
>
> 在 Windows 上，當您在 PowerShell 中時，提示字元會顯示 `PS C:\`，而在 CMD 中時會顯示 `C:\`（不含 `PS`）。
>
> **Windows PowerShell：**
>
> ```powershell theme={null}
> irm https://claude.ai/install.ps1 | iex
> ```
>
> **Windows CMD：**
>
> ```batch theme={null}
> curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
> ```
>
> 安裝命令在下載 Claude Code 時不會顯示進度。當安裝程式完成時，請開啟新的終端機視窗並執行 `claude --version`。正常的安裝會列印版本號碼。如果您的 shell 說找不到 `claude` 或無法識別，安裝目錄還未在您的 PATH 上：請參閱[修正您的 PATH](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#command-not-found-claude-after-installation)。
>
> 如果您看到 `The token '&&' is not a valid statement separator`，表示您在 PowerShell 中，而非 CMD。如果您看到 `'irm' is not recognized as an internal or external command`，表示您在 CMD 中，而非 PowerShell。
>
> 如果安裝命令失敗並出現 `syntax error near unexpected token '<'`、`403` 或其他任何錯誤，請參閱[疑難排解安裝](https://code.claude.com/docs/zh-TW/troubleshoot-install.md#find-your-error)以將錯誤與修正相對應，並查看替代安裝方法。
>
> 建議在原生 Windows 上安裝 [Git for Windows](https://git-scm.com/downloads/win)，以便 Claude Code 可以使用 Bash 工具。如果未安裝 Git for Windows，Claude Code 會改用 PowerShell 作為殼層工具。WSL 設定不需要 Git for Windows。
>
> > [!NOTE]
> >
> > 原生安裝會在背景自動更新，以保持您使用最新版本。

> [tab] Homebrew
>
> ```bash theme={null}
> brew install --cask claude-code
> ```
>
> Homebrew 提供兩個 casks。`claude-code` 追蹤穩定版本通道，通常比最新版本晚約一週，並跳過有重大迴歸的版本。`claude-code@latest` 追蹤最新通道，並在新版本發佈時立即接收。
>
> > [!NOTE]
> >
> > Homebrew 安裝不會自動更新。執行 `brew upgrade claude-code` 或 `brew upgrade claude-code@latest`（取決於您安裝的 cask），以取得最新功能和安全修正。

> [tab] WinGet
>
> ```powershell theme={null}
> winget install Anthropic.ClaudeCode
> ```
>
> > [!NOTE]
> >
> > WinGet 安裝不會自動更新。定期執行 `winget upgrade Anthropic.ClaudeCode` 以取得最新功能和安全修正。

您也可以在 Debian、Fedora、RHEL 和 Alpine 上使用 [apt、dnf 或 apk](https://code.claude.com/docs/zh-TW/setup.md#install-with-linux-package-managers) 進行安裝。

若要確認安裝成功，請執行：

```bash theme={null}
claude --version
```

此命令會列印版本號碼，後面跟著 `(Claude Code)`。

## 步驟 2：開始您的第一個工作階段

在任何專案目錄中開啟終端機，然後啟動 Claude Code：

```bash theme={null}
cd /path/to/your/project
claude
```

將 `/path/to/your/project` 替換為您要處理的專案路徑。

Claude Code 會在首次使用時提示您登入。若使用 Claude 訂閱或 Console 帳戶，請依照提示在瀏覽器中完成身分驗證。如果您已設定 `ANTHROPIC_API_KEY` 環境變數，且在 Claude Code 詢問是否使用該金鑰時予以核准，Claude Code 便會略過登入提示。

您可以使用下列任一種帳戶類型登入：

* [Claude Pro、Max、Ultra、Team 或 Enterprise](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=quickstart_login)（建議）
* [Claude Console](https://platform.claude.com/)（使用預付額度的 API 存取）。首次登入時，系統會自動在 Console 中建立一個「Claude Code」工作區，以便集中追蹤費用。
* [Amazon Bedrock、Google Cloud's Agent Platform 或 Microsoft Foundry](https://code.claude.com/docs/zh-TW/third-party-integrations.md)（企業雲端供應商）
* 自行託管的 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)（如果您的組織有執行的話）：您的管理員會預先設定閘道 URL，而 `/login` 會直接開啟 **Cloud gateway** 畫面，供您使用企業 SSO 登入

登入後，您的憑證會被儲存，之後不需要再次登入。如需了解更多資訊，請參閱[憑證管理](https://code.claude.com/docs/zh-TW/authentication.md#credential-management)。

Claude Code 提示字元會出現，其上方會顯示版本、目前的模型及工作目錄。輸入 `/help` 以查看可用的命令，或輸入 `/resume` 以繼續先前的對話。若之後要切換帳戶或重新進行身分驗證，請在執行中的工作階段內輸入 `/login`。

## 步驟 3：提出您的第一個問題

試試以下其中一個命令：

```text wrap theme={null}
what does this project do?
```

Claude 將分析您的檔案並提供摘要。您也可以提出更具體的問題：

```text wrap theme={null}
what technologies does this project use?
```

```text wrap theme={null}
where is the main entry point?
```

```text wrap theme={null}
explain the folder structure
```

您也可以詢問 Claude 關於其自身功能的問題：

```text wrap theme={null}
what can Claude Code do?
```

```text wrap theme={null}
how do I create custom skills in Claude Code?
```

```text wrap theme={null}
can Claude Code work with Docker?
```

> [!NOTE]
>
> Claude Code 會視需要讀取您的專案檔案。無需手動新增上下文。

## 步驟 4：進行您的第一次程式碼變更

試試一個小任務：

```text wrap theme={null}
add a hello world function to the main file
```

Claude Code 會找到適當的檔案並向您顯示變更內容。如果它在進行變更前詢問，請選擇 **Yes** 以核准。

工作階段的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)決定了 Claude 可以在不先詢問您的情況下執行哪些動作。隨時按下 `Shift+Tab` 即可切換您目前所在工作階段的權限模式。

## 步驟 5：搭配 Claude Code 使用 Git

Claude Code 讓 Git 操作變得像對話一樣自然：

```text wrap theme={null}
what files have I changed?
```

```text wrap theme={null}
commit my changes with a descriptive message
```

您也可以透過提示詞執行更複雜的 Git 操作：

```text wrap theme={null}
create a new branch called feature/quickstart
```

```text wrap theme={null}
show me the last 5 commits
```

```text wrap theme={null}
help me resolve merge conflicts
```

## 步驟 6：修正錯誤或新增功能

以自然語言描述您想要的內容：

```text wrap theme={null}
add input validation to the user registration form
```

或修正現有問題：

```text wrap theme={null}
there's a bug where users can submit empty forms - fix it
```

## 步驟 7：試用其他常見工作流程

再試試幾個提示詞。您可以請 Claude 重構程式碼、撰寫測試、更新文件，或審查您的變更：

```text wrap theme={null}
refactor the authentication module to use async/await instead of callbacks
```

```text wrap theme={null}
write unit tests for the calculator functions
```

```text wrap theme={null}
update the README with installation instructions
```

```text wrap theme={null}
review my changes and suggest improvements
```

> [!TIP]
>
> 像與一位樂於助人的同事交談一樣與 Claude 對話。描述您想要達成的目標，它就會協助您實現。

## 基本命令

以下是日常使用中最重要的命令，依執行位置分組。

### Shell 命令

從您的終端機執行這些命令以啟動或繼續 Claude Code。

| 命令 | 功能 | 範例 |
| - | - | - |
| `claude` | 啟動互動模式 | `claude` |
| `claude "task"` | 使用初始提示啟動互動模式 | `claude "fix the build error"` |
| `claude -p "query"` | 執行一次性查詢，然後退出 | `claude -p "explain this function"` |
| `claude -c` | 在目前目錄中繼續最近的對話 | `claude -c` |
| `claude -r` | 恢復之前的對話 | `claude -r` |

請參閱 [CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)以取得完整的 shell 命令清單。

### 工作階段命令

在 Claude Code 啟動後於其內部執行這些命令。

| 命令 | 功能 | 範例 |
| - | - | - |
| `/clear` | 清除對話歷史 | `/clear` |
| `/help` | 顯示可用命令 | `/help` |
| `/exit` 或 Ctrl+D 兩次 | 退出 Claude Code | `/exit` |

請參閱 [命令參考](https://code.claude.com/docs/zh-TW/commands.md)以取得完整的工作階段命令清單。

## 初學者的專業提示

如需更多資訊，請參閱[最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)和[常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)。

> [accordion] 對您的請求要具體
>
> 不要這樣做："修復錯誤"
>
> 試試這樣："修復登入錯誤，使用者輸入錯誤認證後看到空白畫面"

> [accordion] 使用逐步說明
>
> 將複雜任務分解為步驟：
>
> ```text wrap theme={null}
> 1. create a new database table for user profiles
> 2. create an API endpoint to get and update user profiles
> 3. build a webpage that allows users to see and edit their information
> ```

> [accordion] 讓 Claude 先探索
>
> 在進行變更之前，讓 Claude 了解您的程式碼：
>
> ```text wrap theme={null}
> analyze the database schema
> ```
>
> ```text wrap theme={null}
> build a dashboard showing products that are most frequently returned by our UK customers
> ```

> [accordion] 使用快捷方式節省時間
>
> * 輸入 `/` 查看所有命令和 skills
> * 使用 Tab 進行命令完成
> * 按 ↑ 查看命令歷史
> * 按 `Shift+Tab` 循環切換權限模式

## 接下來呢？

現在您已經學習了基礎知識，請探索更多進階功能：

* [Claude Code 如何運作](https://code.claude.com/docs/zh-TW/how-claude-code-works.md)：了解代理式迴圈、內建工具以及 Claude Code 如何與您的專案互動
* [最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)：透過有效的提示和專案設定獲得更好的結果
* [常見工作流程](https://code.claude.com/docs/zh-TW/common-workflows.md)：常見任務的逐步指南
* [擴展 Claude Code](https://code.claude.com/docs/zh-TW/features-overview.md)：使用 CLAUDE.md、skill、hook、MCP 等進行自訂

請參閱[進階設定](https://code.claude.com/docs/zh-TW/setup.md)以了解安裝選項、手動更新或解除安裝說明。

## 獲取幫助

* **在 Claude Code 中**：輸入 `/help` 或詢問「how do I」問題
* **文件**：瀏覽本網站上的其他指南
* **課程**：參加 [Claude Code 101](https://academy.claude.com/courses/claude-code-101) 和其他免費自學課程，位於 [Claude Academy](https://academy.claude.com/)
* **社群**：加入 [Discord 伺服器](https://www.anthropic.com/discord) 以獲取提示和支援
