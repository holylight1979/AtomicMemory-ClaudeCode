# 使用者放行的判定要防偽造-只認tool-use-id對到askuserquestion的答案-打字放行要整句嚴格比對-跨回合要承接

- Scope: global
- Author: holylight
- Source: workflow/v6-inbox/to-track-e/006-returned.md；session:59fc1054 2026-10-13（040／041）
- Quote: 「這session所有你學到的重要知識、經驗都記好的話，我就關掉了。」
- Confidence: [臨]
- Trigger: 收尾放行確認, 使用者放行, 放行判定, AskUserQuestion 答案, tool_use_id, 偽造放行, 否定句, pending_release, wg_release, 擋滿, 放行沒生效, transcript_path, turn_prompts_seq
- Created-at: 2026-10-12

## 知識

- [臨] 第一版被 codex 抓到三個「AI 自己能過」的洞：解析任何 tool_result 的 `"題"="答"` 文字（Bash 印出就能偽造）；打字放行只排除緊貼否定字；另送「好，放行」開新回合、預算歸零。正解：只採用 tool_use_id 對到 AskUserQuestion、題目含固定標記的答案；打字放行 NFKC 後整句比對；擋滿記 pending 跨回合承接。通則：「人同意了」的來源必須是 AI 產生不了的結構欄位。無法互動情境（子代理、headless、裁判）擋到底。
- [臨] 實走時放行仍無效，三個根因疊加：①只在擋滿（count≥max 或 pending）才查放行，第 1 次擋後就選放行被忽略，第 2 次擋又把擋位置推到答案之後；②預算與放行用 turn_seq 計，同伴 session 訊息、背景 task 通知都走 UserPromptSubmit 讓它 +1（Stop hook 回饋續跑不走），多 session 並行時永遠 count=1、擋不滿、放行換號就失效；③session 中途 EnterWorktree，transcript 改寫在新 cwd 的 projects 資料夾，Stop 用 state 開場 cwd 推路徑找不到 → 擋位置記 0、讀不到任何答案。
- [臨] 修法（v6/track-e7）：每次擋都查放行，只認最後一次擋之後的答案、放行後重記擋位置把答案用掉；回合以使用者打字開的回合計（turn_prompts_seq；通知開的續跑回合裡使用者第一則字仍算新回合）；Stop 先用 hook 輸入的 transcript_path。
- [臨] 診斷順序：state 的 last_block.offset 是 0 → transcript 沒找到；拿真 transcript 對 wg_release._answers_after 重算認得到 → Stop 讀錯檔；回合推進來源查 transcript 的 queued_command 附件與 Logs/guard-reconcile.jsonl 的 turn_seq→count。

## 行動

- （依知識內容判斷）
