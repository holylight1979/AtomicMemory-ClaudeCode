# atom-write-replace-對舊格式卡片會丟-confirmations-與-last-used

- Scope: global
- Author: holylight
- Source: 某專案的一張舊格式卡片（該專案 repo 留有改寫前版本）
- Confidence: [臨]
- Trigger: atom_write replace, Confirmations 歸零, 舊格式 atom, Last-used 丟失, preserved conf=0, 裁剪 atom, 超預算 append 被拒
- Created-at: 2026-10-07
- Quote: 「幫你登入了啊」

## 知識

- [臨] 實測：對舊格式專案 atom（標題行為中文、檔名為英文 slug、`- Scope: project`、有 `- Last-used: 2026-04-23` / `- Confirmations: 10`）做 `atom_write mode=replace`，回訊「preserved conf=0 rh=0」，結果標題被改成檔名、Confirmations 與 Last-used 行消失、Created-at 變成當天；歸因候選：replace 路徑的中繼資料讀取沒容忍舊格式（標題≠檔名或 Scope=project）。附帶：knowledge 區超 3072 bytes 的舊卡 append 必被預算擋，只能 replace，所以這個丟失會在「裁剪舊卡」時必然觸發。
- [臨]（再踩）對 `decisions` 與一張 local 卡做 `mode=replace`：沒帶 `related` → 整行 Related 被清掉；舊卡沒有 Created-at → 補成當天；舊卡沒有 Quote → PostToolUse 來源自動補填用「本回合使用者原話」補（工作 session 裡就是開工派工句，與卡片無關）；標題行換成 title 參數（用檔名 `decisions` 才找得到卡，標題「全域決策」就被覆蓋）。Related 可用 atom_edit_meta 補回；Quote、Created-at、標題字樣沒有工具能改（清空 Quote 會被自動補填再寫回）。
- [臨] 已修（v6/track-a6c 9eaa8bf）：根因是 replace 用參數整張重建檔頭，只有幾個欄位走「沿用舊值」，而且 py 與 MCP js 各寫一份。現在兩端共用 `lib/atom_io.carry_replace_header`：舊格式（標題 slug≠檔名）沿用舊標題、舊卡沒 Created-at 不補、沒給的檔頭鍵（Related、Status、Confirmations、Last-used、Type…）原行帶回；Quote 自動填遇開工句不填（`lib/harness_text.is_kickoff_prompt`）。
- [臨] post-mortem：用檔名當 title replace 舊卡，標題、Created-at、Related 被改，Quote 被填開工句，寫後沒讀卡核對。根因：replace 實作成「參數重建整張檔頭」，舊值保留是逐欄白名單且 py／js 各一份；Quote 來源只剝 harness 區塊，開工句樣板鎖在萃取器。設計原理：build 是 py↔js 逐 byte 單源，重用它求格式一致，代價是只輸出認得的鍵；同伴訊息回合沿用前回合原話是口令閘需求，連帶把開工句帶進後面的卡。防再犯：改寫類 API 定成「只換給的、其餘原樣」一支函式；改寫既有記憶前後各 Read 一次比對中繼資料；「使用者原話」判斷要排除開工句；修根因先跑受影響模組既有全組（這次靠它抓到自己把空 Depends 行帶回的回歸）。
- [臨] 補：自動填錯的 Quote 用 Python 呼叫 `lib.atom_io.edit_metadata(path, quote="", source="tool:memory-cleanup")` 清成空行，不會再被補填；replace 對整份知識重跑 realm 與敍事日期閘，舊行的專案名、日期要順手改寫。

## 行動

- 修：在 ~/.claude session 追 lib/atom_io 的 replace 中繼資料保留邏輯，對舊格式標題/Scope 也要讀到 Confirmations 與 Last-used
- 裁剪舊卡前先記下 Confirmations，replace 後核對回訊的 preserved conf
