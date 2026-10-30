# 寫碼守門開關會改記憶系統的收尾閘-關時九道記憶收尾閘照擋-開時反而只提醒且只在寫碼回合-背景收割與hook計時降級只在開時有

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 守門開關, 兩層, 收尾擋, KnowledgeHarvest 擋, gate_mode, 背景收割, hook 計時, 跨層
- Created-at: 2026-10-30
- Source: session:bc7c5340#5efdb29c 2026-10-30

## 知識

- [臨] 寫碼守門開關不只管守門：知識收割、同步、收尾檢核、退縮等 9 道記憶系統收尾閘，守門關時照擋、開時由 gate_mode 改成只提醒且只在寫碼回合跑；背景收割（stop.py）、hook 計時與快逾時降級（dispatcher）、Depends 召回、開場追蹤項只在守門開時有。
- [臨] TECH.md 開頭「系統的兩層」表寫「關掉只少守門這一層」不準；判某個行為前先查它在關、開兩種模式各怎麼跑。

## 行動

- 說明或改記憶系統收尾行為前：同時查守門關與開兩種模式的走法
