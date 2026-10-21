# 無頭驗收實跑期間同一台機器不跑重測試與判分-並行負載讓受測session的hook逾時被砍-凍結合併不夠還要凍結重負載

- Scope: global
- Author: holylight
- Source: v6.0 第二波第三跑裁決（results/2026-10-21-C3/裁決-C3.md）
- Confidence: [臨]
- Trigger: 無頭驗收, 實跑期間, hook 逾時, 並行負載, 同機跑測試, 凍結合併, hook_cancelled, 總控台實跑規矩
- Created-at: 2026-10-21
- Quote: 「我今天要下班離開電腦前了、明早才會進公司。 我有另外開一個空Fable Session，title 我也改了名字叫 `(備)v6總控台-人+調`，如果此session的context又快用完(超過85%)了，你再自己去貼session prompt來繼承你； Codex的檢核意見，你要提醒工作session審過 (別呆呆的就又掉進飄移坑)； **用經驗、朝目標、避免飄、不空等、不浪費**。」

## 知識

- [臨] 無頭驗收實跑時受測 session 的 hook 是 live 程式、跟總控台同一台機；總控台同時跑判分子代理、codex、合併後的幾百案 verify，受測 session 的 PreToolUse（上限 5 秒）跟 SessionStart（20 秒）就被擠到逾時被 Claude Code 取消，閘整條靜默失效，判分時「閘正確放行」跟「閘沒跑」分不出來。
- [臨] 規矩：實跑期間不只凍結合進 live，也不在同機跑重負載（幾百案以上的 verify、判分子代理、codex、模型量測）；判分等兩題都跑完再起，或題與題之間串行。
- [臨] 判準：判分時看到 hook_cancelled，先查同時段機器上有沒有別的重負載，再歸因給 hook 本身慢。
- [臨] 工作軌也算同機重負載：接到要重建資料根、跑 selfcheck、整合測的派工，動手前先查有沒有實跑在進行（results/ 底下最新 run-*.log 的時間、受測專案目錄的修改時間），有就先問總控台或等它跑完。實例：A′ 07:15 開跑，總控台只通知了別的軌，本軌 07:20～07:28 照派工跑了三次重建自檢，事後才看到新的 run-A2.log。

## 行動

- 起實跑前列出同機正在跑的重負載，跑完或停掉再起
- 實跑中收到交付只對帳不跑 verify
