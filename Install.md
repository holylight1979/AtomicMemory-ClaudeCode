# 安裝 — 由 AI 全程代跑

你不用手動裝任何東西：把本套件放到 `~/.claude/`，把一段 prompt 貼給 Claude Code，剩下的它自己做。

---

## 安裝

### 0. 版控庫

<!-- repo-url -->
* GitHub：`https://github.com/holylight1979/AtomicMemory-ClaudeCode.git`
* GitLab（公司內網）：`https://gitlab.uj.com.tw/holylight/ClaudeCode-AtomMemory.git`
<!-- /repo-url -->

### 1. 在 `~/.claude/` 開一個 Claude Code 對話

`~/.claude/` 就是 Claude Code 的使用者設定資料夾（Windows 在 `C:\Users\<你的帳號>\.claude`，用過 Claude Code 就會存在）。用 VS Code 開啟這個資料夾（Windows 可在資料夾上按右鍵「以 Code 開啟」），再打開 Claude Code 面板。

### 2. 貼 prompt

把上面的網址換進 `[版控庫]`，整段貼給 Claude Code：

```
1. 請把 [版控庫] 這套原子記憶系統（Atomic Memory）git clone 或下載到 ~/.claude/；
   ~/.claude/ 已有內容的話，先 clone 到暫存資料夾再合併，不要覆蓋我現有的個人檔案。
2. 先讀 ~/.claude/Install-forAI.md 完整流程；
3. 檢查我環境的必備套件是否齊全（Python / Node.js / Ollama / Git / 向量 DB 套件），列出缺項告訴我怎麼補；
4. 照 Install-forAI.md 的 AI 執行流程合併安裝（不覆蓋我現有的 settings.json permissions）；
5. 最後跑驗證 checklist 並回報「安裝完成 / 尚缺 X」。
```

* AI 讀 `Install-forAI.md` 時會逐項檢查需要哪些東西、缺了怎麼辦，你基本上不用自己查。
* AI 會自己走完檔案合併 + npm 套件 + MCP 設定 + Ollama 模型 + Vector Service + 驗證；缺套件會主動列給你去補，不會硬裝。

---

## 驗證安裝

同樣在 `~/.claude/` 下開一個**新的** session，貼這段請 AI 自檢：

```
請確認我電腦下 ~/.claude/ 的原子記憶系統已正確安裝（hooks、Vector Service、Ollama 模型、Skills）。
```

---

## 在「專案」裡使用 — 3 步到底

記憶分兩層、分別從版控拉取：**根層**（`~/.claude`，本套件＋跨專案的根本知識）就是上面裝的這份；**專案層**（`{專案}/.claude/memory/`）跟著各專案自己的版控走，不需要再安裝，pull 下來就接上。

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
- 兩個重要縮寫：**「執P」**（分階段執行＋驗證＋上 GIT＋給下階段 prompt）、**「上GIT」**（把當次異動一次推上 GIT / SVN）——直接問 AI 會解釋，也會照規則執行。
- 深入技術 → [TECH.md](TECH.md)；給 AI 看的安裝細節與降級邏輯 → [Install-forAI.md](Install-forAI.md)。
