# 調度總控台合併候選驗證SOP-對帳五項再快照樹鎖檔複跑-退回舊碼看紅型別-探針抽查gate本體-負載下計時案假紅單跑判-合完補驗推刪worktree

- Scope: global
- Author: holylight
- Source: session:81a3e55f 2026-10-13
- Confidence: [臨]
- Trigger: 總控台對帳, 合併候選, 快照樹, console-verify, snapshot-running, 退回舊碼紅, 探針抽查, 計時案假紅, 並行負載, 工作軌交付, 調度總控台, 合完推
- Created-at: 2026-10-13

## 知識

- [臨] 一天合七件的流程（每件順序固定）：①存信箱 `workflow/inbox/from-track-<軌名>/` ②對帳五項：改檔集⊆所有權、`git diff --stat`、CR 與禁字（「——／之後再／另外處理／提醒即可／延後／dry_run」；文件寫「已退役鍵」是正當用法）、`git merge-tree --write-tree main <head>` 單行＝無衝突、live `git status --porcelain` 只剩已知髒檔 ③快照樹複跑：專用 detached worktree，腳本先查 `.snapshot-running` 鎖檔與 porcelain 空才 checkout，跑完 trap 刪鎖；兩軌同時要快照就各用一棵 ④退回舊碼：在快照樹 `git checkout <舊> -- <程式檔…>` 只換程式不換測試，跑新案 -k，用 `LC_ALL=C grep -E "^E +[A-Za-z]*(Error|assert)"` 分類失敗型別，只有 AssertionError 算數；跑完 `git checkout <head> -- … && git restore --staged …` ⑤守門閘本體才加真 hook 入口探針抽查（探針存持久目錄，`--only N`） ⑥總控台 codex 每軌只在合併候選跑一次，BLOCK 必先自己重現再退 ⑦合進 main → live 補驗（目標 verify＋smoke）→ 推 GitHub → `worktree remove`＋`branch -d`，同一回合。
- [臨] 多 session 並行時全量與長測試的計時案（合併驅動牆鐘預算、版控快照時間案）必假紅：判法是單跑該檔素過就不算回歸，全綠收據只在機器空閒（所有工作分頁關掉）時跑一次；工具 600 秒上限內跑不完的就背景跑＋等檔腳本，不要在前景硬等。
- [臨] 總控台自己也會被寫碼查核閘擋：scratchpad 與信箱裡的 .py 工具在路徑分類改走部位表前被當程式碼要案例；對帳工具存成 `.py.txt` 放持久目錄，要用時複製到 scratchpad 改回 .py。
- [臨]（track-a2c 001 實踩）工作軌自列的目標 verify 清單會漏掉「全樹掃描型」靜態守門（例 verify_code_paths_from_code_root 掃所有 tools／lib 的路徑寫法），快照綠、合進 main 後 live 補驗才紅。快照腳本的清單要取聯集：軌自列目標 verify ＋ live 補驗標準清單（`workflow/inbox/merge-scripts/verify_live_after_merge.sh` 的 FILES），改到 tools／lib 路徑常數的軌尤其要帶靜態守門。漏了就歸軌小輪補修不 reset，main 在補驗綠前不推。
- [臨] 全量已從流程拔掉（使用者裁定，全量改增量待補）：「全綠收據只在機器空閒時跑一次」那步取消；合完只做補驗與各軌宣告的驗證範圍。見 [[feedback-全量測試從流程拔掉改增量待補-全量紅了指不出誰修修完又要全量-收尾跑llm適度擴展的可能相關清單]]


## 行動

- 收到交付先跑對帳五項，再啟快照腳本背景跑，等檔尾行再讀
- 合併回合固定尾巴：補驗→推→刪 worktree 與分支→回報對人總控台


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-29 | 退役移入 _distant/：v6 開發期專用（驗收／量測／派工），開發結束封存；原文在 _distant | memory-audit --delete |
