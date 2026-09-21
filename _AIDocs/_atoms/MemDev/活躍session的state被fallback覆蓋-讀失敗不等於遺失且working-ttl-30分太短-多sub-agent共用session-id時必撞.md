# 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: state 已重建, fallback state, state 遺失, turn_seq 歸零, read_state, _ensure_state, _cleanup_old_states, state TTL, 歷史歸零, sub-agent 共用 session_id, PermissionError state, read_state_status
- Created-at: 2026-09-21
- Related: memory-pipeline-silent-failure-2026-05, 糾正與失敗偵測把sub-agent完成通知當使用者輸入-task-notification整則進ups-引用的糾正詞誤觸deeppostmortem, 併發-session-共用工作樹-收尾選擇性-staging-勿-git-add-a

## 知識

- [臨] 始末（2026-09-21 全面檢視 session）：主持 session 進行到 turn 15、同時有 5 支 sub-agent 在跑，UPS 突然回報「state 已重建（原 state 遺失/被 TTL 清除）」，state 檔 source 變 fallback、turn_seq 歸 1，注入→效用→AEC 的整場歷史全失，atom-debug 沒有任何 ERROR。
- [臨] 根因有兩個、互相獨立：① `wg_core.read_state` 把「檔在但讀失敗」（另一支 hook 正 tmp+replace 或 msvcrt 鎖檔、JSON 半寫）與「檔不存在」都回 None，`_ensure_state` 就建 fallback 並 write_state 覆蓋真的 state——sub-agent 的 hook 用父 session 的 session_id，5 支一起跑 PostToolUse 就是 6 個寫者對同一檔；② `handlers/_shared._cleanup_old_states` 對「有 prompt 的 working state」30 分鐘沒寫就刪，使用者在想、或在等長背景任務就中招；它由任何 session 的 SessionStart/SessionEnd 觸發，所以是別的 session 刪你的。
- [臨] 設計原理：fallback 重建是為了 SessionStart 沒跑到（例如 hook 逾時）的 session 仍能有最小索引；TTL 清理是為了孤兒 state 不無限堆。兩者都把「讀不到」當「不存在」，在單一寫者、短 session 的假設下成立，在多 sub-agent、長 session 下就崩。
- [臨] 修法：`read_state_status()` 回 (state, ok|missing|error)；`_ensure_state` 遇 error 重試三次（30ms）、仍失敗就本次 hook 回 None（呼叫端 output_nothing）、落 ERROR log、絕不建 fallback；`_ACTIVE_WORKING_TTL_S` 6 小時（CC 正常結束走 SessionEnd 標 done，TTL 只兜底孤兒）。verify_state_loss_guard.py 4 案。
- [臨] 防再犯：任何「讀不到就重建」的自癒邏輯，先分辨 missing 與 error；error 一律重試後放棄本次，不得覆寫；TTL 別拿「檔多久沒寫」當「session 已死」的證據，CC 有 SessionEnd 事件就該用它。看到「state 已重建」提示→先查 state 檔 mtime 距今與同時間有沒有 sub-agent 在跑。

## 行動

- 看到 [Guardian] state 已重建：先查 workflow/state-<sid>.json 的 source/started_at 與同時段的 sub-agent，不要當成正常 TTL
- 寫自癒／重建邏輯：先分 missing 與 error，error 只重試不覆寫
- 多 sub-agent 共用 session_id 的場景，state 寫入要當成多寫者設計
