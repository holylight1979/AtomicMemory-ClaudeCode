<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/best-practices | lastmod: 2026-11-04 | section: Getting started / Use Claude Code -->
> 來源：https://code.claude.com/docs/zh-TW/best-practices（官方 zh-TW，lastmod 2026-11-04）｜分類：Getting started › Use Claude Code｜EN 摘要：Get more out of Claude Code: tell Claude what it can't see, give it a check to run, and enforce the rules that can't have exceptions.

# Claude Code 最佳實踐

> 充分發揮 Claude Code 的效用：告訴 Claude 它看不到的資訊、給它一個可執行的檢查，並強制執行不容例外的規則。

Claude Code 的設計讓您在大多數情況下，於全新工作階段中輸入的第一個簡單提示詞就已經能做對事情，完全不需要您事先進行任何設定。

例如：

* 為了讓命令能安全執行而不需要您逐一核准，新的終端機和 VS Code 工作階段會以[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)啟動，由分類器在任何有風險的操作執行前先進行審查。
* 為了讓您的主要對話保持專注，同時讓獨立的工作平行進行，Claude 會將工作委派給 subagent，並且只在必要時才回報。
* 為了讓長時間的工作階段能持續進行而不需要您管理，對話會在上下文視窗填滿之前自動壓縮。

本頁說明預設行為不夠用時該怎麼做。這通常發生在您的專案有 Claude 無法單憑程式碼看出的知識、規則或限制時：

* 只存在於某個人腦中的部署流程
* 絕對不能被讀取的檔案
* 任何工作必須通過才能算完成的檢查
* 您必須控制在範圍內的預算

沒有任何預設值能知道您專案的這些事情，因此在這方面，您只需少量設定就能獲得豐厚回報。

當工作階段的進展不如預期時，原因幾乎總是以下其中之一：

* Claude 打造出的東西與您想像的不同，或者它必須在每個工作階段開始時重新發現同一件事實。它缺少了無法透過閱讀儲存庫取得的資訊。請參閱[告訴 Claude 它看不到的資訊](#tell-claude-what-it-cant-see)。
* Claude 說它完成了，但其實並未完全完成，通常是因為它沒有辦法檢查自己的工作。請參閱[給 Claude 一個可執行的檢查](#give-claude-a-check-to-run)。
* Claude 做了在這個儲存庫中絕對不能發生的事，或跳過了必須執行的步驟。單靠提示詞無法保證這兩者。請參閱[強制執行不容例外的規則](#enforce-the-rules-that-cant-have-exceptions)。
* Claude 做對了，但花費的時間、token 或權限提示超出了這項任務應有的成本。請參閱[變更預設值](#change-a-default)。

[讓 Claude 在您不在時執行](#let-claude-run-without-you)將同樣的四點套用到無人值守的執行上，而[可以停止做的事](#what-you-can-stop-doing)則列出了因目前的模型而變得不再必要的建議。

> [!NOTE]
>
> 整個團隊的設定請參閱另一個頁面：[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)。

## 確定性與非確定性指令

您給 Claude Code 的每一項指令都屬於以下其中一種：

1. 非確定性：您撰寫指令，由 Claude（模型）讀取。這可以是您的提示詞、`CLAUDE.md` 或 skill。接著由模型決定如何處理這些資訊。它通常會遵循您的命令，而且目前的模型很擅長在沒有太多上下文的情況下理解您的意圖，但*無法保證*它會遵循您的指令。它仍然可能決定不做某些事，或做其他的事。
2. 確定性：您設定指令，由 Claude Code（執行框架）*必須*執行。這可以是 hook、拒絕規則或受管設定。無論模型決定做什麼，Claude Code 每次都會套用它。

Claude Code 中的大多數功能都有這兩種形式：

| | 非確定性（由 Claude 決定） | 確定性（由 Claude Code 強制執行） |
| :- | :- | :- |
| 要做什麼 | 您的提示詞、`CLAUDE.md`、Claude 自行選用的 skill | Hook，以及只有您能啟動的 skill |
| 可以觸及什麼 | 自動模式的分類器 | 拒絕規則、[嚴格模式](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)下的沙箱、受管設定 |
| 何時算完成 | 要求提供證據、`/goal`、`/code-review` | 測試、型別檢查、`Stop` hook、CI |
| 花費多少 | Effort 等級、Claude 自己的步調 | 搭配 `-p` 使用的 `--max-turns` 或 [`--max-budget-usd`](https://code.claude.com/docs/zh-TW/cli-reference)、您設定的[支出上限](https://code.claude.com/docs/zh-TW/costs.md) |
| 誰有最終決定權 | Claude 對其所做工作的摘要 | 分支保護、核准合併的人 |

大多數時候，您會希望由 Claude 來決定。幾乎每項準則都有例外，而目前的模型很擅長閱讀眼前的程式碼，並判斷某項準則是否適用於當下情況。面對實際的程式碼，Claude 通常比您事先寫好的規則更適合做出判斷。

確定性的方式適用於您希望確保某些事情*一定*發生（或一定不發生）的情況，無論模型如何決定。這不一定是什麼重大的事。自動模式已經會[封鎖重大的事情](https://code.claude.com/docs/zh-TW/permission-modes.md#what-the-classifier-blocks-by-default)，例如正式環境部署或強制推送覆蓋他人的工作。它通常是*您的*專案特有的事情，而且可以要多小眾就多小眾：

* 絕對不要編輯 `src/gen/` 中產生的用戶端
* 建立檔案後一律執行授權標頭指令碼

您可以將上述任一項寫成 `CLAUDE.md` 或提示詞中的一行，而 Claude 幾乎每次都會遵循。但無論您的措辭多麼強烈，Claude 是否在某個回合遵循那一行，仍然是由 Claude 決定。

> [!TIP]
>
> 如果您不斷為 `CLAUDE.md` 中的某一行加強語氣，而 Claude 仍然漏掉它，這表示那一行應該改成 hook。反之亦然：如果您為只是偏好的事情設了 hook，請刪除它們，讓 Claude 自行決定。

## 告訴 Claude 它看不到的資訊

> [!TIP]
>
> 只寫下 Claude 無法透過閱讀儲存庫找到的內容，或是它原本必須在每個工作階段花時間重新發現的內容。

Claude 在每項任務開始時都會閱讀您的程式碼，而目前的模型在這方面*非常*擅長。它們會找出您的檔案配置、慣例、測試框架，以及現有元件的建構方式，通常比您解釋得還快。這意味著您可能想為它寫下的大部分內容，Claude 其實都已經知道了。

它找不到的是從來不在儲存庫中的資訊：

* 您的團隊在會議中做出的決定
* 只存在於某個人腦中的部署流程
* 整合測試需要的環境變數

還有一些資訊*確實*在儲存庫中，但需要花幾分鐘挖掘才能找到，而 Claude 必須在每個工作階段開始時重新挖掘一次。

在為 Claude 寫下任何內容之前，一個很好的測試方式是：

1. 它能透過閱讀程式碼找到這個資訊嗎？
2. 它實際上會去找嗎？

如果兩者的答案都是肯定的，就不用寫。

### 撰寫具體的提示詞

具體的提示詞之所以有幫助，也是同樣的道理，因為它給了 Claude 原本沒有的資訊。如果您一開始就指出檔案、描述症狀，並說明「修好」是什麼樣子，通常可以省下之後一輪的修正。

在兩種合理做法之間的偏好也是如此：Claude 無法從程式碼中讀出這一點，所以如果您在意它選哪一種，請一開始就說明。

| 與其說 | 不如試試 |
| :- | :- |
| *「修復登入錯誤」* | *「使用者回報工作階段逾時後登入失敗。檢查 src/auth/ 中的 token 重新整理，寫一個能重現問題的失敗測試，然後修復它」* |
| *「新增日曆小工具」* | *「依照 HotDogWidget.php 的模式，打造一個可以選擇月份並在年份之間翻頁的日曆小工具。不要使用新的程式庫」* |

如果您手上已經有 Claude 需要的東西，請直接交給它，而不是描述它：

* 檔案：輸入 `@` 和路徑，即可在訊息中[包含檔案內容](https://code.claude.com/docs/zh-TW/common-workflows.md#reference-files-and-directories)。
* 影像：將設計或錯誤的螢幕擷取畫面貼到提示詞中。
* 命令輸出：從您的 shell 用 `cat error.log | claude -p "what's going on here"` 以管道傳入。

像 `think step by step` 或 `be thorough` 這樣的詞句只是一般的提示詞文字，而不是關鍵字。控制 Claude 思考深度的主要方式是 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)，[變更模型和 effort](#change-the-model-and-effort) 中會說明。這類措辭仍然可以在 effort 設定範圍內稍微引導 Claude，但無法讓它超越該設定。

仍然有幫助的一句話是 `be ambitious`。Claude 傾向以保守的方式理解請求，並打造能滿足需求的最小成果，因為它看不出您期望的程度有多高。當您想要更完整的版本，包含處理邊界情況和自然延伸的功能時，請明確說出來：

```text theme={null}
build the settings page from the mockup. be ambitious: empty and error states, the save flow wired up, keyboard navigation, not just the layout
```

這是在告訴 Claude 範圍（只有您知道），而不是要它多努力思考。

而當您是在探索而非修復特定問題時，像 `what would you improve in this file?` 這樣模糊的提示詞完全沒問題。您在過程中會需要多修正一些，這就是取捨。

### 先與 Claude 腦力激盪

當您還不確定自己到底想要什麼時，不必在下提示詞之前就全部想清楚。改為請 Claude 採訪您：

```text theme={null}
I want to add rate limiting to the public API but haven't thought it through yet. Interview me until you could write the spec, then write it to SPEC.md.
```

Claude 會針對您尚未確定的部分提出選擇題：依使用者或依金鑰限制、超過限制的請求如何處理、哪些不在範圍內。它會持續提問，直到答案足以構成一份規格。

`SPEC.md` 產生之後，開啟一個全新的工作階段來依據它進行建置，讓建置從乾淨的上下文和書面的完成定義開始。這也是您之後在[給 Claude 一個可執行的檢查](#give-claude-a-check-to-run)中要讓審查者參照的檔案。

### 保持 CLAUDE.md 簡短

Claude Code 會在每個工作階段載入 [`CLAUDE.md`](https://code.claude.com/docs/zh-TW/memory)，這意味著其中的每一行在*每項*任務中都會佔用 Claude 一點注意力，無論是否相關。這就是為什麼這個檔案最好只包含 Claude 無法從程式碼本身推斷出的內容：

* 如何在這個儲存庫中確認工作：確切的測試、型別檢查和 lint 命令，以及如何執行單一測試檔案
* 程式碼容易誤導的地方：到處都是但新程式碼不能仿效的舊模式，或看起來未使用但其實在用的目錄
* 不在儲存庫中的決定：團隊最終採用哪個錯誤輔助函式、部署如何運作、什麼需要遷移審查
* 任何您已經修正過兩次的事情

通過這項測試的 `CLAUDE.md` 會保持簡短：

```markdown CLAUDE.md theme={null}
# Commands
- Install: pnpm install
- Run one test file: pnpm vitest run path/to/file.test.ts
- Typecheck: pnpm tsc --noEmit

# Conventions
- Use the error helpers in src/lib/errors.ts, never throw raw strings
- src/legacy/ is still live but don't copy its patterns into new code

# Gotchas
- Integration tests need DATABASE_URL set, see .env.example
```

在工作階段中，執行 [`/context all`](https://code.claude.com/docs/zh-TW/commands#all-commands) 以確認 Claude 已載入該檔案。

請注意，型別檢查那一行只有命令。Claude 需要知道這個命令，才能在過程中檢查自己的工作。如果您還希望 Claude Code 在 Claude 完成前*強制*通過型別檢查，那是 [`Stop` hook](#enforce-the-check-with-a-stop-hook) 的工作。在這個檔案中寫 `Always typecheck before you finish` 這樣的一行，大多數時候有效，但不是每次都有效。

您不必從頭撰寫這個檔案：

* `/init` 會根據您的程式碼庫產生一個初始版本。之後的工作主要是刪除行數。[記憶指南](https://code.claude.com/docs/zh-TW/memory.md#write-effective-instructions)建議保持在 200 行以下。
* `/doctor` 會針對 Claude [已經能從程式碼推斷出](https://code.claude.com/docs/zh-TW/memory.md#my-claude-md-is-too-large)的內容建議刪除。
* `/doctor prompt-audit` 會標記為舊模型撰寫的指令、指向已不存在之檔案的指令，或[彼此矛盾](https://code.claude.com/docs/zh-TW/memory.md#audit-your-instruction-files)的指令。

您的個人偏好應放在 `CLAUDE.local.md` 而非 `CLAUDE.md`，並將該檔案加入 `.gitignore`，讓它不會進入儲存庫。

> [!NOTE]
>
> 如果 Claude 一直忽略*確實*寫在 `CLAUDE.md` 中的某一行，加上 IMPORTANT 大概無法解決問題。要嘛是檔案變得太長導致那一行被淹沒，要嘛那一行是不容例外的規則，這種情況下它應該放在 [hook](#enforce-the-rules-that-cant-have-exceptions) 中。

### 將規則限定在程式碼庫的某個部分

如果某條規則只在程式碼庫的某個部分有意義，請將它放在 [`.claude/rules/`](https://code.claude.com/docs/zh-TW/memory#path-specific-rules) 中並加上 `paths:` 篩選器，讓它只在 Claude 實際於該處工作時才載入。例如，這個 `.claude/rules/api.md` 會在處理 `src/api/` 下的 TypeScript 檔案時載入：

```markdown .claude/rules/api.md theme={null}
---
paths:
  - "src/api/**/*.ts"
---
- Validate request bodies with the zod schemas in src/api/schemas/, don't hand-roll checks
- Every new endpoint needs an entry in openapi.yaml, CI fails without it
```

### 將團隊流程放在 skill 中

能力更強的模型懂得更多工程知識，但它不知道*您的*團隊如何進行發布、您的事件處理手冊寫了什麼，或您希望 API 文件如何撰寫。這類知識應放在 [skill](https://code.claude.com/docs/zh-TW/skills.md) 中：一個儲存在 `.claude/skills/<name>/SKILL.md` 的流程或團隊知識。

對於這類內容，skill 佔用的上下文也比 `CLAUDE.md` 少。對於 Claude 可以自行啟動的 skill，它在每個工作階段都會看到名稱和描述，但只有在任務需要時才會[讀取完整檔案](https://code.claude.com/docs/zh-TW/skills.md#skill-content-lifecycle)。放在 skill 中的冗長發布流程，不會像放在 `CLAUDE.md` 中那樣拖累您無關的錯誤修復。

> [!NOTE]
>
> `CLAUDE.md` 的原則同樣適用於 skill：只寫下 Claude 無法自行找到的內容。

對於有副作用的工作流程，例如實際進行發布，請加上 `disable-model-invocation: true`。這樣 Claude 就[無法自行啟動該 skill](https://code.claude.com/docs/zh-TW/skills.md#control-who-invokes-a-skill)，只有在您自己輸入 `/release` 時才會執行。儲存為 `.claude/skills/release/SKILL.md` 時，它可能看起來像這樣：

```markdown .claude/skills/release/SKILL.md theme={null}
---
name: release
description: Cut a new release. Bumps the version, writes the changelog entry, tags it and pushes the tag so CI can publish.
disable-model-invocation: true
---
1. Make sure you're on main with a clean tree. If not, stop and ask.
2. Run `pnpm changeset version` and commit the result.
3. Summarize the PRs merged since the last tag into CHANGELOG.md, one line each, user-facing changes only.
4. Tag `v<new version>` and push the tag. CI publishes from there, never publish from your machine.
```

### 連接 Claude 需要的工具

Claude 看不到的部分資訊完全存在於另一個系統中，例如您的議題追蹤器或錯誤儀表板。如果該系統有 CLI，那通常是最簡單的接入方式。例如，安裝並登入 `gh` 後，Claude 就能開啟 pull request 並閱讀審查留言，完全不需要您解釋。對於它沒見過的 CLI，讓它參考 `--help` 就足夠了。

對於沒有 CLI 的系統，可以使用 [MCP](https://code.claude.com/docs/zh-TW/mcp.md)。您可以從 shell 新增伺服器：

```bash theme={null}
claude mcp add --transport http notion https://mcp.notion.com/mcp
```

之後該伺服器會出現在工作階段內的 `/mcp` 下。已連接的伺服器即使在您沒有使用時，也會將它們的工具名稱和指令加入上下文，因此值得在那裡[關閉您不需要的伺服器](https://code.claude.com/docs/zh-TW/mcp.md#disable-a-server-without-removing-it)。

如果您使用的是有型別的語言，[程式碼智慧外掛](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)能讓 Claude 直接跳到定義處，而不必翻閱許多檔案來尋找。

## 給 Claude 一個可執行的檢查

Claude 在工作看起來完成時就會停止。如果它沒有可以執行的東西來告訴它工作是否*真的*完成，那麼「看起來完成」就是它唯一的依據。實際上這會讓您成為測試套件，每個錯誤都會一直留在那裡，直到您碰巧注意到為止。

如果您給它一個會回傳通過或失敗的東西，Claude 就能自己完成這個迴圈。它會進行變更、執行檢查，如果有東西壞了，它會閱讀輸出並加以修復，然後再次執行檢查。

> [!TIP]
>
> 給 Claude 一個它可以執行且會回傳通過或失敗的東西。一旦有了這個，它就能自行持續進行，您也不必在旁盯著。

只要 Claude 能讀取結果，檢查幾乎可以是任何東西：

* 一個測試檔案
* 建置的退出碼
* Linter
* 將輸出與固定測試資料進行差異比對的指令碼
* 與設計稿並排的[瀏覽器螢幕擷取畫面](https://code.claude.com/docs/zh-TW/chrome.md)

如果您的儲存庫已經有其中之一，那麼 `CLAUDE.md` 中最有用的一行就是執行它的命令。

檢查要多嚴格由您決定。選項從由 Claude 自行決定，一路到由 Claude Code 強制執行：

* 在提示詞中：`run the auth tests after, and keep going until they pass`。由 Claude 自行決定何時滿意。這適用於任何任務，今天就能用，不需要任何設定。
* 作為目標：[`/goal all tests in tests/auth pass and lint is clean`](https://code.claude.com/docs/zh-TW/goal) 會設定一個條件，由另一個模型在每個回合後根據對話進行檢查，Claude 會持續工作直到條件達成。您在工作階段中自己很少需要這個。它對長時間的背景執行很重要，因為 Claude 有時會在仍有未完成項目時以進度摘要結束回合，而目標會把它送回去繼續工作。
* 作為 Stop hook：[`Stop` hook](https://code.claude.com/docs/zh-TW/hooks#stop) 會在 Claude 嘗試結束回合時執行您的指令碼，如果指令碼以退出碼 2 結束，就會讓 Claude 回去繼續工作。這是由 Claude Code（執行框架）強制執行的，因此在型別檢查通過或達到[封鎖上限](https://code.claude.com/docs/zh-TW/hooks.md#stop-input)之前，回合不會結束。[下方有範例](#enforce-the-check-with-a-stop-hook)。
* 由沒有撰寫程式碼的人審查：在終端機中，[`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) 會在一個從未看過您對話的全新 subagent 中審查差異。它不會受到產生程式碼時的推理所影響。

無論使用哪個選項，都請向 Claude 要求*證據*：它執行的命令及其輸出，或螢幕擷取畫面。單單一句「所有測試都通過」能告訴您的資訊很少，而閱讀輸出比自己重新執行檢查更快。對於您沒有在旁觀看的工作階段，這也是您唯一擁有的證據。

> [!TIP]
>
> Claude 說它完成後，您也可以在工作階段中執行 [`/verify`](https://code.claude.com/docs/zh-TW/skills#run-and-verify-your-app)，讓 Claude 建置並執行應用程式，然後查看結果。這能抓到測試和型別檢查會漏掉的問題。

### 依據您的規格進行審查

如果您希望審查是依據您的計畫檢查工作，而不是廣泛地尋找錯誤，請自己撰寫審查提示詞：

```text theme={null}
use a subagent to review the rate limiter diff against SPEC.md, check every requirement is implemented and the listed edge cases have tests, report gaps that affect correctness and skip style
```

> [!NOTE]
>
> 不要刪掉提示詞中的 `skip style` 部分。被要求找出問題的審查者一定會找到*某些東西*。如果您修正每一項發現，最後會得到多餘的抽象層，以及針對不可能發生之情況的測試。

### 使用 Stop hook 強制執行檢查

型別檢查規則的 `Stop` hook 版本只需要在 `.claude/settings.json` 中寫幾行。退出碼 2 會阻止停止。命令輸出到 stderr 的任何內容都會回傳給 Claude，作為它還不能完成的原因，這就是為什麼要將編譯器輸出重新導向到那裡：

```json .claude/settings.json theme={null}
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "pnpm tsc --noEmit 1>&2 || exit 2" }
        ]
      }
    ]
  }
}
```

若要看看它的效果，請要求 Claude 做一個會破壞型別的變更：它不會直接完成，而是收到編譯器錯誤並持續工作，直到 `tsc` 通過。如果 hook [連續封鎖八次停止](https://code.claude.com/docs/zh-TW/hooks.md#stop-input)且期間沒有任何工具呼叫，Claude Code 會覆寫下一次封鎖並結束回合。若要提高上限，請設定 [`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`](https://code.claude.com/docs/zh-TW/env-vars)。

## 強制執行不容例外的規則

> [!TIP]
>
> 如果某件事每次都必須發生，就把它做成 hook、拒絕規則或受管設定。`CLAUDE.md` 是用來放準則的，而 Claude 可以決定某項準則不適用。

以您現在可能寫在 `CLAUDE.md` 中的三條規則為例：`Never read .env`、`Always run the formatter after editing`、`Don't touch the migrations folder`。Claude 幾乎每次都會遵循這些規則。對於那些「幾乎」還不夠好的規則，請將它們從 `CLAUDE.md` 移到由 Claude Code（執行框架）自行套用的設定中。從此以後，結果就不再取決於模型記得什麼或決定什麼。

### 使用 hook 強制執行步驟

[Hook](https://code.claude.com/docs/zh-TW/hooks-guide.md) 會在 Claude 迴圈中的固定時間點執行您的某個東西：工具呼叫之前或之後、Claude 嘗試停止時、工作階段開始時等等。這個東西可以是：

* Shell 命令（一般情況）
* 對 HTTP 端點發送 POST
* 對您某個 MCP 伺服器的工具呼叫
* [`prompt` 或 `agent` hook](https://code.claude.com/docs/zh-TW/hooks#hook-handler-fields)，讓模型來決定

`prompt` 或 `agent` hook 是請*另一個模型*做決定，所以它也不是確定性的。若要真正強制執行，請使用 `command` 或 `http` hook，如果在 hook 本身當機或逾時時也應該阻止該動作，請加上 [`onFailure: "block"`](https://code.claude.com/docs/zh-TW/hooks#block-the-action-when-a-hook-fails)。例如，對於掃描提交中機密資訊的 hook，在掃描器故障時，您會寧願阻止提交，而不是讓它未經掃描就通過。

以下是以 `PostToolUse` hook 實作的格式化工具規則。它會在每次 `Edit` 或 `Write` 後執行，Claude 是否記得這條規則已經不重要了，因為執行它的不是 Claude：

```json .claude/settings.json theme={null}
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "npx prettier --write --ignore-unknown \"$(jq -r '.tool_input.file_path')\"" }
        ]
      }
    ]
  }
}
```

若要檢查這個 hook，請要求 Claude 在 Prettier 會格式化的檔案中加入一行縮排錯誤的程式碼。儲存後的檔案會以修正後的縮排呈現。

遷移規則則變成一個 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/hooks-guide#block-edits-to-protected-files)，對 `migrations/` 下的任何路徑以退出碼 2 結束。您不必自己撰寫：`write a hook that blocks edits to the migrations folder` 就能當作提示詞使用，而 `/hooks` 會顯示結果。不過不要過度使用：hook 是給*零*例外的規則用的，而 `Prefer named exports` 有很多例外，所以它應該留在 `CLAUDE.md` 中。

### 使用權限規則和沙箱限制存取

[權限規則](https://code.claude.com/docs/zh-TW/permissions.md)決定 Claude 可以執行、讀取和擷取什麼。`deny` 規則在每種權限模式中都有效，包括自動模式和 `bypassPermissions`，這正是 `.env` 規則應該放在那裡的原因：

```json .claude/settings.json theme={null}
{
  "permissions": {
    "allow": ["Bash(pnpm tsc --noEmit)"],
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)", "Read(./.env.local)", "Read(./secrets/**)"]
  }
}
```

儲存這個設定後，詢問 Claude `.env` 的內容會失敗，無論是透過 `Read` 工具還是透過 `cat .env` 都一樣。

規則比對的是工具呼叫，而不是意圖，所以值得了解它的邊界在哪裡：

* `Read` 規則*確實*會攔截 `cat .env`，因為 Claude Code 能辨識[常見的檔案讀取命令](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。
* 它不會攔截開啟該檔案的指令碼。
* 針對某個網域的 `WebFetch` 拒絕規則，對於以 `curl` 存取同一網域毫無作用，除非沙箱已開啟。

若要在作業系統層級限制檔案系統或網路存取，請在工作階段中使用 `/sandbox` 開啟[沙箱](https://code.claude.com/docs/zh-TW/sandboxing.md)。它會在 macOS、Linux 和 WSL2 上限制 Claude 的 shell 命令，而且也會[套用您的 `Read` 拒絕規則和 `WebFetch(domain:...)` 規則](https://code.claude.com/docs/zh-TW/sandboxing#permission-rules)，因此對於任何與安全相關的事項，您會希望兩者都使用。

預設情況下，Claude 仍然可以要求在沙箱外重試被封鎖的命令，而該請求會經過一般的權限流程。`/sandbox` **Overrides** 分頁中的[嚴格沙箱模式](https://code.claude.com/docs/zh-TW/sandboxing.md#turn-off-the-retry-with-strict-sandbox-mode)會關閉這種重試。

> [!WARNING]
>
> 自動模式是由分類器模型判斷每個動作，而不是硬性規則。它很擅長這件事，但就像任何判斷一樣，它也可能出錯。您也可以調整它認定為有風險的內容，而您的組織可以完全關閉它，所以您的「絕對不行」規則應該放在拒絕規則或 hook 中。

### 選擇規則適用的對象

規則放在哪裡，決定了它適用於誰：

* `.claude/settings.local.json` 和 `~/.claude/settings.json` 只屬於您自己。當您對某個命令選擇 **Yes, and don't ask again** 時，Claude Code 會將該規則儲存到本機檔案。
* `.claude/settings.json` 及其中的 hook 屬於儲存庫。提交之後，它們會適用於在該儲存庫中工作的每個人。其中的拒絕規則會立即生效。其中的 `allow` 規則會等到每個人接受該資料夾的[信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)後才生效，而[工作區信任](https://code.claude.com/docs/zh-TW/hooks.md#workspace-trust)也決定了其中的 hook 何時開始在他們的電腦上執行。
* [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)屬於組織。它們來自管理主控台、MDM 或 `managed-settings.json` 檔案，任何個人設定檔都無法覆寫它們，這使得它們成為安全團隊政策的唯一存放處。如果您是負責設定它們的人，請參閱[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)。

無論範圍為何，都請讓強制執行的項目保持精簡。每個 hook 和拒絕規則偶爾都會在不該觸發時觸發，而且每一項都需要有人維護。如果您發現自己累積了四十個，其中大多數可能都只是 Claude 本可以自行權衡的偏好。

## 變更預設值

> [!TIP]
>
> 預設值已經夠好，可以維持不動，直到某項任務花費的時間、token 或中斷超出應有的程度為止。發生這種情況時，請在工作階段中執行 `/usage` 查看花費去了哪裡。

新的工作階段已經替您做了幾項決定：

* 互動式終端機和 VS Code 工作階段以自動模式啟動。
* 在大多數方案和供應商上，它會執行[中等 effort 的 Claude Opus 5.5](https://code.claude.com/docs/zh-TW/model-config.md#default-model-setting)。
* 當它認為有理由時，會將工作委派給 subagent。
* 它會在對話增長時進行壓縮。

大多數時候您根本不會想到這些。當某項任務的花費確實超出應有的程度時，原因通常就是這四項之一。

### 變更權限模式

權限範圍的兩端都有代價：

* **手動模式**：您要親自核准每一次編輯和每一個非唯讀的命令。很安全，但到了第十個提示後，您就會開始不讀內容就核准，而且在您離開鍵盤時，一切都不會進展。
* **`bypassPermissions`**：核准所有不在您的拒絕和詢問規則涵蓋範圍內的操作，這只在可拋棄的容器中才合理。

[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)介於兩者之間，也是互動式終端機和 VS Code 工作階段[啟動時](https://code.claude.com/docs/zh-TW/permission-modes.md#which-mode-a-session-starts-in)使用的模式。Claude 在工作時不會為例行核准而停下來，而另一個分類器模型會在動作執行前依照[固定順序](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)檢查它們。它專注於[您會希望有人出面阻止的事情](https://code.claude.com/docs/zh-TW/permission-modes.md#what-the-classifier-blocks-by-default)：

* `curl | bash`
* 正式環境部署和遷移
* 強制推送覆蓋他人的工作
* 將敏感資料傳送到外部端點
* 看起來是由 Claude 讀取的內容而非由您驅動的動作

當自動模式封鎖某個動作時，您會收到通知，而該動作會顯示在 `/permissions` 中的 **Recently blocked** 下，您可以在那裡[核准該動作，讓 Claude 可以重試](https://code.claude.com/docs/zh-TW/auto-mode-config.md#review-denials)。在[連續封鎖三次](https://code.claude.com/docs/zh-TW/permission-modes.md#when-auto-mode-falls-back)（或總計二十次）之後，自動模式會暫停並改回詢問您。

這些都不會取代您的確定性控制，因為它是在確定性控制*之後*執行的。拒絕和詢問規則以及 `PreToolUse` hook 會在分類器看到任何內容之前套用，因此拒絕規則在自動模式中的封鎖效果與在其他地方完全相同。沙箱仍然會限制[它所包覆的 shell 命令](https://code.claude.com/docs/zh-TW/sandboxing.md#what-runs-outside-the-sandbox)。

> [!NOTE]
>
> 您也可以在對話中說 `don't push until I've reviewed`，分類器會[將其視為封鎖訊號](https://code.claude.com/docs/zh-TW/permission-modes.md#boundaries-you-state-in-conversation)。但這仍然是由模型閱讀逐字稿，而這句話可能會在對話壓縮時遺失，所以任何重要的事項都應該放在拒絕規則中。

相反的問題是分類器一再阻止在您環境中屬於例行的操作。與其每次都手動核准，不如將它加入 `autoMode.allow`，或在[自動模式設定](https://code.claude.com/docs/zh-TW/auto-mode-config.md)中描述您信任的基礎設施。它使用的是一般英文而非模式比對，而 [`/auto-mode-setup`](https://code.claude.com/docs/zh-TW/auto-mode-config#generate-environment-entries) 可以根據您的專案和最近的工作階段為您草擬 `environment` 部分：

```json ~/.claude/settings.json theme={null}
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Source control: github.com/example-org and every repo under it",
      "Trusted internal domains: *.internal.example.com"
    ],
    "allow": [
      "$defaults",
      "Deploying to the staging namespace is fine, it's isolated from production and resets nightly"
    ]
  }
}
```

> [!WARNING]
>
> 請在您設定的每個清單中保留 `"$defaults"`，因為如果沒有它，您的項目會*取代*該清單的內建規則，而不是新增到其中。對於 `environment` 和 `allow`，您會失去內建的上下文和例外，而沒有它的 `soft_deny` 清單則會移除針對強制推送和正式環境部署的內建封鎖。
>
> `autoMode` 區塊也必須放在 `~/.claude/settings.json` 中，而不是專案中，因為分類器會忽略專案設定中的 `autoMode`。

如果您希望在每次編輯和命令發生前都能看到它們，可以在工作階段中按 `Shift+Tab` 循環切換權限模式（包括手動模式），或從 shell 以 `claude --permission-mode manual` 啟動。而如果手動模式詢問得太頻繁，`/fewer-permission-prompts` 會掃描您最近的逐字稿，找出常見的唯讀 Bash 和 MCP 呼叫，並將它們加入 `.claude/settings.json` 中的允許清單。

### 變更模型和 effort

[Effort](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) 是控制 Claude 思考時間長短的主要方式，它取代了過去人們透過提示詞措辭所做的大部分事情。Claude Opus 5.5、Sonnet 5.5 和 Haiku 5.5 預設為 `medium`，這對於範圍明確的日常功能開發已經綽綽有餘。您會需要在工作階段中以 `/effort` 調整它的時機：

* 當做對與否取決於容易被忽略的情況時，用 `/effort high` 或 `/effort xhigh` 調高它。例如您沒寫過的程式碼中的錯誤、不穩定的測試，或是 Claude 必須找出舊結構所有讀取者的 schema 變更。這樣 Claude 會在回答之前檢查更多邊界情況並驗證更多工作，額外的時間和 token 就花在這裡。
* 當您正在快速來回互動且無論如何都會審查每個結果時，用 `/effort low` 調低它：腦力激盪、初步草稿、跨幾個檔案的重新命名。Claude 會更快給您一個起點，而既然您在每一步都會引導，額外的深思熟慮除了讓您等待更久之外，不會有太大改變。
* 將 `max` 留給您希望 Claude 在沒有您的情況下努力解決的困難問題，例如尋找安全漏洞。在一般任務上它容易想太多，所以您會付出更多，得到的答案卻可能不比 `high` 更好。
* 當只有下一則訊息需要時，例如在原本例行的工作中穿插一個棘手的問題，請在該提示詞中加入 [`ultrathink`](https://code.claude.com/docs/zh-TW/model-config#use-ultrathink-for-one-off-deep-reasoning)，而不是變更設定。

至於模型本身，預設的 Opus 5.5 能妥善處理大多數程式撰寫工作，而 Sonnet 在例行工作上成本較低。[Claude Fable 5.1](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable) 需要您以 `/model fable` 明確選取，而 Haiku 很適合做簡單工作的 subagent。[模型設定](https://code.claude.com/docs/zh-TW/model-config.md)列出了各方案和供應商的完整清單。

### 了解 subagent 的成本

Claude 會自行將工作委派給 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)：

* 大範圍的程式碼庫搜尋會交給內建的 Explore agent。
* 在分叉模式開啟時（預設），支線任務會被[分叉](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)出去。
* 它啟動的 subagent 預設在背景執行，因此您的主要對話可以持續進行。

您很少需要主動要求這些，但了解您得到什麼以及它的成本會有幫助。

Subagent 在以下情況能帶來效益：

* 同時執行獨立的工作片段，讓整個任務更快完成
* 將冗長的輸出（例如完整的測試執行或大範圍搜尋）排除在主要對話之外，否則它會在整個工作階段剩餘時間中一直跟著
* 取得一個沒看過程式碼撰寫過程的審查者
* 給予某項任務比主要工作階段更少的工具，例如只能讀取但不能編輯的審查者

它們的成本主要是 token，因為每個 subagent 都會發送自己的請求，而這些請求與您的主要對話計入相同的用量。有時也包括時間：全新的 subagent 必須先收集您的對話中已有的上下文，所以它最後可能比您直接在當下完成任務*更慢*。

而且預設情況下，它是同一個模型（或更小的模型）處理同一項任務。您能從中得到平行處理或一雙新的眼睛，但不會得到更聰明的答案。

若要減少它們的花費：

* 如果某個 subagent 的工作很簡單，例如收集匯入某個模組的檔案或檢查文件中的連結，請在其定義中設定 [`model: haiku`](https://code.claude.com/docs/zh-TW/sub-agents#choose-a-model)。這類工作不需要較大的模型，而 Haiku 每次請求的成本低得多。
* 要求回傳簡短的摘要，這樣二十個結果就不會塞滿您的上下文。
* 查看 `/usage`，了解每種 subagent 類型佔您用量的比例，藉此判斷哪些是值得其成本的。
* 為 `.claude/agents/` 中的自訂 subagent 只提供 `tools: Read, Grep, Glob`。如此它就成為一個無法編輯任何內容的審查者，而這項限制是由 Claude Code 強制執行的，而不是在提示詞中請求的。

這個審查者只是一個簡短的檔案，`.claude/agents/reviewer.md`：

```markdown .claude/agents/reviewer.md theme={null}
---
name: reviewer
description: Reviews changed files against the spec they were built from. Use after implementing a feature, before opening the PR.
tools: Read, Grep, Glob
---
You're reviewing code you didn't write. Compare the changed files against the spec you're given,
check that every requirement is implemented and the listed edge cases have tests,
and report only the gaps that affect correctness. Skip style.
```

請 Claude `have the reviewer compare the rate limiter against SPEC.md`，缺漏就會回到您的工作階段中，讓 Claude 加以修正。

### 降低成本和上下文

大多數目前的模型都有 1M token 的視窗，而且壓縮會在接近上限時進行，因此您很少會用完上下文。不過，您仍然可能為不需要的上下文*付費*。每個請求都會傳送整個對話，所以一個累積了三項不相關任務的工作階段，在第四項任務的每個回合都會重新讀取這三項。在[快取仍有效時會有折扣](https://code.claude.com/docs/zh-TW/costs.md#why-usage-climbs-in-a-long-session)，快取過期後則是全價。

[`/usage`](https://code.claude.com/docs/zh-TW/costs) 是第一個要查看的地方。在 Pro、Max、Ultra、Team 和 Enterprise 上，它會依 skill、subagent、外掛和 MCP 伺服器細分您的用量。當長上下文或頻繁的快取未命中等模式超過您用量的 10% 時，它也會標記出來。接下來是常見的解決方式：

* 在不相關的任務之間使用 `/clear`。它不需要任何成本，而且意味著下一項任務不必持續為前一項任務的歷史付費。`/clear oauth-migration` 會為您要離開的工作階段命名，讓您之後可以回來。
* 帶著重點使用 `/compact`，例如 `/compact keep the API changes and the test commands`。在長時間的工作階段中，`/compact` 本身就是一個大型請求，因為它要讀取整個對話才能進行摘要，快取過期後更是如此。
* 留意背景工作：`/loop`、目標在每個回合後的檢查，以及 Claude 自己的 subagent，都會在您沒有輸入時持續發送請求。

> [!NOTE]
>
> [提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)在訂閱方案上約持續一小時，在 API 金鑰、雲端供應商或用量點數上則是五分鐘。除非您變更設定，否則 subagent 的快取為五分鐘。
>
> 在一小時快取的情況下，超過約 200K token 且閒置的工作階段會在快取過期前不久被壓縮，所以午餐後回來時，您會從摘要繼續。如果您完全不需要歷史紀錄，開啟新的工作階段仍然比較便宜。

## 引導工作階段

> [!TIP]
>
> 觀察第一分鐘，在 Claude 偏離方向時立即按 `Esc`，在兩次修正失敗後執行 `/clear` 並寫一個更好的提示詞，而不是進行第三次修正。

再多的設定也無法取代觀察第一分鐘，並在 Claude 朝著您不想要的方向前進時介入。這方面的控制方式只有少數幾個，值得熟記：

* `Esc` 會讓 Claude 在動作途中停下，並保留到那一刻為止的所有內容，讓您可以重新導向而不會失去工作成果。
* `/rewind`，或在空白提示下按兩次 `Esc`，會開啟[倒帶選單](https://code.claude.com/docs/zh-TW/checkpointing.md#rewind-and-summarize)，您可以在那裡將程式碼、對話或兩者都回復到先前的提示詞。這使得先嘗試較大膽的做法、不成功再倒帶變得低風險。同一個選單也可以在部分對話已經過時時將其摘要。
* `/clear` 會重新開始。如果您已經修正同一件事兩次而它仍然是錯的，第三次修正大多只是增加到一個已經包含兩次失敗嘗試的對話中，而 Claude 必須一直重新讀取這些內容。`/clear` 加上一個納入您所學內容的新提示詞，幾乎每次都效果更好。

> [!WARNING]
>
> 檢查點涵蓋 Claude 在主要對話中以其自身檔案工具編輯的檔案，因此只被 Bash 命令動過的檔案[不會被還原](https://code.claude.com/docs/zh-TW/checkpointing.md#bash-command-changes-not-tracked)。它們與 git 搭配使用，而不是取代 git。

另外兩個較小的控制：[`/btw`](https://code.claude.com/docs/zh-TW/interactive-mode#side-questions-with-%2Fbtw) 可以回答快速問題而不在歷史中加入任何內容。而對於跨越數天的工作，在工作階段中使用 `/rename oauth-migration` 為它命名，之後從 shell 執行 [`claude --resume oauth-migration`](https://code.claude.com/docs/zh-TW/sessions#resume-by-session-id-or-name) 就能接續，檢查點也包含在內。`claude --continue` 會繼續最近的一個工作階段。

## 讓 Claude 在您不在時執行

> [!TIP]
>
> 在執行進入無人值守狀態之前，請確保它知道完成是什麼樣子、能檢查自己的工作，而且只能觸及它應該觸及的東西。給它回合數或花費的上限，並在最後讓一個人核准結果。

當您不在場捕捉錯誤時，本頁的所有內容都會變得更重要一些。在您觀看時，Claude 缺少某些上下文不是什麼大問題：您會在一兩則訊息內注意到並告訴它。但在您睡前啟動的執行中，沒有人會告訴它，而您會在隔天早上發現它整晚都在錯誤的假設上打造東西。

在讓任務自行執行之前，值得針對該特定任務逐一檢視以下五個問題：

1. 它知道完成是什麼樣子嗎？一個目標條件、一份規格檔案，或一個它必須讓其通過的失敗測試。
2. 它能檢查自己的工作嗎？測試套件、`Stop` hook、某種審查步驟。
3. 它被允許觸及什麼？權限規則、`dontAsk`、沙箱、worktree、它唯一可以推送的分支。
4. 什麼會讓它停下？`--max-turns`、`--max-budget-usd`、支出上限。
5. 結果會送到哪裡，由誰簽核？一個 PR、一則留言或一份摘要，然後由一個人核准合併、部署，或任何其他無法撤回的動作。

一旦開始執行，Claude 就會自行完成一項長時間的任務。留給您的部分是啟動它、決定這次「完成」的意義，以及在最後核准合併。

### 從指令碼執行 Claude

[`claude -p "prompt"`](https://code.claude.com/docs/zh-TW/headless) 會執行一次後結束，Claude Code 就是這樣被用在 CI 作業、git hook 和 shell 迴圈中。

在指令碼中，您幾乎總會需要多加幾個旗標：

* [`--bare`](https://code.claude.com/docs/zh-TW/headless#start-faster-with-bare-mode) 會略過 hook、skill、外掛、MCP 伺服器和 `CLAUDE.md` 檔案（包括儲存庫的以及電腦的），讓執行無論在哪裡執行都做同樣的事。它也完全不會動到您的 claude.ai 登入：身分驗證來自 `ANTHROPIC_API_KEY`、您以 `--settings` 傳入的檔案中的 `apiKeyHelper`，或您雲端供應商的憑證。
* `--append-system-prompt`、`--mcp-config` 和 `--settings` 會明確傳入執行*確實*需要的東西。
* `--allowedTools` 會預先核准它的工具，而 [`--permission-mode dontAsk`](https://code.claude.com/docs/zh-TW/permission-modes#allow-only-pre-approved-tools-with-dontask-mode) 會拒絕其他任何原本會觸發提示的操作。
* `--output-format json` 會給您一個可供剖析的單一結果物件，而搭配 `--verbose` 的 `stream-json` 會在事件發生時即時串流。

組合起來看起來像這樣：

```bash theme={null}
for file in $(cat files.txt); do
  claude --bare -p "Migrate $file to the new logger API and commit. Reply OK or FAIL." \
    --allowedTools "Read,Edit,Bash(git add *),Bash(git commit *)" \
    --permission-mode dontAsk \
    --max-turns 20
done
```

執行完成時，Claude 會回覆 `OK` 或 `FAIL`，而達到回合上限的執行則會以錯誤結束。請先在三個檔案上試試看，看看哪裡出錯，修正提示詞，然後再執行其餘檔案。

如果您傳入 `--permission-mode auto`，自動模式也能搭配 `-p` 使用。在非互動式執行中，分類器的封鎖會拒絕該單一動作，而 Claude 會繼續進行，重複的封鎖也不會像在終端機中那樣暫停執行。在依賴它之前，請先閱讀[門檻在該情況下如何套用](https://code.claude.com/docs/zh-TW/permission-modes.md#repeated-block-thresholds)。

### 依排程或事件啟動執行

一旦執行開始，Claude 就能自行處理其餘部分。它唯一做不到的是決定*開始*，所以必須有某個東西來啟動：您、計時器，或是像 CI 檢查失敗或新 PR 這類的事件。

在開啟的工作階段內，那就是 [`/loop`](https://code.claude.com/docs/zh-TW/scheduled-tasks#run-a-prompt-repeatedly-with-%2Floop)，它會依間隔重複執行一個提示詞：

```text theme={null}
/loop 15m check CI on this branch, and if it's red pull the failing job's log, fix it and push
```

每次執行都是同一個工作階段中的另一個回合，所以不要在長對話中讓它一直執行。對於任何應該在您筆電闔上時進行的事情，[`/schedule`](https://code.claude.com/docs/zh-TW/routines#create-from-the-cli) 會設定一個依計時器執行的[雲端排程任務](https://code.claude.com/docs/zh-TW/routines.md)。它需要 claude.ai 登入，而不是 API 金鑰。您可以請 Claude 新增 GitHub 事件觸發條件，或在 [claude.ai/code/routines](https://claude.ai/code/routines) 新增 API 觸發條件。

> [!WARNING]
>
> 在讓雲端排程任務持續執行之前，請以[任務無法繞過的 GitHub 分支規則](https://code.claude.com/docs/zh-TW/routines.md#repositories-and-branch-permissions)保護 `main`。對於任何新的東西，請先觀察最初幾次執行，再放心讓它無人值守。

### 平行執行工作階段

當您同時進行多項獨立的工作時，請為每一項提供自己的檢出，讓編輯不會互相衝突。[`claude -w feature-auth`](https://code.claude.com/docs/zh-TW/worktrees#start-claude-in-a-worktree) 會在新的 worktree 中啟動工作階段，[桌面應用程式](https://code.claude.com/docs/zh-TW/desktop.md#work-in-parallel-with-sessions)可以並排執行多個這樣的工作階段，而[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)則是在雲端而非您的電腦上執行它們。

Worktree 是全新的檢出，這意味著像 `.env` 這樣被 gitignore 的檔案不會在那裡，相依套件也尚未安裝。對於前者，請在儲存庫根目錄的 [`.worktreeinclude`](https://code.claude.com/docs/zh-TW/worktrees#copy-gitignored-files-into-worktrees) 中列出您需要的被 gitignore 檔案（語法與 `.gitignore` 相同），Claude Code 就會將它們複製到它建立的每個 worktree 中：

```text .worktreeinclude theme={null}
.env
.env.local
config/dev-credentials.json
```

只放小檔案：它是複製而不是連結，所以把 `node_modules` 放在裡面就意味著每個 worktree 都要完整複製一份。對於大型目錄，可以使用 [`worktree.symlinkDirectories`](https://code.claude.com/docs/zh-TW/settings-reference#worktree-symlinkdirectories) 設定，或將安裝命令寫在 `CLAUDE.md` 中，讓 Claude 每次在新的檢出中啟動時都會執行它。

您很少需要自己清理這些：

* 當您結束一個未命名的 worktree 工作階段時，如果其中沒有任何內容，Claude Code 會[移除該 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#clean-up-worktrees)。對於已命名的工作階段或有變更的工作階段，它會詢問要怎麼做。
* Subagent 的 worktree 會在 subagent 完成且沒有變更時消失。
* 確實被遺留下來的 subagent 和背景工作階段 worktree，會在存在時間超過 `cleanupPeriodDays` 且不含任何工作時被清除。

> [!NOTE]
>
> `claude -p --worktree` 執行需要您自己清理，因為它結束時不會詢問。請使用 `git worktree remove <path>` 移除它們，如果 git 因為 worktree 被鎖定而拒絕，請先執行 `git worktree unlock <path>`。

對於跨越許多檔案的單一大型機械式變更，[`/batch migrate every handler to the v2 response helpers`](https://code.claude.com/docs/zh-TW/commands) 會將工作分成 5 到 30 個單元，並向您展示計畫。您核准後，每個單元都會取得自己的 worktree，並開啟一個 PR 或回報發生的情況。從您的 shell 執行 [`claude agents`](https://code.claude.com/docs/zh-TW/agent-view)（仍為研究預覽）可以在一個畫面中查看您電腦上所有在背景執行的內容。

第二個工作階段也是您能取得的最簡單的獨立審查者。一個工作階段撰寫速率限制器，另一個在沒有看過撰寫過程的情況下審查 `@src/middleware/rateLimiter.ts`，然後您將發現貼回第一個工作階段。這與 `/code-review` 的概念相同，只是由您傳遞訊息。

## 可以停止做的事

以下每一項在撰寫時都是好建議。大多數是為了彌補模型當時還無法可靠做到的事，而模型現在已經趕上了。如果其中幾項仍是您的習慣，以下說明為什麼可以安心捨棄它們。

| 舊建議 | 為什麼不再需要 |
| :- | :- |
| 上下文視窗是您的主要限制，要積極管理它 | 大多數目前的模型都有 1M token 的視窗，而且壓縮會自動進行，所以用完的情況很少見。在任務之間使用 `/clear` 仍然值得，因為專注的上下文能帶來更好的答案且成本更低。 |
| 對 Claude 一直漏掉的指令加上 IMPORTANT 或全大寫 | 較舊的模型有時需要這種強調。目前的模型會遵循措辭平實的一行，而堆疊強調大多只會讓 Claude 過度套用規則。如果它是不能變通的規則，請將它改成 hook 或拒絕規則。如果那一行在長檔案中被淹沒了，需要的是讓檔案更短。 |
| 使用 subagent 來保護您的上下文視窗 | 用完上下文已經很少是問題了。Subagent 仍然很適合平行工作、將嘈雜的輸出排除在外，以及獨立審查，但每一項都需要額外的 token。 |
| 委派給 subagent 以得到更好的答案 | 將同一項任務交給 subagent 並不會讓答案變得更好。全新的審查者確實有幫助，因為它沒看過您的推理，但這與委派是不同的事。 |
| 在提示詞中使用 `think hard`、`think harder`、`be thorough` | Effort 才是控制這件事的方式。這些詞句是一般的提示詞文字，只會在 effort 設定範圍內稍微引導 Claude，而不是能提高 effort 的關鍵字。`ultrathink` 仍然有效：它會在該單一回合要求更深入的推理，而不會動到您的 effort 設定。 |
| 告訴 Claude 繼續、迴圈直到完成、不要偷懶 | 目前的模型通常會在不被告知的情況下持續完成已說定的任務，而這類語句更可能導致過度工作，而不是解決停滯。給 Claude 一個要通過的檢查則是另一回事，仍然值得去做。如果某次執行確實提前停止，請說 `continue`，而對於沒有人觀看的執行，`/goal` 或 `Stop` hook 會強制執行。 |
| 在 `CLAUDE.md` 中描述您的架構和檔案配置 | Claude 會自己閱讀儲存庫。只寫下儲存庫中沒有的內容。 |

如果本頁的任何其他建議開始讓您覺得是瑣碎的雜事，那可能表示它也應該被列入這張表中。

## 相關資源

* [Claude Code 如何運作](https://code.claude.com/docs/zh-TW/how-claude-code-works.md)：迴圈、工具，以及啟動時載入的內容
* [探索上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)：工作階段中佔用空間的內容及其載入時機
* [擴充 Claude Code](https://code.claude.com/docs/zh-TW/features-overview.md)：在 skill、hook、MCP、subagent 和外掛之間做選擇
* [選擇權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)和[設定權限](https://code.claude.com/docs/zh-TW/permissions.md)
* [有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)
* [以程式方式執行 Claude Code](https://code.claude.com/docs/zh-TW/headless.md)和[使用雲端排程任務自動化工作](https://code.claude.com/docs/zh-TW/routines.md)
* 給團隊主管和管理員：[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)
