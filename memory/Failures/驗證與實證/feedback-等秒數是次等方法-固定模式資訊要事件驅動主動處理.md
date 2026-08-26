# feedback-等秒數是次等方法-固定模式資訊要事件驅動主動處理

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 等秒數, sleep, 超時處理, 等待時間, 輪詢, debounce, 固定模式, 事件驅動, timeout 當主要手段, 等一下再送
- Created-at: 2026-08-25
- Related: feedback-workflow-discipline, goal-driven-verify-loopkarpathy-吸收

## 知識

- [臨] 使用者定調（MudClient 登入探針案 2026-08-25）：對「經分析可知有固定模式資訊、可主動處理」的狀況，用「等秒數」（sleep/超時/閒置重試）永遠是次等方法，逼不得已才用。正解是辨認模式、事件驅動回應（例：登入後有「請輸入ENTER繼續」/「Huh?」兩種已知模式→直接補一發 ENTER 再送指令，而不是靠 60s 閒置重試自癒）。
- [臨] **Why**：時間等待把「可確定的因果」降級成「碰運氣的競態」——慢時白等、快時漏接，且遮蓋真正的機制理解。**How to apply**：設計等待邏輯前先問「這個状態變化有沒有可辨認的訊號/模式？」有→事件驅動；時間窗只當最後一層 backstop（且要出聲），不當主要手段。驗收標準寫「收到訊號 X 後發生 Y」，不寫「N 秒內發生 Y」。

## 行動

- 審查/設計任何 sleep、timeout、閒置重試前：先找可辨認訊號改事件驅動；留下的時間窗只能是 backstop 並註明理由
