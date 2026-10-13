# hook-state跨行程三方合併要依欄位業務語意分型-通用合併會破壞去重鍵-事件序號-分回合版本

- Scope: global
- Author: holylight
- Source: v6/track-b3 94a3c8a→7494909→f6d6676；workflow/v6-inbox/from-track-b3/001-codex-review.md、003-codex-review.md（2026-10-13）
- Confidence: [臨]
- Trigger: write_state, state 並行, state 互相覆蓋, 三方合併, _merge_state, event_seq, next_event_seq, modified_files 合併, verify_receipts 合併, knowledge_harvest 合併, pending 版本, 鎖內重讀, track-b3
- Created-at: 2026-10-13
- Related: 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞
- Quote: 「你是 v6.0 的工作 session track-b3，總控台是 claude-2c。第一步用 EnterWorktree 切進 worktree C:\Users\holylight\.claude-wt\track-b3（分支 v6/track-b3，已存在，不要新建）。派工 prompt 在 C:\Users\holylight\.claude\workflow\v6-inbox\to-…」

## 知識

- [臨] 背景：多支 hook 行程同時對 state-<sid>.json 讀→改→寫，後寫者洗掉先寫者。b3 試過「鎖內重讀磁碟＋三方合併」，codex 審了兩輪都 BLOCK，b3 排出 v6.0，分支 v6/track-b3 停在 f6d6676 給維護軌。
- [臨] 通用 dict／list／max 合併會弄壞欄位語意，每個鍵都要先分型：
- [臨] 業務鍵紀錄：modified_files 與 agent_modified_files[*] 以 (path, session_id) 為一筆，count＝base＋兩邊增量。
- [臨] 要有事件身分的序列：verify_receipts（seq）、turn_prompts／recent_user_prompts、atom_ops[sid]／atom_ops_seq。依事件順序合併後才截窗；prompt 目前沒有事件 id，同文字與先後無法辨識。
- [臨] 累加計數＝base＋兩邊增量：turn_seq、stop_blocked_count、edit_counts[path]、topic_tracker.prompt_count、sync_reminder_count。
- [臨] 分版本整組：reconcile_gate_turn[sid] 看 turn，overview_hub[key] 看 injected_turn，knowledge_harvest[sid] 的 validated 不可與 items／pending 拆開。版本新的整組勝，「重設為 0」也算新版本。
- [臨] 一次性事件 pending_*：要用唯一 generation 當版本，秒級 _now_iso 會撞。failing_tests 的清除也要當成事件記，否則已清掉的失敗會被舊快照救活。
- [臨] 序號陷阱：合併時替 event_seq 挪號只保證不重號，不保證先後。receipt.seq > edit.seq 會在「同秒＋落盤順序與完成順序相反」時誤判驗證在修改後。對外用的序號必須在同一把鎖內配置並記錄；已輸出的事件身分不可事後改號。
- [臨] 失敗語意有兩面：拿不到鎖、重讀失敗、壞 JSON 時不可退回覆蓋；但放棄寫入會讓閘誤擋或漏擋（收據、改檔紀錄遺失）。沒有快照的路徑（sibling 重讀失敗、new_state）也要在鎖內確認目的檔不存在，才能整份寫。
- [臨] 實作陷阱一：在呼叫端 dict 上就地合併，replace 失敗後再重試，會把對方的增量再算一次。要先合併到候選 dict，replace 成功後才同步呼叫端與 base。
- [臨] 實作陷阱二：「兩邊改成同一個值」不等於沒衝突，兩邊各自 +1 會長得一樣。
- [臨] 兩輪審查一致的方向：序號配置與紀錄放在同一把鎖保護的讀改寫內；只在寫入前事後合併，補不完語意。全文見 workflow/v6-inbox/from-track-b3/001-codex-review.md 與 003-codex-review.md。

## 行動

- 改 write_state 或任何 state 合併前：先列每個鍵屬於哪一型（業務鍵／事件序列／累加／分版本／一次性事件），沒列名的鍵不可走通用規則就宣稱不覆蓋
- 要對外比先後的序號（event_seq、seq、last_seq）只在鎖內配置，不在合併時重編
