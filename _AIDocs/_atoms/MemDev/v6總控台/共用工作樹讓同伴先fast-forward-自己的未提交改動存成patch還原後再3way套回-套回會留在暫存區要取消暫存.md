# 共用工作樹讓同伴先fast-forward-自己的未提交改動存成patch還原後再3way套回-套回會留在暫存區要取消暫存

- Scope: global
- Author: holylight
- Source: session:8e847955 2026-10-16
- Confidence: [臨]
- Trigger: ff-only, 讓路, git apply --3way, 暫存區, 共用工作樹, 同伴合併, patch 收回, 未提交改動擋住合併
- Created-at: 2026-10-16
- Related: 共用工作樹有merge-head時不要git-commit-選擇性staging擋不住會把別人的合併以你的訊息收尾, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a
- Quote: 「其實我想把 v6 加的驗證通通拔掉.. 感覺根本做錯了方向.. 但我先選做 0,4,1,2； 3,5下一波 4我還想碎念：測試檔 也納入驗證不是鬼打牆的設定嗎(測->改->又測->又改.. 到底是要測需求目標還是要測 驗證code自己... )? 居然還連無關的都涵蓋..，LLM先前的決定是哪裡短路了(?)。看你描述的修法，我理解應該確實是認同我這想法的(針對目標進行驗證的腳本全部都不算)..…」

## 知識

- [臨] 情境：共用工作樹裡自己有未提交、還沒驗完的改動，同伴要把已驗完的分支 fast-forward 進 main，但兩邊改到同檔，live 有本地改動就 ff-only 不了。對方已驗完、自己還在半途 → 讓對方先。
- [臨] 做法：先確認沒有 .git/MERGE_HEAD；`git diff --binary -- <自己的檔> > scratchpad/x.patch`，`git apply --check -R` 確認反套得回去，再 `git apply -R` 把這幾檔還原成 HEAD（不用 stash，stash 是整個 repo 共用的，別的 session 可能 pop 走）；回同伴「你先」並背景輪詢 HEAD 變動；對方 ff 後 `git apply --3way x.patch` 套回。
- [臨] 坑：`git apply --3way` 套回後那些檔會留在暫存區（git status 第一欄 M）。共用工作樹裡任何 session 下一次 commit 都會把它們一起帶走，套回後立刻 `git restore --staged -- <檔>`。

## 行動

- 同伴要 ff 而自己半途：存 patch → 反套還原 → 讓對方先 → 3way 套回 → 取消暫存
- 不用 git stash 讓路
