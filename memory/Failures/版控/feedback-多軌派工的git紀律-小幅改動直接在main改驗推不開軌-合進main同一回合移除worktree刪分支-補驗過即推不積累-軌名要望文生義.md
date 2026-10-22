# feedback-多軌派工的git紀律-小幅改動直接在main改驗推不開軌-合進main同一回合移除worktree刪分支-補驗過即推不積累-軌名要望文生義

- Scope: global
- Author: holylight
- Quote: 「git 樹開枝散葉看不出做完沒、衝突與 push 積累。小幅改動不開分支不開 worktree，直接在 main 改、跑目標 verify、推；合進 main 即 worktree remove＋branch -d，同一回合做完；補驗過即推；新軌名字要能望文生義。」
- Confidence: [臨]
- Trigger: 多軌派工, worktree 太多, 開枝散葉, 小幅改動不開分支, 合完刪 worktree, branch -d, 推送積累, 軌名, 總控台合併, 單檔小修, 純文件改動
- Created-at: 2026-10-13

## 知識

- [臨] 使用者指正（多軌並行一天後）：git 樹開枝散葉看不出做完沒、衝突與未推積累。從此規則：①小幅改動（純測試、純文件、單檔小修、clean-up）不開分支不開 worktree，直接在 main 改、跑目標 verify、推；只有多檔或跨部位改動才開軌。②合進 main 即 `git worktree remove`＋`git branch -d`，同一回合做完，不留。③補驗過即推，不等下一件。④軌名要讓人望文生義（track-bkp 被問是不是備份 → 改 track-b-hooks），派工單檔名與開工句第一句寫全名。
- [臨] 原因：對人的可讀性——使用者看 git 樹與分頁標題判進度，留著的 worktree、分支、未推 commit 都是「做完沒」的雜訊。
- [臨] 使用者提醒 ：工作 session 交付信尾端補一句「三把尺的腳本和比對資料在 scratchpad，關分頁後可能被清掉」，這種補刀型提醒一沒注意重要腳本就掉。實查：調度回報「已複製」時只複製了腳本、比對資料沒複製。規則：「可關分頁」判定固定四項——收割 atom 跑完、worktree 乾淨、無未結交付、**scratchpad 裡要留的東西（腳本、比對資料、log）已逐檔複製到持久路徑並列清單**；交付信裡任何「可能會掉」的提醒要當待辦處理，不當備註。
- [臨] 原設計者再次指正：「為什麼 TECH.md 這種改文件也通通都開 git 分支？這不是妥妥的浪費時間＋空間＋token 嗎」——規則早在（小幅改動不開軌），這次還是把整份 TECH 重檢、checklist 更新都當「工作軌一律進 worktree」。補判準：**工人 session 做的文件軌也一樣**——只改文件就讓工人直接在 live 改派工單指定的那幾個檔，交付信列改了哪些檔，總控台看 diff 後在 main 提交；開工句文件版不帶 EnterWorktree 與啟動器。文件軌進 worktree 的代價全是為程式設的（整樹 checkout、啟動器、CHANGELOG 衝突、合併後驗證）。
- [臨] 原設計者指正：「TECH.md 這種改文件也通通開 git 分支，妥妥浪費時間＋空間＋token」。規矩：只改文件、不改程式的軌（TECH、README、checklist、DevHistory、派工單、說明檔）不開 worktree、不開分支：工人直接在 live 改派工單「只准動這幾個檔」點名的檔，交付信列改了哪些檔，總控台看 diff 直接在 main commit＋推；程式＋文件一起改的才開軌；已在跑的文件軌做完這次不換。

## 行動

- 派工前先問：這件是小幅改動嗎？是就直接在 main 做，不開軌
- 合併回合的固定尾巴：補驗 → 推 → worktree remove → branch -d → 回報
