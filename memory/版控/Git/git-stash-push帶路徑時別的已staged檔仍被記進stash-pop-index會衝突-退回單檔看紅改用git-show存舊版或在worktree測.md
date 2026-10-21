# git-stash-push帶路徑時別的已staged檔仍被記進stash-pop-index會衝突-退回單檔看紅改用git-show存舊版或在worktree測

- Scope: global
- Author: holylight
- Source: session 27f1e0a9 2026-10-21（PR #4 整併時退回 mail.py 測紅）
- Confidence: [臨]
- Trigger: git stash, stash push --, stash pop --index, 退回舊碼看紅, could not write index, patch does not apply, 單檔退回, 舊碼紅
- Created-at: 2026-10-21
- Related: 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a
- Quote: 「好奇你的流程怎麼沒有寫之前有出的 側寫視角 那些? XD」

## 知識

- [臨] 實踩：工作樹有 A、B 兩檔已 staged，跑 `git stash push -- A` 想只退回 A 測舊碼紅；`git stash show --stat` 卻列出 A、B 兩檔（stash 的 index 樹記的是整份 index）。之後 `git stash pop --index` 先撞到別的 session 同時寫 index（could not write index），重試又因 B 已在 index 而 patch does not apply；stash 保留不丟，最後用 `git checkout stash@{0} -- A` 取回、比對 0 差異後才 drop。
- [臨] 判準：有其他已 staged 檔、或同一工作樹有其他 session 在動 git 時，不要用 stash 做「退回單檔看紅」。改用 `git show HEAD:<路徑> > 暫存檔` 把舊版當另一支腳本跑，或在獨立 worktree 測。

## 行動

- 退回單檔看紅：優先 git show HEAD:<路徑> 存成暫存檔跑，或在 worktree 測；不在有 staged 檔的共用工作樹用 stash
- stash pop 失敗：先 git stash list／show --stat 確認內容還在，用 git checkout stash@{N} -- <路徑> 逐檔取回並比對 0 差異，再 drop
