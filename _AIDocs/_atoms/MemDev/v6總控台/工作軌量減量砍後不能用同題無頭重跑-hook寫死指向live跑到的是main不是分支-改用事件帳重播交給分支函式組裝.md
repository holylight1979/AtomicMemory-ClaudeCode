# 工作軌量減量砍後不能用同題無頭重跑-hook寫死指向live跑到的是main不是分支-改用事件帳重播交給分支函式組裝

- Scope: global
- Author: holylight
- Source: workflow/inbox/_console/減量二輪共同規則與檔案歸屬.md 量尺段；session 9af7f47a 2026-10-27
- Confidence: [臨]
- Trigger: 砍後量法, 無頭重跑量砍後, 事件帳重播, hook 指向 live, worktree 量測, 省多少三欄, 減量量測
- Created-at: 2026-10-27
- Related: 用事件帳重播量改動省多少前先拿舊碼重播跟實跑transcript逐字對帳-對上了才換新碼量-重播輸入要還原到當時

## 知識

- [臨] settings.json 的 hook 指令寫死跑家目錄的 ~/.claude/hooks（live），在 worktree 開的受測 session 一樣跑 live main：工作軌用「同題無頭重跑」量自己那刀的砍後，量到的是 main 不是分支；調度中途合併進 live 還會讓同一跑前後半段跑不同程式。
- [臨] 做法：用 004 事件帳重播——transcript 裡同一批輸入依序交給分支的函式組裝，先拿舊碼重播證明逐字等於帳上，再換分支版比；真要無頭跑就用 --settings 指到 worktree 的 dispatcher 並在交付寫明，期間不合併進 live。
- [臨] 實例：減量二輪六軌全照重播量（導讀卡 15/15、擋訊息 13/13＋12/12、注入 5 跑×2 回合逐字對上才比）；004 題沒有導讀卡與日常噪音源，T1、T4 在題上省 0，另用真實 session transcript 重播量日常情境。

## 行動

- 派減量軌時在派工單寫明砍後量法：事件帳重播、先證舊碼逐字對帳
- 工作軌在跑無頭時調度不合併進 live
