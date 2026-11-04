<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/common-workflows | lastmod: 2026-10-22 | section: Getting started / Use Claude Code -->
> 來源：https://code.claude.com/docs/zh-TW/common-workflows（官方 zh-TW，lastmod 2026-10-22）｜分類：Getting started › Use Claude Code｜EN 摘要：Step-by-step guides for exploring codebases, fixing bugs, refactoring, testing, and other everyday tasks with Claude Code.

# 常見工作流程

> 使用 Claude Code 探索程式碼庫、修復錯誤、重構、測試和其他日常任務的逐步指南。

本頁涵蓋日常開發的簡短食譜。如需更高層級的提示和背景資訊管理指導，請參閱[最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)。

本頁涵蓋：

* [提示食譜](#prompt-recipes)，用於探索程式碼、修復錯誤、重構、測試、PR 和文件
* [繼續之前的對話](#resume-previous-conversations)，以便任務可以跨越多個會話
* [使用 worktrees 執行平行會話](#run-parallel-sessions-with-worktrees)，以便並行編輯不會衝突
* [編輯前規劃](#plan-before-editing)，以在變更觸及磁碟前檢查變更
* [將研究委派給 subagents](#delegate-research-to-subagents)，以保持主要背景資訊清潔
* [將 Claude 管道輸入指令碼](#pipe-claude-into-scripts)，用於 CI 和批次處理

## 提示食譜

這些是日常任務的提示模式，例如探索陌生程式碼、除錯、重構、編寫測試和建立 PR。每個都可在任何 Claude Code 介面中工作；根據您的專案調整措辭。

### 了解新的程式碼庫

如需在 monorepo 或大型程式碼庫中配置 Claude Code，請參閱 [Monorepos 和大型儲存庫](https://code.claude.com/docs/zh-TW/large-codebases.md)。

#### 快速取得程式碼庫概覽

假設您剛加入一個新專案，需要快速了解其結構。

**1. 導航到專案根目錄**

```bash theme={null}
cd /path/to/project 
```

將 `/path/to/project` 替換為您專案的路徑。

**2. 啟動 Claude Code**

```bash theme={null}
claude 
```

**3. 要求高層級概覽**

```text wrap theme={null}
give me an overview of this codebase
```

**4. 深入探討特定元件**

```text wrap theme={null}
explain the main architecture patterns used here
```

```text wrap theme={null}
what are the key data models?
```

```text wrap theme={null}
how is authentication handled?
```

> [!TIP]
>
> 提示：
>
> * 從廣泛的問題開始，然後縮小到特定領域
> * 詢問專案中使用的編碼慣例和模式
> * 要求提供專案特定術語的詞彙表

#### 尋找相關程式碼

假設您需要找到與特定功能或功能相關的程式碼。

**1. 要求 Claude 尋找相關檔案**

```text wrap theme={null}
find the files that handle user authentication
```

**2. 取得元件如何互動的背景資訊**

```text wrap theme={null}
how do these authentication files work together?
```

**3. 了解執行流程**

```text wrap theme={null}
trace the login process from front-end to database
```

> [!TIP]
>
> 提示：
>
> * 明確說明您要尋找的內容
> * 使用專案中的領域語言
> * 為您的語言安裝[程式碼智能外掛](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)，以便 Claude 進行精確的「前往定義」和「尋找參考」導航

***

### 有效地修復錯誤

假設您遇到了錯誤訊息，需要找到並修復其來源。

**1. 與 Claude 分享錯誤**

```text wrap theme={null}
I'm seeing an error when I run npm test
```

**2. 要求修復建議**

```text wrap theme={null}
suggest a few ways to fix the @ts-ignore in user.ts
```

**3. 應用修復**

```text wrap theme={null}
update user.ts to add the null check you suggested
```

> [!TIP]
>
> 提示：
>
> * 告訴 Claude 重現問題的命令並取得堆疊追蹤
> * 提及重現錯誤的任何步驟
> * 讓 Claude 知道錯誤是間歇性的還是持續的

***

### 重構程式碼

假設您需要更新舊程式碼以使用現代模式和實踐。

如需將整個程式碼庫移植到新語言，請參閱部落格上的[Anthropic 如何使用 Claude Code 執行大規模程式碼遷移](https://claude.com/blog/ai-code-migration)。

**1. 識別用於重構的舊版程式碼**

```text wrap theme={null}
find deprecated API usage in our codebase
```

**2. 取得重構建議**

```text wrap theme={null}
suggest how to refactor utils.js to use modern JavaScript features
```

**3. 安全地應用變更**

```text wrap theme={null}
refactor utils.js to use ES2024 features while maintaining the same behavior
```

**4. 驗證重構**

```text wrap theme={null}
run tests for the refactored code
```

> [!TIP]
>
> 提示：
>
> * 要求 Claude 解釋現代方法的優點
> * 在需要時要求變更保持向後相容性
> * 以小的、可測試的增量進行重構

***

### 使用測試

假設您需要為未涵蓋的程式碼新增測試。

**1. 識別未測試的程式碼**

```text wrap theme={null}
find functions in NotificationsService.swift that are not covered by tests
```

**2. 產生測試框架**

```text wrap theme={null}
add tests for the notification service
```

**3. 新增有意義的測試案例**

```text wrap theme={null}
add test cases for edge conditions in the notification service
```

**4. 執行並驗證測試**

```text wrap theme={null}
run the new tests and fix any failures
```

Claude 可以產生遵循您專案現有模式和慣例的測試。要求測試時，請明確說明您想驗證的行為。Claude 會檢查您現有的測試檔案，以符合已在使用的風格、框架和斷言模式。

若要提高涵蓋範圍，請要求 Claude 識別您可能遺漏的邊界情況。Claude 可以分析您的程式碼路徑，並建議測試錯誤條件、邊界值和容易忽視的意外輸入。

***

### 建立提取請求

您可以直接要求 Claude 建立提取請求（「為我的變更建立 pr」），或逐步引導 Claude 完成：

**1. 總結您的變更**

```text wrap theme={null}
summarize the changes I've made to the authentication module
```

**2. 產生提取請求**

```text wrap theme={null}
create a pr
```

**3. 檢查並細化**

```text wrap theme={null}
enhance the PR description with more context about the security improvements
```

若要稍後找到會話，請執行 `claude --from-pr 1234`，並使用您自己的 PR 編號，這會開啟會話選擇器，篩選連結到該 PR 的會話，或將 PR URL 貼到 [`/resume` 選擇器](https://code.claude.com/docs/zh-TW/sessions#use-the-session-picker)搜尋中。當 Claude 使用 `gh pr create` 或 `glab mr create` 建立提取請求時，Claude Code 會將會話連結到 PR，以及當 Claude [處理現有 PR](https://code.claude.com/docs/zh-TW/agent-view.md#pull-request-status) 時。

> [!TIP]
>
> 在提交前檢查 Claude 產生的 PR，並要求 Claude 突出顯示潛在的風險或考慮事項。

### 處理文件

假設您需要為程式碼新增或更新文件。

**1. 識別未記錄的程式碼**

```text wrap theme={null}
find functions without proper JSDoc comments in the auth module
```

**2. 產生文件**

```text wrap theme={null}
add JSDoc comments to the undocumented functions in auth.js
```

**3. 檢查並增強**

```text wrap theme={null}
improve the generated documentation with more context and examples
```

**4. 驗證文件**

```text wrap theme={null}
check if the documentation follows our project standards
```

> [!TIP]
>
> 提示：
>
> * 指定您想要的文件風格（JSDoc、docstrings 等）
> * 要求文件中的範例
> * 要求公開 API、介面和複雜邏輯的文件

***

### 在筆記和非程式碼資料夾中工作

Claude Code 可在任何目錄中工作。在筆記保管庫、文件資料夾或任何 markdown 檔案集合中執行它，以搜尋、編輯和重新組織內容，就像您處理程式碼一樣。

`.claude/` 目錄和 `CLAUDE.md` 與其他工具的設定目錄並存，不會產生衝突。Claude 在每次工具呼叫時都會重新讀取檔案，所以它會在下次讀取該檔案時看到您在另一個應用程式中所做的編輯。

***

### 使用影像

假設您需要在程式碼庫中使用影像，並希望 Claude 幫助分析影像內容。

**1. 將影像新增到對話中**

您可以使用以下任何方法：

1. 將影像拖放到 Claude Code 視窗中
2. 複製影像並使用 `Ctrl+V` 將其貼到 CLI 中，或在 [Windows 和 WSL 上使用 `Alt+V`](https://code.claude.com/docs/zh-TW/interactive-mode#general-controls)
3. 向 Claude 提供影像路徑。例如，「分析此影像：/path/to/your/image.png」

**2. 要求 Claude 分析影像**

```text wrap theme={null}
What does this image show?
```

```text wrap theme={null}
Describe the UI elements in this screenshot
```

```text wrap theme={null}
Are there any problematic elements in this diagram?
```

**3. 使用影像作為背景資訊**

```text wrap theme={null}
Here's a screenshot of the error. What's causing it?
```

```text wrap theme={null}
This is our current database schema. How should we modify it for the new feature?
```

**4. 從視覺內容取得程式碼建議**

```text wrap theme={null}
Generate CSS to match this design mockup
```

```text wrap theme={null}
What HTML structure would recreate this component?
```

> [!TIP]
>
> 提示：
>
> * 當文字描述不清楚或繁瑣時，使用影像
> * 包含錯誤、UI 設計或圖表的螢幕截圖以獲得更好的背景資訊
> * 您可以在對話中使用多個影像
> * 影像分析適用於圖表、螢幕截圖、模型等
> * 當 Claude 參考影像時（例如 `[Image #1]`），`Cmd+Click`（Mac）或 `Ctrl+Click`（Windows/Linux）連結以在預設檢視器中開啟影像

***

### 參考檔案和目錄

使用 @ 快速包含檔案或目錄，無需等待 Claude 讀取它們。

**1. 參考單個檔案**

```text wrap theme={null}
Explain the logic in @src/utils/auth.js
```

當檔案符合 [Read 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#read-tool-behavior)的 token 限制（預設為 25,000 個 token）時，這會在對話中包含檔案的內容。大於 256KB 的文字檔案不會被包含。

**2. 參考目錄**

```text wrap theme={null}
What's the structure of @src/components?
```

**3. 參考 MCP 資源**

```text wrap theme={null}
Show me the data from @github:repos/owner/repo/issues
```

這使用 @server:resource 格式從連接的 MCP 伺服器取得資料。有關詳細資訊，請參閱 [MCP 資源](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-resources)。

> [!TIP]
>
> 提示：
>
> * 檔案路徑可以是相對的或絕對的
> * 輸入 `@` 以開啟路徑建議功能表，然後按 Enter 或 Tab 以接受反白顯示的路徑，再按 Enter 以傳送訊息
> * @ 檔案參考會在檔案的目錄和父目錄中新增 `CLAUDE.md` 到背景資訊
> * 目錄參考顯示檔案清單，而不是內容
> * 您可以在單個訊息中參考多個檔案（例如「@file1.js and @file2.js」）

若要阻止 `@` 參考包含檔案內容和目錄清單，請在您的 shell 中，或在使用者設定或[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)的 [`env` 區塊](https://code.claude.com/docs/zh-TW/env-vars#set-variables-in-settings-files)中，將 [`CLAUDE_CODE_DISABLE_FILE_MENTIONS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `1`。Claude 隨後會收到您參考的路徑，並附帶一則說明，指示其使用檔案工具讀取這些路徑。此變數需要 Claude Code v2.1.299 或更新版本，且 Claude Code 會在專案和本機設定中忽略它。

當 Claude Code 包含您以 `@` 參考的檔案時，您的 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 不會執行，因為它不會進行任何工具呼叫。如果您依賴這些 hook 來控制 Claude 讀取的內容，請封鎖特定路徑，或阻止 `@` 參考包含檔案：

* **封鎖特定路徑**：為這些路徑新增 [`Read` 拒絕規則](https://code.claude.com/docs/zh-TW/permissions#read-and-edit)。Claude Code 不會包含符合該規則的檔案。
* **阻止 `@` 參考包含檔案**：設定 `CLAUDE_CODE_DISABLE_FILE_MENTIONS=1`，這會阻止您訊息中的 `@` 檔案和目錄參考包含內容，即使是您的 hook 未檢查的路徑也是如此。之後，在 Claude 使用 `Read` 等工具開啟所參考的路徑之前，您相符的 hook 會先執行。

***

### 按排程執行 Claude

假設您想讓 Claude 自動定期處理任務，例如每天早上檢查開放 PR、每週審計依賴項或在夜間檢查 CI 失敗。

根據您想讓任務執行的位置選擇排程選項：

| 選項 | 執行位置 | 最適合 |
| :- | :- | :- |
| [雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md) | 雲端，預設由 Anthropic 管理 | 應該在您的電腦關閉時執行的任務。除了排程之外，也可以由 API 呼叫或 GitHub 事件觸發。在 [claude.ai/code/routines](https://claude.ai/code/routines) 設定。 |
| [桌面排程任務](https://code.claude.com/docs/zh-TW/desktop-scheduled-tasks.md) | 您的機器，通過桌面應用 | 需要直接存取本地檔案、工具或未提交變更的任務。 |
| [GitHub Actions](https://code.claude.com/docs/zh-TW/github-actions.md) | 您的 CI 管道 | 與儲存庫事件（如開啟的 PR）相關的任務，或應與工作流程設定一起存在的 cron 排程。 |
| [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks) | 當前 CLI 會話 | 會話開啟時的快速輪詢。`--resume` 和 `--continue` 恢復未過期的固定間隔迴圈。 |

> [!TIP]
>
> 為排程任務編寫提示時，明確說明成功是什麼樣子以及如何處理結果。任務自主執行，所以它無法提出澄清問題。例如：「檢查標記為 `needs-review` 的開放 PR，對任何問題留下內聯評論，並在 `#eng-reviews` Slack 頻道中發佈摘要。」

***

### 詢問 Claude 其功能

Claude 可以回答有關其自身功能和限制的問題。它會在當前的 Claude Code 文件中查找答案，因此答案不受限於您正在執行的版本。

#### 範例問題

```text wrap theme={null}
can Claude Code create pull requests?
```

```text wrap theme={null}
how does Claude Code handle permissions?
```

```text wrap theme={null}
what skills are available?
```

```text wrap theme={null}
how do I use MCP with Claude Code?
```

```text wrap theme={null}
how do I configure Claude Code for Amazon Bedrock?
```

```text wrap theme={null}
what are the limitations of Claude Code?
```

> [!NOTE]
>
> Claude 根據文件提供對這些問題的答案。如需可執行的範例和實踐演示，請執行 `/powerup` 以取得具有動畫演示的互動式課程，或參閱上面的特定工作流程部分。

> [!TIP]
>
> 提示：
>
> * 提出具體問題以獲得詳細答案
> * Claude 可以解釋複雜的功能，如 MCP 整合、企業設定和進階工作流程

***

## 繼續之前的對話

當任務跨越多個會話時，從您停止的地方繼續，而不是重新解釋背景資訊。Claude Code 在本地儲存每個對話。

```bash theme={null}
claude --continue
```

這會繼續當前目錄中最近的會話；如果還沒有，它會列印 `No conversation found to continue` 並退出。使用 `claude --resume` 從清單中選擇，或從執行中的會話內使用 `/resume`。有關命名、分支和完整選擇器參考，請參閱[管理會話](https://code.claude.com/docs/zh-TW/sessions.md)。

## 使用 worktrees 執行平行會話

在一個終端中處理功能，同時 Claude 在另一個終端中修復錯誤，而不會編輯衝突。每個 [git worktree](https://git-scm.com/docs/git-worktree) 是其自己分支上的單獨簽出，從現有提交建立，因此儲存庫需要至少先有一個提交。

```bash theme={null}
claude --worktree feature-auth
```

在第二個終端中使用不同的名稱執行相同的命令以啟動隔離的平行會話。在沒有提交的儲存庫中，命令失敗並顯示 `Failed to resolve base branch "HEAD": git rev-parse failed`。有關清理、`.worktreeinclude` 和非 git VCS 支援，請參閱 [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md)。要從一個螢幕而不是單獨的終端監視平行會話，請參閱[背景代理](https://code.claude.com/docs/zh-TW/agent-view.md)。

## 編輯前規劃

對於您想在變更觸及磁碟前檢查的變更，切換到 plan mode。Claude 讀取檔案並提出計畫，但在您批准前不進行編輯。狀態列會在 plan mode 啟用時顯示 `⏸ plan mode on`。

```bash theme={null}
claude --permission-mode plan
```

您也可以在會話期間按 `Shift+Tab` 直到狀態列顯示 `⏸ plan mode on`。有關批准流程和在文字編輯器中編輯計畫，請參閱 [Plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)。

## 將研究委派給 subagents

探索大型程式碼庫會用檔案讀取填滿您的背景資訊。委派探索，以便只有發現結果返回。

```text wrap theme={null}
use a subagent to investigate how our auth system handles token refresh
```

subagent 在其自己的背景資訊視窗中讀取檔案並報告摘要。有關定義具有自己工具和提示的自訂代理，請參閱 [Subagents](https://code.claude.com/docs/zh-TW/sub-agents.md)。

## 將 Claude 管道輸入指令碼

以非互動方式執行 Claude，用於 CI、提交前 hooks 或批次處理。Stdin 和 stdout 像任何 Unix 工具一樣工作。

```bash theme={null}
git log --oneline -20 | claude -p "summarize these recent commits"
```

有關輸出格式、權限標誌和扇出模式，請參閱[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)。

## 後續步驟

> [card] [最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)
>
> 從 Claude Code 中獲得最大收益的模式

> [card] [管理會話](https://code.claude.com/docs/zh-TW/sessions.md)
>
> 繼續、命名和分支對話

> [card] [Worktrees](https://code.claude.com/docs/zh-TW/worktrees.md)
>
> 執行隔離的平行會話

> [card] [擴展 Claude Code](https://code.claude.com/docs/zh-TW/features-overview.md)
>
> 新增 skills、hooks、MCP、subagents 和外掛
