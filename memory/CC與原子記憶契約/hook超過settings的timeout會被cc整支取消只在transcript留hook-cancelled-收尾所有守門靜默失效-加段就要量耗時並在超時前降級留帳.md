# hook超過settings的timeout會被CC整支取消只在transcript留hook_cancelled-收尾所有守門靜默失效-加段就要量耗時並在超時前降級留帳

- Scope: global
- Author: holylight
- Source: 第二波 B′ 第二跑（results/2026-10-21-B2，transcript:284）；原設計者 10-21 已把 Stop／SubagentStop timeout 調 20
- Confidence: [臨]
- Trigger: hook_cancelled, hook timeout, Stop hook 逾時, 收尾沒反應, 最該修沒問, settings timeout 10, hook 變慢
- Created-at: 2026-10-21
- Quote: 「收割此session的知識與經驗」

## 知識

- [臨] settings.json 每個 hook 有 timeout（Stop 原設 10 秒），超過就被 CC 整支取消：沒有 stderr、沒有 additionalContext、守門自己的帳也沒有，只在 transcript 多一筆 hook_cancelled。實例：收尾 Stop 跑 10.37 秒，最該修、拐彎判斷、知識收割全被吞，判分者跟總控台都以為機制沒動。同一天合進多條守門後 hook 變慢（一條正規式對長英數 10 秒）就踩到。
- [臨] 規矩：在 Stop／PostToolUse 加任何一段，dispatcher 要累計各段耗時，到上限 80% 就留帳「超時降級：跑到哪段、各段秒數」並 stderr 一行；驗收判分先 grep transcript 的 hook_cancelled，有就不能判「機制沒動」。

## 行動

- 改 hook 前後用真 state 重放一次量總耗時，靠近上限就先調 settings timeout 或拆段
- 判分／除錯「收尾沒反應」先 grep hook_cancelled
