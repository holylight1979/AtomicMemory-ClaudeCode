# 換資料根跑時要帶memory-meta三個詞表-缺檔守門靜默退回程式寫死的舊詞表-repo內任何memory資料夾都會被背景同步當記憶卡自動commit

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: WG_CLAUDE_DIR, 換資料根, forbidden-phrases.json, realm-lexicon.json, taxonomy.json, 詞表退回, 索引 0 筆, 試跑資料根, 背景同步自動 commit, memory 資料夾被 commit
- Created-at: 2026-10-29
- Supersedes: 驗收用乾淨資料根三坑-缺memory-meta詞表g6靜默退回舊詞表-索引0筆與健檢警告帶偏ai-試跑資料根放在系統repo內會被背景同步commit
- Source: session:bc7c5340#13bc0220 2026-10-29
- Quote: 「幾個額外整理.. DevHistory/ "這一層" 下的散檔是否還能歸類資料夾? 舉例像是 有 "v4-conflict、v4-layers.. " 這種帶著版號的檔名，看起來很刺眼 (如果是 v4 的為什麼不是塞進 v4 資料夾內 ?)；以及 ab-test.. 這種看起來就都是可以歸類進資料夾的.. 要改掉，但也要確認過 是否系統內、或其他文件 有 針對這些路徑或檔名做了什麼特殊的寫死、連…」

## 知識

- [臨] wg_evasion 從資料根 memory/_meta/forbidden-phrases.json 讀宣稱詞、退避詞與不做行提示，缺檔不出聲退回程式裡寫死的舊詞表。用 WG_CLAUDE_DIR 换資料根跑（測試、雔離環境）要從 live 複製 forbidden-phrases.json、realm-lexicon.json、taxonomy.json 三個詞表；不要複製 always-load-contracts.json。
- [臨] 空的 memory/ 開場會出「索引 0 筆、跑 sync-atom-index 重建」與健檢警告，會把 AI 帶去修根層；要帶卡就照 live 索引複製再 --rebuild 重建，並預寫健檢 last-run。
- [臨] 資料根或試跑目錄放在系統 repo（含 worktree）裡、沒被 .gitignore 排掉時，背景記憶同步會把 <任意路徑>/memory/** 當記憶卡自動 commit 進當前分支；放 repo 外或被忽略的目錄（例 jobs/）就不會。

## 行動

- 换資料根跑：複製 config.json 與三個 _meta 詞表，帶卡就 --rebuild 重建索引、預寫健檢 last-run
- 試跑目的地選 repo 外或被 .gitignore 排掉的目錄，不放 worktree 根
