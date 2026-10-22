---
name: text-score
description: 文字評分（G15）手動叫：收尾預設只自動評「交付改了哪些程式」那一則回覆，其他回覆或文件要評時用這個。使用者說「評一下這則」「幫我評分」「這段好不好讀」「評分上一則回覆」「text-score」時用。
user-invocable: true
triggers: 評分這則, 評一下這則, 幫我評分, 評分上一則, 這段好不好讀, 文字評分, text-score
pattern: tool-wrapper
---

# /text-score — 叫一次文字評分

> 後端 `~/.claude/tools/text-score.py`：照文字規格逐條問內網免費模型裁判，印評分表與一行摘要，留帳 `Logs/guard-text_score.jsonl`。
> 收尾自動評只評交付「改了哪些程式」的那一則（規則 TEXT_SCORE_CODE_REPLY_ONLY，`text_score.reply_scope`）；其他都靠這裡叫。只附不擋。

## 意圖 → 動作

| 使用者說 | 做什麼 |
|---|---|
| 評上一則回覆／這則回覆 | 把那則回覆全文原樣寫進 scratchpad 的暫存 .txt，跑 `python ~/.claude/tools/text-score.py <暫存檔>` |
| 評某個檔 `<路徑>` | `python ~/.claude/tools/text-score.py "<路徑>"` |
| 指定規格 `<代號>` | 上面指令加 `--spec <代號>`（規格在 `~/.claude/text-specs/`，沒給用 `text_score.default_spec`） |

## 完成判定與回報

- 尾行 `TEXT_SCORE DONE spec=… pass=… fail=…`：回報摘要那一行（`評分 N/M｜沒過：…`），沒過的條目各一句白話說哪裡不好讀；不改寫原文，除非使用者接著要。
- 印「裁判不在，未評」：照實說沒評成，不換付費模型重評。
- exit 2：把 stderr 原樣回報（常見：檔案路徑錯、規格代號錯）；暫存檔用完刪掉。
