# 連鎖斷路器警報看same-count不看link-改什麼算修補要same-count與link兩處一起改-只改link不會少響

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 連鎖斷路器, wg_chain, same_count, link, CHAIN_ALARM_SAME_GATE, 什麼算修補, 警報沒少響
- Created-at: 2026-10-27
- Depends: path:C:/Users/holylight/.claude/hooks/wg_chain.py
- Related: 斷路器判原樣重試要比被擋呼叫的逐字指紋-跟同閘同對象上一次被擋比-不能只看中間有沒有ai動作或只比前一步
- Source: session:17c8cd5c 2026-10-27

## 知識

- [臨] hooks/wg_chain.py 的 judge 只拿 same_count（同閘同對象這一段第幾次）對 max_same_gate 判 CHAIN_ALARM_SAME_GATE；link（這一步接不接上前一步）只影響深度與帳上的說明，不決定同閘警報。
- [臨] 「什麼算修補」（看過擋訊息後改到檔、不同批、不是原樣重試）在 same_count 的計次條件與 link 各寫一份；改定義只改 link，警報次數照舊。

## 行動

- 改「什麼算修補」：same_count 與 link 一起改，各補一案
- 驗「少響」要斷言 same_count 的值，不只看 link.linked
