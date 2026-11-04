# 放寬gitignore前先搬走不該公開的檔-背景同步隨時會把新放行的檔commit並push-搬檔結果要看完整輸出不先grep

- Scope: global
- Author: holylight
- Source: 私人卡分層（secret 資料夾）實作過程，commit 6ec419ac
- Confidence: [臨]
- Trigger: 放寬 gitignore, gitignore 放行, 負向規則, 背景同步, 自動 push, knowledge harvest, 放行名單, 資料搬移順序
- Created-at: 2026-11-04
- Related: 改名被gitignore忽略的資料夾要同一個commit改gitignore-否則新名字底下的檔全變未追蹤-一次git-add就把不該公開的東西推出去

## 知識

- [臨] 有背景自動 commit＋push 的 repo，改 .gitignore 放行一個資料夾的那一刻，裡面所有檔都變成待提交；要留在外面的檔必須在改 .gitignore 之前就搬走或排除。實踩：先改 .gitignore 才搬檔，搬檔工具被範疇閘擋下、輸出又被 grep 濾掉，沒發現失敗，那段時間背景同步還推了一次（這次運氣好沒帶到那些檔）。
- [臨] 順序：先搬檔並看完整輸出確認成功 → 用 git add -n 列出會進版控的清單逐項對 → 最後才放行。對外公開的 repo 推出去就收不回。

## 行動

- 改 .gitignore 放行前：先搬走不該進版控的檔，跑 git add -n 對清單
- 會改動資料的指令不要用 grep 濾輸出，失敗訊息會被濾掉
