# 守門改成提醒後只在Stop寫stderr的提醒AI看不到-提醒要掛PostToolUse或PostToolBatch才進AI眼前-提醒句給了放行出口就要同時寫什麼時候不能走

- Scope: global
- Author: holylight
- Source: 2026-10-29 跑 011：workflow/inbox/wave2-kit/results/2026-10-29-011/判分-claude-opus.md；_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/v6.0的代價-守門改提醒後.md
- Confidence: [臨]
- Trigger: 守門改提醒, 提醒沒送到, Stop stderr, PostToolBatch 提醒, 只留帳, 提醒重驗, AI 照做程式沒認帳, PickOne 沒送到, 放行出口
- Created-at: 2026-10-30
- Supersedes: 守門改成提醒後只在stop寫stderr的提醒ai看不到-提醒要掛posttooluse或posttoolbatch才進ai眼前-提醒句若自帶不需出口又沒附判準卡ai會直接走出口

## 知識

- [臨] 六項守門從「擋」改成「提醒一句」後的三題實跑判分：提醒真的進到 AI 眼前的（PostToolUse／PostToolBatch 送的 G3、G7、G11、G13、G14）AI 五項都照做；只在 Stop hook 寫進 stderr 的提醒（順手看到最該修、沒補測試 (d)、拐彎 (t)）從頭到尾沒進 transcript，AI 不可能照做——「收尾只留帳」等於沒提醒。
- [臨] 提醒句自己列了放行出口（例：「不需第二意見｜理由」）卻沒同時教「什麼時候不能走出口」，AI 改了 7～8 支程式仍兩次寫「改動小」走出口。給出口就要同送什麼時候不能走的判準，否則出口就是預設路。
- [臨] 同跑另抓到兩處「AI 照做了、守門沒認帳」的誤判形狀：補測試只認案例檔名／內容點到被改模組名，test_lines.py 對 lines.py 也判沒覆蓋；改資料檔先宣告在「本 session 還沒改過程式」時整個跳過、宣告沒留帳。判「提醒重驗沒過」前先分 AI 沒做還是程式沒認。

## 行動

- 把某道守門改成提醒時，先確認提醒走 PostToolUse／PostToolBatch 進 AI 眼前，不是只在 Stop 寫 stderr
- 提醒句有放行出口（不需／不適用）就要同時寫明什麼時候不能走，並留帳
- 判分提醒重驗時，每條沒過先查 transcript 裡 AI 有沒有做，再查守門帳有沒有認；分開寫
