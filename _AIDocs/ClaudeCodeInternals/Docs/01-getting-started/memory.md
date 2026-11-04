<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/memory | lastmod: 2026-11-04 | section: Getting started / Use Claude Code -->
> 來源：https://code.claude.com/docs/zh-TW/memory（官方 zh-TW，lastmod 2026-11-04）｜分類：Getting started › Use Claude Code｜EN 摘要：Give Claude persistent instructions with CLAUDE.md or AGENTS.md files, and let Claude accumulate learnings automatically with auto memory.

# Claude 如何記住您的專案

> 使用 CLAUDE.md 或 AGENTS.md 檔案為 Claude 提供持久指示，並讓 Claude 透過自動記憶自動累積學習。

每個 Claude Code 工作階段都以全新的內容視窗開始。兩個機制可以跨工作階段傳遞知識：

* **CLAUDE.md 檔案**：您撰寫的指示，為 Claude 提供持久上下文。Claude 也可以讀取儲存庫的 [`AGENTS.md` 檔案](#agents-md)來取代 CLAUDE.md
* **自動記憶**：Claude 根據您的更正和偏好自己撰寫的筆記

本頁涵蓋如何：

* [撰寫和組織 CLAUDE.md 檔案](#claude-md-files)
* [使用現有的 AGENTS.md](#agents-md) 作為您的專案指示
* [使用 `.claude/rules/` 將規則範圍限定於特定檔案類型](#organize-rules-with-claude/rules/)
* [設定自動記憶](#auto-memory)，讓 Claude 自動記筆記
* [疑難排解](#troubleshoot-memory-issues)當指示未被遵循時

## CLAUDE.md 與自動記憶

Claude Code 有兩個互補的記憶系統。兩者都在每次對話開始時載入。Claude 將它們視為上下文，而不是強制配置。若要阻止某個動作（無論 Claude 決定什麼），請改用 [PreToolUse hook](https://code.claude.com/docs/zh-TW/hooks-guide.md)。您的指令越具體和簡潔，Claude 遵循它們的一致性就越高。

| | CLAUDE.md 檔案 | 自動記憶 |
| :- | :- | :- |
| **誰編寫** | 您 | Claude |
| **包含內容** | 指令和規則 | 學習和模式 |
| **範圍** | 專案、使用者或組織 | 每個儲存庫，跨 worktrees 共享 |
| **載入到** | 每個工作階段 | 每個工作階段（前 200 行或 25KB） |
| **用於** | 編碼標準、工作流程、專案架構 | 您的偏好、您給予 Claude 的更正、Claude 無法從程式碼衍生的專案上下文 |

當您想引導 Claude 的行為時，使用 CLAUDE.md 檔案。自動記憶讓 Claude 從您的更正中學習，無需手動操作。

Subagents 也可以維護自己的自動記憶。有關詳細資訊，請參閱 [subagent 配置](https://code.claude.com/docs/zh-TW/sub-agents.md#enable-persistent-memory)。

## CLAUDE.md 檔案

CLAUDE.md 檔案是 markdown 檔案，為 Claude 提供專案、個人工作流程或整個組織的持久指令。您以純文字編寫這些檔案；Claude 在每個工作階段開始時讀取它們。如果您的儲存庫改用 `AGENTS.md`，請參閱 [AGENTS.md](#agents-md)。

### 何時新增至 CLAUDE.md

將 CLAUDE.md 視為您寫下原本需要重複解釋的內容的地方。在以下情況下新增至它：

* Claude 第二次犯同樣的錯誤
* 程式碼審查發現 Claude 應該知道的關於此程式碼庫的事項
* 您在聊天中輸入的相同更正或澄清是您上一個工作階段輸入的
* 新的團隊成員需要相同的背景資訊才能提高生產力

將其保持為 Claude 應該在每個工作階段中保留的事實：建置命令、慣例、專案配置、「始終執行 X」規則。如果一個條目是多步驟程序或僅對程式碼庫的一部分重要，請改為將其移至 [skill](https://code.claude.com/docs/zh-TW/skills.md) 或 [path-scoped rule](#organize-rules-with-claude/rules/)。[擴充功能概述](https://code.claude.com/docs/zh-TW/features-overview.md#build-your-setup-over-time) 涵蓋何時使用每個機制。

### 選擇 CLAUDE.md 檔案的放置位置

CLAUDE.md 檔案可以位於多個位置，每個位置具有不同的範圍。下表按載入順序列出它們，從最廣泛的範圍到最具體的範圍，因此專案指令在使用者指令之後出現在背景中。

| 範圍 | 位置 | 目的 | 使用案例範例 | 共享對象 |
| - | - | - | - | - |
| **受管理的原則** | • macOS：`/Library/Application Support/ClaudeCode/CLAUDE.md` • Linux 和 WSL：`/etc/claude-code/CLAUDE.md` • Windows：`C:\Program Files\ClaudeCode\CLAUDE.md` | 由 IT/DevOps 管理的組織範圍指令 | 公司編碼標準、安全原則、合規要求 | 組織中的所有使用者 |
| **使用者指令** | `~/.claude/CLAUDE.md` | 所有專案的個人偏好設定 | 程式碼樣式偏好設定、個人工具快捷方式 | 僅您（所有專案） |
| **專案指令** | `./CLAUDE.md` 或 `./.claude/CLAUDE.md`。請參閱 [AGENTS.md](#agents-md) 以了解何時 `./AGENTS.md` 載入而不是或與它們一起載入 | 專案的團隊共享指令 | 專案架構、編碼標準、常見工作流程 | 透過原始碼控制的團隊成員 |
| **本機指令** | `./CLAUDE.local.md` | 個人專案特定偏好設定；新增至 `.gitignore` | 您的沙箱 URL、偏好的測試資料 | 僅您（目前專案） |

工作目錄上方目錄階層中的 CLAUDE.md 和 CLAUDE.local.md 檔案在啟動時載入。子目錄中的檔案按需載入。請參閱 [CLAUDE.md 檔案如何載入](#how-claude-md-files-load) 以了解它們何時載入以及完整的解析順序。

對於大型專案，您可以使用 [project rules](#organize-rules-with-claude/rules/) 將指令分解為主題特定的檔案。規則可讓您將指令範圍限制為特定檔案類型或子目錄。

### 設定專案 CLAUDE.md

專案 CLAUDE.md 可以儲存在 `./CLAUDE.md` 或 `./.claude/CLAUDE.md` 中。建立此檔案並新增適用於在專案上工作的任何人的指令：建置和測試命令、編碼標準、架構決策、命名慣例和常見工作流程。這些指令透過版本控制與您的團隊共享，因此請專注於專案級標準而不是個人偏好設定。

若要確認檔案已載入，請在工作階段中執行 [`/context all`](https://code.claude.com/docs/zh-TW/commands#all-commands) 並檢查 **Memory files** 下的清單。在[全螢幕模式](https://code.claude.com/docs/zh-TW/fullscreen.md)中，單獨使用 `/context` 會收合該清單。

> [!TIP]
>
> 執行 `/init` 以自動產生起始 CLAUDE.md。Claude 分析您的程式碼庫並建立包含建置命令、測試指令和它發現的專案慣例的檔案。如果 CLAUDE.md 已存在，`/init` 會建議改進而不是覆寫它。從那裡使用 Claude 不會自行發現的指令進行精煉。
>
> 若要改用互動式多階段流程，請在執行 `/init` 之前將 `CLAUDE_CODE_NEW_INIT` 環境變數設定為 `1`。請在您的 shell 中或在設定檔的 `env` 區塊中設定它，如 [設定環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#set-environment-variables) 中所示。設定後，`/init` 會詢問要設定哪些 artifact：CLAUDE.md 檔案、skills 和 hooks。然後它使用 subagent 探索您的程式碼庫，透過後續問題填補空白，並在寫入任何檔案之前呈現可審查的提案。該變數僅改變 `/init` 的執行方式，因此您可以保持它設定。

### 撰寫有效的指令

Claude 將 CLAUDE.md 檔案視為背景資訊而非強制執行的設定，因此您撰寫指令的方式會影響 Claude 遵循它們的可靠性。撰寫具體到足以驗證的指令：

* 「使用 2 空格縮排」而不是「正確格式化程式碼」
* 「在提交前執行 `npm test`」而不是「測試您的變更」
* 「API 處理程式位於 `src/api/handlers/`」而不是「保持檔案組織」

保持您的檔案簡短、組織有序且一致：

* **大小**：每個 CLAUDE.md 檔案的目標為 200 行以下。較長的檔案消耗更多背景並降低遵守度。將僅對程式碼庫的一部分重要的指令移至 [path-scoped rules](#path-specific-rules)，這些規則僅在 Claude 使用匹配檔案時載入。[匯入](#import-additional-files) 可幫助您組織長檔案，但不會減少其背景成本，因為匯入的檔案會與匯入它們的 CLAUDE.md 一起載入。
* **結構**：在 markdown 標題和項目符號下分組相關指令。組織的部分比密集的段落更容易讓 Claude 遵循。
* **一致性**：如果兩個指令相互矛盾，Claude 可能會任意選擇一個。定期審查您的 CLAUDE.md 檔案、子目錄中的巢狀 CLAUDE.md 檔案和 [`.claude/rules/`](#organize-rules-with-claude/rules/) 以移除過時或衝突的指令。若要讓 Claude 為您找到它們，請 [執行提示詞審計](#audit-your-instruction-files)。

#### 審計您的指令檔案

若要讓 Claude 檢查您的指令檔案是否有過時或衝突的內容，請在工作階段中執行 `/doctor prompt-audit`。Claude 尋找問題，例如為舊版模型編寫的指令、對不存在的檔案或命令的參考，以及相互矛盾的檔案。您會獲得發現報告和建議的編輯，在您要求 Claude 應用它們之前，您的檔案中不會有任何變更。

根據預設，審計涵蓋您的 CLAUDE.md、CLAUDE.local.md 和 AGENTS.md 檔案，加上 `.claude/` 和 `~/.claude/` 下的規則、skills、命令、subagents 和輸出風格。若要改為審計一個檔案或目錄，請傳遞其路徑，例如 `/doctor prompt-audit .claude/skills/deploy`。

審計透過捆綁的 `/claude-api` skill 執行。當該 skill 在 [`skillOverrides`](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings) 中關閉或使用 [`disableBundledSkills`](https://code.claude.com/docs/zh-TW/settings-reference#disablebundledskills) 時，它不可用。`/doctor prompt-audit` 需要 Claude Code v2.1.283 或更新版本。

### 匯入其他檔案

CLAUDE.md 檔案可以使用 `@path/to/import` 語法匯入其他檔案。匯入的檔案會展開並載入到背景中，與參考它們的 CLAUDE.md 一起。

允許相對和絕對路徑。相對路徑相對於包含匯入的檔案解析，而不是工作目錄。匯入的檔案可以遞迴匯入其他檔案，最大深度為四個躍點。

若要匯入路徑包含空格的檔案，請在每個空格前放置反斜線。沒有反斜線，路徑在第一個空格處結束，即使匯入在其自己的行上。用引號包裝的路徑根本不會被匯入，無論是否有反斜線。此匯入從名為 `Design Docs` 的資料夾載入檔案：

```text theme={null}
- API conventions @Design\ Docs/api-conventions.md
```

匯入解析會跳過 Markdown 程式碼跨度和圍欄程式碼區塊。若要在您的 CLAUDE.md 中提及路徑而不匯入它，請將其包裝在反引號中：寫入 `` `@README` `` 會保持文字為字面，而反引號外的 `@README` 會匯入檔案。

若要引入 README、package.json 和工作流程指南，請在 CLAUDE.md 中的任何位置使用 `@` 語法參考它們：

```text theme={null}
See @README for project overview and @package.json for available npm commands for this project.

# Additional Instructions
- git workflow @docs/git-instructions.md
```

對於不應簽入版本控制的私人每個專案偏好設定，請在專案根目錄建立 `CLAUDE.local.md`。它與 `CLAUDE.md` 一起載入並以相同方式處理。將 `CLAUDE.local.md` 新增至您的 `.gitignore`，以便不提交它。設定 `CLAUDE_CODE_NEW_INIT=1` 後，執行 `/init` 並選擇個人選項會為您執行此操作。

如果您在同一儲存庫的多個 git worktrees 中工作，gitignored `CLAUDE.local.md` 僅存在於您建立它的 worktree 中。若要在 worktrees 中共享個人指令，請改為從您的家目錄匯入檔案：

```text theme={null}
# Individual Preferences
- @~/.claude/my-project-instructions.md
```

> [!WARNING]
>
> 專案級記憶檔案中的匯入是外部的，當其路徑解析到工作目錄外時，例如上面的家目錄匯入。Claude Code 首次在專案中遇到外部匯入時，會顯示核准對話框，列出檔案。如果您拒絕，匯入將保持停用狀態，對話框不會再出現。
>
> Claude Code 顯示對話框以保護您免受其他人提交到共享專案的檔案。使用者範圍記憶檔案（例如 `~/.claude/CLAUDE.md` 和 `~/.claude/rules/`）是您自己編寫的檔案。除了在您的桌面上的 [Cowork](https://claude.com/product/cowork) 工作階段中，Claude Code 會載入它們的匯入而不顯示對話框，並像信任您的其餘個人設定一樣信任它們。
>
> 在您的桌面上的 Cowork 工作階段中，Claude Code 會跳過使用者範圍檔案中解析到工作階段工作目錄外路徑的任何匯入，並載入檔案的其餘部分。在這些工作階段中，它也會跳過本身是符號連結或硬連結的 `~/.claude/CLAUDE.md`，以及指向工作目錄外的符號連結 `~/.claude/rules/` 目錄或規則檔案。

### CLAUDE.md 檔案如何載入

Claude Code 從您目前的工作目錄和其上方的每個目錄載入 `CLAUDE.md` 和 `CLAUDE.local.md`。在 `foo/bar/` 中執行 Claude Code，它會從 `foo/bar/CLAUDE.md`、`foo/CLAUDE.md` 和任何 `CLAUDE.local.md` 檔案載入指令。

所有發現的檔案都會串聯到背景中，而不是相互覆寫。在目錄樹中，內容從檔案系統根目錄向下排序到您的工作目錄。對於 `foo/bar/` 範例，`foo/CLAUDE.md` 在背景中出現在 `foo/bar/CLAUDE.md` 之前，因此更接近您啟動 Claude 的位置的指令最後讀取。在每個目錄中，`CLAUDE.local.md` 附加在 `CLAUDE.md` 之後，因此您的個人筆記是 Claude 在該級別讀取的最後一件事。

Claude 也會發現您目前工作目錄下子目錄中的 `CLAUDE.md` 和 `CLAUDE.local.md` 檔案。它們不是在啟動時載入，而是在 Claude 讀取、寫入或編輯該子目錄中的另一個檔案時，由 Claude Code 逐一載入。讀取包括使用 [算作讀取](https://code.claude.com/docs/zh-TW/tools-reference.md#edit-tool-behavior) 的 Bash 命令檢視檔案，例如對單一檔案執行 `cat` 或 `head`。關於 `.claude/worktrees/` 下 worktree 中的檔案，請參閱 [使用 worktree 隔離 subagent](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees)。

如果您在大型 monorepo 中工作，其中其他團隊的 CLAUDE.md 檔案被拾取，請使用 [`claudeMdExcludes`](#exclude-specific-claude-md-files) 跳過它們。有關根目錄和每個目錄 CLAUDE.md 檔案和規則的完整配置，請參閱 [Monorepos 和大型儲存庫](https://code.claude.com/docs/zh-TW/large-codebases.md)。

CLAUDE.md 檔案中的區塊級 HTML 註解（`<!-- maintainer notes -->`）在內容注入到 Claude 的背景之前被移除。使用它們為人類維護者留下筆記，而不在它們上花費背景 token。程式碼區塊內的註解會保留。當您直接使用 Read 工具開啟 CLAUDE.md 檔案時，註解保持可見。

#### 從其他目錄載入

`--add-dir` 旗標讓 Claude 可以存取主工作目錄外的其他目錄。根據預設，這些目錄中的 CLAUDE.md 檔案不會載入。

若要也從其他目錄載入記憶檔案，請設定 `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` 環境變數：

```bash theme={null}
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude --add-dir ../shared-config
```

內聯形式在 Bash 或 Zsh 中為該次啟動設定變數。若要在每個工作階段中保持它開啟，請將它新增至 `~/.claude/settings.json` 中的 `env` 區塊，如 [設定環境變數](https://code.claude.com/docs/zh-TW/env-vars.md#set-environment-variables) 中所示。

這會從其他目錄載入 `CLAUDE.md`、`.claude/CLAUDE.md`、`.claude/rules/*.md` 和 `CLAUDE.local.md`。如果您從 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference) 排除 `local`，則會跳過 `CLAUDE.local.md`。

### 使用 `.claude/rules/` 組織規則

對於較大的專案，您可以使用 `.claude/rules/` 目錄將指令組織成多個檔案。這使指令保持模組化並更容易讓團隊維護。規則也可以 [scoped to specific file paths](#path-specific-rules)，因此它們僅在 Claude 使用匹配檔案時載入到背景中，減少雜訊並節省背景空間。

> [!NOTE]
>
> 規則在每個工作階段或開啟匹配檔案時載入到背景中。對於不需要始終在背景中的任務特定指令，請改用 [skills](https://code.claude.com/docs/zh-TW/skills.md)，它們僅在您叫用它們或 Claude 確定它們與您的提示詞相關時載入。

#### 設定規則

在您的專案的 `.claude/rules/` 目錄中放置 markdown 檔案。每個檔案應涵蓋一個主題，具有描述性檔案名稱，例如 `testing.md` 或 `api-design.md`。所有 `.md` 檔案都會遞迴發現，因此您可以將規則組織到子目錄中，例如 `frontend/` 或 `backend/`：

```text theme={null}
your-project/
├── .claude/
│   ├── CLAUDE.md           # Main project instructions
│   └── rules/
│       ├── code-style.md   # Code style guidelines
│       ├── testing.md      # Testing conventions
│       └── security.md     # Security requirements
```

沒有 [`paths` frontmatter](#path-specific-rules) 的規則在啟動時載入，優先順序與 `.claude/CLAUDE.md` 相同。

如果您從 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference) 排除 `project`，則會跳過專案規則。在 v2.1.211 之前，按需載入的規則（包括路徑範圍規則和巢狀 `.claude/rules/` 目錄中的規則）即使排除了 `project` 也會載入。

#### 路徑特定規則

規則可以使用 YAML frontmatter 與 `paths` 欄位範圍限制為特定檔案。這些條件規則僅在 Claude 使用與指定模式匹配的檔案時適用。

```markdown theme={null}
---
paths:
  - "src/api/**/*.ts"
---

# API Development Rules

- All API endpoints must include input validation
- Use the standard error response format
- Include OpenAPI documentation comments
```

當 Claude 對匹配的檔案使用 Read、Write 或 Edit 工具時，路徑範圍規則就會載入。當 Claude 使用 [算作讀取](https://code.claude.com/docs/zh-TW/tools-reference.md#edit-tool-behavior) 的 Bash 命令檢視匹配的檔案時（例如對單一檔案執行 `cat` 或 `head`），該規則也會載入。當 Claude 透過到專案目錄的符號連結路徑到達檔案時，匹配也有效，例如在符號連結簽出中。

每個模式都相對於規則的基礎目錄：

* **專案規則**：包含該規則的 `.claude` 資料夾的目錄
* **[使用者級規則](#user-level-rules)**：工作階段的[主要工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)

若要讓路徑範圍規則針對同層級 git worktree 中的檔案載入，請在該 worktree 中啟動 Claude Code，或[使用 `/cd` 將工作階段移至該處](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory)。

在 `paths` 欄位中使用 glob 模式以按副檔名、目錄或任何組合匹配檔案：

| 模式 | 匹配 |
| - | - |
| `**/*.ts` | 基礎目錄下任何位置的 `.ts` 檔案 |
| `src/**/*` | 基礎目錄的 `src/` 下的所有檔案 |
| `*.md` | 基礎目錄下任何位置的 `.md` 檔案 |
| `/*.md` | 直接位於基礎目錄中的 `.md` 檔案，不含子資料夾中的檔案 |
| `src/components/*.tsx` | 直接位於基礎目錄的 `src/components/` 中的 `.tsx` 檔案，不含子資料夾中的檔案 |

您可以指定多個模式並使用大括號展開在一個模式中匹配多個副檔名：

```markdown theme={null}
---
paths:
  - "src/**/*.{ts,tsx}"
  - "lib/**/*.ts"
  - "tests/**/*.test.ts"
---
```

每個大括號群組會乘以展開模式的數量：`src/*.{ts,tsx}` 展開為兩個模式，`{a,b}/{c,d}/*.{ts,tsx}` 展開為八個。若要保持展開有界，規則的整個 `paths` 清單共享一個 1,000 個展開模式和 4 MiB 的預算，沒有大括號的模式不計入其中。

Claude Code 使用任何會超過預算的未展開模式，其字面大括號不匹配任何檔案。

Glob 語法將 `[` 視為括號表達式的開始，例如 `[abc]`。具有無法讀取為括號表達式的 `[` 的模式（例如 `photos [2024/**`）無效：它不匹配任何檔案，規則的其他模式保持工作。若要匹配檔案名稱中的字面 `[`，請將其逸出為 `photos \[2024/**`。

#### 規則 frontmatter 參考

使用 YAML [frontmatter](https://code.claude.com/docs/zh-TW/glossary.md#frontmatter) 在檔案頂部的 `---` 標記之間設定規則。`paths` 是 Claude Code 從規則讀取的唯一欄位；任何其他欄位都會被忽略而不出現錯誤。Claude Code 在將規則載入到背景之前移除 frontmatter。

| 欄位 | 必需 | 描述 |
| :- | :- | :- |
| `paths` | 否 | [將規則範圍限制為匹配檔案](#path-specific-rules) 的 Glob 模式。接受 YAML 清單或逗號分隔的字串 |

如果標記之間的 YAML 無法解析，Claude Code 會忽略 frontmatter 並載入規則，就像它沒有 `paths` 一樣。執行 `claude --debug` 以查看解析錯誤。

#### 使用符號連結在專案間共享規則

`.claude/rules/` 目錄支援符號連結，因此您可以維護一組共享規則並將它們連結到多個專案。循環符號連結會被偵測並妥善處理。

Claude Code 將其目標在工作目錄外的符號連結視為 [external import](#import-additional-files)。連結的規則在您核准專案的外部匯入之前不會載入，之後僅載入沒有 [`paths` 欄位](#path-specific-rules) 的規則。

Claude Code 每個專案只會要求一次該核准，方式是在互動式工作階段開始時顯示對話框。該對話框會列出連結的規則檔案，以及任何外部 `@path` 匯入。若要載入共享規則而不需要該核准，請將它們保留在 [`~/.claude/rules/`](#user-level-rules) 中，其中它們適用於您機器上的每個專案。

此範例連結共享目錄和個別檔案：

```bash theme={null}
ln -s ~/shared-claude-rules .claude/rules/shared
ln -s ~/company-standards/security.md .claude/rules/security.md
```

如果您將 `.claude/rules/` 或 `CLAUDE.md` 符號連結指向網路路徑（例如 UNC 共享 `\\server\share` 或 `/net` 或 `/Network` 下的路徑），連結的指令不會載入。Claude Code 不會跟隨連結，因為查詢此類路徑可能會聯絡它命名的主機。`\\wsl$` 路徑不計為網路路徑。

#### 使用者級規則

`~/.claude/rules/` 中的個人規則適用於您機器上的每個專案。使用它們來設定不是專案特定的偏好設定：

```text theme={null}
~/.claude/rules/
├── preferences.md    # Your personal coding preferences
└── workflows.md      # Your preferred workflows
```

Claude Code 在專案規則之前載入使用者級規則，因此專案規則在 Claude 的背景中出現得更晚。兩個集合都不會覆寫另一個：如果使用者規則和專案規則衝突，Claude 可能會遵循任一個，因此請保持兩者一致。

### 為大型團隊管理 CLAUDE.md

對於在團隊中部署 Claude Code 的組織，您可以集中指令並控制載入哪些 CLAUDE.md 檔案。

#### 部署組織範圍 CLAUDE.md

組織可以部署適用於機器上所有使用者的集中管理 CLAUDE.md。開發人員可以使用 `claudeMdExcludes` 設定 [排除其他 CLAUDE.md 檔案](#exclude-specific-claude-md-files)，但無法排除此檔案。如果開發人員在完全關閉 CLAUDE.md 載入的情況下啟動工作階段，該工作階段也不會載入受管理的內容。請將此檔案用於指導，並使用 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md)（例如 `permissions.deny`）強制執行規則。

**1. 在受管理的原則位置建立檔案**

* macOS：`/Library/Application Support/ClaudeCode/CLAUDE.md`
* Linux 和 WSL：`/etc/claude-code/CLAUDE.md`
* Windows：`C:\Program Files\ClaudeCode\CLAUDE.md`

**2. 使用您的設定管理系統進行部署**

使用 MDM、Group Policy、Ansible 或類似工具在開發人員機器上分發檔案。請參閱 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md) 以了解其他組織範圍設定選項。

`claudeMd` 金鑰可讓您將受管理的 CLAUDE.md 內容直接放入 `managed-settings.json` 中，而不是部署單獨的檔案。

**範圍**：機器上的所有使用者，在任何儲存庫中。對於儲存庫特定的指導，請改為提交專案 CLAUDE.md。

**優先順序**：與受管理的 CLAUDE.md 檔案相同。在使用者和專案 CLAUDE.md 之前載入。

**適用位置**：僅受管理和原則設定。在使用者、專案或本機設定中設定 `claudeMd` 無效。

下面的範例直接在受管理的設定檔案中新增行為指令：

```json theme={null}
{
  "claudeMd": "Always run `make lint` before committing.\nNever push directly to main."
}
```

受管理的 CLAUDE.md 和 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md) 服務於不同的目的。使用設定進行技術強制執行，使用 CLAUDE.md 進行行為指導：

| 關注 | 設定於 |
| :- | :- |
| 阻止特定工具、命令或檔案路徑 | 受管理的設定：`permissions.deny` |
| 強制執行沙箱隔離 | 受管理的設定：`sandbox.enabled` |
| 環境變數和 API 提供者路由 | 受管理的設定：`env` |
| 登入方法和組織限制 | 受管理的設定：`forceLoginMethod`、`forceLoginOrgUUID` |
| 程式碼樣式和品質指南 | 受管理的 CLAUDE.md |
| 資料處理和合規提醒 | 受管理的 CLAUDE.md |
| Claude 的行為指令 | 受管理的 CLAUDE.md |

設定規則由用戶端強制執行，無論 Claude 決定做什麼。CLAUDE.md 指令塑造 Claude 的行為，但不是硬強制執行層。

#### 排除特定 CLAUDE.md 檔案

在大型 monorepos 中，祖先 CLAUDE.md 檔案可能包含與您的工作無關的指令。`claudeMdExcludes` 設定可讓您按路徑或 glob 模式跳過特定檔案。您無法使用 `claudeMdExcludes` 排除 [受管理的 CLAUDE.md 檔案](#deploy-organization-wide-claude-md)。

此範例排除頂級 CLAUDE.md 和來自父資料夾的規則目錄。將其新增至 `.claude/settings.local.json`，以便排除保持本機於您的機器：

```json theme={null}
{
  "claudeMdExcludes": [
    "**/monorepo/CLAUDE.md",
    "/home/user/monorepo/other-team/.claude/rules/**"
  ]
}
```

模式使用 glob 語法與絕對檔案路徑匹配。您可以在任何 [settings layer](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)：使用者、專案、本機或受管理原則中設定 `claudeMdExcludes`。陣列在各層中合併。

若要排除您透過 [symlink](#share-rules-across-projects-with-symlinks) 到達的規則檔案（無論檔案或其目錄是連結），請針對任一路徑編寫模式：檔案在 `.claude/rules/` 下的路徑或其連結目標。匹配任一路徑的模式會排除檔案。在 v2.1.239 之前，僅匹配連結目標的模式會排除檔案。

## AGENTS.md

Claude Code 可以將 [`AGENTS.md`](https://code.claude.com/docs/zh-TW/glossary#agents-md) 讀取為您的專案指示，因此已為其他編碼代理設定的儲存庫無需新增 `CLAUDE.md`、匯入或設定即可運作。此表格顯示 Claude 在您的儲存庫中指示檔案的每種組合下預設讀取的內容：

| 您的儲存庫有 | Claude 讀取 |
| :- | :- |
| 一個 `AGENTS.md`，且在您的工作目錄或其上方沒有 `CLAUDE.md` 或 `CLAUDE.local.md` | 您的 `AGENTS.md` |
| 一個 `AGENTS.md` 和一個 `CLAUDE.md` 或 `CLAUDE.local.md` 在您的工作目錄或其上方 | 僅您的 `CLAUDE.md` 檔案 |
| 一個已經[匯入 `AGENTS.md`](#share-one-file-with-other-coding-tools) 的 `CLAUDE.md` | 您的 `CLAUDE.md`，透過匯入包含 `AGENTS.md` |

若要變更預設值，例如讓 Claude 始終讀取兩個檔案、僅讀取 `CLAUDE.md` 或僅讀取您組織的受管指示，請[變更**專案指示**設定](#choose-which-instruction-files-load)。

> [!NOTE]
>
> 直接讀取 `AGENTS.md` 需要 Claude Code v2.1.277 或更新版本。在某些工作階段中，Claude [無法讀取 `AGENTS.md`](#when-agents-md-support-is-unavailable)，因此請改為[從 `CLAUDE.md` 匯入](#share-one-file-with-other-coding-tools)。

### Claude Code 何時讀取 AGENTS.md

預設情況下，Claude 只有在您的工作目錄或其上方沒有 `CLAUDE.md` 時才會讀取 `AGENTS.md`。以下是您的哪些檔案計入該檢查：

* **計入，因此 Claude 改為讀取它們而不是 `AGENTS.md`**：您的工作目錄或其上方任何目錄中的 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md`
* **不計入，並繼續與 `AGENTS.md` 一起載入**：您的 `~/.claude/CLAUDE.md`、您組織的受管 `CLAUDE.md` 和 `.claude/rules/` 檔案

當沒有計入時，以下是 Claude 讀取的內容以及您如何判斷：

* **在工作階段開始時**：您的工作目錄及其上方目錄中的每個 `AGENTS.md` 和 `.claude/AGENTS.md`。在互動式工作階段中，您會在對話中看到類似 `no CLAUDE.md found; AGENTS.md loaded: /home/you/repo/AGENTS.md` 的行
* **當 Claude 在子目錄中工作時**：當 Claude 使用 Read 工具在該處開啟檔案，且該子目錄本身沒有這三個 `CLAUDE.md` 檔案中的任何一個時，子目錄的 `AGENTS.md`
* **在每個 `AGENTS.md` 內**：[`@path` 匯入](#import-additional-files)會展開，[`claudeMdExcludes`](#exclude-specific-claude-md-files) 模式適用，而[啟動時不含專案指示](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)的 subagent 啟動時也不含這些檔案
* **不讀取**：`AGENTS.local.md`、`AGENTS.override.md` 或 `.agents/` 目錄下的任何內容

> [!NOTE]
>
> 因為 `CLAUDE.local.md` 計入，在依賴 `AGENTS.md` 的專案中新增一個以保留您自己的未提交指示會停止 Claude 為您讀取 `AGENTS.md`。若要保留您的 `CLAUDE.local.md` 並仍讓 Claude 讀取 `AGENTS.md`，請將**專案指示**設定為 [`claude-md-and-agents-md`](#choose-which-instruction-files-load)。

### 選擇要載入的指示檔案

若要變更 Claude 讀取的檔案，請在 Claude Code 工作階段中輸入 `/config` 以開啟設定面板，然後將**專案指示**設定為以下其中一個值：

| 值 | Claude 讀取的內容 |
| :- | :- |
| `claude-md-or-agents-md` | 您的 `CLAUDE.md` 檔案，或當您在工作目錄或其上方沒有 `CLAUDE.md` 或 `CLAUDE.local.md` 時的 `AGENTS.md` 檔案。這是預設值 |
| `claude-md-and-agents-md` | 您的 `CLAUDE.md` 和 `AGENTS.md` 檔案一起，每個目錄的 `CLAUDE.md` 檔案優先，其 `AGENTS.md` 在之後。Claude Code 會跳過已經載入的 `AGENTS.md`，因此您的 `CLAUDE.md` 匯入或符號連結到的 `AGENTS.md` 不會讀取兩次 |
| `claude-md` | 僅您的 `CLAUDE.md` 檔案 |
| `managed-only` | 僅您組織的受管 `CLAUDE.md` 和啟動時的[自動記憶](#auto-memory)。您的專案、本機和使用者 `CLAUDE.md` 檔案、您的 `.claude/rules/` 檔案和每個 `AGENTS.md` 都被排除在外。子目錄的 `CLAUDE.md` 和 `.claude/rules/` 檔案，以及[路徑範圍規則](#path-specific-rules)，仍會按需載入 |

您也可以在設定檔中設定值，而不是使用 `/config`。將它新增到 [`pluginConfigs`](https://code.claude.com/docs/zh-TW/settings-reference#pluginconfigs) 中的 `cc-plugin-agents-md@builtin` 下，這是讀取 `AGENTS.md` 的內建外掛的 ID。Claude Code 會從 `~/.claude/settings.json`、`--settings` 檔案或[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中讀取該項目，並在專案和本機設定檔中忽略它。此範例讓 Claude 讀取兩個檔案：

```json settings.json theme={null}
{
  "pluginConfigs": {
    "cc-plugin-agents-md@builtin": {
      "options": { "instructionFiles": "claude-md-and-agents-md" }
    }
  }
}
```

在 v2.1.285 之前，該外掛的 ID 是 `agents-md@builtin`，且 Claude Code 會忽略 `cc-plugin-agents-md@builtin` 下的項目。如果較早的版本也會讀取您的設定檔，請在其中使用 `agents-md@builtin`。Claude Code v2.1.285 及更新版本會讀取任一 ID 下的項目。

您的變更從您傳送的下一則訊息和每個新工作階段開始套用。

### 當 AGENTS.md 支援不可用時

在這些工作階段中，Claude 僅讀取 `CLAUDE.md` 檔案，**專案指示**不會出現在 `/config` 設定面板中：

* 您使用的是 v2.1.277 之前的 Claude Code 版本
* 您使用 `/plugin` 停用了讀取 `AGENTS.md` 的內建外掛
* 在某些情況下，這是您[從 v2.1.276 或更早版本升級](https://code.claude.com/docs/zh-TW/env-vars.md#first-session-after-an-install-or-upgrade)後的第一個工作階段。Claude 會從您的下一個工作階段開始讀取 `AGENTS.md`

在 v2.1.281 之前，某些工作階段（例如在 Amazon Bedrock 上或停用遙測的工作階段）僅讀取 `CLAUDE.md` 檔案。在這些版本上，請更新 Claude Code。若要在這些工作階段中將您的 `AGENTS.md` 提供給 Claude，請[從 `CLAUDE.md` 匯入](#share-one-file-with-other-coding-tools)。

### AGENTS.md 與 CLAUDE.md 的差異

通過**專案指示**設定讀取的 `AGENTS.md` 與 `CLAUDE.md` 在以下方面有所不同：

| | `CLAUDE.md` | 通過設定讀取的 `AGENTS.md` |
| :- | :- | :- |
| [`InstructionsLoaded` hooks](https://code.claude.com/docs/zh-TW/hooks#instructionsloaded) | 觸發 | 不觸發。當 `CLAUDE.md` 匯入或符號連結到 `AGENTS.md` 時，它們會照常觸發 |
| 當 [`CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD`](#load-from-additional-directories) 設定時，您使用 `--add-dir` 新增的目錄 | 它們的 `CLAUDE.md` 載入 | 它們的 `AGENTS.md` 不載入 |
| 工作目錄外檔案的 `@path` 匯入 | Claude Code 要求您核准[外部匯入](#import-additional-files) | 僅在您已經為此專案核准外部匯入時載入，無提示 |

### 移除較早的 AGENTS.md 因應措施

如果您在 Claude Code 自行讀取 `AGENTS.md` 之前設定它來讀取，以下是對每個常見設定的處理方式：

* **包含 `@AGENTS.md` 的 `CLAUDE.md`**：您可以保留它。保留匯入永遠不會讓 Claude 讀取 `AGENTS.md` 兩次，無論您使用哪個**專案指示**值。如果檔案不包含其他內容，請移除 `CLAUDE.md`，或如果您的某些工作階段[無法直接載入 `AGENTS.md`](#when-agents-md-support-is-unavailable)，請保留它。
* **告訴 Claude 用文字讀取 `AGENTS.md` 的 `CLAUDE.md`**：Claude 只有在決定開啟檔案時才會看到 `AGENTS.md`。刪除 `CLAUDE.md` 以便 Claude 直接讀取 `AGENTS.md`，或用 `@AGENTS.md` 匯入取代該句子。
* **符號連結到 `AGENTS.md` 的 `CLAUDE.md`**：無，或刪除符號連結。無論哪種方式，Claude 都會讀取內容一次。
* **列印 `AGENTS.md` 的 `SessionStart` hook**：移除它。一旦 Claude 直接讀取 `AGENTS.md`，hook 會將第二份副本新增到內容中。

### 與其他編碼工具共享一個檔案

當 Claude 不直接讀取您的 `AGENTS.md` 時，您仍然可以通過在其旁邊的 `CLAUDE.md` 中放置 `@AGENTS.md` 匯入來將其保留為每個工具共享的一個檔案。當您的專案也有 `CLAUDE.md` 時、當您已將**專案指示**設定為 `claude-md` 時，或在[無法載入 `AGENTS.md`](#when-agents-md-support-is-unavailable) 的工作階段中執行此操作。在匯入下方新增任何 Claude 特定的指示，Claude 會先讀取匯入的檔案，然後讀取其餘部分：

```markdown CLAUDE.md theme={null}
@AGENTS.md

## Claude Code

Use plan mode for changes under `src/billing/`.
```

如果您不需要 Claude 特定的內容，符號連結也可以運作：

```bash theme={null}
ln -s AGENTS.md CLAUDE.md
```

該命令在成功時不列印任何輸出。在選擇符號連結而不是匯入之前，請檢查這些限制：

* **編輯**：Claude 通過連結讀取 `CLAUDE.md`，但 Edit 和 Write 工具[拒絕通過符號連結寫入](https://code.claude.com/docs/zh-TW/errors.md#refusing-after-a-symlink-changed)，拒絕會指示 Claude 改為編輯連結的目標 `AGENTS.md`
* **Windows**：如果您或任何複製儲存庫的人在 Windows 上工作，請改用 `@AGENTS.md` 匯入。在那裡建立符號連結需要系統管理員權限或開發人員模式，Git 會將已提交的符號連結簽出為純文字檔案，除非啟用 `core.symlinks`，這會使該複製具有一行 `CLAUDE.md` 代替您的指示

使用任一方法，在您的下一個工作階段中執行 `/context all`，並確認 `CLAUDE.md` 出現在**記憶檔案**下。

### 從其他工具遷移指示

執行 [`/init`](https://code.claude.com/docs/zh-TW/commands) 會讀取其他工具的指示檔案並將相關部分合併到產生的 `CLAUDE.md` 中：

* `.cursor/rules/` 或 `.cursorrules` 中的 Cursor 規則
* `.github/copilot-instructions.md` 中的 Copilot 規則
* 設定 `CLAUDE_CODE_NEW_INIT=1` 時：`AGENTS.md`、`.devin/rules/`、`.windsurf/rules/` 或 `.windsurfrules`，以及 `.clinerules`

您也可以執行 [`/import`](https://code.claude.com/docs/zh-TW/commands) 將支援的編碼 agent 的設定帶入 Claude Code，這會將指示檔案（例如 `AGENTS.md`）的一次性副本附加到相符的 `CLAUDE.md`，並帶入 MCP 伺服器、命令、subagent 和 skill。

## 自動記憶

自動記憶讓 Claude 在您不編寫任何內容的情況下跨工作階段累積知識。Claude 在工作時為自己保存四種筆記。Claude 在記憶檔案的 frontmatter 中將類型記錄為 `type` 欄位：

* `user`：您的角色、專業知識和工作偏好
* `feedback`：您給 Claude 的更正和您確認的方法
* `project`：進行中的工作、截止日期和 Claude 無法從程式碼或 git 歷史記錄推導的決策
* `reference`：在專案外尋找資訊的位置，例如問題追蹤器或儀表板

Claude 會跳過任何可以從程式碼庫推導的內容，例如架構、檔案路徑或除錯修復。它也會跳過您的 CLAUDE.md 檔案已經說過的任何內容。

Claude 不會每個工作階段都保存內容。它根據資訊在未來對話中是否有用來決定值得記住的內容。

### 啟用或停用自動記憶

自動記憶在本機工作階段中預設為開啟。在 [Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段以外，[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-configuration.md#how-each-session’s-config-is-assembled)中的工作階段預設會在自動記憶關閉的情況下執行。

要切換它，請在工作階段中開啟 `/memory` 並使用自動記憶切換，這會將 `autoMemoryEnabled` 保存到您的使用者設定 `~/.claude/settings.json`。

該切換可以關閉自動記憶，但在以下工作階段中無法將其重新開啟：

* [背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)
* 由另一個 Claude Code 工作階段啟動的工作階段，例如當 Claude 透過其 Bash 工具執行 `claude` 時

當自動記憶在這些工作階段中關閉時，切換會顯示 `off · can't be turned on here; use a session started outside Claude Code`。若要重新開啟自動記憶，請直接在您的終端機中執行 `claude`，並在該工作階段中使用 `/memory` 切換。

要為單一專案關閉它，請在該專案的設定中設定 `autoMemoryEnabled`：

```json theme={null}
{
  "autoMemoryEnabled": false
}
```

要透過環境變數停用自動記憶，請設定 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。

### 儲存位置

每個專案在 `~/.claude/projects/<project>/memory/` 獲得自己的記憶目錄。`<project>` 路徑源自 git 儲存庫，因此同一儲存庫內的所有 worktrees 和子目錄共享一個自動記憶目錄。在 git 儲存庫外，改用專案根目錄。

如果您在 `CLAUDE_CONFIG_DIR` 旁邊設定 [`CLAUDE_CODE_PROJECT_DIR_NAME`](https://code.claude.com/docs/zh-TW/sessions#name-the-project-directory-yourself)，Claude Code 會使用該名稱作為 `<config dir>/projects/` 下的 `<project>` 目錄，無論您在哪個儲存庫中啟動它，因此使用該設定目錄啟動的專案共享一個自動記憶目錄。需要 Claude Code v2.1.234 或更新版本。

要將自動記憶儲存在不同位置，請在您的 `settings.json` 中設定 `autoMemoryDirectory`。它從任何[設定範圍](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)讀取：使用者、專案、本地、原則或 `--settings`。

```json theme={null}
{
  "autoMemoryDirectory": "~/my-custom-memory-dir"
}
```

此值必須是絕對路徑或以 `~/` 開頭。

當在專案的 `.claude/settings.json` 或 `.claude/settings.local.json` 中設定時，Claude Code 會根據與[設定檔案中的 hooks 相同的工作區信任規則](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)來接受它。當 [`permissions.blockReadsOutsideWorkingDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-blockreadsoutsideworkingdirectories) 開啟時，Claude Code 不會從[儲存庫提供的設定檔案](https://code.claude.com/docs/zh-TW/permissions.md#when-your-local-settings-file-needs-trust)選擇的目錄載入自動記憶，也不會將其保存到該目錄，無論該目錄位於何處。

目錄包含 `MEMORY.md` 索引和每個記憶一個主題檔案：

```text theme={null}
~/.claude/projects/<project>/memory/
├── MEMORY.md           # 索引，每個記憶一行，載入到每個工作階段
├── user_role.md        # 一個記憶
├── feedback_testing.md # 一個記憶
└── ...                 # Claude 建立的任何其他主題檔案
```

`MEMORY.md` 充當記憶目錄的索引。Claude 在您的工作階段中讀取和寫入此目錄中的檔案，使用 `MEMORY.md` 追蹤儲存的內容。

自動記憶是機器本地的。同一 git 儲存庫內的所有 worktrees 和子目錄共享一個自動記憶目錄。檔案不在機器或雲端環境之間共享。

Claude Code 在 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 保留期後刪除舊的工作階段記錄，但會從該[保留掃描](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)中排除記憶目錄中的記憶檔案。`MEMORY.md` 和主題檔案會保留到您或 Claude 編輯或刪除它們。

### 它如何運作

`MEMORY.md` 的前 200 行或前 25KB（以先到者為準）在每次對話開始時載入。超過該閾值的內容在工作階段開始時不載入。Claude 透過將詳細筆記移到單獨的主題檔案中來保持 `MEMORY.md` 簡潔。

Claude 寫入 `MEMORY.md` 後，Claude Code 會根據 200 行和 25KB 讀取限制測量檔案。如果檔案接近限制，Claude Code 會提醒 Claude 縮短它：每個條目保留一行，將詳細資訊移到主題檔案，並合併或刪除過時的條目。如果檔案超過限制，寫入仍然成功，但 Claude Code 會返回[錯誤，告訴 Claude 重寫索引](https://code.claude.com/docs/zh-TW/errors.md#memory-index-is-over-its-read-limit)，因為超過限制的所有內容在下次載入時都會被丟棄。

> [!NOTE]
>
> 此限制僅適用於 `MEMORY.md`。只要檔案不超過 4 MiB，Claude 就會取得啟動時載入的每個 CLAUDE.md 檔案的完整內容。Claude Code 會跳過超過 4 MiB 的檔案，完全不載入其內容。路徑範圍的規則和子目錄中的 CLAUDE.md 檔案有[各自較小的單一檔案限制](#claude-ignores-the-end-of-my-subdirectory-claude-md)。

Claude Code 在啟動時不載入主題檔案，例如 `user_role.md` 或 `feedback_testing.md`。Claude 在需要資訊時使用其標準檔案工具按需讀取它們。

主對話的自動記憶不會載入到[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#what-loads-at-startup)中；例外是[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)，它繼承父對話和系統提示。子代理自己的自動記憶（透過子代理 `memory` 欄位啟用）是一個單獨的目錄。

Claude 在您的工作階段中讀取和寫入記憶檔案。當您在 Claude Code 介面中看到「已保存 2 個記憶」或「已回憶 2 個記憶」之類的訊息時，Claude 正在主動更新或讀取 `~/.claude/projects/<project>/memory/`。

當 Claude 寫入以 YAML frontmatter 開頭的記憶檔案時，Claude Code 會在 `modified` frontmatter 欄位中記錄寫入時間作為 ISO 8601 時間戳。時間戳會向您以及讀回記憶時的 Claude 顯示該事實的新舊程度。

### 審計和編輯您的記憶

自動記憶檔案是純 markdown，您可以隨時編輯或刪除。執行 [`/memory`](#view-and-edit-with-%2Fmemory) 以從工作階段中瀏覽和開啟記憶檔案。

## 使用 `/memory` 檢視和編輯

`/memory` 命令列出您的 CLAUDE.md、CLAUDE.local.md 和其他記憶檔案在使用者和專案範圍內的位置。清單中包括尚不存在的檔案的使用者和專案 CLAUDE.md 項目。此命令也讓您切換自動記憶開啟或關閉，並提供開啟自動記憶資料夾的選項。選擇任何檔案以在您的編輯器中開啟它；選擇尚不存在的檔案會先建立它。

VS Code 等 GUI 編輯器會在單獨的視窗中開啟檔案，您可以在檔案開啟時繼續使用工作階段。Vim 等終端機編輯器會接管終端機，直到您退出。

當您要求 Claude 記住某些內容時，例如「始終使用 pnpm，而不是 npm」或「記住 API 測試需要本地 Redis 實例」，Claude 會將其保存到自動記憶。要改為將指令新增到 CLAUDE.md，請直接要求 Claude，例如「將此新增到 CLAUDE.md」，或透過 `/memory` 自己編輯檔案。

## 疑難排解記憶問題

這些是 CLAUDE.md 和自動記憶最常見的問題，以及除錯步驟。

### Claude 不遵循我的 CLAUDE.md

CLAUDE.md 內容作為系統提示詞後的使用者訊息傳遞，而不是系統提示詞本身的一部分。Claude 讀取它並嘗試遵循它，但沒有嚴格遵守的保證，特別是對於模糊或衝突的指令。

要除錯：

* 執行 `/context all` 並檢查 **Memory files** 下的清單，以驗證應在啟動時載入的 CLAUDE.md 和 CLAUDE.local.md 檔案。如果其中某個檔案未列在那裡，Claude 就看不到它。使用 `/memory` 開啟和編輯檔案。
* 如果出現 `Instruction file not loaded` 通知，請參閱[其含義以及處理方式](https://code.claude.com/docs/zh-TW/errors.md#instruction-file-not-loaded)。
* 工作目錄之子目錄中的 `CLAUDE.md` 不會出現在 **Memory files** 下，因為它是按需載入，而不是在啟動時載入。當它載入時，終端機中會出現一行包含其路徑的 `Loaded`。若要測試新的檔案，請從 shell 建立它，而不是要求 Claude 撰寫，然後要求 Claude 讀取該子目錄中的檔案。
* 檢查相關的 CLAUDE.md 是否位於為您的工作階段載入的位置（請參閱 [選擇 CLAUDE.md 檔案的位置](#choose-where-to-put-claude-md-files)）。
* 使指令更具體。「使用 2 空格縮排」比「正確格式化程式碼」效果更好。
* 查找跨 CLAUDE.md 檔案的衝突指令。如果兩個檔案為相同行為提供不同的指導，Claude 可能會任意選擇一個。
* 檢查您的指令是否與 Claude Code 自行新增的指導相競爭。如果您的 CLAUDE.md 設定提交或 pull request 規則，請使用 [`includeGitInstructions`](https://code.claude.com/docs/zh-TW/settings-reference#includegitinstructions) 關閉內建規則，並使用 [`attribution`](https://code.claude.com/docs/zh-TW/settings-reference#attribution) 設定歸屬文字。

如果指令是必須在特定時間點執行的內容，例如在每次提交前或每次檔案編輯後，請改為將其寫成 [hook](https://code.claude.com/docs/zh-TW/hooks-guide.md)。Hook 在固定的生命週期事件中作為 shell 命令執行，並且無論 Claude 決定做什麼都適用。

對於您想要在系統提示詞級別的指令，請使用 [`--append-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags)。您在啟動時傳遞它，因此它更適合指令碼和自動化，而不是互動式使用。如需了解它在恢復對話時的行為方式，請參閱 [已恢復對話中的系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)。

> [!TIP]
>
> 使用 [`InstructionsLoaded` hook](https://code.claude.com/docs/zh-TW/hooks#instructionsloaded) 記錄載入了哪些 `CLAUDE.md` 和規則檔案、何時載入以及為什麼。這對於除錯路徑特定規則或子目錄中的延遲載入檔案很有用。

### 我的 AGENTS.md 未載入

如果您的儲存庫有 `AGENTS.md` 且 Claude 似乎不知道它說什麼，通常原因是專案路徑上某處有 `CLAUDE.md`。根據預設，Claude 只有在您的工作目錄或其上方沒有 `CLAUDE.md` 或 `CLAUDE.local.md` 時才讀取 `AGENTS.md`。按順序檢查這些：

1. 在您的工作目錄或其上方的任何目錄中查找 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md`，除了您的 `~/.claude/CLAUDE.md`。如果您找到一個，Claude 會讀取它而不是 `AGENTS.md`，除非您將 **Project instructions** 設定為 `claude-md-and-agents-md`。
2. 執行 `claude --version` 並確認 v2.1.277 或更新版本。在 v2.1.281 之前，某些工作階段（例如 Amazon Bedrock 上的工作階段或停用遙測的工作階段）[無法載入 `AGENTS.md`](#when-agents-md-support-is-unavailable)，因此在這些版本上更新至 v2.1.281 或更新版本。
3. 在您的工作階段中輸入 `/config` 以開啟設定面板，並確認 **Project instructions** 未設定為 `claude-md` 或 `managed-only`。如果您根本看不到該設定，您的工作階段是 [無法載入 `AGENTS.md`](#when-agents-md-support-is-unavailable) 的工作階段。

要檢查 Claude 是否讀取了您的 `AGENTS.md`，請執行 `/memory` 並在清單中查找其路徑。

在 v2.1.280 之前，`/memory` 和 `/context` 未列出 Claude 直接讀取的 `AGENTS.md`。在這些版本上，改為詢問 Claude 其專案指令說什麼。

如果您想保留找到的 `CLAUDE.md`，或您的工作階段無法載入 `AGENTS.md`，[在您的 `AGENTS.md` 旁邊新增匯入它的 `CLAUDE.md`](#share-one-file-with-other-coding-tools)。

### 我不知道自動記憶保存了什麼

執行 `/memory` 並選擇自動記憶資料夾以瀏覽 Claude 保存的內容。一切都是純 markdown，您可以讀取、編輯或刪除。

### 我的 CLAUDE.md 太大了

超過 200 行的檔案消耗更多上下文，可能會降低遵守度。Claude Code 會跳過超過 4 MiB 的檔案。使用 [路徑範圍規則](#path-specific-rules) 僅在 Claude 處理符合的檔案時載入指令，或修剪不是每個工作階段都需要的內容。分割成 [`@path` 匯入](#import-additional-files) 有助於組織，但不會減少上下文，因為匯入的檔案會與匯入它們的 CLAUDE.md 一起載入。

如果您的其中一個指令檔案超過建議長度，您會在啟動時和執行 `/status` 時看到警告。當在工作階段開始時各自在該長度內的檔案加起來超過合併限制時，您也會看到警告。每個 CLAUDE.md、規則檔案和 `@path` 匯入都計為單獨的檔案。

[`/doctor`](https://code.claude.com/docs/zh-TW/commands#all-commands) 檢查會為已簽入的 CLAUDE.md 提出修剪建議：它會刪除 Claude 可以從程式碼庫衍生的內容，例如目錄配置、相依性清單和架構概述，並保留與工具預設值不同的陷阱、基本原理和慣例。

> [!NOTE]
>
> 請將每個路徑範圍規則檔案保持在[其各自的單一檔案大小限制](#claude-ignores-the-end-of-my-subdirectory-claude-md)內，因為對於超過該限制的檔案，Claude 只會收到檔案的開頭部分。

### Claude 忽略了我的子目錄 CLAUDE.md 的結尾部分

當子目錄中的 `CLAUDE.md` 或按需載入的規則檔案超過單一檔案大小限制時，Claude 只會收到檔案的開頭部分。該部分的結尾會附上一則說明，告知 Claude 使用 Read 工具讀取其餘內容；在 Claude 選擇這麼做之前，後面的指令不會出現在其上下文中。

檢查您的檔案是否超過限制，如果超過，請將其縮減：

1. 確認該限制適用於您的檔案。此限制適用於以下按需載入的檔案：
   * 位於您啟動 Claude Code 之目錄的子目錄中的 `CLAUDE.md` 和 `CLAUDE.local.md`，以及它們透過 `@path` [匯入](#import-additional-files)的檔案
   * 子目錄 `.claude/rules/` 中的規則檔案
   * 專案的 `.claude/rules/` 或 `~/.claude/rules/` 中的[路徑範圍規則](#path-specific-rules)
2. 找出適用於您工作階段之[上下文視窗](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)的限制：
   * **200K 上下文視窗**：40,000 個字元
   * **1M 上下文視窗**：在 Claude Opus 4.6 和 Claude Sonnet 4.6 上為 200,000 個字元，在更新的模型上為 150,000 個字元
3. 在 Bash 或 Zsh 中，執行 `wc -m path/to/CLAUDE.md` 以輸出檔案的字元數。
4. 將字元數與您的限制進行比較：
   * **超過限制**：修剪檔案，或將其中一部分移至一個或多個規則檔案中，每個規則檔案會各自計算是否超過限制
   * **未超過限制**：在 [Claude 不遵循我的 CLAUDE.md](#claude-isn’t-following-my-claude-md) 中尋找其他原因

在 v2.1.309 之前，Claude Code 不會對按需載入的檔案套用此限制。

### 指令在 `/compact` 後似乎丟失了

專案根目錄 CLAUDE.md 在壓縮中倖存：在 `/compact` 之後，Claude 從磁碟重新讀取它並將其重新注入到工作階段中。子目錄中的巢狀 CLAUDE.md 檔案和具有 [`paths:` frontmatter](#path-specific-rules) 的規則會按需重新載入。

如果指令在壓縮後消失，它要麼只在對話中給出，要麼位於尚未重新載入的巢狀 CLAUDE.md 中，或者是尚未符合檔案的路徑範圍規則。將對話專用指令新增到 CLAUDE.md 以使其持久化。有關完整的細目，請參閱 [壓縮後倖存的內容](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)。

請參閱 [編寫有效的指令](#write-effective-instructions) 以取得有關大小、結構和具體性的指導。

## 相關資源

* [除錯您的配置](https://code.claude.com/docs/zh-TW/debug-your-config.md)：診斷為什麼 CLAUDE.md 或設定未生效
* [Skills](https://code.claude.com/docs/zh-TW/skills.md)：封裝按需載入的可重複工作流程
* [設定](https://code.claude.com/docs/zh-TW/settings.md)：使用設定檔案配置 Claude Code 行為
* [Subagent 記憶](https://code.claude.com/docs/zh-TW/sub-agents.md#enable-persistent-memory)：讓 subagents 維護自己的自動記憶
