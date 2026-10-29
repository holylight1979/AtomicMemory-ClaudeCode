# DevHistory — 開發紀錄索引

> 從 atom／Architecture.md／memory/_staging 移出的版本演進、遷移紀錄、實測數據、計畫與審查紀錄。按需閱讀、不自動注入 session context。
> 每個資料夾自己有 `_INDEX.md`（或 `README.md`），一檔一行白話說明；這一層只列資料夾。

| 資料夾 | 是什麼 | 檔數 |
|---|---|---|
| [向量與模型評測/](向量與模型評測/_INDEX.md) | Ollama 模型 A/B 實測、向量門檻校準、cross-encoder rerank 評估 | 5 |
| [記憶管線演進/](記憶管線演進/_INDEX.md) | atom 寫入／分類／注入／預算機制每次改版的為什麼與數字（含 2026-08 分類階層化、注入變弱調查） | 9 |
| [檢視與審查/](檢視與審查/_INDEX.md) | 三方比對評估（2026-08）、同伴 MR 審查（2026-10） | 2 |
| [工作流與協調/](工作流與協調/_INDEX.md) | 多 agent 協作協議、跨 session 衝突預警、session 管理、PAN 預告閘門終局判讀 | 4 |
| [設定與遷移/](設定與遷移/_INDEX.md) | settings.json 權限總覽（2026-04）、版本遷移表 | 2 |
| [v4-archive/](v4-archive/README.md) | V4 設計文件（三層 scope、衝突偵測、V4.1 開發歷程）＋ V4.1 hook 模組退役前最後一版 19 檔證物 | 3 md + 19 py |
| [v5-overhaul-2026-05/](v5-overhaul-2026-05/README.md) | V5 升版完整紀錄（起因、4-Wave、全面汰舊、GA 驗收）＋ 封存的 tests／tools／scripts | 2 md + 封存程式 |
| [全面檢視-2026-09-21/](全面檢視-2026-09-21/plan-and-decisions.md) | 2026-09-21 對照 CC 生態的全面檢視：共同簡報、Claude／Codex 審查摘要與全文、遙測統計、拍板 | 15 md + 腳本與輸出 |
| [v6.0-寫程式碼的進化-2026-10/](v6.0-寫程式碼的進化-2026-10/README.md) | v6.0（寫碼守門）開發期全紀錄：預計畫、三方討論、原話輯、工作紀錄、裁定帳、代價量測、checklist 與追蹤項封存、信箱全文；含 `staging封存-2026-10-27/`（開發期從 memory/_staging 清出的接續單與計畫） | 40+ md + 實測夾 |

> 2026-05-27 已移到 `memory/_distant/2026_05_v5_overhaul/`（git 不追蹤）的舊子夾：`session-logs/`、`memory-cleanup-2026-04/`、`atomic-memory-evolution/`、`ab-test-gemma4/`、`atom-v4/`、`atom-v4-phases/`、`changelog-roll/`、`v41-handoffs/`、`v41-p4-simulation/`、`wg-docdrift/`。文件裡指到 `memory-cleanup-2026-04/` 的連結在本機才解得開。
