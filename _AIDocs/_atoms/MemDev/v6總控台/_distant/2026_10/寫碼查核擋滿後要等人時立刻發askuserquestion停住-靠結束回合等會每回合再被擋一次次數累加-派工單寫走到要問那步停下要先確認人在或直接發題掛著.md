# 寫碼查核擋滿後要等人時立刻發AskUserQuestion停住-靠結束回合等會每回合再被擋一次次數累加-派工單寫走到要問那步停下要先確認人在或直接發題掛著

- Scope: global
- Author: holylight
- Source: track-data-root-2 A8 實走 006（session 616e4407）2026-10-14，調度總控台代寫；對人裁定「設計如此不修」
- Confidence: [臨]
- Trigger: 擋滿等人, exhausted_block, 收尾放行確認 等人, 每回合再被擋, 子代理被擋 9 次, 走到要問那步停下, AskUserQuestion 停住
- Created-at: 2026-10-14

- Related: 子代理改碼時寫碼查核的三個實況-子代理共用主session讀檔帳寫檔前要交定位行-主session擋訊息不帶子代理歸屬只在state看得到-刪掉對照引用的案例檔會讓已交對照失效

## 知識

- [臨] 寫碼查核閘擋滿後（要求用 AskUserQuestion 問使用者放行），若只是結束回合等人，Stop 每次都會再擋一次（exhausted_block 次數一路加），沒有不循環的停法；子代理同機制（實測被擋 9 次、花 7 萬多 token）。正解是馬上發 AskUserQuestion，題目會停在分頁等人點、不再被叫回來。設計如此（正確動作就是問人），不修閘。
- [臨] 總控台寫派工單「走到要問人那一步停下回報」時：要嘛先確認人已就位，要嘛改成「直接發題目讓它掛著、同時通知總控台」；跨 session 訊息只在收件端下一次呼叫工具時才進來，光結束回合等不到同伴回覆。
- [臨] 使用者在 AskUserQuestion 選「放行這一回合」後，放行要等 Stop 收尾時才記帳（guard-reconcile.jsonl event=user_release、state.user_released）。還要接著做事（查帳、還原、交付）時，先在背景跑一個短 sleep 當計時器再結束回合，計時器跑完的通知會把 session 叫回來；不要在同一回合先刪掉欠帳的檔，否則 Stop 沒有欠帳可放行、也就不會記 user_release。

## 行動

- 被擋滿要等人：立刻照閘格式發 AskUserQuestion，不靠結束回合等
- 派工單寫「停下等人」時改寫成「發題目掛著並通知總控台」
