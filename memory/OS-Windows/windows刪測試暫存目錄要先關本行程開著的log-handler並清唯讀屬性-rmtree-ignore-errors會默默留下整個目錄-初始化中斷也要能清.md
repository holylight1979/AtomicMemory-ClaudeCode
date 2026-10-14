# Windows刪測試暫存目錄要先關本行程開著的log-handler並清唯讀屬性-rmtree-ignore-errors會默默留下整個目錄-初始化中斷也要能清

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-data-root-2/001-data-root-2-done.md 第 15 條；003-002-done.md WARN 2
- Confidence: [臨]
- Trigger: rmtree ignore_errors, 暫存目錄刪不掉, log handler 佔用, 唯讀 git 物件, 測試殘留目錄, KeyboardInterrupt 清理, pytest_unconfigure, wg-iso 殘留
- Created-at: 2026-10-13
- Quote: 「你是 v6.0 的「調度」總控台（新任，接 claude-aa；對人總控台見接續單「現任」行）。職責：派工、對帳、快照複跑、合併、推送、刪樹刪分支、與各工作 session 通訊；不改碼、不開子代理、不回答原設計者。第一步 ToolSearch 載入 SendMessage 與 ListAgents，ListAgents 看自己的名字，SendMessage claude-aa 與對人總控台各一…」

## 知識

- [臨] 實踩（track-data-root-2）：測試收尾用 shutil.rmtree(ignore_errors=True) 刪暫存資料根，默默留下 19 個目錄。兩個原因：①本行程裡有 logging handler 整個行程開著暫存目錄內的檔（向量觀測紀錄），Windows 不讓刪；②測試建的 git 物件是唯讀檔。正解：刪前先找出指向該目錄的 handler 關掉並移除、對唯讀檔先清屬性（onerror 裡 chmod 再刪），仍刪不掉就在 stderr 列路徑，不静默。
- [臨] 初始化中斷也要能清：mkdtemp 後立刻登記清理資訊（不要等種子資料拷完才記）；收尾函式依狀態做（環境改過才還原、目錄建了才刪）、可重複呼叫；配置階段包 try/except BaseException 收尾後再拋，Ctrl+C 在拷檔中間也不留殘留。

## 行動

- 測試暫存目錄收尾：關 handler→清唯讀→刪→刪不掉列路徑；不用 ignore_errors 吞掉
- 建暫存目錄後立刻登記清理，初始化用 try/except BaseException 保護
