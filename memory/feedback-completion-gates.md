# feedback-completion-gates

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 完成宣告, 收尾, pytest, smoke test, 研究先行, trial-and-error, 清理, 先清後建, 基線, 測試上傳, 上 SVN, known regression, xfail
- Created-at: 2026-05-26
- Related: feedback-workflow-discipline, feedback-tooling-reliability

## 知識

- [臨] 宣告完成前跑全 pytest；失敗逆向分流（相關→修 / 無關≤ 5 行→順手修 / 無關超門→known-regression）
- [臨] 測試 / 練習碼禁上 SVN/GIT，tests/__tests__/Test.* PreToolUse hook 擋
- [臨] 修復失敗 ≥ 2-3 次啟動網搜，不躺溝 trial-and-error
- [臨] 重構先清殘骩到 _archive/{date}/，跑乾淨 baseline 確認
- [臨] 整合 / 上線手動 E2E smoke + 肉眼確認 output
- [臨] xfail / known-regression 必附：原因 / 何時修 / 收尾清單

## 行動

- 完成前全 pytest
- 測試碼不上版控
- 修復失 ≥ 2 走搜尋
- 重構先清 _archive
- 上線 smoke + 肉眼
