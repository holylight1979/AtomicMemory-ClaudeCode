# aspnetcore-關閉卡逾時-requestaborted不觸發-長連線handler內文也要吃linked-token

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: graceful shutdown, 關閉卡住, ShutdownTimeout, RequestAborted, ApplicationStopping, WebSocket, CloseAsync, Kestrel, StopAsync, IHostApplicationLifetime, 關閉逾時, in-flight request
- Created-at: 2026-08-11
- Related: feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, 歸因早停-找到合理嫌疑機制就停止驗證

## 知識

- [臨] `HttpContext.RequestAborted` **不會**在 graceful shutdown 觸發——它只代表對端主動斷線。要在 host 停止時取消，必須 `CancellationTokenSource.CreateLinkedTokenSource(context.RequestAborted, lifetime.ApplicationStopping)`。
- [臨] 只把 linked token 餵給「接收迴圈」不夠。**handler 內文的每一個 await 都要吃同一個 token**：迴圈停了但 handler 還在跑（例如一整輪 LLM 呼叫），Kestrel 仍在等該 request drain，關閉就會撐滿 `HostOptions.ShutdownTimeout`（預設 30s）。
- [臨] `WebSocket.CloseAsync` 會送 close frame **並等對端回一個 close frame**；對端若不再呼叫 ReceiveAsync 就永遠不回。收尾用 `CloseAsync(..., CancellationToken.None)` = 無界等待，必須給有界 token，逾時改 `socket.Abort()`。只送不等用 `CloseOutputAsync`。
- [臨] 分段定位法：在 `host.StopAsync` / `DisposeAsync` 前後打時間戳，並用 decorator 包住每個 `IHostedService` 量它的 `StopAsync`。若各 hosted service 都 0ms 而 `StopAsync` 總時間逼近逾時 → 是 Kestrel 等 in-flight request，不是背景服務。
- [臨] 量關閉秒數前必須先確認服務**真的就緒**（例如輪詢健康端點回 200）。啟動途中關閉時，控制器會（正確地）等啟動流程釋放操作閘門，量到的是啟動時間不是關閉時間——固定秒數暖機會產生 2～15s 的假離群值。
- [臨] `AddHostedService` 的服務在 `builder.Build()` 之前就可用 decorator 換掉；但 `GenericWebHostService`（Kestrel）不在該清單裡，量它要靠 host 層總時間扣除。

## 行動

- 長連線 endpoint（WebSocket/SSE/long-poll）一律建 linked token，並讓 handler 內文全部使用它，不要留 context.RequestAborted 在迴圈之外
- 任何 close 握手、對多連線的廣播、收尾 flush，都要有界 token，不要用 CancellationToken.None
- 關閉變慢先分段量測（host.StopAsync vs DisposeAsync vs 各 hosted service），不要憑相似 pattern 歸因外部元件
- 縮短 ShutdownTimeout 只是止血；它會把真因藏起來，根治後應放寬回保守值並註明它只是保險
