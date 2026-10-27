# 閘擋訊息的guardian閘名標記要自成一行-parse-hits與hit-key只認行首的叉號-標記和叉號擠同一行行首解析器認不到那一條

- Scope: global
- Author: holylight
- Source: 2026-10-23 斷路器與紅測閘修補實測
- Confidence: [臨]
- Trigger: [Guardian:, 閘名標記, parse_hits, _hit_key, 行首 ✗, 擋訊息格式, 斷路器認閘名
- Created-at: 2026-10-22

## 知識

- [臨] 閘的擋訊息裡，`[Guardian:名稱]` 標記要自成一行：hooks/wg_release_rules.parse_hits 與 hooks/wg_release._hit_key 這類解析器只認行首的 ✗。
- [臨] 標記和 ✗ 擠在同一行時，斷路器認得到閘名，但行首解析器認不到那一條，兩邊算出來的命中就不一致。

## 行動

- 替閘的擋訊息加標記時，標記單獨一行，✗ 條目維持在行首
- 改完拿同一份擋訊息同時餵 parse_hits 與斷路器，確認條數一致
