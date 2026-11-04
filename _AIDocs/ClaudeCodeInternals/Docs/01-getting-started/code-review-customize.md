<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/code-review-customize | lastmod: 2026-10-24 | section: Getting started / Code review and pull requests -->
> 來源：https://code.claude.com/docs/zh-TW/code-review-customize（官方 zh-TW，lastmod 2026-10-24）｜分類：Getting started › Code review and pull requests｜EN 摘要：Tune what Code Review flags on your pull requests with REVIEW.md and CLAUDE.md: recalibrate severity, skip paths, add checks, and see which copy applies.

# 自訂 Code Review

> 使用 REVIEW.md 和 CLAUDE.md 調整 Code Review 在您的 pull request 上標記的內容：重新校準嚴重程度、略過路徑、新增檢查，並了解套用的是哪一份副本。

您可以透過將指令提交到儲存庫，來變更 [Code Review](https://code.claude.com/docs/zh-TW/code-review.md) 在該儲存庫上標記的內容。這是減少 nit 數量、停止在產生的檔案上留言，或新增團隊重視之規則的方式。請將指令放在以下兩個檔案之一：

* **`CLAUDE.md`**：Claude Code 在每項任務（包括審查）中都會讀取的[專案指令](https://code.claude.com/docs/zh-TW/memory.md)。Code Review 會將其作為專案脈絡讀取，並標記違反這些指令的變更。
* **`REVIEW.md`**：僅用於審查的指令。用它來說明您的團隊希望標記哪些內容、以何種嚴重程度標記，以及要略過哪些內容。

在儲存庫根目錄新增 `REVIEW.md` 並合併。接著[保護您的預設分支](#which-branch-review-md-is-read-from)。

> [!NOTE]
>
> 若要變更審查的詳盡程度或執行時機，請要求 Owner 變更[審查等級](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-the-default-review-level)或 [**Review runs** 設定](https://code.claude.com/docs/zh-TW/code-review-setup.md#set-when-reviews-run)。

## 使用 CLAUDE.md 設定全專案規則

Code Review 會將儲存庫中的 `CLAUDE.md` 檔案作為專案脈絡讀取。違反其中任一規則的變更，會成為一項發現，並依問題套用適當的[嚴重程度等級](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#severity-levels)。

審查會讀取儲存庫根目錄的 `CLAUDE.md`，以及每個變更檔案之上層目錄中的 `CLAUDE.md` 檔案。當 pull request 變更某個子目錄路徑下的檔案時，就會讀取該子目錄的 `CLAUDE.md`。

## 使用 REVIEW\.md 設定僅限審查的規則

`REVIEW.md` 是位於儲存庫根目錄的檔案，可依您的儲存庫量身調整 Code Review。您也可以在子目錄中新增 `REVIEW.md`，在根目錄檔案之外，針對該路徑下的變更新增檢查。

負責找出問題的 agent 與負責驗證問題的 agent，都會收到其內容作為您儲存庫的審查指令，並搭配 Code Review 的預設審查指引。撰寫最終審查的步驟，會在確定嚴重程度與撰寫摘要之前參考此檔案。

以下範例配置包含一個根目錄檔案和一個子目錄檔案：

```text theme={null}
your-repo/
├── REVIEW.md            # Root file
├── services/
│   └── billing/
│       └── REVIEW.md    # Adds checks for changes under services/billing/
└── src/
```

在依賴子目錄檔案之前，請先保護您的預設分支，並檢查[您的分支設定下審查會讀取哪些內容](#what-a-review-reads-for-each-branch-setup)。

> [!NOTE]
>
> Code Review 服務與本機的 [`/code-review` 命令](https://code.claude.com/docs/zh-TW/code-review-local)是兩個獨立的工具，讀取的檔案也不同。服務會同時讀取 `CLAUDE.md` 和 `REVIEW.md`。`/code-review` 命令是在您自己電腦上的 Claude Code 工作階段中執行，它會讀取您的 `CLAUDE.md` 檔案，但不會讀取 `REVIEW.md`。請將希望在兩處都套用的指引放在 `CLAUDE.md` 中，並將 `REVIEW.md` 保留給 pull request 審查專屬的規則。

### REVIEW\.md 範例

此 `REVIEW.md` 為後端服務重新校準嚴重程度、限制 nit 數量、略過產生的檔案，並新增儲存庫專屬的檢查。

```markdown theme={null}
# Review instructions

## What Important means here

Reserve Important for findings that would break behavior, leak data,
or block a rollback: incorrect logic, unscoped database queries, PII
in logs or error messages, and migrations that aren't backward
compatible. Style, naming, and refactoring suggestions are Nit at
most.

## Cap the nits

Report at most five Nits per review.

## Do not report

- Anything CI already enforces: lint, formatting, type errors
- Generated files under `src/gen/` and any `*.lock` file
- Test-only code that intentionally violates production rules

## Always check

- New API routes have an integration test
- Log lines don't include email addresses, user IDs, or request bodies
- Database queries are scoped to the caller's tenant
```

### 決定在 REVIEW\.md 中撰寫的內容

`REVIEW.md` 是自由格式的 Markdown，可變更審查所發現與回報的內容。它不會變更審查的格式。找出您遇到的問題，然後新增如下所示的指令。[範例](#example-review-md)使用了前四項。

* **錯誤的項目被標記為 Important**：為您的儲存庫重新定義 🔴 Important 的意義。預設校準以正式環境程式碼為目標，而文件儲存庫、設定儲存庫或原型可能需要範圍窄得多的定義。請說明哪些類別的發現屬於 Important，哪些最多只算 Nit。您也可以提高等級，例如將任何違反 `CLAUDE.md` 的情況視為 Important。
* **nit 太多**：限制單次審查張貼的 🟡 Nit 留言數量。例如「最多回報五個 nit」這樣的上限，能讓審查保持可據以行動。
* **在產生的檔案或 CI 已檢查的項目上留言**：列出 Claude 應略過發現的路徑與發現類別。常見的候選項目包括產生的程式碼、lockfile 和 vendored 相依套件，以及 CI 已強制執行的任何項目，例如 linting 或拼字檢查。對於值得某種程度審查但不需完整檢視的路徑，請改為設定較高的門檻：「在 `scripts/` 中，僅在幾乎確定且嚴重時才回報。」
* **團隊規則未被檢查**：新增您希望在每個 pull request 上標記的規則，例如「新的 API 路由必須有整合測試」。
* **結果證明有誤的發現**：要求某類發現在張貼前必須提供證據。例如，「行為相關的主張需要在原始碼中提供 `file:line` 引用，而非從命名推論」，可減少誤報，避免作者因此多花一次往返。

其中部分指令[需要根目錄檔案位於受保護的預設分支上](#which-branch-review-md-is-read-from)。

請讓 `REVIEW.md` 只包含會改變審查行為的指令，並將一般專案脈絡留在 `CLAUDE.md` 中。

### 在 REVIEW\.md 中納入其他檔案

您可以將審查指令拆分到多個檔案中，再將它們引入根目錄的 `REVIEW.md`。當 `REVIEW.md` 變得冗長，或您已經將審查規則保存在其他檔案中時，可以使用此方式。

若要納入檔案，請在根目錄的 `REVIEW.md` 中新增一行，該行只包含 `@` 和檔案名稱。Code Review 會以該檔案的內容取代這一行，因此這些內容會作為 `REVIEW.md` 的一部分套用。在此範例中，根目錄檔案提供了一條自己的指令，然後納入兩個規則檔案：

```markdown theme={null}
# Review instructions

Report at most five Nits per review.

@review-security.md
@review-api.md
```

請將被納入的檔案儲存在儲存庫根目錄，與 `REVIEW.md` 放在一起：

```text theme={null}
your-repo/
├── REVIEW.md
├── review-security.md
└── review-api.md
```

Code Review 從受保護分支讀取 `REVIEW.md` 時才會納入這些檔案，因此請檢查[審查會為您的儲存庫讀取哪個分支](#what-a-review-reads-for-each-branch-setup)：

* **受保護分支**：Code Review 會以被納入的檔案取代其 `@` 行
* **未受保護的預設分支**：`@` 行會以純文字形式保留在 `REVIEW.md` 中。如果 pull request 變更了該行所指名的檔案，該行會被略去。

當審查未套用被納入的檔案時，請逐一檢查下列項目：

* **位置**：將檔案移至儲存庫根目錄。除了 [skill 檔案](#include-a-skill-file)之外，指向子目錄的路徑，例如 `@docs/review-rules.md`，不會被納入。
* **名稱**：檔案名稱必須完全相符（包括大小寫），並使用不含空格的名稱。如果某一行的名稱與 `REVIEW.md` 旁的任何檔案都不相符，該行會以純文字形式保留在 `REVIEW.md` 中，而檢查執行不會將其回報為已略過的納入。
* **僅限一層**：請在根目錄的 `REVIEW.md` 中列出每個檔案。被納入的檔案或子目錄 `REVIEW.md` 中的 `@` 行會保留為純文字（[skill 檔案則不同](#include-a-skill-file)），而指向其他檔案的 Markdown 連結也不算是納入。
* **限制**：最多納入八個不同的檔案，並讓 `REVIEW.md` 及其納入的檔案合計小於 150,000 位元組。會使總量達到位元組上限的檔案會被整個略過，而不是被截斷。檢查執行會回報因任一限制而略過了多少個納入行。
* **連結**：`REVIEW.md` 及其納入的檔案中，Markdown 連結總數請保持在 64 個以內。指向 `http`、`https` 或 `mailto` 位址以及 `#` 錨點的連結不計入，[skill 檔案](#include-a-skill-file)中的連結也不計入。超過此限制時，審查會略過您整個根目錄 `REVIEW.md`，而不只是被納入的檔案。檢查執行接著會[說明指令未被套用](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#the-check-run-mentions-review-md)。
* **已合併的副本**：將被納入的檔案合併到[讀取 `REVIEW.md` 的分支](#which-branch-review-md-is-read-from)。審查會從同一個提交讀取兩者，絕不會從 pull request 本身的變更中讀取。

### 納入 skill 檔案

若要讓審查遵循您保存在 [skill](https://code.claude.com/docs/zh-TW/skills.md) 中的指引，請在根目錄的 `REVIEW.md` 中納入該 skill 的 `SKILL.md`。Code Review 不會執行 skill。

請在獨立的一行中加入 `@` 以及 `SKILL.md` 的路徑，格式為 `.claude/skills/<folder>/SKILL.md`：

```markdown theme={null}
# Review instructions

Report at most five Nits per review.

@.claude/skills/api-review/SKILL.md

Treat any change under `migrations/` as Important.
```

請保護[讀取 `REVIEW.md` 的分支](#which-branch-review-md-is-read-from)，因為 Code Review 只有在從受保護分支讀取 `REVIEW.md` 時才會納入 skill 檔案。skill 檔案會計入八個檔案與 150,000 位元組的限制，並另有 30,000 位元組的專屬限制。

#### 撰寫 Code Review 會納入的 skill 行

請使用不含空格的資料夾名稱。路徑中含有空格的行會以純文字形式保留在 `REVIEW.md` 中，而檢查執行不會將其回報為已略過的納入。

如果 skill 的 `@` 行違反下列任一規則，Code Review 就不會從該行納入此 skill：

* **路徑**：以儲存庫根目錄為起點，將路徑寫成 `.claude/skills/<folder>/SKILL.md`，且 skill 的資料夾須直接位於 `skills/` 之下。與根目錄中的檔案名稱不同，此格式的路徑若不符合任何檔案，會被略過並計入。
* **來源**：將 `.claude/` 下任何其他檔案，或[內建、個人或外掛 skill](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live) 中的指引，複製到 `REVIEW.md` 旁的檔案中。您無法直接納入這些內容。
* **檔案**：將 `SKILL.md` 以一般文字檔的形式提交。Code Review 不會追蹤符號連結，無論該連結是檔案本身還是其路徑中的資料夾。
* **大小**：讓 `SKILL.md` 保持在 30,000 位元組以內（包含 frontmatter）
* **數量**：最多撰寫八個 skill 行。重複的行會再次計入這八個之中。
* **`REVIEW.md` 中的區塊**：不要將 `@` 行放在程式碼圍欄內。請關閉其上方的每個 HTML 註解，以及每個 `<pre>`、`<script>`、`<style>` 或 `<textarea>` 區塊。

當 Code Review 因違反「檔案」、「大小」、「數量」或「區塊」規則而略過 skill 行時，檢查執行的[略過納入行相關訊息](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#the-check-run-mentions-review-md)會將其計入。此訊息只會在審查套用來自受保護分支的 `REVIEW.md` 時出現。

#### 檢查審查從 skill 取得的內容

納入 skill 時，審查只會取得 `SKILL.md` 的本文，而不會取得 skill 中的其他任何內容，因此請依下列清單檢查 skill。

* **Frontmatter**：將審查所需的任何 [frontmatter](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference) 內容在本文中重述，例如 `description` 中提供的 skill 使用條件
* **注入的命令**：將 [`!` 命令](https://code.claude.com/docs/zh-TW/skills#inject-dynamic-context)會提供的內容明確寫出。Code Review 不會執行該命令，並會以預留位置取代包含該命令的整行或整個區塊。
* **替換**：將 `$ARGUMENTS` 及其他[替換](https://code.claude.com/docs/zh-TW/skills.md#available-string-substitutions)改為固定文字，因為審查不會傳遞任何引數，並會讓它們維持原樣
* **輔助檔案**：將審查所需的內容複製到 `SKILL.md` 中，因為 Code Review 不會載入腳本、連結的檔案或 `@file` 參照
* **排除與 Nit 上限**：將排除發現或限制 Nit 數量的指令寫在 `REVIEW.md` 或其旁邊的檔案中，而不是寫在 skill 中。Code Review 不會接受 skill 的文字作為兩者任一的依據。
* **指向儲存庫檔案的連結**：以文字說明連結或 `@file` 參照所指向的內容。審查看到的路徑會是純文字或預留位置。

如果您編輯 skill 的 `!` 命令、`$ARGUMENTS` 或連結，也會改變它在 Claude Code 中的運作方式。如果您的團隊依賴這些功能，請將指引複製到 `REVIEW.md` 旁的檔案中，並改為納入該檔案，而非 skill。

#### Code Review 在 skill 文字中變更的字元

Code Review 會變更 skill 文字中的部分字元，因此您的程式碼範例會以下列形式送達審查。

```text theme={null}
In SKILL.md:       Use `items[0]`, never `List<String>`.
The review reads:  Use ˋitems(0)ˋ, never ˋList< String>ˋ.

In SKILL.md:       Run `ps | grep api` and ask @alice.
The review reads:  Run ˋps ¦ grep apiˋ and ask @ alice.
```

若某條規則依賴這些字元之一，也請以文字加以說明。

### 從哪個分支讀取 REVIEW\.md

Code Review 會從 pull request 的基礎分支或預設分支讀取 `REVIEW.md`，絕不會從 pull request 本身的變更中讀取。若要變更審查行為，請先合併 `REVIEW.md` 的變更。

請將 `REVIEW.md` 保留在預設分支上，並保護該分支。當審查讀取的是受保護預設分支上的副本（即下表第一列）時，會遵循根目錄檔案中的下列指令：

* 降低發現的嚴重程度
* 排除路徑、檔案或問題類別
* 限制 nit 留言數量

請將排除與 Nit 上限寫在 `REVIEW.md` 或其旁邊的檔案中，而不是寫在[被納入的 skill](#include-a-skill-file) 中。

#### 哪些設定算是分支保護

Code Review 將下列設定視為保護：

* **預設分支**：傳統分支保護規則或 ruleset
* **任何其他分支**：僅限 ruleset

當 ruleset 限制更新，或要求 pull request 至少取得一次核准時，即視為保護。如果它要求 pull request，還必須在有新推送時撤銷該核准，或要求核准須在最後一次推送之後取得。

#### 各種分支設定下審查會讀取的內容

請在下表第一欄中找出您儲存庫的情況。

| 分支保護 | 讀取的副本 | 讀取的檔案 |
| :- | :- | :- |
| 預設分支受保護，且 pull request 的目標是預設分支，或是未受任何 ruleset 保護的分支 | 預設分支 | 根目錄檔案、其納入的檔案，以及子目錄檔案 |
| pull request 的目標是受 ruleset 保護的其他分支 | 該基礎分支 | 根目錄檔案、其納入的檔案，以及子目錄檔案 |
| 預設分支未受保護，且基礎分支沒有任何一種保護規則 | 預設分支 | 根目錄檔案 |
| Code Review 無法確認保護設定。這包括預設分支未受保護、而基礎分支僅有傳統規則的情況 | 無 | 無 |

如果檢查執行提及 `REVIEW.md`，請參閱[檢查執行提及 REVIEW.md](https://code.claude.com/docs/zh-TW/code-review-troubleshooting.md#the-check-run-mentions-review-md)。

## 相關資源

* [Code Review](https://code.claude.com/docs/zh-TW/code-review.md)：此服務是什麼，以及審查如何執行
* [在 pull request 上閱讀與請求審查](https://code.claude.com/docs/zh-TW/code-review-pull-requests.md#severity-levels)：各嚴重程度等級的意義，以及發現如何呈現
* [設定 Code Review](https://code.claude.com/docs/zh-TW/code-review-setup.md)：由 Owner 設定的審查等級與審查執行時機
* [使用 `/code-review` 在本機審查](https://code.claude.com/docs/zh-TW/code-review-local)：`/code-review` 命令、其引數與 effort 等級
* [記憶](https://code.claude.com/docs/zh-TW/memory.md)：`CLAUDE.md` 檔案在 Claude Code 中的運作方式
