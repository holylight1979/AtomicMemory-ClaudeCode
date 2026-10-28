# 紅測閘的紅帳以複合指令裡的pytest段為鍵-單獨重跑那支node案例綠了不清帳-要把當初整條指令原樣再跑一次

- Scope: global
- Author: holylight
- Source: session 3588eaca 2026-10-28，workflow/state 的 failing_tests 條目
- Confidence: [臨]
- Trigger: TestFailGate, 測試未綠, 紅帳不清, failing_tests, test_scope, 複合指令, for 迴圈跑 verify, node verify 紅, 重跑綠了還擋
- Created-at: 2026-10-28
- Quote: 「這速度 很可以呀 如果未來改碼速度都這麼快也太棒了! 我reload window完畢了。 008 要跑的內容含你調的，請條列白話，並且以一樣併行考量來估時間給我，不要直接開跑。」

## 知識

- [臨] 一條 Bash 同時跑幾支 node 案例再接一段 pytest，其中一支 node 紅：紅測閘記的 test_scope 只有 cd 與那段 pytest（它認得出 pytest，認不出 node 迴圈），之後單獨重跑那支 node 案例綠了，閘仍以同一鍵判「還沒綠」，Stop 連擋兩次。
- [臨] 解法：把當初那整條複合指令原樣再跑一次（含 pytest 段），帳才對得上清掉；或一開始就一支一條指令跑，不把 node 與 pytest 疊在同一條。

## 行動

- 跑驗證別把多支 node 案例與 pytest 疊成一條複合指令；紅了先看 state failing_tests 的 test_scope 是哪段
- 被擋「還有 N 支沒跑綠」而你確定已修：找 state 裡 cmd 原文、原樣重跑整條
