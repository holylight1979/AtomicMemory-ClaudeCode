# 驗收用乾淨資料根三坑-缺memory-meta詞表g6靜默退回舊詞表-索引0筆與健檢警告帶偏ai-試跑資料根放在系統repo內會被背景同步commit

- Scope: global
- Author: holylight
- Source: session 26d36367 track-wave2-kit（2026-10-21），w2_build_env 實跑與 wave2-kit 分支 5166ac00..f50c3f02
- Quote: 「track-某專案：你是工作軌 track-某專案，調度總控台是 claude-e3（送信前先 ListAgents 確認，名字會變）。第一步用 EnterWorktree 切進 C:\Users\holylight\.claude-wt\某專案（分支 某專案，已存在，不要新建；不存在就 SendMessage 調度要，不要自己建）。派工單在 C:\Users\holylight\.claude…」
- Confidence: [臨]
- Trigger: 乾淨資料根, WG_CLAUDE_DIR, 驗收環境, forbidden-phrases.json, IndexZero, 資料根帶卡, 試跑資料根, knowledge harvest 自動 commit, build_env, 洩題卡
- Created-at: 2026-10-21
- Related: claude-p無頭跑會被hook判成無法互動-G9第二意見整條不觸發-預設CLAUDE_CODE_ENTRYPOINT=claude-vscode可保留但-p沒有AskUserQuestion

## 知識

- [臨] wg_evasion 從資料根 memory/_meta/forbidden-phrases.json 讀宣稱詞、退避詞與不做行提示，缺檔不出聲退回程式裡寫死的 fallback。建驗收資料根要從 live 複製 forbidden-phrases.json、realm-lexicon.json、taxonomy.json（設定詞表，不是記憶卡）；不要複製 always-load-contracts.json。
- [臨] 空 memory 會讓開場出「索引 0 筆、跑 sync-atom-index 重建」，健檢 last-run 缺或紅燈也會出警告，兩條都把 AI 帶去修根層；且受測時一張記憶卡都進不來，量不到「卡有沒有教會它」。解法：照 live 索引把 memory/ 底下的全域卡帶進資料根（personal 與 _AIDocs/_atoms 不帶）、用 --rebuild 重建索引、預寫 workflow/health-last-run.json 0 紅；帶的是建環境那一刻的 live，實跑前重建。
- [臨] 帶卡要排除講驗收題本身的卡（題目怎麼藏、驗收經過與判錯、代打的原句、指路到答案資料夾的）。注入時只送觸發詞、知識、行動，不送 Source／ Quote，所以洩題字只在 Source 的切入點卡可以帶；字面命中「受測」「題組」多半是一般用語。自檢要把「命中洩題字樣、又沒判過」的新卡擋下來，因為 live 還在長卡。
- [臨] 試跑資料根放在系統 repo（含其 worktree）裡、沒被 .gitignore 排掉時，背景記憶同步會把 <任意路徑>/memory/** 當記憶卡自動 commit 進當前分支；放 repo 外或被忽略的目錄（例 jobs/）就不會。

## 行動

- 建驗收資料根：複製 config.json 與三個 _meta 詞表、帶 live 全域卡並排除洩題卡、--rebuild 重建索引、預寫健檢 last-run
- 試跑目的地選 repo 外或被 .gitignore 排掉的目錄，不放 worktree 根
