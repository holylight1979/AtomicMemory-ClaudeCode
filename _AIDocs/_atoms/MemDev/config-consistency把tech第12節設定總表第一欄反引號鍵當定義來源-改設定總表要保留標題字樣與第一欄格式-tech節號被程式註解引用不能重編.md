# config-consistency把TECH第12節設定總表第一欄反引號鍵當定義來源-改設定總表要保留標題字樣與第一欄格式-TECH節號被程式註解引用不能重編

- Scope: global
- Author: holylight
- Source: track-tech-refresh 001 代寫 2026-10-22
- Confidence: [臨]
- Trigger: config-consistency, TECH 設定總表, 節號, 重編節號, TECH §12, 改 TECH
- Created-at: 2026-10-22

## 知識

- [臨] tools/config-consistency.py 把 TECH.md「## 12. 設定總表」與 12.1 兩張表第一欄的反引號鍵當成定義來源；改 §12 要保留標題字樣與第一欄格式。
- [臨] pre_tool_use.py、post_tool_use.py、_shared.py、overview-map.md 的註解引用 TECH §7.x 節號，TECH 不能重編節號；要刪的節改成原位改寫。

## 行動

- （依知識內容判斷）
