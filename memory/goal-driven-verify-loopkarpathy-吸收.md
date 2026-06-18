# goal-driven-verify-loop（karpathy 吸收）

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 寫程式, 寫扣, 實作, refactor, 重構, fix bug, 修 bug, add validation, 成功標準, verify, 驗收
- Created-at: 2026-06-12
- Related: feedback-workflow-discipline, workflow-icld, decisions, handoff-綜觀品質與抗失真寫法

## 知識

- [臨] 來源：karpathy-guidelines skill（已裝 ~/.claude/skills/）。四原則中前三條（Think Before/Simplicity/Surgical）你 IDENTITY+USER 已涵蓋，**唯一新增吸收的是這條**：把命令式任務轉成可驗證目標 + 逐步 verify，給成功標準讓自己 loop（強標準才能獨立 loop，弱標準『make it work』會反覆要澄清）。
- [臨] 套路：imperative→declarative。例：『Add validation』→『為非法輸入寫測試，再讓它過』；『Fix the bug』→『先寫重現測試，再讓它過』；『Refactor X』→『改動前後測試都綠』。多步任務先列 brief plan，每步附 `→ verify: <check>`。
- [臨] **衝突調和（重要）**：karpathy 的 Surgical Changes『別動相鄰碼/別刪既有 dead code/每行追溯到 request』與本系統 [[feedback-workflow-discipline]] 的『順手修補/drift 修補』方向相反。**裁決：以 feedback-workflow-discipline 的門檻判定為準**——Surgical 只取『不擅自擴張 scope』之意，不否決有門檻的順手修補。故 karpathy 全文僅以 skill (on-demand) 存在，不全域 always-on，避免覆蓋既有契約。

## 行動

- （依知識內容判斷）
