# 計畫：安裝一鍵化＋系統自我認知必載（審查後定稿）

> 人稱約定：[使用者]＝holylight（決策者）；[AI]＝本 session 主持的 Claude；[實作 agent A／C]、[審查 agent]、[Codex]＝被派工的子代理；[新同事]＝第一次安裝的人；[安裝 AI]＝替新同事跑安裝的 Claude Code（可能是 Opus 等較弱模型）。
> 名詞：根層＝`~/.claude`（本 repo）；專案層＝`{專案}/.claude/memory/`；公司層＝`/org` 接上的公司記憶 repo；必載檔＝每個 session 一定進 context 的檔；接管＝在既有、非 git 的 `~/.claude` 原地接上版控；覆蓋檔＝使用者值要疊在 repo 版本上的兩個 JSON：`settings.json`、`workflow/config.json`。

## 0. 重大發現

### 0.1 現行安裝文件現在就壞的三點（本計畫要根治）

都在 `Install-forAI.md` Step 2「合併安裝」；`Install.md:24` 寫明「用過 Claude Code 就會有 `~/.claude`」，所以幾乎每位[新同事]都走這條路。

1. `rsync` 在 Git for Windows 不存在（[AI] 實測），Step 2 有 6 行靠它。
2. 根層共享知識沒被裝進去：Step 2 只補 `_reference`、`_meta` 兩檔與兩個索引檔，`memory/` 其餘 atom 沒複製（[Codex]、[審查 agent] 皆對碼證實）。同漏 `prompts/`、`verify/`、`run_verify.py`、`.gitattributes`、`.editorconfig`。
3. 合併後的 `~/.claude` 不是 git repo，但升級與背景記憶同步都靠 repo。

### 0.2 計畫審查挖出、初版計畫會造成的問題（已全數改進設計，見 §7）

- 初版只備份「內容不同的檔」，使用者有同名但型別不同的東西（檔 `hooks`、目錄 `version.json/`、symlink）會被 checkout **無備份刪掉**（[審查 agent] 實跑重現）。
- 接管中途失敗後重跑會被判成「已安裝」而永久半套（[審查 agent] 實跑兩種觸發：shallow 來源 fetch、Windows 長路徑）。
- `settings.json` 留在「已修改」狀態的機器，背景同步會**分叉卡死**：本地記憶照常自動 commit，但整樹不乾淨不拉程式碼、push 被拒（`hooks/wg_vcs_sync.py:1066-1082,1306,1357`）。
- `hooks/user-init.sh` 無條件覆蓋 `USER.md`；`hooks/ensure-mcp.py` 直接執行會背景跑全域 `npm i`；`tools/fix-hook-python.py` 用自身位置決定改哪份 `settings.json`（[AI] 對碼確認）。
- 沒有 `settings.json` 的[新同事]會原樣拿到 repo 擁有者的 `permissions` 與 `bypassPermissions` 預設模式。

另一個獨立缺口：必載檔完全沒提公司層，也沒寫系統核心目標。

## 1. 目標與非目標

- 目標 A：任何等級的[安裝 AI] 只需跑 3–4 個指令並轉述輸出就能完成安裝。
- 目標 B：裝完後每個 session 開機即知「核心目標＋三層記憶在哪、怎麼寫」。
- 非目標：不改 hook／MCP 行為（例外：`hooks/user-init.sh` 的 `USER.md` 覆蓋 bug 修 3 行）；不自動 `pip install`／`npm i`／`ollama pull`；不動 `skills/upgrade`；不把 `settings.json` 改成模板制（見 §6）；不碰 git commit／push。

## 2. 已實證的地基

[AI] 在暫存目錄實跑：既有 `~/.claude` 上 `git init` → fetch → `git reset --mixed origin/main`（工作目錄零改動）→ 備份 → `git checkout -- .`（865 檔就位，個人檔與 ignored 檔全在）。[審查 agent] 另實跑確認：對檔案下 `git update-index --skip-worktree` 後 `git status` 乾淨，上游沒動該檔時 ff 成功且保留本機內容，上游動到時 pull 安全中止。

## 3. 設計

### 3.1 `tools/install.py`（新檔，單檔，純標準函式庫）

共通規則：
- 目標一律 `Path.home()/".claude"`。**所有子程序的環境都強制帶 `HOME` 與 `USERPROFILE` ＝ `str(Path.home())`**，讓 bash 與 Python 算出同一個家目錄。
- 來源＝腳本所在的 clone。來源沒有 `.git` → 報錯要求用 `git clone` 取得。
- 輔助工具一律呼叫**目標樹內**那份（`<目標>/tools/fix-hook-python.py`、`<目標>/hooks/user-init.sh`）。
- subprocess 帶 `CREATE_NO_WINDOW`（Windows）；git 路徑清單一律用 `-z`。
- JSON 寫入走暫存檔＋`os.replace`。輸出為人讀文字，不做 `--json`。
- 不呼叫 `hooks/ensure-mcp.py`（MCP 註冊交給 SessionStart；`--apply` 只印一句說明）。

| 子指令 | 做什麼 | exit code |
|---|---|---|
| `--check` | 安裝前自檢（Python／Node／Git／bash／Ollama＋三模型／lancedb／sentence-transformers／Codex），每項 `OK` 或「缺：少什麼功能＋補裝指令」。唯讀 | 0；Python < 3.10 或缺 git 回 2 |
| `--apply` | 安裝，冪等可重跑 | 0；3＝目標是別的 repo；1＝其他失敗 |
| `--upgrade` | 已安裝機器升級 | 0／1 |
| `--verify` | 安裝後驗證，每項 `PASS`／`DEGRADED（少了什麼）`／`FAIL（怎麼修）`；末尾印三層現況（根層 atom 數、公司層接上沒）。唯讀 | 0＝無 FAIL |

`--check` 與 `--verify` 共用同一組探測函式。

**`--apply` 流程**

1. 模式判定
   - 目標不存在 → 不動，印「請 `git clone <來源的 origin URL> ~/.claude` 後在其中重跑 `--apply`」，exit 1。
   - 目標有 `.git`，且 `.git/atom-install-state.json` 不存在或 `phase=done`：origin URL 與來源相同（或腳本就在目標內）→ **就地模式**，只做 6–9，**不碰覆蓋檔、不設 skip-worktree**（開發機的 `settings.json` 是版控真源）。origin 不同 → exit 3，零改動。
   - 目標無 `.git`，或狀態檔存在且 `phase≠done` → **接管模式**（可從中斷處續跑）。
2. 接管：`git init -b <分支>`（分支＝來源 clone 的當前分支，detached 則 `main`）→ 立刻寫狀態檔 `{phase:"adopting", backup_dir, branch}` → Windows 設 `core.longpaths=true` → `remote add origin <來源 clone 的 origin URL>` → `git fetch origin <分支>`（從真正的遠端抓，不從來源本機路徑；fetch 後驗 `refs/remotes/origin/<分支>` 存在，不存在即失敗）→ `git reset --mixed origin/<分支>` → 設 upstream。
3. 備份（備份目錄 `~/.claude/backups/install-<時間戳>/`，續跑時沿用狀態檔記的同一個，已存在的備份不覆寫）。對每個 tracked 路徑：
   - 任一祖先存在且不是真目錄（檔或 symlink）→ 整個**移進**備份。
   - 路徑本身是目錄或 symlink → **移進**備份。
   - 是一般檔且 git 判定內容不同 → **複製**進備份。
   - 另外無條件備份既有的 `USER.md`、`IDENTITY.md`（ignored，git 不會列）。
4. `git checkout -- .`（全流程唯一的覆寫動作，只在接管模式、備份完成後）。狀態檔 `phase:"restored"`。
5. 覆蓋檔合併（「使用者的」＝備份目錄裡的原檔；「系統的」＝`git show HEAD:<檔>`）：
   - `settings.json`：`hooks` 取系統的整段，使用者原有且指令不指向本系統（`.claude/hooks/`、`.claude/tools/`）的條目保留附加；`statusLine` 使用者有就用使用者的；其餘頂層鍵**只用使用者的**。使用者原本沒有 `settings.json` → 結果只含系統的 `hooks` 與 `statusLine`，**不帶入 repo 擁有者的 `permissions`／`model`／預設權限模式**，並印一句「想要同款授權清單見 `git show HEAD:settings.json`」。
   - `workflow/config.json`：使用者原本有 → 深度合併，使用者值優先、新鍵補系統預設；沒有 → 系統檔原樣。
   - 兩檔都下 `git update-index --skip-worktree`（不論是否與 HEAD 相同），標記這台是「安裝器管理的機器」。狀態檔 `phase:"merged"`。
6. 直譯器：跑目標樹的 `fix-hook-python.py`，有缺失才 `--write`。
7. 個人啟動檔：用與 `hooks/run-bash-hidden.py` 相同的方式找 bash，執行目標樹的 `hooks/user-init.sh`。
8. 索引：`tools/sync-memory-index.py --check`（結果列入輸出，不因它失敗而中止）。
9. 狀態檔 `phase:"done"`。收尾輸出：備份位置與清單（特別點名：原 `CLAUDE.md` 內容已不再載入，要保留請貼進 `USER-{帳號}.md`）、MCP 會在下次啟動自動註冊、選配項指令（Ollama 模型、pip 套件、「接上公司記憶」）、「請重開 Claude Code」。

**`--upgrade` 流程**（只管帶 skip-worktree 標記的覆蓋檔；沒有標記的機器等同 `git pull --rebase` 後跑 6）

1. 有未解衝突或進行中的 rebase／merge → 拒絕並說明。
2. 對每個帶標記的覆蓋檔：現檔存進 `backups/upgrade-<時間戳>/`，並記下 `base＝git show HEAD:<檔>`。
3. 取消標記 → `git checkout -- <檔>` → `git pull --rebase`。
4. 重新合併（一律以步驟 2 存的檔為「使用者的」）：`settings.json` 用 `--apply` 同一條規則；`workflow/config.json` 做三方合併——「使用者改過的鍵」＝存檔與 `base` 的遞迴差異，套到新版 HEAD 上（沒改過的鍵跟著新預設走）。寫回、重新下標記。
5. 任何一步失敗：若在 rebase 中先 `git rebase --abort`，再把存檔寫回原位並重新下標記，exit 1 並印原因。用 try/finally 保證。
6. 跑直譯器校正。

**`--verify` 項目**：版本檔可讀、目標是 git repo 且 upstream 存在、hook 直譯器全數存在、SessionStart hook 實跑輸出含 `additionalContext`、`IDENTITY.md`／`USER.md` 存在、索引一致、`memory-search.py` 查得到東西、MCP 已註冊（未註冊＝DEGRADED「重開 Claude Code 後自動註冊」）、Node／Ollama／模型／向量套件／Codex（缺＝DEGRADED 並說少什麼）、合併驅動、公司層（未接＝資訊，不算降級）。

**測試 `tools/verify/verify_install.py`**（pytest；假家目錄用 `USERPROFILE`＋`HOME` 同時指過去；以真實 repo 的 `git clone --bare` 當假上游、再 clone 出來源；session 級 fixture 共用上游，總時長目標 < 90 秒）：
- 接管：個人檔與 ignored 檔不丟、tracked 檔就位、`settings.json`／`CLAUDE.md` 有備份。
- 型別衝突：檔 `hooks`、目錄 `version.json/keep.txt` 都進備份且安裝成功。
- 中斷續跑：在 checkout 前人為中止（例如 monkeypatch 拋例外）→ 重跑完成，備份未被覆寫。
- settings 合併：使用者 `permissions` 保留、外來 hook 保留、系統 hooks 齊全；無 settings 時不含 `permissions`。
- config 合併：使用者值保留、新鍵補上。
- 兩個覆蓋檔帶 skip-worktree，`git status --porcelain` 無 tracked 修改。
- 就地模式：不動覆蓋檔、不下標記。別的 repo → exit 3 且零改動。目標不存在 → exit 1 且不建立。
- `--upgrade`：上游新增一筆同時改 `settings.json` hooks 與 `workflow/config.json` 預設值的 commit → 升級後使用者值仍在、新 hooks 與新預設生效、標記還在；pull 失敗情境 → 檔案還原。
- `USER.md`：只有自訂 `USER.md` 的使用者，安裝後內容不變。
- `--verify` exit code。

### 3.2 `rules/core.md` 自我認知段＋`hooks/user-init.sh` 修補（[AI] 自己做）

新段（每 session 必載，約 130 token；保留現有 Realm／Scope 行並在 Scope 行補 `org`）：

```markdown
## 系統自我認知
- **核心目標**：每一次的知識與經驗全部積累、分門別類，並在需要的那一刻精準送到眼前——該想起的要完整送到，不相關的一行都不佔 token。記憶系統的取捨兩題都要過。
- **記憶三層**（寫入時的 scope）：
  - 根層 `~/.claude/memory/`：跨專案通用知識，隨本系統 repo 同步 → `global`
  - 公司層（`/org` 接上的公司記憶 repo）：所有專案共用的公司知識與工具卡 → `org`
  - 專案層 `{專案}/.claude/memory/`：該專案的決策與踩坑，隨專案版控 → `shared`／`personal`
- 哪層接上沒、裝得完不完整 → `python ~/.claude/tools/install.py --verify`。
```

`memory/_meta/always-load-contracts.json` 的 `core-治理與記憶鐵律` 契約 `must_contain` 加 `系統自我認知`、`公司層`。

`hooks/user-init.sh`：`USER-{帳號}.md` 不存在而 `USER.md` 已存在時，先把 `USER.md` 拷成 `USER-{帳號}.md`（保住使用者內容），否則才從模板建。

### 3.3 文件（[實作 agent C]）

- `Install-forAI.md` 改寫成約 100 行 runbook：執行守則 → 指令序（clone 到暫存 → `--check` → `--apply` → 重開 → `--verify`；`~/.claude` 不存在時直接 clone 進去再 `--apply`）→ 怎麼回報 → 選配項一行一個（Ollama 模型、pip 套件、公司層、多子專案佈局、其他 AI 客戶端查記憶）→ 升級（`--upgrade`）→ 移除。不再複述 hook 表、config 鍵表、降級邏輯。
- 被移出的每一塊：TECH.md／`_AIDocs/` 已有等價內容 → 刪；沒有 → 搬到合適章節。交「原段落 → 新去處」對照表。
- 重指舊章節引用：`README.md:28`（Step 4b）、`_AIDocs/Tools/_INDEX.md:20`（Step 7）、`TECH.md:233`（多子專案佈局）、`_AIDocs/_INDEX.md:19` 說明欄、`skills/upgrade/SKILL.md:154`、`version.json` 的 `_doc`（只在敘述失真時改）。
- `tools/skill-index.py:36` 把 `Install-forAI.md` 列為 skill-count marker 檔：改寫後跑該工具的檢查確認不紅（marker 整段移除或保留擇一，以工具不紅為準）。
- `Install.md` 的 prompt 改成新流程；`_AIDocs/_INDEX.md:36` 過時數字修正。
- 依 atom `feedback-memory-system-doc-sync` 完整清單逐項過：`_AIDocs/_CHANGELOG.md`（必更）、`TECH.md`、`_AIDocs/SPEC_ATOM_V5.md`、`README.md`、`_AIDocs/DocIndex-System.md`、`_AIDocs/Architecture.md`、`_AIDocs/Project_File_Tree.md`——沒受影響的不動。原則：指向真源，不複製計數與規則本體。

## 4. 分工（檔案集互不重疊）

| 線 | 誰 | 動的檔 |
|---|---|---|
| A 安裝器 | [實作 agent A] | `tools/install.py`、`tools/verify/verify_install.py`（皆新檔） |
| B 自我認知 | [AI] | `rules/core.md`、`memory/_meta/always-load-contracts.json`、`hooks/user-init.sh` |
| C 文件 | [實作 agent C] | §3.3 列的文件 |

A、C 同時開跑；C 依 §3.1 的 CLI 契約寫，A 不得偏離契約（要偏離先回報理由）。

## 5. 審查與監督

- 計畫審查：已完成（[Codex] gpt-6-astra ＋ [審查 agent]，各自獨立），裁決見 §7。
- 完工審查：[Codex]＋[審查 agent] 審實際 diff；另派一個 **Opus 模型的 agent 只拿新版 `Install-forAI.md`，在假家目錄把安裝從頭跑到尾**。
- 驗證：A、C 線只跑自己的目標測試；整合後不跑全量（全量 `python run_verify.py` 已從流程拔掉，全量改增量待補）。
- 收尾報告標驗證強度：實跑通過／讀碼推論／未驗。

## 6. 留意事項

- **另一個 session 正在同一個工作目錄改檔**。動任何既有檔前先看該檔的 `git diff`，把別人未提交的語意保留；寫檔前重讀最新內容。任何 agent 不得對真實 `~/.claude` 執行 `git checkout`／`stash`／`reset`／`commit`／`add`／`update-index`。
- **嚴禁對真實 `~/.claude` 執行 `--apply`／`--upgrade`**；所有安裝器測試只在假家目錄跑，且 `HOME` 與 `USERPROFILE` 必須同時指向假家。`--check`、`--verify` 唯讀，可對真實環境跑。
- 已知限制：`fix-hook-python.py --write` 會改寫所有以 python 開頭的指令，包含使用者保留下來的外來 hook（只在直譯器缺失時觸發）。
- 已知限制：直接 clone 進空 `~/.claude` 的機器走就地模式、不下 skip-worktree；之後自行改了覆蓋檔，升級時由 git 自己報衝突。
- 未做的根治（供 [使用者] 日後決定）：把 `settings.json` 改成「版控放模板、安裝生成實檔」，可讓 skip-worktree 與 `--upgrade` 的合併邏輯整個消失，但會動到開發機現行流程與多支工具。

## 7. 審查裁決紀錄

[Codex] 7 BLOCK、[審查 agent] 4 BLOCK，互相印證；[AI] 逐條對碼或採信對方實跑後裁決如下。

| 來源 | 主張 | 裁決 |
|---|---|---|
| 兩者 | 只備份 `diff-filter=M` 會漏型別衝突、無備份刪檔 | **採納**。§3.1 步驟 3 改為逐路徑檔案系統檢查，衝突者移進備份（不採 [Codex] 的「拒絕安裝」：移進備份同樣不丟資料，且安裝不必中斷） |
| 兩者 | 中斷後重跑永久半套 | **採納**。`.git/atom-install-state.json` 記階段；fetch 後驗 ref；Windows 設 `core.longpaths` |
| [Codex] | 既有 `workflow/config.json` 自訂值失效 | **採納**。列為第二個覆蓋檔，升級走三方合併 |
| 兩者 | `user-init.sh` 覆蓋 `USER.md` | **採納**，[AI] 對碼確認（`hooks/user-init.sh:13-17`）。在 hook 本身修，不在安裝器繞 |
| 兩者 | 假家目錄隔離不足（`fix-hook-python.py:34`、bash `$HOME`） | **採納**。強制子程序環境、只呼叫目標樹工具 |
| 兩者 | `ensure-mcp.py` 會背景 `npm i -g` | **採納**，[AI] 對碼確認（`hooks/ensure-mcp.py:185-198`）。安裝器不呼叫它 |
| [Codex] | `--upgrade` 覆寫窗口無保護 | **採納**。持久存檔、以存檔為合併來源、原子寫入、try/finally 還原 |
| [審查 agent] | 已修改的 `settings.json` 讓背景同步分叉；`pull --ff-only` 必敗 | **採納**。接管時對覆蓋檔下 skip-worktree；升級改 `pull --rebase` |
| [審查 agent] | 從來源本地分支 fetch，未 push commit 會讓追蹤 ref 失真；shallow 來源 fetch 失敗 rc 仍 0 | **採納**，改成直接從真正的遠端 URL fetch |
| [審查 agent] | 無 `settings.json` 的新同事拿到擁有者的 `bypassPermissions` | **採納並改變現狀行為**：只帶 `hooks`＋`statusLine`。[AI] 判斷：授權範圍不該隨安裝靜默擴大；代價是新同事多幾次確認窗。[使用者] 可推翻 |
| 兩者 | `[Org]` 行不是每次都有 | **採納**，新段不再宣稱它報實況 |
| 兩者 | 漏列的文件引用、skill-count marker | **採納**，列入 §3.3 |
| [審查 agent] | 砍 `--json`、砍「目標不存在」模式 | **採納** |
| [Codex] | 首版延後 `--upgrade` | **[AI] 保留裁決：不採**。接管後覆蓋檔帶 skip-worktree，上游一改 `settings.json`（每次增減 hook 都會）pull 就中止；沒有 `--upgrade` 等於裝完第一次升級就卡住 |
| [審查 agent] | `--check` 併入 `--verify` | **[AI] 保留裁決：不採**。一個在安裝前從暫存 clone 跑、一個在安裝後跑，判定標準不同；兩者共用探測函式即可 |
| [審查 agent] | 使用者自建檔寫進 `.git/info/exclude` | **不採**。`??` 無害，背景同步只 add 記憶路徑 |
| [審查 agent] | CRLF 同內容檔 checkout 後仍是 CRLF | **不處理**。git 視為乾淨，無功能影響 |
