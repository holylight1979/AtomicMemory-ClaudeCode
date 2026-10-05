---
name: org
description: 公司層共用記憶（org）一站式入口：接上公司記憶 repo、查看接入與身份職能狀態、把知識寫到公司層、把 skills／MCP／專案工具登記成工具卡。使用者說「接上公司記憶」「記到公司層」「登記工具」「我現在是什麼職能」時用。
user-invocable: true
triggers: 接上公司記憶, 公司記憶, 公司層, 記到公司層, 登記工具, 工具卡, 我的職能, org, 中台記憶
pattern: tool-wrapper
---

# /org — 公司層共用記憶

> 公司記憶 repo＝所有專案都看得到、都能寫的一層記憶。本 skill 把四件事包成一個入口，
> 使用者用講的就好，不必記指令。機制細節見 `~/.claude/TECH.md` §4.4；腳本參數以
> `python ~/.claude/tools/org-memory.py --help` 為準。

## 使用方式

```
/org                 # 預設 status
/org status          # 接上沒、有幾顆、同步狀態、我是誰／什麼職能
/org join [路徑]     # 新機器一步接上（沒 clone 就自動 clone）
/org scan            # 把 skills／MCP 登記成工具卡
/org scan <專案根>   # 另掃該專案 .claude/tools/*.py
```

寫公司知識沒有子命令：直接呼叫 `atom_write`，`scope` 給 `org`。

## 意圖 → 動作

| 使用者說 | 做什麼 |
|---|---|
| 啟動行有 `❓ [Org] …還沒接上，使用者也還沒被問過` | 第一則回覆前用 AskUserQuestion 問：放預設路徑／指定路徑／先不接，再照答案跑 `--join [路徑]` 或 `--decline` |
| 接上公司記憶／公司層怎麼沒有／`[Org] 尚未接上` | `python ~/.claude/tools/org-memory.py --join [路徑]` |
| 這台先不要接公司層／不要再問我 | `python ~/.claude/tools/org-memory.py --decline` |
| 公司層狀態／我現在是什麼職能／誰能裁決 | `python ~/.claude/tools/org-memory.py --status` |
| 把這條記到公司層／全公司都該知道 | `atom_write(scope="org", domain=<Lv1>, …)` |
| 登記工具／掃工具卡 | `python ~/.claude/tools/org-memory.py --scan-tools [--project <專案根>]` |
| 公司層有沒有 X 的工具／知識 | `memory_search(query=…)`，結果 `scope` 為 `org` 者即公司層 |

## 各動作的完成判定與回報

### join
- 成功：輸出含 `[org-memory] 完成：`，exit 0。回報一句「已接上，重啟 Claude Code 後啟動行會有 `[Org] 公司層 N 顆`」。
- 不給路徑即可：落點用共用 config 的 `org_memory.default_root`；接上狀態寫在本機 `workflow/org-memory.local.json`（不進版控），不會弄髒 `~/.claude` 工作樹。
- exit 2「沒有本機路徑」／「無從 clone」：config 沒有 `default_root`／`repo_url` 也沒給路徑 → 問使用者公司記憶 repo 的網址或本機路徑，只問這一件。
- exit 1「clone 失敗」：把 stderr 末段原樣回報（多半是 GitLab 權限或網路），不改用別的方式硬接。

### status
- 讀 JSON 後用白話回三句：公司層接上沒與顆數、同步狀態（`uncommitted`／`ahead`／`behind` 皆 0 即已同步）、身份與職能來源（`roles_source`：`ad`＝AD 群組、`role.md`＝人工覆寫、`none`＝查不到）。
- `ready` 為 false → 直接接著做 join，不反問。
- 職能不對：`python ~/.claude/tools/init-roles.py --project-cwd <專案根> --me <職能>` 人工覆寫；刪掉該 `role.md` 即回到 AD 解析。

### 寫公司知識
- 判準：「換一個專案、換一個人，這條還成立嗎？」成立才寫 org；只對本專案成立寫 `shared`；只關於本人寫 `personal`。
- `domain` 必須是公司層既有 Lv1（`<公司層根>/.claude/memory/shared/_taxonomy.json` 的 `domains`）；沒有合適的才 `allow_new_category=true` 開新 Lv1，並在回報裡說明開了什麼。
- 寫完不必手動 commit：背景 vcs-sync 會把公司層的變更 commit 並 push。

### scan
- 只建缺的卡，既有卡不動；進入點檔案消失的卡會被標 `Status: deprecated`（不刪）。
- 回報「建了幾張、退役幾張」；輸出有「略過」「失敗」的逐條原樣列出。

## 鐵則

1. 公司層的檔案一律經 `atom_write`／`org-memory.py` 寫，不直接編輯公司 repo 裡的 atom 檔。
2. 不替使用者決定「誰能裁決」：`review.deciders` 名單只在使用者明說時才改。
3. 腳本失敗就回報 stderr，不繞道、不重試三次以上。
