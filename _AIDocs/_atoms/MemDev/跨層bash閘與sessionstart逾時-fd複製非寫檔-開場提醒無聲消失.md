# 跨層Bash閘與SessionStart逾時-fd複製非寫檔-開場提醒無聲消失

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CrossRealmBashBlock, 2>&1, fd 複製, hook_cancelled, SessionStart 逾時, timedOut, 開場提醒沒出, ScopeLayout 沒出, 一律被擋, 冷啟動
- Created-at: 2026-09-01
- Related: realm-範疇分區機制-v5, feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長

## 知識

- [臨] 專案 session 回報「跑 ~/.claude/tools 一律被擋」時先查 transcript 實錄指令：實證被擋的全帶 `2>&1`，裸跑放行。`_BASH_WRITE_OP_RE` 的 `>` 分支判寫檔，fd 複製 `2>&1`／`>&2` 須排除（lookahead `&\d`），`&> file`／`>& file` 仍是真寫檔。
- [臨] 開場 `[Guardian:*]` 提醒整批沒出現 → 先查 transcript 有無 `attachment.type=hook_cancelled`（`timedOut`/`durationMs`），不是先懷疑判定邏輯。SessionStart guardian 單跑 1.85s，實際 session 冷啟動 8.9～10.5s（多 hook＋MCP 同起 CPU 爭用）；timeout 太緊 = 所有 fail-open 提醒無聲消失，違反可觀測性鐵律卻無訊號。
- [臨] 另一 session 的「一律／整段不可用」是推論非事實：接到轉述的修 bug prompt，先用它的 transcript 重現，再定範圍。

## 行動

- 接到專案 session 轉述的閘門誤判 → 在 projects/<proj>/*.jsonl 撈 tool_use 指令 + tool_result 是否含 Block 標籤，餵 check_* 函數重現
- 開場提醒疑消失 → grep transcript `hook_cancelled`；逾時就調 settings.json timeout，不改判定邏輯
- 改 wg_core regex 必補 verify 案並跑 hooks/verify/verify_cross_realm_bash_guard.py
