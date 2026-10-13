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

## 行動

- 派工前先問：這件是小幅改動嗎？是就直接在 main 做，不開軌
- 合併回合的固定尾巴：補驗 → 推 → worktree remove → branch -d → 回報
