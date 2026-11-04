# 記憶系統repo在github是公開的-進版控等於對外公開-內網位址與個人敏感資訊不寫進會上版控的檔

- Scope: global
- Author: holylight
- Source: gh repo view；Quote 自動回填外流的實例，commit 5f84adf3
- Confidence: [臨]
- Trigger: 公開 repo, repo 可見性, 對外公開, 外流, 進版控, gh repo view, 內網位址, 使用者原話回填
- Created-at: 2026-11-04
- Related: 放寬gitignore前先搬走不該公開的檔-背景同步隨時會把新放行的檔commit並push-搬檔結果要看完整輸出不先grep, git-已push-commit-勿改寫-雙-push-url-gitlab-main-force-保護致遠端分叉
- Quote: 「你很棒；請收割好經驗與知識，如果沒有其他事情，我就要關session了。」

## 知識

- [臨] ~/.claude 這個 repo 的 GitHub 遠端是公開的（gh repo view --json visibility 查得到），而且背景同步會自動 commit＋push 記憶卡：進版控等於對外公開，歷史收不回。
- [臨] 卡片內容不只來自寫卡的人：寫卡後自動回填的 Quote 是使用者原話，實例是使用者貼的內網共用資料夾路徑就這樣進了公開卡。防流出要連這類自動填的欄位一起看。

## 行動

- 寫卡、寫文件前先想這會不會進公開 repo；敦感內容放 personal/<user>/secret/
- 加防流出把關時，列出所有會寫進卡片的來源，含自動回填
