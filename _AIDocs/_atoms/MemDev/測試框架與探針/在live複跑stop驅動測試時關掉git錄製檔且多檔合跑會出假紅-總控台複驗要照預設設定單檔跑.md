# 在live複跑Stop驅動測試時關掉git錄製檔且多檔合跑會出假紅-總控台複驗要照預設設定單檔跑

- Scope: global
- Author: holylight
- Source: session 2026-10-20 v6 第一波總控台 claude-12，G6 軌驗收
- Confidence: [臨]
- Trigger: WG_GIT_CASSETTE, 假紅, 總控台複驗, verify_stop_reconcile, 收件驗收, live 跑測試, 15 failed, 錄製檔關掉, 多檔合跑
- Created-at: 2026-10-20
- Quote: 「你說的是 "G2需要判斷的條件可能不夠用" 這樣的意思嗎?? 是的話，請該session開agent上網蒐、提給你做核可呀。」

## 知識

- [臨] 始末：驗收 G6 軌時，工作軌提醒「在 live 跑會自動重錄的測試會弄髒錄製檔，建議設 WG_GIT_CASSETTE=off」，我照做並把四支 Stop 驅動測試檔（stop_reconcile、deferral_gate、evasion_guard、release_rules）一次合跑 → 15 failed／913 passed，紅集中在 stop_reconcile 的 test_046 系列。改回預設設定單跑 stop_reconcile：494 passed；其餘三支合跑：432 passed。工作軌在工作樹跑同一批是全綠，紅的是我的跑法。
- [臨] 判讀：WG_GIT_CASSETTE=off 讓那些靠錄製重播的 git 情境改打真 git，fixture 目錄的 git 狀態跟錄製時不同就紅；這種紅不代表產品碼有問題。預設設定下只重播、不重錄，live 的錄製檔也不會被弄髒（跑完 git status 乾淨），所以「關錄製檔以免弄髒 live」的前提在預設設定下不成立。
- [臨] 總控台收件驗收的複跑規矩：照工作軌交付信寫的指令與設定原樣跑、一次一檔、不另加環境變數；跑出紅先用預設設定單檔重跑一次再判，紅只在自己改過設定時出現就是跑法問題，不退件。

## 行動

- 總控台複驗工作軌的測試：不加 WG_GIT_CASSETTE=off、不把多支 Stop 驅動測試檔合跑；先照交付信原樣單檔跑
- 複跑出紅：先用預設設定單檔重跑，再決定是退件還是跑法問題
