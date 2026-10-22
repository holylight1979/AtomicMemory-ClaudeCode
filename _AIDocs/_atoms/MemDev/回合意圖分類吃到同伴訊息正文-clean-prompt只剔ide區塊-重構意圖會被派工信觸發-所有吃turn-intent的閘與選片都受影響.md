# 回合意圖分類吃到同伴訊息正文-clean_prompt只剔IDE區塊-重構意圖會被派工信觸發-所有吃turn_intent的閘與選片都受影響

- Scope: global
- Author: holylight
- Source: 2026-10-20 實測；實測位置 user_prompt_submit.py:107／:148
- Confidence: [臨]
- Trigger: turn_intent, classify_intent, clean_prompt, 意圖分類, 同伴訊息, 重構意圖, refactor 誤判, user_typed_text, goal_weights, 意圖來源
- Created-at: 2026-10-20

## 知識

- [臨] 實測：`hooks/handlers/user_prompt_submit.py` 的 `clean_prompt` 只用 `strip_harness_blocks(only=IDE_TAG_NAMES)` 剔 IDE 區塊，`classify_intent(clean_prompt)` 會吃到同伴 SendMessage 的正文：同伴信「把 wg_x 的分派重構成查表」會把回合意圖判成 refactor，同一則改取 `user_typed_text` 則是 general。寫 `state["turn_intent"]` 的只有這裡與 `wg_overview.on_prompt`，AI 自己回合中途說「重構」不會改意圖。
- [臨] 影響面：所有吃 turn_intent 的地方——OverviewHub 導讀卡選片、goal_weights 注入（含等值證法與熱路徑一問）、任何依意圖觸發的閘——都會被同伴訊息裡的字眼帶偏。所以依意圖擋的規則在意圖來源改成只認使用者原話之前只提醒不擋。通則同「使用者原話權威判斷只吃單一清理函式」：任何『使用者想做什麼』的判斷都要先過 user_typed_text。

## 行動

- 新增或審任何依意圖觸發的閘：先查意圖是不是從 user_typed_text 判；不是就只提醒不擋
- 修法：UPS 改 classify_intent(user_typed_text(prompt))，配一正一反案例（同伴信不觸發、使用者同句觸發）
