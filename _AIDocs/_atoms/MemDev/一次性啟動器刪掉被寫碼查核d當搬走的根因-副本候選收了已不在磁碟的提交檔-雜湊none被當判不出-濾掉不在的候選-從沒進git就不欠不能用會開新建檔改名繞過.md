# 一次性啟動器刪掉被寫碼查核d當搬走的根因-副本候選收了已不在磁碟的提交檔-雜湊None被當判不出-濾掉不在的候選-從沒進git就不欠不能用會開新建檔改名繞過

- Scope: global
- Author: holylight
- Source: track-old-test-declare 2026-10-20 010（總控台代寫）
- Confidence: [臨]
- Trigger: MOVED_NEW_CODE_SEEN, 啟動器刪掉, 搬走的程式, 副本候選, vanished_code_paths, moved_copy_candidates, small_content_sha, 從沒進 git, gone_verdict, 一次性檔
- Created-at: 2026-10-20

## 知識

- [臨] 工作軌把一次性啟動器刪掉後被寫碼查核 (d) 擋 MOVED_NEW_CODE_SEEN（「已不存在、同根出現可能是它的副本」）的根因：`vanished_code_paths` 的副本候選收了本 session 提交後又被 git mv 掉的檔，磁碟上已不在、`small_content_sha` 回 None 被當「判不出」照算副本，任何刪掉的檔都被它拖成搬走。修法：副本候選先濾掉自己也不在磁碟的檔（真的搬過去的副本一定還在；hooks/wg_verify_ledger.py）。「從沒進 git＋本 session 新建＋已刪 → 不欠」這條不能用：會打開「新寫沒提交的檔用沒記帳的方式改名」的繞法（守門 test_0a_session_new_untracked_code_moved_still_owes）。

## 行動

- (d) 誤擋「搬走」時先看副本候選里有沒有磁碟上不存在的檔，不要放寬「從沒追蹤」這類條件
