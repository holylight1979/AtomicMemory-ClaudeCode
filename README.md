# 原子記憶系統 Atomic Memory

讓 Claude Code 擁有「長期記憶」的**擴充套件**——增強 Claude Code 與人的協作：AI 記得你們一起做過的決定、踩過的坑、養成的習慣，換一個 session、換一個專案都不失憶。

---

## 如何安裝

請見 [Install.md](Install.md)。

知識庫有兩個不同的範圍：**根層**（`~/.claude/`，原子記憶系統本身＋跨專案的根本知識，來自**本系統自己的版控庫**，全員共用同一個庫、隨 pull / push 同步）與**專案層**（`{專案}/.claude/memory/`，跟著**專案的版控**走，pull 就有、不用安裝）。Install.md 裝的是根層。

---

## 如何使用

安裝完成後照你原本的方式使用 Claude Code 就可以了，系統在背景自動運作。第一次進到某個專案時，請 AI「初始化原子記憶庫」一次即可（步驟見 [Install.md](Install.md)）。

---

## 它平常在做什麼

- 你每問一句，它就翻遍記憶卡片，挑最相關的幾張塞給 AI——你不用提醒「上次我們說過……」。
- AI 學到教訓（跑失敗、被你糾正、做了決策）會自動寫成新卡片，下次不再犯。
- 卡片用過有效會加分升級，久沒用會淡出，記憶庫不會越長越亂。
- 回合收尾時檢查 AI 有沒有敷衍、有沒有把該做的事推給「下次再說」。
- 想看記憶狀態（需 Claude Code 開著才有資料）：
  1. Dashboard：打開 `http://127.0.0.1:3848/`；
  2. 更生動的「腦內世界」視覺化：用瀏覽器直接開 `tools/workflow-guardian-mcp/world.html`。

---

## 核心設計理念

一句話：**每一次的知識與經驗，全部積累、分門別類，並在需要的那一刻精準送到 AI 眼前，一個字都不浪費。**

- **全部積累**：對話裡學到的東西（決策、踩坑、你的偏好）不能隨 session 結束而消失，要變成一張張「記憶卡片（atom）」存下來。
- **分門別類**：每張卡片都有明確的範疇（版控、工作流、某個技術領域……），沒分類的知識不收——找得到才叫記得。
- **高精準＋零浪費**：你每問一句，系統只挑「跟這句最相關」的幾張卡片給 AI 看；該想起的要完整送到，不相關的一行都不塞。
- **跨 session、跨專案不失憶**：核心知識全專案共用，專案知識跟著專案走。
- **自動分層**：卡片有信心等級——剛學到的是「臨時」，反覆驗證有效才升為「固定」；久沒用的自然淡出。
- **分使用者**：同一台機器多人使用時，各自的個人資料與偏好分開存放。
- **團隊共享**：專案知識庫存在專案的 `.claude/memory/`，跟著 GIT / SVN 版控走；隊友 pull 下來就接上最新的經驗與決策——別人踩過的坑，你不用再踩。

### 與原始 Claude Code 有何差異

| 面向 | 原始 Claude Code | 本系統 |
|------|------|------|
| 記憶範圍 | 綁在單一專案，換專案就不記得 | 核心知識跨專案共用，專案知識另存 |
| 什麼時候拿出來用 | 不主動；只在啟動時載入一份索引，其餘靠 AI 自己去翻 | 你每問一句，就自動挑最相關的卡片塞給 AI |
| 品質分級 | 沒有，寫了就是寫了 | 臨時 → 觀察 → 固定；用過有效才升級，沒用的淡出 |
| 學習來源 | AI 自己決定要不要寫 | AI 顯式記錄為主，另自動萃取失敗教訓與你的決策 |
| 收尾把關 | 沒有 | 回合結束時檢查有沒有敷衍、有沒有把該做的事推給下次 |
| 看得見嗎 | 只能翻檔案 | 有網頁 Dashboard 與「腦內世界」視覺化 |

---

## 多台電腦／多人同時寫記憶

兩台電腦各自寫了新卡片再同步，三個「索引檔」（記憶卡片的目錄：`MEMORY.md`、`_ATOM_INDEX.md`、`_atom_index.json`）會在同一個地方各多一行，git 自己合不起來。系統把這件事包掉了：

- **你什麼都不用做**。前提兩個：這台電腦的 `~/.claude` 已更新到含這個機制的版本；而且在 Claude Code 裡跑過一次同步指令（pull／merge／rebase），或手動跑過一次 `python tools/merge-atom-index.py --install`。之後 git 合併索引檔時走系統自己的「語意合併」（兩邊各加的那幾列都留下、計數相加），不會停下來問你。
- **會看到的訊息**：第一次同步時 `[Guardian:MergeDriver] 已自動安裝索引三檔合併驅動`；萬一 git 還是停在索引檔衝突，你（或 AI）下 `git rebase --continue` 之類的指令時會先看到 `[Guardian:IndexConflict] 已自動合併並 add 索引檔：…`，然後正常繼續。
- **自檢**：`python ~/.claude/tools/merge-atom-index.py --status` 末行「已安裝」就是好的。git 停住而訊息沒出現時，手動跑 `python ~/.claude/tools/merge-atom-index.py --resolve` 再繼續。
- **只管三個索引檔**。其他檔案的衝突照舊由你或 AI 處理。
- **rebase 時「HEAD／ours」是同事那邊**：git 做 rebase 是先站到對方的基底上再重放你的 commit，看衝突標記時方向別搞反。
- **唯一會留給人判斷的情況**：`MEMORY.md` 表格以外的手寫文字，兩邊改了同一段。系統把兩邊都留著、加 `<<<<<<<` 標記、不自動 add，交給正在同步的 Claude Code 看內容決定。
- **Fork 等圖形工具**：驅動裝在 git 本身的設定裡，所以 Fork 按 pull 也受益；但「自動安裝」只在 Claude Code 裡發生——這台還沒裝好前用 Fork 拉會停一次，之後用 Claude Code 拉一次或跑一次 `--install` 就好。Fork 定位是看圖與介入，不為它另補機制。

- **SVN 專案也一樣**：TortoiseSVN 或命令列 `svn update` 停在索引三檔衝突（狀態 C）屬正常——SVN 沒有合併驅動可裝。回到 Claude Code 下 `svn commit`（或 `svn resolve`）時，hook 先自動把三檔合好並標記 resolved，接著正常提交；也可手動 `python ~/.claude/tools/merge-atom-index.py --resolve --cwd <工作副本>`。
- **專案記憶樹的換行不必你管**：每次寫入記憶後，系統順手把該專案的 `.claude/memory/` 統一成 LF——git 專案在 `.gitattributes` 加一段規則、SVN 專案對已版控檔設 `svn:eol-style=LF`；改動跟著下一次提交一起上，不用到專案 session 貼任何 prompt。

細節（給 AI 或想深究的人）：[_AIDocs/MultiMachineMemorySync.md](_AIDocs/MultiMachineMemorySync.md)。

---

## 技術細節

想深入了解系統技能、運作流程、與 Claude Code 的接合方式 → [TECH.md](TECH.md)。
目前版本見 `version.json`。

---

## License

[GNU General Public License v3.0](LICENSE)
