# 同一回合先寫文字再呼叫工具時那段文字可能不進transcript-要讓hook或下一session看到的話必須以純文字回合結尾

- Scope: global
- Author: holylight
- Source: session ac67589e 2026-10-07（tri-link root/064 診斷 + 自查 jsonl）
- Confidence: [臨]
- Trigger: transcript 沒有我寫的字, 定位三行沒被認到, located=false, hook 讀不到回覆, 文字沒被持久化, text 與 tool_use 同回合, 回覆文字消失, 先說再做, 動手前預告沒留下, jsonl 找不到文字
- Created-at: 2026-10-07
- Quote: 「/continue <專案路徑>\.claude\memory\_staging\next-phase-tri-link-某專案.md 記得掛 monitor」

## 知識

- [臨]（實查 2026-10-07，CC 2.1.292 VSCode，session jsonl 逐筆數）同一回合「先輸出一段文字、接著呼叫工具」時，那段文字有時不會進 transcript：全場 169 筆 assistant 紀錄是 tool-only、13 筆 text-only、0 筆 text＋tool_use 同筆；兩段實際有輸出的文字（定位三行、回讀段）jsonl 裡完全找不到，只有第一回合的「執行目標」段留下來。後果：靠讀 transcript 的 hook（R5 定位三行檢查、紀律稽核）與下一 session 回看都會認定「沒說」，而模型自己相信說了。機制未定（可能與 thinking 區塊或串流切分有關），但後果已實證。
- [臨] 根層複驗（自己的 session jsonl）：文字＋工具呼叫同一筆 0、文字單獨筆 22、工具單獨筆 237；抽 5 句「先文字再工具」的開場句掉 1 句。第二台機器上的專案也重現（text 19 筆全是純文字回合）。不是單一 session 的偶發。OverviewHub 因此改成定位三行三個管道都認（回覆文字、工具參數、thinking）並記 located_via；要讓 hook 看到的宣告，最保險是同時放進下一個工具呼叫的參數（Bash 開頭註解），不必為了留紀錄結束回合。
- [臨]（實跑 2026-10-07）替代做法已驗：把要被 hook 讀到的宣告（如定位三行）放在**下一個 Bash 指令開頭的 `#` 註解**，工具參數一定進 transcript；R5 注入閘改成三管道（回覆文字→工具參數→thinking）後，同一 session 同一人：三行只在回覆文字 → `located=False`；放 Bash 註解 → 5 筆 edit 全 `located=True via=tool_input`。比「純文字回合結尾」省一個回合。
- [臨] 第二台機器、第二條管線（VSCode 擴充＋bypass，2026-10-07）重現：解析自己的 jsonl，assistant 區塊 text 19／tool_use 138／thinking 75，確定寫過的三段「定位三行」全不在 text，19 筆 text 全是純文字回合。對照實驗：同一檔同一人，「先文字再 Edit」那筆 located=false；「純文字回合寫三行、下一回合再 Edit」那筆 located=true via=text。根層已把判法改成三管道（回覆文字→工具呼叫參數→thinking）；最穩的做法是 Edit 前那一個 Bash 指令開頭放 `# 定位｜…` 三行（另一專案 5 筆全 via=tool_input）。

## 行動

- 要被 hook／下個 session 看到的宣告（定位三行、關鍵決策）：單獨一個純文字回合結束，下一回合再呼叫工具
- 被質疑「沒寫」時先 grep jsonl 確認，別和自己的記憶争
