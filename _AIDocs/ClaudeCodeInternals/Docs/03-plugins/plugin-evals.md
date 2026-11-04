<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/plugin-evals | lastmod: 2026-10-14 | section: Plugins / Create plugins -->
> 來源：https://code.claude.com/docs/zh-TW/plugin-evals（官方 zh-TW，lastmod 2026-10-14）｜分類：Plugins › Create plugins｜EN 摘要：Write eval cases for your Claude Code plugin, run them with claude plugin eval, grade the results, compare against a no-plugin baseline, and gate CI on the score.

# 使用 evals 測試 plugins

> 為您的 Claude Code plugin 編寫 eval 案例，使用 claude plugin eval 執行它們，評分結果，與無 plugin 基準線進行比較，並在 CI 中根據分數進行把關。

`claude plugin eval` 針對一套測試案例執行您的 [plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md)，並對結果進行評分。每個案例都是一個真實的提示加上一個或多個評分器。評分器是對 Claude 產生的內容進行的通過/失敗檢查，例如對回覆的正規表達式、是否呼叫了特定工具，或由第二個模型判斷回覆的評分標準。

您不必手動編寫測試套件；`claude plugin eval init` 會詢問您有關 plugin 的問題，提議案例和評分器，嘗試它們，並編寫檔案。您也可以要求 Claude 從已開啟的工作階段中執行相同操作。

使用 evals 來：

* 測量您的 plugin 可靠地引導 Claude 達到正確結果的程度
* 在您變更 plugin 或新模型發佈時捕捉迴歸
* 查看與沒有 plugin 相比 plugin 的貢獻

本頁面適用於擁有可運作 plugin 並想測試其行為的 plugin 和 skill 作者，以及在 CI 中把關 plugin 變更的團隊。若要在 Claude Code 對話中反覆改進單一 skill，[skill-creator plugin](https://code.claude.com/docs/zh-TW/skills.md#run-evals-with-skill-creator) 會使用其自己的 `evals/evals.json` 格式執行類似的比較，且兩個工具都不會讀取另一個的案例檔案。若要建立 plugin，請參閱 [建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)；若要檢查 plugin 的檔案是否存在語法和架構錯誤而不是其行為，請使用 [`claude plugin validate`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#plugin-validate)。

> [!NOTE]
>
> 每次 eval 執行和每個評判評分器都是您帳戶上的真實模型呼叫，計入您的方案使用量或 API 帳單，因此請先檢查 [requirements](#requirements)。然後 [create your first eval suite](#create-your-first-eval-suite)，或如果您已經有一個，請前往 [Run evals in CI](#run-evals-in-ci)。

## Requirements

若要執行 plugin evals，您需要：

* Claude Code v2.1.269 或更新版本。執行 `claude --version` 檢查，執行 `claude update` 升級。
* Git 2.31 或更新版本（如果已安裝 git）。執行 `git --version` 檢查。使用較舊的 git，`claude plugin eval` [在執行任何案例之前停止](#git-is-too-old-for-claude-plugin-eval)。沒有 git，它會正常執行。
* 具有 `plugin.json` 或 `.claude-plugin/plugin.json` 資訊清單的 plugin 目錄，或 [skills-directory plugin](https://code.claude.com/docs/zh-TW/plugins/loading.md#plugins-shared-through-a-repository)。
* 與您的正常 Claude Code 工作階段相同的身分驗證和模型提供者。Eval 執行、評判評分器和 `claude plugin eval init` 使用您的憑證呼叫模型，因此它們計入您方案的用量上限或 API 帳單。當命令報告成本時，該數字是這些呼叫的 [list-price estimate](https://code.claude.com/docs/zh-TW/costs.md)。如果您在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上執行 Claude Code，請從匯出與正常工作階段相同提供者變數的 shell 執行測試套件，因為每次執行都會從該 shell 繼承這些變數，如 [`env` 欄位](#prompt-md-fields)所述。

## Eval 執行的運作方式

Eval 套件位於 plugin 內名為 `evals/` 的目錄中，其佈局如 [撰寫和精化案例](#write-and-refine-cases) 所示。每個案例都是其自己的子目錄，包含 [prompt](#set-run-limits-and-tools-in-prompt-md) 和一個或多個 [graders](#grade-the-result)。提示是使用您的 plugin 的人可能輸入的內容，例如其中一個 skills 應該處理的請求。

### 執行中發生的情況

對於案例的每次執行，Claude Code 啟動一個新的、[隔離](#how-runs-are-isolated) [非互動式工作階段](https://code.claude.com/docs/zh-TW/headless.md)，僅載入您的 plugin，發送提示，並讓 Claude 工作直到完成或達到案例的轉數或時間限制。然後每個評分器檢查最終回覆、完整文字記錄或 Claude 建立的檔案，並通過或失敗。

### 案例如何評分

非確定性代理的一次執行告訴您很少，所以每個案例預設執行三次。執行的分數是其通過的評分器的比例，如果您設定權重則加權，案例的分數是其執行的平均值。當案例的分數達到 [`--threshold`](#command-options)（預設為 1.0）時，案例通過。在模型呼叫中，套件大約進行案例 × 執行代理執行與 plugin，以及同樣多的 [no-plugin baseline](#the-no-plugin-baseline)，加上每個 `llm` 或 `baseline` 評分器每次執行三個短評判呼叫。

### No-plugin 基準線

高分本身並不能告訴您 plugin 是否有幫助，因為 Claude 可能在沒有它的情況下做得同樣好。為了區分兩者，每個案例的執行會在沒有載入 plugin 的情況下重複，您會獲得兩個分數：`WITH` 和 `W/OUT`。它們的差異 `Δ` 是 plugin 的貢獻。如果案例在有 plugin 和沒有 plugin 的情況下都得分 1.0，則不是 plugin 使其通過。

這兩組執行稱為 with-arm 和 without-arm；[與 no-plugin 基準線比較](#compare-against-a-no-plugin-baseline) 涵蓋哪些案例只執行 with-arm 以及評分器如何在兩個 arm 之間評分。

## 建立您的第一個 eval suite

本逐步解說為您自己的 plugin 編寫一個案例，執行它，並讀取結果。在開始之前，請確保您有：

* Claude Code v2.1.269 或更新版本以及其他 [requirements](#requirements)
* 在 plugin 根目錄開啟的終端機，即包含 `plugin.json` 或 `.claude-plugin/plugin.json` 的目錄
* plugin 中您想測試的一個 skill，以及使用者應該輸入的請求以觸發它

**1. Create the cases**

從 plugin 根目錄執行：

```bash theme={null}
claude plugin eval init
```

如果 Claude Code 還不信任此目錄，它首先會詢問 `Trust this plugin directory?`；回答 `y`。

然後開啟互動式 Claude Code 工作階段。Claude 讀取您的 plugin 並詢問您好的結果是什麼樣子，提議應該和不應該觸發 plugin 的提示詞，為每個設計評分器，試驗它們一次以檢查它們的行為，並在 `evals/` 下為每個提示詞編寫一個案例目錄，每個都以其提示詞命名。

當 Claude 告訴您套件已準備好時，使用 `/exit` 或 Ctrl+D 退出該工作階段以返回您的 shell。

如果您已經在 plugin 根目錄開啟了 Claude Code 工作階段，您可以改為要求 Claude 在該對話中執行 `claude plugin eval init`。Claude 執行命令，然後在該對話中詢問您相同的問題。

如果您寧願自己編寫案例以查看檔案包含的確切內容，請遵循 [Write a case manually](#write-a-case-manually) 並返回此處執行它。

**2. Run the suite**

回到 plugin 根目錄的 shell，執行 `evals/` 下的每個案例：

```bash theme={null}
claude plugin eval .
```

您已在步驟 1 中信任此目錄，因此執行立即開始。如果您改為手動編寫案例，執行首先會詢問 `Trust this plugin directory? [y/N]`；回答 `y`。[What a run can access](#security) 解釋了您同意的內容。

每個案例使用您的 plugin 執行三次，沒有它執行三次，因此一個案例是六次執行。隨著每次執行完成，進度行會列印，顯示該執行的分數和每個評分器的判決。

**3. Read the summary**

當套件完成時，您會看到摘要表，然後是報告的位置：

```text theme={null}
CASE        WITH  W/OUT Δ      RUNS COST    NOTES
first-case  1.00  0.33  +0.67  6    $0.41

1 case(s) · mean Δ +0.67 · 74s · $0.41
Report: /Users/you/my-plugin/evals/results/2026-09-10T17-02-11-482Z/report.html
Published: https://claude.ai/... · keep local next time with --no-publish
```

`WITH` 是案例在載入您的 plugin 時的分數，`W/OUT` 是沒有它時的分數，正 `Δ` 表示 plugin 提高了分數。`COST` 是模型呼叫的 list-price estimate，`NOTES` 顯示最高權重失敗評分器的解釋或執行的錯誤，來自 with-arm。

**4. Open the report and iterate**

開啟 `Published:` URL 或當沒有 `Published:` 行出現時開啟 `Report:` 路徑，以查看每個評分器對每次執行的判決和解釋，以及對於 `llm` 評分器的評判投票和它判斷的摘錄。`Published:` 行僅在您的帳戶可以 [publish reports](#html-report) 時出現。

最常見的第一個發現是 `Δ` 接近零，案例的 `tool_used: Skill` 評分器失敗，這意味著 Claude 在自然措辭上沒有選擇您的 skill。調整 skill 的 [`description`](https://code.claude.com/docs/zh-TW/skills#frontmatter-reference)，再次執行 `claude plugin eval .`，並進行比較。

若要以較少的執行次數迭代單個案例，執行單個 arm 一次。單次執行是有噪音的，因此在信任任何變更之前，請在預設三次執行時確認任何變更。使用一個 arm，表格顯示 `SCORE` 和 `PASS%` 列而不是 `WITH`、`W/OUT` 和 `Δ`：

```bash theme={null}
claude plugin eval . --case <case-name> --runs 1 --ablation none
```

將 `<case-name>` 替換為 `evals/` 下的目錄名稱之一。

## 撰寫和改進案例

`claude plugin eval init` 撰寫的案例是純文字檔案，您可以開啟、變更和新增。案例是外掛程式 eval 目錄下的目錄，包含 `prompt.md`、`case.yaml` 或兩者。每個案例至少要有一個評分器，作為 `graders/<name>.md` 檔案或 `case.yaml` 中的 `graders:` 項目，因為沒有評分器的案例無法載入。若要分組案例，請將它們巢狀放在不是案例本身的目錄下；案例目錄內的任何內容（例如 `graders/` 和 fixture 檔案）都屬於該案例。

這是 `claude plugin eval init` 撰寫的配置，也是用於新套件的配置。[eval 套件參考](#eval-suite-reference)包含完整的樹狀結構，包括 mocks 和結果：

```text theme={null}
my-plugin/
├── .claude-plugin/plugin.json
├── skills/...
└── evals/
    ├── first-case/
    │   ├── prompt.md          # frontmatter: case fields; body: the prompt
    │   ├── graders/
    │   │   ├── criteria.md    # frontmatter: type + options; body: rubric or pattern
    │   │   └── skill-fired.md
    │   └── case.yaml          # optional: only for context.* fields
    ├── ignores-unrelated-request/
    │   └── ...
    └── results/               # written by each run; add to .gitignore
```

### 手動撰寫案例

讓 Claude 使用 `claude plugin eval init` 撰寫案例是建議的方式。若要自己撰寫，請從空白範本開始。下列命令會撰寫一個名為 `first-case` 的案例，包含預留位置 `prompt.md` 和一個預留位置 grader，且不執行任何內容：

```bash theme={null}
claude plugin eval init --bare first-case
```

```text theme={null}
evals/first-case/
├── prompt.md            # the prompt sent to Claude, plus run limits
└── graders/
    └── criteria.md      # one grader: how to score the result
```

在 `prompt.md` 中，您撰寫 Claude 在每次執行時收到的訊息，並在 frontmatter 中設定執行的限制和案例可能使用的工具。開啟 `evals/first-case/prompt.md` 並將預留位置本文替換為您某個 skill 應處理的請求，用使用者會輸入的方式表述，而不是直接命名該 skill。此範例適用於起草提交訊息的 skill；請使用您自己的請求：

```markdown theme={null}
---
max_turns: 10
allowed_tools: [Read, Glob, Grep, Skill]
---

Write me a commit message for this change: I renamed getUser to fetchUser and updated the three call sites.
```

每次執行都在空的工作目錄中開始，所以將任務需要的內容放在提示詞本身中，或[先設定工作區](#add-setup-or-history-with-case-yaml)。

[frontmatter 欄位的完整清單](#prompt-md-fields)涵蓋模型、逾時、標籤和環境變數。

`graders/` 下的每個檔案都是執行後套用的一項檢查。開啟 `evals/first-case/graders/criteria.md` 並將預留位置替換為評判模型的評分標準，寫成具體的 PASS 和 FAIL 條件：

```markdown theme={null}
---
type: llm
---

PASS if <what a correct response contains>.
FAIL if <what a wrong or missing response looks like>.
```

然後新增第二個 grader，檢查您的 skill 是否是產生答案的原因。建立 `evals/first-case/graders/skill-fired.md`，將 `your-skill-name` 替換為 `skills/` 下您 skill 的目錄名稱，這是 Claude 呼叫它的名稱：

```markdown theme={null}
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?your-skill-name"'
---
```

當 Claude 在執行期間至少呼叫過該 skill 一次時，這會通過，包括其命名空間 `plugin-name:skill-name` 形式。

[Grader 類型](#grader-types)列出其他可用的檢查，例如符合正規表達式或確認檔案已建立。

兩個檔案都儲存後，按照[快速入門](#create-your-first-eval-suite)的方式執行案例，從外掛程式根目錄執行 `claude plugin eval .`。

### 在 prompt.md 中設定執行限制和工具

在 `prompt.md` frontmatter 中設定案例的 `max_turns`、`timeout_seconds`、`model`、`tags` 和它可能使用的 `allowed_tools`；[prompt.md frontmatter](#prompt-md-fields) 參考列出每個欄位及其預設值。

Claude 會完全按照您撰寫的方式接收本文。其中的 `@path` 提及不會展開為檔案附件，所以如果 Claude 需要讀取檔案，請在 `allowed_tools` 中授予工具。

### 選擇和加權 graders

Grader 的 frontmatter 設定其 `type`，以及可選的 `weight` 使其計入執行分數的更多部分，以及控制如何針對基準線評分的 [`arm`](#compare-against-a-no-plugin-baseline)。在六種類型中，`regex`、`tool_used`、`tool_order` 和 `file_exists` 是從逐字稿和檔案計算的，不需要成本，而 `llm` 和 `baseline` 呼叫評判模型並增加執行成本。

沒有自訂程式碼 graders。

[Grader 類型](#grader-types)列出每種類型的選項和通過條件，[grader 可以查看的內容](#what-a-grader-can-look-at)列出 `target` 和 `focus` 接受的值。

`llm` 和 `baseline` graders 的評判者預設是 Claude Code 用於背景任務的模型。傳遞 `--judge-model sonnet` 或完整模型 ID 以自行選擇評判者。

#### 選擇提供穩定訊號的 graders

`llm` grader 要求模型提供判決，所以其答案可能在執行之間有所不同，且文字越長差異越大。這些習慣可以讓套件的分數穩定到足以信任：

* 對於長輸出（例如產生的檔案），使用檔案內容上的 `regex` grader 進行評分，它每次都以相同的方式檢查整個檔案。將 `llm` graders 保留用於短輸出，評分標準寫成具體的 PASS 和 FAIL 條件。
* 為每個案例提供一個 grader 來評分結果（例如最終訊息或產生的檔案），以及一個來評分 Claude 產生結果所採取的步驟（例如 `tool_used` 或 `tool_order`）。它們一起告訴您答案是否正確以及您的外掛程式是否產生了它。
* 如果案例的 `tool_used: Skill` grader 通過但 `Δ` 為負，請懷疑評判者而不是外掛程式。小型評判模型可能會因為格式與評分標準描述的不同而將正確答案標記為錯誤。使用 `--judge-model sonnet` 重新執行，並收緊評分標準，使格式不會決定判決。
* 若要檢查建置或測試在執行內通過，請讓提示詞要求 Claude 執行它並將結果寫入檔案，評分該檔案，並使用 `tool_used` grader（其 `input_match` 命名該命令）判斷命令已執行。

### 針對無外掛程式基準線評分

當外掛程式在測試中時，案例通常在兩個 arm 中執行。with-arm 是使用外掛程式載入的執行，without-arm 是沒有外掛程式的相同數量執行。摘要和報告顯示兩個分數和 `Δ`（with-arm 分數減去 without-arm 分數）。

在這些情況下，案例只執行 with-arm，所以它沒有 `W/OUT` 分數或 `Δ`：

* **您傳遞 `--ablation none`**：每個案例執行一個 arm，當您不需要比較時（例如在迭代 graders 時）成本減半。
* **案例繼續逐字稿且目標是路徑**：使用[目標](#choose-what-to-evaluate)（例如 `.` 而不是已安裝外掛程式的名稱），[`context.history_file`](#add-setup-or-history-with-case-yaml) 案例預設執行一個 arm，假設記錄的對話已反映外掛程式。執行會在 stderr 上列印 `single-arm (no Δ)` 通知，命名這些案例。若要比較繼續的回合在使用和不使用外掛程式時的差異，請傳遞 `--ablation with-without`。
* **找不到案例的外掛程式**：當目標是路徑時，Claude Code 無法定位的案例外掛程式也預設執行一個 arm。請參閱[基準線 arm 顯示無外掛程式](#the-baseline-arm-shows-no-plugin-or-delta-is-zero)以修正它。

在雙 arm 執行中，某些 graders 會以 `scored: false` 報告。像「skill 已呼叫」這樣的檢查在沒有外掛程式的情況下永遠無法通過，所以計算它會將 without-arm 推向零並誇大 `Δ`。為了保持兩個 arm 可比較，Claude Code 在兩個 arm 中排除此類 graders 的分數，並在 with-arm 中將其報告為僅通過/失敗指標。這包括：

* 每個 `tool` 為 `Skill` 的 `tool_used` grader
* 每個 `regex` grader 具有 `target: mock_calls` 和每個 `llm` grader 具有 `focus: mock_calls`，當案例中的每個[模擬伺服器](#mock-mcp-servers)都是您的外掛程式宣告的
* 任何您標記為 `arm: with-only` 的 grader

三個設定會改變該排除：

* **每個 grader 都被排除**：如果案例中的每個 grader 都在排除集合中，它們會改為正常評分，因為沒有其他內容可評分。
* **`arm: both`**：在 grader 上設定 `arm: both` 以無論如何在兩個 arm 中評分，這是您想要的「不得呼叫 skill」檢查，具有 `min: 0` 和 `max: 0`。
* **`--ablation none`**：在 `--ablation none` 下，沒有任何內容被排除，所以相同的套件在兩種模式中可能產生不同的絕對分數。

### 使用不同的 eval 目錄

如果 `evals/` 已被另一個工具佔用，請將套件保留在不同的目錄中。您可以在外掛程式的 `plugin.json` 中記錄該目錄，以便每次執行和每個協作者都使用它，或在命令列上傳遞它以進行單次執行：

* **在 `plugin.json` 中**：新增 `"experimental": { "evals": "quality/evals" }`。
* **在命令列上**：將 `--eval-dir quality/evals` 傳遞給 `claude plugin eval` 和 `claude plugin eval init`。

如果同時設定兩者，則使用旗標的目錄。給出相對路徑，包含純目錄名稱，例如 `qa` 或 `quality/evals`。絕對路徑或包含 `..` 的路徑不被接受：作為旗標值時會出現錯誤，而無法使用的資訊清單值會列印 `Warning:` 行，執行會改用 `evals/`。案例、結果和 `init` 輸出都會移至該目錄。

## 設定 fixtures 和 mocks

案例可能需要的不僅僅是提示：工作區中的檔案或 git 儲存庫、要繼續的早期對話，或您的 plugin 與之交談的 MCP 伺服器的答案。每個都在案例旁邊設定，以便執行保持可重複。

### Seed the workspace or conversation

每次執行都在空工作區中開始。當案例需要的不僅僅是提示時，在 `prompt.md` 旁邊新增 `case.yaml`，其中包含 `context` 區塊：

* **Fixture 檔案或 git 儲存庫**：在案例目錄中編寫 Bash 指令碼並在 `context.scaffold_script` 中命名它。指令碼以您的身份在代理沙箱外執行，僅當您傳遞 `--scaffold` 時，因此僅對您或您的組織編寫的套件傳遞該標誌。
* **要繼續的早期對話**：將文字記錄保存為 `.jsonl` 檔案並在 `context.history_file` 中命名它，案例的提示變成下一個使用者轉數。當目標是路徑時，這樣的案例預設會[不與無 plugin 基準進行比較](#compare-against-a-no-plugin-baseline)。
* **Claude 在執行期間可以讀取的 Fixture 目錄**：在 `context.add_dirs` 中列出它們。

`case.yaml` 也需要 `schema_version: "1.1"` 和 `name`；[case.yaml fields](#case-yaml-fields) 參考有完整列表。

此 `case.yaml` 從指令碼播種工作區並讓 Claude 從 `resources/` 目錄讀取 fixtures：

```yaml theme={null}
schema_version: "1.1"
name: changelog-from-diff
tags: [smoke]
context:
  scaffold_script: fixture.sh
  add_dirs: [resources]
```

scaffold 指令碼在空工作區中開始，具有小型固定環境：您的 shell 的 `PATH`、`HOME` 設定為執行的臨時主目錄、`TMPDIR` 和一些常數，例如 `TERM=dumb`。您的 shell 中沒有其他內容到達它，案例的 `EVAL_*` 變數也不會。如果指令碼以非零值退出或執行時間超過 120 秒，該執行的分數為 0，並出現 `scaffold failed` 錯誤。僅將指令碼用於檔案和 git 狀態，因為它編寫的專案設定[未被載入](#how-runs-are-isolated)。

### Mock MCP servers

您可以評估 plugin，其 skills 呼叫 MCP 工具，而無需它們後面的真實服務。在 `evals/mocks/<server>/<tool>.md` 下為整個套件放置一個 Markdown 檔案，或在案例自己的 `mocks/` 目錄下為一個案例，其中 `<server>` 是您的 plugin 的 [MCP configuration](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers) 中伺服器的名稱。

執行永遠不會啟動您的 plugin 的真實 MCP 伺服器，除非您要求。Claude Code 在每個伺服器自己的名稱下註冊替代伺服器。具有 mock 檔案的工具從它回答，並且無需 `--allow-tools` 授予即可允許，具有無 mock 檔案的工具對 Claude 不可用。完全沒有 mocks 的伺服器在案例的 `mocked:` 進度行中顯示為 `plugin_<plugin>_<server>[not started: no mock]`。

檔案的主體是工具返回給 Claude 的內容。此 mock 代替名為 `tracker` 的伺服器上的 `create_issue` 工具，檢查 Claude 發送的輸入，並回顯標題。將其保存為 `evals/mocks/tracker/create_issue.md`：

```markdown theme={null}
---
expect:
  title: string
  priority: [low, medium, high]
---

Created issue #4821: {{input.title}}
```

Mock 檔案的主體和 frontmatter 接受這些選項：

* **替換**：使用 `{{input.<field>}}` 從呼叫的輸入插入欄位，使用 `{{file:fixtures/{input.<field>}.json}}` 插入 mock 旁邊的 fixture 檔案的內容。
* **`expect:`**：`expect:` 區塊保護輸入。如果呼叫違反它，執行會中止，分數為 0，並記錄原因，因此案例可以斷言您的 plugin 要求伺服器執行的操作。
* **`error: true`**：設定 `error: true` 以改為將主體作為工具錯誤返回。
* **`type: agent`**：設定 `type: agent` 讓評判模型依據主體中的指令扮演伺服器回應。對 agent mocks 的呼叫共用一個[每次執行的預算](#mock-call-budget-exceeded)，為案例 `max_turns` 的四倍，超過預算的呼叫會中止執行，分數為 0。

[mock file reference](#mock-files) 列出每個鍵和 `_server.md` 和 `_tools.json` 檔案。

若要評分呼叫本身，請將評分器指向 `target: mock_calls`。

若要改為針對 plugin 的真實 MCP 伺服器執行，請傳遞以下標誌之一。無論哪種方式，這些程序都以您的身份在執行沙箱外執行，其工具需要 [`--allow-tools` 授予](#grant-tools)：

* **`--allow-real-servers`**：為您未 mock 的每個伺服器啟動真實程序，並繼續從其檔案回答 mocked 工具
* **`--mocks off`**：完全忽略 `mocks/` 並啟動 plugin 宣告的每個伺服器

#### Replay agent mock answers

`type: agent` mock 使用 [`--judge-model`](#command-options) 呼叫回答，因此其輸出在執行之間變化，如果您變更評判者則會改變。當執行完成而沒有錯誤或中止時，Claude Code 在結果目錄中的 `mock-recordings/` 下保存代理 mock 給出的每個答案。

開啟那裡的 `ADOPT.txt` 以查看每個記錄和 `.replay/<server>/` 目錄以複製到，在產生它的 mock 旁邊。複製記錄後，稍後執行會從它回答相同呼叫，沒有模型呼叫。將 `mocks/.replay/` 與 `mocks/` 的其餘部分一起提交，以便 CI 執行可重複。

## 執行評估

一旦建立了測試套件，`claude plugin eval` 就會執行它。您可以使用 target 引數選擇要執行哪個外掛程式和案例，使用 `--allow-tools` 授予案例所需的任何工具（超出唯讀集合），並使用其他選項控制執行次數、模型、成本和輸出。

### 選擇要評估的內容

大多數情況下，您會從外掛程式根目錄執行 `claude plugin eval .`，這會執行測試套件中的每個案例，並載入您所在的外掛程式。若要執行單一案例檔案，或評估您安裝的外掛程式而非您正在開發的外掛程式，請傳遞不同的 target：

| Target | 執行的內容 |
| :- | :- |
| 外掛程式的根目錄，例如 `.` | 其 eval 目錄下的每個案例，並載入該外掛程式 |
| 單一 `prompt.md` 或 `case.yaml` 檔案 | 該案例，並載入其所在的外掛程式 |
| 已安裝的外掛程式（按名稱），`name` 或 `name@marketplace` | 該外掛程式及其 eval 目錄中的案例，[就地讀取或從已安裝的副本讀取](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins)。結果寫入您目前目錄下的 `./evals/results/`，或使用 `--eval-dir` 時寫入 `./<dir>/results/` |
| `name@skills-dir` | 相同，適用於[技能目錄外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#plugins-shared-through-a-repository) |
| 省略 | 目前目錄作為路徑 |

新增 `--case <glob>` 以按案例名稱篩選，並新增 `--tag <tag>` 以保留具有任何給定標籤的案例。

將 target 放在 `--tag`、`--allow-tools` 和 `--json` 之前。前兩個採用清單，`--json` 採用選用路徑，因此它們各自讀取後面的 target 作為其自己的值。

### 授予工具

執行永遠不會停止以要求許可。需要您未授予的授權的內建工具（例如 `Bash`、`Write`、`Edit`、`WebFetch` 和 `WebSearch`）會從工作階段中移除，因此 Claude 根本無法呼叫它們。

執行只允許案例在 `allowed_tools` 中列出的唯讀工具，來自 `Read`、`Glob`、`Grep`、`NotebookRead`、`Skill`、`AskUserQuestion`、`Agent`、`TodoWrite` 和工作工具 `TaskCreate`、`TaskGet`、`TaskList`、`TaskUpdate` 和 `TaskStop`，加上您使用 `--allow-tools` 授予的任何工具。該授權適用於執行中的每個案例。若要讓案例使用 `Bash`、`Write`、`Edit`、`WebFetch` 或 `WebSearch`，請自行授予它們：

```bash theme={null}
claude plugin eval . --allow-tools Write Edit "Bash(npm test *)"
```

當案例要求您未授予的工具時，進度輸出會將其列為 `not granted`。[模擬](#mock-mcp-servers) MCP 伺服器上的工具不需要授權。真實外掛程式 MCP 伺服器上的工具需要伺服器啟動（使用 `--allow-real-servers` 或 `--mocks off`）和按名稱授權，例如 `--allow-tools "mcp__plugin_my-plugin_github__*"`；外掛程式的 MCP 工具命名為 `mcp__plugin_<plugin>_<server>__<tool>`。

當您以任何形式授予 `Bash` 時，每個命令都會在 Claude Code 的 [OS 層級沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)下執行。寫入限制在執行的工作區、您的主目錄和 Claude Code 設定無法讀取，網路存取限制在您使用 `--allow-tools "WebFetch(domain:example.com)"` 授予的網域。如果您在沒有沙箱後端的機器上授予 Bash 或 PowerShell，Claude Code 會拒絕每次執行，而不是無限制地執行它，案例會顯示執行錯誤，通常得分為 0。原生 Windows 沒有後端，因此在 WSL2 下執行授予 shell 的測試套件；在 Linux 上，請先安裝 `bubblewrap` 和 `socat`。請參閱[沙箱先決條件](https://code.claude.com/docs/zh-TW/sandboxing.md)。

### 命令選項

此表涵蓋執行次數、模型、評分、成本、工具授權、模擬和輸出的選項。執行 `claude plugin eval --help` 以取得完整清單，其中也包括 `--case`、`--tag`、`--eval-dir`、`--no-scaffold`、`--report` 和 `--verbose`。

| 選項 | 預設值 | 效果 |
| :- | :- | :- |
| `--runs <n>` | 每個案例的 `runs`，否則 3 | 每個案例每個分支的執行次數 |
| `-j`, `--concurrency <n>` | `1` | 一次最多執行這麼多個代理執行，從 1 到 8。它們共享您帳戶的速率限制，因此這會縮短實際時間，而不是將吞吐量提高到超過該限制。結果保持案例順序 |
| `--model <model>` | 每個案例的 `model`，否則 `ANTHROPIC_MODEL`（如果已設定），否則 Claude Code 的預設值 | 受測代理的模型。在 CI 中固定它，以便模型推出不會被誤認為是外掛程式迴歸 |
| `--judge-model <model>` | 用於[背景任務](#grade-the-result)的模型 | `llm` 和 `baseline` 評分器的模型 |
| `--ablation <mode>` | 按案例決定；請參閱[針對無外掛程式基線進行比較](#compare-against-a-no-plugin-baseline) | 是否也執行每個案例而不使用外掛程式來測量它增加的內容。`none` 執行一個分支；`with-without` 新增無外掛程式基線 |
| `--threshold <0..1>` | `1.0` | 當案例的 with 分支得分至少達到此值時，案例通過。任何低於此值的案例都會使命令以 1 結束 |
| `--max-cost-usd <usd>` | 無上限 | 執行的列表價格成本估計上限，不是計畫使用量上限。在每次執行開始前檢查。一旦花費，不會進一步開始任何內容；已經開始的執行會完成，因此花費可能會因這些執行而超過上限。如果有任何執行未開始，命令會以 2 結束並返回部分結果 |
| `--allow-tools <tools...>` | 無 | 授予超出唯讀集合的工具。請參閱[授予工具](#grant-tools) |
| `--scaffold` | 關閉 | 執行每個案例的 [`scaffold_script`](#add-setup-or-history-with-case-yaml) |
| `--trust-plugin` | 關閉 | 跳過您會自行執行其程式碼和測試套件的外掛程式的首次執行信任提示。在 CI 中傳遞它，以便工作永遠不會被提示拒絕或留在等待。請參閱[執行可以存取的內容](#security) |
| `--mocks <mode>` | `record` | `record` 從[模擬](#mock-mcp-servers)回答 MCP 工具呼叫，不啟動外掛程式的真實伺服器，並儲存代理模擬答案以供重播。`off` 忽略模擬並啟動外掛程式的真實 MCP 伺服器 |
| `--allow-real-servers` | 關閉 | 使用 `--mocks record`，也為沒有模擬的伺服器啟動外掛程式的真實 MCP 伺服器 |
| `--json [path]` | 關閉 | 將[結果文件](#json-result)列印到標準輸出，或將其寫入以 `.json` 結尾的路徑。執行是安靜的：沒有進度行或摘要表 |
| `--output-dir <dir>` | `<eval dir>/results/<timestamp>/` | `aggregate-result.json` 和 `report.html` 的位置 |
| `--no-publish` | | 保持 HTML 報告本機。請參閱 [HTML 報告](#html-report) |
| `--publish-report` | | 發佈報告，即使它在預設情況下會保持本機，例如 Claude Code 工作階段啟動的執行 |
| `--keep-temp` | 關閉 | 保留每次執行的沙箱目錄並列印其路徑，以便偵錯 Claude 產生的內容 |

### 在 CI 中執行評估

在您的 CI 工作中，使用 `--json` 執行測試套件以寫入結果以供存檔，並根據結束代碼使建置失敗。傳遞 `--trust-plugin` 以便工作永遠不會在[首次執行信任提示](#security)處等待，固定兩個模型以便得分在一段時間內可比較，保持報告本機，並設定成本上限作為上限：

```bash theme={null}
claude plugin eval . \
  --trust-plugin \
  --json results.json \
  --threshold 0.8 \
  --model claude-sonnet-5 \
  --judge-model claude-haiku-4-5 \
  --no-publish \
  --max-cost-usd 20
```

工作的結束代碼告訴您發生了什麼：

| 結束代碼 | 含義 |
| :- | :- |
| 0 | 測試套件通過：每個案例的得分都在或高於 `--threshold`，且沒有其他原因導致執行失敗 |
| 1 | 案例得分低於閾值、案例檔案無法載入、找不到案例、無法啟動執行，或執行[因 API 錯誤而結束](#runs-ended-on-an-api-error)。當外掛程式目錄不受信任且未傳遞 `--trust-plugin`、選項無效，或無法寫入 `--json` 結果時，也會傳回此代碼 |
| 2 | 部分執行：達到 `--max-cost-usd` 上限，或您的認證在首次執行前或首次執行時被拒絕。`results.json` 仍會以 `partial: true` 和原因寫入 |
| 130 | 已中斷。部分結果已寫入 |
| 143 | 已終止，例如由 CI 逾時 |

with-minus-without 差異會被報告，但永遠不會改變結束代碼，寫入或發佈 HTML 報告的問題也不會改變結束代碼。

若要查看案例得分低的原因，請在本機執行它而不使用 `--json`，以便列印每次執行的進度和評分器行。

CI 執行器還需要以下內容：

* **安裝和憑證**：CI 執行器需要 Claude Code 安裝和[環境中的憑證](https://code.claude.com/docs/zh-TW/authentication.md)，例如 `ANTHROPIC_API_KEY` 或您雲端供應商的變數。
* **信任**：沒有 `--trust-plugin`，其簽出目錄 Claude Code 尚未信任的工作需要[首次執行信任提示](#trust-the-plugin-directory)，無法詢問的執行會被拒絕，結束代碼為 1。
* **CI 中的 `init`**：`claude plugin eval init` 需要終端機來詢問您的問題；在 CI 中，執行 `claude plugin eval init --bare <name>` 以取得空白範本。

若要保持成本可預測，只為不呼叫評判的評分器提供快速的每次變更測試套件，在您不需要 `Δ` 的地方使用 `--ablation none`，並將 `partial: true` 文件和具有 `skippedPaidGraders` 的執行排除在您繪製的任何趨勢之外。

## 讀取結果

每次執行至少一個案例會在 eval 目錄內寫入 `results/<timestamp>/` 目錄，包含 `aggregate-result.json` 和 `report.html`。對於 plugin 下的路徑目標；對於您命名的 plugin，它在您的目前目錄下，如 [target table](#choose-what-to-evaluate) 所示。摘要表、JSON 和報告都呈現相同的結果資料。

### HTML report

`report.html` 是一個單一的自包含檔案，不進行外部請求，因此您可以將其附加到 CI 工作或從磁碟開啟它。這個範例是使用 `--threshold 0.8` 執行三案例套件的報告頂部；顯示的成本是列表價格估計，會因模型和案例數量而異：

![eval 報告的頂部：一條判決行讀取「Plugin effect: +33.3 pts vs baseline, improved 2, flat 1, regressed 0 of 3 cases」，五個摘要磚塊分別用於套件分數、消融差異、基準分數、通過閾值的案例和完美執行，然後是第一個案例及其差異、分數條和一次執行，其兩個評分器都顯示通過](https://mintcdn.com/claude-code/qq7LHDi_F0aeFHgk/images/plugin-eval-report.png?fit=max\&auto=format\&n=qq7LHDi_F0aeFHgk\&q=85\&s=106eb6e6a70a6565f891ea3a4564f87d)

從上到下讀取：

* **判決行和磚塊**回答 plugin 是否在整個套件中有幫助。套件分數是每個案例 with-plugin 分數的平均值，Ablation Δ 是該分數高於或低於基準分數的距離，Cases 計算有多少個達到閾值。Perfect runs 是 with-plugin 執行的比例，其中每個評分器都通過。
* **每個案例卡**顯示案例自己的 `Δ` 和 with-plugin 分數，在閾值處有一個刻度。`Δ` 為負的案例在左邊緣獲得紅色，因此當您捲動時迴歸會突出顯示。
* **在案例內**，with-plugin 執行首先出現，基準執行之後。每次執行列出其評分器及通過或失敗晶片。失敗的評分器已經展開並附帶其解釋，`llm` 評分器也顯示法官的投票和它被顯示的證據，這是您發現執行分數低原因的地方。不計入分數的評分器，例如 `tool_used: Skill`，帶有 `plugin-fired indicator` 徽章。
* **Prompt 和 Graders**，在執行下方，顯示案例的 prompt 和每個評分器的評分標準或模式，因此閱讀報告而不查看套件的人可以看到被要求的內容和什麼被視為良好。

如果您使用 claude.ai 訂閱登入並且 [artifacts](https://code.claude.com/docs/zh-TW/artifacts.md) 可用於您的帳戶，Claude Code 也會將報告發佈為私人 artifact 並列印 `Published: <url>`。傳遞 `--no-publish` 以保持本地。如果沒有 `Published:` 行出現，例如使用 API 金鑰驗證，本地檔案是報告。

Claude Code 工作階段啟動的執行，例如當您要求 Claude 為您執行套件時，也保持本地，其 `Report:` 行說 `kept local`。將 `--publish-report` 新增到該命令以發佈它。

### JSON result

`aggregate-result.json` 和 `--json` 輸出是版本化文件，具有 `schemaVersion: 1` 供 CI 指令碼解析。欄位名稱是 camelCase，新欄位在不重新命名現有欄位的情況下新增，因此編寫您的指令碼以忽略它不識別的欄位。

這些是把關指令碼通常讀取的欄位。文件還包含套件設定、每個評分器定義和每次執行評分器結果及解釋和證據：

| Field | Meaning |
| :- | :- |
| `partial`, `partialReason` | `true` with `cost_ceiling`, `interrupted`, or `auth_failed` when the suite didn't finish. Leave partial results out of trend charts |
| `aggregates.overallScore` | Mean case score across the suite |
| `aggregates.casesPassed`, `aggregates.casesTotal` | Cases at or above `--threshold`, and the total |
| `aggregates.meanDelta` | Mean `Δ` across cases, under the two-arm mode |
| `cases[].name` | Case name |
| `cases[].aggregates.score` | Mean with-arm run score for the case |
| `cases[].aggregates.delta` | With-arm score minus without-arm score. Omitted when the case ran one arm or the arms aren't comparable |
| `cases[].arms.with[].error` | `null`，或執行異常結束的原因，例如 `timed out after 300s`。其中部分執行仍會依其產出進行評分，因此非 null 的錯誤不代表分數為 0。[因 API 錯誤而結束](#runs-ended-on-an-api-error)的執行會直接得分 0，不進行評分 |
| `cases[].arms.with[].aborted` | 當 [mock](#mock-mcp-servers) 透過 `expect:`、`abort_when` 或 [agent-mock 呼叫預算](#mock-call-budget-exceeded) 停止執行時出現，包含 `server`、`tool` 和 `reason`。該執行得分為 0，且 `error` 維持 `null` |
| `cases[].arms.with[].skippedPaidGraders` | `true` when the cost ceiling skipped this run's judge graders, so its score isn't comparable |
| `costUsd`, `durationSeconds`, `claudeVersion` | Estimated cost at list price including judge calls, wall-clock seconds, and the Claude Code version that ran the suite |

## 執行可以存取的內容

`claude plugin eval` 載入目標 plugin 的 skills、hooks 和 agents，並在您的機器上以您的身份執行其 eval 套件。將其指向 plugin 與 `claude --plugin-dir` 相同的信任決定，因此僅評估您信任的 plugins。本節中描述的隔離限制了被測試代理可以到達的內容；它不是針對 plugin 自己程式碼的邊界，通過套件的套件對 plugin 是否安全沒有說明。

### 信任 plugin 目錄

第一次針對目錄執行 `claude plugin eval` 時，Claude Code 會詢問 `Trust this plugin directory?`，除非您已在互動式 `claude` 工作階段中在那裡接受信任提示。在 git 儲存庫內，回答是信任整個儲存庫，對於互動式工作階段也是如此。當 stdin 或 stdout 不是終端時，或在 `--json` 下，執行無法詢問並被拒絕，退出代碼 1；傳遞 `--trust-plugin` 以自己斷言信任，僅對您會在自己的機器上執行的 plugin。您命名而不是作為路徑給出的目標（意味著已安裝的 plugin 或 skills-directory plugin）跳過提示。

plugin 和套件的某些部分僅在您為該執行傳遞其標誌時執行：

* 案例的 [`scaffold_script`](#add-setup-or-history-with-case-yaml) 使用 `--scaffold`
* [讀取專用集合之外的工具](#grant-tools) 使用 `--allow-tools`
* plugin 的 [真實 MCP 伺服器](#mock-mcp-servers) 使用 `--allow-real-servers` 或 `--mocks off`

案例的 `allowed_tools` 和 skill 自己的 `allowed-tools` frontmatter 無法擴展它們中的任何一個。

當 plugin 發佈您未編寫的 hooks，或您啟動其真實 MCP 伺服器時，除非您在隔離環境（例如容器或 CI 執行器）中執行它，否則將其分數視為建議，因為 hooks 和伺服器在代理沙箱外執行，可能會修改評分器讀取的檔案。

### 執行如何被隔離

每次執行都獲得一次性主目錄、工作目錄和 Claude Code 設定，被測試代理在那裡以 `claude -p` 子程序執行，僅載入您的 plugin。在編寫案例時牢記這些後果：

* **沒有個人或專案級別載入。** 您的使用者設定、hooks、`CLAUDE.md` 檔案、MCP 伺服器、其他已安裝的 plugins、記憶和 skills 不存在。專案範圍的設定不會在任何地方讀取：沒有 `.claude/` 目錄、`CLAUDE.md` 或 `.mcp.json` 從工作區上方或內部載入，即使是 `scaffold_script` 寫入的，而且 `add_dirs` 目錄僅授予讀取存取權。您的大部分 shell 環境也被扣留；僅 [allowlist](#prompt-md-fields) 和 `EVAL_*` 變數到達執行。發佈案例依賴的任何 skills、agents、hooks 或 MCP 伺服器在被測試的 plugin 中，因為 [`scaffold_script`](#add-setup-or-history-with-case-yaml) 只能提供檔案和 git 狀態。
* **受管理的原則仍然可以限制執行。** 管理員部署到機器的 [managed settings](https://code.claude.com/docs/zh-TW/managed-settings.md) 中的限制適用於執行內，因此受管理機器上的結果可能因該原則而與非受管理機器不同。
* **Artifact 工具已關閉。** 發佈 [artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 的 skill 只能在該步驟之前評分其產生的內容。
* **案例定義對代理隱藏。** 執行無法讀取 eval 目錄，因此 Claude 無法看到案例的提示、其評分器或同級案例。
* **shell 命令外沒有網路沙箱。** 您授予的 shell 命令在沙箱的網路規則下執行。`WebFetch(domain:…)` 授予直接到達該網域，plugin 自己的 hooks 和您啟動的任何真實 MCP 伺服器可以到達任何主機。

## Eval suite reference

eval 套件可以包含的所有內容都位於 plugin 的 eval 目錄 `evals/` 下，除非您 [configured another](#use-a-different-eval-directory)。當目錄包含 `prompt.md` 或 `case.yaml` 時，該目錄就算作一個案例，沒有至少一個評分器的案例會因為 `invalid case.yaml` 錯誤而無法載入，該錯誤會命名 `graders`。此樹顯示 `claude plugin eval` 在 eval 目錄中讀取或寫入的每個檔案：

```text theme={null}
evals/
├── <case>/                        # one directory per case; nest under a non-case directory to group
│   ├── prompt.md                  # frontmatter: case and run fields; body: the prompt
│   ├── case.yaml                  # optional: context.* fields, or the whole case in one file
│   ├── graders/
│   │   └── <name>.md              # one grader per file; frontmatter: type and options; body: rubric
│   ├── mocks/                     # optional: mocks for this case only, same layout as below
│   └── <fixtures, scripts, transcripts referenced by case.yaml>
├── mocks/                         # optional: suite-wide MCP mocks
│   ├── <server>/
│   │   ├── <tool>.md              # one mocked tool; body: the tool result
│   │   ├── _server.md             # optional: one agent that answers several tools
│   │   ├── _tools.json            # optional: saved tools/list response for real descriptions and schemas
│   │   └── fixtures/              # files inserted with {{file:fixtures/...}}
│   └── .replay/<server>/          # adopted agent-mock recordings, answered without a model call
└── results/<timestamp>/           # written by each run; add results/ to .gitignore
    ├── aggregate-result.json
    ├── report.html
    └── mock-recordings/           # agent-mock answers from clean runs, with ADOPT.txt
```

### prompt.md frontmatter

`prompt.md` frontmatter 接受這些欄位。未知鍵是錯誤：

| Field | Default | Purpose |
| :- | :- | :- |
| `schema_version` | `"1.1"`，為您設定 | 案例格式版本。寫成 `prompt.md` 的案例會自動取得它，所以您很少設定它 |
| `name` | 目錄名稱 | 案例名稱。`--case` globs 符合它，報告以它為鍵 |
| `description` | | 供人類使用。在執行時不使用 |
| `tags` | `[]` | `--tag` 篩選的標籤。如果任何標籤符合，案例就會執行 |
| `plugins` | 最近的封閉 plugin | 在測試中的 plugin 目錄，相對於案例目錄。當自動偵測找不到您的 plugin 時，設定 `plugins: ["../.."]`；請參閱 [the plugin didn't load](#the-baseline-arm-shows-no-plugin-or-delta-is-zero) |
| `runs` | `3` | 每個 arm 的執行次數，1 到 50。`--runs` 覆蓋它 |
| `expected_outcome` | | 供人類使用。在執行時不使用 |
| `model` | 子工作階段的預設值 | 被測試代理的模型。`--model` 覆蓋它 |
| `max_turns` | `10` | 回合上限，最多 200。達到它會被記錄為執行錯誤，通常會降低分數，所以請慷慨設定 |
| `timeout_seconds` | `300` | 每次執行的牆鐘上限，最多 3600 |
| `allowed_tools` | `[]` | 案例想要的工具，例如 `[Read, Glob, Grep, Skill]`。唯讀工具在此列出時被授予；對於其他任何東西，請參閱 [Grant tools](#grant-tools) |
| `append_system_prompt` | | 附加到子工作階段系統提示的文字 |
| `env` | `{}` | 子工作階段的額外環境變數。鍵必須符合 `EVAL_[A-Z0-9_]*`；任何其他鍵都會導致執行失敗。執行只從您的 shell 繼承一個允許清單：基本項目如 `PATH` 和語言環境、代理和憑證設定、選擇和驗證您的模型提供者的變數、大多數 `ANTHROPIC_*` 和 `CLAUDE_CODE_*` 設定，以及 `EVAL_*`。要將任何其他東西交給 plugin，例如工具鏈設定，請將其匯出為 `EVAL_*` 變數 |

### case.yaml fields

`case.yaml` 是 `prompt.md` 的替代或伴隨：它以 YAML 描述案例並新增指向其他檔案的欄位。它需要 `schema_version: "1.1"` 和 `name`。`prompt.md` 欄位 `description`、`tags`、`plugins`、`runs` 和 `expected_outcome` 在頂層；`model`、`max_turns`、`timeout_seconds`、`allowed_tools`、`append_system_prompt` 和 `env` 在 `execution:` 下。當兩個檔案都存在時，`prompt.md` frontmatter 覆蓋匹配的 `case.yaml` 欄位，`prompt.md` 主體是提示，`graders/*.md` 在 `case.yaml` 中列出的任何評分器之後新增。

這些欄位僅存在於 `case.yaml` 中：

| Field | Purpose |
| :- | :- |
| `context.scaffold_script` | 案例目錄中的 Bash 指令碼，在 Claude 啟動前在空工作區中執行，以建立 fixture 檔案或 git 儲存庫。它只在您傳遞 [`--scaffold`](#add-setup-or-history-with-case-yaml) 時執行，具有最小環境和 120 秒的限制，非零退出會導致執行失敗 |
| `context.history_file` | 案例目錄中的 `.jsonl` 文字記錄以繼續。案例的提示變成下一個使用者回合 |
| `context.add_dirs` | 案例目錄內的目錄，Claude 可能在執行期間讀取，被授予唯讀 |
| `execution.prompt` | 提示，當您將整個案例保留在 `case.yaml` 中並省略 `prompt.md` 時 |
| `graders` | 評分器清單，每個都有一個 `name` 加上 `graders/*.md` 檔案在 frontmatter 中採用的相同鍵。對於 `llm` 評分器，將評分標準放在 `criteria` 中 |

### Grader frontmatter

`graders/` 下的每個評分器檔案在 frontmatter 中採用這些鍵，加上其類型的選項。評分器的名稱是沒有 `.md` 的檔案名稱：

| Key | Default | Purpose |
| :- | :- | :- |
| `type` | 必需 | [grader types](#grader-types) 之一 |
| `weight` | `1` | 執行分數中的相對權重。任何正數 |
| `arm` | 未設定 | `with-only` 在 [two-arm run](#compare-against-a-no-plugin-baseline) 中排除評分器的評分；`both` 強制 Claude Code 否則會排除的評分器在兩個 arm 中都被評分 |

#### What a grader can look at

`regex` 評分器採用 `target`，`llm` 評分器採用 `focus`。兩者都接受相同的值：

| Value | What the grader sees |
| :- | :- |
| `last_message` | Claude 的最終回應文字。這是預設值 |
| `trace` | 工作階段為 JSON，每行一條訊息。`regex` 評分器看到每條訊息；`llm` 評分器看到前 12 條和最後 12 條。其中的引號和換行符是 JSON 轉義的，所以 regex 符合 `\"` 而不是 `"` |
| `files` | Claude 在執行期間建立的路徑清單，每行一個。不是它們的內容，也不是 scaffold 建立或 Claude 只修改的檔案 |
| `{ source: file, path: <path> }` | 執行後工作區中一個檔案的內容。使用此來評分 plugin 產生的內容。PNG、JPEG、GIF 或 WebP 檔案會作為影像顯示給 `llm` 評分器。`llm` 評分器拒絕其他二進位檔案，例如 `.pptx` 或 PDF；將它們渲染為影像或寫出為文字並評分 |
| `mock_calls` | Claude 對 [mocked MCP tool](#mock-mcp-servers) 進行的每次呼叫，及其輸入和 mock 的答案 |

#### Grader types

下面的每種評分器類型列出其選項和何時通過：

| Type | Options | Passes when |
| :- | :- | :- |
| `regex` | `pattern`、`flags`、`match`、`target` | JavaScript regex `pattern` 在目標中被找到。設定 `match: not_contains` 以要求缺失或 `match: "count:N"` 以要求恰好 N 個符合。在 `flags: i` 中放置不區分大小寫；不支援內聯 `(?i)` |
| `tool_used` | `tool`、`input_match`、`min`、`max` | 對 `tool` 的呼叫次數，其 JSON 編碼的輸入符合可選的 `input_match` regex，介於 `min`（預設 1）和 `max`（預設無限制）之間。要聲稱工具從未被呼叫，請同時設定 `min: 0` 和 `max: 0` |
| `tool_order` | `before`、`after` | 兩個工具都被呼叫，第一個符合的 `before` 呼叫先於第一個符合的 `after` 呼叫。每個都是工具名稱或 `{ tool, input_match }` |
| `file_exists` | `path`、`exists` | Claude 建立的檔案符合 `path` glob，或沒有符合 `exists: false` 的。只有在執行期間建立的檔案計數 |
| `llm` | `criteria`、`focus` | 評分器模型在至少三票中的兩票對評分標準投票通過。在 `.md` 佈局中，檔案主體是評分標準 |
| `baseline` | `baseline_file`、`criteria` | 評分器發現執行至少與 `baseline_file`（案例目錄中的 `.jsonl`）的參考文字記錄一樣好地滿足評分標準 |

### Mock files

`mocks/<server>/` 下的 `<tool>.md` 檔案回答一個工具。其主體是工具結果，具有 `{{input.<field>}}` 和 `{{file:fixtures/<name>}}` 替換。其 frontmatter 接受這些鍵：

| Key | Default | Purpose |
| :- | :- | :- |
| `type` | `fixed` | `fixed` 會原樣回傳主體。`agent` 會將主體視為給[評審模型](#command-options)的指示，該模型在該次執行中扮演伺服器，並將先前的呼叫視為歷史記錄 |
| `expect` | 未設定 | 從點分輸入路徑到類型名稱（例如 `string`、`number`、`boolean`、`array` 或 `object`）、[`/regex/`](#expect-patterns)、字面值或允許的字面值清單的對應。違反它的呼叫會以分數 0 中止執行，並報告為 `aborted`，包含伺服器、工具和原因 |
| `error` | `false` | 僅 `fixed`。將主體作為工具錯誤返回 |
| `abort_when` | 未設定 | 僅 `agent`。散文列出代理可能中止執行的唯一條件 |

兩個可選檔案位於伺服器目錄中的工具檔案旁邊：

* **`_server.md`**：一個單一的 `type: agent` mock，回答多個工具，在其 `tools:` frontmatter 鍵中列出。相同工具的 `<tool>.md` 優先。除非 `tools:` 只列出單一工具，否則在此處放置 `expect:` 保護會造成載入錯誤，因此請改為在個別 `<tool>.md` 上放置保護
* **`_tools.json`**：來自真實伺服器的已保存 `tools/list` 回應，因此 mocked 工具帶有其真實描述和輸入架構，而不是寬鬆的佔位符

案例自己的 `mocks/` 目錄使用相同的佈局並逐檔案覆蓋套件的 mocks。

#### Regex patterns in expect

`expect:` 中的 `/regex/` 值使用一種小型方言，Claude Code 會在載入套件時檢查它：

* 字面字元、`.`、跳脫序列（例如 `\d`），以及字元類別（例如 `[a-z]`）
* 量詞 `*`、`+`、`?` 以及 `{m,n}` 形式，每個都作用於單一字元、跳脫序列或類別
* 開頭可選的 `^` 與結尾可選的 `$`
* 僅限旗標 `i` 和 `s`

超出此方言的模式，例如含有群組、選擇（alternation）、反向參照、環視或其他旗標的模式，會使案例無法載入：該案例得分為 0，其錯誤會指出該模式。若要允許多個確切值，請改寫為字面值清單，而不是使用選擇。

每個模式只會檢查到某個最大長度為止的值，較長的值會被視為違反。量詞可能會降低該長度，而開頭的 `^` 會提高該長度，因此請以 `^` 錨定模式，並盡量減少量詞。

## 疑難排解

以下是作者最常遇到的問題，依您看到的內容分類。

### "plugin eval is currently in early access"

您的建置早於此命令的正式發佈。請執行 `claude update`，然後在新的工作階段中再次執行此命令。

### "plugin eval is currently unavailable"

Anthropic 已在伺服器端關閉此命令。您的機器上沒有任何設定能將其重新開啟；請執行 `claude update`，並稍後在新的工作階段中重試。

### "is not a trusted plugin directory, and this run cannot stop to ask you about it"

這是第一次針對 Claude Code 尚未信任的目錄執行，而且由於 stdin 或 stdout 不是終端機，或您傳遞了 `--json`，因此無法詢問您。請在終端機中執行一次 `claude plugin eval <dir>` 並回答提示，或者如果您信任該外掛的程式碼和套件，請傳遞 `--trust-plugin`。請參閱[執行可存取的內容](#security)。

### "is too old for claude plugin eval"

您 `PATH` 上的 `git` 早於 2.31，因此 `claude plugin eval` 在執行任何案例之前就已停止，並以代碼 1 結束，同時顯示指出您版本的訊息：

```text theme={null}
git 2.30 is too old for claude plugin eval: it ignores the environment configuration (GIT_CONFIG_COUNT, added in git 2.31) that switches off the repository's git hooks and helper programs for the run. Install git 2.31 or newer.
```

每次執行時，Claude Code 都會關閉 git hook、憑證輔助程式，以及儲存庫的 git 設定可啟動的其他程式。它是透過 git 從 2.31 版起才會讀取的環境設定來達成此目的。較舊的 git 會忽略該設定，因此套件會停止，而不是對那些程式可能執行的執行進行評分。請安裝 git 2.31 或更新版本，然後再次執行套件。

在 v2.1.283 之前，`claude plugin eval` 不會檢查 git 版本，在較舊的 git 上，套件執行時這些程式會保持開啟。

### "cannot be evaluated where sessions load it"

您在 shell 中以某個外掛的名稱執行了 `claude plugin eval`，而該外掛是從您[透過本機路徑新增](https://code.claude.com/docs/zh-TW/plugins/loading.md#in-place-and-copied-plugins)的市集所安裝。目前沒有任何工作階段能從該市集載入此外掛，因此命令會以此訊息拒絕執行，並以代碼 1 結束。

```text theme={null}
Error: formatter@my-marketplace cannot be evaluated where sessions load it: no session could load it now. Its marketplace is a folder whose catalog could not be read, or lists it no more. Check the marketplace with `claude plugin marketplace list`, or pass ./<dir> to evaluate a directory.
```

`no session could load it now.` 之後的句子會指出失敗的項目。

請在 shell 中執行 `claude plugin marketplace list`，並修正訊息所指出的問題。例如，還原市集目錄，或將外掛的項目放回其目錄清單中。若要在不透過市集的情況下評估外掛的原始碼，請將其目錄作為目標傳遞，例如 `claude plugin eval ./plugins/formatter`。

### "No eval cases found"

目前生效的 eval 目錄下不存在任何 `<case>/prompt.md` 或 `<case>/case.yaml`，或是您的 `--case` 和 `--tag` 篩選器沒有符合任何案例。請從外掛根目錄執行，或執行 `claude plugin eval init` 以建立套件。

### 基準 arm 未顯示外掛，或 delta 為零

如果摘要中沒有 `W/OUT` 欄，或案例失敗並顯示「ablation requested but no plugin resolved」，常見原因是沒有為該案例找到外掛。如果每個案例都透過 `context.history_file` 接續逐字稿，則缺少該欄是預期的，因為這些案例[預設只執行一個 arm](#compare-against-a-no-plugin-baseline)。否則，請將 `plugins: ["../.."]` 新增到案例中，提供從案例目錄到外掛目錄的路徑。

如果外掛確實已載入，但 `Δ` 仍接近零，且您的 `tool_used: Skill` 評分器失敗，這通常是一個真實的發現，表示該 skill 的 `description` 不會因提示詞的措辭而觸發。請調整描述，然後重新執行相同的套件。

### 您外掛的某個 agent 出現 "Agent type '...' not found"

根據預設，每個案例都會在載入您的外掛和不載入外掛的情況下各執行一次，而不載入外掛的執行即為[無外掛基準](#the-no-plugin-baseline)。當 Claude 在基準執行中分派您外掛的某個 agent 時，Agent 工具呼叫會失敗，並顯示 `Agent type '<plugin>:<agent-name>' not found. Available agents: ...`。該清單只列出不需外掛即存在的 agent，例如[內建 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#built-in-subagents)。

此錯誤是預期的，因為 `Δ` 會將您外掛的執行與基準進行比較。在 JSON 結果中，基準執行位於 `cases[].arms.without` 下。

在載入您外掛的執行中，在 `allowed_tools` 中列出 `Agent` 的案例可以透過命名空間名稱分派您外掛的某個 agent，例如名為 `my-plugin` 的外掛中的 `code-reviewer` agent 為 `my-plugin:code-reviewer`。若要略過基準執行，請傳遞 `--ablation none`。

### 已產生正確的檔案，但所有項目都評分為零

您的評分器以 `files`（已建立路徑的清單）為目標，但您實際想要的是檔案的內容。請使用 `{ source: file, path: <path> }` 作為 `target` 或 `focus`。

另外，`file_exists` 只計算執行期間建立的檔案，因此由 scaffold 建立或 Claude 僅編輯過的檔案對它而言是不可見的；請對其內容評分，或對 `Edit` 使用 `tool_used`。

### 針對 trace 的正規表示式無法比對我看得到的文字

* **目標錯誤**：預設的 `target` 是 `last_message`，而不是 trace。
* **JSON 逸出**：當您確實以 `trace` 為目標時，它是每行一筆 JSON，因此引號會顯示為 `\"`。
* **正規表示式語法**：正規表示式使用 JavaScript 語法，因此請在 `flags` 中放入 `i`，而不是寫成 `(?i)`。

### 工具遭拒、MCP 工具遺失，或 Bash 無法執行

唯讀集合以外的任何項目都需要您授予權限，例如 `--allow-tools Bash Write`。您的個人 MCP 伺服器永遠不會在執行中載入。外掛本身的伺服器除非您[選擇啟用](#mock-mcp-servers)否則不會啟動，而且其工具還需要 `--allow-tools "mcp__plugin_<plugin>_<server>__*"` 授權；mock 工具則兩者都不需要。

### 執行以 1 結束，但結果看起來正常

當每個案例的分數都達到或高於 `--threshold`，但命令仍以 1 結束時，stderr 上會有一行指出原因，即使在 `--json` 下也是如此。例如，某個案例檔案無法載入，或執行[因 API 錯誤而結束](#runs-ended-on-an-api-error)。其他原因請參閱[退出碼](#run-evals-in-ci)。

預設的 `--threshold` 是 1.0，因此只要任何案例的分數低於滿分，命令就會以 1 結束。請設定符合您要求分數的閾值。

### `--json output path must end in .json`

您將目標放在 `--json` 之後，因此它被讀取為輸出路徑。請將目標放在前面，例如 `claude plugin eval . --json`，或為 `--json` 提供明確的 `.json` 路徑。

### 在評分為 1.0 的執行下，評分器顯示 passed: false

在雙 arm 執行中，該評分器依設計會被排除在分數之外，其 `scored` 欄位為 `false`。請參閱[與無外掛基準比較評分](#compare-against-a-no-plugin-baseline)。

### "ended on an API error and scored 0 without grading"

此 stderr 警告表示 API 以 HTTP 錯誤回應了至少一次執行的最後一個請求，例如速率限制或方案用量上限。這類執行會得到 0 分且沒有評分器結果，而且無論分數和 `--threshold` 為何，命令都會以非零值結束。

若要修正此問題，請找出每個受影響執行的錯誤，並解決其所回報的原因，然後再次執行套件：

* **未使用 `--json` 時**：錯誤位於該執行進度行的結尾，在 `error:` 之後
* **使用 `--json` 時**：錯誤位於 [JSON 結果](#json-result)中的 `cases[].arms.with[].error` 或 `cases[].arms.without[].error`

此計數也包含[基準](#the-no-plugin-baseline)執行。基準執行的分數從不決定案例是否通過，因此即使每個案例都通過，命令仍可能失敗。在雙 arm 執行中，受影響案例的 `W/OUT` 和 `Δ` 會顯示為 `—`。若為用量上限或速率限制，請參閱[執行中途因用量上限或速率限制錯誤而失敗](#runs-fail-with-a-usage-limit-or-rate-limit-error-partway-through)。

在 v2.1.299 之前，這類執行會根據其已產生的內容進行評分。

### 執行中途因用量上限或速率限制錯誤而失敗

以用量上限或速率限制錯誤結束的執行會[不經評分直接記為 0 分](#runs-ended-on-an-api-error)，且命令會以非零值結束。套件仍會完成，且不會被標記為 `partial`。請在限制重設後重新執行；如果需要維持在限制之內，請使用 `--runs 1` 或 `--case` 篩選器。

### "mock call budget exceeded"

一次執行中的每個 `type: agent` [mock](#mock-mcp-servers) 都會共用一份呼叫預算，其大小為案例 `max_turns` 的四倍，以預設值 10 計算即為 40 次呼叫。從 `.replay/` 錄製內容回應的呼叫也會計入，而案例的 `mock budget` 進度行會顯示該預算。超出預算的呼叫會中止執行，並以此原因記為 0 分，因此對於會多次呼叫 agent mock 的 skill，請在案例中提高 `max_turns`。

### 執行逾時或達到回合上限

預設值為 10 個回合和 300 秒。對於需要更多資源的任務，請在案例中提高 `max_turns` 和 `timeout_seconds`，並使用 `--max-cost-usd` 作為成本上限，而不是設定嚴格的每次執行限制。

## See also

* [建立 plugin](https://code.claude.com/docs/zh-TW/plugins/create.md)：建立您正在測試的 plugin，並在開發期間使用 `--plugin-dir` 載入它
* [Plugin 命令參考](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-eval)：`plugin eval` 和 `plugin eval init` 命令項目。資訊清單的 [`experimental.evals`](https://code.claude.com/docs/zh-TW/plugins/manifest-reference#fields) 鍵位於資訊清單參考中
* [Skills](https://code.claude.com/docs/zh-TW/skills.md)：skill 的描述如何決定 Claude 何時呼叫它，這是檢查 skill 是否觸發的案例測量的內容
* [Sandboxing](https://code.claude.com/docs/zh-TW/sandboxing.md)：當您授予 Bash 執行時適用的 OS 級沙箱
* [發佈 plugin](https://code.claude.com/docs/zh-TW/plugins/publish.md)：一旦其測試套件通過，發佈 plugin
* [測量 plugin 成本和使用情況](https://code.claude.com/docs/zh-TW/plugins/measure.md)：plugin 新增至每個工作階段內容的內容，以及人們是否仍在使用它
