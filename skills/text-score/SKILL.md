---
name: text-score
description: 文字評分（G15）手動叫：照文字規格逐條問免費小模型裁判，對使用者這次要的需求評一則回覆或一份文件好不好讀。使用者說「評一下這則」「幫我評分」「這段好不好讀」「評分上一則回覆」「text-score」時用。
user-invocable: true
triggers: 評分這則, 評一下這則, 幫我評分, 評分上一則, 這段好不好讀, 文字評分, text-score
pattern: tool-wrapper
---

# /text-score — 叫一次文字評分

> 後端 `~/.claude/tools/text-score.py`：照文字規格逐條問內網免費模型裁判，印評分表與一行摘要，留帳 `Logs/guard-text_score.jsonl`。
> 只在使用者叫的時候跑，只附不擋。規格裡的「目標」由 `--goal` 填，沒給就印「不評：沒有當下的需求目標」、不問裁判。

## 先定 --goal

- `--goal` 寫使用者這次要達成的那一件事：用使用者的話、一句（例：「sales CLI 能列出每個產品的數量」）。評的是這段文字對這個目標交代得清不清楚。
- 從這次對話的使用者原話取；看不出來就用 AskUserQuestion 問一題、附推薦的那一句，不要自己編。

## 意圖 → 動作

| 使用者說 | 做什麼 |
|---|---|
| 評上一則回覆／這則回覆 | 把那則回覆全文原樣寫進 scratchpad 的暫存 .txt，跑 `python ~/.claude/tools/text-score.py <暫存檔> --goal "<需求一句>"` |
| 評某個檔 `<路徑>` | `python ~/.claude/tools/text-score.py "<路徑>" --goal "<需求一句>"` |
| 指定規格 `<代號>` | 上面指令加 `--spec <代號>`（規格在 `~/.claude/text-specs/`，沒給用 `text_score.default_spec`） |

## 完成判定與回報

- 尾行 `TEXT_SCORE DONE spec=… pass=… fail=…`：回報摘要那一行（`評分 N/M｜沒過：…`），沒過的條目各一句白話說哪裡不好讀；不改寫原文，除非使用者接著要。
- 印「不評：沒有當下的需求目標」：補 `--goal` 重跑，不要回報成評過。
- 印「裁判不在，未評」：照實說沒評成，不換付費模型重評。
- exit 2：把 stderr 原樣回報（常見：檔案路徑錯、規格代號錯）；暫存檔用完刪掉。
