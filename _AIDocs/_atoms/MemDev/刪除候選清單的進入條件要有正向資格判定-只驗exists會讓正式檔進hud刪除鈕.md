# 刪除候選清單的進入條件要有正向資格判定-只驗exists會讓正式檔進HUD刪除鈕

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 殘檔帳本, aec_ledger, protected_reason, (d) 衍生暫存, HUD 刪除鈕, 正式檔誤列, vcs_tracked, 受保護路徑, 刪除候選, 破壞性候選清單
- Status: 已落地 2026-08-28，帳本清 4 筆；mcp.js (d) 說明需重啟 MCP 生效
- Created-at: 2026-08-28
- Related: hud暫存清單靠prose猜路徑的失敗-改殘檔帳本以檔案系統為權威, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長

## 知識

- [臨] 始末：專案 session 的 HUD「本 session 尚存殘檔」面板把 `_AIDocs/_CHANGELOG.md`、`memory/_ATOM_INDEX.md`、一顆新 atom 配上「刪除」鈕。追帳本 jsonl：三筆 source=aec-d——模型把「已改但還沒 commit、等使用者說上 GIT」的正式檔當「衍生暫存」報進 anti_evasion_report (d)；`parse_d_paths` 只驗 `os.path.exists()` 就進帳。兩層都破：模型錯報 + 程式端沒資格判定。
- [臨] 根因：帳本的每一列在 UI 都配破壞動作，但進入條件只有「存在」（必要條件），沒有「是暫存」（正向資格）。tempdir 來源（record_temp_write）有限定 tempdir 之下，(d) 來源卻沒有任何限定——兩條進帳來源標準不對稱。exists() 解決的是「還在不在」（上一輪教訓），解決不了「該不該在清單裡」。
- [臨] 修法（`hooks/handlers/aec_ledger.py`）：`protected_reason(path)` 依序 tempdir 直接放行 → 路徑段含 `memory`/`_AIDocs` → 檔名 `_INDEX`/`_ATOM_INDEX`/`_CHANGELOG`/CLAUDE/MEMORY/IDENTITY/USER/TECH/README → `vcs_tracked()`（有 .git/.svn 祖先才起子行程：git ls-files --error-unmatch／svn info，3s timeout，例外偏向不保護但前兩條仍擋）。三個消費點：`parse_d_paths` 拒收回 `rejected` 供 PostToolUse 以 additionalContext 告知模型「改列 (a)(b) 未同步事項」；`ledger_append` 不論來源最後一道；UPS `_drain_aec_decisions` 對受保護路徑的刪除決策注入 ⛔ 拒絕並直接 verified 結案。未追蹤的專案內合法暫存（.bak、undo、一次性 log）仍照收。
- [臨] 通則：凡是「候選清單 → 使用者一鍵破壞動作」的管線，進入條件必須是正向資格（它是什麼），不能只是消極條件（它存在／模型說它是）；拒收要浮出訊號給錯報的那一方，靜默丟掉會讓錯報一直重複。

## 行動

- 殘檔帳本／任何刪除候選清單：進入條件用 protected_reason() 類正向判定，不只 exists()
- 拒收的項目回告模型（additionalContext），不靜默
- 已改未 commit 的正式檔列 (a)(b) 未同步事項，不進 (d)
