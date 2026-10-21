# 讀取點從家目錄改走資料根時寫死家目錄的舊測試會一起紅-conftest把WG_CLAUDE_DIR隔離成暫存根-改merge-atom-index會重錄git錄製檔

- Scope: global
- Author: holylight
- Source: session b009a8ab 2026-10-20 track-config-consistency 派工 002 commit 03327f72
- Confidence: [臨]
- Trigger: claude_data_dir, Path.home() / .claude, 資料根改寫, CLAUDE_DIR, WG_CLAUDE_DIR 隔離, 舊測試寫死家目錄, git 錄製檔重錄, cassette 重錄, merge-atom-index 改動
- Created-at: 2026-10-20
- Quote: 「track-config-consistency：你是工作軌 track-config-consistency，總控台是 claude-e3（送信前先 ListAgents 確認，名字會變）。第一步用 EnterWorktree 切進 C:\Users\holylight\.claude-wt\config-consistency（分支 config-consistency，已存在，不要新建；不…」

## 知識

- [臨] repo 根 conftest.py 每個 pytest session 都把 WG_CLAUDE_DIR 指到暫存資料根。把讀取點從 `Path.home()/".claude"` 改成 CLAUDE_DIR／claude_data_dir() 後，自己也寫死家目錄當核心根的舊測試會一起紅（G8 實例：verify_cross_realm_guard 9 案、cross_realm_bash_guard 1 案、git_privacy_gate 1 案）。改法：測試常數改成 wg_core.CLAUDE_DIR、斷言不變，先宣告「改舊測試｜…」。
- [臨] tools/merge-atom-index.py 是 git 錄製檔的程式依賴：改它會讓 verify_vcs_sync_worker 與 verify_merge_atom_index 約 100 個錄製檔重錄（跑真 git），錄製檔要一起提交。重錄時在重負載下偶發過一次 resolver 未解開；單跑、off 模式、整檔重跑都是綠。

## 行動

- 改資料根讀取點前先 grep 測試裡的 Path.home() / ".claude"，同一筆一起改並宣告
- 改了 merge-atom-index.py 後整檔跑那兩支 verify，提交重錄的錄製檔
