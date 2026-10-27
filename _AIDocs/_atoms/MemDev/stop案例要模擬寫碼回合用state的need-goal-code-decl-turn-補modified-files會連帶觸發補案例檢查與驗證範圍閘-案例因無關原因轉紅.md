# Stop案例要模擬寫碼回合用state的need_goal_code_decl_turn-補modified_files會連帶觸發補案例檢查與驗證範圍閘-案例因無關原因轉紅

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: need_goal_code_decl_turn, modified_files, Stop 案例, 模擬寫碼回合, verify_need_goal, 案例轉紅
- Created-at: 2026-10-27
- Related: 守門只在寫碼回合啟動時-入口要認本回合的實質改碼或本回合宣告-不能認跨回合常駐的目標樹-也不能認關鍵字意圖
- Source: session:17c8cd5c#c404b251 2026-10-27

## 知識

- [臨] Stop hook 的測試案例要模擬「寫碼回合」，在造的 state 補 need_goal_code_decl_turn（本回合宣告寫碼的訊號）即可；不要補 modified_files。
- [臨] 補 modified_files 會連帶觸發補案例檢查與驗證範圍閘，案例會因跟受測邏輯無關的原因轉紅。實例：verify_need_goal.py 兩支案例舊造法沒有任何寫碼回合訊號，補了 need_goal_code_decl_turn、斷言不動。

## 行動

- 造 Stop 案例的寫碼回合訊號用 need_goal_code_decl_turn，不用 modified_files
- 案例轉紅先看是不是 state 欄位帶起了別道閘
