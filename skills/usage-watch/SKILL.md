---
name: usage-watch
description: "查 Claude 帳號目前用量（所有機器／網頁合計的每週％、5 小時窗、漲速、預估用完、日用量）與異常，把用量摘要發到 Discord，測試用量通知，查看或註冊用量監控排程。使用者說「Claude 用量多少」「額度還剩多少」「這週會不會爆」「發用量到 Discord」「用量監控有沒有在跑」「測一下用量通知」「/usage-watch」時用。量單一 session 的 token 用 /token，不是這個。"
user-invocable: true
when_to_use: 觸發詞：Claude 用量, 額度還剩多少, 每週額度, 這週會不會爆, 用量摘要發 Discord, 用量監控狀態, 用量通知測試, 用量排程, usage-watch
metadata:
  pattern: tool-wrapper
---

# Skill：usage-watch（Tool Wrapper）

> 包住 `~/.claude/tools/usage-watch.py`：用 Claude Code 的登入 token 問 Anthropic 帳號額度，判異常、留紀錄、發通知。

## 什麼時候用

- 問帳號用量、額度剩多少、照這速度這週夠不夠。
- 要把目前用量發到 Discord、看圖表、測通知通不通、看排程有沒有在跑、重建排程。
- 追「是哪個專案在燒」：加本機段（只算這台電腦的 transcript）。
- 不用在：單一 session 用了多少 token（/token）、API 價目、帳單金額。

## 怎麼叫

| 要做的事 | 指令 |
|----------|------|
| 看帳號用量（約 1 秒） | `python ~/.claude/tools/usage-watch.py --account-only` |
| 帳號＋本機各專案（約 10 秒） | `python ~/.claude/tools/usage-watch.py` |
| 發摘要到 Discord | `python ~/.claude/tools/usage-watch.py --account-only --report` |
| 看圖表（每週走勢、每日用量、各專案 token） | `python ~/.claude/tools/usage-watch.py --chart`（產生 `workflow/usage-watch/chart.html` 並打開；加 `--account-only` 跳過掃本機 transcript） |
| 測通知（Windows＋Discord） | `python ~/.claude/tools/usage-watch.py --test-notify` |
| 各排程與最近一次結果 | `python ~/.claude/tools/usage-watch.py --status` |
| 建／重建每小時監控（異常才通知） | `python ~/.claude/tools/usage-watch.py --register` |
| 建／改定時發摘要（每天、工作日或指定星期） | `python ~/.claude/tools/usage-watch.py --register report --at HH:MM [--on weekdays\|mon,wed,fri]`（不加 `--on`＝每天） |
| 移除排程 | `python ~/.claude/tools/usage-watch.py --unregister [watch\|report]`（不指定＝watch） |

- 門檻參數（`--rate-alert`、`--daily-budget`、`--five-hour-alert`、`--week-factor`）與完整說明看 `--help`。
- 一般執行尾行 `USAGE_WATCH DONE account_ok= alerts= new= notified=`；`account_ok=0` 代表帳號查詢失敗，原因印在 `✖` 那行。
- 建排程、發 Discord 是對外動作：使用者這次有要才做。

## 怎麼讀結果

- **只有百分比、沒有 token 數**：Anthropic 只回帳號額度％（整數）；本機段的「加權 token」只算這台電腦。
- **① 突增**：與 45 分鐘～3 小時前那筆比的每小時漲幅；間隔太短整數％會被放大，所以不拿更近的比。
- **② 預估**：最近 24 小時速度（不足 12 小時退回本週平均）推到重置時會用到多少；早於重置用完就是異常。
- **日／週**：靠排程每小時累積的紀錄；剛建排程時「上週同期」「近幾週結算」會是空的。
- **查詢失敗「token 已過期」**：開一次 Claude Code 就會刷新；工具刻意不自己刷新（會弄壞 Claude Code 登入）。
- **紀錄位置**：`~/.claude/workflow/usage-watch/`（account／alerts jsonl、hourly.json、last-run.json、settings.json 放 Discord webhook，不進版控）。

## 反模式

- ❌ 用本機 transcript 的 token 數回答「帳號用了多少」（只算這台電腦）
- ❌ 自己拿 token 去打 API 或手算額度，繞過工具
- ❌ 使用者只問用量，就順手 `--register` 或 `--report`
- ❌ 把 webhook 網址或 settings.json 內容貼進回覆、commit 或文件
