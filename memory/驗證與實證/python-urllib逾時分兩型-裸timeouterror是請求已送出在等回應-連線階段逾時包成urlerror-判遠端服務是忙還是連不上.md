# Python-urllib逾時分兩型-裸TimeoutError是請求已送出在等回應-連線階段逾時包成URLError-判遠端服務是忙還是連不上

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: TimeoutError, URLError, urllib 逾時, timed out, 連不上, 遠端服務逾時, WinError 10053, 回報管理者
- Created-at: 2026-11-02
- Source: session:3f490ffe 2026-11-02

## 知識

- [臨]（讀 Python 3.14 urllib 原始碼）urllib.request.urlopen 在 TCP 連線階段逾時，會包成 `URLError(reason=timeout)`；只有連線成功、請求已送出、在等回應時逾時，才拋裸的 `TimeoutError: timed out`。所以 log 裡只有裸 TimeoutError、沒有 URLError／拒絕連線／HTTP 錯誤碼，代表網路與服務程序是通的，卡在對方處理請求（忙、載入模型、排隊），不是連不上。
- [臨] 實例：遠端 Ollama 一段時間只出 TimeoutError（等 120 秒沒回一個字），同時健康檢查 `/api/tags` 是通過的；回報管理者要寫「某時段某端點回應逾時」並附來源 IP、端點、模型、逾時秒數，不寫「一直連不上」。

## 行動

- 看到逾時先分型：URLError＝連不上；裸 TimeoutError＝連上了在等回應
- 轉給服務管理者的回報附來源 IP、端點、模型、逾時秒數與時段
