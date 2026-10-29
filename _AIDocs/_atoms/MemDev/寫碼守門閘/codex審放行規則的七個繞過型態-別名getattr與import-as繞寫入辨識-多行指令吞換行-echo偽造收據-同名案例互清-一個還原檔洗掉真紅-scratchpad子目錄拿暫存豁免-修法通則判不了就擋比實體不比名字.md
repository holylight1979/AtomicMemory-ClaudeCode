# codex審放行規則的七個繞過型態-別名getattr與import-as繞寫入辨識-多行指令吞換行-echo偽造收據-同名案例互清-一個還原檔洗掉真紅-scratchpad子目錄拿暫存豁免-修法通則判不了就擋比實體不比名字

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/from-track-gate-rules/001-codex-review.md
- Confidence: [臨]
- Trigger: codex 繞過, 放行規則繞過, INLINE_PY_READONLY, GIT_READONLY_SUBCMD, CASE_GREEN_AFTER_EDIT, RED_WHILE_REVERTED, 判不了就擋, 比實體不比名字, 對抗審, shlex 吞換行, echo 偽造 PASS
- Created-at: 2026-10-13

## 知識

- [臨] codex 對 045 放行規則模組一輪審出 7 個 BLOCK，全部親自重現成立，型態與修法：①python -c 唯讀判定被別名／getattr／import as／lambda 繞（`f=open; f('x','w')`）→ 判不了就擋：寫入名字只准當被呼叫的函式名出現、import 不准取別名或 *、getattr／globals／vars／lambda／def 一律擋；②多行 git 指令 shlex 吞換行，`status\ngit reset --hard` 被當一段放行；`diff --output` 寫檔 → 先按換行再按運算子切段、唯讀子命令配寫檔選項表、含 $( 或反引號就擋；③`echo test_x.py && echo X_CHECK PASS` 能清補案例欠帳 → 收據採認與 (a) 同一套（指令必須真的執行程式、點名只看跑程式那幾段的參數）；④不同目錄同名案例互相清紅 → 比絕對正規化路徑＋cwd，不比 basename；⑤一個無關的還原檔讓真紅不入帳 → 刻意紅＝有退回且同根沒有任何自己的現行改碼，拿不到事實的檔算現行；⑥正式 repo 的 scratchpad 子目錄拿到暫存 commit 豁免 → 判 repo 根不判執行目錄；⑦一般交付通知提到派工單路徑就開回合、清掉口令 → 只看正文首行的派工標記。
- [臨] 通則：放行規則的對抗審兩向（繞得過＋誠實流程過得了），同一面退第二次就定死規則；判定一律比實體身分（路徑、repo 根、blob、執行段）不比名字（basename、字串出現），能解析不了的寫法一律擋並在訊息指路。


## 行動

- 寫或審任何放行判定：逐一對這七型自問繞不繞得過，寫成紅案例再改
- 對帳閘的收據採認只認真的執行程式的指令段，echo／註解／重導向出去的不算
