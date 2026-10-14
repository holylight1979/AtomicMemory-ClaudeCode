---
name: console
description: 多 session 協作總控台：一個入口三種用法——「/console 對人」開對人總控台、「/console 調度」開調度總控台、「/console 開工句 <軌名>」產生工作軌第一句。要多開 session 並行開工、開總控台、派工、寫開工句、Reload 後重新點名、判斷分頁可不可關時都該觸發。
user-invocable: true
triggers: 總控台, 對人總控台, 調度總控台, 雙總控台, 開工句, 派工, 工作軌, 多開 session, 並行開工, 收割後關, console
pattern: pipeline
---

# /console — 雙總控台＋工作軌

> 人只跟一個分頁（對人總控台）說話；調度總控台指揮各工作軌（每軌一個分頁、一棵 worktree、一條分支）。
> 給人讀的一頁說明：[references/guide-for-humans.md](references/guide-for-humans.md)。全軌現況：`python ~/.claude/tools/console-status.py`。
> 下文〔 〕是來源，代號對照在最後一節；「為什麼」去讀那張卡。

## 用法

| 指令 | 誰用 | 做什麼 |
|---|---|---|
| `/console 對人` | 人開的第一個分頁 | 當對人總控台：回人、裁定、把人的命令轉給調度 |
| `/console 調度` | 第二個分頁 | 當調度總控台：派工、對帳、合併、推送、收材料 |
| `/console 開工句 <軌名> [派工單路徑]` | 任一總控台 | 產生工作軌第一句，給人貼進新分頁 |

名詞：**軌**＝一件可獨立做完的工作；**信箱**＝`workflow/v6-inbox/`（`to-track-<軌>/` 派工單、`from-track-<軌>/` 交付信、`_console/` 總控台的帳與 log，擺法見 [dispatch.md](references/dispatch.md)）；**接續單**＝`memory/_staging/next-phase-<專案>.md`，第一段「現任」行寫兩個總控台現在的名字。

## 開始前：開幾個總控台、用什麼模型

- 一兩條軌 → 一個總控台兼兩職；三條以上平行軌才開雙總控台。〔原話〕
- 模型依工作分：調度與小修軌用 Opus；對人在裁定密集階段才用 Fable，平常 Opus。〔A、原話〕

## 共通硬規則（總控台與工作軌都守）

1. 送信前先 `ListAgents`，不寫死 claude-xx；名字 Reload 後會全變。〔C〕
2. 跟人說話用分頁標題看得到的軌名，不用 claude-xx。〔B〕
3. 每封信（回報、交付、派工）結尾寫「我在等：<誰／什麼>」，互等一眼看出來。〔接續單〕
4. 派工訊息正文第一行固定「派工 NNN：to-track-<軌>/<檔>.md」；交付信內文引用派工單路徑不算開工。〔#13〕
5. 等同伴回信不能空手結束回合：收件端只在下一次呼叫工具時才收得到。〔S〕
6. context 80% 起不再接新件；85% 寫交接備忘換手（[handoff-memo.md](references/handoff-memo.md)），不等自動壓縮。〔A、H〕
7. 閘誤擋：先報總控台，不反覆問人；修法是有名規則＋會紅案例，不放寬、不加例外清單。〔Y、Z1〕

## 用法一：對人總控台

### Step 1 報到
- **動作**：ToolSearch `select:SendMessage,ListAgents` → ListAgents 第一行是自己名字 → 讀接續單 → 「現任」行改成自己 → SendMessage 調度「對人總控台：<名字>」。
- **完成判定**：調度回「調度總控台：<名字>」（一個總控台兼兩職時略過）。

### Step 2 只做三件事
- **回人**：人的問題最高優先，同一回合先答再做別的；要人動手的事獨立成一則、放最前面。
- **裁定**：先填裁定帳三欄（[ruling-ledger.md](references/ruling-ledger.md)）；寫不出服務哪條目標就不裁、先問人。〔F〕
- **轉派**：人的命令整理成一句話交調度；不直接派工給工作軌。
- **不做**：派工、對帳、合併、推送、改碼、開子代理寫碼。〔A〕

### Step 3 什麼時候叫人去工作分頁（只有兩種）
- 某軌收尾閘擋滿、已發「放行這一回合」選擇題，要人去那頁點。〔I、K〕
- MCP 程式改了，要人 Reload Window 才載得到新程式。〔J〕

### Step 4 Reload Window 前後
- 前：兩個總控台寫好交接備忘，接續單「現任」行與待辦更新。
- 後：對人先 ListAgents 點名，對陌生名字只送「你是哪一軌？只回身份」→ 新名寫回接續單 → 轉給調度 → 調度改派工單裡的收件名。〔C、接續單〕

### Step 5 可關與多開
- 四項全過才跟人說「<軌名> 可關」：收割跑完、worktree 乾淨、無未結交付、scratchpad 要留的已複製到持久路徑。〔G〕
- 有分頁閒著＝沒派工，先問自己是不是漏派；人嫌慢就評估能不能再拆一軌。〔Z2〕

## 用法二：調度總控台

### Step 1 報到與核實
- **動作**：同對人 Step 1，改送「調度總控台：<名字>」；對名單上每個工作軌送「調度總控台改為 <名字>」；跑 `console-status.py`。
- **完成判定**：尾行 `CONSOLE_STATUS DONE …` 跟接續單對得上。

### Step 2 派工
- **動作**：寫派工單到 `to-track-<軌>/`（[dispatch.md](references/dispatch.md)）；新軌先建 worktree 與分支，再用用法三產生開工句；舊軌直接 SendMessage「派工 NNN：…」。
- 派工素材不以 `.py`／`.sh` 放進信箱，存成 `.py.txt`。〔T〕
- **完成判定**：工作軌回「<軌名> 收到開工」。

### Step 3 收信對帳
- 交付信存 `from-track-<軌>/`，對五項：改檔集＝自述、退避禁字（之後再／另外處理／延後）、CR、live `git status` 沒被動、對 main `merge-tree` 無衝突。〔D〕
- Codex 意見兩面判：一般寫法會踩的重大問題 → 退；快且具體有效 → 也收；兩者都不是 → 維護軌。文件類不跑 codex。〔#27、Z3〕

### Step 4 合併（裁定 #37 減量版）
- 合併回合先 `need_goal set`「把 X 合進 main 並推」；背景跑的尺不入帳，跑完前景 grep log 取收據。〔U〕
- 快照複跑只對閘本體改動；其他件信工作軌自附的收據與反證。〔#37〕
- codex 每軌一次，工作軌自跑那次算。〔#37〕
- 補驗只在候選基底落後 main 或解過衝突時跑；含最新 main 且可快轉的直接推。〔#37、D〕
- 合 MCP 工具類改動前，先確認還在改碼的分頁已 Reload 或關掉。〔#23〕
- 全量只在所有軌合完、分頁關到剩總控台時跑一次。〔#37、P、Z4〕

### Step 5 推送與收尾
- 推前看 `git log origin/main..main`：待推段有不是自己合的 commit，只推自己的或先問。〔X〕
- 推完同回合刪樹刪分支：`git worktree remove <路徑>` → `git branch -d <分支>`。〔G〕
- **完成判定**：`console-status.py` 顯示 `unpushed=0`、worktree 清單沒有該軌。

## 用法三：開工句 <軌名>

- **動作**：ListAgents 找調度名字 → 照 [kickoff.md](references/kickoff.md) §3 填軌名、worktree、分支、派工單路徑、調度名 → 包成 code block 給人。
- 第一句一定以軌名開頭（「<軌名>：你是工作軌…」），分頁標題才認得出。〔B〕
- 告訴人：開新分頁、貼上、點送出鈕；之後用分頁標題跟總控台核對。
- **完成判定**：該軌 SendMessage 調度「<軌名> 收到開工」。

## 工作軌守則（開工句已帶）

- 第一步 EnterWorktree；之後只用 worktree 絕對路徑，不碰 live；交付用 SendMessage 送全文（[delivery.md](references/delivery.md)）並附 live 未動證明。〔R〕
- 含 git 字樣的 Bash 指令會被 worktree 守門拒絕：寫成 worktree 內的 Python 啟動器再跑，啟動器檔名也不能含 git。〔Q〕
- 接單先核實路徑與跑法；pytest 收 0 案不是綠。〔W〕
- 只跑目標 verify，不跑全量；commit 在分支上、不推。〔P、X〕

## 反模式自查（命中任一就回頭改）

- ❌ 開工句、派工單、交接備忘寫死 claude-xx
- ❌ 總控台自己改碼或開子代理寫碼；對人直接派工給工作軌
- ❌ 每件都快照、每次合完都補驗、反覆跑全量（#37 已減量）
- ❌ 信結尾沒寫「我在等」；空手結束回合等回信
- ❌ 一有事就叫人去工作分頁（只有兩種情況）
- ❌ 開工句第一句不是軌名

## 來源代號

- 原話：track-skill-console 派工原話（2026-10-14）；接續單：`memory/_staging/next-phase-v6.0-寫程式碼的進化.md` 規則清單與「現任」行
- #13、#23、#27、#37：`workflow/v6-inbox/_console/裁定帳-*.md`（本機信箱）
- A [[feedback-總控台多軌流程五規則-雙總控台對人與調度分開-原設計者提問同回合先答-寫碼全拆去工作session-各session自跑codex交報告總控台只裁定]]
- B [[feedback-對使用者指稱session一律用分頁標題看得到的軌名-claude-xx是session間通訊名他看不見]]
- C [[vscode-reload-對並行ai-session的影響]]
- D [[總控台多軌合併經驗-退回同一面第二次就定死規則或改設計-整批合併後的紅先單跑歸軌補修不reset-接續單要寫舊步驟作廢與停工恢復條件]]
- F [[裁定類判斷的校準法-每筆先填服務目標框架來源零成本反事實三欄-被翻率當數字-審查者角色的讀入事件是收到外部主張要裁定前]]
- G [[feedback-多軌派工的git紀律-小幅改動直接在main改驗推不開軌-合進main同一回合移除worktree刪分支-補驗過即推不積累-軌名要望文生義]]
- H [[盤點並行session的context用量-讀projects下各transcript最後一筆assistant-usage三欄相加-名字對應靠worktree資料夾與listagents啟動時間]]
- I [[寫碼查核擋滿後要等人時立刻發askuserquestion停住-靠結束回合等會每回合再被擋一次次數累加-派工單寫走到要問那步停下要先確認人在或直接發題掛著]]
- J [[mcp的node端程式改了要開新session才載到-同機其他session的mcp程序仍跑舊碼-python端每次spawn立即生效]]
- K [[收尾放行確認的選項要用固定字樣-放行這一回合-自訂選項文字使用者選了也不算]]
- P [[並行實作線不要各自跑全量驗證-簡報只給目標verify清單-全量由主持人整合後單獨跑一次]]
- Q [[worktree隔離session的bash守門拒絕任何含git字樣的指令-codex的skip-git-repo-check與pytest參數檔名都中-改寫成worktree內的python啟動器再跑]]
- R [[工作session切進worktree後被隔離寫不到worktree外-交付改用sendmessage回全文-cwd不在worktree時收據根對不上]]
- S [[跨session訊息只在收件端下一次呼叫工具時才送進來-光結束回合等不到同伴回覆-要等人答完再醒可先背景跑短sleep當計時器]]
- T [[總控台別把py檔放進派工信箱-查核閘只看副檔名與同根就記成改碼-owed程式檔刪了也不查存在-義務永掛要人放行]]
- U [[總控台合別人驗過的分支也走need-goal閘-checkout同步工作樹算改程式要先set樹-commit前要合併後的收據-背景bash的尺不入帳要前景grep-log取收據]]
- W [[接派工單先核實檔案路徑與跑法-pytest收0案不是綠-掃描型verify腳本要直接python跑]]
- X [[feedback-共用工作樹push前先看待推範圍-git-push推的是整段待推歷史-含別人等口令的commit就只推自己的或先問]]
- Y [[feedback-閘門反覆擋同一件事時要修判定的根因-不要一再請使用者放行]]
- Z1 [[feedback-閘誤判的修法不是加例外清單-把欠帳本回合放行改碼的判定抽成獨立模組-每情境一條有名字的規則加會紅案例-擋訊息印規則名與證據-不准整輪不擋或放寬]]
- Z2 [[feedback-多session協作時主持端要派工問進度分工寫文件-不要只回信等信-閒置session要給解決問題的工作-文件分開寫再彙整]]
- Z3 [[feedback-文件類交付不跑codex不採codex意見-驗收只看活項對照與原設計者讀得懂-codex自檢對文件挑的不一致一律不處理除非指出活項漏了]]
- Z4 [[全量驗證與agent測試並行跑會互相干擾出假失敗-作準的全量要單獨跑]]
