# 驗證探針的副作用與假失敗-heredoc反斜線-假session登記-dry-run留目錄-fallback索引源

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: 探針, 假失敗, 假紅, heredoc, 反斜線, node -e, 假 session, 實機驗證, dry-run 副作用, 探針副作用, 空目錄, parse_memory_index fallback, 驗證機制, post-mortem
- Created-at: 2026-08-31
- Related: 記憶索引分類讀寫鏈總審計結論-驗無誤清單與一條龍中斷點, 注入預算三教訓-裁切要回填-分級看token不看字元-橋接檔須隨索引重產

## 知識

- [臨] 始末：一連串記憶系統修正後用「真 hook 進程／node 直驅 js／py dry-run」做實機驗證，四次出現「看起來壞了」但其實是探針自己的問題：① bash heredoc 裡 JS 字串 "c:\\Projects" 的反斜線在工具層被吃掉→py 收到 c:Projects→走進「在 ~/.claude 底下」分支，讓「專案 cwd 禁寫 global」變成放行（改用正斜線後正確）；② 探針送 SessionStart 時 cwd=~/.claude，register_project 把 ~/.claude 登記成專案；③ py 的 _resolve_target 會 mkdir 落點，dry-run 在 c:\Projects 留下 shared/版控/Git、projects/Demo/… 空目錄；④ 新測試斷言「索引 JSON 壞掉就該沒結果」，但 parse_memory_index 有 _ATOM_INDEX.md/MEMORY.md fallback → 假紅。
- [臨] 根因：把探針當成「只讀的觀察」，沒意識到它本身也走實機寫入路徑（登記表、mkdir、access sidecar 曝光計數、state 檔、injection-turns.jsonl）；且探針的輸入經過 bash→檔→node→JSON→py 四層轉譯，反斜線這類字元任一層吃掉就改變語意，輸出卻還是「合理」的拒寫訊息，很難一眼看出。
- [臨] 設計原理：_resolve_target 在定位時就 mkdir，是為了 create 後的寫檔零分支；register_project 在 SessionStart 登記，是為了跨專案掃描；都是對真 session 合理、對探針有副作用的設計。parse_memory_index 的三源 fallback 是容錯，不是真相源——測試要測「不再回舊快取」而非「回空」。
- [臨] 防再犯：① 探針路徑一律正斜線，或直接用 py 呼叫不經 heredoc；看到拒寫訊息先檢查它印出的 cwd 字串是不是你給的；② 探針結束必做三清：workflow/state-<sid>.json、injection-turns.jsonl 假 session 列、memory/project-registry.json 新垃圾；③ dry-run 後到目標 repo 跑 git status / 找空目錄 rmdir；④ 斷言寫「不含舊值」而非「為空」；⑤ 審計報告記得把「探針副作用」列進 (a) 誠實揭露。

## 行動

- 實機探針用正斜線路徑；結果異常先檢視輸入字串有沒有被吃
- 探針後三清（state / jsonl / registry）並 rmdir 空目錄
- 測試斷言寫「不再含舊結果」，不假設 fallback 不存在
