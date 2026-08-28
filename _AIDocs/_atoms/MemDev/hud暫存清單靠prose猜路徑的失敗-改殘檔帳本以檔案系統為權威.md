# HUD暫存清單靠prose猜路徑的失敗-改殘檔帳本以檔案系統為權威

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 殘檔帳本, aec-tempfiles, aec_ledger, HUD 刪除鈕, isDeletable, 衍生暫存清單, scratchpad 清除, post-mortem, prose 猜路徑, exists() 權威
- Status: 帳本 + HUD 面板已落地 2026-08-25，待新 session 肉眼驗面板流程
- Created-at: 2026-08-25
- Related: feedback-completion-gates, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長, 歸因早停-找到合理嫌疑機制就停止驗證, 路徑解析函式的根層分支是遷移盲點-cwd在claude根時專案分支會長出舊址, 刪除候選清單的進入條件要有正向資格判定-只驗exists會讓正式檔進hud刪除鈕

## 知識

- [臨] 始末：使用者在 Anti-Evasion HUD (d) 衍生暫存清單想刪檔，刪除鈕卻被藏起→第一輪只修啟發式（拿掉「保留」字樣否決），並在報告裡寫「scratchpad 隨 session 結束清除」→使用者追問才實查：%TEMP%\claude 下 476 個 session 目錄從 3 月堆到現在，根本沒有自動清除→最終做法：per-session 殘檔帳本 workflow/aec-tempfiles/<sid>.jsonl（Python 唯一 writer，三來源：tempdir 寫入 / (d) 一行一路徑 / Stop 掃 scratchpad），HUD 面板讀帳本 + 當下 exists() 過濾，決策檔改路徑 hash 命名帶 path 供真後驗。
- [臨] 根因：不是啟發式寫得不好，是「讓 UI 從模型自報的 prose 猜檔案狀態」這個方向本身錯——模型同時是「會寫未驗證斷言的那個人」，它的字樣（保留/已刪/會自動清）不能當作檔案是否存在的依據；與之搭配的 Python 後驗把整行 prose 當路徑查 exists()，永遠解不出→靜默 verified:true，等於假驗。
- [臨] 設計原理：舊 (d) 是 freeform 文字欄（為了不增加模型 emit 成本），HUD 逐行拆 + 啟發式配鈕、決策鍵 (sid,turn,行序)；藏刪除鈕是因為使用者曾誤按引發一波改動，用「藏按鈕」代替「二次確認」——防誤按的正解是 confirm()，不是拿掉使用者的決定權。
- [臨] 運作邏輯與斷點：MCP tool 只回 chip → Python PostToolUse 落 aec-report → Node 讀報告供 HUD → HUD 按鈕寫 aec-decision → Python UPS drain 注入 + 後驗。斷在「報告裡只有 prose、沒有機器可讀路徑」：下游所有環節（配鈕、後驗、跨回合追蹤）都只能猜。新設計把「進過帳」（帳本）與「還在不在」（讀端 exists()）分開，後者永遠問檔案系統。附帶發現：UPS drain glob 只認 <sid>-t*.json，新命名沒改 glob 會靜默漏掉——新增檔名樣式必 grep 所有 glob 點。
- [臨] 防再犯：(1) 任何「會自動清/會消失」的斷言先 ls 實查再寫；(2) UI 要判檔案狀態一律 exists()，不讀模型文字；(3) 防誤按用 confirm() 不藏鈕；(4) 使用者拒絕「保留 N 天」型 TTL（雞肋、依賴下次開工、會變成默許不刪），殘檔正解是完工即刪 + 帳本讓沒刪的曝光。

## 行動

- 對檔案存在與否的判斷只信 exists()，不信模型字樣
- 斷言「會自動清除」前先 ls 實查
- 新增檔名樣式時 grep 全部 glob 消費點
- 防誤按用 confirm()，不藏按鈕
