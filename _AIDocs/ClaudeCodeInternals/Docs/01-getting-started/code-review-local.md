<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-local | lastmod: 2026-11-03 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-local（官方 zh-TW，lastmod 2026-11-03）｜分類：Getting started › Code review and pull requests｜EN 摘要：Run `/code-review` in a Claude Code session to find bugs in your branch's changes, point the review at a pull request or path, and have Claude apply the fixes.

# 使用 /code-review 在本機審查

> 在 Claude Code 工作階段中執行 `/code-review`，找出分支變更中的錯誤、將審查指向 pull request 或路徑，並讓 Claude 套用修正。

`/code-review` 是在您工作的工作階段中，於 Claude Code 提示詞輸入處輸入的命令。Claude 會審查您分支上的變更、尋找正確性錯誤，並在對話中回報發現的問題。視您的模型與 effort 等級而定，審查也會涵蓋重複利用、簡化與效率方面的整理。

此命令適用於任何方案。審查在您自己的工作階段中執行，因此會與工作階段的其餘部分一樣，計入您方案的使用量或 API 計費。

> [!NOTE]
>
> 若要在 GitHub 上自動審查儲存庫中的每個 pull request，請參閱 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)，這是由 Owner 為您的組織啟用的託管服務。

`/review` 是 `/code-review` 的別名。在 v2.1.223 之前，`/review` 是一個獨立的命令，會對 GitHub pull request 執行單次、唯讀的審查。

**1. 執行 /code-review**

執行命令：

```text theme={null}
/code-review
```

未指定目標時，審查會涵蓋您目前分支上的變更。若要改為將審查指向 pull request、其他分支、路徑或提交範圍，請參閱[選擇要審查的內容](#choose-what-to-review)。

您也可以加入旗標：

* `--fix`：同時要求 Claude 在審查後將發現的問題套用到您的工作樹。其編輯會經過您的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。
* `--comment`：將發現的問題以行內留言的形式張貼到 GitHub pull request，或以單一備註的形式張貼到 [GitLab merge request](#post-findings-to-a-gitlab-merge-request)

**2. 繼續工作**

在終端機工作階段中，審查會以背景 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的形式執行，擁有自己的上下文視窗，因此不會填滿您的對話。審查完成時，發現的問題會出現在您的對話中。

**3. 處理發現的問題**

請 Claude 修正審查發現的問題。使用 `--fix` 或 `--comment` 時，Claude 會在審查過程中套用或張貼發現的問題，且可能會請您核准其編輯。

## 選擇要審查的內容

若要審查目前分支以外的內容，請在 effort 等級與任何旗標之後輸入目標。Claude 會將該文字作為審查目標接收。目標可以是 pull request 編號、分支名稱、檔案路徑或 Git 修訂範圍。在第一欄找到您要審查的內容，並輸入第二欄所示的內容：

| 要將審查指向 | 輸入 |
| :- | :- |
| 您目前的分支與未提交的變更 | `/code-review` |
| 您最近的 15 個提交 | `/code-review HEAD~15..HEAD` |
| 一個分支對照另一個分支 | `/code-review main...my-feature` |
| 單一提交，其中 `abc1234` 為該提交的雜湊值 | `/code-review abc1234^..abc1234` |
| 依編號指定的 pull request | `/code-review 1234` |
| 檔案或目錄路徑 | `/code-review src/auth` |

未指定目標時，`/code-review` 會審查您分支中領先其上游分支的提交，以及您未提交的變更。若分支沒有上游，Claude 會與 `main` 或前一個提交進行比較。

使用 `ultra` 時，Claude Code 會以不同方式解讀目標，如 [effort 等級與旗標之後的文字](#text-after-the-effort-level-and-flags)所述。

## 審查會讀取與編輯的內容

執行審查前請先確認以下事項，特別是使用 `--fix` 時：

* **編輯**：未使用 `--fix` 時，審查的指令只要求 Claude 提供報告。使用 `--fix` 時，指令還會要求它將發現的問題套用到您的工作樹。無論哪種情況，任何編輯都會經過您的權限模式。
* **倒回**：背景審查會在您工作階段的[檢查點](https://code.claude.com/docs/zh-TW/checkpointing.md#subagent-edits-not-restored)之外套用其 `--fix` 編輯。之後，`/rewind` 只會還原 Claude 先前已在您的對話中編輯過的檔案。審查對其他檔案的編輯會保留，因此請使用 git 將其還原。當審查[在前景執行](#run-in-the-foreground)時，它會在您自己的回合中編輯工作樹，因此 `/rewind` 會照常還原其編輯。
* **指令**：審查會遵循您的 `CLAUDE.md`，包括在非互動的 `-p` 執行中。它不會讀取 `REVIEW.md`。該檔案用於設定 GitHub pull request 上的託管 [Code Review 服務](https://code.claude.com/docs/zh-TW/code-review-customize.md#use-review-md-for-review-only-rules)。

## 發現的問題如何回報

在以下兩種執行方式中，Claude 都會以回覆中的文字回報發現的問題：

* 在終端機工作階段中，`/code-review` 會以 [forked subagent](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent) 的形式執行審查
* 在使用文字或 JSON 輸出的 `-p` 執行中

在會請求發現問題清單的主機應用程式中（例如[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#review-your-code)），Claude 會改為透過 [`ReportFindings` 工具](https://code.claude.com/docs/zh-TW/tools-reference)回報審查發現的問題。報告會以發現問題清單的形式呈現，每個項目會顯示檔案位置、一句話摘要，以及該問題若帶有類別標籤時所顯示的標籤（例如 `correctness`）。主機請求適用於所有 effort 等級。

當 Claude 在工作階段稍後修正已回報的問題時，會再次回報這些問題。接著 Claude Code 會在更新後的發現問題清單中，將每個問題標記為已修正、已略過或無需變更。

## 調整 effort 與引數

除了 `--fix` 與 `--comment` 之外，此命令還接受以下旗標：

* `--post`：在針對 `github.com` pull request 的 `ultra` 雲端審查中，於啟動對話框中預先選取將完成的發現問題張貼到 PR。請參閱[將發現的問題張貼到 pull request](https://code.claude.com/docs/zh-TW/ultrareview.md#post-findings-to-the-pull-request)。需要 Claude Code v2.1.227 或更新版本。
* `--max-findings <n>`、`--max-findings all` 或 `--max-findings default`：回報最多 `n` 個發現的問題，或使用 `all` 回報所有問題，以取代審查的一般上限。當審查透過發現問題工具回報時，上限為 32。之後的審查會沿用您輸入的值，直到您傳入 `--max-findings default` 為止，但在非互動的 `-p` 執行中傳入的值不會被記住。需要 Claude Code v2.1.288 或更新版本。

傳入 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，可在涵蓋範圍與信心程度之間取捨。在 `low` 時，審查會回報它最有把握的問題，因此您看到的誤判會較少。從 `medium` 到 `max`，審查會擴大涵蓋範圍。

若您未輸入等級，審查會沿用您上次輸入的 `low` 到 `max` 之間的等級，即使是在先前的工作階段中輸入的。Claude Code 會顯示如 `Reusing high effort, the level you typed last time` 的通知。以下規則決定每次執行使用哪個等級：

* **輸入等級**：您輸入的等級（例如 `/code-review high`）會改變之後執行所沿用的等級
* **非互動執行**：您在非互動 `-p` 執行中傳入的等級不會更新記住的等級
* **`ultra`**：審查既不使用也不更新記住的等級
* **從未輸入過等級**：審查會使用工作階段目前的 effort

在 v2.1.223 之前，未指定等級的 `/code-review` 一律使用工作階段目前的 effort。

### 將發現的問題張貼到 GitLab merge request

當您為 GitLab merge request 傳入 `--comment` 時，Claude Code 會透過 GitLab 的 `glab` CLI 張貼發現的問題。需要 Claude Code v2.1.257 或更新版本。若未安裝 `glab`，Claude 會改為在終端機中印出發現的問題。

請以 URL 或 `!123` 參照的形式傳入 merge request。只有當檢出的 origin 位於 `gitlab.com` 時，Claude Code 才會將單純的數字或分支名稱視為 merge request。在自行管理的 GitLab 執行個體上，請傳入 URL 或 `!123` 形式。

### effort 等級與旗標之後的文字

在 effort 等級與旗標之後，Claude Code 會將該行的其餘部分讀取為審查目標。`ultra` 引數會改變這種解讀方式：

* **使用 `ultra` 時**：Claude Code 會將單一字詞讀取為基底分支或 PR 編號。未指明分支或 PR 的較長文字會成為[附加到審查的備註](https://code.claude.com/docs/zh-TW/ultrareview.md#pass-a-request-in-plain-words)。`/code-review ultra check my auth changes` 會審查您目前的分支，而 Claude 會將發現的問題與您的備註相關聯。
* **未使用 `ultra` 時**：剩餘的所有內容都是審查目標，即使它以另一個命令名稱開頭也一樣。`/code-review /fix-issue 123` 會以 `/fix-issue 123` 作為目標文字進行審查，而不是將 `/fix-issue` 載入為第二個[堆疊的 skill](https://code.claude.com/docs/zh-TW/skills.md#stack-several-skills-in-one-message)。

## 在前景執行

若要讓審查在前景執行，請執行下列其中一項：

* 以非互動模式執行，使用 `-p` 旗標或 Agent SDK。Claude Code 會等待審查完成，並在回應中包含發現的問題，但 `ultra` 除外，它[不會等待雲端審查](https://code.claude.com/docs/zh-TW/ultrareview.md#run-ultrareview-non-interactively)。
* 將 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 `1`，這也會關閉其他背景任務功能
* 在先前的審查仍在進行時，再次執行 `/code-review`

## 讓 Claude 啟動審查

Claude 可以自行啟動 `/code-review`，無需您輸入命令：

* **當您以一般語言提出要求時**：請 Claude 審查您的變更，它就可以執行此 skill
* **從排程任務**：以 `/code-review` 作為提示詞的[工作階段範圍排程任務](https://code.claude.com/docs/zh-TW/scheduled-tasks.md)會執行審查

工作階段範圍的排程任務永遠不會啟動[雲端審查](#escalate-to-ultrareview)，因此請排程不帶 `ultra` 引數的 `/code-review`。

若要阻止 Claude 與排程任務啟動審查，同時保留 `/code-review` 供您自行輸入，請在[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)（例如 `~/.claude/settings.json`）中加入 [`skillOverrides`](https://code.claude.com/docs/zh-TW/skills#override-skill-visibility-from-settings) 項目：

```json theme={null}
{
  "skillOverrides": {
    "code-review": "user-invocable-only"
  }
}
```

在 v2.1.246 之前，只有在從 Anthropic 取得的功能旗標將其開啟時，Claude 才會自行啟動 `/code-review`。在[不取得功能旗標的工作階段](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)中，`/code-review` 只有在您輸入時才會執行，而排程的 `/code-review` 會以純文字形式傳送給 Claude。

## 升級至 ultrareview

`/code-review ultra --fix` 會在雲端執行更深入的 [ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)，然後在發現的問題傳回您的工作階段時，要求 Claude 將其套用到您的工作樹。

Ultrareview 使用自己的範圍：

* **比較的內容**：您目前的分支對照儲存庫的預設分支，加上工作樹中未提交與已暫存的變更
* **敏感檔案**：對於名稱類似憑證或金鑰的檔案（例如 `.env` 與 `*.tfvars` 檔案）的未提交變更，Claude Code 會遵循[將本機儲存庫上傳至雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#send-local-repositories-without-github)的規則
* **不同的基底**：傳入分支名稱（例如 `/code-review ultra develop`），即可與不同的基底進行比較

當目標是 `github.com` pull request 時，您可以讓 Claude 以您的 GitHub 帳戶，將[完成的發現問題以留言形式張貼到 PR](https://code.claude.com/docs/zh-TW/ultrareview.md#post-findings-to-the-pull-request)。需要 Claude Code v2.1.227 或更新版本。

> [!NOTE]
>
> Ultrareview 需要使用 claude.ai 帳戶進行身分驗證。它不適用於 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry，也不適用於已啟用 Zero Data Retention 或已套用 [HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md)的組織。在這些情況下，`/code-review ultra` 會改為在您的工作階段中執行本機審查。使用[客戶管理加密金鑰](https://platform.claude.com/docs/en/manage-claude/cmek)（CMEK）的組織無法執行 ultrareview。若要在本機審查您的變更，請執行 `/code-review`。

若要從指令碼或 CI 作業執行雲端審查，請使用 [`claude ultrareview` 子命令](https://code.claude.com/docs/zh-TW/ultrareview#run-ultrareview-non-interactively)，它會等待發現的問題並將其印出到 stdout。

## 變更或擴充審查

`/code-review` 是一個[隨附 skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)：其指令內建於 Claude Code 中，因此磁碟上沒有可開啟或編輯的 `SKILL.md` 檔案。若要讓每次審查都遵循專案規則，請將規則加入您的 `CLAUDE.md`。若要更進一步，請從以下其中一個頁面開始：

* **取代命令**：名為 `code-review` 的專案或個人 skill 會取代隨附的 skill 執行，而 `/review` 別名則會繼續執行隨附的審查。請參閱[解決名稱相同的 skill](https://code.claude.com/docs/zh-TW/skills.md#resolve-skills-that-share-a-name)。
* **打造您自己的審查者**：撰寫審查者 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 或審查 [skill](https://code.claude.com/docs/zh-TW/skills.md)
* **使用相關命令**：[`/simplify`](https://code.claude.com/docs/zh-TW/commands) 僅審查整理方面的問題並套用其修正，而 [`/verify`](https://code.claude.com/docs/zh-TW/commands) 會執行您的應用程式以確認變更是否有效

此命令在 v2.1.147 之前名為 `/simplify`，當時預設會套用修正。若您曾為了找出錯誤而在指令碼中使用 `/simplify`，請改用 `/code-review --fix`。

## 相關資源

* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：為您的組織審查 GitHub 上每個 pull request 的託管服務
* [Ultrareview](https://code.claude.com/docs/zh-TW/ultrareview.md)：更深入的雲端審查的設定、限制與費用
* [命令](https://code.claude.com/docs/zh-TW/commands.md)：`/code-review`、`/review`、`/simplify` 與 `/verify` 的單行參考
* [Skills](https://code.claude.com/docs/zh-TW/skills.md)：隨附 skill 的運作方式，以及如何撰寫您自己的 skill
