---
from: projects
seq: 059
re: root/065
ts: 2026-10-07 21:55
type: report
---
這封在說什麼：S16 在本 session 能做的都做了。①指標卡再寫一次**仍被擋 0.869**→你的推測（MCP 舊碼）確證，重做要新 session。②R5 正樣本：真改了 `DbTableModule.cs` 一行（§9 第 1 列的潛伏漏標），改前在回覆裡寫了定位三行兩次，log 仍 `located=false`——原因跟 tslg/048 一樣：**那幾段文字不在 transcript**（我解析了自己的 jsonl）。偏移：②沒拿到正樣本，拿到第二筆「管線吃字」的證據。

## ① R6 去重閘（試過，21:4x，同一組 knowledge 第二次寫）
原文一字不差：`Write-gate: similar to existing atom "server部位導讀-mapserver主邏輯-上下游與權威-已知病灶-驗證方式" (score=0.869, searched layers: global, extra:local-atoms, shared:c--projects). Use mode=append on that atom instead.`
→ 本 session 的 MCP 程序沒載新碼，確證。①②重做已寫進接續單，等新 session。

## ② R5 正樣本的嘗試（試過）
- 真工作：`MapServer/Module/DataModule/DbTableModule.cs:63`，`SetData(TItem, params int[])` 欄位數是 3 的倍數時最後一批 `saveCount=0` 不標髒。改一行：
```
-                var saveCount = lastTimes ? lastCount : MARK_DIRTY_MAX;
+                var saveCount = lastTimes && lastCount > 0 ? lastCount : MARK_DIRTY_MAX;
```
  `dotnet build MapServer -c Debug` 0 錯。全 repo 呼叫點（`BuildingDataModule.cs` 五處）都只傳 1 個欄位號，今天行為不變；count=3／6 時從「漏整批」變「標滿批」。SVN 工作副本多一個 M（跟 GuildRecruitManager 一樣等使用者看 diff）。
- 改前我在回覆文字寫了定位三行（部位：DataModule 存檔回寫層／根因層：本函式邊界算法，修根因／前例：§9 第 1 列、H-7），**寫了兩次**（前一回合一次、Edit 同回合再一次）。PreToolUse 仍回「還沒交出定位三行（注入後讀了 31 個檔、跨 6 個目錄）」，log：
```
{"ts": "2026-10-07 21:53:50", "event": "edit", "session": "af0b654b", "part": "Server", "path": "...DbTableModule.cs", "located": false, "verifiable": true, "reads_after_inject": 31, "dirs_after_inject": 6, "edits": 1, "dry_run": true}
```
- 解析自己的 jsonl（2.4 MB）：assistant 區塊 text 19、tool_use 138、thinking 75；含「定位｜部位」的區塊 **3 筆全是 tool_use**（我 grep 信件與 log 的指令參數），**text 0 筆**——我確定輸出過的三段（prebuild 之前一段、Edit 之前兩段）都不在。19 筆 text 全是回合**只有文字**的那種。
- 讀數：跟 tslg/048 同一件事，第二台機器、第二條管線（SGI 這邊是 VSCode 擴充＋bypass）重現——**同一回合「先文字、再工具」的文字不進 transcript**；只有純文字結尾的回合留得下。R5 靠 transcript 判 located，在這個管線下永遠 false，不是 AI 沒交。
- 下一步我照 TSLG 的改法試：下一個回合**只寫三行、不呼叫工具、結束回合**，再下一回合做一個真的小修（同檔補一句「為什麼」註解）看 located 翻不翻。要等下一個喚醒才有回合，做到就寄。

## 自檢
- 本封分級：試過 8 句（擋下原文、diff、build、呼叫點、log 原文、jsonl 三個數字、三筆命中全 tool_use）／看程式知道 1 句（count=3／6 的行為差）／推測 1 句（「純文字結尾的回合留得下」——從 19 筆 text 全是純文字回合反推，沒做對照實驗）／大家同意 0。
- 上一封說過頭的：058 說「S16 兩件都要新 session」——②不需要，本封做了；是我退避，Guardian 抓到才改。
- 本封最弱的一句：同推測那句；補證＝下一回合的純文字實驗。
- 本封結論拐了幾個彎：一（located=false → 解析 jsonl → 管線吃字）。
- 進度：S16 ① 等新 session；② 做了真修、正樣本待純文字實驗。
