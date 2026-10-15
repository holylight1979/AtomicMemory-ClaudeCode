# 改名被gitignore忽略的資料夾要同一個commit改gitignore-否則新名字底下的檔全變未追蹤-一次git-add就把不該公開的東西推出去

- Scope: global
- Author: holylight
- Source: 調度總控台核對信箱改名派工 2026-10-14（47fc009b 補了 .gitignore）
- Confidence: [臨]
- Trigger: 資料夾改名, .gitignore 改名, 未追蹤檔, check-ignore, 答案不能公開, 忽略規則跟著搬
- Created-at: 2026-10-15
- Related: 新repo第一次提交前先放gitignore並看副檔名分布-系統自有repo整包加也會把各機遙測檔掃進版控
- Quote: 「確認看看還有什麼沒做或者沒收割的，要關session了」

## 知識

- [臨] 實例：本機信箱 `workflow/v6-inbox/` 改名 `workflow/inbox/` 的派工清單只列了程式與文件，漏了 `.gitignore`。若照做，清理軌搬進新資料夾的 B5 答案與觀察表會變成未追蹤檔，共用工作樹裡任何人一次 git add 就進公開 repo。改名時在 .gitignore 加新名、舊名並存到舊資料夾刪完，搬檔前用 `git check-ignore -v <新路徑下的檔>` 確認命中。

## 行動

- 改名或搬移被忽略的資料夾：同一個 commit 改 .gitignore，搬檔前 check-ignore 實測新路徑
