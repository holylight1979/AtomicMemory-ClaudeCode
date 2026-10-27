# 送得到ai眼前的擋訊息與提示從源頭避開退避詞-ai會原樣貼回-用守門案例逐則跑detect-evasion

- Scope: global
- Author: holylight
- Source: commit:70a666c7、d873acaa、15d94495
- Confidence: [臨]
- Trigger: 擋訊息退避詞, 提示被判退避, 原樣貼回擋訊息, 轉述被擋那則, 字面值掃描, detect_evasion 守門, 源頭換說法, GATE_TEXT_AVOIDS_EVASION_WORDS
- Created-at: 2026-10-27
- Related: 禁語-hook-不開引用豁免誤報噪音-vs-契約破洞不對稱, 被宣稱或退避詞表命中先看主詞-轉述別人與更早回合已驗過的就回非本回合宣稱或不是退避-自己本回合的絕不套, 擋訊息教的替代管道會被當成替代做法-寫明註解只放在不寫檔的指令上-宣告完照常用edit-write-同類說法全面grep並用掃原始碼的案例守住

## 知識

- [臨] 閘的擋訊息與提示會被 AI 原樣貼回自己的回覆（轉述被擋的那則）→ 送得到 AI 眼前的字串從源頭就避開退避詞表，不在偵測端開引用豁免（豁免會讓真退避躲進引號，原設計者已否決）。實例：DataFileAsk 擋訊息寫「(c) 非本 session 建」，AI 照貼，兩次判分都記成退避。
- [臨] 守門：hooks/verify/verify_evasion_guard.py 把 hooks／lib 這類字面值逐則跑 detect_evasion，判得出退避就紅；`+` 串接先併成一條、只排除 `re.<函式>` 的第一個參數、只排除印到 sys.stderr 的。合進別支之後也要跑：合 main 時 main 帶進來的一句新擋訊息就是被它抓到的。

## 行動

- 新寫或改擋訊息、提示時避開退避詞表的說法（例：「下個 session」改「接手的 session」）
- 合進別的分支後跑一次擋訊息掃描守門案例
