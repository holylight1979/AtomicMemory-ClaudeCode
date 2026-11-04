<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/large-codebases | lastmod: 2026-11-04 | section: Build with Claude Code / Guides -->
> 來源：https://code.claude.com/docs/zh-TW/large-codebases（官方 zh-TW，lastmod 2026-11-04）｜分類：Build with Claude Code › Guides｜EN 摘要：Configure Claude Code for monorepos and large single-tree codebases with nested CLAUDE.md files, sparse worktrees, code intelligence, and per-package skills so Claude stays focused on the code you're working in.

# 在 monorepo 或大型程式碼庫中設定 Claude Code

> 使用巢狀 CLAUDE.md 檔案、稀疏 worktrees、程式碼智能和按套件技能為 monorepos 和大型單樹程式碼庫設定 Claude Code，讓 Claude 專注於您正在處理的程式碼。

大型程式碼庫可以是擁有數百萬行程式碼的單一儲存庫，也可以是擁有許多套件的 monorepo。Claude Code 可在任何規模下運作，但隨著程式碼庫的增長，針對較小專案調整的預設設定可能會用與任務無關的指令和檔案讀取填滿上下文視窗，浪費 tokens 並降低 Claude 的效能。

本指南向個別開發人員和工程團隊展示如何將 Claude 的範圍限制在任務涉及的程式碼庫部分。每個部分都會說明設定是個人設定還是提交到儲存庫。

## 本指南涵蓋的內容

下方的[表格](#settings-on-this-page)列出每個設定及其用途。其後的[檔案樹](#the-example-monorepo)是本頁面每個程式碼範例所參考的範例 monorepo。

### 本頁面的設定

下方的每個設定都是獨立的。它們是分層的，而不是相互替代的，因此請應用適合您的儲存庫的任何設定。[選擇在何處啟動 Claude](#choose-where-to-start-claude) 決定了您的設定檔案的位置，因此請先閱讀它。[將其整合在一起](#put-it-together)顯示了所有設定的組合。

| 我想要 | 使用 |
| :- | :- |
| 只載入您接觸的程式碼的約定，而不是一個根檔案涵蓋每個子系統 | 按目錄的[CLAUDE.md 檔案](#layer-claude-md-files-by-directory) |
| 排除您從不使用的套件的 CLAUDE.md 檔案 | [`claudeMdExcludes`](#exclude-irrelevant-claude-md-files) |
| 阻止 Claude 開啟建置輸出、生成的程式碼和供應商依賴項 | `permissions.deny` 中的 [`Read` 拒絕規則](#block-reads-of-generated-and-vendored-code) |
| 透過語言伺服器而不是掃描檔案來尋找符號的定義或呼叫者 | [程式碼智能外掛](#reduce-file-reads-with-code-intelligence) |
| 當 Claude 建立 worktree 時，只簽出任務需要的目錄 | [`worktree.sparsePaths`](#check-out-only-the-directories-you-need) |
| 從同一工作階段讀取和編輯同級套件或另一個儲存庫 | [`--add-dir`](#grant-access-across-packages-or-repositories) 或 `additionalDirectories` |
| 給 Claude 特定於一個區域的程序，只在相關時載入 | 按目錄的[技能](#add-per-directory-skills) |
| 用一組每個人都安裝的約定替換許多按目錄的 CLAUDE.md 檔案 | 內部市場中的[外掛](#centralize-conventions-when-layering-stops-scaling) |

> [!TIP]
>
> 有關在任何儲存庫中保持上下文較小的工作流程技術，請參閱 [Claude Code 的最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md)。其中一個例子是[在 subagent 中執行探索](https://code.claude.com/docs/zh-TW/best-practices.md#know-what-subagents-cost)，使檔案讀取保持在主對話之外。若要向組織中的每個開發人員推出基線設定，請參閱[為您的組織設定 Claude Code](https://code.claude.com/docs/zh-TW/admin-setup.md)。

### 範例 monorepo

本頁面的範例參考了一個具有三個套件的 monorepo。相同的模式適用於大型單樹程式碼庫：其中範例使用 `packages/api/`，請替換為您自己的子系統目錄，例如 `src/backend/` 或 `lib/core/`。

```text theme={null}
monorepo/
  CLAUDE.md                     # 根指令
  packages/
    api/
      CLAUDE.md                 # API 特定指令
      .claude/skills/
      src/
    web/
      CLAUDE.md                 # 前端特定指令
      .claude/skills/
      src/
    shared/
      CLAUDE.md                 # 共享庫指令
      src/
```

## 選擇在何處啟動 Claude

您啟動 `claude` 的位置決定了 Claude 可以讀取和編輯哪些檔案而無需額外的權限授予、在啟動時載入哪些 CLAUDE.md 檔案，以及哪些專案設定適用。

| 啟動位置 | 檔案存取 | 啟動時載入的 CLAUDE.md | 使用時機 |
| :- | :- | :- | :- |
| 儲存庫根目錄 | 每個檔案 | 僅根檔案；子目錄檔案按需載入 | 任務跨越多個套件或子系統 |
| 子目錄 | 僅該子樹，直到您授予更多權限 | 該目錄的加上每個祖先的 | 工作範圍限於一個套件或子系統 |

`.claude/settings.json` 中的專案設定不像 CLAUDE.md 檔案那樣從父目錄繼承。如需瞭解工作階段讀取哪個目錄的 `.claude/settings.json`，請參閱 [Claude Code 在何處查找各個檔案](https://code.claude.com/docs/zh-TW/settings.md#where-claude-code-looks-for-each-file)。

下方的每個部分都說明其設定檔案應位於儲存庫根目錄還是您啟動的子目錄中，以及它是提交還是保持本地。

## 按目錄分層 CLAUDE.md 檔案

在大型程式碼庫中，儲存庫根目錄的單個 CLAUDE.md 往往要麼增長到涵蓋每個子系統的約定，在與當前任務無關的指令上浪費上下文，要麼保持太通用而無用。將指令分散到按目錄的檔案中意味著 Claude 載入儲存庫範圍的規則加上僅適用於您正在處理的程式碼的約定。

Claude Code 在啟動時從您的工作目錄和每個父目錄載入每個 [CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md) 檔案，然後[按需](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)載入每個子目錄的檔案。根檔案設定儲存庫範圍的規則，每個子目錄添加其自己的規則。

常見的分割是兩個級別：

* **根 `CLAUDE.md`**：適用於任何地方的指令，例如編碼標準和提交約定
* **按子目錄 `CLAUDE.md`**：特定於該區域堆疊的約定。在 monorepo 中，這是每個套件一個。在大型單樹中，它是每個子系統一個，例如 `src/db/` 或 `src/api/`

將這些檔案提交到儲存庫，以便隊友繼承它們。每個目錄的所有者通常維護其檔案。

若要修剪已簽入的檔案，請執行 [`/doctor` 檢查](https://code.claude.com/docs/zh-TW/memory#my-claude-md-is-too-large)。根 `CLAUDE.md` 保存適用於每個套件的規則：

```markdown CLAUDE.md theme={null}
從套件目錄而不是 monorepo 根目錄執行套件指令碼。
提交主題前綴為套件名稱，例如 `api: add rate limiting`。
永遠不要編輯 packages/*/generated/ 下的檔案。改為在套件中執行 `npm run codegen`。
```

每個子目錄的 `CLAUDE.md`，這裡是 `packages/api/CLAUDE.md`，添加特定於該區域的約定：

```markdown packages/api/CLAUDE.md theme={null}
執行任何操作之前，將 `.env.example` 複製到 `.env`。沒有它，測試和開發伺服器會失敗。
使用 Knex 查詢建構器編寫資料庫查詢。永遠不要在路由處理程式中放入原始 SQL 字串。
遷移合併後永遠不要編輯它。改為添加新的遷移。
```

當您從 `packages/api/` 啟動 Claude 時，它會載入 `packages/api/CLAUDE.md` 和根 `CLAUDE.md`。Claude 看到本地指令以及儲存庫範圍的規則，上下文中沒有來自 `packages/web/` 的指令。非 monorepo 樹中的任何子目錄也是如此。若要確認載入了哪些檔案，請執行 [`/context all`](https://code.claude.com/docs/zh-TW/commands#all-commands) 並檢查 **Memory files** 下的清單。

保持檔案在程式碼庫和模型變化時最新的幾種方法：

* **在拉取請求中審查**：將 CLAUDE.md 編輯視為任何其他文件變更，以便約定跟蹤程式碼
* **在主要模型發佈後重新訪問**：適用於舊模型限制的指令在較新模型自行處理該情況後可能會變成開銷。例如，強制單檔案重構的規則在限制消除後可以刪除
* **添加一個 Stop hook 來提議更新**：[`Stop` hook](https://code.claude.com/docs/zh-TW/hooks#stop) 在 Claude 完成回應時接收工作階段記錄的路徑，因此指令碼可以審查工作階段並在暴露的差距仍然新鮮時提議 CLAUDE.md 更新

有關 CLAUDE.md 檔案如何載入和互動的更多資訊，請參閱[記憶和專案指令](https://code.claude.com/docs/zh-TW/memory.md)。

### 在按目錄 CLAUDE.md 和路徑範圍規則之間選擇

按目錄的 `CLAUDE.md` 檔案和 `.claude/rules/` 下的[路徑範圍規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)都允許您將指令定向到樹的一部分。它們在檔案位置和載入時間上有所不同。

| 方法 | 檔案位置 | 載入時機 | 使用時機 |
| :- | :- | :- | :- |
| 按目錄 `CLAUDE.md` | 在目錄內，與其程式碼一起 | 從該目錄啟動時在啟動時，或按需 | 目錄所有者維護自己的約定；指令與程式碼一起版本化 |
| `.claude/rules/` 中的路徑範圍規則 | 儲存庫根目錄的中央 `.claude/` | 當 Claude 使用與規則的 `paths:` glob 匹配的檔案時 | 您希望所有約定都在一個地方，或相同的規則適用於許多分散的路徑 |

有關也涵蓋技能的比較，請參閱[比較相似功能](https://code.claude.com/docs/zh-TW/features-overview.md#compare-similar-features)。

### 排除無關的 CLAUDE.md 檔案

當您從儲存庫根目錄啟動 Claude 時，每個子目錄的 CLAUDE.md 可以在工作階段期間[按需載入](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)。`claudeMdExcludes` 設定按路徑或 glob 模式跳過特定檔案，以便它們永遠不會載入。

將此用於您從不使用的目錄，例如其他團隊的套件、舊程式碼或供應商子樹。排除清單是靜態的，不是按任務的開關。若要今天專注於一個套件，明天專注於另一個套件，請[從該套件的目錄啟動 Claude](#choose-where-to-start-claude)，而不是編輯排除項。

如果您只想為自己進行這些排除，請將設定放在 `.claude/settings.local.json` 中。Claude Code 在建立該檔案時會將其添加到您的全域 gitignore。由於您在此手動建立它，請將其添加到您的 gitignore。模式使用針對絕對檔案路徑匹配的 glob 語法，因此以 `**/` 開始相對樣式的模式以在樹中的任何地方匹配。下面的範例排除由其他團隊擁有的套件：

```json .claude/settings.local.json theme={null}
{
  "claudeMdExcludes": [
    "**/packages/web/**"
  ]
}
```

這會跳過該套件下的每個 CLAUDE.md 和規則檔案。根 CLAUDE.md 和您確實使用的套件仍然正常載入。

這些模式涵蓋其他常見情況：

* `"**/packages/*/CLAUDE.md"`：排除每個套件的 CLAUDE.md，同時保留根目錄
* `"**/packages/legacy-*/**"`：排除每個名稱與 glob 匹配的套件，包括規則
* `"/home/user/monorepo/legacy/CLAUDE.md"`：按絕對路徑排除一個特定檔案

您可以在任何[設定範圍](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)設定 `claudeMdExcludes`：使用者、專案、本地或受管理。陣列會跨範圍合併，因此團隊可以設定專案級別的預設值，而個人添加本地覆寫。如果您的組織部署了[受管理的 CLAUDE.md 檔案](https://code.claude.com/docs/zh-TW/memory.md#deploy-organization-wide-claude-md)，與其匹配的模式並不會跳過它，無論該模式是在哪個範圍設定的。

有關完整的排除文件，請參閱[排除特定 CLAUDE.md 檔案](https://code.claude.com/docs/zh-TW/memory.md#exclude-specific-claude-md-files)。

## 減少 Claude 讀取的內容

指令只是最終進入 Claude 上下文的一部分。檔案讀取是另一個隨著程式碼庫增長而增加的成本。下方的設定阻止讀取無關的路徑，並用語言伺服器查詢替換詳盡的檔案掃描。

### 阻止讀取生成的和供應商程式碼

Claude 的內容搜尋預設尊重 `.gitignore`，因此已列在其中的路徑（例如 `node_modules/`、`dist/` 和 `build/`）無需額外設定即可保持在搜尋結果之外。

對於已簽入的路徑，例如供應商 SDK 或提交的生成程式碼，在 `permissions.deny` 中添加 `Read` 拒絕規則以阻止 Claude 開啟這些檔案。

拒絕規則可以涵蓋在儲存庫中工作的每個人、只有您，或機器上的每個工作階段，取決於您將它們放在哪個設定檔中：

* **在儲存庫中工作的每個人**：將規則提交到 `.claude/settings.json`，位於儲存庫根目錄（如果您從那裡啟動 Claude），或位於每個套件的 `.claude/`（如果您從子目錄啟動）。與本頁面上的其他專案設定一樣，該檔案不會從父目錄繼承。
* **僅您自己**：在儲存庫根目錄使用 `.claude/settings.local.json`。它會在儲存庫內的每個 CLI 工作階段中載入，無論啟動目錄如何，除了 Claude Code [不使用儲存庫根目錄](https://code.claude.com/docs/zh-TW/settings.md#where-claude-code-looks-for-each-file)的情況，例如在 Windows 上。

  相對模式（如範例的 `Read(./**/vendor/**/*)`）仍然[錨定在工作階段的目前工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)而不是儲存庫根目錄。如果您從子目錄啟動工作階段，請在此檔案中將規則寫為 `//` 絕對路徑，例如 `Read(//absolute/path/to/repo/**/vendor/**/*)`。
* **每個人，在每個工作階段中強制執行**：在[受管理設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定規則，使用者和專案設定無法覆蓋。

下面的範例阻止建置工件和供應商 SDK。其目錄模式以 `/**/*` 結尾而不是 `/**`，以便每個規則涵蓋目錄內的所有內容，但不涵蓋目錄本身。Claude 仍然可以列出這些目錄或進入它們，例如使用 `ls dist` 或 `cd build`。

```json .claude/settings.json theme={null}
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**/*)",
      "Read(./**/build/**/*)",
      "Read(./**/*.generated.*)",
      "Read(./**/vendor/**/*)"
    ]
  }
}
```

拒絕規則涵蓋 Claude 的內建檔案工具。在 Bash 中，它們涵蓋 Claude Code 識別的檔案命令，例如 `cat`、`head`、`grep` 和 `find`，當拒絕的路徑作為引數出現時，以及[重新導向](https://code.claude.com/docs/zh-TW/permissions.md#redirections)的目標，例如 `< file`。Claude Code 也會盡力嘗試將拒絕的路徑排除在內建 Grep 和 Glob 工具的結果之外。Bash 搜尋（例如 `grep -r` 或 `find`）在包含拒絕檔案的目錄上仍然會在其輸出中包含它們。

拒絕規則不涵蓋自己開啟檔案的子程序。有關完整的模式語法，請參閱[讀取和編輯權限規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)。

### 使用程式碼智能減少檔案讀取

在大型程式碼庫中，尋找符號的定義或使用位置可能會花費許多檔案讀取和 grep 呼叫。[程式碼智能外掛](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)將 Claude 連接到語言伺服器，以便它可以跳轉到定義、尋找參考和直接顯示類型錯誤，而不是掃描樹。

官方市集有 TypeScript、Python、Go、Rust 和其他常見語言的外掛。在 VS Code 擴充功能或桌面應用程式中，請依照[安裝外掛](https://code.claude.com/docs/zh-TW/plugins/install.md#install-a-plugin)進行安裝。在終端機中，執行 `claude` 啟動 Claude Code，然後在其提示字元中輸入以下內容以安裝 TypeScript 外掛：

```shell theme={null}
/plugin install typescript-lsp@claude-plugins-official
```

如果安裝失敗，請符合 Claude Code 報告的訊息：

* `Marketplace "claude-plugins-official" not found`：使用 `/plugin marketplace add anthropics/claude-plugins-official` 添加市場，然後重試安裝。
* `Plugin "<name>" not found in marketplace "claude-plugins-official"`：您本機的市集目錄副本可能已過期。請使用 `/plugin marketplace update claude-plugins-official` 重新整理，然後重試安裝。如果重試後顯示相同的訊息，請參閱[在市集中找不到外掛](https://code.claude.com/docs/zh-TW/plugins/troubleshooting.md#plugin-not-found-in-marketplace)。

若要為儲存庫中的每個人啟用外掛而不是自己安裝，請將其添加到 [`enabledPlugins` 專案設定](https://code.claude.com/docs/zh-TW/settings-reference#plugin-settings)。

程式碼智能外掛需要每個開發人員機器上的語言的語言伺服器二進位檔案。請參閱[每種語言需要哪個二進位檔案](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)。從官方市場安裝需要網路存取 GitHub，市場在那裡託管。在受限網路上，[改為從內部 Git 主機或本地路徑添加市場](https://code.claude.com/docs/zh-TW/plugins/install.md#add-a-marketplace)。

這與上面的 `claudeMdExcludes` 和 `Read` 拒絕規則配對良好。這些將無關的內容保持在上下文之外，程式碼智能防止 Claude 通過讀取剩餘內容來定位定義。

## 範圍 worktrees 和檔案存取

這些設定控制 worktrees 中磁碟上的內容以及 Claude 可以讀取和寫入的超出啟動點的目錄。

### 只簽出您需要的目錄

`--worktree` 旗標在新的 git worktree 中啟動工作階段，以便變更與您的主簽出隔離。預設情況下，它簽出整個儲存庫。在大型儲存庫中，`worktree.sparsePaths` 設定使用 git sparse-checkout 只將列出的目錄加上根級檔案寫入磁碟，以便 worktrees 啟動更快並使用更少空間。

如果在此目錄中工作的每個人都需要相同的路徑，請將設定提交到 `.claude/settings.json`。若要為自己添加路徑，請使用 `.claude/settings.local.json`：列表在範圍內合併，因此本地檔案可以添加到提交的清單中但不能刪除它們。

此頁面上的 JSON 範例一次只顯示一個設定。如果您的 `.claude/settings.json` 已經包含其他鍵，例如上面的 `permissions.deny` 規則，請在它們旁邊添加 `worktree` 鍵，而不是替換檔案。[將其整合在一起](#put-it-together)顯示合併的結果。

下面的範例顯示提交的檔案：

```json .claude/settings.json theme={null}
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ]
  }
}
```

當 Claude 建立 worktree 時，它只簽出 `.claude/`、`packages/api/` 和 `packages/shared/`，而不是完整樹。`sparsePaths` 中的路徑相對於儲存庫根目錄，無論您從哪個子目錄啟動 Claude。任何目錄路徑都可以在這裡工作，不僅僅是套件根目錄。

這對於[子代理 worktree 隔離](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees)特別有用。子代理是為子任務生成的平行 Claude 實例，每個在 worktree 中執行的都會獲得輕量級簽出而不是完整樹。工作階段中的所有 worktrees 共享相同的 `sparsePaths`，因此如果一個子代理需要 `packages/api/` 而另一個需要 `packages/web/`，請列出兩者。

在 `sparsePaths` 中列出目錄，而不是個別檔案。根級檔案（如 `package.json`、`tsconfig.base.json` 和鎖定檔案）始終與您列出的目錄一起簽出。根級目錄不是，因此如果您想要儲存庫根目錄的 `.claude/settings.json` 或 `.claude/rules/` 在 worktree 內可用，請在清單中包含 `.claude`。對於專案 skills、agents 和命令，請參閱[worktrees 與主簽出共享的內容](https://code.claude.com/docs/zh-TW/worktrees.md#what-worktrees-share-with-the-main-checkout)。

Sparse checkout 需要 git 在儲存庫的共享 `.git/config` 中啟用 `extensions.worktreeConfig`，同時存在 sparse worktree。Claude Code 在移除最後一個 worktree 後會移除該項目，但僅當 Claude Code 添加了它時。它永遠不會移除您自己設定的值。

若要避免在 worktrees 中複製 `node_modules` 等大型目錄，請在同一 `.claude/settings.json` 中將 `sparsePaths` 與 `symlinkDirectories` 配對：

```json .claude/settings.json theme={null}
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ],
    "symlinkDirectories": [
      "node_modules"
    ]
  }
}
```

這會建立從每個 worktree 的 `node_modules/` 回到主儲存庫副本的符號連結，而不是在磁碟上複製它。

> [!NOTE]
>
> `sparsePaths` 和 `symlinkDirectories` 設定在建立 worktree 之前從您的啟動目錄讀取。建立後，工作階段的工作目錄是 worktree 根目錄，而不是您啟動的子目錄。因此，worktree 內的專案設定從 worktree 根目錄的 `.claude/settings.json`（儲存庫根目錄檔案的簽出副本）載入。將您在 worktrees 內需要的任何其他設定（例如權限規則或 hooks）放在儲存庫根目錄的 `.claude/settings.json` 中。

有關完整的 worktree 設定參考，請參閱 [Worktree 設定](https://code.claude.com/docs/zh-TW/settings-reference.md#worktree)。

### 授予跨套件或儲存庫的存取權限

本部分適用於您從子目錄啟動 Claude 或任務跨越多個簽出時。如果您在單個大型樹中從儲存庫根目錄啟動，Claude 已經可以存取每個檔案，您可以跳過此部分。

當您從 `packages/api/` 啟動 Claude 時，它可以讀取和寫入該目錄內的檔案。如果任務需要跨套件進行變更，例如更新 `api` 和 `web` 都匯入的共享類型，您需要授予對同級目錄的存取權限。相同的機制授予對單獨簽出的儲存庫的存取權限。

`.claude/settings.json` 中的 `additionalDirectories` 設定給予 Claude 對工作目錄外目錄的存取權限。下面的範例授予對兩個同級套件的存取權限：

```json packages/api/.claude/settings.json theme={null}
{
  "permissions": {
    "additionalDirectories": [
      "../shared",
      "../web"
    ]
  }
}
```

相對路徑相對於您啟動 Claude 的目錄解析。使用此設定，Claude 可以在從 `packages/api/` 工作時讀取和編輯 `packages/shared/` 和 `packages/web/` 中的檔案。

您也可以在執行時不編輯設定而授予存取權限，方法是在啟動 Claude 時傳遞 `--add-dir`：

```bash theme={null}
claude --add-dir ../shared
```

無論您如何添加目錄，Claude 都可以讀取和編輯其中的檔案。該目錄的 CLAUDE.md、`.claude/rules/` 檔案和技能是否也載入取決於您如何添加它：

| 添加方式 | 載入 CLAUDE.md 和規則 | 載入技能 |
| :- | :- | :- |
| `additionalDirectories` 設定 | 永不 | 永不 |
| `--add-dir` 旗標或 `/add-dir` 命令 | 僅使用下面的環境變數 | 是 |

若要從使用 `--add-dir` 或 `/add-dir` 添加的目錄載入 CLAUDE.md 和規則檔案，請設定 `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD` 環境變數：

```bash theme={null}
CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1 claude --add-dir ../shared
```

環境變數對 `additionalDirectories` 設定中列出的目錄無效。有關詳細資訊，請參閱[從其他目錄載入](https://code.claude.com/docs/zh-TW/memory.md#load-from-additional-directories)。

對於此區域中的每個人都需要的同級目錄，請將 `additionalDirectories` 提交到 `.claude/settings.json`。對於個人選擇或一次性存取，請使用 `.claude/settings.local.json` 或在啟動時傳遞 `--add-dir`。

## 新增各目錄範圍的 skills

任何子目錄都可以定義[skills](https://code.claude.com/docs/zh-TW/skills.md)，其範圍限於該目錄自己的堆疊。當 Claude 判斷 skill 相關時，它會按需載入。

Skills 位於目錄內的 `.claude/skills/` 下。將它們與該區域的程式碼一起提交，這樣任何複製儲存庫的人都能取得它們。在 monorepo 中，每個套件可以有一組 skills。在大型單一樹狀程式碼庫中，每個子系統（例如 `src/db/.claude/skills/`）有一組。

在子目錄內建立 skill 目錄：

```bash theme={null}
mkdir -p packages/api/.claude/skills/api-testing
```

然後在該目錄內寫入 `SKILL.md`，這裡是 `packages/api/.claude/skills/api-testing/SKILL.md`。此範例教導 Claude API 套件的測試模式：

```markdown packages/api/.claude/skills/api-testing/SKILL.md theme={null}
---
name: api-testing
description: Testing patterns for the API package. Use when writing or modifying tests in packages/api/.
---

## Test structure

Tests are in `src/__tests__/` mirroring the `src/` directory structure.
Each route file has a corresponding `.test.ts` file.

## Running tests

- All tests: `npm test`
- Single file: `npm test -- src/__tests__/routes/users.test.ts`
- Watch mode: `npm test -- --watch`

## Test utilities

- `src/__tests__/helpers/db.ts`: provides `setupTestDb()` and `teardownTestDb()` for database tests
- `src/__tests__/helpers/auth.ts`: provides `createTestUser()` and `getAuthToken()` for authenticated endpoints

## Patterns

- Use `supertest` for HTTP assertions, not raw fetch
- Always wrap database tests in a transaction that rolls back
- Mock external services in `src/__tests__/mocks/`
```

不同的子目錄以相同方式保存不同的 skills：`packages/web/.claude/skills/component-patterns/` 描述前端的元件慣例，而不是測試。當 Claude 在 `packages/api/` 中的檔案上工作時，它會載入 api-testing skill。當它在 `packages/web/` 中工作時，它會載入 component-patterns。

您也可以按檔案模式而不是按位置來限定 skill 的範圍。[`paths` frontmatter 欄位](https://code.claude.com/docs/zh-TW/skills#frontmatter-reference)採用 glob 模式，只有當 Claude 使用符合的檔案時，它才會自動載入 skill。使用此方法可以讓 skill 位於儲存庫根目錄的 `.claude/skills/` 中，但僅適用於特定檔案，例如限定於 `**/migrations/**` 的資料庫遷移 skill。

如需更多關於建立和組織 skills 的資訊，請參閱 [Skills](https://code.claude.com/docs/zh-TW/skills.md)。

### 保持 skills 可發現

隨著 skills 分散在許多目錄中，Claude 可選擇的清單可能會變得很大。Claude 透過讀取每個已發現 skill 的名稱和描述來選擇 skill，只有選定 skill 的完整內容才會載入上下文。本節涵蓋如何保持該清單較小。

哪些 skills 在範圍內取決於您從何處啟動 Claude：

* **從子目錄（例如 `packages/api/`）**：該目錄的 skills、每個父目錄直到儲存庫根目錄，以及使用者和企業級別的 skills
* **從儲存庫根目錄**：根目錄 skills，加上 Claude 在工作階段期間接觸的每個子目錄的 skills，這可能會累積成數百個
* **在使用 [`--add-dir`](#grant-access-across-packages-or-repositories) 新增同層目錄後**：該同層目錄的 skills 也會載入。`additionalDirectories` 設定僅授予檔案存取權限，不會載入 skills

名稱總是會載入，但[當有許多時，某些 skills 會完全失去其描述](https://code.claude.com/docs/zh-TW/skills.md#skill-descriptions-are-cut-short)，這可能會移除 Claude 用來決定 skill 是否適用的關鍵字。保持描述簡短，並以請求會包含的詞語開頭，例如「在 `packages/api/` 中寫入或修改測試」。

對於許多目錄共享的 skills，例如 PR 慣例或部署檢查清單，將它們放在儲存庫根目錄的 `.claude/skills/` 中，以便從任何啟動目錄載入。當共享 skills 需要自己的版本歷史或必須跨儲存庫工作時，改為將它們打包為[plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md)。Plugin skills 使用 `plugin-name:skill-name` 命名空間，因此它們永遠不會與各目錄 skills 衝突。平台團隊可以在一個地方進行版本控制和更新。

若要找出哪些 skills 未被使用，請啟用 OpenTelemetry [logs exporter](https://code.claude.com/docs/zh-TW/monitoring-usage.md)，並設定 `OTEL_LOG_TOOL_DETAILS=1`，以便 skill 名稱按字面記錄而不是被編輯。[`skill_activated` 事件](https://code.claude.com/docs/zh-TW/monitoring-usage#skill-activated-event)在其 `skill.name` 屬性中記錄每次調用，`invocation_trigger` 記錄命令、Claude 或巢狀 skill 是否調用了它，這告訴您要整合或淘汰什麼。

## 當分層停止擴展時集中約定

隨著程式碼庫的增長，按目錄的 CLAUDE.md 檔案可能變得難以管理。約定漂移、檔案變得陳舊，沒有人擁有根目錄。解決這個問題通常落在維護儲存庫 Claude Code 設定的團隊身上，而不是在自己的區域中工作的每個開發人員。

將約定和參考內容從始終載入的 CLAUDE.md 移出到按需載入的機制中：

* [技能](https://code.claude.com/docs/zh-TW/skills.md)：Claude 僅在與任務相關時載入的參考資料
* [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)：由平台團隊集中擁有的 skill、hook 和命令的版本化捆綁，並可[透過受管設定為所有人安裝](https://code.claude.com/docs/zh-TW/plugins/org.md#pre-install-and-require-plugins)
* [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)：如果您的組織已經在儲存庫上執行程式碼搜尋或 RAG 索引，請將其公開為 MCP 工具，以便 Claude 查詢它而不是直接讀取檔案

有關平台團隊如何集中強制執行這些的資訊，請參閱[伺服器管理或端點管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md#choose-between-server-managed-and-endpoint-managed-settings)。

### 在工作階段啟動時推薦正確的外掛

一旦約定位於外掛中，在樹的陌生部分啟動 Claude 的隊友就沒有信號表明該區域的所有者維護哪個外掛。[`SessionStart` hook](https://code.claude.com/docs/zh-TW/hooks#sessionstart) 可以彌補這一差距，因為 Claude Code 會在第一個提示之前將 hook 列印到 stdout 的純文字添加到 Claude 的上下文中。

例如，您可以編寫一個指令碼，從[hook 輸入](https://code.claude.com/docs/zh-TW/hooks.md#common-input-fields)讀取啟動目錄，在提交到儲存庫的路徑到外掛對應中查詢它，並列印建議供 Claude 在其第一個回覆中中繼。請參閱[使用 hooks 自動化操作](https://code.claude.com/docs/zh-TW/hooks-guide.md)來編寫和註冊 hook。

## 將其整合在一起

下面的組合設定使用 monorepo 佈局。相同的檔案適用於大型單樹中的任何子目錄。每個子目錄的 `.claude/settings.json` 必須是自包含的，而不是分層在根檔案上。

該範例在 `.claude/settings.json` 中提交 `worktree`、`additionalDirectories` 和 `Read` 拒絕規則，以便 `packages/api/` 中的每個開發人員都獲得相同的同級存取、稀疏路徑和排除。下面的檔案是 `packages/api/` 的提交按區域設定：

```json packages/api/.claude/settings.json theme={null}
{
  "worktree": {
    "sparsePaths": [
      ".claude",
      "packages/api",
      "packages/shared"
    ],
    "symlinkDirectories": [
      "node_modules"
    ]
  },
  "permissions": {
    "additionalDirectories": [
      "../shared"
    ],
    "deny": [
      "Read(./**/dist/**/*)",
      "Read(./**/build/**/*)"
    ]
  }
}
```

因為此工作階段從 `packages/api/` 啟動，同級套件的 CLAUDE.md 檔案已經超出範圍，因此此處不需要 `claudeMdExcludes`。如果您也從根目錄啟動工作階段，請改為將其添加到儲存庫根目錄的 `.claude/settings.local.json`。

`additionalDirectories` 項目在您直接從 `packages/api/` 啟動 Claude 時適用。在從此工作階段建立的 worktree 內，工作目錄是 worktree 根目錄，因此此設定檔案不會載入。同級套件已經在 worktree 內可達，無需它，但拒絕規則需要在儲存庫根目錄的 `.claude/settings.json` 中複製一份，以便 worktree 工作階段選擇它們，如[worktree 設定注意](#check-out-only-the-directories-you-need)所述：

```json .claude/settings.json theme={null}
{
  "permissions": {
    "deny": [
      "Read(./**/dist/**/*)",
      "Read(./**/build/**/*)"
    ]
  }
}
```

設定後，儲存庫具有此佈局：

```text theme={null}
monorepo/
  CLAUDE.md
  .claude/settings.json                           # worktree 工作階段的拒絕規則
  packages/
    api/
      CLAUDE.md
      .claude/settings.json                       # worktree、additionalDirectories、拒絕規則
      .claude/skills/api-testing/SKILL.md
    web/
      CLAUDE.md
      .claude/skills/component-patterns/SKILL.md
    shared/
      CLAUDE.md
```

使用此設定，從 `packages/api/` 啟動 Claude：

* 載入根 CLAUDE.md 和 `packages/api/CLAUDE.md`，跳過 `packages/web/CLAUDE.md`
* 可以讀取和編輯 `packages/api/` 和 `packages/shared/` 中的檔案
* 跳過 `packages/api/` 中 `dist/` 和 `build/` 下的建置輸出讀取
* 有 api-testing 技能可按需使用
* 建立包含 `.claude/`、`packages/api/`、`packages/shared/` 和根級檔案的 worktrees，並從根設定檔案在 worktree 中應用拒絕規則

## 範圍和計劃跨套件的變更

上面的設定控制 Claude 看到的內容。當單個變更涉及多個套件時，例如更新共享類型以及使用它的每個呼叫位置，您如何範圍和排序任務也會影響結果。

兩種技術有助於保持跨套件變更的一致性：

* **在一個工作階段中給 Claude 整個變更**：將共享編輯及其呼叫位置一起交付可以保持每個編輯背後的決策一致，而不是按套件重新推導它們
* **在編輯前計劃**：先在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中計劃，Claude 會將計劃寫入檔案。長跨套件工作階段在進行中[壓縮其上下文](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)。Claude Code 在每次壓縮後重新注入計劃檔案，因此計劃在對話歷史可能不會的地方倖存

## 後續步驟

一旦此設定就位，您可以對其進行細化：

* 使用 [hooks](https://code.claude.com/docs/zh-TW/hooks-guide.md) 在 Claude 編輯檔案後執行按目錄的 linters 或類型檢查器
* 審查[有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)以瞭解程式碼庫大小如何影響 token 使用以及如何在更廣泛推出前設定支出限制
* 在 Claude 部落格上閱讀[Claude Code 如何在大型程式碼庫中工作](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start)，瞭解組織推出模式和所有權模型，這些模型位於本頁面上的按儲存庫設定之上
