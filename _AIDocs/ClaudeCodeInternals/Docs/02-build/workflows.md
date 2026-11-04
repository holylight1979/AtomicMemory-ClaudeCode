<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/workflows | lastmod: 2026-10-27 | section: Build with Claude Code / Agents and parallel work -->
> 來源：https://code.claude.com/docs/zh-TW/workflows（官方 zh-TW，lastmod 2026-10-27）｜分類：Build with Claude Code › Agents and parallel work｜EN 摘要：Dynamic workflows orchestrate many subagents from a script Claude writes and you can rerun. Use them for codebase audits, large migrations, and cross-checked research.

# 使用動態工作流程大規模協調子代理

> 動態工作流程從 Claude 編寫的指令碼協調許多子代理，您可以重新執行。用於程式碼庫審計、大規模遷移和交叉檢查研究。

> [!NOTE]
>
> 動態工作流程在所有付費方案上可用，具有 Anthropic API 存取權限，以及在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上可用。在 Pro 上，從 `/config` 中的 Dynamic workflows 列啟用它們。

動態工作流程是一個 JavaScript 指令碼，可大規模協調許多[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)。Claude 為您描述的任務編寫指令碼，執行時期在背景執行它，同時您的工作階段保持回應。

當任務需要超過一個對話可以協調的代理數量時，或當您想將協調編成可以讀取和重新執行的指令碼時，請使用工作流程。範例包括程式碼庫範圍的錯誤掃描、500 個檔案遷移、需要相互交叉檢查來源的研究問題，以及值得從多個獨立角度起草的困難計畫，然後再提交給其中一個。

## 何時使用工作流程

[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)、[技能](https://code.claude.com/docs/zh-TW/skills.md)、[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)和工作流程都可以執行多步驟任務。區別在於誰掌握計畫：

| | 子代理 | 技能 | 代理團隊 | 工作流程 |
| :- | :- | :- | :- | :- |
| 它是什麼 | Claude 生成的工作者 | Claude 遵循的指示 | 監督對等工作階段的主導代理 | 執行時期執行的指令碼 |
| 誰決定接下來執行什麼 | Claude，逐輪 | Claude，遵循提示 | 主導代理，逐輪 | 指令碼 |
| 中間結果在哪裡 | Claude 的上下文視窗 | Claude 的上下文視窗 | 共享任務清單 | 指令碼變數 |
| 什麼是可重複的 | 工作者定義 | 指示 | 團隊定義 | 協調本身 |
| 規模 | 每輪委派的幾項任務 | 與子代理相同 | 少數長時間執行的對等代理 | 每次執行數十到數百個代理 |
| 中斷 | 重新啟動輪次 | 重新啟動輪次 | 隊友繼續執行 | 在同一工作階段中可恢復 |

工作流程將計畫移入程式碼。使用子代理、技能和代理團隊，Claude 是協調者：它逐輪決定接下來要生成或指派什麼，每個結果都進入上下文視窗。工作流程指令碼保存迴圈、分支和中間結果本身，因此 Claude 的上下文只保存最終答案。

將計畫移入程式碼也讓工作流程應用可重複的品質模式，而不僅僅是執行更多代理：它可以讓獨立代理在報告前對彼此的發現進行對抗性審查，或從多個角度起草計畫並相互權衡，因此您獲得比單次通過更可信的結果。

## 執行捆綁的工作流程

查看工作流程運作的最快方式是執行 `/deep-research`，[內建工作流程](#bundled-workflows)Claude Code 包含用於跨許多來源調查問題。您將看到代理在背景中完成一組階段，同時您的工作階段保持自由，最後獲得一份報告而不是逐輪記錄。

**1. 執行工作流程**

使用您想調查的問題執行 `/deep-research`。它在多個角度上展開網路搜尋，獲取並交叉檢查它找到的來源，並合成引用的報告。

```text wrap theme={null}
/deep-research What changed in the Node.js permission model between v20 and v22?
```

**2. 允許工作流程**

Claude Code 詢問是否允許工作流程。選擇 **Yes** 以繼續。確切的提示取決於您的權限模式。有關每種模式選項，請參閱[在執行前批准計畫](#approve-the-plan-before-it-runs)。

**3. 監視進度**

執行在背景中啟動。執行 `/workflows` 以開啟其進度檢視：

```text wrap theme={null}
/workflows
```

如果 `/workflows` 改為顯示執行清單，請選擇您剛啟動的執行並按 Enter。檢視顯示每個階段及其 agent 數量。深入任何階段以查看其 agent 及每個 agent 發現的內容。有關完整的控制集，請參閱[監視執行](#watch-the-run)。

您也可以從輸入框下方的任務面板監視：執行進行時會出現一行進度摘要。按向下箭頭聚焦它，然後按 Enter 展開。

**4. 閱讀報告**

執行完成後，報告進入您的工作階段。它引用每項聲明來自的來源，未通過交叉檢查的聲明已被篩選出去。

當驗證代理無法檢查聲明時（例如在速率限制或 API 錯誤之後），報告會將該聲明列為未驗證，而不是計為駁回。

要為您自己的任務執行工作流程，[讓 Claude 編寫一個](#have-claude-write-a-workflow)，一旦執行執行您想要的操作，您可以[儲存它](#save-the-workflow-for-reuse)作為您自己的命令。

### 捆綁的工作流程

Claude Code 包含 `/deep-research` 作為內建工作流程：

| 命令 | 它做什麼 |
| :- | :- |
| `/deep-research <question>` | 在多個角度上展開網路搜尋問題，獲取並交叉檢查它找到的來源，對每項聲明進行投票，並返回引用的報告，其中未通過交叉檢查的聲明已被篩選出去。需要 [WebSearch 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#websearch-tool-behavior)可用 |

`/deep-research` 僅在您叫用時執行。

[您自己儲存的工作流程](#save-the-workflow-for-reuse)以相同方式成為命令，並在 `/` 自動完成中與捆綁的命令一起出現。

### 監視執行

工作流程在背景中執行，因此工作階段在 agent 工作時保持回應。隨時執行 `/workflows` 以列出執行中和已完成的工作流程，然後選擇一個以開啟其進度檢視。當工作階段只有一個執行時，`/workflows` 會略過清單並直接開啟該執行。若要停止執行中的工作流程而不開啟它，請在清單中選擇它並按 `x`。

進度檢視顯示每個階段及其 agent 數量。頁腳列出每個動作的鍵：

| 鍵 | 動作 |
| :- | :- |
| `↑` / `↓` | 選擇階段或代理 |
| `Enter` 或 `→` | 深入選定的階段，然後進入代理的詳細資訊。在詳細資訊中，`Enter` 展開或摺疊它 |
| `Esc` 或 `←` | 返回一個級別 |
| `j` / `k` | 當代理詳細資訊溢出時在其中捲動 |
| `f` | 按狀態篩選選定階段中的代理清單。再次按以循環 |
| `p` | 暫停或恢復執行 |
| `x` | 停止選定的代理，或當焦點在執行上時停止整個工作流程 |
| `r` | 重新啟動選定的執行中代理 |
| `s` | [儲存](#save-the-workflow-for-reuse)執行的指令碼作為命令 |

代理詳細資訊列出代理的提示、其最近的工具呼叫和其結果。每個呼叫顯示其狀態，例如仍在執行或失敗。當代理保持自己的任務清單時，詳細資訊會顯示它，以及每個任務的狀態。

按 `Enter` 展開詳細資訊。提示和結果隨後會完整顯示，每個列出的呼叫會顯示其輸入和其結果的開始。

## 讓 Claude 撰寫工作流程

您可以透過兩種方式讓 Claude 為您的任務撰寫工作流程：

* [在提示中要求工作流程](#ask-for-a-workflow-in-your-prompt)，用您自己的話語或包含關鍵字 `ultracode`，Claude 會為該任務撰寫一個工作流程。
* [讓 Claude 使用 ultracode 決定](#let-claude-decide-with-ultracode)：設定 `/effort ultracode`，Claude 會為工作階段中的每個實質性任務規劃一個工作流程。

您也可以執行已存在的工作流程命令：像 `/deep-research` 這樣的[捆綁工作流程](#bundled-workflows)，或您[保存](#save-the-workflow-for-reuse)的工作流程。

### 在提示中要求工作流程

若要在不變更工作階段努力程度的情況下將單一任務作為工作流程執行，請在提示中包含關鍵字 `ultracode`。用您自己的話語提問，例如「使用工作流程」或「執行工作流程」，也同樣有效：Claude 將直接要求視為相同的選擇加入。

```text wrap theme={null}
ultracode: audit every API endpoint under src/routes/ for missing auth checks
```

Claude Code 會在您的輸入中突顯該關鍵字，Claude 會為該任務撰寫工作流程指令碼，而不是逐步進行。該關鍵字只會選擇 Claude 如何組織工作：代理程式的工具呼叫會收到與工作階段中任何其他工具呼叫相同的權限檢查和[沙箱隔離](https://code.claude.com/docs/zh-TW/sandboxing.md)。

如果執行結果符合您的需求，您可以之後[將其保存為命令](#save-the-workflow-for-reuse)。如果您已經用另一種方式建立了協調器，例如子代理程式提示的資料夾或分散工作的技能，您可以指向它並要求 Claude 撰寫執行相同操作的工作流程。

#### 關閉或停用關鍵字

如果您不打算啟動工作流程，請在 macOS 上按 `Option+W` 或在 Windows 和 Linux 上按 `Alt+W` 以關閉此提示的突顯，或在游標位於突顯關鍵字之後時按退格鍵。若要完全停止關鍵字觸發，請在 `/config` 中關閉 Ultracode 關鍵字觸發。

#### 關鍵字的適用位置

該關鍵字是僅在您自己輸入的提示中選擇加入：在互動式提示、IDE 擴充面板、[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)用戶端或在代理程式 SDK 應用程式中，該應用程式將您的鍵盤輸入的 [`origin`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkmessageorigin) 標記為 `{ kind: "human" }`。當它以其他方式進入工作階段時，不會啟動工作流程：

* 使用 `-p` 傳遞的提示
* 代理程式 SDK 應用程式發送但未標記為人類輸入的提示
* 排程任務提示
* 轉發到對話中的 webhook 承載或拉取要求評論

### 讓 Claude 使用 ultracode 決定

Ultracode 是一個 Claude Code 設定，它在工作階段中啟用自動工作流程協調，無論工作階段執行的[努力程度](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)為何。啟用它後，Claude 會為每個實質性任務規劃一個工作流程，而不是等待您提出要求。在 Claude Code 提示中啟用它：

```text wrap theme={null}
/effort ultracode
```

若要在已啟用 ultracode 的情況下啟動工作階段，請使用 `claude --effort ultracode` 啟動，這也會將 effort 等級設定為 `xhigh`。

若要從 `/effort` 滑塊啟用它，請按 `Tab` 翻轉 **Ultracode** 切換，然後按 `Enter` 套用。[調整努力程度](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)列出了啟用 ultracode 的路由。

啟用 ultracode 後，Claude 會決定任務何時需要工作流程。單一要求可以轉變為連續的多個工作流程：一個用於理解程式碼，一個用於進行變更，一個用於驗證。這適用於工作階段中的每個任務，因此每個要求使用更多令牌並花費比沒有工作流程的相同要求更長的時間。在訂閱方案上，這些令牌會計入您的使用限制，因此啟用 ultracode 的工作階段會比在沒有啟用的情況下進行相同工作更快達到工作階段或每週限制。

啟用 ultracode 已經讓您選擇加入大型執行，因此在啟用時這些檢查不適用：

* [`Large workflow` 警告](#cost)不會出現在工作流程執行上
* 工作階段的[並行子代理程式限制](https://code.claude.com/docs/zh-TW/sub-agents.md#concurrent-subagent-limit)不會對 Claude 使用代理程式工具產生的子代理程式強制執行
* 在自動權限模式中，您不會被要求[批准第一個工作流程啟動](#approve-the-plan-before-it-runs)

`/effort ultracode` 在目前工作階段期間有效；若要讓每個工作階段都以它開始，請設定 [`ultracode`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode) 設定。當您回到例行工作時，使用 `/effort ultracode off` 關閉它。`/effort` 滑桿僅在 [ultracode 可用時](https://code.claude.com/docs/zh-TW/model-config.md#when-ultracode-is-available)提供此開關。在 v2.1.284 之前，`/effort ultracode` 會將工作階段設定為 `xhigh`，而 `/effort ultracode off` 會失敗並顯示 `Invalid argument`。

### 在執行前批准計畫

在 CLI 中，每次執行提示會顯示計畫的階段和這些選項：

* **Yes, run it**：啟動執行
* **Yes, and don't ask again for `<name>` in `<path>`**：啟動，並從現在開始在此專案中跳過此工作流程的此提示。當您按名稱執行捆綁、保存或外掛工作流程時，Claude Code 會提供此選項，而不是針對 Claude 為目前任務撰寫的指令碼。
* **View raw script**：在決定前讀取指令碼
* **No**：取消

`Ctrl+G` 在您的編輯器中開啟指令碼。選取 **Yes, run it** 或 **No** 時，按 `Tab` 可為您的回答[新增註解](https://code.claude.com/docs/zh-TW/permissions.md#add-a-comment-when-you-answer-a-permission-prompt)。

您是否看到此提示取決於您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)：

| 權限模式 | 何時提示您 |
| :- | :- |
| Auto | 僅首次啟動。任何 **Yes** 會在您的使用者設定中記錄同意，之後啟動時不會提示。當 ultracode 啟用時完全跳過 |
| Manual, accept edits | 每次執行，除非您已為此專案中的該工作流程選擇 **Yes, and don't ask again** |
| Bypass permissions | Claude Code 不會提示您。執行立即啟動 |
| `claude -p`, Agent SDK | Claude Code 不會提示您 |

在 `claude -p` 和 Agent SDK 中，Claude Code 永遠不會顯示此提示。它透過與工作階段其餘部分相同的[權限評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)執行 Workflow 工具呼叫，因此拒絕規則、詢問規則和 `dontAsk` 模式適用於啟動，就像它們適用於每個工具呼叫一樣。若要讓工作流程在這些執行中啟動，請使用以下其中一個：

* **Permission rule**：將 `Workflow` 新增到您的允許規則以核准每個工作流程，或新增 `Workflow(<name>)` 以按名稱核准一個保存的工作流程。
* **Auto permission mode**：在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中執行，分類器會檢查該呼叫並可以核准它。
* **Bypass permissions mode**：在 bypass permissions 模式中執行。
* **A hook**：從 [`PreToolUse`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) hook 為該呼叫回傳 `"allow"`。在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中，工作流程不會僅憑 hook 的核准就啟動，因此請在該處改用權限規則或您主機的核准。
* **Your host**：[`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 會核准它，或在使用 Agent SDK 時，由 [`canUseTool`](https://code.claude.com/docs/zh-TW/agent-sdk/permissions) 回呼核准它。

在桌面應用程式中，批准卡會顯示工作流程名稱、階段清單和令牌使用警告，具有 **Once**、**Always** 和 **Deny** 動作。進度檢視會出現在「背景任務」側窗格中。

工作流程產生的子代理程式使用您的[權限規則](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)，Claude Code 根據[子代理程式執行的權限模式](https://code.claude.com/docs/zh-TW/sub-agents.md#permission-modes)下的規則選擇其權限模式。若要避免在長時間執行時出現提示，請在啟動前將代理程式需要的工具新增到您的允許規則。

### 保存工作流程以供重複使用

當 Claude 為您將重複的任務撰寫工作流程時，您可以將該執行的指令碼保存為命令。像在每個分支上執行的檢查這樣的程序然後每次執行相同的協調。

執行 `/workflows`，選擇您想保留的執行，然後按 `s`。在保存對話中，Tab 在兩個保存位置之間切換：

* 您專案中的 `.claude/workflows/`：與克隆儲存庫的每個人共享
* 您主目錄中的 `~/.claude/workflows/`：在每個專案中可用，僅對您可見。如果您設定了 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，此位置是該路徑下的 `workflows/` 目錄。

保存對話框會顯示個人位置的已解析路徑。按 Enter 保存。工作流程在未來工作階段中從任一位置作為 `/<name>` 執行。

Claude Code 在寫入前檢查保存位置是否有符號連結，並顯示錯誤而不是透過符號連結寫入：

* 專案位置：如果 `.claude`、`.claude/workflows` 或目標檔案是符號連結，Claude Code 會拒絕。
* 個人位置：Claude Code 僅在目標檔案本身是符號連結時拒絕，因此由 dotfiles 工具管理的 `~/.claude` 目錄仍然有效。

在具有多個 `.claude/` 目錄的 monorepo 中，您可以將工作流程保留在它們適用的套件旁邊。保存到專案位置會寫入您的工作目錄和儲存庫根目錄之間已存在的最接近的 `.claude/workflows/` 目錄，或如果尚不存在，則寫入儲存庫根目錄。專案工作流程也會從該路徑沿著的每個 `.claude/workflows/` 載入，當多個定義相同名稱時，Claude Code 執行最接近工作目錄的那個。

如果專案工作流程和個人工作流程共享名稱，則執行專案工作流程。

### 在外掛中分發工作流程

若要在團隊或儲存庫之間共享工作流程，請將其包含在[外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)中。將指令碼放在外掛根目錄的 `workflows/` 目錄中，或使用 [`workflows` 資訊清單欄位](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#fields)指向不同位置。

外掛工作流程由外掛名稱命名空間。名為 `acme-tools` 的外掛，其 `meta.name` 為 `release-audit` 的指令碼作為 `/acme-tools:release-audit` 執行。

### 將輸入傳遞到保存的工作流程

保存的工作流程可以透過 `args` 參數接受輸入。指令碼將其讀取為名為 `args` 的全域變數。使用此方法在呼叫時提供研究問題、目標路徑清單或設定物件，而不是為每次執行編輯指令碼。

以下提示使用問題編號清單執行保存的工作流程：

```text wrap theme={null}
Run /triage-issues on issues 1024, 1025, and 1030
```

Claude 將清單作為結構化資料傳遞，因此指令碼可以直接在 `args` 上呼叫陣列和物件方法，而無需先解析它。如果省略 `args`，全域變數在指令碼內為 `undefined`。

## 工作流程提示範例

工作流程最適合當任務大於一個代理可以在上下文中保存的情況，或當相同的步驟需要在許多項目上執行時。下面的提示顯示常見的形狀。每一個都要求 Claude 為該任務編寫並執行工作流程；您不自己編寫指令碼。

### 審計許多檔案以查找相同問題

展開每個檔案一個代理，然後收集並驗證發現。

```text wrap theme={null}
use a workflow to audit every route handler under src/routes/ for missing authentication checks, and adversarially verify each finding before reporting it
```

### 持續修復直到檢查通過

執行檢查器、修復失敗的內容，並重複直到通過或停止進展。

```text wrap theme={null}
use a workflow to run npx tsc --noEmit and keep fixing the reported errors until the type check passes or two rounds in a row make no progress
```

### 並行遷移許多檔案

發現要遷移的檔案，在隔離的副本中轉換每個檔案，以便編輯不衝突，並驗證每個結果。

```text wrap theme={null}
use a workflow to migrate every component under src/components/ from JavaScript to TypeScript, working on each file in its own isolated copy
```

### 審查每個更改的檔案並寫一份摘要

為每個檔案執行審查者，然後將所有發現交給一個代理，該代理對它們進行排名和去重。

```text wrap theme={null}
use a workflow to review every file changed in this PR for correctness issues, then merge the per-file findings into one ranked summary
```

### 跨許多來源研究主題

在變更日誌、問題和文件中展開讀者，然後合成。捆綁的 `/deep-research` 工作流程執行此操作；您也可以描述更狹隘的版本。

```text wrap theme={null}
use a workflow to research how our three competitors handle rate limiting: read their public docs and recent changelog entries in parallel, then compare the approaches
```

### 查找問題直到清單停止增長

持續搜尋並在新輪次發現沒有新內容時停止。

```text wrap theme={null}
use a workflow to find flaky tests in this repo: run the suite repeatedly, record which tests fail intermittently, and stop once two rounds in a row find nothing new
```

### 已儲存的指令碼看起來像什麼

當您[儲存工作流程](#save-the-workflow-for-reuse)時，`.claude/workflows/` 中的檔案保存一個 `meta` 塊，後面跟著協調子代理的指令碼主體。您通常不需要編輯它，但這是一個小的形狀，以便您可以識別 Claude 生成的內容：

```javascript theme={null}
export const meta = {
  name: 'audit-routes',
  description: 'Audit every route handler for missing auth checks',
}

const found = await agent('List every .ts file under src/routes/.', {
  schema: { type: 'object', required: ['files'], properties: { files: { type: 'array', items: { type: 'string' } } } },
})

const audits = await pipeline(found.files, file =>
  agent(`Audit ${file} for missing authentication checks.`, { label: file }),
)

return audits.filter(Boolean)
```

主體是具有頂級 `await` 的純 JavaScript。`agent()` 生成一個子代理，`pipeline()` 為清單中的每個項目執行一個，而 `parallel()` 同時執行一組代理任務並等待所有任務完成。

如果您在執行中途停止 `agent()` 呼叫，或它遇到無法恢復的 API 錯誤，該呼叫會解析為 `null`。`pipeline()` 在結果陣列中保留每個 `null`，這就是為什麼範例以 `.filter(Boolean)` 結尾以刪除這些項目，包括[每次嘗試都停滯的 agent](#when-an-agent-stalls-and-restarts) 所佔的位置。

在[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中，您的指令碼傳遞給 `agent()` 的提示不會計為您的請求，當分類器審查該子代理的動作時，因為 Claude Code 將其標記為指令碼計算的文字。

如果您在 `agent()` 呼叫上傳遞 `schema`，該子代理會傳回與形狀相符的 JSON 而不是散文。Claude Code 在啟動子代理之前檢查架構：當它可以證明架構自相矛盾時，呼叫會失敗並出現錯誤，命名矛盾，子代理永遠不會啟動。它可以證明的一個矛盾是 `additionalProperties: false` 排除的 `required` 鍵。

如果子代理的輸出在五次嘗試後仍然無法通過驗證，呼叫會失敗並出現包含最後驗證失敗的錯誤。若要變更嘗試次數，請設定 [`MAX_STRUCTURED_OUTPUT_RETRIES`](https://code.claude.com/docs/zh-TW/env-vars)。

### 編輯已儲存的指令碼

若要變更[您儲存的工作流程](#save-the-workflow-for-reuse)，請編輯其 `.js` 檔案或要求 Claude 進行變更。在您編輯或要求之前，執行 `/workflow-authoring` [捆綁技能](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)以載入 Claude 工作的指令碼編寫參考。該技能需要 Claude Code v2.1.248 或更新版本。

若要在目前工作階段中執行編輯版本，執行 [`/reload-skills`](https://code.claude.com/docs/zh-TW/commands#all-commands) 以重新讀取工作流程目錄，然後再次執行 `/<name>`。

Claude Code 在載入和執行指令碼時對檔案的每個部分應用這些規則：

* **`meta` 塊**：將 `export const meta` 保留為第一個陳述式，並將其保留為具有 `name` 和 `description` 的純物件字面值。如果它包含除字面值以外的任何內容，例如變數、函式呼叫或展開，Claude Code 會從 `/` 自動完成中刪除 `/<name>`。
* **主體**：除了 `agent()`、`pipeline()` 和 `parallel()` 之外，您可以呼叫 `phase()` 以在進度檢視中將後續代理分組到標題下，呼叫 `log()` 以在階段上方顯示訊息，並讀取 [`args`](#pass-input-to-a-saved-workflow) 全域。如果主體有語法錯誤，Claude Code 會在您執行工作流程時報告它。
* **`phases`**：如果您在 `meta` 中列出它們，請為每個項目提供您傳遞給 `phase()` 的確切標題。沒有項目的 `phase()` 標題會獲得自己的進度群組。
* **時間戳記和隨機性**：Claude Code 使 `Date.now()`、`Math.random()` 和無引數 `new Date()` 在指令碼內拋出，以便[重新啟動的執行](#resume-after-a-pause)重複相同的 `agent()` 呼叫。改為透過 `args` 傳遞時間戳記。

您也可以編輯[單次執行的指令碼](#how-a-workflow-runs)而不是已儲存的副本。[在暫停後繼續](#resume-after-a-pause)涵蓋當您重新啟動編輯的指令碼時哪些代理再次執行。如需 Workflow 工具的輸入，請參閱其在 [Agent SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#workflow)中的項目。

## 工作流程如何執行

工作流程執行時期在隔離環境中執行指令碼，與您的對話分開。中間結果保留在指令碼變數中，而不是進入 Claude 的上下文。

除非 Claude 從指令碼檔案的路徑啟動執行，否則 Claude Code 會將該次執行的指令碼寫入您工作階段目錄下 `~/.claude/projects/` 中的檔案。執行開始時 Claude 會收到該指令碼的路徑，因此您可以向它詢問。您可以開啟該檔案以讀取 Claude 編寫的協調指令碼，將其與先前執行的指令碼進行差異比較，或編輯它並要求 Claude 從編輯後的版本重新啟動。

Claude 只能從工作階段已允許讀取的指令碼檔案啟動工作流程。若要執行保存在工作目錄外的指令碼，請先使用 [`/add-dir`](https://code.claude.com/docs/zh-TW/permissions#working-directories) 或 [Read 允許規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)新增其目錄。

執行時期在執行進行時追蹤每個代理的結果，這是使執行在同一工作階段中[可恢復](#resume-after-a-pause)的原因。

### 扇出中的提示快取

同一執行中的代理可以讀取彼此的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#subagents-and-the-cache)。使用相同模型、努力等級、代理類型、工具、輸出架構和工作目錄執行的兩個代理會建立相同的工具和系統提示前綴，因此在匹配同級代理的回應開始後啟動的代理會在其第一個請求上讀取該同級代理的快取。

工作流程代理的請求不在主對話的[快取 TTL 時段](https://code.claude.com/docs/zh-TW/prompt-caching.md#which-ttl-each-request-gets)內，因此其快取預設保留五分鐘，包括在 Claude 訂閱上。若要將其保留一小時，請將 [`subagentPromptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#subagentpromptcachettl) 設定為 `1h`。API 以更高的費率計費 1 小時快取寫入。

當扇出同時啟動多個匹配的代理時，Claude Code 會保留除第一個外的所有代理，直到第一個代理的回應開始，然後一起釋放保留的代理，以便它們的第一個請求讀取共享前綴，而不是每個都未快取地處理它。Claude Code 將保留時間上限設定為 [`CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS`](https://code.claude.com/docs/zh-TW/env-vars) 毫秒，預設為 `5000`。將其設定為 `0` 以停用保留。

### 行為和限制

執行時期應用以下約束：

| 約束 | 為什麼 |
| :- | :- |
| 無中途使用者輸入 | 執行只會因代理權限提示和[使用量限制等待](#when-a-run-hits-your-usage-limit)而暫停。對於階段之間的簽核，將每個階段作為其自己的工作流程執行 |
| 無來自工作流程本身的直接檔案系統或 shell 存取 | 代理讀取、寫入和執行命令。指令碼協調代理 |
| 無模組載入：包含 `import()` 的指令碼在執行開始前會失敗 | 指令碼主體是純 JavaScript。將需要程式庫的工作放在代理的任務中 |
| 最多 16 個並行代理，在 Claude Code 可用 CPU 較少時更少，包括在 CPU 受限的容器內。若要變更限制，請將 [`CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 1 到 256 的值，這需要 Claude Code v2.1.269 或更新版本 | 限制本地資源使用 |
| 在扇出中，共享第一個代理提示快取前綴的代理預設在其後最多啟動 5 秒 | 除第一個外的所有代理都讀取[第一個代理快取的前綴](#prompt-caching-in-a-fan-out)，而不是每個都未快取地處理它 |
| 單一 `parallel()` 或 `pipeline()` 呼叫中最多 4,096 個項目：執行時期會以錯誤拒絕更長的清單 | 無聲上限會在不告知指令碼的情況下丟棄部分工作負載 |
| 每次執行 1,000 個代理 | 防止失控迴圈 |

## 管理執行

執行啟動後，您從 `/workflows` 檢視或通過展開輸入框下方任務面板中的進度線來管理它。

當您停止執行時，它會保留在任務面板中，而其任何代理的程序仍在執行。如果您再次停止它，Claude Code 會重新向這些程序發送信號。

### 暫停後恢復

從 `/workflows` 恢復暫停的執行，方法是選擇它並按 `p`。對於您停止的執行，要求 Claude 使用相同指令碼重新啟動工作流程。如果已停止執行中的代理尚未退出，Claude Code 會拒絕重新啟動，直到它們退出為止，因此這些代理的第二個副本無法與它們並行執行。

#### 哪些 agent 會再次執行

Claude Code 按 agent 啟動的順序重新執行該執行，每個 agent 要麼返回其已保存的結果，要麼再次執行：

* **已完成**：返回其已保存的結果。第一個提示與前次執行不同的代理（因為您編輯了指令碼或較早的代理返回了不同的內容）會再次執行，之後的每個代理也會執行，即使是已完成的代理。

  在 v2.1.305 之前，當您重新啟動未經編輯的指令碼，且其 `pipeline()` 項目或 `parallel()` 任務各自執行多個 agent 時，已完成的 agent 也可能再次執行。若要讓新的執行不再發生這些重新執行，請更新 Claude Code。
* **停止時仍在執行**：重新開始。停止整個執行不會將任何代理計為失敗。
* **失敗**：再次執行，指令碼在其之後啟動的每個 agent 也會執行，即使是已完成的 agent。透過在 [`/workflows`](#watch-the-run) 中選擇 agent 並按 `x` 來單獨停止一個 agent，會將其計為失敗。

最後一種情況意味著中間的失敗會重新執行已完成的工作。如果指令碼按該順序啟動 A、B、C 和 D，並且 B 失敗，重新啟動會從快取返回 A 並再次執行 B、C 和 D。

如果您將原本依序啟動 A、B、C 和 D 的指令碼編輯為依序啟動 A、C、B 和 D，那麼第二個啟動的 agent 現在是 C，而前次執行在此處啟動的是 B。重新啟動會從快取返回 A，並再次執行 C、B 和 D。

#### 離開工作階段後恢復

如果您在工作流程執行進行中將工作階段放到背景或退出 Claude Code，該執行不會自行繼續。只有當 Claude 以 `Workflow` 呼叫重新啟動它時，執行才會繼續，這會[從其已保存的結果重新執行該執行](#which-agents-run-again)。

* **您將工作階段放到背景，或選擇了 [`Move to background and exit`](https://code.claude.com/docs/zh-TW/agent-view#from-inside-a-session)**：如果您查看[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#what-carries-over-when-you-background)時執行尚未繼續，請在那裡要求 Claude 重新啟動工作流程。視您的[權限模式](#approve-the-plan-before-it-runs)而定，Claude Code 會先要求您核准重新啟動。如果該工作階段在 agent 檢視中顯示於 `Needs input` 之下，請[附加到該工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#attach-to-a-session)以回應核准提示。
* **背景工作階段中的重新啟動因 `nothing to resume` 而失敗**：要求 Claude 將工作流程作為新執行重新開始。如果 Claude 是從 `~/.claude/projects/` 以外的指令碼檔案路徑（例如您工作目錄中的檔案）啟動該執行，Claude 就無法在背景工作階段中重新啟動它。
* **您選擇了 `Exit and stop tasks`，或未提供 `Move to background and exit`**：執行已隨工作階段停止，Claude Code 會將執行的已保存結果保留在 `~/.claude/projects/` 中該工作階段的目錄下。請在您的 shell 中使用 `claude --resume` 恢復工作階段，然後要求 Claude 重新啟動工作流程。在全新的工作階段中，Claude 沒有較早的執行可重新啟動，會將工作流程重新開始。

在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，Claude Code 也會將執行的結果與工作階段的對話歷史記錄一起保存，當工作階段的 VM 被回收時，這些結果會保留。當您[重新開啟此類工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#environment-expired)並要求 Claude 重新啟動工作流程時，已完成的代理仍會返回其已保存的結果。

在本地和雲端工作階段中，當 Claude 重新啟動較早的執行並且 Claude Code 根本找不到該執行的已保存結果時，重新啟動會失敗並出現 `nothing to resume` 錯誤，而不是自動啟動執行。要求 Claude 將工作流程作為新執行啟動。

### 當執行達到您的使用限制時

當代理達到您的 claude.ai [使用限制](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset)時，執行會暫停而不是該代理失敗：達到限制的代理會等待重設，並且不會啟動新代理。限制重設後不久，等待中的代理會再次執行，執行會自動繼續。需要 Claude Code v2.1.271 或更新版本；在較早版本上，受影響的代理會失敗。

執行等待時，任務面板中的進度線和 [`/workflows`](#watch-the-run) 標題會顯示限制何時重設。

執行只在以下所有情況成立時暫停；當其中一個不成立時，受影響的代理會改為失敗：

* 工作階段是互動式的，並使用 claude.ai 訂閱登入。執行不會在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `claude -p` 或 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 暫停，在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，或在[遠端控制](https://code.claude.com/docs/zh-TW/remote-control.md)或[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)隊友工作階段中。
* [`autoContinueAtUsageLimit`](https://code.claude.com/docs/zh-TW/settings-reference#autocontinueatusagelimit) 已開啟，這是允許工作階段本身[等待使用限制重設](https://code.claude.com/docs/zh-TW/interactive-mode.md#wait-for-a-usage-limit-to-reset)的相同設定。如果您在等待期間關閉它，等待會結束，等待中的代理會失敗。
* 限制在 24 小時內重設。每週限制可能會更晚重設。
* 執行尚未已等待兩次。當它第三次達到限制時，代理會失敗。

### 當 agent 停滯並重新啟動時

若 agent 的輸出停止傳來達一定時間，該 agent 會以相同的提示詞重新開始。在 [`/workflows`](#watch-the-run) 中，其名稱會加上 `(retry 1)` 後綴，其詳細資訊會顯示 `attempt 2 (stalled)`。重新啟動是自動的，因此您不需要執行任何操作。

新的嘗試在啟動時不會帶有停滯嘗試的逐字稿。停滯嘗試已變更的檔案會維持變更，其花費的 token 也會保留在執行的總數中。停滯時間窗是 Claude Code 在結束該次嘗試之前等待 agent 輸出的時間長度。agent 等待其自身工具呼叫或等待[用量上限重設](#when-a-run-hits-your-usage-limit)所花費的時間，不會計入停滯時間窗。

一個 agent 最多重新啟動五次，包括您使用 `r` 要求的任何重新啟動。如果第六次嘗試也停滯，`agent()` 呼叫會失敗，錯誤的開頭會說明原因：

* `agent stalled on all 6 attempts`：每次嘗試都在整個時間窗內沒有輸出。如果 agent 的工作會讓它保持沉默這麼久，請延長時間窗
* `agent lost its reply on all 6 attempts`：每次嘗試的回應串流都變得沉默，而 Claude Code 放棄了等待。延長停滯時間窗沒有幫助，因為[串流閒置監控程式](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)會先結束回應，而 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 用於設定該監控程式的逾時
* `agent abandoned after 6 attempts`：各次嘗試以不同方式結束，錯誤會依序列出這些方式

若要在時間窗結束前給予 agent 更多時間產生輸出：

* **單一 agent**：在其 `agent()` 呼叫上傳入以毫秒為單位的 `stallMs`，例如 `agent(prompt, { stallMs: 1800000 })` 表示 30 分鐘
* **每個 agent**：設定 [`CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables)，這也適用於工作流程以外的 subagent

失敗後執行是否繼續，取決於您的指令碼如何呼叫該 agent：

* **在 [`parallel()` 或 `pipeline()`](#what-the-saved-script-looks-like) 內**：執行會繼續，並以 `null` 取代該 agent 的結果
* **直接 await**：執行會隨錯誤結束

若要再試一次，請要求 Claude 重新啟動工作流程。[暫停後恢復](#resume-after-a-pause)說明了哪些部分會再次執行。

### 成本

工作流程生成許多代理，因此單次執行可以使用比在對話中完成相同任務更多的令牌。執行計入您的方案使用量和速率限制。

為了在提交大型任務前評估支出，請先在小片段上執行工作流程：一個目錄而不是整個儲存庫，或一個狹隘的問題而不是廣泛的問題。`/workflows` 檢視顯示每個代理的令牌使用量，隨著執行進行，您可以隨時在那裡停止執行，通常不會丟失已完成的工作。[暫停後恢復](#resume-after-a-pause)涵蓋已停止的執行保留的內容。執行時間的[代理上限](#behavior-and-limits)限制單次執行可以生成多少個代理，這限制了失控指令碼的成本。要保持執行為較少的代理，請選擇 `small`[大小指南](#set-a-size-guideline)。

Claude Code 也會標記異常增長的執行。當工作流程排程超過 25 個代理，或其預計令牌總數超過 150 萬時，輸入框下方任務面板中的進度線會顯示 `Large workflow` 警告。警告指向您可以停止執行的 [`/workflows`](#watch-the-run)。

警告是建議性的：它不會暫停或限制執行。當您看到它時，有兩個設定會改變：

* 如果您自己選擇[大小指南](#set-a-size-guideline)，其代理計數會取代 25 個代理的閾值。內建預設指南將閾值保留在 25。
* 啟用[ultracode](#let-claude-decide-with-ultracode) 的工作階段不會顯示警告，因為啟用 ultracode 已經讓您選擇加入大型執行。

Claude Code 按照它用於子代理的相同[順序選擇每個工作流程代理的模型](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)。指令碼為階段命名的模型在該順序中計為每次調用模型。當沒有其他內容分配模型時，代理在您的工作階段模型上執行。

要控制模型成本：

* 在大型執行前檢查 `/model`，如果您通常為日常工作切換到較小的模型
* 當您描述任務時，要求 Claude 為不需要最強模型的階段使用較小的模型

當您組織的 [`availableModels` 允許清單](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection)封鎖指令碼為 agent 請求的模型時，該 agent 會改為在替代模型上執行，並遵循與 [subagent 相同的替代規則](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)。

### 設定大小指南

大小指南告訴 Claude 在編寫動態工作流程時應該針對多少個 agent。Claude Code 將指南作為建議而不是上限發送給 Claude，因此要求不同規模的提示詞仍會覆寫它。

每個值對應一個代理計數：

| 值 | Claude 目標的代理計數 |
| :- | :- |
| `unrestricted` | 無指南：Claude 根據任務調整工作流程大小 |
| `small` | 少於 5 個代理 |
| `medium` | 少於 10 個代理 |
| `large` | 少於 50 個代理 |

預設值為 `medium`，或當您使用 Claude Code v2.1.271 或更新版本登入 Pro 方案時為 `small`。在您選擇值之前，`/config` 列會將值標記為預設值，工作流程的 `Running in background` 列會指出生效的大小。

要變更指南，請在 `/config` 中為 Dynamic workflow size 設定選擇一個值，或執行 `/config workflowSizeGuideline=small`。您也可以在任何設定檔中設定 [`workflowSizeGuideline` 鍵](https://code.claude.com/docs/zh-TW/settings-reference#workflowsizeguideline)；該值優先於 `/config`，而當設定檔提供該值時，Claude Code 會隱藏 `/config` 列。

變更在下一個提示時生效。[執行時間代理上限](#behavior-and-limits)仍然適用，無論設定如何。

### 關閉工作流程

工作流程在 CLI、桌面應用程式、IDE 擴充功能、[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)與 `claude -p` 和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中可用。相同的禁用設定適用於每個表面。

要為自己關閉工作流程：

* 在 `/config` 中切換 Dynamic workflows 關閉。在工作階段中持續。
* 在 `~/.claude/settings.json` 中設定 `"disableWorkflows": true`。在工作階段中持續。
* 設定 `CLAUDE_CODE_DISABLE_WORKFLOWS=1`。在啟動時讀取，因此它適用於您設定它的任何位置。

要為整個組織關閉工作流程，在[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中設定 `"disableWorkflows": true`，或使用 [Claude Code 管理員設定](https://claude.ai/admin-settings/claude-code)頁面上的切換。

停用工作流程時：

* `/workflows`、工作流程命令和 `/workflow-authoring` skill 不可用
* `ultracode` 關鍵字不再觸發執行，**Ultracode** 切換從 `/effort` 中移除

已在進行中的執行會繼續進行。

關閉工作流程也會使 [ultracode](#let-claude-decide-with-ultracode) 不可用。沒有受管設定單獨排除 ultracode：無論它在何處[可用](https://code.claude.com/docs/zh-TW/model-config.md#when-ultracode-is-available)，使用者都可以使用 `/effort ultracode` 將其開啟。[努力上限](https://code.claude.com/docs/zh-TW/model-config.md#organization-effort-limits)會降低啟用 ultracode 的工作階段執行的努力等級，但不會關閉 ultracode。

## 相關資源

* [並行執行代理](https://code.claude.com/docs/zh-TW/agents.md)：比較子代理、代理檢視、代理團隊和工作流程
* [建立自訂子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)：工作流程協調的工作者原始類型
* [管理成本](https://code.claude.com/docs/zh-TW/costs.md)：多代理執行如何計入使用限制
