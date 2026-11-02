# 量測前後要核受測模型與effort-settings的model與effortLevel會蓋過CLAUDE_EFFORT環境變數-同一跑殼隔幾小時可能換了模型

- Scope: global
- Author: holylight
- Source: 2026-11-02 拔留改上版量測，wave2-kit results 2026-11-02-020 對 031
- Confidence: [臨]
- Trigger: CLAUDE_EFFORT, effortLevel, settings.json model, 受測模型, 量測對照, modelUsage, 拔前拔後, xhigh, 同一跑殼, token 少一半
- Created-at: 2026-11-02

## 知識

- [臨] 實例：同一支量測跑殼（設 CLAUDE_EFFORT=xhigh）下午跑出 Opus 5.5 xhigh，晚上跑出 Fable 5.1 high；中間只差本機 settings.json 改了 model=fable 與該模型的 effortLevel=high。settings 的 model／effortLevel 蓋過環境變數，token 整體少一半以上是模型換了，不是改動的功勞。
- [臨] 判準：要拿兩批實跑比「改前改後」，先從每跑的 turns JSON 讀 modelUsage 的模型名與 effort 計數，兩批不同就只能各自比開關差、不能比絕對值；寫紀錄時把模型與 effort 寫在表格前一行。

## 行動

- 跑對照量測前先印一次模型名與 effort（turns JSON 的 modelUsage），兩批不同就在表前標明、不比絕對值
- 跑殼要鎖模型就寫進 claude 的 --model／settings 參數，別只靠 CLAUDE_EFFORT 環境變數
