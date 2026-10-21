# 先寫紅案例再分多次Edit改同一檔會被重試計數當成反覆修正-FixEscalation與DeepPostMortem誤觸

- Scope: global
- Author: holylight
- Source: session 68f0fc93 2026-10-14（track-fix-depends-recall 001）；hooks/wg_release_rules.py retry_bump、hooks/wisdom_engine.py
- Confidence: [臨]
- Trigger: FixEscalation, DeepPostMortem, RETRY_COUNTS_EDITS_SINCE_RED, retry=5, 重複修正, 紅案例先行, 改前紅改後綠, 同檔多次 Edit, 精確修正升級
- Created-at: 2026-10-14
- Related: need-goal-reconcile的case證據只認磁碟路徑-pytest節點id會被拒-寫檔加冒號行號

## 知識

- [臨] 始末：派工單要「新案例改前紅、改後綠」。先加兩個新案例跑紅，再用 5 次獨立 Edit 改 wg_need_goal.py（一個常數加四則訊息）、兩次改 points，一次跑綠。下一回合跳 FixEscalation retry=5，收尾又跳 DeepPostMortem。沒有任何修正失敗過，正確做法就是原本的紅先行。
- [臨] 運作邏輯（wisdom_engine 約 310 行、wg_release_rules.retry_bump）：紅測條目記 edits_after[path]，紅之後對同一檔的第 N 次編輯達門檻起每次 +1。它數的是 Edit 呼叫次數，分不出「一個計畫拆成幾個 Edit」與「改了跑、紅了再改」。刻意紅只認 RED_WHILE_REVERTED（退回舊碼反證），不認「新案例先紅」。
- [臨] 設計原理：觀察到的失敗模式是紅了就在同一檔反覆試，所以只數紅之後、同檔的編輯，不數整場累計。斷掉的環節是中間沒有「再跑一次測試」也照樣累計，紅先行就必然中。
- [臨] 根因：計數單位是編輯而不是「編輯→跑測試→仍紅」的循環。反覆重試的定義應該是紅之後改、跑了仍紅、再改，紅測之間沒有重跑的編輯不該算重試。
- [臨] 已由規則 RETRY_COUNTS_RERUN_CYCLES 修掉：重試只數「同一組測試上次跑之後碼有改過、再跑仍紅」的輪數，兩輪觸發，plan 與 direct 同門檻；篩選過的綠（單案、-k）只清它涵蓋的紅。已知限制（同時修多組時對沒改到的那組多報一次提醒）見 TECH §7.7。

## 行動

- 紅先行時同一檔的改動盡量併成一次 Edit，或用 Write 整檔，少累計
- 被 FixEscalation／DeepPostMortem 誤觸：用「紅之後有沒有跑過仍紅」判真假，在收割備註或交付信記誤判
- 根治候選（待總控台派工）：retry 只數「紅→改→再跑仍紅」的循環數，在 wg_release_rules 加規則與紅案例


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-10-21 | 退役移入 _distant/：重試計數已改成 RETRY_COUNTS_RERUN_CYCLES（只數「紅→改→再跑仍紅」），卡講的「數 Edit 次數」機制已不存在；行動「同檔改動盡量併成一次 Edit」與「根治候選（待總控台派工）」都過時，且 Trigger 正吃 FixEscalation 擋訊息字樣，會教 LLM 過時應對。判真假的有用部分由新卡「修不好兩輪先比兩輪紅案與錯誤原文-…」承接。出處：LLM切入點自評-2026-10-21.md 建議退役清單 #3（組C E18）。退役前已依閘提示移除 need-goal-reconcile的case證據只認磁碟路徑-… 對它的 Related 引用 | memory-audit --delete |
