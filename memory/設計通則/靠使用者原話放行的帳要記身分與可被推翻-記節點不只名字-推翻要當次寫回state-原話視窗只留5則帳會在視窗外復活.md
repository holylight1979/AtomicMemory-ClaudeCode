# 靠使用者原話放行的帳要記身分與可被推翻-記節點不只名字-推翻要當次寫回state-原話視窗只留5則帳會在視窗外復活

- Scope: global
- Author: holylight
- Source: commit:cfda1231 2026-10-21（修補實證）
- Confidence: [臨]
- Trigger: 豁免帳, 放行帳, 使用者撤回, state 帳復活, 原話視窗, 口令失效, 使用者本人打的字
- Created-at: 2026-10-21

## 知識

- [臨] 靠使用者原話放行的帳要記身分：是哪一個對象的完整名字（例：測試節點記 a.py::test_total），不只是短名，否則 a.py::test_total 的帳會放過 b.py::test_total。
- [臨] 使用者後來的話要能推翻它，而且推翻要當次寫回 state：原話視窗只留 5 則（recent_user_prompts），若只在讀取時判「後來有沒有提到」，那則擠出視窗後帳會活回來。例：版控口令「上GIT」——push 完成就當次寫回 state 把口令用掉（order_push_seq），使用者新打的字開新回合、口令要重下（hooks/handlers/ups_gates.py）。
- [臨] 先認說話的人：只算使用者本人打的字（wg_core.user_typed_text 剔掉同伴訊息、背景通知、其他 session 的訊息）。例：「先這樣／跳過」清紅測清單、口令、否決記憶都只吃這份。
- [臨] 帳是逐件記的，就每件各自要有依據：只點名 A 不能連 B 一起放。目前紅測清單不是逐件帳：使用者本人打「先這樣／跳過」整份清掉，使用者放掉的是哪幾支要 AI 在收尾報告講清楚。

## 行動

- 寫靠原話放行的帳：鍵用對象完整名、推翻當次寫回 state、原話只取 user_typed_text
