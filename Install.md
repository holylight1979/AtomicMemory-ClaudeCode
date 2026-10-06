# 安裝 — 由 AI 全程代跑

你不用手動裝任何東西：把一段 prompt 貼給 Claude Code，它會用 git 取得本套件、跑安裝器，剩下的它自己做。

> 本檔裝的是**根層**（`~/.claude/`：系統本身＋跨專案通則），來自本系統自己的版控庫，全員共用；只有個人啟動檔（`USER-{帳號}.md`、`IDENTITY-{帳號}.md`）不進版控。
> **公司層**（公司記憶庫）與**專案層**（`{專案}/.claude/memory/`）不用安裝，見下方「接上公司層」「在專案裡使用」；三層分工見 [README.md](README.md)。

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

## 接上「公司層」— 每台機器一次

公司記憶庫是全公司、所有專案共用的一份記憶，自己一個 git／svn repo（網址已寫在系統設定裡）。根層裝好後第一次啟動 Claude Code，AI 會問你要放哪（預設放家目錄下的 `CompanyAtomsMem`／自己指定／先不接）；回答後它自己 clone、接上，「先不接」會記住、不再問。之後對 AI 說「接上公司記憶」可補接、「公司記憶接上沒」可查狀態。啟動訊息有一行 `[Org] 公司層 N 顆（路徑）` 就是接上了。

---

## 在「專案」裡使用 — 3 步到底

專案層 `{專案}/.claude/memory/` 跟著專案自己的 GIT / SVN 走，隊友 pull 專案就接上，**不需要再安裝任何東西**。

- **STEP A**：在專案根目錄開啟 VS Code（或在專案目錄啟動 Claude Code CLI）。
- **STEP B**（首次）：告訴 AI「初始化原子記憶庫，並且立即將知識分類、分層存儲」——AI 會建立 `{專案}/.claude/memory/MEMORY.md` 與分類結構，系統從此認得這個專案。
- **STEP C**：把 `{專案}/.claude/memory/` 上傳 GIT / SVN 讓團隊共享。這一次之後不用再手動——新卡片由背景同步自動上傳，程式碼仍等你說「上GIT」（分界見 [README.md](README.md)）。

專案根底下有多個可單獨開啟的子專案（Client／Server／tools…）時，AI 開在子專案會問你一次「記憶歸哪個根」，選定後重開 session 生效；第一個使用者想先讓 AI 預載某部分知識：`/read-project <目錄> <方向>`。

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

## 深入

各依賴缺了會怎樣、疑難排解 → [TECH.md](TECH.md)；給 AI 照著跑的安裝步驟 → [Install-forAI.md](Install-forAI.md)。
