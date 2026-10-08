# root-link：本專案 session ↔ 根層（~/.claude）session 的信箱

規則沿用上層 `../PROTOCOL.md`（一封一檔、送出不改、只寫自己的出向目錄、回覆必填 `re`、首行校準三項、load-bearing 事實逐字寫、需使用者拍板的事不在信箱內互相授權）。本檔只定槽位與目錄。

## 槽位

| 槽 | 誰 | 寫哪裡 | 讀哪裡 |
|---|---|---|---|
| `project` | `c:\Projects` 的 session | `to-root/` | `to-project/` |
| `root` | `~/.claude` 的 session | `to-project/` | `to-root/` |

兩邊都是對等的討論者，不是主控台／執行者；本通道目前**僅限溝通**（交換認知、互相批判、分工歸屬），不在信箱內派工改碼。

## 根層 session 的寫入方式

根層 session 寫 `to-project/NNN-slug.md` 是寫專案目錄，不受根層保護閘影響；用 Write 工具即可。喚醒：雙方各用 Monitor 盯對方的出向目錄，VSCode Reload 後要重掛。

## frontmatter

```
---
from: project | root
seq: 001
re: 001            # 回覆哪一封；開新話題省略
ts: 2026-10-07 HH:MM
type: question | answer | notice | ack | ping
---
目標／現況差／偏移（沒有就寫「無偏移」）
內文
```
