# 安裝 — 由 AI 全程代跑

你不用手動裝任何東西：把一段 prompt 貼給 Claude Code，它會用 git 取得本套件、跑安裝器，剩下的它自己做。

> **先分清兩個範圍**：知識庫有「根層」與「專案層」兩個不同的範圍限定，各自有各自的版控庫。
>
> | 範圍 | 在哪裡 | 裝什麼／記什麼 | 版控庫 |
> |------|------|------|------|
> | **根層** | `~/.claude/` | 原子記憶系統本身 + 跨專案通用的根本知識（通則、工具踩坑） | **原子記憶系統自己的版控庫**（下面 §0）——全員共用同一個庫，根層知識隨 pull / push 同步；只有個人啟動檔（`USER-{帳號}.md`、`IDENTITY-{帳號}.md`）不進版控 |
> | **專案層** | `{專案}/.claude/memory/` | 這個專案的決策、踩坑、共識 | **專案自己的 GIT / SVN**——跟著專案 pull，不需安裝 |
>
> 本檔只講「根層」的安裝。專案層見最後的「在專案裡使用」。

---

## 安裝

### 0. 版控庫（原子記憶系統本身的，不是你專案的）

就是你正在看這份文件的這個版控庫——clone 網址在版控庫頁面的 Clone / Code 按鈕裡。

### 1. 在 `~/.claude/` 開一個 Claude Code 對話

`~/.claude/` 就是 Claude Code 的使用者設定資料夾（Windows 在 `C:\Users\<你的帳號>\.claude`，用過 Claude Code 就會存在）。用 VS Code 開啟這個資料夾（Windows 可在資料夾上按右鍵「以 Code 開啟」），再打開 Claude Code 面板。

### 2. 貼 prompt

把版控庫的 clone 網址換進 `[版控庫]`，整段貼給 Claude Code：

```
請幫我安裝原子記憶系統（Atomic Memory），版控庫網址：[版控庫]
1. 用 git clone -c core.longpaths=true 取得（不要下載壓縮檔），clone 到家目錄下的 atomic-memory-src 資料夾，不要直接動 ~/.claude。
2. 讀 clone 下來的 Install-forAI.md，照它的步驟一步一步做，不要自己加步驟。
3. 缺什麼套件只列給我看、告訴我怎麼補，不要自己安裝。
4. 做完照 Install-forAI.md 的方式回報；需要我重開 Claude Code 時明確告訴我。
```

* 安裝器會先檢查環境（Python / Node.js / Git / Ollama / 向量套件），缺的項目會寫明「少了什麼功能、怎麼補」；缺項不影響安裝，之後再補即可。
* 你原有的 `settings.json`（權限等設定）、個人檔案都會保留；被更新的檔案先備份到 `~/.claude/backups/`，AI 會告訴你備份位置。
* 原本的 `~/.claude/CLAUDE.md` 會換成本系統的版本；裡面有想保留的內容，請貼進 `USER-{你的帳號}.md`（見下方「啟動檔維護」）。
* 裝完 AI 會請你**重開 Claude Code**，再做下一節的驗證。

---

## 驗證安裝

重開 Claude Code 後，同樣在 `~/.claude/` 下開一個**新的** session，貼這段請 AI 自檢：

```
請執行 python ~/.claude/tools/install.py --verify，把結果逐項告訴我。
```

結果每項是 `PASS`（正常）、`DEGRADED`（能用，但少了某個功能，會寫怎麼補）或 `FAIL`（要修，會寫怎麼修）。沒有 `FAIL` 就是裝好了。

## 之後要更新

貼這段給 Claude Code：

```
請執行 python ~/.claude/tools/install.py --upgrade，把結果告訴我；成功的話提醒我重開 Claude Code。
```

---

## 在「專案」裡使用 — 3 步到底

上面裝的是**根層**（原子記憶系統本身；全員共用同一個版控庫，根層知識隨它同步）。**專案層**是另一個範圍：`{專案}/.claude/memory/` 跟著專案自己的 GIT / SVN 走，隊友 pull 專案就接上，**不需要再安裝任何東西**。

- **STEP A**：在專案根目錄開啟 VS Code（或在專案目錄啟動 Claude Code CLI）。
- **STEP B**（首次）：告訴 AI「初始化原子記憶庫，並且立即將知識分類、分層存儲」——AI 會建立 `{專案}/.claude/memory/MEMORY.md` 與分類結構，系統從此認得這個專案。
- **STEP C**：把 `{專案}/.claude/memory/` 上傳 GIT / SVN 讓團隊共享。到這就完成了，照你原本 Claude Code 的方式繼續使用——系統在背景自動運作。

---

## 啟動檔維護（IDENTITY / USER）

這幾個檔案決定 AI「是誰」和「你是誰」，每次啟動都會載入：

| 檔案 | 它是什麼 | 你要動哪個 |
|------|------|------|
| `IDENTITY.md` | AI 的行為契約，單一真相 | 想改 AI 行為 → 直接改這裡；改完同步一份到 `templates/IDENTITY.template.md`（檔案損毀時的還原來源） |
| `IDENTITY-{你的帳號}.md` | 選配的個人擴充槽，預設空置 | 只想加「僅屬於你」的行為 → 寫這裡，並在 `CLAUDE.md` 加一行 `@IDENTITY-{你的帳號}.md` 啟用 |
| `USER-{你的帳號}.md` | 你的個人資料與偏好 | 改這裡。每次啟動會自動拷成 `USER.md`，所以不要直接改 `USER.md` |
| `BOOTSTRAP.md` | 第一次使用、上面兩檔還是空的時候，引導你問答填寫的模板 | 不用動 |

---

## 更順手的補充

- **第一個使用者**想先讓 AI 預載某部分知識：`/read-project <目錄> <方向>` → 掃描並寫入知識庫，之後也記得上傳 GIT / SVN。
- **接續使用者**：從版控 pull 專案的 `.claude/memory/` 即可直接接上團隊記憶。
- **多台機器／多人同時寫記憶**：各自新增 atom 後 pull 會在索引三檔（`MEMORY.md`／`_ATOM_INDEX.md`／`_atom_index.json`）衝突。不必手動裝任何東西：Claude Code 裡第一次跑 pull／merge／rebase 時，hook 自動把合併驅動寫進這台機器的 git 設定，之後索引三檔自動合併；git 真的停住時，`git rebase --continue` 前 hook 也會先自動解掉這三檔。**已裝過舊版的機器不必預先做什麼**：更新（見上方「之後要更新」）之後，下一次在 Claude Code 裡跑 pull／merge／rebase 時 hook 就會自動裝；連更新當下若停在索引三檔，`git rebase --continue` 前新 hook 也會先自動解掉。想立刻確認可手動跑 `python tools/merge-atom-index.py --install`（可選）。自檢 `python tools/merge-atom-index.py --status`。**SVN 專案**：update 停在索引三檔衝突後，回 Claude Code 下 `svn commit` 前 hook 自動解。**專案記憶樹的換行（LF）**也在每次寫入記憶後自動統一（git 寫 `.gitattributes` 區塊、SVN 設 `svn:eol-style`），不需要到專案 session 貼任何 prompt。說明見 [README](README.md)「多台電腦／多人同時寫記憶」。
- 兩個重要縮寫：**「執P」**（分階段執行＋驗證＋上 GIT＋給下階段 prompt）、**「上GIT」**（把當次異動一次推上 GIT / SVN）——直接問 AI 會解釋，也會照規則執行。
- 深入技術（含各依賴缺了會怎樣、疑難排解）→ [TECH.md](TECH.md)；給 AI 照著跑的安裝步驟 → [Install-forAI.md](Install-forAI.md)。
