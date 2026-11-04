<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/checkpointing | lastmod: 2026-10-28 | section: Reference / Reference -->
> 來源：https://code.claude.com/docs/zh-TW/checkpointing（官方 zh-TW，lastmod 2026-10-28）｜分類：Reference › Reference｜EN 摘要：Track, rewind, and summarize Claude's edits and conversation to manage session state.

# Checkpointing

> 追蹤、回溯和總結 Claude 的編輯和對話以管理會話狀態。

Claude Code 會自動追蹤 Claude 在您工作時所做的檔案編輯，讓您可以快速撤銷變更並回溯到先前的狀態，以防任何事情出現偏差。

## 檢查點的運作方式

在您與 Claude 協作時，檢查點功能會在您送出每個開啟新回合的提示詞之前，自動擷取程式碼的狀態。

### 自動追蹤

Claude Code 會追蹤其檔案編輯工具所做的所有變更：

* 您送出的每個開啟新回合的提示詞都會建立一個新的檢查點
* Claude Code 會在一個工作階段中保留最近 100 個檢查點的檔案快照。捨棄較舊的檢查點時，會刪除任何剩餘檢查點都不再參照的快照檔案，但每個檔案的第一個快照除外，因為 VS Code 擴充功能會將其作為工作階段差異的基準。
* Claude Code 會將檢查點與對話一起儲存，因此在您恢復工作階段後，仍然可以執行 `/rewind`
* Claude Code 會在[保留期清理](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)中刪除工作階段的檔案快照，預設大約在該工作階段最後一次儲存快照的 30 天後進行。倒轉至快照已被刪除的檢查點時，可能會失敗並顯示 [`No files were restored`](https://code.claude.com/docs/zh-TW/errors#no-files-were-restored)。若要將快照保留更久，請設定 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays)。

### 倒轉與摘要

執行 `/rewind`，或在提示詞輸入框為空時按兩次 `Esc`，即可開啟倒轉選單。

> [!NOTE]
>
> 如果提示詞輸入框中有文字，按兩次 `Esc` 會清除文字，而不是開啟選單。被清除的文字會儲存至輸入歷史記錄中，因此在倒轉選單中完成操作後，可以按 `Up` 將其叫回。

倒轉選單會列出您在工作階段中送出的提示詞。選取您要操作的時間點，然後選擇一個動作：

* **Restore code and conversation**：將程式碼和對話都還原至該時間點
* **Restore conversation**：倒轉至該訊息，同時保留目前的程式碼
* **Restore code**：還原檔案變更，同時保留對話
* **Summarize from here**：將從此時間點之後的對話壓縮成摘要，以釋放上下文視窗空間
* **Summarize up to here**：將此時間點之前的對話壓縮成摘要，並完整保留之後的訊息
* **Never mind**：返回訊息清單，不做任何變更

只有在所選檢查點有可還原的已追蹤檔案變更時，才會出現這兩個程式碼還原選項。如果在該時間點之後沒有擷取到任何檔案編輯，選單只會提供 **Restore conversation**、摘要選項以及 **Never mind**。

還原對話或選擇 Summarize from here 後，所選訊息中的原始提示詞會被還原至輸入欄位，方便您重新送出或加以編輯。

選擇 Summarize up to here 會讓您停留在對話的結尾，且輸入框為空。無論使用哪一個摘要選項，對話中原本被壓縮訊息所在的位置都會出現一個 **Summarized conversation** 標記。

#### 若在下一個提示詞之前退出，被倒轉的訊息可能會再次出現

若要再次移除這些重新出現的訊息，請在該工作階段中執行 `/rewind` 並選取相同的提示詞，然後選擇 **Restore conversation**。在退出之前，請先向 Claude 送出一個提示詞，因為 Claude Code 會將倒轉後的對話與該提示詞一起儲存。您已還原的檔案會維持倒轉後的狀態。

#### 倒轉至已清除的對話之前

如果您稍早在同一個 Claude Code 程序中執行過 `/clear`，倒轉選單會在清單頂端顯示一個額外的項目，標示為 `/resume <session-id> (previous session)`。選取該項目即可恢復執行 `/clear` 之前使用中的對話。在您退出 Claude Code 或恢復其他工作階段之前，此項目都可使用。

#### 引導摘要內容

摘要不會變更磁碟上的檔案，且原始訊息會保留在工作階段逐字稿中，因此 Claude 仍可參考其中的細節。若要引導摘要的重點，請使用方向鍵反白某個 **Summarize** 選項，並在該列顯示 **add context (optional)** 的位置輸入指示，然後按 `Enter`。若使用數字鍵選取該選項，則會立即進行摘要，不附帶任何指示。

> [!NOTE]
>
> 摘要會讓您留在同一個工作階段中並壓縮上下文，類似於有針對性的 `/compact`。若要分支出去嘗試不同的做法，同時完整保留原始工作階段，請改用 [`/branch`](https://code.claude.com/docs/zh-TW/sessions#branch-a-session) 或 `claude --continue --fork-session`。

## 常見使用案例

Checkpoints 在以下情況下特別有用：

* **探索替代方案**：嘗試不同的實現方法，而不會失去起點
* **從錯誤中恢復**：快速撤銷引入錯誤或破壞功能的變更
* **迭代功能**：進行變化實驗，同時知道您可以回復到工作狀態
* **釋放上下文空間**：從中點開始總結冗長的除錯會話，保持初始指示完整

## 限制

### Bash 命令的變更不會被追蹤

一旦 Claude 在您的對話中使用其檔案編輯工具編輯過某個檔案，`/rewind` 就會復原 Bash 命令之後對該檔案所做的變更。僅由 Bash 命令變更的檔案不會被追蹤，並會保持原樣。若要還原該檔案，請使用版本控制，例如 Git。

在每個提示詞下方，rewind 選單會計算對 Claude 已編輯過之檔案的變更，無論這些變更由何者造成。若某個提示詞中有 shell 命令變更了此類檔案，該提示詞也會列出檔案變更。

### Subagent 的編輯不會被還原

[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 會使用 Claude 的檔案編輯工具進行編輯，但 Claude Code 通常不會在您工作階段的檢查點中擷取這些編輯。rewind 是否會還原這些編輯，取決於 subagent 的執行方式：

* **前景分支的 skill**：在前景執行的[具有 `context: fork` 的 skill](https://code.claude.com/docs/zh-TW/skills#run-skills-in-a-subagent) 會在您自己的回合中編輯您的工作樹，因此 rewind 會照常還原其編輯。設定 `background: false` 即可在前景執行分支；在少數情況下（[列於 skills 頁面](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)），無論此設定為何，都會在前景執行。
* **任何其他 subagent**：rewind 只會還原 Claude 在您的對話中已編輯過的檔案。subagent 對其他檔案的編輯會保留下來，因此請使用版本控制（例如 Git）來還原這些編輯。這包括在背景執行的分支 skill（預設行為），以及在背景執行的 [`/code-review --fix`](https://code.claude.com/docs/zh-TW/code-review-local)。

### 外部變更不會被追蹤

檢查點功能只會追蹤在目前工作階段中編輯過的檔案。您在 Claude Code 之外對檔案所做的手動變更，以及其他同時進行之工作階段的編輯，通常不會被擷取，除非它們剛好修改了與目前工作階段相同的檔案。

### 回合中途傳送的訊息不會建立檢查點

在 rewind 選單中，您[在 Claude 仍在工作時輸入](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)的訊息可能會被標示為 **No code restore**。被標示的訊息沒有自己的[檢查點](#how-checkpoints-work)。

若要復原 Claude 在該訊息之後所做的檔案編輯，請選取開始該回合的提示詞，並選擇 **Restore code** 或 **Restore code and conversation**。這會還原 Claude 在整個回合中所做的檔案編輯，包括您的訊息送達之前的編輯。

### 符號連結與硬連結路徑不會被還原

檢查點功能不會 rewind 符號連結或硬連結的檔案。當您從 `/rewind` 選單中選擇 **Restore code** 或 **Restore code and conversation** 時，Claude Code 會略過任何屬於符號連結或硬連結的追蹤路徑，並顯示 `Restored the code, but skipped N files` 警告。被略過的檔案會保留其目前內容。若要復原工作階段對其中某個檔案的變更，請要求 Claude 反轉該編輯，或自行編輯該檔案。由 dotfile 管理工具以符號連結放入您專案中的設定檔，以及由 pnpm 以硬連結放置到位的檔案，都屬於此類別。

若要查看還原時會略過哪些路徑，請在還原之前使用 `/debug` 開啟除錯日誌：位於 `~/.claude/debug/<session-id>.txt` 的除錯日誌會列出每個被略過的路徑。如需所有略過原因及復原步驟，請參閱[錯誤參考中的略過檔案項目](https://code.claude.com/docs/zh-TW/errors.md#restored-the-code-but-skipped-files)。

### 無法取代版本控制

檢查點是為了快速的工作階段層級復原而設計。若需要永久的版本歷史與協作，請繼續使用版本控制（例如 Git）來進行提交、分支及長期歷史管理。

## 另請參閱

* [Interactive mode](https://code.claude.com/docs/zh-TW/interactive-mode.md) - 快捷鍵和會話控制
* [Commands](https://code.claude.com/docs/zh-TW/commands.md) - 使用 `/rewind` 存取 checkpoints
* [CLI reference](https://code.claude.com/docs/zh-TW/cli-reference.md) - 命令列選項
