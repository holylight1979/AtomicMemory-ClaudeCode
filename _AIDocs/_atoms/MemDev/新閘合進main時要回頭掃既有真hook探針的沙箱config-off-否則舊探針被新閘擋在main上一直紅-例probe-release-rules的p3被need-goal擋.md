# 新閘合進main時要回頭掃既有真hook探針的沙箱config-off-否則舊探針被新閘擋在main上一直紅-例probe-release-rules的p3被need-goal擋

- Scope: global
- Author: holylight
- Source: track-retry-cycles 004 交付（claude-c0）2026-10-14，調度總控台代寫
- Confidence: [臨]
- Trigger: 探針沙箱 CONFIG_OFF, probe_release_rules P3, 新閸合進 main, 探針在 main 一直紅, 探針要關的閸
- Created-at: 2026-10-14

## 知識

- [臨] 真 hook 入口探針的沙箱要關掉「不在受測範圍的閸」（CONFIG_OFF）；新閸合進 main 後，早於它寫的探針沙箱沒關它，探針的情境就被新閸擋、在 main 上一直紅、被當成「既有不符」帶著跑（實例：probe_release_rules 的 P3 checkout --theirs 被 need_goal「改程式前要目標樹」擋，跟放行規則無關）。修法是在探針 CONFIG_OFF 加那道閸的開關，不是改規則。
- [臨] 同族第二例（fix/verify-scope）：Stop 收尾閘前段插新閘時，所有驅動 handle_stop 的既有案例會先被新閘擋（本次 22 支先紅）。開閘前先列出 Stop 驅動案，用沙箱 config 把新閘關掉或替它們補宣告，不要等全量才發現。

## 行動

- 合併任何新閸時：掃 hooks/verify/probe_*.py 的 CONFIG_OFF，把新閸的開關加進不受測它的探針
- 探針在 main 上「既有不符」先查是不是別的閸擋的，再判歸屬
