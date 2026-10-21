# 開工句範本（四種，角括號換掉就能貼）

> 給誰：總控台產生開工句時照填；人只負責開新分頁、貼上、按送出鈕（VS Code 裡 Enter 只換行）。
> 共同規則：第一句一定以角色名或軌名開頭（分頁標題取自第一句，人靠標題認分頁）；不寫死 claude-xx，總控台名字寫「送信前先 ListAgents 確認」。

## 目錄
1. 對人總控台
2. 調度總控台
3. 工作軌
4. 待命 session
5. 總控台之間的固定訊息
6. 由腳本送出（/console 開工）

---

## 1. 對人總控台（人開的第一個分頁）

```
對人總控台：你是對人總控台，執行 /console 對人。專案根 <專案根絕對路徑>；接續單 <專案根>\memory\_staging\next-phase-<專案>.md（沒有就建，第一段寫「現任」行）。我主要只跟你說話：我的問題同一回合先答；我的命令轉給調度總控台去派。
```

## 2. 調度總控台（三條以上平行軌才開；一兩條軌由對人兼任）

```
調度總控台：你是調度總控台，執行 /console 調度。專案根 <專案根絕對路徑>；接續單 <接續單路徑>；信箱 <專案根>\workflow\inbox\。對人總控台是 <對人名>（送信前先 ListAgents 確認，名字會變）。開工先 SendMessage 對人一句「調度總控台：<你的名字>」，再跑 python ~/.claude/tools/console-status.py 核實現況。
```

## 3. 工作軌（`/console 開工句 <軌名>` 產生的就是這段）

```
<軌名>：你是工作軌 <軌名>，調度總控台是 <調度名>（送信前先 ListAgents 確認，名字會變）。第一步用 EnterWorktree 切進 <worktree 絕對路徑>（分支 <分支>，已存在，不要新建；不存在就 SendMessage 調度要，不要自己建）。派工單在 <派工單絕對路徑>，讀完全文照做，先核實裡面的路徑與跑法。切進去之後所有讀寫只用 worktree 絕對路徑，不碰 <live 專案根>。含 git 字樣的 Bash 指令先寫成 worktree 內的 Python 啟動器（檔名不含 git）再跑。只跑派工單列的目標 verify，不跑全量、不輪詢；commit 在分支上、不推。交付用 SendMessage 送全文給調度（照 delivery 範本），附 live 未動證明，結尾寫「我在等：…」。開工前先 SendMessage 調度一句「<軌名> 收到開工」。
```

填法：
- `<軌名>`：望文生義，例 `track-login-fix`，不用編號代號。
- worktree 與分支由調度先建好（`git worktree add <路徑> -b <分支> main`），開工句只叫它切進去。
- 工作軌已經存在、只是派下一件：不用開工句，調度直接 SendMessage「派工 NNN：to-track-<軌>/<檔>.md」。
- 判斷入口（哪些要判斷、誰判）寫在派工單的「判斷入口」段（dispatch 範本），開工句只指過去，不在開工句裡寫死規則。
- 交出開工句前再對一次：還對得上最新的計畫（接續單、checklist）嗎？剛改的東西有沒有讓之前給過的開工句過時？有就一起改。

## 4. 待命 session（換手前先開好，接手前不耗 token）

```
待命：你是待命 session。只做三步，之後不讀檔、不做別的事：①ToolSearch query select:SendMessage,ListAgents 載入工具 ②ListAgents，最上面「This session is <名字>」那行是你的名字 ③SendMessage <要接的角色的現任名> 一句「待命對人／調度總控台：<你的名字>」。收到「接手…」＋接續單路徑才執行 /continue <接續單路徑>。
```

## 5. 總控台之間的固定訊息

| 情境 | 誰送給誰 | 第一行 |
|---|---|---|
| 報到 | 新總控台 → 另一個總控台 | `對人總控台：<名字>` ／ `調度總控台：<名字>` |
| 換總控台 | 現任 → 待命 | `接手對人總控台：<接續單路徑>`（或調度） |
| 調度換人 | 新調度 → 各工作軌 | `調度總控台改為 <名字>` |
| Reload 後點名 | 對人 → 陌生名字 | `你是哪一軌？只回身份` |
| 派工 | 調度 → 工作軌 | `派工 NNN：to-track-<軌>/<檔>.md`（第一行固定這樣寫，程式只看第一行判斷是不是派工） |
| 收割後關 | 調度 → 工作軌 | `收割後關：收割（寫不了的卡列代寫清單給調度）、樹乾淨、無未結、scratchpad 要留的複製到持久路徑，四項做完回報` |
| 寫交接備忘 | 總控台 → 快滿的分頁 | `寫交接備忘：停手、不 commit，照 handoff-memo 範本回 20 行內備忘` |

## 6. 由腳本送出（`/console 開工 <軌名> <派工單路徑>`）

§3 的開工句本文不變，只是改由程式送進新 session、不用人貼：

1. 總控台照 §3 填好，整段存成 `<專案根>/workflow/inbox/_console/kickoff-<軌名>.txt`（信箱不進版控）。
2. 跑 `python ~/.claude/tools/console-spawn.py --track <軌名> --worktree <worktree 絕對路徑> --branch <分支> --prompt-file <上面那個檔> --permission-mode <總控台自己的模式> --model <派工單寫的模型 id>`。
   腳本用 `claude --bg` 在 worktree 起 session（cwd 只准是登記過的 worktree）、把整檔當第一句送出、輪詢到那個 session 說出「<軌名> 收到開工」。
3. 尾行 `CONSOLE_SPAWN_CHECK PASS`：它印的「ListAgents 名字」就是該軌的 claude 名字，寫回接續單「軌對應」行；「模型＝<id>」是那個 session 實際在用的模型（讀它的 transcript）。人要看那個 session 的畫面或答它的問題：`claude attach <短 id>`、`claude logs <短 id>`。
4. 尾行 `FAIL`：多數情況 stdout 已印「退回人貼：停在「<哪一步>」」與開工句 code block，原樣轉給人照 §3 的老辦法貼；不重試超過一次。兩種 FAIL 不退人貼（人貼救不了），只印 stop 指令：
   - 「模型不符：指定＝…／實際＝…」：session 已開工、沒殺。要換模型就 `claude stop <短 id>` 後改 `--model` 重跑；將就用就照常派工。
   - 「session 回 API 錯誤」：例如模型 id 不存在。claude 不會拒起，第一回合回錯後就停著，腳本讀到就立刻 FAIL、印 claude 的原文。`claude stop <短 id>` 收掉，修正後重跑。

填法：開工句第一個詞仍是軌名（腳本靠「<軌名> 收到開工」認報到）；`--permission-mode` 一律明帶，腳本不猜、不假設新 session 繼承總控台的模式。`--model` 照派工單寫的模型給完整 id（派工單要寫模型與理由：閘本體與小修軌用 Opus，例 `claude-opus-5-5`；對人裁定密集才用 Fable，例 `claude-fable-5-1`）。別名（`opus`、`fable`）對不上 transcript 記的完整 id，會判模型不符。不帶 `--model` 就用 `workflow/config.json` 的 `console.spawn.default_model`；那裡也沒設，就吃 Claude Code 預設。
