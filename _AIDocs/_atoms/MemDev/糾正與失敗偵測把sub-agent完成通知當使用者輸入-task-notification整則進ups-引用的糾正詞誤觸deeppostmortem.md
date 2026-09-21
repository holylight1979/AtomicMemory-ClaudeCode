# 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進UPS-引用的糾正詞誤觸DeepPostMortem

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: task-notification, DeepPostMortem 誤觸, 糾正訊號誤報, wg_friction, user_correction_count, FailureDetect 誤觸, sub-agent 回報, harness 生成 prompt, is_harness_generated_prompt, sanitize_harness_noise, 假糾正
- Created-at: 2026-09-21
- Related: codegraph與agent-retro評估結論-codegraph只當專案local-mcp不進記憶-agent-retro只拆量測, escalation-hook-在-edit-count-proxy-上-false-fire-的辨識無真實失敗迴圈時不盲從不編造, posttooluse的tool-response不等於模型看到的結果-edit帶整份originalfile-量context浪費要按工具取可見欄位, 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞

## 知識

- [臨] 始末：2026-09-21 全面檢視 session 派了 10 支 sub-agent，使用者全程零糾正；Stop 卻彈 [Guardian:DeepPostMortem]「使用者已糾正 2 次（不對、我說過、重來）」，同 session 稍早還出現 [Guardian:FailureDetect] 背景萃取。查 state.user_correction_hits：兩筆 excerpt 都是 `<task-notification>…`——sub-agent 完成通知整則走 UserPromptSubmit，內文（審查報告引用糾正關鍵字、失敗詞）被當成使用者打的字。
- [臨] 根因：UPS 的 clean_prompt 只剝 `<ide_*>` 標籤；`wg_core.sanitize_harness_noise` 雖列了 system-reminder 等 harness 標籤但沒列 task-notification，而且糾正偵測（wg_friction.detect_correction）與失敗萃取（wg_extraction._maybe_spawn_failure_extraction）根本沒經過它——直接吃原始 prompt。「進 UserPromptSubmit 的都是使用者訊息」這個前提在 background agent 通知出現後就不成立了。
- [臨] 設計原理：friction 糾正計數是 2026-09 從 agent-retro 拆來的量測，目的是「測試全綠但一路被糾正也算真失敗」，餵 Stop 的 Deep Post-Mortem；關鍵字比對走 CJK 子字串，本來就靠「來源一定是使用者」保精度。失敗萃取同理。sub-agent 回報恰好是最容易含這些詞的文本（審查報告會引用「不對／重來」、描述失敗）。
- [臨] 修法：wg_core 加 `task-notification` 進 _HARNESS_TAG_RE，並新增 `is_harness_generated_prompt()`（開頭 `<task-notification` / `[SYSTEM NOTIFICATION`，或 sanitize 後為空）；detect_correction 與 _maybe_spawn_failure_extraction 入口先過這道閘，糾正比對改吃 sanitize 後文字。實跑：通知不命中、真使用者糾正仍命中、「對不對？」仍排除。
- [臨] 防再犯：任何新的 UPS 側「使用者訊號」偵測（糾正、失敗、意圖、決策萃取 L0）都要先問「這則 prompt 是人打的嗎」——統一走 is_harness_generated_prompt + sanitize_harness_noise，不各自 regex。驗法：拿一則真實 task-notification 原文當負例放進 verify。

## 行動

- 新增 UPS 側使用者訊號偵測：入口先 is_harness_generated_prompt() 短路，再對 sanitize_harness_noise() 結果比對
- 看到 DeepPostMortem/FailureDetect 觸發但使用者沒糾正：先查 state.user_correction_hits 的 excerpt 是不是 <task-notification>
