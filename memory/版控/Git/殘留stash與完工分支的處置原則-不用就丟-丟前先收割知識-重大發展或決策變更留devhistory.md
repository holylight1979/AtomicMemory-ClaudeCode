# 殘留stash與完工分支的處置原則-不用就丟-丟前先收割知識-重大發展或決策變更留DevHistory

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: stash, 殘留分支, 完工分支, git 整理, 要不要丟, drop, 舊版記憶檔, DevHistory, 收割後再丟
- Created-at: 2026-10-14
- Source: session:242d1f2a#0c7b293b 2026-10-14
- Quote: 「1. 我剛才有另外讓準備關閉的 B5 做了一次 gitlab 庫的整理 (把已經完工但是還殘留的分支去掉)，可能需要你讓他確認一下。 2.「任務後的日常紀錄」不用了基本原則就是丟掉；如果裡面有重要的知識或經驗要記得先收割，另外如果有留存的必要(重大發展或決策變更)，也能放到 _AIDocs 下的 DevHistory。」

## 知識

- [臨] 使用者定的原則：完工但殘留的 stash／分支／worktree，不用了基本就是丟掉，不用回頭問；丟前兩件事：①裡面若有重要的知識或經驗，先收割成記憶卡；②若有留存必要（重大發展、決策變更），放 _AIDocs/DevHistory。兩者都沒有就直接 drop／branch -d。
- [臨] 判準配套：分支只刪「已完全合進 main」的（git branch --merged 或 merge-base --is-ancestor 核實，用 -d 不用 -D）；未合的列清單回報不刪；快照樹與進行中的軌留。

## 行動

- 整理 git 殘留：已合的分支與 worktree 直接清；stash 先看 diff，收割知識、必要時寫 DevHistory，然後 drop，不反問
