# guardian 警告訊息辨識度-emoji 前綴分流

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 警告辨識度, systemMessage, emoji 前綴, ⛔, ⚠️, Guardian 警告, CoordWarn, PreActionNotice, 警告樣式, 字體放大
- Status: 已上線（PAN ⛔ / CoordWarn ⚠️），verify 釘住
- Created-at: 2026-08-06
- Related: pan-hermes不移植部件與vscode-text-block不落盤實測, 跨session協調-衝突預警機制與cc原生現況

## 知識

- [臨] **hook 警告的字級／顏色無 API 可控**。警告走 hook 輸出的 `systemMessage` 欄位，harness 拿到後怎麼渲染（VSCode 擴充是固定淡色小字區）由它自己決定，hook 端只能給純文字。提高辨識度**只能從訊息內容下手**：emoji／框線／全形字等純 unicode 手段任何渲染器都吃；markdown 粗體不保證。
- [臨] **前綴分流（使用者 2026-08-06 裁決）**：不是「所有警告用同一個標記」，而是**依類型分流、一眼區分**：PAN 預告閘門（`config.deny_template` + `pre_tool_use._PAN_FALLBACK_DENY`，warn／deny 共用）用 **⛔**；跨 session 衝突預警（`wg_coordination.py` 三處：`format_conflict_warning`／`format_late_collision`／`check_bash_git_finalize`）用 **⚠️**。
- [臨] 實模板與 fallback 模板必須同步帶前綴（config 壞掉時走 fallback，漏加會退回無標記版）。兩套 verify 釘住：`verify_pre_action_notice.py::test_messages_carry_alert_emoji_prefix`（直讀真實 config.json）與 `verify_session_coordination.py::test_warning_texts_carry_alert_emoji_prefix`。

## 行動

- 新增任何 Guardian 警告管道 → 先定類型再選 emoji，勿沿用已有標記造成語意混淆；同時補 verify 釘前綴
- 改警告文案時，實模板與 fallback 模板兩邊都要改
- 有人提議「將警告字體放大／變色」→ 直接告知無 API；真要放大只能讓模型在可見回覆裡複述（正文才吃 markdown）
