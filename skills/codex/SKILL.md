---
name: codex
description: 叫 Codex 當第二意見（唯讀審查）或施工者（在專用工作樹裡改檔），先填同步包讓它的綜觀跟 CC 同步。CC 自己判斷叫不叫：結論錯了代價大（設計方向、影響多處、不可逆）、設計討論已有自己的答案要另一個 context 來挑、要找邊界反例、有邊界清楚且驗收寫得出來的活可以並行交出去；使用者說「加派 codex」「問 codex」「叫 codex 審」「交給 codex 做」時也用。只改文件、註解、措辭時不用；已查到答案只差使用者確認時不用。切換舊的 Codex Companion 監督開關是 /codex-companion，不是這個。
user-invocable: true
when_to_use: 觸發詞：加派 codex, 問 codex, codex 第二意見, codex 審查, 叫 codex 審, 交給 codex 做, codex 施工, codex agent, 同步包, codex-call
metadata:
  pattern: pipeline
---

# Skill：codex（Pipeline）

> 讓 Codex 的綜觀認知跟當下 session 的 CC 幾乎同步，再請它獨立判斷或施工。【原話】「Codex 的"綜觀認知"要與當下 session 的 CC llm 幾乎完全同步，而不是針對性的亂驗」
> 入場由 CC 判斷，沒有 hook 閘。每條規矩後面標來源：【原話】使用者說的；【實證】紀錄裡發生過；【推論】AI 推出來的，使用者沒定。

## 一、要不要叫

叫：
- 結論錯了代價很大：設計方向、影響多處、不可逆。【原話】「Codex 建議要用綜觀很確定會造成重大問題再派」
- 設計討論或回答使用者的設計問題時，CC 已經有自己的答案，需要另一個 context 來挑。【原話】「session 內的思考與參與討論，務必加派 codex」
- 要找邊界反例，這是 Codex 的強項。【實證】多模型交叉審查：五個 BLOCK 全部成立
- 有一塊施工邊界清楚、驗收條件寫得出來的活，可以交出去並行做。【推論】

不叫：
- 只改文件、註解、措辭。【原話】文件整理那次：「codex 對文件的意見一概不採」
- 已經查到答案，只差使用者確認。【推論】

判斷不看改了幾檔、幾行。【實證】舊閘用「≥4 檔或 150 行」當門檻，被 9 支一次性腳本誤觸

## 二、流程（前一步沒過，不進下一步）

腳本：`python ~/.claude/skills/codex/scripts/codex-run.py`（`new`、`run` 兩個子命令，`--help` 看全部參數）。暫存檔放 session 的 scratchpad。

### Step 1：先寫好自己的答案
- 審查模式：CC 打算回給使用者的結論，或這次的設計／改動說明，就是第 7 段。
- 施工模式：施工單（要做的事、驗收、可改／不准碰、驗證清單附哨兵行）就是第 7 段。
- 完成判定：第 7 段的內容已經寫好。

### Step 2：生提示詞骨架
- `codex-run.py new --mode review|build --out <scratchpad>/prompt.md`
- 第 2 段的尺由腳本原文照貼（IDENTITY〈設定衝突與程式需求〉、coding-style 優先序＋〈設計取捨的尺〉、code-thinking 全文），CC 不手抄。【推論】Codex 自己的 `~/.codex/AGENTS.md` 沒有這把尺，還把「最小 diff」排得很前面，判設計題容易偏向維持現況
- 完成判定：尾行 `CODEX_RUN_NEW DONE`。

### Step 3：照實填同步包（每段的填法寫在段內）
- 第 1 段逐字照抄原話，CC 自己想加的限制不放這裡。【實證】SGI 那題第一輪被帶歪，頭號來源就是轉交時夾了一句自己加的限制「不動存檔格式」
- 第 3 段只放事實、推論、不知道的；結論與建議只放第 7 段。【推論】放進第 3 段，「先不看第 7 段、自己下結論」那步就失效
- 第 5 段只貼知識段原文，不貼卡名清單。Codex 沒有依題目自動帶卡的機制，自己翻索引也挑不準；它另有一份自己的記憶（`~/.codex/memories/`），跟我們的不同步。
- 第 6 段給 repo 路徑讓它自己讀，不只給 diff；開場自動載入的 CLAUDE.md 也列路徑。【實證】有紀錄的誤判全是「沒看到 diff 以外」那一型：只給 diff、commit 後才送審變成空 diff、沒追蹤的新檔不在 diff 裡、路徑被遮罩
- 完成判定：檔內沒有「〔待填」（`run` 會擋）。

### Step 4：跑
- 審查：`codex-run.py run --mode review --prompt-file <prompt.md> --cwd <repo> --out-dir <scratchpad>/<題目> [--guard <其他會讀到的 repo>]`
- 施工：先建好專用工作樹和分支，再 `codex-run.py run --mode build --prompt-file <prompt.md> --cwd <工作樹> --out-dir <…> --guard <live repo>`
- 沙箱由腳本照模式固定帶（審查 read-only、施工 workspace-write）。不帶的話會照 `~/.codex/config.toml` 預設的 `danger-full-access` 跑，live 也寫得到。【實證】讀設定檔確認的
- 跑前跑後各記一次 guard 的 git／svn status，有變就 exit 1。【實證】唯讀沙箱起不來時就是靠這個護欄
- 唯讀沙箱起不來：記下錯誤原文，把 repo 用 `git archive`（svn 用 `svn export`）或複製到 scratchpad，加 `--sandbox workspace-write --cwd <副本> --guard <原 repo>` 重跑一次。不用 `danger-full-access`。【推論】
- 未實測：workspace-write 沙箱裡 pytest 有沒有可寫的暫存目錄；唯讀沙箱下 pytest 整個中止過。【實證】
- 完成判定：尾行 `CODEX_RUN DONE … ok=1 guard_changed=0`；原始輸出在 `<out-dir>/codex-output.md`，Codex 自己的執行紀錄在 `codex-stderr.txt`。

### Step 5：CC 裁決（不交給 Codex）
- 每一條先問服務哪句原話（第 1 段，或第 2 段的尺）。指不出來的就是飄移，寫一句理由，不做。【原話】「LLM 判斷後其實屬於"飄移"的，直接不做」
- Codex 回得很短或說沒問題：先看 `codex-stderr.txt` 確認它真的讀了檔，再採用。【實證】審查者回沒問題或回得很短時，採用前先看執行紀錄
- 它說要改目標或縮小目標：沒附「做不到」的證據（只說成本高）就不採。【推論】依 code-thinking「只有一種情況能提改目標」
- 「重大」先轉成反例親自重現：成立就當場修，先寫測試看它紅、修到綠；重現不了，寫出是哪一行碼擋住它。【實證】第二意見分歧裁決卡
- 「快且有效」的當場做掉。【原話】「有關且確實有問題，就應該要立即修正」
- 駁回不能只說「我方測試全綠」；採納也不能只說「Codex 說的」。【實證】
- 不開第二輪找新洞；第二輪只確認採納的那幾條修好了沒有。【實證】對抗審沒封頂：g12 審了十二輪，Codex 每輪都找得到新邊角
- 施工模式：CC 自己讀 diff，在工作樹裡自己重跑驗證清單（通過數以 CC 跑的為準），對照原話驗收之後才 commit。【實證】Codex 那邊的沙箱環境不一定跑得起來
- 回覆使用者分三段：CC 的答案、Codex 的答案與分歧、CC 的裁決附理由。【原話】等價認知那張卡
- 完成判定：每條 Codex 發現都有「採／不採＋理由」。

## 三、叫之前要讀的卡（trigger 會自動帶進來）

- `memory/工作流/協作與並行/` 的「Codex 歪樓三因與入場用法」
- 等價認知那張（personal）、總控台不被 codex 牽著走、審查挖出的問題飄移就不做、第二意見分歧裁決、評 AI 分析先看結論

## 檔案

- `assets/sync-package.md`：同步包第 1～6 段（兩種模式共用）
- `assets/review-prompt.md`：審查模式（第 7 段＝結論草稿、兩級嚴重度、紅旗、停止條件）
- `assets/build-prompt.md`：施工模式（第 7 段＝施工單、停下來回報的條件）
- `scripts/codex-run.py`：`new` 組骨架並貼尺；`run` 擋未填、固定沙箱、比對前後狀態、存原始輸出
