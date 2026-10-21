# 驗收用乾淨資料根三坑-缺memory_meta詞表G6靜默退回舊詞表-索引0筆與健檢警告帶偏AI-試跑資料根放在系統repo內會被背景同步commit

- Scope: global
- Author: holylight
- Source: session 26d36367 track-wave2-kit（2026-10-21），w2_build_env 實跑與 wave2-kit 分支 5166ac00..f50c3f02
- Confidence: [臨]
- Trigger: 乾淨資料根, WG_CLAUDE_DIR, 驗收環境, forbidden-phrases.json, IndexZero, 資料根種卡, 試跑資料根, knowledge harvest 自動 commit, build_env
- Created-at: 2026-10-21
- Related: claude-p無頭跑會被hook判成無法互動-G9第二意見整條不觸發-預設CLAUDE_CODE_ENTRYPOINT=claude-vscode可保留但-p沒有AskUserQuestion
- Quote: 「track-某專案：你是工作軌 track-某專案，調度總控台是 claude-e3（送信前先 ListAgents 確認，名字會變）。第一步用 EnterWorktree 切進 C:\Users\holylight\.claude-wt\某專案（分支 某專案，已存在，不要新建；不存在就 SendMessage 調度要，不要自己建）。派工單在 C:\Users\holylight\.claude…」

## 知識

- [臨] wg_evasion 從資料根 memory/_meta/forbidden-phrases.json 讀宣稱詞、退避詞與不做行提示，缺檔不出聲退回程式裡寫死的 fallback；第一波驗收六個乾淨資料根（C:\w1、C:\w2）都沒這個檔，G6 驗的是舊詞表。建資料根要從 live 複製 forbidden-phrases.json、realm-lexicon.json、taxonomy.json（設定詞表，不是記憶卡）；不要複製 always-load-contracts.json（會對資料根裡不存在的必載檔告警）。
- [臨] 空 memory 一旦有任何 .md（如 episodic），開場自動重建索引得 0 筆 → IndexZero「跑 sync-atom-index 重建」，加上健檢 last-run 缺或紅燈，第一波 AI 被帶去修根層。解法：種一張中性卡並用 live 的 tools/sync-atom-index.py --memory-dir <root>/memory --add-from-frontmatter（WG_CLAUDE_DIR 指資料根）建索引、預寫 workflow/health-last-run.json 0 紅；實測開場只剩 Global: 1 atoms。
- [臨] 試跑資料根放在系統 repo（含其 worktree）裡、沒被 .gitignore 排掉時，背景記憶同步把 <任意路徑>/memory/** 當記憶卡自動 commit 進當前分支（實遇 4 筆 knowledge harvest 只碰 _w4_trial/**/memory/**）；放 repo 外或被忽略的目錄（如 jobs/）就不會。

## 行動

- 建驗收資料根：複製 config.json 與三個 _meta 詞表、種一張卡建索引、預寫健檢 last-run
- 試跑目的地選 repo 外或被 .gitignore 排掉的目錄，不放 worktree 根
