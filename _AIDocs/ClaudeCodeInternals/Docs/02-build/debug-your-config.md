<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/debug-your-config | lastmod: 2026-11-04 | section: Build with Claude Code / Troubleshooting -->
> 來源：https://code.claude.com/docs/zh-TW/debug-your-config（官方 zh-TW，lastmod 2026-11-04）｜分類：Build with Claude Code › Troubleshooting｜EN 摘要：Diagnose why CLAUDE.md, settings, hooks, MCP servers, or skills aren't taking effect. Use /context, /doctor, /hooks, and /mcp to see what actually loaded.

# 偵錯您的設定

> 診斷為什麼 CLAUDE.md、settings、hooks、MCP servers 或 skills 沒有生效。使用 /context、/doctor、/hooks 和 /mcp 查看實際載入的內容。

當 Claude 忽略您的指令或您設定的功能沒有出現時，通常是因為檔案沒有載入、從您預期以外的位置載入，或被另一個檔案覆蓋。本指南展示如何檢查 Claude Code 實際載入的內容，以便您縮小範圍。

如需安裝、驗證和連線問題的協助，請改為參閱 [Troubleshoot installation and login](https://code.claude.com/docs/zh-TW/troubleshoot-install.md)。

## 查看載入上下文的內容

`/context` 命令會顯示目前工作階段中佔用上下文視窗的所有內容，並依類別細分：系統提示詞、系統工具、MCP 工具、自訂 subagent（含各自的載入來源）、記憶檔案、skill 以及對話訊息。請先執行此命令，確認您的 `CLAUDE.md`、規則或 skill 描述是否確實存在。`/context` 中的 skill 區段也包含 [隨附 skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)，而這些是 `/skills` 不會列出的。

在 [全螢幕模式](https://code.claude.com/docs/zh-TW/fullscreen.md) 中，`/context` 會收合逐項細分內容，因此請執行 `/context all` 將其展開。

若要查看特定類別的詳細資訊，請接著使用對應的專用命令：

| 命令 | 顯示內容 |
| :- | :- |
| `/memory` | 使用者與專案範圍中的記憶檔案位置，並可在編輯器中開啟各檔案，另可存取自動記憶資料夾及自動記憶開關 |
| `/skills` | 來自專案、使用者及外掛來源的可用 skill |
| `/hooks` | 作用中的 hook 設定 |
| `/mcp` | 已連線的 MCP 伺服器及其狀態 |
| `/permissions` | 目前生效、經解析後的允許與拒絕規則 |
| `/doctor` | 設定檢查：安裝健康狀態、無效的設定檔、未使用的擴充功能、同一目錄中重複的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 名稱，以及已簽入版本控制、但 Claude 可從程式碼庫自行推導出的 `CLAUDE.md` 內容，並提供建議的修正方式 |
| `/debug [issue]` | 為工作階段啟用偵錯日誌，並提示 Claude 利用日誌輸出與設定路徑進行診斷 |
| `/status` | 作用中的設定來源，包括受管設定是否生效 |

如果某個記憶檔案未出現在 `/context` 的細分結果中，請對照 [CLAUDE.md 檔案的載入方式](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load) 檢查其位置。子目錄中的 `CLAUDE.md` 檔案是按需載入，而非在工作階段開始時載入，因此不會出現在該細分結果中。

如果 `/context` 確認檔案已載入，但 Claude 仍未遵循某項特定指令，問題很可能出在指令的撰寫方式，而非是否已載入。CLAUDE.md 很適合用於您會提供給新進團隊成員的各類指引，例如專案慣例、建置命令，以及檔案應放置的位置。

當指令模糊到可有多種解讀方式、兩個檔案給出互相衝突的指示，或檔案變得過長以致個別規則所受的關注降低時，遵循程度就會下降。[撰寫有效的指令](https://code.claude.com/docs/zh-TW/memory.md#write-effective-instructions) 說明了能維持高遵循程度的具體性、篇幅與結構模式。

> [!NOTE]
>
> CLAUDE.md 與權限解決的是不同的問題。CLAUDE.md 告訴 Claude 您的專案如何運作，讓它做出良好的決策。[權限](https://code.claude.com/docs/zh-TW/permissions.md) 與 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 則無論 Claude 做出何種決定都會強制執行限制。請將 CLAUDE.md 用於「我們這裡是這樣做的」這類情況。對於安全邊界以及任何絕不能發生的事情，也就是您需要的是保證而非指引時，請使用權限或 hook。

## 檢查已解析的設定

設定在受管、使用者、專案和本機範圍之間合併。受管設定在存在時始終優先。在其餘的設定中，較近的範圍會按本機、專案、使用者的順序覆蓋較廣的範圍。某些設定也可以由命令列旗標或 [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md) 設定，這些變數充當另一個覆蓋層。當設定似乎不適用時，您設定的值通常被另一個範圍或環境變數覆蓋。

若要找出無效的設定檔案，請從您的終端機執行 `claude doctor`。它會列印唯讀的安裝和設定診斷，而不會啟動工作階段。如需完整檢查，也會提議修正並在套用前詢問，請在工作階段內執行 [`/doctor`](https://code.claude.com/docs/zh-TW/commands#all-commands)。

執行 `/status` 以查看哪些設定來源處於作用中，包括是否啟用了受管設定。若要瞭解 Claude Code 對於給定鍵使用哪個範圍，請參閱 [設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。

## 檢查 MCP servers

執行 `/mcp` 以查看每個已設定的 server、其連線狀態，以及您是否已為目前專案核准它。server 可以定義正確但仍然不提供 tools，原因有幾個常見的：

* `.mcp.json` 中的專案範圍 servers 需要一次性核准。如果提示被關閉，server 將保持停用狀態，直到您從 `/mcp` 核准它。
* 啟動失敗的 server 在 `/mcp` 中顯示為失敗。`command` 或 `args` 中的相對檔案路徑是常見原因，因為它們相對於您啟動 Claude Code 的目錄而不是 `.mcp.json` 的位置進行解析。
* 顯示為已連線但列出零個 tools 的 server 已成功啟動但未返回 tool 清單。從 `/mcp` 選擇 **Reconnect**。如果計數保持為零，執行 `claude --debug=mcp` 並在 `~/.claude/debug/<session-id>.txt` 的偵錯日誌中讀取 server 的 stderr。

如需設定位置和範圍規則，請參閱 [MCP](https://code.claude.com/docs/zh-TW/mcp.md)。

## 檢查 hooks

執行 `/hooks` 以列出為目前工作階段註冊的每個 hook，按事件分組。如果您定義的 hook 沒有出現，表示 Claude Code 未載入它。請檢查以下原因：

* hook 定義在獨立檔案中。hook 應位於[設定檔](https://code.claude.com/docs/zh-TW/settings.md#settings-files)中的 `"hooks"` 鍵下。
* `matcher` 值是陣列而不是單一字串。當您啟動互動式工作階段時以及在 `claude doctor` 中，Claude Code 會將該項目列為無效設定。如果該陣列位於 `PreToolUse` 或 `PermissionRequest` 下，該檔案的其他 hook 也都不會載入。
* hook 位於 skill 的 frontmatter 中，而您和 Claude 在此工作階段中都尚未叫用該 skill。請叫用它或要求 Claude 叫用，然後再次執行 `/hooks`。如果 hook 仍未出現，請檢查其他原因，例如[未能解析的 frontmatter](https://code.claude.com/docs/zh-TW/skills.md#skill-not-triggering)或其中一項 [skill hook 的限制](https://code.claude.com/docs/zh-TW/hooks.md#limits-on-skill-hooks)。

如果 hook 出現但不觸發，通常是 matcher 的問題。檢查它是否有這些錯誤：

* `matcher` 欄位是一個使用 `|` 匹配多個 tool 名稱的單一字串，例如 `"Edit|Write"`。`,` 分隔符是等效的，因此 `"Edit,Write"` 匹配相同的 tools。在 v2.1.191 之前，逗號會進入正規表達式評估，matcher 永遠不會匹配，因此如果您不在 v2.1.191 版本上，請使用 `|`。
* 拼寫錯誤的 tool 名稱會產生一個不匹配任何內容的 matcher，因此 hook 會無聲地失敗。

對 `settings.json` 的編輯在短暫的檔案穩定延遲後在執行中的工作階段中生效，即使您在工作階段開始後才建立檔案或專案的 `.claude/` 資料夾。您不需要重新啟動。在 v2.1.257 之前，Claude Code 沒有偵測到在工作階段開始後建立的 `.claude/` 資料夾中的編輯。

如果在保存後幾秒鐘 `/hooks` 仍顯示舊定義，請再次執行 `/hooks` 以重新整理檢視。

如果 `/hooks` 顯示 hook 但它仍然不觸發，下一步是即時監視 hook 評估。使用 `claude --debug` 啟動工作階段並觸發 tool 呼叫。偵錯日誌記錄每個事件、檢查了哪些 matchers 以及 hook 的結束代碼和輸出。如需日誌格式，請參閱 [Debug hooks](https://code.claude.com/docs/zh-TW/hooks.md#debug-hooks)，如需常見失敗模式，請參閱 [hooks 疑難排解](https://code.claude.com/docs/zh-TW/hooks-guide.md#limitations-and-troubleshooting)。

## 針對乾淨的設定進行測試

使用 [`claude --safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 開始，它會啟動一個停用您自訂項目的工作階段，包括：

* `CLAUDE.md`
* Skills、外掛和 hook
* MCP 伺服器
* 自訂命令和 agent
* 自訂輸出風格
* 自訂快捷鍵

身分驗證、模型選擇、內建工具和權限正常運作。如果問題在安全模式中消失，表示您已將原因縮小到您關閉的其中一個項目。若要找出是哪一個，請使用該項目對應的檢查，例如[查看載入到上下文中的內容](#see-what-loaded-into-context)、[檢查 MCP 伺服器](#check-mcp-servers)或[檢查 hook](#check-hooks)。

安全模式仍然會套用來自您組織的受管 hook 和設定原則。受管外掛、skills、`CLAUDE.md` 和 MCP 伺服器會被關閉。

如果問題在安全模式中持續存在，或您的設定本身令人懷疑，請啟動一個完全不含您自己設定的工作階段，並檢查問題是否仍然出現。

**1. 建立空目錄並切換到該目錄**

在沒有執行任何 Claude Code 工作階段的情況下，於您的 shell 中建立目錄並移至其中：

> [tab] Bash 或 Zsh
>
> ```bash theme={null}
> mkdir -p ~/claude-clean/empty && cd ~/claude-clean/empty
> ```

> [tab] PowerShell
>
> ```powershell theme={null}
> New-Item -ItemType Directory -Force "$HOME/claude-clean/empty" | Out-Null
> Set-Location "$HOME/claude-clean/empty"
> ```

**2. 使用乾淨的設定目錄啟動 Claude Code**

在同一個 shell 中，將 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars) 設定為一個新的目錄來取代 `~/.claude`，並傳入 [`--setting-sources user`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 以關閉專案設定，例如 `.claude/settings.json`、`CLAUDE.md` 和 `.mcp.json`：

> [tab] Bash 或 Zsh
>
> 此變數僅適用於這一次啟動。
>
> ```bash theme={null}
> CLAUDE_CONFIG_DIR=~/claude-clean/config claude --setting-sources user
> ```

> [tab] PowerShell
>
> 此變數會在此 PowerShell 工作階段的剩餘時間內保持設定，因此在同一視窗中稍後啟動的 `claude` 會繼續使用乾淨的目錄。若要回到您平常的目錄，請在下次啟動前執行 `Remove-Item Env:CLAUDE_CONFIG_DIR`。
>
> ```powershell theme={null}
> $env:CLAUDE_CONFIG_DIR = "$HOME/claude-clean/config"
> claude --setting-sources user
> ```

首次啟動時，您會再次經歷首次執行設定畫面，這表示乾淨的設定目錄已生效。受管設定仍然適用，而且如果您使用 claude.ai 帳戶登入，[連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)仍會載入。

**3. 重現問題**

在乾淨的工作階段中重複觸發問題的操作：

* **問題消失**：原因在於您的使用者或專案設定。將 `~/.claude.json` 和 `~/.claude` 中的檔案一次一個地複製到 `~/claude-clean/config`。如果沒有任何一個讓問題重新出現，請在同一個 shell 中前往您的專案目錄，並在不使用 `--setting-sources user` 的情況下啟動 Claude Code。在 Bash 或 Zsh 中，執行 `CLAUDE_CONFIG_DIR=~/claude-clean/config claude`。在 PowerShell 中，該變數仍然已設定，因此執行 `claude` 即可。
* **問題持續存在**：原因在於您的使用者和專案設定之外。在工作階段中執行 `/status` 以檢查是否有受管設定，檢查您 shell 中的[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)，然後參閱[疑難排解](https://code.claude.com/docs/zh-TW/troubleshooting.md)。

## 檢查常見原因

大多數設定問題都可以追溯到一小組位置和語法規則。在假設有錯誤之前，請先檢查這些項目：

| 症狀 | 原因 | 修正 |
| :- | :- | :- |
| Hook 永遠不會觸發 | `matcher` 是 JSON 陣列而不是字串 | 使用單一字串搭配 `\|` 來比對多個工具，例如 `"Edit\|Write"`。請參閱 [matcher 模式](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns)。 |
| Hook 永遠不會觸發 | `matcher` 在 v2.1.191 之前的版本中使用 `,` 作為分隔符 | Claude Code v2.1.191 或更新版本將 `,` 視為列表分隔符，如 `\|`。較早的版本會將逗號評估為字面字元，因此 `"Edit,Write"` 不會比對任何內容。改用 `\|`，或升級 Claude Code。 |
| Hook 永遠不會觸發 | `matcher` 值為小寫，例如 `"bash"` | 比對區分大小寫。工具名稱採用大寫：`Bash`、`Edit`、`Write`、`Read`。 |
| Hook 永遠不會觸發 | Hook 定義在獨立檔案中，而不是 `settings.json` | 專案或使用者設定沒有獨立的 hooks 檔案。在 `settings.json` 中的 `"hooks"` 鍵下定義 hooks。只有 [plugins](https://code.claude.com/docs/zh-TW/plugins/components.md#hooks) 會載入獨立的 `hooks/hooks.json`。請參閱 [hook 設定](https://code.claude.com/docs/zh-TW/hooks.md)。 |
| 全域設定的權限或 hooks 被忽略 | 設定已新增至 `~/.claude.json` | `~/.claude.json` 保存應用程式狀態和 UI 切換。`permissions`、`hooks` 和 `env` 應該在 `~/.claude/settings.json` 中。這是兩個不同的檔案。 |
| `settings.json` 值似乎被忽略 | 相同的鍵在 `settings.local.json` 中設定 | `settings.local.json` 會覆寫 `settings.json`，兩者都會覆寫 `~/.claude/settings.json`。請參閱 [settings 優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。 |
| Skill 未出現在 `/skills` 中 | Skill 檔案位於 `.claude/skills/name.md` 而不是在資料夾中 | 使用包含 `SKILL.md` 的資料夾：`.claude/skills/name/SKILL.md`。 |
| Skill 出現在 `/skills` 中，但 Claude 從未叫用它 | Skill 在其 frontmatter 中有 `disable-model-invocation: true`，或其描述與您提出請求的方式不符 | 檢查 `/skills` 中的徽章：「user-only」標籤表示 Claude 不會自動觸發它。請參閱 [skill 叫用](https://code.claude.com/docs/zh-TW/skills.md)。 |
| 子目錄 `CLAUDE.md` 指示似乎被忽略 | 子目錄檔案按需載入，而不是在工作階段開始時載入 | 若要載入子目錄的 `CLAUDE.md`，請要求 Claude 讀取該子目錄中的另一個檔案。請參閱 [子目錄檔案何時載入](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)。 |
| Subagent 忽略 `CLAUDE.md` 指示 | 內建的 Explore 和 Plan agent 會在啟動時跳過 `CLAUDE.md`。自訂 subagent 的載入方式與主對話相同，除非其定義設定了 [`omitClaudeMd`](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields) | 對於 Explore 或 Plan，在您的委派提示詞中重新陳述指示。對於設定 `omitClaudeMd` 的 subagent，移除該欄位。對於任何其他自訂 subagent，將關鍵指示放在 agent 檔案本文中，該本文會成為 agent 的系統提示詞。請參閱 [啟動時載入的內容](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)。 |
| 清理邏輯在工作階段結束時永遠不會執行 | 未設定 `SessionEnd` hook | 在 `settings.json` 中新增 `SessionEnd` hook。請參閱 [hook 事件列表](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)。 |
| `.mcp.json` 中的 MCP 伺服器永遠不會載入 | 檔案位於 `.claude/` 下，或其伺服器位於頂層 `servers` 鍵下（如 VS Code 的 `mcp.json`），而不是 `mcpServers` | 專案 MCP 設定位於存放庫根目錄的 `.mcp.json`，而不是在 `.claude/` 內，伺服器位於 `mcpServers` 鍵下。請參閱 [MCP 設定](https://code.claude.com/docs/zh-TW/mcp.md)。 |
| 在 `settings.json` 中的 `mcpServers` 下新增的 MCP 伺服器永遠不會出現 | `settings.json` 不讀取 `mcpServers` 鍵 | 在存放庫根目錄的 `.mcp.json` 中定義專案伺服器，或執行 `claude mcp add --scope user` 以取得使用者範圍的伺服器。請參閱 [MCP 設定](https://code.claude.com/docs/zh-TW/mcp.md)。 |
| 新增的專案 MCP 伺服器但未出現 | 一次性核准提示被關閉 | 專案範圍的伺服器需要核准。執行 `/mcp` 以查看狀態並核准。 |
| MCP 伺服器從某些目錄啟動失敗 | `command` 或 `args` 使用相對檔案路徑 | 對本機指令碼使用絕對路徑。您 `PATH` 上的可執行檔（如 `npx` 或 `uvx`）可以按原樣使用。 |
| MCP 伺服器啟動時沒有預期的環境變數 | 伺服器的設定項目未設定它們，且它們不在 Claude Code 傳遞給 stdio 伺服器的環境中：其自身環境，減去 [它從子程序中移除的變數](https://code.claude.com/docs/zh-TW/monitoring-usage.md#administrator-configuration) | 在伺服器的 `.mcp.json` 項目內設定每個伺服器的 `env`，這不取決於啟動環境或工作區信任。 |
| `Bash(rm *)` 拒絕規則不會阻止 `/bin/rm` 或 `find -delete` | Bash 規則比對字面命令字串，而不是基礎可執行檔；請參閱 [Bash 規則不比對的內容](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits) | 使用 [PreToolUse hook](https://code.claude.com/docs/zh-TW/hooks-guide.md) 或 [sandbox](https://code.claude.com/docs/zh-TW/sandboxing.md) 以獲得硬性保證。 |

## 相關資源

如需每個設定表面的完整參考，請參閱專用頁面：

* **[`.claude` 目錄參考](https://code.claude.com/docs/zh-TW/claude-directory)**：每個設定檔案位置及其讀取方式
* **[Settings](https://code.claude.com/docs/zh-TW/settings.md)**：使用哪個檔案以及 Claude Code 使用哪個值；[settings 參考](https://code.claude.com/docs/zh-TW/settings-reference.md)有完整的鍵清單
* **[Hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)**：事件名稱、承載和 `--debug` 輸出格式
* **[MCP](https://code.claude.com/docs/zh-TW/mcp.md)**：server 設定、核准和 `/mcp` 輸出
* **[Troubleshoot installation and login](https://code.claude.com/docs/zh-TW/troubleshoot-install.md)**：`command not found`、PATH 和身份驗證問題
* **[Troubleshooting](https://code.claude.com/docs/zh-TW/troubleshooting.md)**：效能、掛起和搜尋問題
