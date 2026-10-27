# hook-state跨行程三方合併要依欄位業務語意分型-通用合併會破壞去重鍵-事件序號-分回合版本

- Scope: global
- Author: holylight
- Source: v6/track-b3 94a3c8a→7494909→f6d6676；workflow/v6-inbox/from-track-b3/001-codex-review.md、003-codex-review.md（2026-10-13）；2026-10-23 state 讀改寫握鎖修補實測
- Confidence: [臨]
- Trigger: write_state, state 並行, state 互相覆蓋, 三方合併, _merge_state, _MERGE_TYPES, event_seq, next_event_seq, modified_files 合併, verify_receipts 合併, knowledge_harvest 合併, pending 版本, 鎖內重讀, 待併帳併回, STATE_PENDING_MERGED, 計數歸零
- Created-at: 2026-10-13
- Related: 活躍session的state被fallback覆蓋-讀失敗不等於遺失且working-ttl-30分太短-多sub-agent共用session-id時必撞, 平行hook讀改寫session-state要整段握鎖-寫時重讀再合併只當拿不到鎖的退路-鎖內只有50到80ms, state待併帳退路的不變量-基準記讀到的原文與指紋-自己的帳沒落盤只能再留帳-併過帳名與結果同次落盤-不轉給別的session

## 知識

- [臨] 背景：多支 hook 行程同時對 state-<sid>.json 讀→改→寫，後寫者洗掉先寫者。主路徑是整段握鎖（讀→改→寫與序號配置都在 session 鎖裡）；三方合併只用在兩個退路：拿不到鎖留下的待併帳要併回、沒進 hook 模式的寫者在鎖裡發現檔被換過。以下分型是退路的規則，實作在 hooks/wg_core 的 _merge_state／_MERGE_TYPES。
- [臨] 通用 dict／list／max 合併會弄壞欄位語意，每個鍵都要先分型：
- [臨] 業務鍵紀錄：modified_files 與 agent_modified_files[*] 以 (path, session_id) 為一筆，count＝base＋兩邊增量。
- [臨] 要有事件身分的序列：verify_receipts（seq）、turn_prompts／recent_user_prompts、atom_ops[sid]／atom_ops_seq。依事件順序合併後才截窗；prompt 目前沒有事件 id，同文字與先後無法辨識。
- [臨] 累加計數＝base＋兩邊增量：edit_counts[path]、stop_blocked_count、sync_reminder_count、topic_tracker.prompt_count、各筆 count；可歸零的計數有一邊比 base 小（被歸零）就取小的，不相加。回合與序號（turn_seq 這類）取大。
- [臨] 分版本整組：reconcile_gate_turn[sid] 看 turn，overview_hub[key] 看 injected_turn，knowledge_harvest[sid] 的 validated 不可與 items／pending 拆開。版本新的整組勝，「重設為 0」也算新版本。
- [臨] 一次性事件 pending_*：要用唯一 generation 當版本，秒級 _now_iso 會撞。failing_tests 的清除也要當成事件記，否則已清掉的失敗會被舊快照救活。
- [臨] 序號陷阱：合併時替 event_seq 挪號只保證不重號，不保證先後。receipt.seq > edit.seq 會在「同秒＋落盤順序與完成順序相反」時誤判驗證在修改後。對外用的序號必須在同一把鎖內配置並記錄；已輸出的事件身分不可事後改號。
- [臨] 失敗語意有兩面：拿不到鎖、重讀失敗、壞 JSON 時不可退回整份覆蓋，也不可放棄寫入（收據、改檔紀錄遺失會讓閘誤擋或漏擋），所以拿不到鎖改留待併帳。fallback 重建的 state 在鎖裡發現檔已存在就不寫、改用磁碟那份；沒讀過檔就寫（合併轉址、測試造檔）才照整份寫。
- [臨] 實作陷阱一：在呼叫端 dict 上就地合併，replace 失敗後再重試，會把對方的增量再算一次。要先合併到候選 dict，replace 成功後才同步呼叫端與 base。
- [臨] 實作陷阱二：「兩邊改成同一個值」不等於沒衝突，兩邊各自 +1 會長得一樣。
- [臨] 序號配置與紀錄要在同一把鎖保護的讀改寫內；只在寫入前事後合併補不完語意，所以合併只當退路（見整段握鎖那張卡）。

## 行動

- 改 write_state 或任何 state 合併前：先列每個鍵屬於哪一型（業務鍵／事件序列／累加／分版本／一次性事件），沒列名的鍵不可走通用規則就宣稱不覆蓋
- 要對外比先後的序號（event_seq、seq、last_seq）只在鎖內配置，不在合併時重編
