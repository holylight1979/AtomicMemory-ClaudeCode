# _AIDocs/_atoms/MemDev/測試框架與探針 — 範疇索引

> 階層範疇索引（自動生成，`_` 前綴非 atom）。機制見 [[realm-範疇分區機制-v5]]。

## 本層 atom

| Atom | 說明 |
|------|------|
| conftest隔離資料根要先放本樹受版控資料否則默默讀live設定與真實atom的既有案整批紅-放pytest-configure不放模組層-同行程多次pytest-main才都隔離 | conftest隔離資料根要先放本樹受版控資料否則默默讀live設定與真實atom的既有案整批紅-放pytest-configure不放模組層-同行程多次pytest-main才都隔離 |
| git-cassette錄製檔-測試裡git參數或呼叫次序一改就要用-git-record重錄並進版控-框架判過期會自動重錄-紅著的檔別把錄製進版控 | git-cassette錄製檔-測試裡git參數或呼叫次序一改就要用--git-record重錄並進版控-框架判過期會自動重錄-紅著的檔別把錄製進版控 |
| git測試慢用錄製重播git-cassette-受測程式的隨機暫存名與uuid要序號化-路徑寫法逐種還原-子程序裡的git與模組共用目錄不適用 | git測試慢用錄製重播git_cassette-受測程式的隨機暫存名與uuid要序號化-路徑寫法逐種還原-子程序裡的git與模組共用目錄不適用 |
| v6守門出廠預設關-直接跑的js與lib-verify驗證要自己帶wg-v6等於1 | v6守門出廠預設關-直接跑的js與lib-verify驗證要自己帶WG_V6等於1 |
| verify案例的連鎖帳預設按案例名放且跨次執行不清-第二次跑必紅-案例要把ledger-dir與snap-root指到tmp-path | verify案例的連鎖帳預設按案例名放且跨次執行不清-第二次跑必紅-案例要把ledger-dir與snap-root指到tmp-path |
| verify用importlib載入tools腳本-dataclass配future-annotations會炸-先註冊sys-modules或改namedtuple | verify用importlib載入tools腳本-dataclass配future-annotations會炸-先註冊sys-modules或改NamedTuple |
| 在live複跑stop驅動測試時關掉git錄製檔且多檔合跑會出假紅-總控台複驗要照預設設定單檔跑 | 在live複跑Stop驅動測試時關掉git錄製檔且多檔合跑會出假紅-總控台複驗要照預設設定單檔跑 |
| 多軌並行共用規則表時-規則名須出現在共用測試檔的守門案會逼每軌改共用測試檔-解法是各軌在檔尾加自己的小案段落-完整案例放各軌新檔 | 多軌並行共用規則表時-規則名須出現在共用測試檔的守門案會逼每軌改共用測試檔-解法是各軌在檔尾加自己的小案段落-完整案例放各軌新檔 |
| 改wg-release-rules後verify-release-rules要整支跑-有模組級檢查每條規則名要有案例與禁連續破折號-k篩選會漏 | 改wg_release_rules後verify_release_rules要整支跑-有模組級檢查每條規則名要有案例與禁連續破折號-k篩選會漏 |
| 新閘合進main時要回頭掃既有真hook探針的沙箱config-off-否則舊探針被新閘擋在main上一直紅-例probe-release-rules的p3被need-goal擋 | 新閘合進main時要回頭掃既有真hook探針的沙箱config-off-否則舊探針被新閘擋在main上一直紅-例probe-release-rules的p3被need-goal擋 |
| 案例造的state要帶真實形狀的鍵-缺鍵時程式setdefault自建成另一種形狀會假綠-實跑三次都炸而案例全綠 | 案例造的state要帶真實形狀的鍵-缺鍵時程式setdefault自建成另一種形狀會假綠-實跑三次都炸而案例全綠 |
| 真hook子行程探針只設wg-claude-dir隔離不了守門紀錄-guard-log-dir固定家目錄-要再帶wg-test-logs-dir與home-userprofile | 真hook子行程探針只設WG_CLAUDE_DIR隔離不了守門紀錄-GUARD_LOG_DIR固定家目錄-要再帶WG_TEST_LOGS_DIR與HOME-USERPROFILE |
| 範圍漏判歸因測試換真git後-前一session改檔與head相同被判原樣還原-範圍不結案-期望不記的案空轉綠 | 範圍漏判歸因測試換真git後-前一session改檔與HEAD相同被判原樣還原-範圍不結案-期望不記的案空轉綠 |
| 錄製重播的兩個假象-核對失敗被fail-open吞掉測試照綠-跨案共用的session帳本讓錄製檔依執行順序 | 錄製重播的兩個假象-核對失敗被fail-open吞掉測試照綠-跨案共用的session帳本讓錄製檔依執行順序 |
| 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源 | 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源 |
