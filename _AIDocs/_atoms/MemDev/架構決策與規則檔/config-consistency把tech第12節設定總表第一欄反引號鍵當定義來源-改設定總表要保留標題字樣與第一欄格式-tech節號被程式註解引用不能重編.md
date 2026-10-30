# config-consistency把TECH第12節設定總表第一欄反引號鍵當定義來源-改設定總表要保留標題字樣與第一欄格式-TECH節號被程式註解引用不能重編

- Scope: global
- Author: holylight
- Source: track-tech-refresh 001 代寫 2026-10-22
- Confidence: [臨]
- Trigger: config-consistency, TECH 設定總表, 節號, 重編節號, TECH §12, 改 TECH
- Created-at: 2026-10-22

## 知識

- [臨] tools/config-consistency.py 把 TECH.md「## 12. 設定總表」與 12.1 兩張表第一欄的反引號鍵當成定義來源；改 §12 要保留標題字樣與第一欄格式。
- [臨] 程式註解引用 TECH 節號的只剩 hooks/extract-worker.py（TECH §12.1）；重編 TECH 節號前先 grep hooks、tools、lib、.claude/overview-map.md 裡的「TECH §」引用，一起改。

## 行動

- （依知識內容判斷）
