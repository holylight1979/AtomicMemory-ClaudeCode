# Codex 歪樓三因與入場用法-只給diff沒綜觀-沒嚴重度門檻照單全收-叫它找洞沒停止條件-對策是同步包自讀repo加兩級嚴重度一輪封頂

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/工作紀錄.md、總控台裁定帳與誤判清冊.md；session 3f490ffe 2026-11-02
- Quote: 「Codex 要怎麼用才不會歪掉(包括讓他以agent的型態做事)，能先把prompt或者需收錄、注入的atoms寫好、或挖出來嗎?」
- Confidence: [臨]
- Trigger: 加派 codex, codex 入場, codex 審查, codex 施工, codex agent, codex 歪樓, 帶歪, 第二意見, 同步包, codex-call
- Created-at: 2026-11-02
- Related: feedback-總控台要主動發掘矛盾與困擾並維持使用者立的工作要求-不被codex或自檢工具牽著走, 第二意見分歧裁決-codex的block要親自重現成立才採-重現不了才不採-我方測試全綠不是駁回理由

## 知識

- [臨] 開發期 Codex 第二意見歪樓的紀錄全是用法問題，不是 Codex 判斷力差，分三因：①材料只給 diff、讀不到 repo，有紀錄的誤判全是「沒看到 diff 以外」（commit 後送審 diff 為空、未追蹤新檔不在 diff、路徑遮罩）；②沒有嚴重度門檻、主 session 照單全收，邊角建議一條條變成工作；③叫它找洞卻沒停止條件，舊 Companion 審查 991 次 86% 回「要跟進」、g12 對抗審十二輪每輪都有新邊角。同一個 Codex 拿到全套材料（往返信、原話）時抓到的硬傷都成立。
- [臨] 對策（使用者原話：Codex 的綜觀認知要與當下 session 的 CC 幾乎完全同步、不是針對性亂驗、動態判斷是否入場）：入場由 CC 判、不看檔數行數；送同步包＝使用者原話逐字（不夾自己的限制）、設計尺原文、CC 的事實/推論/未知、已定案、相關卡知識段原文、repo 路徑與基準 commit 讓它自己讀；只收兩級：重大（一般寫法就踩到、漏記或誤認、誠實流程過不了）與快且有效，其餘只報條數；結論要改目標須附「做不到」的證據；一輪封頂，第二輪只驗採納項。
- [臨] Codex 自己的全域 AGENTS.md 沒有使用者的設計尺與衝突處置，還把最小 diff 排很前（推論：判設計題易偏向維持現況），所以設計尺要隨同步包貼原文；config.toml 預設 sandbox 是 danger-full-access，施工模式不帶 --sandbox workspace-write 就寫得到 live。用法正本是 skill `codex`（skills/codex/：SKILL.md、assets/sync-package.md、review-prompt.md、build-prompt.md、scripts/codex-run.py），叫 Codex 就用這個 skill。

## 行動

- 叫 Codex 前：先填同步包，原話逐字、設計尺貼原文、給 repo 路徑讓它自讀，不只給 diff
- 收 Codex 結果：只看重大與快且有效兩級，逐條對原話，重大的親自重現；不開第二輪找新洞
- 施工模式：專用工作樹＋--sandbox workspace-write，CC 自己重跑驗證再 commit
