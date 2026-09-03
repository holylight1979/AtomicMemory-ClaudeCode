# TestFailGate 非 pytest 失敗紀錄只靠同前綴 40 字的成功指令清除-重跑勿加 cd 前綴

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: TestFailGate, 測試未綠, failing_tests, 不得宣告完成, 重複觸發, Stop 閘, node --check, heredoc
- Created-at: 2026-09-01

## 知識

- [臨] `[Guardian:TestFailGate] 測試未綠` 對同一筆紀錄反覆觸發時，不是閘門壞，是清除條件沒對上：`post_tool_use` 只在「後續某個 test 指令成功、且其前 40 字與失敗紀錄的 cmd 前綴相同」或「pytest 成功且該紀錄有 pytest 標記」時移除條目。heredoc（`python - <<'PYEOF'…`）內夾 `node --check` 的失敗紀錄屬非 pytest，之後跑再多 pytest 綠燈也清不掉。
- [臨] 正確清法：用**逐字相同開頭**（含 heredoc 首兩行）重跑一次通過即清；前面多加 `cd …;` 前綴就對不上（實測踩過一次）。查當前紀錄：`workflow/state-<sid>.json` 的 `failing_tests[].cmd`。使用者放行關鍵字（ups_gates `is_dismiss_prompt`）是另一條清除路。

## 行動

- TestFailGate 第二次同紀錄觸發 → 先讀 state failing_tests[].cmd 前綴，再以相同開頭重跑成功指令
- 不要靠重述「已修好」文字過閘；不要在重跑指令前加 cd
