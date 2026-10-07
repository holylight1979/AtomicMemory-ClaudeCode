# 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾

- Scope: global
- Author: holylight
- Source: session ac67589e 2026-10-07（tri-link root/064 診斷 + 自查 jsonl）
- Confidence: [臨]
- Trigger: transcript 沒有我寫的字, 定位三行沒被認到, located=false, hook 讀不到回覆, 文字沒被持久化, text 與 tool_use 同回合, 回覆文字消失, 先說再做, 動手前預告沒留下, jsonl 找不到文字
- Created-at: 2026-10-07
- Quote: 「/continue C:\TSLG\.claude\memory\_staging\next-phase-tri-link-tslg.md 記得掛 monitor」

## 知識

- [臨]（實查 2026-10-07，CC 2.1.292 VSCode，session jsonl 逐筆數）同一回合「先輸出一段文字、接著呼叫工具」時，那段文字有時不會進 transcript：全場 169 筆 assistant 紀錄是 tool-only、13 筆 text-only、0 筆 text＋tool_use 同筆；兩段實際有輸出的文字（定位三行、回讀段）jsonl 裡完全找不到，只有第一回合的「執行目標」段留下來。後果：靠讀 transcript 的 hook（R5 定位三行檢查、紀律稽核）與下一 session 回看都會認定「沒說」，而模型自己相信說了。機制未定（可能與 thinking 區塊或串流切分有關），但後果已實證。

## 行動

- 要被 hook／下個 session 看到的宣告（定位三行、關鍵決策）：單獨一個純文字回合結束，下一回合再呼叫工具
- 被質疑「沒寫」時先 grep jsonl 確認，別和自己的記憶争
