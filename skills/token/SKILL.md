---
name: token
description: 量一場或多場 Claude Code session 實際處理了多少 token（輸入分未快取、讀快取、建快取，加輸出與合計，含子代理），不換算美金。使用者說「/token」「這場用了多少 token」「消耗多少 token」「token 用量」「比較兩場 token」時用；預設量目前 session，也可給 session id 前綴或 transcript 路徑一起列表比較。
user-invocable: true
triggers: /token, token 用量, 消耗 token, 這場用了多少 token, 量 token, 比較兩場 token, session 花了多少 token
pattern: tool-wrapper
---

# Skill：token（Tool Wrapper）

> 包住 `scripts/token_usage.py`：讀 transcript，算 session 實際送進模型與產出的 token。

## 什麼時候用

- 問這場（或指定幾場）session 用了多少 token、消耗多少。
- 比較兩場以上（例如同一題開關某設定各跑一場）誰比較省。
- 不用在：API 價目、context window 多大、tokenizer 怎麼切字——那些不是量實際用量。

## 怎麼叫

路徑相對本 skill 資料夾（載入時給的 Base directory）：

| 要做的事 | 指令 |
|----------|------|
| 量目前這場 | `python <skill 資料夾>/scripts/token_usage.py` |
| 量／比較指定幾場 | `python <skill 資料夾>/scripts/token_usage.py <目標> [<目標> ...]` |
| 給程式讀 | 加 `--json` |

- 目標＝session id（完整或前綴，例如 `bc7c5340`）或 transcript `.jsonl` 路徑。
- 不給目標：用目前 session；拿不到時改用目前資料夾對應的最近一份 transcript，並印出選了哪份。
- 完整參數看 `--help`。成功時尾行 `TOKENS DONE sessions=<n>`。
- exit 1＝有目標找不到或前綴對到多份（原因印在輸出）；exit 2＝意外錯誤（看 stderr）。照實回報，不自己改手算。

## 欄位

| 欄 | 意思 |
|----|------|
| 回覆 | assistant 回覆數（同一則拆成多行只算一次，含子代理） |
| 輸入 | 未快取＋讀快取＋建快取 |
| 輸出 | 模型產出的 token |
| 合計 | 輸入＋輸出 |
| 子代理檔 | 一起算進來的子代理對話檔數 |
| 分鐘 | 第一筆到最後一筆紀錄相隔（含等人回話的時間） |

## 怎麼讀數字

- **只報 token、不換美金**：價目會變、各類 token 單價不同；token 才是兩場之間能直接比的量。
- **輸入幾乎都是讀快取**：每次回覆都把整段 context 再讀一遍，所以回覆數越多輸入越大；想省先看回覆數。
- **依序跑的 A/B**：先跑的那場付「建快取」，後跑的可能讀到前一場建好的快取；比較時把建快取分開看。
- **每組只跑一場雜訊很大**：差不到約 10% 不算結論，要多跑幾場再下判斷。

## 反模式

- ❌ 自己逐行加總 transcript 的 usage（同一則回覆拆成多行，會重複算）
- ❌ 把數字換算成美金回報
- ❌ 腳本失敗就改用別的方法自己算
